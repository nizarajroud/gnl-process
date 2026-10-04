"""Tests for gnl_core.anki_review — failed-question detection base.

Uses an in-memory-like temp SQLite mimicking the Anki schema; no real collection.
"""
import os
import sqlite3
import pytest
from gnl_core import anki_review


@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    yield
    monkeypatch.delenv('TEST_MODE', raising=False)


def _make_anki_db(path, entries):
    """entries: list of (guid, failed_bool). Builds minimal Anki schema.

    Detection is now based on the RED FLAG (cards.flags & 7 == 1), which is how
    the user marks a missed question in Anki (works even for New cards).
    """
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT);
        CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER, flags INTEGER DEFAULT 0);
    """)
    for i, (guid, failed) in enumerate(entries, start=1):
        c.execute("INSERT INTO notes(id, guid) VALUES(?,?)", (i, guid))
        c.execute("INSERT INTO cards(id, nid, flags) VALUES(?,?,?)",
                  (i, i, 1 if failed else 0))  # flag 1 = red = failed
    c.commit(); c.close()


def test_test_mode_stub(test_mode):
    assert anki_review.failed_questions_by_exam() == {"test-exam": [1, 3]}


def test_missing_collection_returns_empty(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '0')
    assert anki_review.failed_questions_by_exam('/no/such/collection.anki2') == {}


def test_groups_failed_by_exam(monkeypatch, tmp_path):
    monkeypatch.setenv('TEST_MODE', '0')
    db = str(tmp_path / "col.anki2")
    _make_anki_db(db, [
        ("Dojo-Timed-Mode-2-q40", True),   # failed (red flag)
        ("Dojo-Timed-Mode-2-q12", True),   # failed (red flag)
        ("Dojo-Timed-Mode-2-q5", False),   # not flagged -> passed
        ("Dojo-Timed-Mode-1-q3", True),    # failed, other exam
        ("weird-guid-no-match", True),     # ignored (bad format)
    ])
    res = anki_review.failed_questions_by_exam(db)
    assert res == {"Dojo-Timed-Mode-2": [12, 40], "Dojo-Timed-Mode-1": [3]}


def test_new_card_flagged_red_is_detected(monkeypatch, tmp_path):
    """A NEW card (never reviewed) flagged red must be reported (the bug)."""
    monkeypatch.setenv('TEST_MODE', '0')
    db = str(tmp_path / "col.anki2")
    _make_anki_db(db, [
        ("Dojo-Timed-Mode-2-q4", True),    # New + red flag -> failed
        ("Dojo-Timed-Mode-2-q16", True),   # New + red flag -> failed
        ("Dojo-Timed-Mode-2-q2", False),   # New, no flag -> not failed
    ])
    res = anki_review.failed_questions_by_exam(db)
    assert res == {"Dojo-Timed-Mode-2": [4, 16]}


def test_unflagged_card_not_reported(monkeypatch, tmp_path):
    """A card without a red flag must NOT be reported, even if reviewed before."""
    monkeypatch.setenv('TEST_MODE', '0')
    db = str(tmp_path / "col.anki2")
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT);
        CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER, flags INTEGER DEFAULT 0);
    """)
    c.execute("INSERT INTO notes VALUES(1,'Exam-A-q1')")
    c.execute("INSERT INTO cards VALUES(1,1,0)")   # no flag
    c.execute("INSERT INTO notes VALUES(2,'Exam-A-q2')")
    c.execute("INSERT INTO cards VALUES(2,2,2)")   # orange flag (not red) -> ignored
    c.commit(); c.close()
    assert anki_review.failed_questions_by_exam(db) == {}


def test_guid_regex():
    m = anki_review._GUID_RE.match("Dojo-Timed-Mode-2-q40")
    assert m.group('exam') == "Dojo-Timed-Mode-2"
    assert m.group('num') == "40"


# --- Artefact 1: error document ---

_SAMPLE_MD = """## Question 1:
What is X?
- Option A
- Option B

Explanations:

X is the answer because reasons. Option B is incorrect because other reasons.

## Question 2:
What is Y?
- Option C
- Option D

Explanations:

Y explanation here.
"""


def test_parse_exam_questions(tmp_path):
    md = tmp_path / "e.md"; md.write_text(_SAMPLE_MD, encoding='utf-8')
    qs = anki_review.parse_exam_questions(str(md))
    assert set(qs.keys()) == {1, 2}
    assert "What is X?" in qs[1]['body']
    assert "Option A" in qs[1]['body']
    assert "X is the answer" in qs[1]['explanation']
    assert "Explanations" not in qs[1]['body']  # marker stripped from body


