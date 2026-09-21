"""Tests for adaptive scheduling delay computation (gnl_core.auto_generate).

Pure logic, zero quota.
"""
from gnl_core.auto_generate import (
    compute_next_delay_seconds,
    RECHARGE_BUFFER_SECONDS, CONTINUE_DELAY_SECONDS,
    MIN_DELAY_SECONDS, MAX_DELAY_SECONDS,
)


def _status(w5_rem, w5_reset_h, ww_rem=90, ww_reset_h=160):
    return {
        "window_5h": {"percent_remaining": w5_rem, "resets_in_h": w5_reset_h},
        "window_weekly": {"percent_remaining": ww_rem, "resets_in_h": ww_reset_h},
    }


def test_no_budget_waits_for_5h_reset():
    """5h exhausted, resets in 2h -> wait ~2h + buffer."""
    s = _status(w5_rem=0, w5_reset_h=2.0)
    delay = compute_next_delay_seconds(s, "no_budget")
    assert delay == int(2.0 * 3600 + RECHARGE_BUFFER_SECONDS)


def test_no_budget_picks_sooner_window():
    """If both windows exhausted, wait for the SOONER reset."""
    s = {
        "window_5h": {"percent_remaining": 0, "resets_in_h": 3.0},
        "window_weekly": {"percent_remaining": 0, "resets_in_h": 1.0},
    }
    delay = compute_next_delay_seconds(s, "no_budget")
    assert delay == int(1.0 * 3600 + RECHARGE_BUFFER_SECONDS)


def test_completed_goes_again_soon():
    """Completed with budget likely left -> short continue delay (drain queue)."""
    s = _status(w5_rem=50, w5_reset_h=3.0)
    assert compute_next_delay_seconds(s, "completed") == CONTINUE_DELAY_SECONDS


def test_session_expired_backs_off_max():
    assert compute_next_delay_seconds({}, "session_expired") == MAX_DELAY_SECONDS


def test_quota_error_backs_off_max():
    assert compute_next_delay_seconds({}, "quota_error: boom") == MAX_DELAY_SECONDS


def test_no_material_waits_for_next_5h_window():
    s = _status(w5_rem=80, w5_reset_h=4.0)
    delay = compute_next_delay_seconds(s, "no_material")
    assert delay == int(4.0 * 3600 + RECHARGE_BUFFER_SECONDS)


def test_delay_clamped_to_max():
    """A huge reset horizon is clamped to MAX."""
    s = {"window_5h": {"percent_remaining": 0, "resets_in_h": 999}}
    delay = compute_next_delay_seconds(s, "no_budget")
    assert delay == MAX_DELAY_SECONDS


def test_delay_never_below_min():
    s = {"window_5h": {"percent_remaining": 0, "resets_in_h": 0}}
    delay = compute_next_delay_seconds(s, "no_budget")
    assert delay >= MIN_DELAY_SECONDS


def test_no_budget_without_reset_info_backs_off():
    s = {"window_5h": {"percent_remaining": 0}}  # no resets_in_h
    assert compute_next_delay_seconds(s, "no_budget") == MAX_DELAY_SECONDS
