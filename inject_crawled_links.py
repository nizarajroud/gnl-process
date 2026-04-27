#!/usr/bin/env python3
"""Inject pending crawled links into the podcast generation pipeline.

Transfers links from crawled_links (state=pending) into parent_configuration + podcast_download,
so the existing n8n workflow can process them.

Usage:
    python inject_crawled_links.py <theme> [subtheme]

Examples:
    python inject_crawled_links.py AIP solutions
    python inject_crawled_links.py AIP exam
"""

import fire
import os
import sqlite3
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')


def inject(theme, subtheme=None):
    """Inject pending crawled links into parent_configuration + podcast_download."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT id, link_url, link_title FROM crawled_links WHERE state = 'pending' AND podcast_theme = ?"
    params = [theme]
    if subtheme:
        query += " AND podcast_subtheme = ?"
        params.append(subtheme)

    cursor.execute(query, params)
    links = cursor.fetchall()

    if not links:
        print("No pending links to inject.")
        conn.close()
        return

    now = datetime.now().isoformat()

    # Create one parent_configuration for this batch
    cursor.execute('''
        INSERT INTO parent_configuration
        (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, generation_mode, combination_state)
        VALUES (?, ?, 'WebAndYoutube', ?, ?, 'bulk', 0)
    ''', (f"crawl-{theme}-{subtheme or 'all'}-{now[:10]}", '', theme, subtheme or ''))

    parent_id = cursor.lastrowid

    # Insert each link into podcast_download and update crawled_links
    for cl_id, link_url, link_title in links:
        cursor.execute('''
            INSERT INTO podcast_download
            (parent_configuration_id, source_id, podcast_name, generation_state, download_state, conversion_state, date)
            VALUES (?, ?, '', 0, 0, 0, NULL)
        ''', (parent_id, link_url))

        pd_id = cursor.lastrowid
        cursor.execute('''
            UPDATE crawled_links SET state = 'injected', podcast_download_id = ?, injected_date = ?
            WHERE id = ?
        ''', (pd_id, now, cl_id))

    conn.commit()
    conn.close()
    print(f"✓ Injected {len(links)} links into pipeline (parent_configuration_id={parent_id})")


if __name__ == '__main__':
    fire.Fire(inject)
