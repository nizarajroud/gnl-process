"""Tests for gnl_core.coverart — dynamic cover art for aws-whats-new.

Bedrock and ffmpeg are never really called: TEST_MODE or monkeypatch.
"""
import os
import json
import pytest

from gnl_core import coverart
from gnl_core.coverart import (
    extract_news_titles, render_cover, embed_cover,
    add_cover_for_whatsnew, COVER_CATEGORY,
)


@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    yield
    monkeypatch.delenv('TEST_MODE', raising=False)


# --- TEST_MODE short-circuits ---

def test_extract_titles_test_mode(test_mode):
    titles = extract_news_titles("anything")
    assert titles == ["Test News", "Sample Item"]


def test_render_cover_test_mode(tmp_path, test_mode):
    out = str(tmp_path / "c.png")
    assert render_cover("Ep", ["A", "B"], out) == out
    assert os.path.exists(out)


def test_embed_cover_test_mode(test_mode):
    assert embed_cover("/no/mp3", "/no/png") is True  # no-op


# --- category gating ---

def test_add_cover_skips_other_categories():
    assert add_cover_for_whatsnew("aws/aws-papers", "/x.mp3", "text", "Ep") is False


def test_add_cover_test_mode_whatsnew(test_mode, tmp_path):
    mp3 = tmp_path / "e.mp3"
    mp3.write_bytes(b'\x00' * 100)
    ok = add_cover_for_whatsnew(COVER_CATEGORY, str(mp3), "some news text", "Août")
    assert ok is True


# --- title extraction parsing (Bedrock mocked) ---

def _mock_bedrock(monkeypatch, payload_text):
    class _Body:
        def read(self):
            return json.dumps({"content": [{"text": payload_text}]}).encode()
    class _Client:
        def invoke_model(self, **kw):
            return {"body": _Body()}
    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: _Client())


def test_extract_titles_parses_json_array(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '0')
    _mock_bedrock(monkeypatch, '["Lambda SnapStart", "S3 Tables", "EKS AutoMode"]')
    titles = extract_news_titles("text with news")
    assert titles == ["Lambda SnapStart", "S3 Tables", "EKS AutoMode"]


def test_extract_titles_handles_prose_wrapping(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '0')
    _mock_bedrock(monkeypatch, 'Here you go:\n["Bedrock AgentCore", "Q Developer"]\nHope that helps')
    titles = extract_news_titles("text")
    assert titles == ["Bedrock AgentCore", "Q Developer"]


def test_extract_titles_empty_text_returns_empty(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '0')
    assert extract_news_titles("   ") == []


def test_extract_titles_caps_max(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '0')
    big = json.dumps([f"News{i}" for i in range(50)])
    _mock_bedrock(monkeypatch, big)
    titles = extract_news_titles("text", max_titles=5)
    assert len(titles) == 5


# --- embed command shape (ffmpeg mocked) ---

def test_embed_builds_attached_pic_command(monkeypatch, tmp_path):
    monkeypatch.setenv('TEST_MODE', '0')
    mp3 = tmp_path / "a.mp3"; mp3.write_bytes(b'\x00' * 10)
    png = tmp_path / "a.png"; png.write_bytes(b'\x89PNG')
    captured = {}
    def fake_run(cmd, **kw):
        captured['cmd'] = cmd
        # simulate ffmpeg producing the temp output
        out = cmd[-1]
        with open(out, 'wb') as f:
            f.write(b'\x00' * 10)
        class R: returncode = 0
        return R()
    monkeypatch.setattr(coverart.subprocess, "run", fake_run)
    ok = embed_cover(str(mp3), str(png), metadata={'title': 'T', 'artist': 'A'})
    assert ok is True
    cmd = captured['cmd']
    assert 'attached_pic' in cmd
    assert '-disposition:v' in cmd
    assert 'title=T' in cmd and 'artist=A' in cmd


def test_embed_missing_files_returns_false(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '0')
    assert embed_cover("/nope.mp3", "/nope.png") is False
