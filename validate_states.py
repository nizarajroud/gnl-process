#!/usr/bin/env python3
"""Validate all states after Convert. Reset failed records and signal retry or ready for Combine.

Exit codes:
  0 = all records complete → ready for Combine
  1 = failed records reset, should retry (loop back to Generate)
  2 = max retries exceeded → stop, needs manual intervention
"""

import fire
import os
import sys
import json
import sqlite3
from dotenv import load_dotenv
from resolve_parent import resolve_parent

load_dotenv()

MAX_LOOPS = 3
LOOP_FILE = '/tmp/gnl-validate-loop-count'


def validate(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None) -> None:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')

    if not os.path.exists(db_path):
        print("❌ Database not found")
        sys.exit(2)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT pd.id, pd.source_id, pd.generation_state, pd.download_state, pd.conversion_state
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
    """
    params = [source_type, generation_mode, theme, subfolder]
    if parent_id:
        query += " AND pd.parent_configuration_id = ?"
        params.append(parent_id)
    query += " ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC"

    cursor.execute(query, params)
    records = cursor.fetchall()

    if not records:
        print("❌ No records found")
        conn.close()
        sys.exit(2)

    # VALIDATE_CHECKS: comma-separated list of states to validate (generation,download,conversion)
    checks = os.getenv('VALIDATE_CHECKS', 'generation,download,conversion').split(',')
    
    total = len(records)
    # r[2]=generation_state, r[3]=download_state, r[4]=conversion_state
    def is_complete(r):
        if 'generation' in checks and r[2] != 1:
            return False
        if 'download' in checks and r[3] != 1:
            return False
        if 'conversion' in checks and r[4] != 1:
            return False
        return True

    complete = [r for r in records if is_complete(r)]
    pending_gen = [r for r in records if r[2] != 1]
    failed_dl = [r for r in records if 'download' in checks and r[2] == 1 and r[3] == 0]
    failed_conv = [r for r in records if 'conversion' in checks and r[3] == 1 and r[4] == 0]

    print("=" * 50)
    print("VALIDATION REPORT")
    print("=" * 50)
    print(f"Total: {total} | Complete: {len(complete)} | Pending gen: {len(pending_gen)} | Pending download: {len(failed_dl)} | Pending convert: {len(failed_conv)}")
    if pending_gen:
        print(f"  Pending generation: {', '.join(r[1] for r in pending_gen)}")
    if failed_dl:
        print(f"  Pending download: {', '.join(r[1] for r in failed_dl)}")
    if failed_conv:
        print(f"  Pending convert: {', '.join(r[1] for r in failed_conv)}")
    print("=" * 50)

    if len(complete) == total:
        print("✅ All records complete → ready for Combine")
        # Reset loop counter
        if os.path.exists(LOOP_FILE):
            os.remove(LOOP_FILE)
        conn.close()
        sys.exit(0)

    # There are incomplete records — check loop count
    loop_count = 0
    if os.path.exists(LOOP_FILE):
        with open(LOOP_FILE, 'r') as f:
            loop_count = int(f.read().strip())

    loop_count += 1

    if loop_count > MAX_LOOPS:
        print(f"❌ Max retry loops ({MAX_LOOPS}) exceeded. Manual intervention needed.")
        if os.path.exists(LOOP_FILE):
            os.remove(LOOP_FILE)
        conn.close()
        sys.exit(2)

    # Save loop count
    with open(LOOP_FILE, 'w') as f:
        f.write(str(loop_count))

    # No reset needed — records stay at 0 until successfully processed
    conn.close()
    conn.close()

    print(f"🔄 Loop {loop_count}/{MAX_LOOPS} — {len(pending_gen)} records still pending. Retrying...")
    sys.exit(1)


if __name__ == "__main__":
    fire.Fire(validate)
