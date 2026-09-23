"""Unit tests for gnl_core.quota — NLM compute-based quota parsing.

Zero quota consumption: all NLM calls are mocked.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from gnl_core import quota
from gnl_core.quota import (
    get_quota_status, has_budget, next_recharge_local,
    SessionExpiredError, NetworkTimeoutError, WINDOW_5H, WINDOW_WEEKLY,
)


def _future_ts(hours):
    return int(datetime.now(timezone.utc).timestamp() + hours * 3600)


def _mock_client(usage, tier="NOTEBOOKLM_TIER_PRO_CONSUMER_USER"):
    c = MagicMock()
    c.get_usage.return_value = usage
    c.get_entitlement_tier.return_value = tier
    return c


# --- Window indexing (order NOT stable) ---

def test_windows_indexed_by_code_not_position():
    """Windows returned in [weekly, 5h] order must still map correctly."""
    usage = [
        {"window": WINDOW_WEEKLY, "percent_remaining": 40, "resets_at": _future_ts(100)},
        {"window": WINDOW_5H, "percent_remaining": 80, "resets_at": _future_ts(3)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert status["window_5h"]["percent_remaining"] == 80
    assert status["window_weekly"]["percent_remaining"] == 40


def test_windows_reversed_order_still_correct():
    """Same account can return [5h, weekly] — must also map correctly."""
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 10, "resets_at": _future_ts(2)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 55, "resets_at": _future_ts(120)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert status["window_5h"]["percent_remaining"] == 10
    assert status["window_weekly"]["percent_remaining"] == 55


# --- Session expired (code 16) != quota exhausted ---

def test_session_expired_raises():
    c = MagicMock()
    c.get_usage.side_effect = Exception("RPC failed with code 16")
    with pytest.raises(SessionExpiredError):
        get_quota_status(c)


def test_unauthenticated_raises_session_expired():
    c = MagicMock()
    c.get_usage.side_effect = Exception("UNAUTHENTICATED")
    with pytest.raises(SessionExpiredError):
        get_quota_status(c)


def test_other_error_propagates_not_as_session():
    c = MagicMock()
    c.get_usage.side_effect = Exception("network timeout")
    with pytest.raises(Exception) as exc:
        get_quota_status(c)
    assert not isinstance(exc.value, SessionExpiredError)


# --- has_budget logic ---

def test_has_budget_both_windows_available():
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 50, "resets_at": _future_ts(3)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 50, "resets_at": _future_ts(100)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert has_budget(status) is True


def test_no_budget_when_5h_exhausted():
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 0, "resets_at": _future_ts(3)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 50, "resets_at": _future_ts(100)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert has_budget(status) is False


def test_no_budget_when_weekly_exhausted():
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 80, "resets_at": _future_ts(3)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 0, "resets_at": _future_ts(100)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert has_budget(status) is False


def test_has_budget_respects_min_percent():
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 3, "resets_at": _future_ts(3)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 50, "resets_at": _future_ts(100)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert has_budget(status, min_percent=1) is True
    assert has_budget(status, min_percent=5) is False


def test_has_budget_false_on_bad_status():
    assert has_budget(None) is False
    assert has_budget({"ok": False}) is False


# --- resets_in_h computed ---

def test_resets_in_hours_computed():
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 100, "resets_at": _future_ts(5)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 100, "resets_at": _future_ts(168)},
    ]
    status = get_quota_status(_mock_client(usage))
    assert 4.9 <= status["window_5h"]["resets_in_h"] <= 5.1
    assert 167 <= status["window_weekly"]["resets_in_h"] <= 169


# --- next_recharge_local ---

def test_next_recharge_local_returns_string():
    usage = [
        {"window": WINDOW_5H, "percent_remaining": 100, "resets_at": _future_ts(5)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 100, "resets_at": _future_ts(168)},
    ]
    status = get_quota_status(_mock_client(usage))
    result = next_recharge_local(status)
    assert isinstance(result, str)
    assert "20" in result  # year 20xx


def test_next_recharge_none_when_missing():
    assert next_recharge_local({}) is None
    assert next_recharge_local({"window_5h": {}}) is None


# --- tier fallback ---

def test_tier_fallback_on_error():
    c = MagicMock()
    c.get_usage.return_value = [
        {"window": WINDOW_5H, "percent_remaining": 100, "resets_at": _future_ts(5)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 100, "resets_at": _future_ts(168)},
    ]
    c.get_entitlement_tier.side_effect = Exception("tier rpc failed")
    status = get_quota_status(c)
    assert status["tier"] is None
    assert status["ok"] is True


# --- US-001: transient network timeout handling ---

def _ok_usage():
    return [
        {"window": WINDOW_5H, "percent_remaining": 100, "resets_at": _future_ts(5)},
        {"window": WINDOW_WEEKLY, "percent_remaining": 100, "resets_at": _future_ts(168)},
    ]


def test_timeout_retries_then_succeeds():
    """First call times out, second succeeds -> status returned, no error."""
    c = MagicMock()
    c.get_usage.side_effect = [
        Exception("the read operation timed out"),
        _ok_usage(),
    ]
    c.get_entitlement_tier.return_value = "T"
    status = get_quota_status(c, retries=2, retry_delay=0)  # retry_delay=0 -> fast test
    assert status["ok"] is True
    assert status["window_5h"]["percent_remaining"] == 100
    assert c.get_usage.call_count == 2


def test_timeout_persists_raises_network_timeout():
    """Timeout on every attempt -> NetworkTimeoutError (not a generic failure)."""
    c = MagicMock()
    c.get_usage.side_effect = Exception("read operation timed out")
    with pytest.raises(NetworkTimeoutError):
        get_quota_status(c, retries=2, retry_delay=0)
    assert c.get_usage.call_count == 3  # 1 + 2 retries


def test_timeout_error_type_detected():
    c = MagicMock()
    c.get_usage.side_effect = TimeoutError("socket timed out")
    with pytest.raises(NetworkTimeoutError):
        get_quota_status(c, retries=1, retry_delay=0)


def test_session_expired_not_retried():
    """Code 16 is fatal (session) — must NOT be retried as a timeout."""
    c = MagicMock()
    c.get_usage.side_effect = Exception("RPC failed with code 16")
    with pytest.raises(SessionExpiredError):
        get_quota_status(c, retries=3, retry_delay=0)
    assert c.get_usage.call_count == 1  # no retry


def test_other_error_not_retried():
    c = MagicMock()
    c.get_usage.side_effect = Exception("some unexpected boom")
    with pytest.raises(Exception) as exc:
        get_quota_status(c, retries=3, retry_delay=0)
    assert not isinstance(exc.value, (NetworkTimeoutError, SessionExpiredError))
    assert c.get_usage.call_count == 1
