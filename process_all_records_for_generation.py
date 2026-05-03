#!/usr/bin/env python3
"""Process all matching records by calling the main script repeatedly."""

import subprocess
import sys
import sqlite3
import os
import fire
from resolve_parent import resolve_parent


def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nllm-aws-asl-add-generate-gnl_v2.py')

    STOP_FILE = '/tmp/gnl-stop'
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

    while True:
        if os.path.exists(STOP_FILE):
            print("⛔ Stop signal received. Exiting.")
            os.remove(STOP_FILE)
            sys.exit(0)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        if parent_id:
            cursor.execute("SELECT COUNT(*) FROM podcast_download WHERE parent_configuration_id = ? AND generation_state = 0", (parent_id,))
        else:
            cursor.execute("""SELECT COUNT(*) FROM podcast_download pd JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
                WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ? AND pd.generation_state = 0""",
                (source_type, generation_mode, theme, subfolder))
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            print("\n✓ All records processed!")
            break

        print(f"\n{'='*60}\nRecords remaining: {count}\n{'='*60}\n")
        result = subprocess.run(['python', script_path, source_type, generation_mode, theme, subfolder] + (['--parent_id', str(parent_id)] if parent_id else []))
        if result.returncode != 0:
            print(f"\n⚠ Script failed on one record. Continuing with next...")
            continue


if __name__ == "__main__":
    fire.Fire(main)
