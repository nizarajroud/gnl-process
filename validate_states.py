#!/usr/bin/env python3
"""Validate generation and download states before Convert/Combine.

Called by n8n workflow. Exits 0 if all states are ready, exits 1 otherwise.
Prints a report to stdout for n8n logs.

Usage:
    python validate_states.py <source_type> <generation_mode> <theme> <subfolder>
"""

import fire
import os
import sys
import sqlite3
from dotenv import load_dotenv
from resolve_parent import resolve_parent

load_dotenv()


def validate(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None) -> None:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')

    if not os.path.exists(db_path):
        print("❌ Database not found")
        sys.exit(1)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pd.source_id, pd.generation_state, pd.download_state
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ?
        AND pc.generation_mode = ?
        AND pc.podcast_theme = ?
        AND pc.podcast_subtheme = ?
        ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC
    """, (source_type, generation_mode, theme, subfolder))

    records = cursor.fetchall()
    conn.close()

    if not records:
        print("❌ No records found for this configuration")
        sys.exit(1)

    total = len(records)
    generated = sum(1 for r in records if r[1] == 1)
    downloaded = sum(1 for r in records if r[2] == 1)

    gen_missing = [r[0] for r in records if r[1] != 1]
    dl_missing = [r[0] for r in records if r[2] != 1]

    print("=" * 50)
    print("STATE VALIDATION REPORT")
    print("=" * 50)
    print(f"Config: {theme}/{subfolder} ({source_type}, {generation_mode})")
    print(f"Total records: {total}")
    print()

    if generated == total:
        print(f"✅ Generation: {generated}/{total}")
    else:
        print(f"⚠️  Generation: {generated}/{total} — missing: {', '.join(gen_missing)}")

    if downloaded == total:
        print(f"✅ Download: {downloaded}/{total}")
    else:
        print(f"⚠️  Download: {downloaded}/{total} — missing: {', '.join(dl_missing)}")

    print("=" * 50)

    if generated == total and downloaded == total:
        print("→ READY for Convert + Combine")
        sys.exit(0)
    else:
        print("→ NOT READY — waiting for manual approval in n8n")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(validate)
