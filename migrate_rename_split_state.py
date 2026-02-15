#!/usr/bin/env python3
"""Rename split_state to split_configuration in existing database."""
import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

# SQLite doesn't support RENAME COLUMN directly in older versions
# So we need to check if split_state exists and create split_configuration
try:
    # Check if split_state exists
    cursor.execute("PRAGMA table_info(podcast_download)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'split_state' in columns and 'split_configuration' not in columns:
        # Copy data from split_state to new column split_configuration
        cursor.execute('ALTER TABLE podcast_download ADD COLUMN split_configuration INTEGER DEFAULT 0')
        cursor.execute('UPDATE podcast_download SET split_configuration = split_state')
        print("Created split_configuration column and copied data from split_state")
        print("Note: split_state column still exists. You can manually drop it if needed.")
    elif 'split_configuration' in columns:
        print("split_configuration column already exists")
    else:
        cursor.execute('ALTER TABLE podcast_download ADD COLUMN split_configuration INTEGER DEFAULT 0')
        print("Created split_configuration column")
    
    conn.commit()
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
