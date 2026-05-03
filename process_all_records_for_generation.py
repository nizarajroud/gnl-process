#!/usr/bin/env python3
"""Process all matching records by calling the main script repeatedly."""

import subprocess
import sys
import sqlite3
import os

MAX_RETRIES = 5

def main(source_type: str, generation_mode: str, theme: str, subfolder: str):
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nllm-aws-asl-add-generate-gnl_v2.py')
    retry_counts = {}  # track retries per record id

    while True:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pd.id FROM podcast_download pd
            JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
            WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
            AND pd.generation_state = 0
            ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC
            LIMIT 1
        """, (source_type, generation_mode, theme, subfolder))
        row = cursor.fetchone()
        
        if not row:
            print("\n✓ All records processed!")
            conn.close()
            break

        record_id = row[0]
        
        # Check retry count
        retries = retry_counts.get(record_id, 0)
        if retries >= MAX_RETRIES:
            cursor.execute("UPDATE podcast_download SET generation_state = 2 WHERE id = ?", (record_id,))
            conn.commit()
            print(f"\n❌ Record {record_id} failed after {MAX_RETRIES} attempts. Marked as failed (state=2). Skipping.")
            conn.close()
            continue

        count_cursor = conn.execute("""
            SELECT COUNT(*) FROM podcast_download pd
            JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
            WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
            AND pd.generation_state = 0
        """, (source_type, generation_mode, theme, subfolder))
        remaining = count_cursor.fetchone()[0]
        conn.close()

        print(f"\n{'='*60}")
        print(f"Records remaining: {remaining} | Processing record {record_id} (attempt {retries + 1}/{MAX_RETRIES})")
        print(f"{'='*60}\n")
        
        result = subprocess.run(['python', script_path, source_type, generation_mode, theme, subfolder])
        
        if result.returncode != 0:
            retry_counts[record_id] = retries + 1
            print(f"\n⚠ Record {record_id} failed (attempt {retries + 1}/{MAX_RETRIES}). Retrying...")
            continue


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python process_all_records_for_generation.py <source_type> <generation_mode> <theme> <subfolder>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
