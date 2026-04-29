#!/usr/bin/env python3
"""Check and update daily quota for podcast generation."""
import sqlite3
import os
from datetime import datetime

def check_and_update_quota(db_path='gnl.db'):
    """Check if quota needs reset and return remaining quota."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get current quota info
    cursor.execute("""
        SELECT daily_quota_remaining, quota_date 
        FROM parent_configuration 
        ORDER BY id DESC LIMIT 1
    """)
    
    result = cursor.fetchone()
    
    if result is None:
        # No records yet
        conn.close()
        return 20
    
    current_quota, quota_date = result
    
    # Reset quota if it's a new day
    if quota_date != today:
        cursor.execute("""
            UPDATE parent_configuration 
            SET daily_quota_remaining = 20, quota_date = ?
        """, (today,))
        conn.commit()
        conn.close()
        return 20
    
    conn.close()
    return current_quota if current_quota is not None else 20

def decrement_quota(db_path='gnl.db', count=1):
    """Decrement the daily quota by count."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        UPDATE parent_configuration 
        SET daily_quota_remaining = daily_quota_remaining - ?,
            quota_date = ?
        WHERE id IN (SELECT id FROM parent_configuration ORDER BY id DESC LIMIT 1)
    """, (count, today))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    remaining = check_and_update_quota()
    print(f"Daily quota remaining: {remaining}")
