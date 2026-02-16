#!/usr/bin/env python3
"""Create parent_configuration table and restructure database."""
import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

# Create parent_configuration table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS parent_configuration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        podcast_configuration_id INTEGER,
        parent_file TEXT,
        source_path TEXT,
        source_type TEXT,
        podcast_theme TEXT,
        podcast_subtheme TEXT,
        split_configuration TEXT,
        generation_mode TEXT,
        combination_state INTEGER DEFAULT 0,
        FOREIGN KEY (podcast_configuration_id) REFERENCES podcast_download(id)
    )
''')

print("Created parent_configuration table")

conn.commit()
conn.close()
