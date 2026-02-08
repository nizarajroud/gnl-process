"""AWS Solutions to NotebookLM automation script.

Usage:
python nllm-aws-asl-add-generate-gnl.py <sourceIdentifier> <title> <content_type> [user_data_dir] [--headless]

Content types: GoogleDrive, WebAndYoutube, youtube, copied-text
"""

import fire
import os
import time
import requests
import sqlite3
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pyfzf.pyfzf import FzfPrompt
from nova_act import NovaAct, SecurityOptions

load_dotenv()

def main(sourceIdentifier: str, title: str, content_type: str, user_data_dir: str = None, headless: bool = None) -> None:
    GNL_NAME_VAR = title
    
    # Validate content_type parameter
    valid_types = os.getenv('VALID_CONTENT_TYPES', 'GoogleDrive,WebAndYoutube,LocalStorage').split(',')
    if content_type not in valid_types:
        raise ValueError(f"content_type must be one of: {', '.join(valid_types)}")
    
    if user_data_dir is None:
        user_data_dir = os.getenv('USER_DATA_DIR')
        if user_data_dir is None:
            raise ValueError("USER_DATA_DIR must be provided either as parameter or in .env file")
    
    if headless is None:
        headless_env = os.getenv('HEADLESS')
        headless = headless_env == '1'

    local_storage_path = os.getenv('GNL_PROCESSING_PATH', '')
    
    with NovaAct(
        starting_page="http://notebooklm.google.com/",
        user_data_dir=user_data_dir,
        headless=headless,
        clone_user_data_dir=False,
        security_options=SecurityOptions(allowed_file_upload_paths=[f'{local_storage_path}/*']) if content_type == 'LocalStorage' else None,
    ) as nova:
        time.sleep(3)  # Wait for page to load
        
        # Handle different content types
        if content_type == 'WebAndYoutube':
            nova.act(
                'Click on "+ Create new" button on the right hight corner '
                'Click on "WebAndYoutubes" button '
                f'insert this link <{sourceIdentifier}> into the text box '
                'Click on "insert" button '
                'Wait until the source finishes loading'
            )
        elif content_type == 'GoogleDrive':
            nova.act(
                'Click on "+ Create new" button on the right hight corner '
                'Click on "Drive" button '
                'Click on "My Drive" tab '
                f'search for  <{sourceIdentifier}> and select it '
                'Click on "insert" button '
                'Wait until the source finishes loading'
            )
        elif content_type == 'LocalStorage':
            full_path = f"{local_storage_path}/{sourceIdentifier}"
            nova.act(
                'Click on "+ Create new" button on the right hight corner '
                'Click on the file upload button'
            )
            time.sleep(1)
            nova.act(
                f'Type this path into the file input: {full_path}'
            )
            time.sleep(2)
            nova.act(
                'Wait until the source finishes loading'
            )
        # time.sleep(50)
        nova.act(
            'Click on the "Audio Overview" button to generate an AI podcast based on the available sources '
            'Do not wait for the generation to complete, proceed to the next step immediately'
        )
        
      
        # nova.act(
        #     'Click on the "Audio Overview" button to generate an AI podcast based on the available sources '
        #     'The task is already accomplished - the Audio Overview generation has been successfully initiated and is in progress. No further action is needed at this time. '
        # ) 
        # Go back to main page
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
  
     
        


if __name__ == "__main__":
    fire.Fire(main)
