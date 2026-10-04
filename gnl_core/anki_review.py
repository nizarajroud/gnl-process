"""Detection of failed Anki questions (base for the "questions ratées" feature).

Reads the user's Anki collection to find cards whose LAST review was "Again"
(ease = 1 => wrong answer), maps them back to our exam + question number via the
card GUID (`{exam-name}-q{num}`), and groups them by exam.

Lock-safe: Anki locks collection.anki2 while open, so we always read a COPY.

Used by:
  - Artefact 1 (#51): error-review markdown document per exam
  - Artefact 2 (#52): reset .apkg per exam

TEST_MODE returns a deterministic stub (no real collection access).
"""

import os
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path
from collections import defaultdict


DEFAULT_ANKI_COLLECTION = os.environ.get(
    'ANKI_COLLECTION',
    '/mnt/c/Users/nizar/AppData/Roaming/Anki2/nizar/collection.anki2',
)

# GUID format produced by step5_anki: "{exam-name}-q{num}"
_GUID_RE = re.compile(r'^(?P<exam>.+)-q(?P<num>\d+)$')


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def _read_failed_guids(collection_path):
    """Return the list of GUIDs the user marked as WRONG.

    Source of truth = the Anki RED FLAG (cards.flags = 1). The user flags a
    card red to mark a missed question. This works even for 'New' cards that
    were never reviewed (no revlog entry), which is why we do NOT rely on
    revlog anymore.

    Copies the collection to a private temp dir INCLUDING the -wal and -shm
    sidecar files, so recent flags (still in the Write-Ahead Log while Anki is
    OPEN) are included. Opens the copy read-write so SQLite checkpoints the
    WAL. The user does NOT need to close Anki. Everything is cleaned up after.
    """
    if not os.path.exists(collection_path):
        return []

    workdir = tempfile.mkdtemp(prefix='anki-review-')
    tmp_db = os.path.join(workdir, 'collection.anki2')
    guids = []
    conn = None
    try:
        # Copy main DB + WAL + SHM (WAL holds Anki's in-flight edits/flags).
        shutil.copy2(collection_path, tmp_db)
        for ext in ('-wal', '-shm'):
            src = collection_path + ext
            if os.path.exists(src):
                try:
                    shutil.copy2(src, tmp_db + ext)
                except Exception:
                    pass
        # Read-WRITE so SQLite applies (checkpoints) the WAL into our copy.
        conn = sqlite3.connect(tmp_db)
        # flags & 7 == 1 -> RED flag (Anki stores the flag color in the low
        # 3 bits of cards.flags). Distinct guids across a note's cards.
        rows = conn.execute(
            """
            SELECT DISTINCT n.guid
            FROM cards c
            JOIN notes n ON n.id = c.nid
            WHERE (c.flags & 7) = 1
            """
        ).fetchall()
        guids = [row[0] for row in rows]
    except Exception:
        guids = []
    finally:
        if conn:
            conn.close()
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass
    return guids


def failed_questions_by_exam(collection_path=None):
    """Return {exam_name: sorted[list of failed question numbers (int)]}.

    In TEST_MODE, returns a deterministic stub.
    """
    if _is_test_mode():
        return {"test-exam": [1, 3]}

    collection_path = collection_path or DEFAULT_ANKI_COLLECTION
    guids = _read_failed_guids(collection_path)
    by_exam = defaultdict(set)
    for guid in guids:
        m = _GUID_RE.match(guid or '')
        if not m:
            continue
        by_exam[m.group('exam')].add(int(m.group('num')))
    return {exam: sorted(nums) for exam, nums in by_exam.items()}


# --- Artefact 1 (#51): error-review markdown document -------------------------

def _find_exam_markdown(exam_name, theme='exams', subtheme='sap-c02'):
    """Locate the full-markdown source for an exam. Returns Path or None."""
    # Ensure config is loaded so INBOX_FOLDER is present in the environment.
    inbox = os.environ.get('INBOX_FOLDER', '')
    if not inbox:
        try:
            from gnl_core.config import get_config
            inbox = get_config().get('INBOX_FOLDER', '')
        except Exception:
            inbox = ''
    if not inbox:
        return None
    # Standard path: {inbox}/{theme}/{subtheme}/assets/pdf-formatting/full-markdown/<exam>.md
    candidate = Path(inbox) / theme / subtheme / 'assets' / 'pdf-formatting' / 'full-markdown' / f'{exam_name}.md'
    if candidate.exists():
        return candidate
    # Fallback: search under inbox for <exam>.md in a full-markdown folder
    root = Path(inbox)
    if root.is_dir():
        for p in root.glob(f'**/full-markdown/{exam_name}.md'):
            return p
    return None


