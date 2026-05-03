#!/usr/bin/env python3
"""Process all matching records by calling the main script repeatedly."""

import subprocess
import sys
import sqlite3
import os
import fire
from resolve_parent import resolve_parent

MAX_RETRIES = 5

def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nllm-aws-asl-add-generate-gnl_v2.py')
    retry_counts = {}

    while True:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = """SELECT pd.id FROM podcast_download pd
            JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
            WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
            AND pd.generation_state = 0"""
        params = [source_type, generation_mode, theme, subfolder]
        if parent_id:
            query += " AND pd.parent_configuration_id = ?"
            params.append(parent_id)
        query += " ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC LIMIT 1"
        
        cursor.execute(query, params)
        row = cursor.fetchone()

        if not row:
            print("\n✓ All records processed!")
            conn.close()
            break

        record_id = row[0]
        retries = retry_counts.get(record_id, 0)
        if retries >= MAX_RETRIES:
            cursor.execute("UPDATE podcast_download SET generation_state = 2 WHERE id = ?", (record_id,))
            conn.commit()
            print(f"\n❌ Record {record_id} failed after {MAX_RETRIES} attempts. Marked as failed (state=2).")
            conn.close()
            continue

        remaining = conn.execute("SELECT COUNT(*) FROM podcast_download pd JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ? AND pd.generation_state = 0" + (" AND pd.parent_configuration_id = ?" if parent_id else ""), params).fetchone()[0]
        conn.close()

        print(f"\n{'='*60}\nRecords remaining: {remaining} | Record {record_id} (attempt {retries + 1}/{MAX_RETRIES})\n{'='*60}\n")

        cmd = ['python', script_path, source_type, generation_mode, theme, subfolder]
        if parent_id:
            cmd += ['--parent_id', str(parent_id)]
        result = subprocess.run(cmd)

        if result.returncode != 0:
            retry_counts[record_id] = retries + 1
            print(f"\n⚠ Record {record_id} failed (attempt {retries + 1}/{MAX_RETRIES}).")
            continue


if __name__ == "__main__":
    fire.Fire(main)
