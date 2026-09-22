"""Telegram alerting for GNL — mirrors the `kuse-alert` bash pattern.

Reuses the SAME Telegram channel/token as kuse-alert:
  - credentials from PROC/kiro-budget-alert/.env (KIRO_TG_TOKEN, KIRO_TG_CHAT_ID)
  - sends via the Telegram sendMessage API (curl-equivalent, stdlib urllib)
  - anti-duplication flags under ~/.local/state/gnl-alert/ so the same alert
    isn't resent repeatedly

Alerts are best-effort: any failure here must never break generation.
"""

import os
import json
import urllib.request
import urllib.parse
from pathlib import Path


_ENV_PATH = os.environ.get(
    'GNL_ALERT_ENV',
    '/mnt/d/PERSONAL/SKILLS/Technical/workspace/PROC/kiro-budget-alert/.env',
)
_FLAG_DIR = Path.home() / '.local' / 'state' / 'gnl-alert'


def _load_telegram_creds():
    """Read KIRO_TG_TOKEN and KIRO_TG_CHAT_ID from the shared .env.

    Returns (token, chat_id) or (None, None) if unavailable.
    """
    # Env vars take precedence (useful for tests / overrides).
    token = os.environ.get('KIRO_TG_TOKEN')
    chat_id = os.environ.get('KIRO_TG_CHAT_ID')
    if token and chat_id:
        return token.strip('"'), chat_id.strip('"')

    if not os.path.exists(_ENV_PATH):
        return None, None
    vals = {}
    try:
        with open(_ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line.startswith('KIRO_TG_TOKEN') or line.startswith('KIRO_TG_CHAT_ID'):
                    k, _, v = line.partition('=')
                    vals[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        return None, None
    return vals.get('KIRO_TG_TOKEN'), vals.get('KIRO_TG_CHAT_ID')


def send_telegram(message):
    """Send a Telegram message. Returns True on success, False otherwise.

    Never raises — alerting must not break the caller.
    """
    token, chat_id = _load_telegram_creds()
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def alert(key, message, once_per=None):
    """Send an alert, optionally de-duplicated by `key`.

    once_per: if set (e.g. 'day'), the same key won't re-alert within that window.
    Uses a flag file per (key, window). Best-effort; never raises.
    """
    try:
        _FLAG_DIR.mkdir(parents=True, exist_ok=True)
        if once_per == 'day':
            from datetime import datetime
            stamp = datetime.now().strftime('%Y-%m-%d')
            flag = _FLAG_DIR / f"{key}-{stamp}"
            if flag.exists():
                return False  # already alerted today
            ok = send_telegram(message)
            if ok:
                flag.touch()
            return ok
        return send_telegram(message)
    except Exception:
        return False
