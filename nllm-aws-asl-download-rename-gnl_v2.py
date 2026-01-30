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
        SELECT id, podcast_name 
        FROM podcast_download 
        WHERE source_type = ? 
        AND generation_mode = ? 
        AND podcast_theme = ? 
        AND podcast_subfolder = ? 
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
        if headless_env == '1':
            headless = True
        else:
            fzf = FzfPrompt()
            options = ["Visible (you can see the browser)", "Headless (background, faster)"]
            choice = fzf.prompt(options, "--prompt='Select browser mode: '")
            headless = choice and "Headless" in choice[0]

    record_id, podcast_name = records[0]
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
                f'Click on the notebook named <{podcast_name}> in the list '
                'Scroll down to view the second half of the Studio section. '
                'Then locate the kebab menu (three vertical dots) on the right side of the first audio overview item in that section. '
                'Click only on the three dots icon, NOT on the audio overview card itself. '
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

            dest_dir = os.getenv('GNL_BACKLOG', '/home/nizar')
            dest_dir = os.path.join(dest_dir, theme, subfolder)
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
