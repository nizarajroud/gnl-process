"""AWS Solutions to NotebookLM automation script.

Usage:
python nllm-aws-asl-add-generate-gnl_v2.py <source_type> <generation_mode> <theme> <subfolder> [user_data_dir] [--headless]

Content types: GoogleDrive, WebAndYoutube, LocalStorage
"""

import fire
import os
import time
import sys
import sqlite3
from dotenv import load_dotenv
from pyfzf.pyfzf import FzfPrompt
from nova_act import NovaAct, SecurityOptions
from daily_quota import check_and_update_quota, decrement_quota

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

TEST_MODE = os.getenv('TEST_MODE', '0') == '1'  # Set TEST_MODE=1 in .env for simulation

def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, user_data_dir: str = None, headless: bool = None, parent_id: int = None) -> None:
    from resolve_parent import resolve_parent
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)
    # Normalize case-sensitive parameters
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    # Check database existence
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    # Check daily quota
    remaining_quota = check_and_update_quota(db_path)
    if remaining_quota <= 0:
        print(f"❌ Daily quota exhausted (0/{20}). Try again tomorrow.")
        sys.exit(1)
    print(f"📊 Daily quota: {remaining_quota}/20 remaining")
    
    # Connect and query database
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
        """ + ("AND pd.parent_configuration_id = ? " if parent_id else "") + """
        ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC
    """, (source_type, generation_mode, theme, subfolder) + ((parent_id,) if parent_id else ()))
    
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
    
    # Process only the first record
    if not records:
        print("No records found matching the criteria")
        sys.exit(0)
    
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
    
    # Clean stale SingletonLock to prevent "profile already in use" errors
    singleton_lock = os.path.join(user_data_dir, 'SingletonLock')
    try:
        os.unlink(singleton_lock)
        print("🔓 Removed stale SingletonLock")
    except OSError:
        pass

    try:
        if TEST_MODE:
            # Simulate success without launching browser
            print(f"🧪 [TEST MODE] Simulating upload + generation for record {record_id}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE podcast_download SET generation_state = 1, date = ? WHERE id = ?", (time.strftime("%Y-%m-%d"), record_id))
            conn.commit()
            conn.close()
            print(f"✓ [TEST MODE] Record {record_id} marked as complete")
            decrement_quota(db_path, 1)
            remaining = check_and_update_quota(db_path)
            print(f"📊 Daily quota updated: {remaining}/20 remaining")
            sys.exit(0)

        # For LocalStorage, allow file uploads from the specific file's directory
        security_opts = None
        
        if source_type == 'LocalStorage':
            full_path = f"{source_path}/{sourceIdentifier}"
            file_dir = os.path.dirname(full_path)
            security_opts = SecurityOptions(allowed_file_upload_paths=[f'{file_dir}/*'])
        
        print(f"DEBUG: headless={headless}, type={type(headless)}", flush=True)
        with NovaAct(
            starting_page="http://notebooklm.google.com/",
            user_data_dir=user_data_dir,
            headless=headless,
            clone_user_data_dir=False,
            security_options=security_opts,
        ) as nova:
            time.sleep(int(os.getenv("NAV_WAIT_SECONDS", "3")))
            
            if source_type == 'WebAndYoutube':
                nova.act(
                    'Click on "+ Create new" button on the right hight corner '
                    'Click on "WebAndYoutubes" button '
                    f'insert this link <{sourceIdentifier}> into the text box '
                    'Click on "insert" button '
                    'Wait until the source finishes loading'
                )
            elif source_type == 'GoogleDrive':
                nova.act(
                    'Click on "+ Create new" button on the right hight corner '
                    'Click on "Drive" button '
                    'Click on "My Drive" tab '
                    f'search for  <{sourceIdentifier}> and select it '
                    'Click on "insert" button '
                    'Wait until the source finishes loading'
                )
            elif source_type == 'LocalStorage':
                full_path = f"{source_path}/{sourceIdentifier}"
                nova.act(
                    f'Click on "+ Create new" button '
                    f'Use agentType to provide the file path {full_path} to the hidden file input element'
                )
                time.sleep(int(os.getenv('UPLOAD_WAIT_SECONDS', '5')))
            
            print("✓ Upload successful")
            
            # Rename notebook immediately after upload
            print("Navigating back to notebooks list...")
            nova.act(
                'Click on the black fingerprint icon in the top left corner'
            )
            
            print("Opening edit menu...")
            nova.act(
                'Click on the kebab menu (three dots) of the first notebook in the list '
                'Click on "Edit title" option'
            )
            
            print(f"Renaming to: {GNL_NAME_VAR}")
            nova.act(
                f'Clear the title field completely '
                f'Type exactly: {GNL_NAME_VAR} '
                'Click on "Save" button'
            )
            time.sleep(int(os.getenv("NAV_WAIT_SECONDS", "3")))
            
            # Navigate into the renamed notebook
            nova.act(
                f'Click on the notebook titled "{GNL_NAME_VAR}" in the list'
            )
            time.sleep(int(os.getenv("NAV_WAIT_SECONDS", "3")))
            
            # --- AUDIO GENERATION (common for both cases) ---
            print("Starting audio generation...")
            try:
                prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')
                prompt_file = os.path.join(prompts_dir, f"{subfolder}.txt")
                if not os.path.exists(prompt_file):
                    prompt_file = os.path.join(prompts_dir, "default.txt")
                with open(prompt_file, 'r') as f:
                    audio_prompt = f.read().strip().replace('"', '\\"')

                nova.act(
                    'In the Notebook guide section on the right side, find the Audio Overview card. '
                    'Click on the arrow button (">") located at the top right corner of the Audio Overview card. '
                    'Wait for the "Customize Audio Overview" modal window to appear. '
                    'Once the modal is open, find the text input field labeled '
                    '"What should the AI hosts focus on in this episode?" '
                    f'and type the following prompt: "{audio_prompt}". '
                    'Then click the "Generate" button at the bottom right of the modal. '
                    'Wait for and verify that a message appears confirming that generation has started '
                    '(like "Generating Audio Overview..." or "Come back in a few minutes"). '
                    'Confirm you can see this status message before considering the task complete.'
                )
                print("✓ Audio generation started")
            except Exception as audio_error:
                print(f"⚠ Audio generation failed: {str(audio_error)}")
                raise
            
            # Mark generation_state immediately after successful audio generation
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE podcast_download SET generation_state = 1, date = ? WHERE id = ?", (time.strftime("%Y-%m-%d"), record_id))
            conn.commit()
            conn.close()
            print(f"✓ generation_state updated to 1 for record {record_id}")

            print("Waiting after audio generation...")
            time.sleep(int(os.getenv("POST_GEN_WAIT_SECONDS", "5")))
            
        print(f"\n✓ Successfully processed record {record_id}")
        
        # Decrement daily quota
        decrement_quota(db_path, 1)
        remaining = check_and_update_quota(db_path)
        print(f"📊 Daily quota updated: {remaining}/20 remaining")
        
    except Exception as e:
        print(f"\n✗ Failed to process record {record_id}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(main)
