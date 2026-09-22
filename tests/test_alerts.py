"""Tests for gnl_core.alerts — Telegram alerting (mirrors kuse-alert pattern).

Network is never hit: urllib is monkeypatched.
"""
import os
import pytest

from gnl_core import alerts


@pytest.fixture(autouse=True)
def isolate_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(alerts, '_FLAG_DIR', tmp_path / 'gnl-alert')
    yield


def test_load_creds_from_env(monkeypatch):
    monkeypatch.setenv('KIRO_TG_TOKEN', 'tok123')
    monkeypatch.setenv('KIRO_TG_CHAT_ID', '999')
    token, chat = alerts._load_telegram_creds()
    assert token == 'tok123'
    assert chat == '999'


def test_load_creds_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv('KIRO_TG_TOKEN', raising=False)
    monkeypatch.delenv('KIRO_TG_CHAT_ID', raising=False)
    env = tmp_path / '.env'
    env.write_text('KIRO_TG_TOKEN="abc"\nKIRO_TG_CHAT_ID="12345"\nOTHER=x\n')
    monkeypatch.setattr(alerts, '_ENV_PATH', str(env))
    token, chat = alerts._load_telegram_creds()
    assert token == 'abc'
    assert chat == '12345'


def test_load_creds_missing_returns_none(monkeypatch):
    monkeypatch.delenv('KIRO_TG_TOKEN', raising=False)
    monkeypatch.delenv('KIRO_TG_CHAT_ID', raising=False)
    monkeypatch.setattr(alerts, '_ENV_PATH', '/no/such/.env')
    assert alerts._load_telegram_creds() == (None, None)


def test_send_telegram_success(monkeypatch):
    monkeypatch.setenv('KIRO_TG_TOKEN', 't')
    monkeypatch.setenv('KIRO_TG_CHAT_ID', 'c')
    sent = {}

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=10):
        sent['url'] = req.full_url
        sent['data'] = req.data
        return _Resp()

    monkeypatch.setattr(alerts.urllib.request, 'urlopen', fake_urlopen)
    assert alerts.send_telegram("hello") is True
    assert 'bott' in sent['url'] or 'bot' in sent['url']
    assert b'hello' in sent['data']


def test_send_telegram_no_creds_returns_false(monkeypatch):
    monkeypatch.delenv('KIRO_TG_TOKEN', raising=False)
    monkeypatch.delenv('KIRO_TG_CHAT_ID', raising=False)
    monkeypatch.setattr(alerts, '_ENV_PATH', '/no/such/.env')
    assert alerts.send_telegram("x") is False


def test_send_telegram_never_raises(monkeypatch):
    monkeypatch.setenv('KIRO_TG_TOKEN', 't')
    monkeypatch.setenv('KIRO_TG_CHAT_ID', 'c')
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', boom)
    assert alerts.send_telegram("x") is False  # swallowed


def test_alert_once_per_day_dedup(monkeypatch):
    monkeypatch.setenv('KIRO_TG_TOKEN', 't')
    monkeypatch.setenv('KIRO_TG_CHAT_ID', 'c')
    calls = []
    monkeypatch.setattr(alerts, 'send_telegram', lambda m: calls.append(m) or True)
    # First call sends, second (same key, same day) is suppressed
    assert alerts.alert('k1', 'msg', once_per='day') is True
    assert alerts.alert('k1', 'msg', once_per='day') is False
    assert len(calls) == 1


def test_alert_no_dedup_sends_every_time(monkeypatch):
    monkeypatch.setenv('KIRO_TG_TOKEN', 't')
    monkeypatch.setenv('KIRO_TG_CHAT_ID', 'c')
    calls = []
    monkeypatch.setattr(alerts, 'send_telegram', lambda m: calls.append(m) or True)
    alerts.alert('k2', 'msg')
    alerts.alert('k2', 'msg')
    assert len(calls) == 2
