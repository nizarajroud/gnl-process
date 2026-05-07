#!/usr/bin/env python3
"""Download podcast audio from NotebookLM via MCP library (no browser needed).

Uses notebooklm_tools directly to list notebooks, check audio status, and download.

Usage:
    python download_via_mcp.py --parent_id=1
"""

import os
import sys
import sqlite3
import fire
from dotenv import load_dotenv
from resolve_parent import resolve_parent

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)

    # Get pending download records
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """SELECT pd.id, pd.source_id, pd.podcast_name, pc.parent_file
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
        AND pd.generation_state = 1 AND pd.download_state = 0"""
    params = [source_type, generation_mode, theme, subfolder]
    if parent_id:
        query += " AND pd.parent_configuration_id = ?"
        params.append(parent_id)
    query += " ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC"
    cursor.execute(query, params)
    records = cursor.fetchall()
    conn.close()

    if not records:
        print("✓ No records to download.")
        sys.exit(0)

    # Initialize NotebookLM client
    from notebooklm_tools.mcp.tools._utils import get_client
    from notebooklm_tools.services.notebooks import list_notebooks
    from notebooklm_tools.services.studio import get_studio_status
    from notebooklm_tools.services.downloads import download_async
    import asyncio

    client = get_client()

    # Fetch all notebooks
    print("Fetching notebooks from NotebookLM...")
    nb_result = list_notebooks(client)
    notebooks = {nb['title']: nb for nb in nb_result['notebooks']}
    print(f"Found {len(notebooks)} notebooks")

    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    total = len(records)
    succeeded = []
    failed = []

    print(f"\nStarting MCP download for {total} records (parent_id={parent_id})\n")

    for i, (record_id, source_id, podcast_name, parent_file) in enumerate(records, 1):
        print(f"[{i}/{total}] {podcast_name}...", end=" ")

        # Find notebook by title
        if podcast_name not in notebooks:
            print("⚠ Notebook not found")
            failed.append((record_id, source_id, "Notebook not found"))
            continue

        notebook_id = notebooks[podcast_name]['id']

        # Check audio status
        try:
            status = get_studio_status(client, notebook_id)
            artifacts = status.get('artifacts', [])
            audio = next((a for a in artifacts if a.get('type') == 'audio' and a.get('status') == 'completed'), None)

            if not audio:
                print("⚠ No completed audio")
                failed.append((record_id, source_id, "No completed audio"))
                continue
        except Exception as e:
            print(f"⚠ Status check failed: {e}")
            failed.append((record_id, source_id, str(e)))
            continue

        # Download audio
        dest_dir = os.path.join(audio_parts_folder, subfolder, parent_file)
        dest_file = os.path.join(dest_dir, f"{podcast_name}.m4a")
        os.makedirs(dest_dir, exist_ok=True)

        try:
            result = asyncio.run(download_async(client, notebook_id, "audio", dest_file, artifact_id=audio.get('artifact_id')))
            print(f"✓ Downloaded")

            # Update DB
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE podcast_download SET download_state = 1 WHERE id = ?", (record_id,))
            conn.commit()
            conn.close()
            succeeded.append((record_id, source_id))
        except Exception as e:
            print(f"⚠ Download failed: {e}")
            failed.append((record_id, source_id, str(e)))

    # Summary
    print(f"\n{'='*60}")
    print(f"DOWNLOAD SUMMARY (MCP)")
    print(f"{'='*60}")
    print(f"Total: {total} | Succeeded: {len(succeeded)} | Failed: {len(failed)}")
    if failed:
        print(f"\n{'ID':<6} {'File':<20} {'Reason':<40}")
        print(f"{'-'*6} {'-'*20} {'-'*40}")
        for rid, sid, reason in failed:
            print(f"{rid:<6} {sid:<20} {reason:<40}")
    print(f"{'='*60}")

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    fire.Fire(main)
