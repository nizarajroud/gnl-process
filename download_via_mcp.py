#!/usr/bin/env python3
"""Download podcast audio from NotebookLM via MCP library (no browser needed).

Uses notebooklm_tools directly to list notebooks, check audio status, and download.
Polls until all audios are completed or timeout is reached.

Usage:
    python download_via_mcp.py --parent_id=1
"""

import os
import sys
import sqlite3
import time
import asyncio
import fire
from dotenv import load_dotenv
from resolve_parent import resolve_parent

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

POLL_INTERVAL = 60  # seconds between polls


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

    client = get_client()

    # Fetch all notebooks
    print("Fetching notebooks from NotebookLM...")
    nb_result = list_notebooks(client)
    notebooks = {nb['title']: nb for nb in nb_result['notebooks']}
    print(f"Found {len(notebooks)} notebooks")

    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    timeout = int(os.getenv('MCP_DOWNLOAD_TIMEOUT', '2700'))  # 45 min default
    total = len(records)
    succeeded = []
    failed = []

    # Build pending list
    pending = []
    for record_id, source_id, podcast_name, parent_file in records:
        if podcast_name not in notebooks:
            failed.append((record_id, source_id, "Notebook not found"))
        else:
            pending.append((record_id, source_id, podcast_name, parent_file, notebooks[podcast_name]['id']))

    print(f"\nStarting MCP download for {len(pending)} records (parent_id={parent_id}, timeout={timeout}s)\n")

    start_time = time.time()

    while pending and (time.time() - start_time) < timeout:
        still_pending = []

        for record_id, source_id, podcast_name, parent_file, notebook_id in pending:
            # Check audio status
            try:
                status = get_studio_status(client, notebook_id)
                artifacts = status.get('artifacts', [])
                audio = next((a for a in artifacts if a.get('type') == 'audio' and a.get('status') == 'completed'), None)
            except Exception as e:
                print(f"  [{podcast_name}] ⚠ Status check failed: {e}")
                still_pending.append((record_id, source_id, podcast_name, parent_file, notebook_id))
                continue

            if not audio:
                still_pending.append((record_id, source_id, podcast_name, parent_file, notebook_id))
                continue

            # Download audio
            dest_dir = os.path.join(audio_parts_folder, subfolder, parent_file)
            dest_file = os.path.join(dest_dir, f"{podcast_name}.m4a")
            os.makedirs(dest_dir, exist_ok=True)

            try:
                asyncio.run(download_async(client, notebook_id, "audio", dest_file, artifact_id=audio.get('artifact_id')))
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE podcast_download SET download_state = 1 WHERE id = ?", (record_id,))
                conn.commit()
                conn.close()
                print(f"  [{podcast_name}] ✓ Downloaded")
                succeeded.append((record_id, source_id))
            except Exception as e:
                print(f"  [{podcast_name}] ⚠ Download failed: {e}")
                failed.append((record_id, source_id, str(e)[:80]))

        pending = still_pending

        if pending:
            elapsed = int(time.time() - start_time)
            print(f"\n  ⏳ {len(pending)} pending, {len(succeeded)} done | {elapsed}s elapsed | next poll in {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)

    # Timeout remaining
    for record_id, source_id, podcast_name, parent_file, notebook_id in pending:
        failed.append((record_id, source_id, "Timeout"))

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
