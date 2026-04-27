#!/usr/bin/env python3
"""Crawl a web page, extract links, and store them in crawled_links table.

Usage:
    python crawl_links.py <url> <theme> [subtheme] [--filter PATTERN] [--dry-run] [--list]
    python crawl_links.py --list [--theme THEME]

Examples:
    python crawl_links.py "https://aws.amazon.com/solutions/" AIP solutions
    python crawl_links.py "https://atesino.com/course/123" AIP exam --filter ".pdf"
    python crawl_links.py --list --theme AIP
    python crawl_links.py --dry-run "https://aws.amazon.com/solutions/" AIP solutions
"""

import fire
import os
import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')


def crawl(url, theme, subtheme=None, filter=None, dry_run=False):
    """Crawl a URL, extract links, insert into crawled_links."""
    resp = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    domain = urlparse(url).netloc
    now = datetime.now().isoformat()

    links = []
    for a in soup.find_all('a', href=True):
        href = urljoin(url, a['href'])
        parsed = urlparse(href)

        # Skip non-http, anchors, mailto, javascript
        if parsed.scheme not in ('http', 'https'):
            continue
        # Remove fragment
        href = parsed._replace(fragment='').geturl()

        # Apply filter if provided
        if filter and filter not in href:
            continue

        title = a.get_text(strip=True)[:200] or None
        link_domain = parsed.netloc

        links.append((url, href, title, link_domain, theme, subtheme, now))

    # Deduplicate by URL
    seen = set()
    unique_links = []
    for link in links:
        if link[1] not in seen:
            seen.add(link[1])
            unique_links.append(link)

    if dry_run:
        print(f"Found {len(unique_links)} unique links from {url}:")
        for link in unique_links:
            print(f"  {link[1]}  ({link[2] or 'no title'})")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0
    for link in unique_links:
        try:
            cursor.execute('''
                INSERT INTO crawled_links (source_url, link_url, link_title, domain, podcast_theme, podcast_subtheme, crawl_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', link)
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # duplicate, skip

    conn.commit()
    conn.close()
    print(f"✓ Crawled {url}: {len(unique_links)} links found, {inserted} new inserted, {len(unique_links) - inserted} duplicates skipped")


def list(theme=None, subtheme=None, state='pending'):
    """List crawled links from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT id, link_url, link_title, podcast_theme, podcast_subtheme, state, crawl_date FROM crawled_links WHERE 1=1"
    params = []
    if theme:
        query += " AND podcast_theme = ?"
        params.append(theme)
    if subtheme:
        query += " AND podcast_subtheme = ?"
        params.append(subtheme)
    if state != 'all':
        query += " AND state = ?"
        params.append(state)
    query += " ORDER BY crawl_date DESC"

    rows = cursor.fetchall()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No links found.")
        return

    print(f"{'ID':<5} {'State':<10} {'Theme':<8} {'Sub':<12} {'URL'}")
    print("-" * 100)
    for row in rows:
        print(f"{row[0]:<5} {row[5]:<10} {row[3]:<8} {row[4] or '':<12} {row[1]}")
    print(f"\nTotal: {len(rows)} links")


if __name__ == '__main__':
    fire.Fire({'crawl': crawl, 'list': list})
