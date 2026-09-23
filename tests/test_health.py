"""Tests for gnl_core.health — preventive dry-run health-check (US-002)."""
import pytest
from gnl_core import health


def test_health_check_returns_all_components(monkeypatch):
    # Force each check to a known value
    monkeypatch.setattr(health, '_check_nlm_session', lambda: (True, "5h 100%"))
    monkeypatch.setattr(health, '_check_linkedin_venv', lambda: (True, "venv OK"))
    monkeypatch.setattr(health, '_check_drive', lambda: (True, "accessible"))
    monkeypatch.setattr(health, '_check_bedrock', lambda: (True, "joignable"))
    monkeypatch.setattr(health, '_check_ffmpeg', lambda: (True, "ffmpeg+ffprobe"))
    monkeypatch.setattr(health, '_check_pending', lambda: (True, "25 items"))
    # Rebuild CHECKS to use patched functions
    monkeypatch.setattr(health, 'CHECKS', [
        ("NLM", health._check_nlm_session),
        ("LinkedIn venv", health._check_linkedin_venv),
        ("Drive", health._check_drive),
        ("Bedrock", health._check_bedrock),
        ("ffmpeg", health._check_ffmpeg),
        ("File", health._check_pending),
    ])
    results = health.health_check()
    assert set(results.keys()) == {"NLM", "LinkedIn venv", "Drive", "Bedrock", "ffmpeg", "File"}
    assert all(ok for ok, _ in results.values())


def test_health_check_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("kaboom")
    monkeypatch.setattr(health, 'CHECKS', [("NLM", boom)])
    results = health.health_check()
    assert results["NLM"][0] is False
    assert "exception" in results["NLM"][1]


def test_recap_all_ok():
    results = {"NLM": (True, "5h 100%"), "Drive": (True, "accessible")}
    recap = health.format_recap(results)
    assert "tout OK" in recap
    assert "✅ NLM: 5h 100%" in recap
    assert "✅ Drive: accessible" in recap
    assert "Corriger" not in recap


def test_recap_with_problem():
    results = {"NLM": (True, "5h 100%"), "Drive": (False, "inaccessible (/mnt/g)")}
    recap = health.format_recap(results)
    assert "problème détecté" in recap
    assert "❌ Drive: inaccessible (/mnt/g)" in recap
    assert "Corriger avant la prochaine passe" in recap


def test_check_ffmpeg_detects_missing(monkeypatch):
    monkeypatch.setattr(health.shutil, 'which', lambda x: None)
    ok, detail = health._check_ffmpeg()
    assert ok is False
    assert "manquant" in detail


def test_check_ffmpeg_present(monkeypatch):
    monkeypatch.setattr(health.shutil, 'which', lambda x: "/usr/bin/" + x)
    ok, detail = health._check_ffmpeg()
    assert ok is True


def test_check_linkedin_venv_missing(monkeypatch):
    monkeypatch.setenv('LINKEDIN_MCP_PATH', '/no/such/repo')
    ok, detail = health._check_linkedin_venv()
    assert ok is False
    assert "manquant" in detail
