"""AWS Solutions to NotebookLM automation script.

Usage:
python nllm-aws-asl-add-generate-gnl.py [user_data_dir] [--headless]
"""

import fire
import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pyfzf.pyfzf import FzfPrompt
from nova_act import NovaAct

load_dotenv()

def main(url: str, title: str, user_data_dir: str = None, headless: bool = None) -> None:
    GNL_NAME_VAR = title
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

    with NovaAct(
        starting_page="http://notebooklm.google.com/",
        user_data_dir=user_data_dir,
        headless=headless,
        clone_user_data_dir=False,
    ) as nova:
        time.sleep(3)  # Wait for page to load
        
        nova.act(
            'Click on "+ Create new" button on the right hight corner '
            'Click on "Website" button '
            f'insert this link <{url}> into the text box '
            'Click on "insert" button '
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
