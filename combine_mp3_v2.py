#!/usr/bin/env python3
"""Concatenate multiple MP3 files with database integration."""

import sys
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import subprocess

load_dotenv()

def main(source_type: str, generation_mode: str, theme: str, subfolder: str, output_file: str):
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, podcast_name 
        FROM podcast_download 
        WHERE source_type = ? 
        AND generation_mode = ? 
        AND podcast_theme = ? 
        AND podcast_subfolder = ? 
        AND conversion_state = 1
        AND combination_state = 0
    """, (source_type, generation_mode, theme, subfolder))
    
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        print("No records found matching the criteria")
        sys.exit(0)
    
    print(f"Found {len(records)} records to combine")
    
    base_path = os.getenv('GNL_BACKLOG')
    if not base_path:
        print("Error: GNL_BACKLOG environment variable not set")
        sys.exit(1)
    
    full_path = Path(base_path) / theme / subfolder
    
    try:
        # Create list of files to combine
        mp3_files = []
        for record_id, podcast_name in records:
            mp3_file = full_path / f"{podcast_name}.mp3"
            if mp3_file.exists():
                mp3_files.append(mp3_file)
            else:
                print(f"Warning: File not found: {mp3_file}")
        
        if not mp3_files:
            print("No MP3 files found to combine")
            sys.exit(1)
        
        mp3_files.sort()
        
        # Ensure output file has .mp3 extension
        if not output_file.endswith('.mp3'):
            output_file = f"{output_file}.mp3"
        
        output_path = full_path / output_file
        
        # Use ffmpeg to concatenate
        list_file = "concat_list.txt"
        with open(list_file, "w") as f:
            for file in mp3_files:
                print(f"Adding: {file.name}")
                f.write(f"file '{file.absolute()}'\n")
        
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", str(output_path)], check=True)
        os.remove(list_file)
        print(f"Combined {len(mp3_files)} files into {output_path}")
        
        # Move input files to zz folder
        zz_folder = full_path / "zz"
        zz_folder.mkdir(exist_ok=True)
        for file in mp3_files:
            file.rename(zz_folder / file.name)
        print(f"Moved {len(mp3_files)} files to {zz_folder}")
        
        # Mark all records as combined
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for record_id, _ in records:
            cursor.execute("UPDATE podcast_download SET combination_state = 1 WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
        print(f"\n✓ Successfully combined {len(records)} records")
        
    except Exception as e:
        print(f"\n✗ Failed to combine files: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python combine_mp3_v2.py <source_type> <generation_mode> <theme> <subfolder> <output.mp3>")
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
