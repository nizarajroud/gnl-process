#!/usr/bin/env python3
"""Generate podcast titles from database records with empty podcast_name."""

import sqlite3
import os
import re
import sys
from datetime import datetime

def generate_title(source_id: str, source_type: str, parent_file: str) -> str:
    base_title = os.path.splitext(source_id)[0]
    
    if source_type in ["GoogleDrive", "LocalStorage"]:
        if parent_file:
            return f"{base_title}-{parent_file}"
        return base_title
    else:  # WebAndYoutube
        url = source_id.split('?')[0].split('#')[0].rstrip('/')
        parts = [p for p in url.split('/') if p]
        if parts:
            last_part = parts[-1]
            title = re.sub(r'[^a-zA-Z0-9]', '-', last_part).strip('-')
            base_title = title[:50] if title else "webpage"
        else:
            base_title = "webpage"
        
        if parent_file:
            base_title = f"{base_title}-{parent_file}"
        
        now = datetime.now()
        return f"{now.day:02d}-{now.month:02d}-{base_title}"

if __name__ == "__main__":
    import fire
    
    def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
        if not os.path.exists(db_path):
            print(f"Error: Database not found at {db_path}")
            sys.exit(1)

        if parent_id:
            from resolve_parent import resolve_parent
            source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = """SELECT pd.id, pd.source_id, pc.source_type, pc.parent_file 
                   FROM podcast_download pd
                   JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
                   WHERE (pd.podcast_name IS NULL OR pd.podcast_name = '') AND pd.generation_state = 0"""
        params = []
        
        if parent_id:
            query += " AND pd.parent_configuration_id = ?"
            params.append(parent_id)
        else:
            if source_type:
                query += " AND pc.source_type = ?"
                params.append(source_type)
            if generation_mode:
                query += " AND pc.generation_mode = ?"
                params.append(generation_mode)
            if theme:
                query += " AND pc.podcast_theme = ?"
                params.append(theme)
            if subfolder:
                query += " AND pc.podcast_subtheme = ?"
                params.append(subfolder)
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        if not records:
            print("No records to process (all have generation_state = 1 or podcast_name set)")
            conn.close()
            sys.exit(0)
        
        for record_id, source_id, src_type, parent_file in records:
            cursor.execute("SELECT podcast_name FROM podcast_download WHERE id = ?", (record_id,))
            result = cursor.fetchone()
            if result and result[0]:
                continue
            title = generate_title(source_id, src_type, parent_file)
            cursor.execute("UPDATE podcast_download SET podcast_name = ? WHERE id = ?", (title, record_id))
            print(f"Updated record {record_id}: {title}")
        
        conn.commit()
        conn.close()

    fire.Fire(main)
