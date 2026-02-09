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

load_dotenv()

def main(source_type: str, generation_mode: str, theme: str, subfolder: str, user_data_dir: str = None, headless: bool = None) -> None:
    # Normalize case-sensitive parameters
    generation_mode = generation_mode.lower()
    subfolder = subfolder.lower()
    
    # Check database existence
    db_path = os.path.join(os.path.dirname(__file__), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    # Connect and query database
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
    
    try:
        # For LocalStorage, allow file uploads from the specific file's directory
        security_opts = None
        upload_success = False
        
        if source_type == 'LocalStorage':
            full_path = source_path if source_path else f"{local_storage_path}/{sourceIdentifier}"
            file_dir = os.path.dirname(full_path)
            security_opts = SecurityOptions(allowed_file_upload_paths=[f'{file_dir}/*'])
        
        with NovaAct(
            starting_page="http://notebooklm.google.com/",
            user_data_dir=user_data_dir,
            headless=headless,
            clone_user_data_dir=False,
            security_options=security_opts,
        ) as nova:
            time.sleep(3)
            
            # Handle different content types
            if source_type == 'WebAndYoutube':
                nova.act(
                    'Click on "+ Create new" button on the right hight corner '
                    'Click on "WebAndYoutubes" button '
                    f'insert this link <{sourceIdentifier}> into the text box '
                    'Click on "insert" button '
                    'Wait until the source finishes loading'
                )
                upload_success = True
            elif source_type == 'GoogleDrive':
                nova.act(
                    'Click on "+ Create new" button on the right hight corner '
                    'Click on "Drive" button '
                    'Click on "My Drive" tab '
                    f'search for  <{sourceIdentifier}> and select it '
                    'Click on "insert" button '
                    'Wait until the source finishes loading'
                )
                upload_success = True
            elif source_type == 'LocalStorage':
                full_path = source_path if source_path else f"{local_storage_path}/{sourceIdentifier}"
                try:
                    nova.act(
                        f'Click on "+ Create new" button '
                        f'Use agentType to provide the file path {full_path} to the hidden file input element'
                    )
                    time.sleep(5)
                    
                    # Verify upload by checking for source in the page
                    print("Verifying upload...")
                    result = nova.act('Check if a source file is visible in the notebook. Return "yes" if source is loaded, "no" if not.')
                    print(f"Verification result: {result}")
                    
                    if result and 'yes' in str(result).lower():
                        upload_success = True
                        print(f"✓ Upload verified: {full_path}")
                    else:
                        print(f"⚠ Upload verification failed for {full_path}")
                        print(f"Result was: {result}")
                        upload_success = False
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
                nova.act(
                    'In the Notebook guide section on the right side, find the Audio Overview card. '
                    'Click directly on the "Audio Overview" button inside that card. '
                    'Wait for and verify that a message appears containing both: '
                    '1) Text indicating generation is in progress (like "Generating Audio Overview...") '
                    '2) Text telling the user to wait (like "Come back in a few minutes") '
                    'Confirm you can see this complete status message before considering the task complete.'
                )
                print("✓ Audio generation started")
            except Exception as audio_error:
                print(f"⚠ Audio generation failed: {str(audio_error)}")
                raise
            
            print("Waiting after audio generation...")
            time.sleep(5)
            
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
            
            print("Waiting after rename...")
            time.sleep(3)
            
        print(f"\n✓ Successfully processed record {record_id}")
        
        # Mark record as processed
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
