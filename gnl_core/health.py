"""Preventive dry-run health-check (US-002).

Runs the evening before (18h) and just before the daily pass (~5h30) to verify
ALL components WITHOUT generating anything (zero quota), then sends a compact
Telegram recap. Lets the user detect & fix a problem BEFORE the real run.

Each check is read-only and best-effort (never raises). Returns a dict of
component -> (ok: bool, detail: str).
"""

import os
import shutil


def _check_nlm_session():
    """Session valid + budget available (get_usage is free, fails if session dead)."""
    try:
        from gnl_core.quota import get_quota_status, has_budget, SessionExpiredError, NetworkTimeoutError
        try:
            status = get_quota_status(retries=1, retry_delay=2)
        except SessionExpiredError:
            return False, "session expirée (nlm auth refresh)"
        except NetworkTimeoutError:
            return False, "timeout réseau (transitoire)"
        w5 = status.get('window_5h', {}).get('percent_remaining')
        ww = status.get('window_weekly', {}).get('percent_remaining')
        budget = has_budget(status)
        w5s = f"{round(w5)}%" if isinstance(w5, (int, float)) else "?"
        wws = f"{round(ww)}%" if isinstance(ww, (int, float)) else "?"
        detail = f"5h {w5s} · sem {wws}" + ("" if budget else " · ÉPUISÉ")
        return budget, detail
    except Exception as e:
        return False, f"erreur: {str(e)[:40]}"


def _check_linkedin_venv():
    try:
        path = os.environ.get('LINKEDIN_MCP_PATH', '/home/nizar/HomeWspce/linkedin-mcp-fork')
        venv = os.path.join(path, '.venv', 'bin', 'python')
        return os.path.exists(venv), "venv OK" if os.path.exists(venv) else "venv manquant"
    except Exception as e:
        return False, str(e)[:40]


def _check_drive():
    try:
        from gnl_core.drive import is_drive_accessible
        ok = is_drive_accessible()
        return ok, "accessible" if ok else "inaccessible (/mnt/g)"
    except Exception as e:
        return False, str(e)[:40]


def _check_bedrock():
    """Bedrock reachable (tiny models list — cheap, no generation)."""
    try:
        import boto3
        from gnl_core.config import get_config
        region = get_config().get('BEDROCK_REGION', 'us-east-1')
        client = boto3.client('bedrock', region_name=region)
        client.list_foundation_models()
        return True, "joignable"
    except Exception as e:
        return False, f"KO: {str(e)[:40]}"


def _check_ffmpeg():
    ok = bool(shutil.which('ffmpeg')) and bool(shutil.which('ffprobe'))
    return ok, "ffmpeg+ffprobe" if ok else "ffmpeg/ffprobe manquant"


def _check_pending():
    """How much material is waiting (informational; ok=True unless DB error)."""
    try:
        from gnl_core.config import get_config
        from gnl_core.auto_generate import build_work_queue
        from gnl_core.auto_wiring import list_pending
        defaults = get_config().get('CATEGORY_DEFAULTS', {})
        queue = build_work_queue(defaults, list_pending)
        return True, f"{len(queue)} items"
    except Exception as e:
        return False, f"erreur: {str(e)[:40]}"


CHECKS = [
    ("NLM", _check_nlm_session),
    ("LinkedIn venv", _check_linkedin_venv),
    ("Drive", _check_drive),
    ("Bedrock", _check_bedrock),
    ("ffmpeg", _check_ffmpeg),
    ("File", _check_pending),
]


def health_check():
    """Run all checks. Returns dict name -> (ok, detail). Never raises."""
    results = {}
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"exception: {str(e)[:40]}"
        results[name] = (ok, detail)
    return results


def format_recap(results):
    """Build the compact Telegram recap message from health_check() results."""
    all_ok = all(ok for ok, _ in results.values())
    head = "🧪 GNL — Test à blanc" + (" ✅ tout OK" if all_ok else " ⚠️ problème détecté")
    lines = [head]
    for name, (ok, detail) in results.items():
        mark = "✅" if ok else "❌"
        lines.append(f"{mark} {name}: {detail}")
    if not all_ok:
        lines.append("→ Corriger avant la prochaine passe.")
    return "\n".join(lines)
