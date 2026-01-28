import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS podcast_download (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        source_type TEXT,
        source_path TEXT,
        source_parent TEXT,
        generation_mode TEXT,
        podcast_name TEXT,
        podcast_theme TEXT,
        podcast_subfolder TEXT,
        generation_state INTEGER,
        download_state INTEGER
    )
''')

conn.commit()
conn.close()

print("Database created successfully with podcast_download table")
