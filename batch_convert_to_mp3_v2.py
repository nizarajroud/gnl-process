#!/usr/bin/env python3
"""Convert M4A to MP3 with database integration."""

import subprocess
import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import fire

load_dotenv()

def main(source_type: str, generation_mode: str, theme: str, subfolder: str):
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pd.id, pd.podcast_name, pc.parent_file
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ? 
        AND pc.generation_mode = ? 
        AND pc.podcast_theme = ? 
        AND pc.podcast_subtheme = ? 
        AND pd.download_state = 1
        AND pd.conversion_state = 0
    """, (source_type, generation_mode, theme, subfolder))
    
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        print("No records found matching the criteria")
        sys.exit(0)
    
    print(f"Found {len(records)} records to process")
    
    record_id, podcast_name, parent_file = records[0]
    print(f"\nProcessing record {record_id}: {podcast_name}")
    print(f"Remaining records: {len(records) - 1}")
    
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    try:
        # Use GNL_PROCESSING_PATH/Audio-Parts/subfolder/parent_file
        audio_parts_dir = Path(gnl_processing_path) / "Audio-Parts" / subfolder / parent_file
        input_file = audio_parts_dir / f"{podcast_name}.m4a"
        output_file = audio_parts_dir / f"{podcast_name}.mp3"
        
        # Check if already converted
        if output_file.exists() and not input_file.exists():
            print(f"Already converted: {output_file}")
        elif not input_file.exists():
            print(f"Error: File not found: {input_file}")
            sys.exit(1)
        else:
            subprocess.run(['ffmpeg', '-i', str(input_file), str(output_file)], check=True)
            os.remove(input_file)
            print(f"Converted and removed: {input_file} -> {output_file}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE podcast_download SET conversion_state = 1 WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
        print(f"\n✓ Successfully processed record {record_id}")
        
    except Exception as e:
        print(f"\n✗ Failed to process record {record_id}: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    fire.Fire(main)
