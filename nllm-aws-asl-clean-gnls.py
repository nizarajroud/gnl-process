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
from dotenv import load_dotenv
from pyfzf.pyfzf import FzfPrompt
from nova_act import NovaAct

load_dotenv()


def main(user_data_dir: str = None, headless: bool = None) -> None:
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
        
        # Delete notebooks
        for _ in range(200):
            try:
                nova.act('Click on the kebab menu (three dots) for the first notebook in the list')
                nova.act('Click on the Delete option in the menu')
                nova.act('on the popup that will appear, click on the delete button to confirm deletion')
                time.sleep(2)  # Wait for deletion to complete
            except Exception:
                break  # No more notebooks to delete
        input("Press Enter to close the browser...")


if __name__ == "__main__":
    fire.Fire(main)
