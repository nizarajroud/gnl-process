# Copyright 2025 Amazon Inc

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""AWS Solutions to NotebookLM automation script.

Usage:
python nllm-aws-asl.py [user_data_dir] [--headless]
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
        

        nova.act('Click on "+ Create new" button on the right hight corner ')
        nova.act('Click on "Website" button ')
        nova.act(f'insert this link <{url}> into the text box ')
        nova.act('Click on "insert" button ')
        time.sleep(3) 
        nova.act(f'Click on the name of the generated notebook on the left hight corner, select all and replace it with {GNL_NAME_VAR} ')
        # nova.act("Click on the 'Audio Overview' button to generate an AI podcast based on the available sources")
        # nova.act("The task is already accomplished - the Audio Overview generation has been successfully initiated and is in progress. No further action is needed at this time.")
      


if __name__ == "__main__":
    fire.Fire(main)
