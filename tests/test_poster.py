"""Tests for gnl_core.poster — category-aware posters + PDF booklet.

TEST_MODE avoids Bedrock/rendering; providers are checked for routing.
"""
import os
import pytest
from pathlib import Path

from gnl_core import poster


@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    yield
    monkeypatch.delenv('TEST_MODE', raising=False)


# --- provider routing ---

def test_poster_items_whatsnew_test_mode(test_mode, tmp_path):
    pdf = tmp_path / "p1.pdf"; pdf.write_bytes(b'%PDF-1.4')
    items = poster.poster_items('aws/aws-whats-new', str(pdf))
    assert items == ["Test News", "Sample Item"]  # coverart stub


def test_poster_items_exam_test_mode(test_mode, tmp_path):
    md = tmp_path / "p1.md"; md.write_text("## Question 1:\nfoo\n## Question 2:\nbar")
    items = poster.poster_items('exams/sap-c02', str(md))
    assert items == ["Q1 · Test Problem", "Q2 · Sample Case"]


def test_poster_items_never_raises_on_missing():
    assert poster.poster_items('exams/sap-c02', '/no/such.md') == []
    assert poster.poster_items('aws/aws-whats-new', '/no/such.pdf') == []


def test_exam_parses_question_numbers(monkeypatch, tmp_path):
    """Exam labels keep the real question numbers, even if Bedrock returns nothing."""
    monkeypatch.setenv('TEST_MODE', '0')
    md = tmp_path / "p3.md"
    md.write_text("## Question 7:\nDesign a DR strategy.\n\n## Question 8:\nReduce latency.")
    # Mock Bedrock to return empty -> labels fall back to 'Q{n}'
    import boto3
    class _Body:
        def read(self): return b'{"content":[{"text":"[]"}]}'
    class _Client:
        def invoke_model(self, **k): return {"body": _Body()}
    monkeypatch.setattr(boto3, "client", lambda *a, **k: _Client())
    items = poster._items_exam(str(md))
    assert items == ["Q7", "Q8"]


def test_exam_labels_combine_number_and_problem(monkeypatch, tmp_path):
    monkeypatch.setenv('TEST_MODE', '0')
    md = tmp_path / "p1.md"
    md.write_text("## Question 1:\nDesign DR.\n\n## Question 2:\nCut latency.")
    import boto3, json
    class _Body:
        def read(self):
            return json.dumps({"content": [{"text": '["DR Strategy", "Latency Reduction"]'}]}).encode()
    class _Client:
        def invoke_model(self, **k): return {"body": _Body()}
    monkeypatch.setattr(boto3, "client", lambda *a, **k: _Client())
    items = poster._items_exam(str(md))
    assert items == ["Q1 · DR Strategy", "Q2 · Latency Reduction"]


# --- timecode formatting ---

def test_fmt_ts():
    assert poster._fmt_ts(0) == "0:00"
    assert poster._fmt_ts(65) == "1:05"
    assert poster._fmt_ts(3599) == "59:59"


# --- PDF booklet ---

def test_build_pdf_test_mode(test_mode, tmp_path):
    chunks = [str(tmp_path / f"p{i}.pdf") for i in range(1, 4)]
    for c in chunks:
        Path(c).write_bytes(b'%PDF-1.4')
    out = str(tmp_path / "booklet.pdf")
    result = poster.build_episode_pdf('aws/aws-whats-new', chunks, [], out)
    assert result == out
    assert os.path.exists(out)


def test_build_pdf_empty_returns_none(test_mode, tmp_path):
    assert poster.build_episode_pdf('aws/aws-whats-new', [], [], str(tmp_path / "x.pdf")) is None