def parse_exam_questions(md_path):
    """Parse an exam markdown into {qnum: {'body': str, 'explanation': str}}.

    A question block starts at '## Question N:' and its explanation is the text
    under the 'Explanations:' marker (until the next '## Question' or EOF).
    """
    text = Path(md_path).read_text(encoding='utf-8', errors='ignore')
    # Split keeping the question numbers
    parts = re.split(r'##\s*Question\s+(\d+)\s*:', text)
    questions = {}
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        num = int(parts[i])
        block = parts[i + 1]
        # Split body vs explanation on the 'Explanations:' marker
        m = re.search(r'\n\s*Explanations?:\s*\n', block)
        if m:
            body = block[:m.start()].strip()
            explanation = block[m.end():].strip()
        else:
            body = block.strip()
            explanation = ''
        questions[num] = {'body': body, 'explanation': explanation}
    return questions


def build_error_document(exam_name, failed_nums, md_path, out_path=None):
    """Build a markdown error-review document for one exam's failed questions.

    Returns the output path, or None if nothing to write. Never raises.
    """
    if _is_test_mode():
        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_text(f"# {exam_name} — erreurs (TEST)\n", encoding='utf-8')
        return out_path

    try:
        questions = parse_exam_questions(md_path)
        lines = [f"# {exam_name} — Questions ratées ({len(failed_nums)})\n"]
        written = 0
        for num in failed_nums:
            q = questions.get(num)
            if not q:
                lines.append(f"\n## Question {num}\n\n_(introuvable dans le markdown source)_\n")
                continue
            lines.append(f"\n## Question {num}\n")
            lines.append(q['body'])
            if q['explanation']:
                lines.append(f"\n**Explication :**\n")
                lines.append(q['explanation'])
            lines.append("\n---\n")
            written += 1
        if written == 0 and not failed_nums:
            return None
        if out_path is None:
            out_path = str(Path(md_path).parent.parent.parent / 'erreurs' / f'{exam_name}-erreurs.md')
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("\n".join(lines) + "\n", encoding='utf-8')
        return out_path
    except Exception:
        return None


def generate_error_documents(collection_path=None, theme='exams', subtheme='sap-c02', on_progress=None):
    """For every exam with failed questions, generate its error-review document.

    Returns list of (exam_name, out_path). Best-effort; never raises.
    """
    results = []
    try:
        by_exam = failed_questions_by_exam(collection_path)
        for exam_name, nums in by_exam.items():
            md = _find_exam_markdown(exam_name, theme, subtheme)
            if not md:
                if on_progress:
                    on_progress(f"  ⚠ markdown source introuvable pour {exam_name}")
                continue
            out = build_error_document(exam_name, nums, str(md))
            if out:
                results.append((exam_name, out))
                if on_progress:
                    on_progress(f"  ✓ {exam_name}: {len(nums)} erreur(s) → {out}")
    except Exception as e:
        if on_progress:
            on_progress(f"  ⚠ generate_error_documents: {str(e)[:60]}")
    return results


# --- Artefact 2 (#52): reset .apkg of failed questions -----------------------

def generate_reset_apkg(exam_name, failed_nums, theme='exams', subtheme='sap-c02', on_progress=None):
    """Generate a RESET .apkg containing only the failed questions (2nd pass).

    Distinct GUIDs (`{exam}-r2-qN`) so Anki treats them as brand-new cards.
    Reuses the exam highlight (step3) + step5_anki with filter/suffixes.
    Returns the apkg path, or None. Best-effort.
    """
    if _is_test_mode():
        return f"/tmp/{exam_name}-round2.apkg"
    try:
        md = _find_exam_markdown(exam_name, theme, subtheme)
        if not md:
            if on_progress:
                on_progress(f"  ⚠ markdown source introuvable pour {exam_name}")
            return None
        from gnl_core.exams import step3_highlight, step5_anki
        # Only highlight the failed questions (avoids re-analysing the whole
        # exam through Bedrock just to keep a handful of questions).
        answers = step3_highlight(str(md), on_progress=on_progress,
                                  only_questions=failed_nums)
        out = step5_anki(
            answers, str(md), theme, subtheme, on_progress=on_progress,
            only_questions=failed_nums,           # only the failed ones
            guid_suffix='-r2',                    # distinct GUIDs -> reset
            deck_suffix=' — Round 2',             # distinct deck name
            apkg_suffix='-round2',                # distinct file name
        )
        if on_progress:
            on_progress(f"  ✓ {exam_name}: reset apkg ({len(failed_nums)} Q) → {out}")
        return str(out)
    except Exception as e:
        if on_progress:
            on_progress(f"  ⚠ generate_reset_apkg({exam_name}): {str(e)[:60]}")
        return None


