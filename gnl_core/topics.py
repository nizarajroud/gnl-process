"""
Meta Topics — persistent library for the generic Doc→Meta tool.

A Topic groups its sources (files [name only], pasted texts [saved as .txt],
links [URL]) and keeps a modification journal. The latest state is consultable;
parts are regenerated on demand from texts + links (+ files provided at click
time — file names are just references).

Fully independent of the exam/podcast pipeline. Tables are additive and created
idempotently (CREATE TABLE IF NOT EXISTS), so they never touch existing schema.
"""

import os
from datetime import datetime
from pathlib import Path

from gnl_core.db import get_db


def _now():
    return datetime.now().isoformat(timespec='seconds')


def ensure_schema(db_path=None):
    """Create the topics tables if they don't exist. Idempotent, additive."""
    with get_db(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS meta_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS meta_topic_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                display_name TEXT NOT NULL,
                stored_path TEXT,
                added_at TEXT NOT NULL,
                FOREIGN KEY (topic_id) REFERENCES meta_topics(id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS meta_topic_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                at TEXT NOT NULL,
                FOREIGN KEY (topic_id) REFERENCES meta_topics(id)
            )
        ''')
        conn.commit()


def _log(conn, topic_id, action, detail=''):
    conn.execute(
        "INSERT INTO meta_topic_log (topic_id, action, detail, at) VALUES (?,?,?,?)",
        (topic_id, action, detail, _now()))


# --- Topic CRUD ------------------------------------------------------------

def create_topic(title, db_path=None):
    ensure_schema(db_path)
    title = (title or '').strip() or 'Sans titre'
    with get_db(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO meta_topics (title, created_at, updated_at) VALUES (?,?,?)",
            (title, _now(), _now()))
        tid = cur.lastrowid
        _log(conn, tid, 'created', f"titre: {title}")
        conn.commit()
    return tid


def list_topics(db_path=None):
    ensure_schema(db_path)
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM meta_topics ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            n = conn.execute(
                "SELECT COUNT(*) c FROM meta_topic_sources WHERE topic_id=?", (r['id'],)
            ).fetchone()['c']
            result.append({'id': r['id'], 'title': r['title'],
                           'created_at': r['created_at'], 'updated_at': r['updated_at'],
                           'sources': n})
    return result


def get_topic(topic_id, db_path=None):
    ensure_schema(db_path)
    with get_db(db_path) as conn:
        t = conn.execute(
            "SELECT id, title, created_at, updated_at FROM meta_topics WHERE id=?",
            (topic_id,)).fetchone()
        if not t:
            return None
        sources = conn.execute(
            "SELECT id, type, display_name, stored_path, added_at FROM meta_topic_sources "
            "WHERE topic_id=? ORDER BY added_at", (topic_id,)).fetchall()
        log = conn.execute(
            "SELECT action, detail, at FROM meta_topic_log WHERE topic_id=? ORDER BY at DESC",
            (topic_id,)).fetchall()
        return {
            'id': t['id'], 'title': t['title'],
            'created_at': t['created_at'], 'updated_at': t['updated_at'],
            'sources': [dict(s) for s in sources],
            'log': [dict(l) for l in log],
        }


def rename_topic(topic_id, new_title, db_path=None):
    with get_db(db_path) as conn:
        conn.execute("UPDATE meta_topics SET title=?, updated_at=? WHERE id=?",
                     (new_title.strip(), _now(), topic_id))
        _log(conn, topic_id, 'renamed', f"→ {new_title.strip()}")
        conn.commit()


def delete_topic(topic_id, db_path=None):
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM meta_topic_sources WHERE topic_id=?", (topic_id,))
        conn.execute("DELETE FROM meta_topic_log WHERE topic_id=?", (topic_id,))
        conn.execute("DELETE FROM meta_topics WHERE id=?", (topic_id,))
        conn.commit()


# --- Sources ---------------------------------------------------------------

def _topic_dir(title):
    """Folder for a topic's saved texts: INBOX/Meta-AI/<title>/ (fallback: cwd)."""
    inbox = os.environ.get('INBOX_FOLDER', '') or os.getcwd()
    safe = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in title).strip() or 'topic'
    d = Path(inbox) / 'Meta-AI' / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_file_source(topic_id, filename, db_path=None):
    """Store just the file name as a reference (no content, no path)."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO meta_topic_sources (topic_id, type, display_name, stored_path, added_at) "
            "VALUES (?,?,?,?,?)", (topic_id, 'file', filename, None, _now()))
        conn.execute("UPDATE meta_topics SET updated_at=? WHERE id=?", (_now(), topic_id))
        _log(conn, topic_id, 'source_added', f"fichier: {filename}")
        conn.commit()


def add_link_source(topic_id, url, db_path=None):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO meta_topic_sources (topic_id, type, display_name, stored_path, added_at) "
            "VALUES (?,?,?,?,?)", (topic_id, 'link', url, None, _now()))
        conn.execute("UPDATE meta_topics SET updated_at=? WHERE id=?", (_now(), topic_id))
        _log(conn, topic_id, 'source_added', f"lien: {url}")
        conn.commit()


def add_text_source(topic_id, text, label=None, db_path=None):
    """Save pasted text as a .txt under Meta-AI/<title>/ and store its path."""
    topic = get_topic(topic_id, db_path)
    title = topic['title'] if topic else f"topic{topic_id}"
    with get_db(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO meta_topic_sources (topic_id, type, display_name, stored_path, added_at) "
            "VALUES (?,?,?,?,?)",
            (topic_id, 'text', label or 'Texte collé', None, _now()))
        sid = cur.lastrowid
        path = _topic_dir(title) / f"text_{sid}.txt"
        path.write_text(text, encoding='utf-8')
        conn.execute("UPDATE meta_topic_sources SET stored_path=? WHERE id=?",
                     (str(path), sid))
        conn.execute("UPDATE meta_topics SET updated_at=? WHERE id=?", (_now(), topic_id))
        _log(conn, topic_id, 'source_added', f"texte: {label or 'Texte collé'} → {path.name}")
        conn.commit()
    return sid


def remove_source(topic_id, source_id, db_path=None):
    with get_db(db_path) as conn:
        row = conn.execute("SELECT type, display_name, stored_path FROM meta_topic_sources "
                           "WHERE id=? AND topic_id=?", (source_id, topic_id)).fetchone()
        if row and row['stored_path']:
            try:
                os.unlink(row['stored_path'])
            except Exception:
                pass
        conn.execute("DELETE FROM meta_topic_sources WHERE id=? AND topic_id=?",
                     (source_id, topic_id))
        conn.execute("UPDATE meta_topics SET updated_at=? WHERE id=?", (_now(), topic_id))
        if row:
            _log(conn, topic_id, 'source_removed', f"{row['type']}: {row['display_name']}")
        conn.commit()


# --- Part generation from a topic -----------------------------------------

def build_topic_corpus(topic_id, on_progress=None, db_path=None):
    """Assemble the topic's corpus text from its texts (.txt) + links (scraped).

    File sources are name-only references (no content) and are NOT included in
    the corpus — they are shown in the UI as a memo. Returns (corpus, skipped).
    """
    topic = get_topic(topic_id, db_path)
    if not topic:
        raise ValueError("Topic introuvable")
    blocks = []
    skipped = []
    for s in topic['sources']:
        if s['type'] == 'text' and s['stored_path']:
            try:
                t = Path(s['stored_path']).read_text(encoding='utf-8', errors='ignore')
                if t.strip():
                    blocks.append(f"# {s['display_name']}\n\n{t.strip()}")
                    if on_progress:
                        on_progress(f"✓ texte {s['display_name']}: {len(t)} chars")
            except Exception as e:
                skipped.append(f"{s['display_name']} ({str(e)[:50]})")
        elif s['type'] == 'link':
            try:
                from gnl_core.url_fetch import fetch_url_text
                t = fetch_url_text(s['display_name'])
                blocks.append(f"# {s['display_name']}\n\n{t}")
                if on_progress:
                    on_progress(f"✓ lien {s['display_name'][:50]}: {len(t)} chars")
            except Exception as e:
                skipped.append(f"{s['display_name'][:50]} ({str(e)[:50]})")
    return "\n\n".join(blocks), skipped


def generate_topic_parts(topic_id, on_progress=None, max_chars=None,
                         prompt_template=None, db_path=None):
    """Build the topic corpus and split it into Meta AI parts.
    Returns {'parts': [...], 'skipped': [...], 'name': str} or raises ValueError."""
    from gnl_core.meta_export import generate_doc_export
    topic = get_topic(topic_id, db_path)
    if not topic:
        raise ValueError("Topic introuvable")
    corpus, skipped = build_topic_corpus(topic_id, on_progress=on_progress, db_path=db_path)
    if not corpus.strip():
        raise ValueError("Aucun contenu exploitable dans ce topic (ajoute du texte ou des liens).")
    out_dir = _topic_dir(topic['title']) / 'parts'
    parts = generate_doc_export(corpus, topic['title'], str(out_dir),
                                on_progress=on_progress, max_chars=max_chars,
                                prompt_template=prompt_template)
    with get_db(db_path) as conn:
        _log(conn, topic_id, 'generated', f"{len(parts)} parts")
        conn.commit()
    return {'name': topic['title'], 'out_dir': str(out_dir),
            'parts': parts, 'skipped': skipped}
