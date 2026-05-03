#!/usr/bin/env python3
import json
import sqlite3
import sys
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

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
    podcast_subtheme = files[0].get('podcastSubfolder', '').lower() if files else ''
    
    # Clean existing audio parts folder for this parent
    import shutil
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    if audio_parts_folder and podcast_subtheme and parent_file:
        audio_dir = os.path.join(audio_parts_folder, podcast_subtheme, parent_file)
        if os.path.exists(audio_dir):
            shutil.rmtree(audio_dir)
            print(f"Cleaned audio parts: {audio_dir}", file=sys.stderr)
    
    # Check if parent with same parent_file + podcast_subtheme already exists
    cursor.execute('''
        SELECT id FROM parent_configuration 
        WHERE parent_file = ? AND podcast_subtheme = ?
    ''', (parent_file, podcast_subtheme))
    existing = cursor.fetchone()
    
    if existing:
        parent_config_id = existing[0]
        cursor.execute('DELETE FROM podcast_download WHERE parent_configuration_id = ?', (parent_config_id,))
        cursor.execute('''
            UPDATE parent_configuration 
            SET source_path=?, source_type=?, podcast_theme=?, split_configuration=?, 
                generation_mode=?, combination_state=0
            WHERE id=?
        ''', (source_path, source_type, podcast_theme, split_configuration, generation_mode, parent_config_id))
        print(f"Replaced existing parent {parent_config_id} ({parent_file}/{podcast_subtheme})", file=sys.stderr)
    else:
        cursor.execute('''
            INSERT INTO parent_configuration 
            (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, 
             split_configuration, generation_mode, combination_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, 
              split_configuration, generation_mode))
        parent_config_id = cursor.lastrowid
    
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
    print(f"Inserted {len(files)} records into podcast_download and 1 parent configuration", file=sys.stderr)
    # Output parent_id as JSON for n8n to capture
    print(json.dumps({"parent_id": parent_config_id}))
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
