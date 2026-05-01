"""NotebookLM cleanup script - delete all notebooks.

Usage:
python nllm-aws-asl-clean-gnls.py [user_data_dir] [--tabs=3]
"""

import fire
import os
import time
from dotenv import load_dotenv
from nova_act import NovaAct

load_dotenv()


def main(user_data_dir: str = None) -> None:
    if user_data_dir is None:
        user_data_dir = os.getenv('USER_DATA_DIR')
        if user_data_dir is None:
            raise ValueError("USER_DATA_DIR must be provided either as parameter or in .env file")
    
    headless = os.getenv('HEADLESS', '0') == '1'

    # Clean stale SingletonLock
    singleton_lock = os.path.join(user_data_dir, 'SingletonLock')
    if os.path.exists(singleton_lock):
        os.remove(singleton_lock)
        print("🔓 Removed stale SingletonLock")

    with NovaAct(
        starting_page="http://notebooklm.google.com/",
        user_data_dir=user_data_dir,
        headless=headless,
        clone_user_data_dir=False,
    ) as nova:
        time.sleep(3)
        
        deleted = 0
        for _ in range(200):
            try:
                nova.act(
                    'Click on the kebab menu (three dots) for the first notebook in the list, '
                    'then click "Delete" from the menu, '
                    'then click the "Delete" button on the confirmation popup.'
                )
                deleted += 1
                print(f"✓ Deleted notebook #{deleted}")
                time.sleep(1)
            except Exception:
                print(f"\nDone. Deleted {deleted} notebooks total.")
                break


if __name__ == "__main__":
    fire.Fire(main)
