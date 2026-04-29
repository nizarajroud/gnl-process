#!/usr/bin/env python3
"""Crawl AWS What's New via API, extract announcement links, store in crawl_source + crawl_item.

Usage:
    python crawl_links.py crawl <url> [--date-filter DATE] [--max-items 50]
    python crawl_links.py list [--source-id ID]

Examples:
    python crawl_links.py crawl "https://aws.amazon.com/new/" --date-filter "2026-04-24"
    python crawl_links.py list
"""

import fire
import os
import sqlite3
import hashlib
import requests
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
AWS_API = "https://aws.amazon.com/api/dirs/items/search"


def _hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()[:16]


def crawl(url, theme, subtheme, month=None, max_items=500):
    """Crawl AWS What's New via API, filter by month, insert into DB.
    
    Args:
        month: Month number as string, e.g. "04" for April. Fetches all items for that month.
    """
    MONTHS_FR = {1:'janvier',2:'février',3:'mars',4:'avril',5:'mai',6:'juin',
                 7:'juillet',8:'août',9:'septembre',10:'octobre',11:'novembre',12:'décembre'}

    current_year = datetime.now().year
    month_prefix = f"{current_year}-{month}" if month else None

    page_size = 25
    all_items = []

    for page_num in range(0, max_items // page_size + 1):
        resp = requests.get(AWS_API, params={
            "item.directoryId": "whats-new-v2",
            "sort_by": "item.additionalFields.postDateTime",
            "sort_order": "desc",
            "size": page_size,
            "page": page_num,
            "item.locale": "en_US",
        }, timeout=15)
        resp.raise_for_status()

        items = resp.json().get('items', [])
        if not items:
            break

        stop = False
        for item in items:
            fields = item.get('item', {}).get('additionalFields', {})
            post_dt = fields.get('postDateTime', '')
            post_date = post_dt[:10]  # "2026-04-24"
            post_month = post_dt[:7]  # "2026-04"
            headline = fields.get('headline', '')
            item_url = fields.get('headlineUrl', '')

            if not item_url:
                continue

            if item_url.startswith('/'):
                item_url = f"https://aws.amazon.com{item_url}"

            try:
                dt = datetime.fromisoformat(post_dt.replace('Z', '+00:00'))
                date_formatted = f"{dt.day} {MONTHS_FR[dt.month]} {dt.year}"
            except (ValueError, KeyError):
                date_formatted = post_date

            if month_prefix:
                if post_month == month_prefix:
                    all_items.append((item_url, date_formatted, headline))
                elif post_month < month_prefix:
                    # Past the target month, stop
                    print(f"⛔ Hit {post_month}, past target month {month_prefix}, stopping.")
                    stop = True
                    break
                # else: future month, skip but continue
            else:
                all_items.append((item_url, date_formatted, headline))

        if stop:
            break

    # Insert into DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('INSERT OR IGNORE INTO crawl_source (theme, subtheme, crawl_source_url) VALUES (?, ?, ?)', (theme, subtheme, url))
    cursor.execute('SELECT id FROM crawl_source WHERE crawl_source_url = ? AND theme = ? AND subtheme = ?', (url, theme, subtheme))
    source_id = cursor.fetchone()[0]

    inserted = 0
    for item_url, date_formatted, headline in all_items:
        try:
            cursor.execute(
                'INSERT INTO crawl_item (crawl_source_id, url_hash, crawl_item_url, post_date, headline, processed_state) VALUES (?, ?, ?, ?, ?, ?)',
                (source_id, _hash_url(item_url), item_url, date_formatted, headline, 'False')
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print(f"✓ {len(all_items)} announcements found, {inserted} new inserted, {len(all_items) - inserted} duplicates skipped")


def list(source_id=None):
    """List crawl items from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = ('SELECT ci.id, ci.url_hash, ci.crawl_item_url, cs.crawl_source_url '
             'FROM crawl_item ci JOIN crawl_source cs ON ci.crawl_source_id = cs.id')
    params = []
    if source_id:
        query += ' WHERE ci.crawl_source_id = ?'
        params.append(source_id)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No items found.")
        return

    print(f"{'ID':<5} {'Hash':<18} {'URL'}")
    print("-" * 120)
    for row in rows:
        print(f"{row[0]:<5} {row[1]:<18} {row[2]}")
    print(f"\nTotal: {len(rows)} items")


if __name__ == '__main__':
    fire.Fire({'crawl': crawl, 'list': list})
