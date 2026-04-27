#!/usr/bin/env python3
"""Add daily_quota_remaining and quota_date fields to parent_configuration table."""
import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE parent_configuration ADD COLUMN daily_quota_remaining INTEGER DEFAULT 20')
    print("Added daily_quota_remaining column")
except sqlite3.OperationalError:
    print("daily_quota_remaining column already exists")

try:
    cursor.execute('ALTER TABLE parent_configuration ADD COLUMN quota_date TEXT')
    print("Added quota_date column")
except sqlite3.OperationalError:
    print("quota_date column already exists")

conn.commit()
conn.close()
