"""Database access layer."""

import os
import sqlite3
from contextlib import contextmanager
from .config import load_config

load_config()

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gnl.db')


@contextmanager
def get_db(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def resolve_parent(parent_id, db_path=None):
    """Resolve parent config from parent_id. Returns (source_type, generation_mode, theme, subfolder)."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT source_type, generation_mode, podcast_theme, podcast_subtheme FROM parent_configuration WHERE id = ?",
            (parent_id,)
        ).fetchone()
    if not row:
        raise ValueError(f"Parent ID {parent_id} not found")
    return row['source_type'], row['generation_mode'].lower(), row['podcast_theme'], row['podcast_subtheme'].lower()


def get_records(parent_id, db_path=None, **state_filters):
    """Get podcast_download records for a parent with optional state filters.
    
    Example: get_records(1, generation_state=1, download_state=0)
    """
    source_type, generation_mode, theme, subfolder = resolve_parent(parent_id, db_path)
    
    where = ["pc.source_type = ?", "pc.generation_mode = ?", "pc.podcast_theme = ?", "pc.podcast_subtheme = ?",
             "pd.parent_configuration_id = ?"]
    params = [source_type, generation_mode, theme, subfolder, parent_id]
    
    for col, val in state_filters.items():
        where.append(f"pd.{col} = ?")
        params.append(val)
    
    query = f"""SELECT pd.id, pd.source_id, pd.podcast_name, pc.parent_file, pc.source_path
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE {' AND '.join(where)}
        ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC"""
    
    with get_db(db_path) as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def update_state(record_id, db_path=None, **updates):
    """Update state fields for a record. Example: update_state(1, generation_state=1)"""
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [record_id]
    with get_db(db_path) as conn:
        conn.execute(f"UPDATE podcast_download SET {sets} WHERE id = ?", vals)
        conn.commit()


def parent_status(parent_id, db_path=None):
    """Return counts: total, generated, downloaded, converted, combined, failed."""
    with get_db(db_path) as conn:
        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN generation_state = 1 THEN 1 ELSE 0 END) as generated,
                   SUM(CASE WHEN download_state = 1 THEN 1 ELSE 0 END) as downloaded,
                   SUM(CASE WHEN conversion_state = 1 THEN 1 ELSE 0 END) as converted,
                   SUM(CASE WHEN retry_count >= ? THEN 1 ELSE 0 END) as failed
            FROM podcast_download WHERE parent_configuration_id = ?
        """, (int(os.getenv('MAX_GENERATION_RETRIES', '3')), parent_id)).fetchone()
        combined_row = conn.execute(
            "SELECT combination_state FROM parent_configuration WHERE id = ?", (parent_id,)
        ).fetchone()
    result = dict(row)
    result['combined'] = (combined_row['combination_state'] if combined_row else 0)
    return result


def get_active_parents(db_path=None):
    """Find all parent_ids with pending work."""
    with get_db(db_path) as conn:
        rows = conn.execute("""
            SELECT DISTINCT parent_configuration_id FROM podcast_download
            WHERE generation_state = 0 OR download_state = 0 OR conversion_state = 0
        """).fetchall()
    return [r['parent_configuration_id'] for r in rows]