def test_build_error_document(tmp_path):
    md = tmp_path / "e.md"; md.write_text(_SAMPLE_MD, encoding='utf-8')
    out = tmp_path / "e-erreurs.md"
    result = anki_review.build_error_document("e", [2], str(md), str(out))
    assert result == str(out)
    content = out.read_text()
    assert "Questions ratées (1)" in content
    assert "Question 2" in content
    assert "Y explanation here" in content
    assert "Question 1" not in content  # only failed question 2


def test_build_error_document_missing_question(tmp_path):
    md = tmp_path / "e.md"; md.write_text(_SAMPLE_MD, encoding='utf-8')
    out = tmp_path / "e-erreurs.md"
    anki_review.build_error_document("e", [99], str(md), str(out))
    assert "introuvable" in out.read_text()


def test_build_error_document_test_mode(test_mode, tmp_path):
    out = tmp_path / "e-erreurs.md"
    anki_review.build_error_document("e", [1], "/whatever.md", str(out))
    assert out.exists() and "TEST" in out.read_text()


# --- Artefact 2: reset apkg ---

def test_generate_reset_apkg_test_mode(test_mode):
    out = anki_review.generate_reset_apkg("MyExam", [40])
    assert out == "/tmp/MyExam-round2.apkg"


def test_reset_apkg_filter_and_guid(tmp_path, monkeypatch):
    """step5_anki with only_questions + guid_suffix produces a filtered reset deck."""
    monkeypatch.setenv('TEST_MODE', '0')
    import zipfile, sqlite3, tempfile, os
    from gnl_core import exams
    # minimal answers dict (3 questions) + a source markdown for question text
    answers = {
        '1': {'type': 'single', 'options': ['A', 'B'], 'correct': ['A']},
        '2': {'type': 'single', 'options': ['C', 'D'], 'correct': ['D']},
        '40': {'type': 'single', 'options': ['E', 'F'], 'correct': ['E']},
    }
    md = tmp_path / "MyExam.md"
    md.write_text("## Question 1:\nQ1?\n- A\n- B\n## Question 2:\nQ2?\n- C\n- D\n## Question 40:\nQ40?\n- E\n- F\n")
    monkeypatch.setenv('INBOX_FOLDER', str(tmp_path / "inbox"))
    # step5_anki writes under get_exam_base -> INBOX/exams/sap-c02/assets/Anki-generation/anki
    out = exams.step5_anki(answers, str(md), 'exams', 'sap-c02',
                           only_questions=[40], guid_suffix='-r2',
                           deck_suffix=' — Round 2', apkg_suffix='-round2')
    assert out.endswith('MyExam-round2.apkg')
    z = zipfile.ZipFile(out)
    tmp = tempfile.mkdtemp(); z.extract('collection.anki2', tmp)
    db = sqlite3.connect(os.path.join(tmp, 'collection.anki2'))
    guids = [r[0] for r in db.execute('SELECT guid FROM notes').fetchall()]
    db.close()
    assert guids == ['MyExam-r2-q40']  # only q40, distinct guid


def test_highlight_only_questions_scopes_bedrock(tmp_path, monkeypatch):
    """step3_highlight(only_questions=[...]) must send ONLY those blocks to Bedrock."""
    monkeypatch.setenv('TEST_MODE', '0')
    monkeypatch.setenv('EXAM_USE_NLM', '0')
    from gnl_core import exams
    from docx import Document

    # Build a tiny .docx with 3 questions at the path step3 derives from the .md
    word_dir = tmp_path / "word"
    word_dir.mkdir()
    doc = Document()
    for n in (1, 2, 40):
        doc.add_paragraph(f"Question {n}: Q{n}?")
        doc.add_paragraph("- A\n- B")
    doc.save(str(word_dir / "MyExam.docx"))
    md_dir = tmp_path / "full-markdown"
    md_dir.mkdir()
    (md_dir / "MyExam.md").write_text("stub")

    captured = {}
    def fake_bedrock(blocks, *a, **k):
        captured['nums'] = [n for n, _ in blocks]
        return {n: {'type': 'single', 'options': ['A', 'B'], 'correct': ['A']} for n, _ in blocks}
    monkeypatch.setattr(exams, '_highlight_via_bedrock', fake_bedrock)

    exams.step3_highlight(str(md_dir / "MyExam.md"), only_questions=[40])
    assert captured['nums'] == ['40']  # only the failed question reached Bedrock


