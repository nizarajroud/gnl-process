import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM podcast_download')
podcast_count = cursor.rowcount
cursor.execute('DELETE FROM parent_configuration')
parent_count = cursor.rowcount
conn.commit()
print(f"Deleted {podcast_count} records from podcast_download table")
print(f"Deleted {parent_count} records from parent_configuration table")
conn.close()
