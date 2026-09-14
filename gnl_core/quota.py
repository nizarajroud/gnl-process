"""NotebookLM quota/usage management — compute-based model (2026-09-02+).

Google replaced fixed daily caps with a compute allowance metered against
two windows simultaneously:
  - a rolling ~5h window (recharges continuously)
  - a weekly cap

API (notebooklm-mcp-cli >= 0.11.4):
  client.get_usage() -> list of dicts with keys: window, percent_used,
                        percent_remaining, resets_at (unix ts)
  client.get_entitlement_tier() -> str tier name

Critical gotchas (documented by lib maintainer):
  1. Window order is NOT stable — index by `window` code, never by position.
  2. An expired session returns error code 16 on the usage RPC — this is NOT
     an exhausted quota; it means re-auth is needed.
"""

from datetime import datetime, timezone

# Window type codes (confirmed live)
WINDOW_5H = 1        # rolling ~5h window
WINDOW_WEEKLY = 2    # weekly cap


class SessionExpiredError(Exception):
    """Raised when the NLM session is expired (usage RPC error code 16)."""


def get_quota_status(client=None):
    """Fetch current NLM usage for both windows.

    Returns a dict:
      {
        'tier': str,
        'window_5h':   {'percent_remaining': int, 'resets_at': int, 'resets_in_h': float},
        'window_weekly': {'percent_remaining': int, 'resets_at': int, 'resets_in_h': float},
        'ok': True
      }

    Raises SessionExpiredError if the session is expired (code 16).
    """
    if client is None:
        from notebooklm_tools.mcp.tools._utils import get_client
        client = get_client()

    try:
        usage = client.get_usage()
    except Exception as e:
        msg = str(e)
        # Error code 16 = expired session (NOT quota exhausted)
        if 'code 16' in msg or 'UNAUTHENTICATED' in msg or '16' == msg.strip():
            raise SessionExpiredError(
                "NLM session expired (code 16). Run: nlm auth refresh"
            ) from e
        raise

    try:
        tier = client.get_entitlement_tier()
    except Exception:
        tier = None

    # Index windows by their type code (order is NOT stable!)
    by_window = {}
    for entry in (usage or []):
        w = entry.get('window')
        by_window[w] = entry

    now_ts = datetime.now(timezone.utc).timestamp()

    def _fmt(entry):
        if not entry:
            return None
        resets_at = entry.get('resets_at') or 0
        return {
            'percent_remaining': entry.get('percent_remaining'),
            'percent_used': entry.get('percent_used'),
            'resets_at': resets_at,
            'resets_in_h': round((resets_at - now_ts) / 3600, 1) if resets_at else None,
        }

    return {
        'tier': tier,
        'window_5h': _fmt(by_window.get(WINDOW_5H)),
        'window_weekly': _fmt(by_window.get(WINDOW_WEEKLY)),
        'ok': True,
    }


def has_budget(status, min_percent=1):
    """True if both windows have at least min_percent remaining.

    The 5h window recharges continuously; the weekly cap is the hard limit.
    Generation is possible only if BOTH have budget.
    """
    if not status or not status.get('ok'):
        return False
    w5 = status.get('window_5h') or {}
    ww = status.get('window_weekly') or {}
    r5 = w5.get('percent_remaining')
    rw = ww.get('percent_remaining')
    # If a window is missing, treat conservatively as available (100)
    r5 = 100 if r5 is None else r5
    rw = 100 if rw is None else rw
    return r5 >= min_percent and rw >= min_percent


def next_recharge_local(status, tz_name='America/Toronto'):
    """Return the next 5h-window recharge time as a local datetime string, or None."""
    import zoneinfo
    w5 = (status or {}).get('window_5h') or {}
    ts = w5.get('resets_at')
    if not ts:
        return None
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(zoneinfo.ZoneInfo(tz_name))
    return dt.strftime('%Y-%m-%d %H:%M %Z')
