"""AWS Solutions to NotebookLM automation script using Playwright.

Usage:
python nllm-aws-asl-add-generate-gnl_v2_playwright.py <source_type> <generation_mode> <theme> <subfolder> [user_data_dir] [--headless]

Content types: LocalStorage
"""

import fire
import os
import time
import sys
import sqlite3
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

def main(source_type: str, generation_mode: str, theme: str, subfolder: str, user_data_dir: str = None, headless: bool = False) -> None:
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, source_id, source_path, podcast_name 
        FROM podcast_download 
        WHERE source_type = ? 
        AND generation_mode = ? 
        AND podcast_theme = ? 
        AND podcast_subtheme = ? 
        AND generation_state = 0
    """, (source_type, generation_mode, theme, subfolder))
    
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        print("No records found matching the criteria")
        sys.exit(0)
    
    print(f"Found {len(records)} records to process")
    
    if user_data_dir is None:
        user_data_dir = os.getenv('USER_DATA_DIR')
        if user_data_dir is None:
            raise ValueError("USER_DATA_DIR must be provided either as parameter or in .env file")
    
    local_storage_path = os.getenv('GNL_PROCESSING_PATH', '')
    
    record_id, source_id, source_path, podcast_name = records[0]
    print(f"\nProcessing record {record_id}: {podcast_name}")
    print(f"Remaining records: {len(records) - 1}")
    
    full_path = source_path if source_path else f"{local_storage_path}/{source_id}"
    
    if not os.path.exists(full_path):
        print(f"Error: File not found at {full_path}")
        sys.exit(1)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("http://notebooklm.google.com/")
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            
            # Click "+ Create new" button
            page.click('text="+ Create new"')
            time.sleep(2)
            
            # Upload file using file chooser
            with page.expect_file_chooser() as fc_info:
                page.click('button:has-text("Upload files")')
            file_chooser = fc_info.value
            file_chooser.set_files(full_path)
            
            print(f"Uploaded file: {full_path}")
            time.sleep(30)
            
            # Generate audio overview
            page.click('text="Audio Overview"')
            time.sleep(5)
            
            # Navigate back to notebooks list
            page.click('svg[data-icon="fingerprint"]')
            time.sleep(2)
            
            # Edit title
            page.click('button[aria-label="More actions"]', timeout=5000)
            page.click('text="Edit title"')
            time.sleep(1)
            
            page.fill('input[type="text"]', podcast_name)
            page.click('button:has-text("Save")')
            time.sleep(2)
            
            browser.close()
            
        print(f"\n✓ Successfully processed record {record_id}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE podcast_download SET generation_state = 1 WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Failed to process record {record_id}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(main)
