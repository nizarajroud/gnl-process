#!/usr/bin/env python3
"""Add split_state and date fields to existing database."""

import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE podcast_download ADD COLUMN split_state INTEGER DEFAULT 0')
    print("Added split_state column")
except sqlite3.OperationalError:
    print("split_state column already exists")

try:
    cursor.execute('ALTER TABLE podcast_download ADD COLUMN date TEXT')
    print("Added date column")
except sqlite3.OperationalError:
    print("date column already exists")

conn.commit()
conn.close()

print("Migration completed successfully")
