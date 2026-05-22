"""Content generation — create source PDFs from AWS sources."""

import os
import hashlib
import sqlite3
import requests
import markdown
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

from .db import get_db
from .config import get_config

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


def generate_whats_new(month, on_progress=None):
    """Generate What's New PDF for a given month. Returns output path or None."""
    from weasyprint import HTML

    month = str(month).zfill(2)
    month_name = MONTHS_FR.get(month)
    if not month_name:
        return None

    config = get_config()
    current_year = datetime.now().year
    month_prefix = f"{current_year}-{month}"

    # Crawl
    if on_progress:
        on_progress(f"🔍 Crawl des annonces {month_name} {current_year}...")

    all_items = []
    for page_num in range(50):
        resp = requests.get(AWS_API, params={
            "item.directoryId": "whats-new-v2",
            "sort_by": "item.additionalFields.postDateTime",
            "sort_order": "desc",
            "size": 25,
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

            if post_dt[:7] == month_prefix:
                all_items.append((item_url, date_formatted, headline))
            elif post_dt[:7] < month_prefix:
                stop = True
                break

        if stop:
            break

    if not all_items:
        return None

    if on_progress:
        on_progress(f"✓ {len(all_items)} annonces trouvées")

    # Aggregate by day + fetch content
    if on_progress:
        on_progress("📄 Récupération du contenu...")

    by_day = defaultdict(list)
    for item_url, date_fmt, headline in all_items:
        by_day[date_fmt].append((item_url, headline))

    md_parts = [f"# What's New — {month_name.capitalize()} {current_year}\n"]
    for day in sorted(by_day.keys(), key=lambda d: int(d.split()[0])):
        items = by_day[day]
        md_parts.append(f"\n## {day}\n")
        for item_url, headline in items:
            content = _fetch_content(item_url)
            md_parts.append(f"### {headline}\n")
            md_parts.append(f"{content}\n")
            md_parts.append("---\n")

    # Generate PDF
    if on_progress:
        on_progress("📑 Génération du PDF...")

    html_content = markdown.markdown('\n'.join(md_parts))
    html_full = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
    body {{ font-family: Arial, sans-serif; margin: 40px; font-size: 11px; line-height: 1.5; }}
    h1 {{ color: #232f3e; border-bottom: 2px solid #ff9900; padding-bottom: 8px; }}
    h2 {{ color: #232f3e; background: #f5f5f5; padding: 8px; margin-top: 30px; }}
    h3 {{ color: #0073bb; margin-top: 15px; }}
    hr {{ border: none; border-top: 1px solid #ddd; margin: 15px 0; }}
</style>
</head><body>{html_content}</body></html>"""

    inbox = config.get('INBOX_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'inbox'))
    output_dir = Path(inbox) / "aws" / "aws-whats-new"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"whatsnew-{month_name}.pdf"

    HTML(string=html_full).write_pdf(str(output_path))

    if on_progress:
        on_progress(f"✅ {output_path.name} ({len(all_items)} annonces)")

    return str(output_path)
