#!/usr/bin/env python3
"""Process all matching records by calling the main script repeatedly."""

import subprocess
import sys
import sqlite3
import os

def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
    if not parent_id and not all([source_type, generation_mode, theme, subfolder]):
        print("Usage: python process_all_records.py <source_type> <generation_mode> <theme> <subfolder>")
        print("   or: python process_all_records.py --parent_id=<id>")
        sys.exit(1)

    if generation_mode:
        generation_mode = generation_mode.lower()
    if subfolder:
        subfolder = subfolder.lower()

    # If parent_id provided, resolve params from DB
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    if parent_id and not all([source_type, generation_mode, theme, subfolder]):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source_type, generation_mode, podcast_theme, podcast_subtheme FROM parent_configuration WHERE id = ?", (parent_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            print(f"Error: Parent ID {parent_id} not found")
            sys.exit(1)
        source_type, generation_mode, theme, subfolder = row
    
    script_path = os.path.join(os.path.dirname(__file__), 'nllm-aws-asl-add-generate-gnl_v2.py')
    # script_path = os.path.join(os.path.dirname(__file__), 'nllm-aws-asl-add-generate-gnl_v2_playwright.py')
    
    STOP_FILE = '/tmp/gnl-stop'
    # Clear stop signal at start
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
            cursor.execute("""
                SELECT COUNT(*) 
                FROM podcast_download pd
                WHERE pd.parent_configuration_id = ?
                AND pd.generation_state = 0
            """, (parent_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM podcast_download pd
                JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
                WHERE pc.source_type = ? 
                AND pc.generation_mode = ? 
                AND pc.podcast_theme = ? 
                AND pc.podcast_subtheme = ? 
                AND pd.generation_state = 0
            """, (source_type, generation_mode, theme, subfolder))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        if count == 0:
            print("\n✓ All records processed!")
            break
        
        print(f"\n{'='*60}")
        print(f"Records remaining: {count}")
        print(f"{'='*60}\n")
        
        cmd = ['python', script_path, source_type, generation_mode, theme, subfolder]
        result = subprocess.run(cmd)
        
        if result.returncode != 0:
            print(f"\n⚠ Script failed on one record. Continuing with next...")
            continue

if __name__ == "__main__":
    import fire
    fire.Fire(main)
