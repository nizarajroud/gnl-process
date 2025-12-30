"""AWS Solutions to NotebookLM automation script.

Usage:
python nllm-aws-asl-add-generate-gnl.py [user_data_dir] [--headless]
"""

import fire
import os
import time
import requests
import shutil
import glob
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
            'Scroll down to view the second half of the Studio section. '
            'Then locate the kebab menu (three vertical dots) on the right side of the first audio overview item in that section. '
            'Click only on the three dots icon, NOT on the audio overview card itself. '
            'Then select the Download option from the menu'
        ) 
        time.sleep(300)
    
    # Find and copy the file from playwright-artifacts folder
    playwright_folders = glob.glob("/tmp/playwright-artifacts*")
    if playwright_folders:
        # Get the most recent folder
        latest_folder = max(playwright_folders, key=os.path.getmtime)
        # Find files without extension in the folder
        all_files = [f for f in os.listdir(latest_folder) if os.path.isfile(os.path.join(latest_folder, f)) and '.' not in f]
        if all_files:
            source_file = os.path.join(latest_folder, all_files[0])
            dest_file = os.path.expanduser(f"~/Downloads/{GNL_NAME_VAR}.m4a")
            shutil.copy2(source_file, dest_file)
            print(f"File copied to: {dest_file}")
        else:
            print("No file without extension found in playwright-artifacts folder")
    else:
        print("No playwright-artifacts folder found in /tmp")
     
    input("Press Enter to close the browser...")


if __name__ == "__main__":
    fire.Fire(main)
