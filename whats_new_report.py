#!/usr/bin/env python3
"""Generate a What's New report for a given month.

Crawls AWS What's New API, fetches content for each announcement,
and generates a single PDF grouped by day.

Usage:
    python whats_new_report.py <month> <theme> <subtheme>

Examples:
    python whats_new_report.py 04 AWS AWS-WHATS-NEW
"""

import fire
import os
import hashlib
import sqlite3
import requests
import markdown
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from weasyprint import HTML

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
AWS_API = "https://aws.amazon.com/api/dirs/items/search"
MONTHS_FR = {
    '01': 'janvier', '02': 'février', '03': 'mars', '04': 'avril',
    '05': 'mai', '06': 'juin', '07': 'juillet', '08': 'août',
    '09': 'septembre', '10': 'octobre', '11': 'novembre', '12': 'décembre'
}


def _hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _fetch_content(url):
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        main = soup.find('main') or soup.find('article')
        if not main:
            return "(contenu non disponible)"
        parts = [el.get_text(strip=True) for el in main.find_all(['p', 'li', 'h2', 'h3']) if el.get_text(strip=True)]
        return '\n\n'.join(parts) if parts else "(contenu vide)"
    except Exception as e:
        return f"(erreur: {e})"


def run(month, theme, subtheme):
    month = str(month).zfill(2)
    month_name = MONTHS_FR.get(month)
    if not month_name:
        print(f"Mois invalide: {month}")
        return

    current_year = datetime.now().year
    month_prefix = f"{current_year}-{month}"

    # --- STEP 1: Crawl ---
    print(f"🔍 Crawl des annonces pour {month_name} {current_year}...")
    all_items = []
    page_size = 25

    for page_num in range(50):
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
            post_month = post_dt[:7]
            headline = fields.get('headline', '')
            item_url = fields.get('headlineUrl', '')
            if not item_url:
                continue
            if item_url.startswith('/'):
                item_url = f"https://aws.amazon.com{item_url}"

            try:
                dt = datetime.fromisoformat(post_dt.replace('Z', '+00:00'))
                date_formatted = f"{dt.day} {MONTHS_FR[str(dt.month).zfill(2)]}"
            except (ValueError, KeyError):
                date_formatted = post_dt[:10]

            if post_month == month_prefix:
                all_items.append((item_url, date_formatted, headline))
            elif post_month < month_prefix:
                stop = True
                break

        if stop:
            break

    print(f"  ✓ {len(all_items)} annonces trouvées")

    if not all_items:
        print("Aucune annonce trouvée.")
        return

    # --- STEP 1b: Save to DB ---
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO crawl_source (theme, subtheme, crawl_source_url) VALUES (?, ?, ?)',
                   (theme, subtheme, f"https://aws.amazon.com/new/"))
    cursor.execute('SELECT id FROM crawl_source WHERE theme = ? AND subtheme = ? AND crawl_source_url = ?',
                   (theme, subtheme, f"https://aws.amazon.com/new/"))
    source_id = cursor.fetchone()[0]

    inserted = 0
    for item_url, date_fmt, headline in all_items:
        try:
            cursor.execute(
                'INSERT INTO crawl_item (crawl_source_id, url_hash, crawl_item_url, post_date, headline, processed_state, aggregation_state) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (source_id, _hash_url(item_url), item_url, date_fmt, headline, 'False', 'False'))
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    print(f"  ✓ {inserted} nouvelles, {len(all_items) - inserted} doublons ignorés")

    # --- STEP 2: Aggregate by day + fetch content ---
    print(f"\n📄 Agrégation par jour et récupération du contenu...")
    by_day = defaultdict(list)
    for item_url, date_fmt, headline in all_items:
        by_day[date_fmt].append((item_url, headline))

    md_parts = [f"# What's New — {month_name.capitalize()} {current_year}\n"]

    for day in sorted(by_day.keys(), key=lambda d: int(d.split()[0])):
        items = by_day[day]
        md_parts.append(f"\n## {day}\n")
        print(f"  📅 {day} — {len(items)} annonces")

        for item_url, headline in items:
            content = _fetch_content(item_url)
            md_parts.append(f"### {headline}\n")
            md_parts.append(f"**Source:** {item_url}\n")
            md_parts.append(f"{content}\n")
            md_parts.append("---\n")

    # --- STEP 3: Generate PDF ---
    print(f"\n📑 Génération du PDF...")
    combined_md = '\n'.join(md_parts)
    html_content = markdown.markdown(combined_md)

    html_full = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
    body {{ font-family: Arial, sans-serif; margin: 40px; font-size: 11px; line-height: 1.5; }}
    h1 {{ color: #232f3e; border-bottom: 2px solid #ff9900; padding-bottom: 8px; }}
    h2 {{ color: #232f3e; background: #f5f5f5; padding: 8px; margin-top: 30px; }}
    h3 {{ color: #0073bb; margin-top: 15px; }}
    hr {{ border: none; border-top: 1px solid #ddd; margin: 15px 0; }}
    a {{ color: #0073bb; }}
</style>
</head><body>{html_content}</body></html>"""

    base_path = os.getenv('GNL_PROCESSING_PATH', os.path.dirname(os.path.abspath(__file__)))
    output_dir = Path(base_path) / subtheme
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"whatsnew-{month_name}.pdf"

    HTML(string=html_full).write_pdf(str(output_path))

    # Mark items as aggregated
    for item_url, _, _ in all_items:
        cursor.execute('UPDATE crawl_item SET aggregation_state = "True" WHERE url_hash = ?', (_hash_url(item_url),))
    conn.commit()
    conn.close()

    print(f"\n✅ Rapport généré: {output_path}")
    print(f"   {len(all_items)} annonces, {len(by_day)} jours")


if __name__ == '__main__':
    fire.Fire(run)
