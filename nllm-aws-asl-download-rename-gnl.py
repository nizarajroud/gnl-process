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
    try:
        response = requests.get(url, timeout=2, stream=True)
        # Read only first 8KB to find title quickly
        content = response.raw.read(8192)
        response.close()
        
        soup = BeautifulSoup(content, 'html.parser')
        if soup.title and soup.title.string:
            title = soup.title.string.strip().replace(" ", "-")
            return title[:50] + "-etc" if len(title) > 50 else title
    except:
        pass
    
    # Fast fallback - just use URL
    import re
    last_part = url.split('/')[-1].split('#')[0].split('?')[0]
    title = re.sub(r'[^a-zA-Z0-9]', '-', last_part).strip('-')
    return title[:50] + "-etc" if len(title) > 50 else title or "webpage"

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
            'Click on  the first notebook in the list '
            'Click on the kebab menu (three dots) next to the generated "Audio Overview" '
            'Click on "Download" option'
        )
      

     
        input("Press Enter to close the browser...")


if __name__ == "__main__":
    fire.Fire(main)
