"""Unit tests for gnl_core.auto_wiring — generate_fn routing + TEST_MODE.

Zero quota consumption: exams/articles paths return False (not wired),
file-based path runs in TEST_MODE (no disk/DB/NLM access).
"""
import os
import pytest

from gnl_core.auto_generate import WorkItem, SKIP
from gnl_core import auto_wiring
from gnl_core.auto_wiring import make_generate_fn, prepare_file_item


@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    yield
    monkeypatch.delenv('TEST_MODE', raising=False)


def _item(category, identifier, **cfg):
    return WorkItem(category=category, identifier=identifier, priority=1, config=cfg)


# --- routing ---

def test_generate_skips_linkedin():
    gen = make_generate_fn()
    assert gen(_item('saved-articles/linkedin', 123)) is SKIP


def test_generate_skips_exams():
    gen = make_generate_fn()
    assert gen(_item('exams/sap-c02', 'x.docx')) is SKIP


def test_generate_file_based_in_test_mode(test_mode):
    """File-based category in TEST_MODE returns True without touching disk."""
    gen = make_generate_fn()
    assert gen(_item('aws/aws-papers', 'whatever.pdf')) is True


# --- prepare_file_item TEST_MODE ---

def test_prepare_file_item_test_mode_returns_sentinel(test_mode):
    pid = prepare_file_item(_item('aws/aws-papers', 'anything.pdf'))
    assert pid == -1  # sentinel, no real work done


def test_prepare_file_item_missing_file_returns_none(monkeypatch):
    """Non-test mode + missing file -> None (no crash)."""
    monkeypatch.setenv('TEST_MODE', '0')
    # Point INBOX to a temp dir with no such file
    import gnl_core.config as cfgmod
    monkeypatch.setattr(cfgmod, 'get_config', lambda: {'INBOX_FOLDER': '/nonexistent-inbox'})
    pid = prepare_file_item(_item('aws/aws-papers', 'ghost.pdf'))
    assert pid is None


# --- on_progress callback ---

def test_generate_calls_on_progress(test_mode):
    logs = []
    gen = make_generate_fn(on_progress=logs.append)
    gen(_item('aws/aws-papers', 'doc.pdf'))
    assert any('TEST' in m for m in logs)


def test_generate_exception_returns_false(monkeypatch):
    """If prepare raises, generate_fn swallows and returns False."""
    monkeypatch.setenv('TEST_MODE', '0')
    def boom(item, on_progress=None):
        raise RuntimeError("split failed")
    monkeypatch.setattr(auto_wiring, 'prepare_file_item', boom)
    gen = make_generate_fn()
    assert gen(_item('aws/aws-papers', 'doc.pdf')) is False
