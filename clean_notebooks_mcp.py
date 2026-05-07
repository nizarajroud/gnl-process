#!/usr/bin/env python3
"""Delete NotebookLM notebooks via MCP library.

Usage:
    python clean_notebooks_mcp.py --target=all --confirm
    python clean_notebooks_mcp.py --target=1 --confirm
"""

import os
import sys
import sqlite3
import fire
from dotenv import load_dotenv
from notebooklm_tools.mcp.tools._utils import get_client
from notebooklm_tools.services.notebooks import list_notebooks, delete_notebook

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


def main(target: str = "all", confirm: bool = False):
    client = get_client()

    nb_result = list_notebooks(client)
    notebooks = nb_result['notebooks']

    if not notebooks:
        print("✓ No notebooks to delete.")
        return

    # Filter by parent_id if not "all"
    if target.lower() != "all":
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT podcast_name FROM podcast_download WHERE parent_configuration_id = ?", (int(target),))
        names = {row[0] for row in cursor.fetchall()}
        conn.close()
        notebooks = [nb for nb in notebooks if nb['title'] in names]

    if not notebooks:
        print(f"✓ No notebooks found for target={target}.")
        return

    print(f"Found {len(notebooks)} notebooks to delete (target={target}):")
    for nb in notebooks:
        print(f"  - {nb['title']}")

    if not confirm:
        print(f"\nRun with --confirm to delete.")
        return

    deleted = 0
    for nb in notebooks:
        try:
            delete_notebook(client, nb['id'])
            deleted += 1
            print(f"  ✓ Deleted: {nb['title']}")
        except Exception as e:
            print(f"  ⚠ Failed: {nb['title']} ({e})")

    print(f"\nDone. Deleted {deleted}/{len(notebooks)} notebooks.")


if __name__ == "__main__":
    fire.Fire(main)
