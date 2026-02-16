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

def main(source_type: str, generation_mode: str, theme: str, subfolder: str, user_data_dir: str = None, headless: bool = None) -> None:
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pd.id, pd.source_id, pc.source_path, pd.podcast_name
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ? 
        AND pc.generation_mode = ? 
        AND pc.podcast_theme = ? 
        AND pc.podcast_subtheme = ? 
        AND pd.generation_state = 0
    """, (source_type, generation_mode, theme, subfolder))
    
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        print("No records found matching the criteria")
        sys.exit(0)
    
    print(f"Found {len(records)} records to process")
    
    # Validate content_type parameter
    valid_types = os.getenv('VALID_CONTENT_TYPES', 'GoogleDrive,WebAndYoutube,LocalStorage').split(',')
    if source_type not in valid_types:
        raise ValueError(f"source_type must be one of: {', '.join(valid_types)}")
    
    if user_data_dir is None:
        user_data_dir = os.getenv('USER_DATA_DIR')
        if user_data_dir is None:
            raise ValueError("USER_DATA_DIR must be provided either as parameter or in .env file")
    
    if headless is None:
        headless_env = os.getenv('HEADLESS')
        headless = headless_env == '1'

    local_storage_path = os.getenv('GNL_PROCESSING_PATH', '')
    
    record_id, source_id, source_path, podcast_name = records[0]
    
    # Check if already generated
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT generation_state FROM podcast_download WHERE id = ?", (record_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] == 1:
        print(f"Record {record_id} already generated, skipping")
        sys.exit(0)
    
    print(f"\nProcessing record {record_id}: {podcast_name}")
    print(f"Remaining records: {len(records) - 1}")
    
    sourceIdentifier = source_id
    GNL_NAME_VAR = podcast_name
    
    if source_type == 'LocalStorage':
        full_path = source_path if source_path else f"{local_storage_path}/{sourceIdentifier}"
        if not os.path.exists(full_path):
            print(f"Error: File not found at {full_path}")
            sys.exit(1)
    
    try:
        upload_success = False
        
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
            
            # Dismiss any overlays by pressing Escape
            page.keyboard.press('Escape')
            time.sleep(1)
            
            # Click "Create new notebook" button
            page.click('button[aria-label="Create new notebook"]')
            time.sleep(3)
            
            # Wait for notebook to be created and file input to exist (hidden is ok)
            page.wait_for_selector('input[type="file"]', state='attached', timeout=15000)
            
            # Upload file by setting file input directly
            try:
                file_input = page.locator('input[type="file"]').first
                file_input.set_input_files(full_path)
                time.sleep(5)
                
                # Verify upload
                print("Verifying upload...")
                upload_success = page.locator('text=/source/i').is_visible(timeout=10000)
                if upload_success:
                    print(f"✓ Upload verified: {full_path}")
                else:
                    print(f"⚠ Upload verification failed for {full_path}")
            except Exception as upload_error:
                print(f"⚠ Upload failed: {str(upload_error)}")
                upload_success = False
            
            if not upload_success:
                print("ERROR: Upload was not successful, raising exception")
                raise Exception("Source upload failed - cannot proceed with audio generation")
            
            print("✓ Upload successful, proceeding to audio generation")
            print("Waiting for source to fully load...")
            time.sleep(30)
            
            print("Additional stabilization wait...")
            time.sleep(10)
            
            print("Starting audio generation...")
            try:
                page.click('button[aria-label="Audio Overview"]')
                print("✓ Audio generation started")
            except Exception as audio_error:
                print(f"⚠ Audio generation failed: {str(audio_error)}")
                raise
            
            print("Waiting after audio generation...")
            time.sleep(5)
            
            print("Navigating back to notebooks list...")
            page.click('a[href="/"]')
            time.sleep(2)
            
            print("Opening edit menu...")
            page.click('button[aria-label="More"]')
            page.click('text="Edit title"')
            time.sleep(1)
            
            print(f"Renaming to: {GNL_NAME_VAR}")
            page.fill('input[type="text"]', '')
            page.fill('input[type="text"]', GNL_NAME_VAR)
            page.click('button:has-text("Save")')
            
            print("Waiting after rename...")
            time.sleep(3)
            
            browser.close()
            
        print(f"\n✓ Successfully processed record {record_id}")
        
        # Mark record as processed with current date
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE podcast_download SET generation_state = 1, date = ? WHERE id = ?", (time.strftime("%Y-%m-%d"), record_id))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Failed to process record {record_id}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(main)
