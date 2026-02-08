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
        if headless_env == '1':
            headless = True
        else:
            fzf = FzfPrompt()
            options = ["Visible (you can see the browser)", "Headless (background, faster)"]
            choice = fzf.prompt(options, "--prompt='Select browser mode: '")
            headless = choice and "Headless" in choice[0]

    local_storage_path = os.getenv('GNL_PROCESSING_PATH', '')
    
    # Process only the first record
    if not records:
        print("No records found matching the criteria")
        sys.exit(0)
    
    record_id, source_id, source_path, podcast_name = records[0]
    print(f"\nProcessing record {record_id}: {podcast_name}")
    print(f"Remaining records: {len(records) - 1}")
    
    sourceIdentifier = source_id
    GNL_NAME_VAR = podcast_name
    
    try:
        # For LocalStorage, allow file uploads from the specific file's directory
        security_opts = None
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
                full_path = source_path if source_path else f"{local_storage_path}/{sourceIdentifier}"
                nova.act(
                    f'Click on "+ Create new" button '
                    f'Use agentType to provide the file path {full_path} to the hidden file input element'
                )
                time.sleep(5)
            
            time.sleep(30)
            
            # Wait for page to fully stabilize before attempting audio generation
            time.sleep(10)
            
            nova.act(
                'In the Notebook guide section on the right side, find the Audio Overview card '
                'Click directly on the "Audio Overview" button inside that card '
                'Wait until you see "Generating..." text or a progress indicator appear '
                'The task is complete once the generation process has visibly started'
            )
            time.sleep(5)
            
            nova.act(
                'Click on the black fingerprint icon in the top left corner'
            )
            nova.act(
                'Click on the kebab menu (three dots) of the first notebook in the list '
                'Click on "Edit title" option'
            )        
            nova.act(
                f'Replace the notebook title with {GNL_NAME_VAR} '
                'Click on "Save" button'
            )               
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
