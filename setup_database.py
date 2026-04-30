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
        file_url TEXT,
        FOREIGN KEY (parent_configuration_id) REFERENCES parent_configuration(id)
    )
''')

# Create crawl_source table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS crawl_source (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theme TEXT,
        subtheme TEXT,
        crawl_source_url TEXT NOT NULL,
        UNIQUE(crawl_source_url, theme, subtheme)
    )
''')

# Create crawl_item table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS crawl_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crawl_source_id INTEGER NOT NULL,
        url_hash TEXT NOT NULL,
        crawl_item_url TEXT NOT NULL,
        post_date TEXT,
        headline TEXT,
        processed_state TEXT DEFAULT 'False',
        aggregation_state TEXT DEFAULT 'False',
        FOREIGN KEY (crawl_source_id) REFERENCES crawl_source(id),
        UNIQUE(url_hash, crawl_source_id)
    )
''')

conn.commit()
conn.close()

print("Database created successfully with parent_configuration, podcast_download, crawl_source and crawl_item tables")
