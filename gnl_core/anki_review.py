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
