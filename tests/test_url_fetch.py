"""Tests for the URL fetcher (validation + error handling)."""
import pytest
from gnl_core.url_fetch import fetch_url_text


def test_invalid_url_raises():
    with pytest.raises(ValueError):
        fetch_url_text("not-a-url")


def test_empty_url_raises():
    with pytest.raises(ValueError):
        fetch_url_text("")


def test_ftp_scheme_rejected():
    with pytest.raises(ValueError):
        fetch_url_text("ftp://example.com/file")
