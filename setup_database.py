import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS podcast_download (
        podcast_name TEXT,
        download_state TEXT
    )
''')

conn.commit()
conn.close()

print("Database created successfully with podcast_download table")
