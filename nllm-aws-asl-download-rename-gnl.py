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

def main(title: str, user_data_dir: str = None, suffix: str = None, subsuffix: str = None, headless: bool = None) -> None:
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
        starting_page=os.getenv('NOTEBOOKLM_URL', 'http://notebooklm.google.com/'),
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
        
        # Wait for download to complete by checking for playwright-artifacts folder
        print("Waiting for download to complete...")
        download_timeout = 300  # 5 minutes max
        start_time = time.time()
        
        while time.time() - start_time < download_timeout:
            playwright_folders = glob.glob("/tmp/playwright-artifacts*")
            if playwright_folders:
                latest_folder = max(playwright_folders, key=os.path.getmtime)
                files = [f for f in os.listdir(latest_folder) if os.path.isfile(os.path.join(latest_folder, f))]
                if files:
                    # Wait a bit more to ensure download is complete
                    time.sleep(5)
                    break
            time.sleep(2)
        else:
            print("Download timeout reached")

        # Find and copy the file from playwright-artifacts folder while browser is still open
        dest_dir = os.getenv('GNL_BACKLOG', '/home/nizar')
        if suffix:
            dest_dir = os.path.join(dest_dir, suffix)
        if subsuffix:
            dest_dir = os.path.join(dest_dir, subsuffix)
        os.makedirs(dest_dir, exist_ok=True)
        
        playwright_folders = glob.glob("/tmp/playwright-artifacts*")
        if playwright_folders:
            # Get the most recent folder
            latest_folder = max(playwright_folders, key=os.path.getmtime)
            # Find all files in the folder
            all_files = [f for f in os.listdir(latest_folder) if os.path.isfile(os.path.join(latest_folder, f))]
            if all_files:
                source_file = os.path.join(latest_folder, all_files[0])
                dest_file = os.path.join(dest_dir, f"{GNL_NAME_VAR}.m4a")
                shutil.copyfile(source_file, dest_file)
                print(f"File copied to: {dest_file}")
            else:
                print("No files found in playwright-artifacts folder")
        else:
            print("No playwright-artifacts folder found in /tmp")


if __name__ == "__main__":
    fire.Fire(main)
