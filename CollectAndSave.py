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
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clean records that haven't been generated yet
    cursor.execute("""
        DELETE FROM podcast_download 
        WHERE generation_state = 0
    """)
    deleted_count = cursor.rowcount
    conn.commit()
    if deleted_count > 0:
        print(f"Cleaned {deleted_count} ungenerated records from database")
    
    # Handle both single and bulk modes
    files = data.get('files', [])
    if generation_mode == 'single' and not files:
        files = [data]
    
    # Extract parent configuration data from first file
    split_configuration = data.get('splitConfiguration', '')
    parent_file = files[0].get('parentDir', '') if files else ''
    source_path = os.path.dirname(files[0].get('fullPath', '')) if files else ''
    source_type = files[0].get('sourceType', '') if files else ''
    podcast_theme = files[0].get('podcastTheme', '') if files else ''
    podcast_subtheme = files[0].get('podcastSubfolder', '') if files else ''
    
    # Insert into parent_configuration table
    cursor.execute('''
        INSERT INTO parent_configuration 
        (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, 
         split_configuration, generation_mode, combination_state)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    ''', (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, 
          split_configuration, generation_mode))
    
    parent_config_id = cursor.lastrowid
    
    # Insert files into podcast_download table
    for file in files:
        cursor.execute('''
            INSERT INTO podcast_download 
            (parent_configuration_id, source_id, podcast_name, generation_state, 
             download_state, conversion_state, date)
            VALUES (?, ?, '', 0, 0, 0, NULL)
        ''', (parent_config_id, file.get('fileName', '')))
    
    conn.commit()
    print(f"Inserted {len(files)} records into podcast_download and 1 parent configuration")
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
