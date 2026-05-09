#!/usr/bin/env python3
"""Create/reset the GNL database schema from scratch.

Run this script to initialize or recreate the database.
Update this file whenever the schema changes.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')


def setup_database(db_path=None):
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Series catalog (themes and subthemes for form dropdowns)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS series_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme TEXT NOT NULL,
            subtheme TEXT NOT NULL,
            UNIQUE(theme, subtheme)
        )
    ''')

    # Parent configuration
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

    # Podcast download (individual episodes)
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

    # Crawl source
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_source (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme TEXT,
            subtheme TEXT,
            crawl_source_url TEXT NOT NULL,
            UNIQUE(crawl_source_url, theme, subtheme)
        )
    ''')

    # Crawl item
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

    # Seed series_catalog with known themes/subthemes
    seeds = [
        ("aws", "aws-whats-new"),
        ("aws", "aws-solutions-lib"),
        ("aws", "aws-papers"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO series_catalog (theme, subtheme) VALUES (?, ?)", seeds
    )

    conn.commit()
    conn.close()
    print(f"✓ Database ready: {db_path}")


if __name__ == "__main__":
    setup_database()