def test_apkg_has_explanation_field_and_copy_button(tmp_path, monkeypatch):
    """Generated cards must carry a hidden Explanation field + a Copy button."""
    monkeypatch.setenv('TEST_MODE', '0')
    monkeypatch.setenv('INBOX_FOLDER', str(tmp_path / "inbox"))
    import zipfile, sqlite3, tempfile, os, json
    from gnl_core import exams
    answers = {'1': {'type': 'single', 'options': ['A', 'B'], 'correct': ['A']}}
    md = tmp_path / "MyExam.md"
    md.write_text(
        "## Question 1:\nWhat is A?\n- A\n- B\n\nExplanations:\n"
        "A is correct because it is the first letter. B is incorrect because it is second.\n"
    )
    out = exams.step5_anki(answers, str(md), 'exams', 'sap-c02')
    z = zipfile.ZipFile(out)
    tmp = tempfile.mkdtemp(); z.extract('collection.anki2', tmp)
    db = sqlite3.connect(os.path.join(tmp, 'collection.anki2'))
    flds = db.execute('SELECT flds FROM notes').fetchone()[0].split('\x1f')
    models = json.loads(db.execute('SELECT models FROM col').fetchone()[0])
    afmt = list(models.values())[0]['tmpls'][0]['afmt']
    db.close()
    assert len(flds) == 3                                  # Front, Back, Explanation
    assert 'A is correct because' in flds[2]               # explanation embedded
    assert 'gnlCopyArea' in afmt                           # selectable textarea present
    assert 'Copier' in afmt                                # copy button present
    assert 'display:none' in afmt and 'copysrc' in afmt    # explanation hidden


def test_apkg_meta_prompt_injected_and_configurable(tmp_path, monkeypatch):
    """The card JS must embed the (configurable) Meta AI prompt + answer detection."""
    monkeypatch.setenv('TEST_MODE', '0')
    monkeypatch.setenv('INBOX_FOLDER', str(tmp_path / "inbox"))
    import zipfile, sqlite3, tempfile, os, json
    from gnl_core import exams, config as cfgmod
    # Inject a custom prompt via the config layer
    monkeypatch.setattr(exams, '_get_config', lambda: {
        'META_PROMPT_WRONG': 'CUSTOM WRONG {MY_ANSWER} / {CORRECT}',
        'META_PROMPT_CORRECT': 'CUSTOM RIGHT {MY_ANSWER} / {CORRECT}',
    })
    answers = {'1': {'type': 'single', 'options': ['A', 'B'], 'correct': ['A']}}
    md = tmp_path / "MyExam.md"
    md.write_text("## Question 1:\nWhat is A?\n- A\n- B\n\nExplanations:\nA is right.\n")
    out = exams.step5_anki(answers, str(md), 'exams', 'sap-c02')
    z = zipfile.ZipFile(out)
    tmp = tempfile.mkdtemp(); z.extract('collection.anki2', tmp)
    db = sqlite3.connect(os.path.join(tmp, 'collection.anki2'))
    afmt = list(json.loads(db.execute('SELECT models FROM col').fetchone()[0]).values())[0]['tmpls'][0]['afmt']
    db.close()
    assert 'CUSTOM WRONG' in afmt          # configurable wrong prompt injected
    assert 'CUSTOM RIGHT' in afmt          # configurable correct prompt injected
    assert 'localStorage.getItem(key)' in afmt   # detects user's answer
    assert 'a.wrong||!a.answered' in afmt        # wrong/not-answered branch