def generate_reset_apkgs(collection_path=None, theme='exams', subtheme='sap-c02', on_progress=None):
    """For every exam with failed questions, generate a reset .apkg. Returns list of (exam, path)."""
    results = []
    try:
        for exam_name, nums in failed_questions_by_exam(collection_path).items():
            out = generate_reset_apkg(exam_name, nums, theme, subtheme, on_progress)
            if out:
                results.append((exam_name, out))
    except Exception as e:
        if on_progress:
            on_progress(f"  ⚠ generate_reset_apkgs: {str(e)[:60]}")
    return results


# --- Practice-exam .docx format parser -------------------------------------
# Structure (per question, 75 total):
#   Paragraphs: "Question N" / "Multiple Choice" / "Answer status:" / <status>
#               / "Question" / <statement paras...> / "Answer options"
#   Table (4 cols): Option | Correct answer | Your selection | Rationale
#     - Option:         "A. ...", "B. ...", ...
#     - Correct answer: "Correct" on the right row(s), else empty
#     - Your selection: "Selected" / "Not selected"  (the user's own answer)
#     - Rationale:      per-option explanation (correct AND incorrect)

def parse_practice_exam(docx_path):
    """Parse a practice-exam .docx into a list of question dicts.

    Returns: list of {
        'num': int, 'status': 'Correct'|'Incorrect'|'',
        'statement': str,
        'options': [ {'letter': 'A', 'text': str, 'correct': bool,
                      'selected': bool, 'rationale': str}, ... ]
    }
    Best-effort; skips malformed blocks. Requires python-docx.
    """
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(docx_path)

    def iter_blocks(parent):
        for child in parent.iterchildren():
            if child.tag == qn('w:p'):
                yield ('p', Paragraph(child, doc))
            elif child.tag == qn('w:tbl'):
                yield ('tbl', Table(child, doc))

    blocks = list(iter_blocks(doc.element.body))
    questions = []
    i = 0
    n = len(blocks)
    while i < n:
        kind, el = blocks[i]
        if kind == 'p' and re.match(r'^Question\s+\d+\s*$', el.text.strip()):
            num = int(re.search(r'\d+', el.text).group())
            status = ''
            statement_lines = []
            in_statement = False
            j = i + 1
            # walk paragraphs until we hit the option table
            while j < n:
                k2, e2 = blocks[j]
                if k2 == 'tbl':
                    break
                if k2 == 'p':
                    t = e2.text.strip()
                    if re.match(r'^Question\s+\d+\s*$', t):
                        break  # next question with no table (safety)
                    if t == 'Answer status:':
                        # status is the next non-empty paragraph
                        pass
                    elif t in ('Correct', 'Incorrect') and status == '':
                        status = t
                    elif t == 'Question':
                        in_statement = True
                    elif t == 'Answer options':
                        in_statement = False
                    elif in_statement and t:
                        statement_lines.append(t)
                j += 1
            # parse the option table if present
            options = []
            if j < n and blocks[j][0] == 'tbl':
                tbl = blocks[j][1]
                rows = tbl.rows
                if rows and rows[0].cells[0].text.strip().lower() == 'option':
                    for r in rows[1:]:
                        cells = r.cells
                        opt_text = cells[0].text.strip()
                        m = re.match(r'^([A-Z])\.\s*(.*)', opt_text, re.S)
                        letter = m.group(1) if m else ''
                        text = (m.group(2).strip() if m else opt_text)
                        correct = cells[1].text.strip().lower() == 'correct'
                        selected = cells[2].text.strip().lower() == 'selected'
                        rationale = cells[3].text.strip() if len(cells) > 3 else ''
                        options.append({
                            'letter': letter, 'text': text,
                            'correct': correct, 'selected': selected,
                            'rationale': rationale,
                        })
                i = j  # advance to the table; outer loop will move past it
            questions.append({
                'num': num, 'status': status,
                'statement': '\n'.join(statement_lines).strip(),
                'options': options,
            })
        i += 1
    return questions


# --- Meta AI prompt for failed questions, per exam (copy-by-block) -----------

_VOICE_PREAMBLE = (
    "I'm studying for the AWS SAP-C02 exam. Below are the questions I FAILED, "
    "with their options and explanations. For now, just RECEIVE and KEEP "
    "everything in memory across the blocks I paste, and reply ONLY \"Block K "
    "received.\" after each. When I say \"ALL BLOCKS SENT\", reply ONLY "
    "\"Ready — say 'go'.\" Then, the moment I say ANYTHING (even just \"go\"), "
    "IMMEDIATELY walk me through EACH failed question in order, in one flowing "
    "spoken-style explanation (no questions back, no waiting): for each, why the "
    "correct answer is right and why the wrong options are wrong. Plain, easy to "
    "listen to, no tables."
)


