import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if columns already exist
cursor.execute("PRAGMA table_info(podcast_download)")
columns = [column[1] for column in cursor.fetchall()]

if 'conversion_state' not in columns:
    cursor.execute('ALTER TABLE podcast_download ADD COLUMN conversion_state INTEGER DEFAULT 0')
    print("Added conversion_state column")
else:
    print("conversion_state column already exists")

if 'combination_state' not in columns:
    cursor.execute('ALTER TABLE podcast_download ADD COLUMN combination_state INTEGER DEFAULT 0')
    print("Added combination_state column")
else:
    print("combination_state column already exists")

conn.commit()
conn.close()

print("Database migration completed successfully")
