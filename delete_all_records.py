import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('DELETE FROM podcast_download')
print(f"Deleted {cursor.rowcount} records from podcast_download")
cursor.execute('DELETE FROM parent_configuration')
print(f"Deleted {cursor.rowcount} records from parent_configuration")
cursor.execute('DELETE FROM crawl_item')
print(f"Deleted {cursor.rowcount} records from crawl_item")
cursor.execute('DELETE FROM crawl_source')
print(f"Deleted {cursor.rowcount} records from crawl_source")
cursor.execute("DELETE FROM sqlite_sequence")

conn.commit()
conn.close()
print("✓ Database cleaned")
