"""Regression tests for LinkedIn fetch robustness (venv detection, cache safety).

Reproduces the incident where the MCP venv had vanished: the fetch used to
swallow the error as a silent 'Scraping échoué' and delete the cache.
"""
import asyncio
import os
import pytest


def test_call_linkedin_mcp_reports_missing_venv(monkeypatch):
    monkeypatch.setenv('LINKEDIN_MCP_PATH', '/definitely/not/here')
    from gnl_core.web.app import _call_linkedin_mcp
    result = asyncio.run(_call_linkedin_mcp())
    assert isinstance(result, str)
    assert result.startswith('venv_missing:')
    assert '/definitely/not/here' in result


def test_missing_venv_does_not_touch_cache(monkeypatch, tmp_path):
    """A missing venv must NOT delete an existing cache."""
    # Point HOME so the cache path resolves under tmp
    fake_home = tmp_path
    cache_dir = fake_home / ".linkedin-mcp"
    cache_dir.mkdir()
    cache = cache_dir / "saved_posts.db"
    cache.write_bytes(b"existing-cache-data")

    monkeypatch.setenv('LINKEDIN_MCP_PATH', '/definitely/not/here')
    monkeypatch.setattr(os.path, 'expanduser', lambda p: p.replace('~', str(fake_home)))
    import pathlib
    monkeypatch.setattr(pathlib.Path, 'home', staticmethod(lambda: fake_home))

    from gnl_core.web.app import _call_linkedin_mcp
    result = asyncio.run(_call_linkedin_mcp())

    assert result.startswith('venv_missing:')
    # Cache must be intact (we bailed out before touching it)
    assert cache.exists()
    assert cache.read_bytes() == b"existing-cache-data"