def test_parse_practice_exam(tmp_path):
    """Parse the practice-exam docx format (paragraphs + 4-col option table)."""
    from docx import Document
    from gnl_core.anki_review import parse_practice_exam
    doc = Document()
    doc.add_paragraph("Question 1")
    doc.add_paragraph("Multiple Choice")
    doc.add_paragraph("Answer status:")
    doc.add_paragraph("Incorrect")
    doc.add_paragraph("Question")
    doc.add_paragraph("What is the best storage for X?")
    doc.add_paragraph("Which solution is cheapest?")
    doc.add_paragraph("Answer options")
    t = doc.add_table(rows=3, cols=4)
    hdr = t.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = 'Option', 'Correct answer', 'Your selection', 'Rationale'
    r1 = t.rows[1].cells
    r1[0].text, r1[1].text, r1[2].text, r1[3].text = 'A. Use S3', '', 'Selected', 'S3 is object storage but not cheapest here.'
    r2 = t.rows[2].cells
    r2[0].text, r2[1].text, r2[2].text, r2[3].text = 'B. Use Glacier', 'Correct', 'Not selected', 'Glacier is the cheapest for archival.'
    p = tmp_path / "prac.docx"
    doc.save(str(p))

    qs = parse_practice_exam(str(p))
    assert len(qs) == 1
    q = qs[0]
    assert q['num'] == 1
    assert q['status'] == 'Incorrect'
    assert 'best storage' in q['statement'] and 'cheapest' in q['statement']
    assert len(q['options']) == 2
    a, b = q['options']
    assert a['letter'] == 'A' and a['selected'] and not a['correct']
    assert b['letter'] == 'B' and b['correct'] and not b['selected']
    assert 'Glacier is the cheapest' in b['rationale']


def test_meta_copy_mode_prompt_selection(tmp_path, monkeypatch):
    """Conversation mode (default) keeps the old prompt; oneshot swaps it."""
    import json
    import sqlite3
    import zipfile
    from pathlib import Path
    from gnl_core import exams

    def _build(mode):
        cfg = {'DEBUG_NLM': '0'}
        if mode:
            cfg['META_COPY_MODE'] = mode
        exams._get_config = lambda: cfg
        exams.get_exam_base = lambda t, s: tmp_path
        src = tmp_path / 'm.md'
        src.write_text('## Question 1:\nQ?\n- A. x\n- B. y\n')
        out = exams.step5_anki({'1': {'type': 'single', 'options': ['A. x', 'B. y'],
                                      'correct': ['a']}}, str(src), 'exams', 'sap-c02')
        z = zipfile.ZipFile(out)
        z.extract('collection.anki2', tmp_path)
        col = sqlite3.connect(tmp_path / 'collection.anki2').execute(
            'SELECT models FROM col').fetchone()[0]
        afmt = list(json.loads(col).values())[0]['tmpls'][0]['afmt']
        (tmp_path / 'collection.anki2').unlink()
        return afmt

    conv = _build(None)                       # default (conversation primary)
    # Both prompts and both buttons are embedded regardless of mode.
    assert 'continue by voice' in conv        # conversation prompt present
    assert 'ONE complete reply' in conv       # one-shot prompt present
    assert 'Copier (conversation)' in conv and 'Copier (one-shot)' in conv
    assert 'Copier (vocal)' in conv

    one = _build('oneshot')
    assert 'continue by voice' in one and 'ONE complete reply' in one
    assert 'Copier (conversation)' in one and 'Copier (one-shot)' in one
    assert 'Copier (vocal)' in one


def test_localstorage_keys_are_content_based(tmp_path, monkeypatch):
    """localStorage keys bind to option CONTENT (hash), not positional index,
    so stale index-state from a previous import can't mis-mark an option."""
    import re
    import sqlite3
    import zipfile
    from gnl_core import exams
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'DEBUG_NLM': '0'}
    exams.get_exam_base = lambda t, s: tmp_path
    src = tmp_path / 'm.md'
    src.write_text('## Question 1:\nQ?\n- Option Alpha\n- Option Beta\n- Option Gamma\n')
    out = exams.step5_anki({'1': {'type': 'single',
                                  'options': ['Option Alpha', 'Option Beta', 'Option Gamma'],
                                  'correct': ['option gamma']}}, str(src), 'exams', 'sap-c02')
    z = zipfile.ZipFile(out)
    z.extract('collection.anki2', tmp_path)
    flds = sqlite3.connect(tmp_path / 'collection.anki2').execute(
        'SELECT flds FROM notes').fetchone()[0]
    front, back = flds.split('\x1f')[0], flds.split('\x1f')[1]
    fkeys = set(re.findall(r"setItem\('([^']+)'", front))
    bkeys = set(re.findall(r"data-qkey='([^']+)'", back))
    # front and back reference the SAME content-based keys
    assert fkeys == bkeys and len(fkeys) == 3
    # each key suffix is an 8-hex content hash, never a bare index o0/o1/o2
    for k in fkeys:
        suffix = k.rsplit('o', 1)[-1]
        assert re.fullmatch(r'[0-9a-f]{8}', suffix)
