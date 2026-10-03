"""Tests for Anki TTS (Amazon Polly) — flag-gated audio on cards."""
import json
import zipfile
from pathlib import Path

from gnl_core import anki_tts, exams


def test_strip_html_cleans_for_tts():
    assert anki_tts._strip_html('<b>Q</b><br>line<style>x{}</style>') == 'Q\nline'
    assert anki_tts._strip_html('A &amp; B') == 'A & B'
    assert anki_tts._strip_html('x\u2605y\u2691z') == 'xyz'


def test_chunks_respect_limit():
    long = 'Sentence. ' * 1000
    parts = anki_tts._chunks(long, size=500)
    assert parts and all(len(p) <= 500 for p in parts)
    assert ''.join(parts).replace(' ', '') == long.replace(' ', '')


def test_synthesize_test_mode_stub(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    out = tmp_path / 's.mp3'
    r = anki_tts.synthesize('Hello world', str(out))
    assert r and Path(r).exists()


def _mini_exam(tmp):
    exams.get_exam_base = lambda t, s: Path(tmp)
    src = Path(tmp) / 'mini.md'
    src.write_text('## Question 1:\nStores objects?\n- A. S3\n- B. EBS\n')
    return str(src), {'1': {'type': 'single', 'options': ['A. S3', 'B. EBS'], 'correct': ['a']}}


def test_apkg_embeds_audio_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'ANKI_TTS': '1', 'POLLY_VOICE': 'Matthew',
                                 'POLLY_ENGINE': 'neural', 'DEBUG_NLM': '0'}
    src, answers = _mini_exam(str(tmp_path))
    out = exams.step5_anki(answers, src, 'exams', 'sap-c02')
    media = json.loads(zipfile.ZipFile(out).read('media').decode())
    assert 'q1_front.mp3' in media.values()
    assert 'q1_back.mp3' in media.values()


def test_apkg_no_audio_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    exams._get_config = lambda: {'ANKI_TTS': '0', 'DEBUG_NLM': '0'}
    src, answers = _mini_exam(str(tmp_path))
    out = exams.step5_anki(answers, src, 'exams', 'sap-c02')
    media = json.loads(zipfile.ZipFile(out).read('media').decode())
    assert not any('.mp3' in v for v in media.values())
