"""AWS Solutions to NotebookLM automation script - Download with DB integration.

Usage:
python nllm-aws-asl-download-rename-gnl_v2.py <source_type> <generation_mode> <theme> <subfolder> [user_data_dir] [--headless]
"""

import fire
import os
import time
import sys
import sqlite3
import shutil
import glob
from dotenv import load_dotenv
from pyfzf.pyfzf import FzfPrompt
from nova_act import NovaAct

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
        SELECT id, podcast_name, parent_file 
        FROM podcast_download 
        WHERE source_type = ? 
        AND generation_mode = ? 
        AND podcast_theme = ? 
        AND podcast_subtheme = ? 
        AND generation_state = 1
        AND download_state = 0
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
    
    if headless is None:
        headless_env = os.getenv('HEADLESS')
        headless = headless_env == '1'

    record_id, podcast_name, parent_file = records[0]
    
    # Check if already downloaded
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT download_state FROM podcast_download WHERE id = ?", (record_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] == 1:
        print(f"Record {record_id} already downloaded, skipping")
        sys.exit(0)
    
    print(f"\nProcessing record {record_id}: {podcast_name}")
    print(f"Remaining records: {len(records) - 1}")
    
    try:
        with NovaAct(
            starting_page=os.getenv('NOTEBOOKLM_URL', 'http://notebooklm.google.com/'),
            user_data_dir=user_data_dir,
            headless=headless,
            clone_user_data_dir=False,
        ) as nova:
            time.sleep(3)
     
            nova.act(
                f'Click on the notebook named <{podcast_name}> in the list'
            )
            
            print("Waiting for audio generation to complete...")
            generation_complete = False
            max_attempts = 15
            attempt = 0
            
            while not generation_complete and attempt < max_attempts:
                attempt += 1
                print(f"Attempt {attempt}/{max_attempts}: Checking if generation is complete...")
                
                try:
                    # Refresh the page to get latest status
                    nova.page.reload()
                    time.sleep(3)
                    
                    result = nova.act_get(
                        'Look in the Studio section (the lower half of the page with generated items). '
                        'Check the audio overview item in that section. '
                        'If you see "Generating Audio Overview..." message, return "generating". '
                        'If you see a completed audio overview item with a kebab menu (More button) visible, return "complete". '
                        'If there is no audio overview item at all, return "missing". '
                        'Do NOT click anything, just observe and return only one word: "generating", "complete", or "missing".'
                    )
                    
                    print(f"Nova Act returned: {result.response}")
                    
                    if result.response and 'missing' in result.response.lower():
                        print("✗ No audio overview found - generation may not have started")
                        raise Exception("Audio overview generation not found")
                    elif result.response and 'complete' in result.response.lower():
                        generation_complete = True
                        print("✓ Audio generation complete!")
                        break
                    else:
                        print(f"Still generating... waiting 1 minute before next check")
                        time.sleep(60)  # Wait 1 minute
                        
                except Exception as e:
                    if 'ActExceededMaxStepsError' in str(type(e).__name__):
                        print(f"Max steps reached, waiting 1 minute before retry...")
                        time.sleep(60)  # Wait 1 minute
                    else:
                        raise
            
            if not generation_complete:
                print("⚠ Max attempts reached, proceeding anyway...")
            
            time.sleep(3)
            
            nova.act(
                'In the Studio section, locate the audio overview item. '
                'Find and click the kebab menu (three vertical dots or "More" button) on the right side of the audio overview item. '
                'Then select the Download option from the menu'
            ) 
            
            print("Waiting for download to complete...")
            download_timeout = 300
            start_time = time.time()
            
            while time.time() - start_time < download_timeout:
                playwright_folders = glob.glob("/tmp/playwright-artifacts*")
                if playwright_folders:
                    latest_folder = max(playwright_folders, key=os.path.getmtime)
                    files = [f for f in os.listdir(latest_folder) if os.path.isfile(os.path.join(latest_folder, f))]
                    if files:
                        time.sleep(5)
                        break
                time.sleep(2)
            else:
                print("Download timeout reached")
                sys.exit(1)

            # Use GNL_PROCESSING_PATH/Audio-Parts/podcast_subtheme/name
            gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
            dest_dir = os.path.join(gnl_processing_path, "Audio-Parts", subfolder, parent_file)
            os.makedirs(dest_dir, exist_ok=True)
            
            playwright_folders = glob.glob("/tmp/playwright-artifacts*")
            if playwright_folders:
                latest_folder = max(playwright_folders, key=os.path.getmtime)
                all_files = [f for f in os.listdir(latest_folder) if os.path.isfile(os.path.join(latest_folder, f))]
                if all_files:
                    source_file = os.path.join(latest_folder, all_files[0])
                    dest_file = os.path.join(dest_dir, f"{podcast_name}.m4a")
                    shutil.copyfile(source_file, dest_file)
                    print(f"File copied to: {dest_file}")
                else:
                    print("No files found in playwright-artifacts folder")
                    sys.exit(1)
            else:
                print("No playwright-artifacts folder found in /tmp")
                sys.exit(1)
        
        print(f"\n✓ Successfully processed record {record_id}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE podcast_download SET download_state = 1 WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Failed to process record {record_id}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(main)
