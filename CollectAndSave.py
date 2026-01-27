#!/usr/bin/env python3
import json
import sqlite3
import sys
import os

def collect_and_save(json_input):
    data = json.loads(json_input)
    generation_mode = data.get('mode', '')
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'gnl.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Handle both single and bulk modes
    files = data.get('files', [])
    if generation_mode == 'single' and not files:
        files = [data]
    
    for file in files:
        cursor.execute('''
            INSERT INTO podcast_download 
            (source_id, source_type, source_path, source_parent, generation_mode, 
             podcast_name, podcast_theme, podcast_subfolder, download_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            file.get('fileName', ''),
            file.get('sourceType', ''),
            file.get('fullPath', ''),
            file.get('parentDir', ''),
            generation_mode,
            '',
            file.get('podcastTheme', ''),
            file.get('podcastSubfolder', ''),
            1 if file.get('downloadState', False) else 0
        ))
    
    conn.commit()
    print(f"Inserted {cursor.rowcount} records")
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if os.path.isfile(sys.argv[1]):
            with open(sys.argv[1], 'r') as f:
                collect_and_save(f.read())
        else:
            collect_and_save(' '.join(sys.argv[1:]))
    else:
        json_input = sys.stdin.read()
        collect_and_save(json_input)
