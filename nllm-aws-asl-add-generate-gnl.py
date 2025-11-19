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

def get_webpage_title(url: str) -> str:
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    if soup.title:
        title = soup.title.string.strip().replace(" ", "-")
    else:
        import re
        last_part = url.split('/')[-1].split('#')[0].split('?')[0]
        title = re.sub(r'[^a-zA-Z]', ' ', last_part).strip().replace(" ", "-")
    
    return title[:50] + "-etc" if len(title) > 50 else title

def main(url: str, user_data_dir: str = None, headless: bool = None) -> None:
    GNL_NAME_VAR = get_webpage_title(url)
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
        )
        time.sleep(3) 
        nova.act(
            f'Click on the name of the generated notebook on the left hight corner, select all and replace it with {GNL_NAME_VAR} '
            'Click on Enter to save the new name '
        )   
        time.sleep(10) 
        # nova.act(
        #     'Click on the "Audio Overview" button to generate an AI podcast based on the available sources '
        #     'The task is already accomplished - the Audio Overview generation has been successfully initiated and is in progress. No further action is needed at this time. '
        # ) 
        # time.sleep(10)         
        


if __name__ == "__main__":
    fire.Fire(main)
