import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS podcast_download (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        source_type TEXT,
        source_path TEXT,
        parent_file TEXT,
        generation_mode TEXT,
        podcast_name TEXT,
        podcast_theme TEXT,
        podcast_subtheme TEXT,
        generation_state INTEGER,
        download_state INTEGER,
        conversion_state INTEGER,
        combination_state INTEGER,
        split_configuration INTEGER DEFAULT 0,
        date TEXT
    )
''')

conn.commit()
conn.close()

print("Database created successfully with podcast_download table")
