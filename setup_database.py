import sqlite3

conn = sqlite3.connect('gnl.db')
cursor = conn.cursor()

# Create parent_configuration table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS parent_configuration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_file TEXT,
        source_path TEXT,
        source_type TEXT,
        podcast_theme TEXT,
        podcast_subtheme TEXT,
        split_configuration TEXT,
        generation_mode TEXT,
        combination_state INTEGER DEFAULT 0,
        daily_quota_remaining INTEGER DEFAULT 20,
        quota_date TEXT
    )
''')

# Create podcast_download table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS podcast_download (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_configuration_id INTEGER,
        source_id TEXT,
        podcast_name TEXT,
        generation_state INTEGER,
        download_state INTEGER,
        conversion_state INTEGER,
        date TEXT,
        FOREIGN KEY (parent_configuration_id) REFERENCES parent_configuration(id)
    )
''')

# Create crawled_links table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS crawled_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url TEXT NOT NULL,
        link_url TEXT NOT NULL,
        link_title TEXT,
        domain TEXT,
        podcast_theme TEXT NOT NULL,
        podcast_subtheme TEXT,
        state TEXT DEFAULT 'pending',
        podcast_download_id INTEGER,
        crawl_date TEXT NOT NULL,
        injected_date TEXT,
        UNIQUE(link_url, podcast_theme, podcast_subtheme),
        FOREIGN KEY (podcast_download_id) REFERENCES podcast_download(id)
    )
''')

conn.commit()
conn.close()

print("Database created successfully with parent_configuration, podcast_download and crawled_links tables")
