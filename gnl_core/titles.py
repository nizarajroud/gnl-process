"""Generate podcast titles for records with empty podcast_name."""

import os
import re
from .db import get_db


def _generate_title(source_id, source_type, parent_file):
    base_title = os.path.splitext(source_id)[0]
    if source_type in ("GoogleDrive", "LocalStorage"):
        return f"{base_title}-{parent_file}" if parent_file else base_title
    else:
        url = source_id.split('?')[0].split('#')[0].rstrip('/')
        parts = [p for p in url.split('/') if p]
        last_part = parts[-1] if parts else "webpage"
        title = re.sub(r'[^a-zA-Z0-9]', '-', last_part).strip('-')[:50] or "webpage"
        return f"{title}-{parent_file}" if parent_file else title


def generate_titles(parent_id, db_path=None):
    """Generate titles for all records with empty podcast_name. Returns count updated."""
    with get_db(db_path) as conn:
        rows = conn.execute("""
            SELECT pd.id, pd.source_id, pc.source_type, pc.parent_file
            FROM podcast_download pd
            JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
            WHERE pd.parent_configuration_id = ? AND (pd.podcast_name IS NULL OR pd.podcast_name = '')
        """, (parent_id,)).fetchall()

        count = 0
        for row in rows:
            title = _generate_title(row['source_id'], row['source_type'], row['parent_file'])
            conn.execute("UPDATE podcast_download SET podcast_name = ? WHERE id = ?", (title, row['id']))
            count += 1

        conn.commit()
    return count
