#!/usr/bin/env python3
"""Generate podcast titles from database records with empty podcast_name."""

import sqlite3
import os
import re
import sys
from datetime import datetime

def generate_title(source_id: str, source_type: str, source_parent: str) -> str:
    base_title = os.path.splitext(source_id)[0]
    
    if source_type in ["GoogleDrive", "LocalStorage"]:
        if source_parent:
            return f"{base_title}-{source_parent}"
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
        
        if source_parent:
            base_title = f"{base_title}-{source_parent}"
        
        now = datetime.now()
        return f"{now.day:02d}-{now.month:02d}-{base_title}"

if __name__ == "__main__":
    source_type = sys.argv[1] if len(sys.argv) > 1 else None
    generation_mode = sys.argv[2].lower() if len(sys.argv) > 2 else None
    podcast_theme = sys.argv[3] if len(sys.argv) > 3 else None
    podcast_subfolder = sys.argv[4].lower() if len(sys.argv) > 4 else None
    
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = "SELECT id, source_id, source_type, source_parent FROM podcast_download WHERE (podcast_name IS NULL OR podcast_name = '') AND download_state = 0"
    params = []
    
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if generation_mode:
        query += " AND generation_mode = ?"
        params.append(generation_mode)
    if podcast_theme:
        query += " AND podcast_theme = ?"
        params.append(podcast_theme)
    if podcast_subfolder:
        query += " AND podcast_subfolder = ?"
        params.append(podcast_subfolder)
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    
    for record_id, source_id, source_type, source_parent in records:
        title = generate_title(source_id, source_type, source_parent)
        cursor.execute("UPDATE podcast_download SET podcast_name = ? WHERE id = ?", (title, record_id))
        print(f"Updated record {record_id}: {title}")
    
    conn.commit()
    conn.close()
