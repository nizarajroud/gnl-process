#!/usr/bin/env python3
"""Restructure database to split columns between parent_configuration and podcast_download."""
import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

# Backup existing data
cursor.execute("SELECT * FROM podcast_download")
old_data = cursor.fetchall()

# Drop both tables
cursor.execute("DROP TABLE IF EXISTS podcast_download")
cursor.execute("DROP TABLE IF EXISTS parent_configuration")

# Create new parent_configuration table
cursor.execute('''
    CREATE TABLE parent_configuration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_file TEXT,
        source_path TEXT,
        source_type TEXT,
        podcast_theme TEXT,
        podcast_subtheme TEXT,
        split_configuration TEXT,
        generation_mode TEXT,
        combination_state INTEGER DEFAULT 0
    )
''')

# Create new podcast_download table
cursor.execute('''
    CREATE TABLE podcast_download (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_configuration_id INTEGER,
        source_id TEXT,
        podcast_name TEXT,
        generation_state INTEGER,
        download_state INTEGER,
        conversion_state INTEGER,
        date TEXT,
        FOREIGN KEY (parent_configuration_id) REFERENCES parent_configuration(id)
    )
''')

print("Restructured database with split columns")
print(f"Note: {len(old_data)} old records need to be re-imported")

conn.commit()
conn.close()
