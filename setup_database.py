#!/usr/bin/env python3
"""Create/reset the GNL database schema from scratch.

Run this script to initialize or recreate the database.
Update this file whenever the schema changes.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')

CURRENT_VERSION = 4


def setup_database(db_path=None):
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Schema version tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    # Check current version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current = row[0] if row[0] else 0

    if current < 1:
        _apply_v1(cursor)
    if current < 2:
        _apply_v2(cursor)
    if current < 3:
        _apply_v3(cursor)
    if current < 4:
        _apply_v4(cursor)

    conn.commit()
    conn.close()
    print(f"✓ Database ready (v{CURRENT_VERSION}): {db_path}")


def _apply_v1(cursor):
    """v1: Initial schema."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_configuration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_file TEXT,
            source_path TEXT,
            source_type TEXT,
            podcast_theme TEXT,
            podcast_subtheme TEXT,
            split_configuration TEXT,
            generation_mode TEXT,
            combination_state INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS podcast_download (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_configuration_id INTEGER,
            source_id TEXT,
            podcast_name TEXT,
            generation_state INTEGER DEFAULT 0,
            download_state INTEGER DEFAULT 0,
            conversion_state INTEGER DEFAULT 0,
            date TEXT,
            FOREIGN KEY (parent_configuration_id) REFERENCES parent_configuration(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_source (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme TEXT,
            subtheme TEXT,
            crawl_source_url TEXT NOT NULL,
            UNIQUE(crawl_source_url, theme, subtheme)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_source_id INTEGER NOT NULL,
            url_hash TEXT NOT NULL,
            crawl_item_url TEXT NOT NULL,
            post_date TEXT,
            headline TEXT,
            processed_state TEXT DEFAULT 'False',
            aggregation_state TEXT DEFAULT 'False',
            FOREIGN KEY (crawl_source_id) REFERENCES crawl_source(id),
            UNIQUE(url_hash, crawl_source_id)
        )
    ''')

    cursor.execute("INSERT INTO schema_version (version) VALUES (1)")


def _apply_v2(cursor):
    """v2: Series catalog."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS series_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme TEXT NOT NULL,
            subtheme TEXT NOT NULL,
            UNIQUE(theme, subtheme)
        )
    ''')

    seeds = [
        ("aws", "aws-whats-new"),
        ("aws", "aws-solutions-lib"),
        ("aws", "aws-papers"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO series_catalog (theme, subtheme) VALUES (?, ?)", seeds
    )

    cursor.execute("INSERT INTO schema_version (version) VALUES (2)")


def _apply_v3(cursor):
    """v3: Add retry_count for generation failure tracking."""
    cursor.execute("ALTER TABLE podcast_download ADD COLUMN retry_count INTEGER DEFAULT 0")
    cursor.execute("INSERT INTO schema_version (version) VALUES (3)")


def _apply_v4(cursor):
    """v4: Add prompt column to series_catalog."""
    cursor.execute("ALTER TABLE series_catalog ADD COLUMN prompt TEXT DEFAULT ''")
    cursor.execute("INSERT INTO schema_version (version) VALUES (4)")


if __name__ == "__main__":
    setup_database()


