"""Configuration management via gnl-config.json."""

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / 'gnl-config.json'

_config = {}


def load_config():
    """Load config from JSON file into os.environ."""
    global _config
    if CONFIG_PATH.exists():
        _config = json.loads(CONFIG_PATH.read_text())
    for key, value in _config.items():
        os.environ.setdefault(key, str(value))
    return _config


def get_config():
    """Get current config dict."""
    if not _config:
        load_config()
    return _config


def save_config(data: dict):
    """Save config dict to JSON file and update os.environ."""
    global _config
    _config = data
    CONFIG_PATH.write_text(json.dumps(data, indent=2) + '\n')
    for key, value in data.items():
        os.environ[key] = str(value)


def export_config() -> str:
    """Return config + prompts as JSON string for download."""
    from .db import get_db
    data = dict(get_config())
    with get_db() as conn:
        rows = conn.execute("SELECT theme, subtheme, prompt FROM series_catalog").fetchall()
    data['_prompts'] = [{"theme": r['theme'], "subtheme": r['subtheme'], "prompt": r['prompt'] or ''} for r in rows]
    return json.dumps(data, indent=2)


def import_config(json_str: str):
    """Import config + prompts from JSON string."""
    from .db import get_db
    data = json.loads(json_str)
    prompts = data.pop('_prompts', None)
    save_config(data)
    if prompts:
        with get_db() as conn:
            for p in prompts:
                conn.execute("UPDATE series_catalog SET prompt=? WHERE theme=? AND subtheme=?", (p['prompt'], p['theme'], p['subtheme']))
            conn.commit()
