import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM podcast_download')
conn.commit()
print(f"Deleted {cursor.rowcount} records from podcast_download table")
conn.close()
