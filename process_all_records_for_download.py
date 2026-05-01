#!/usr/bin/env python3
"""Process all matching records for download by calling the main script repeatedly."""

import subprocess
import sys
import sqlite3
import os

def main(source_type: str, generation_mode: str, theme: str, subfolder: str):
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    script_path = os.path.join(os.path.dirname(__file__), 'nllm-aws-asl-download-rename-gnl_v2.py')
    
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
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM podcast_download pd
            JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
            WHERE pc.source_type = ? 
            AND pc.generation_mode = ? 
            AND pc.podcast_theme = ? 
            AND pc.podcast_subtheme = ? 
            AND pd.generation_state = 1
            AND pd.download_state = 0
        """, (source_type, generation_mode, theme, subfolder))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        if count == 0:
            print("\n✓ All records downloaded!")
            break
        
        print(f"\n{'='*60}")
        print(f"Records remaining: {count}")
        print(f"{'='*60}\n")
        
        result = subprocess.run([
            'python', script_path,
            source_type, generation_mode, theme, subfolder
        ])
        
        if result.returncode != 0:
            print(f"\n✗ Script failed. Stopping.")
            sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python process_all_records.py <source_type> <generation_mode> <theme> <subfolder>")
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
