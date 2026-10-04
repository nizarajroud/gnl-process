"""Tests for the empty Anki reflection-template image (per question)."""
import json
import zipfile
from pathlib import Path

from gnl_core import anki_template, exams


def test_render_template_creates_png(tmp_path):
    out = tmp_path / 't.png'
    anki_template.render_template('Q1 · Some Concept', str(out))
    assert out.exists() and out.stat().st_size > 1000


def test_titles_test_mode(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    titles = anki_template._titles_for_questions('x.md', {'1': {}, '3': {}})
    assert titles['1'].startswith('Q1') and titles['3'].startswith('Q3')


def test_apkg_embeds_template_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'DEBUG_NLM': '0', 'ANKI_TEMPLATE_IMG': '1'}
    exams.get_exam_base = lambda t, s: tmp_path
    src = tmp_path / 'm.md'
    src.write_text('## Question 1:\nQ?\n- A. x\n- B. y\n')
    out = exams.step5_anki({'1': {'type': 'single', 'options': ['A. x', 'B. y'],
                                  'correct': ['a']}}, str(src), 'exams', 'sap-c02')
    media = json.loads(zipfile.ZipFile(out).read('media').decode())
    assert 'template_Q1.png' in media.values()


def test_apkg_no_template_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'DEBUG_NLM': '0'}
    exams.get_exam_base = lambda t, s: tmp_path
    src = tmp_path / 'm.md'
    src.write_text('## Question 1:\nQ?\n- A. x\n- B. y\n')
    out = exams.step5_anki({'1': {'type': 'single', 'options': ['A. x', 'B. y'],
                                  'correct': ['a']}}, str(src), 'exams', 'sap-c02')
    media = json.loads(zipfile.ZipFile(out).read('media').decode())
    assert not any('template_' in v for v in media.values())


def test_highlighter_present_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'DEBUG_NLM': '0', 'ANKI_HIGHLIGHTER': '1'}
    exams.get_exam_base = lambda t, s: tmp_path
    src = tmp_path / 'm.md'
    src.write_text('## Question 1:\nQ with LEAST effort?\n- A. x\n- B. y\n')
    out = exams.step5_anki({'1': {'type': 'single', 'options': ['A. x', 'B. y'],
                                  'correct': ['a']}}, str(src), 'exams', 'sap-c02')
    import zipfile
    import sqlite3
    z = zipfile.ZipFile(out)
    z.extract('collection.anki2', tmp_path)
    flds = sqlite3.connect(tmp_path / 'collection.anki2').execute(
        'SELECT flds FROM notes').fetchone()[0]
    assert 'gnlHlToggle' in flds and 'Surligneur' in flds


def test_highlighter_absent_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'DEBUG_NLM': '0'}
    exams.get_exam_base = lambda t, s: tmp_path
    src = tmp_path / 'm.md'
    src.write_text('## Question 1:\nQ?\n- A. x\n- B. y\n')
    out = exams.step5_anki({'1': {'type': 'single', 'options': ['A. x', 'B. y'],
                                  'correct': ['a']}}, str(src), 'exams', 'sap-c02')
    import zipfile
    import sqlite3
    z = zipfile.ZipFile(out)
    z.extract('collection.anki2', tmp_path)
    flds = sqlite3.connect(tmp_path / 'collection.anki2').execute(
        'SELECT flds FROM notes').fetchone()[0]
    assert 'gnlHlToggle' not in flds