def _failed_corpus_for_exam(exam_name, failed_nums, md_path):
    """Build the plain-text corpus of an exam's failed questions (body +
    explanation), ready to be split into Meta AI blocks. Returns str."""
    questions = parse_exam_questions(md_path)
    chunks = [f"FAILED QUESTIONS — {exam_name} ({len(failed_nums)})\n"]
    for num in failed_nums:
        q = questions.get(num)
        if not q:
            continue
        chunks.append(f"\n## Question {num}\n{q['body']}")
        if q.get('explanation'):
            chunks.append(f"\nExplanations:\n{q['explanation']}")
        chunks.append("\n---\n")
    return "\n".join(chunks)


def build_failed_meta_parts(collection_path=None, theme='exams',
                            subtheme='sap-c02', max_chars=None, on_progress=None):
    """For each exam with failed questions, build a Meta AI prompt split into
    copy blocks. Returns {exam_name: {'count': n, 'parts': [str, ...]}}.

    Reuses the generic block splitter (build_parts_from_text) and the voice
    preamble so the user pastes block-by-block, then says 'go' for the full
    explanation of all failed questions.
    """
    from gnl_core.meta_export import build_parts_from_text
    result = {}
    by_exam = failed_questions_by_exam(collection_path)
    for exam_name, nums in by_exam.items():
        md = _find_exam_markdown(exam_name, theme, subtheme)
        if not md:
            if on_progress:
                on_progress(f"  ⚠ markdown source introuvable pour {exam_name}")
            continue
        corpus = _failed_corpus_for_exam(exam_name, nums, str(md))
        if not corpus.strip():
            continue
        parts = build_parts_from_text(corpus, max_chars=max_chars,
                                      prompt_template=_VOICE_PREAMBLE)
        result[exam_name] = {'count': len(nums), 'parts': parts}
        if on_progress:
            on_progress(f"  ✓ {exam_name}: {len(nums)} ratées → {len(parts)} bloc(s)")
    return result


# --- Podcast of failed questions, per exam (uses category defaults) ---------

def generate_failed_podcasts(collection_path=None, theme='exams',
                             subtheme='sap-c02', on_progress=None):
    """For each exam with failed questions, build an error-doc PDF and prepare it
    into the production DB (split + collect + titles) using the exams CATEGORY
    DEFAULTS. Returns list of {'exam','parent_id','count'}.

    This is the QUOTA-FREE prepare phase; the actual NotebookLM audio generation
    then runs via the normal production flow (like any prepared edition).
    """
    import math
    results = []
    if _is_test_mode():
        by_exam = failed_questions_by_exam(collection_path)
        return [{'exam': e, 'parent_id': -1, 'count': len(n)} for e, n in by_exam.items()]

    from gnl_core.config import get_config
    from gnl_core.pdf_export import write_pdf
    from gnl_core.split import split
    from gnl_core.collect import collect
    from gnl_core.titles import generate_titles

    config = get_config()
    cat_defaults = (config.get('CATEGORY_DEFAULTS', {}) or {}).get(theme, {}) or {}
    pages_per_episode = int(cat_defaults.get('pages_per_episode', 0) or 0)

    by_exam = failed_questions_by_exam(collection_path)
    for exam_name, nums in by_exam.items():
        md = _find_exam_markdown(exam_name, theme, subtheme)
        if not md:
            if on_progress:
                on_progress(f"  ⚠ markdown source introuvable pour {exam_name}")
            continue
        # 1. Build the error-doc markdown for this exam's failed questions.
        err_name = f"{exam_name}-failed"
        err_md = Path(md).parent.parent.parent / 'erreurs' / f'{err_name}.md'
        out = build_error_document(exam_name, nums, str(md), out_path=str(err_md))
        if not out:
            continue
        # 2. Convert the error-doc markdown to a PDF the pipeline can split.
        err_pdf = Path(out).with_suffix('.pdf')
        try:
            write_pdf(Path(out).read_text(encoding='utf-8'), str(err_pdf),
                      title=f"{exam_name} — questions ratées")
        except Exception as e:
            if on_progress:
                on_progress(f"  ⚠ PDF {exam_name}: {str(e)[:60]}")
            continue
        # 3. Prepare: split + collect + titles (quota-free), exams defaults.
        try:
            from PyPDF2 import PdfReader
            total = len(PdfReader(str(err_pdf)).pages)
            ppe = pages_per_episode if pages_per_episode > 0 else max(1, math.ceil(total / 20))
            res = split(str(err_pdf), ppe, err_name,
                        podcast_theme=theme, podcast_subtheme=subtheme, mode='pages')
            parent_id = collect(res)
            generate_titles(parent_id)
            results.append({'exam': exam_name, 'parent_id': parent_id, 'count': len(nums)})
            if on_progress:
                on_progress(f"  ✓ {exam_name}: {len(nums)} ratées → édition prête (parent_id={parent_id})")
        except Exception as e:
            if on_progress:
                on_progress(f"  ⚠ prepare {exam_name}: {str(e)[:80]}")
    return results
