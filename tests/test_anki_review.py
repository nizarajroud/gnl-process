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
    """entries: list of (guid, ease_of_last_review). Builds minimal Anki schema."""
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT);
        CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER);
        CREATE TABLE revlog (id INTEGER PRIMARY KEY, cid INTEGER, ease INTEGER);
    """)
    rid = 1
    for i, (guid, ease) in enumerate(entries, start=1):
        c.execute("INSERT INTO notes(id, guid) VALUES(?,?)", (i, guid))
        c.execute("INSERT INTO cards(id, nid) VALUES(?,?)", (i, i))
        # two reviews: an early ease=3, then the LAST review with the given ease
        c.execute("INSERT INTO revlog(id, cid, ease) VALUES(?,?,?)", (rid, i, 3)); rid += 1
        c.execute("INSERT INTO revlog(id, cid, ease) VALUES(?,?,?)", (rid, i, ease)); rid += 1
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
        ("Dojo-Timed-Mode-2-q40", 1),   # failed
        ("Dojo-Timed-Mode-2-q12", 1),   # failed
        ("Dojo-Timed-Mode-2-q5", 3),    # passed (last review good)
        ("Dojo-Timed-Mode-1-q3", 1),    # failed, other exam
        ("weird-guid-no-match", 1),     # ignored (bad format)
    ])
    res = anki_review.failed_questions_by_exam(db)
    assert res == {"Dojo-Timed-Mode-2": [12, 40], "Dojo-Timed-Mode-1": [3]}


def test_only_last_review_counts(monkeypatch, tmp_path):
    """A card failed early but passed on its LAST review must NOT be reported."""
    monkeypatch.setenv('TEST_MODE', '0')
    db = str(tmp_path / "col.anki2")
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT);
        CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER);
        CREATE TABLE revlog (id INTEGER PRIMARY KEY, cid INTEGER, ease INTEGER);
    """)
    c.execute("INSERT INTO notes VALUES(1,'Exam-A-q1')")
    c.execute("INSERT INTO cards VALUES(1,1)")
    c.execute("INSERT INTO revlog VALUES(1,1,1)")  # early: failed
    c.execute("INSERT INTO revlog VALUES(2,1,3)")  # last: passed
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
