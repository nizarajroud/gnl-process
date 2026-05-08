#!/usr/bin/env python3
"""Generate podcasts via MCP NotebookLM library (no browser, no Nova Act).

Creates notebook, uploads PDF, triggers audio generation, confirms status.

Usage:
    python generate_via_mcp.py --parent_id=1
"""

import os
import sys
import sqlite3
import time
import fire
from dotenv import load_dotenv
from resolve_parent import resolve_parent

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

GENERATION_CONFIRM_TIMEOUT = 120  # seconds to wait for in_progress confirmation
GENERATION_POLL_INTERVAL = 10  # seconds between status checks


def confirm_generation(client, get_studio_status, notebook_id):
    """Poll studio_status until audio is in_progress or completed. Returns True/False."""
    start = time.time()
    while (time.time() - start) < GENERATION_CONFIRM_TIMEOUT:
        try:
            status = get_studio_status(client, notebook_id)
            artifacts = status.get('artifacts', [])
            audio = next((a for a in artifacts if a.get('type') == 'audio'), None)
            if audio and audio.get('status') in ('in_progress', 'completed'):
                return True
        except Exception:
            pass
        time.sleep(GENERATION_POLL_INTERVAL)
    return False


def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)

    # Get pending records
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """SELECT pd.id, pd.source_id, pd.podcast_name, pc.source_path
        FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
        AND pd.generation_state = 0"""
    params = [source_type, generation_mode, theme, subfolder]
    if parent_id:
        query += " AND pd.parent_configuration_id = ?"
        params.append(parent_id)
    query += " ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC"
    cursor.execute(query, params)
    records = cursor.fetchall()
    conn.close()

    if not records:
        print("✓ No records to generate.")
        sys.exit(0)

    # Initialize NotebookLM client
    from notebooklm_tools.mcp.tools._utils import get_client
    from notebooklm_tools.services.notebooks import create_notebook, delete_notebook
    from notebooklm_tools.services.sources import add_source
    from notebooklm_tools.services.studio import create_artifact, get_studio_status

    client = get_client()

    # Load prompt
    prompts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')
    prompt_file = os.path.join(prompts_dir, f"{subfolder}.txt")
    if not os.path.exists(prompt_file):
        prompt_file = os.path.join(prompts_dir, "default.txt")
    with open(prompt_file, 'r') as f:
        audio_prompt = f.read().strip()

    total = len(records)
    succeeded = []
    failed = []

    print(f"\nStarting MCP generation for {total} records (parent_id={parent_id})\n")

    for i, (record_id, source_id, podcast_name, source_path) in enumerate(records, 1):
        print(f"[{i}/{total}] {podcast_name}...", end=" ")

        full_path = f"{source_path}/{source_id}"
        if not os.path.exists(full_path):
            print(f"⚠ File not found: {full_path}")
            failed.append((record_id, source_id, "File not found"))
            continue

        notebook_id = None
        try:
            # 1. Create notebook
            nb = create_notebook(client, title=podcast_name)
            notebook_id = nb['notebook_id']

            # 2. Upload PDF
            add_source(client, notebook_id, source_type="file", file_path=full_path, wait=True)

            # 3. Generate audio
            language = os.getenv('NOTEBOOKLM_LANGUAGE', 'en')
            create_artifact(client, notebook_id, artifact_type="audio", focus_prompt=audio_prompt, language=language)

            # 4. Confirm generation started
            if confirm_generation(client, get_studio_status, notebook_id):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE podcast_download SET generation_state = 1, date = ? WHERE id = ?", (time.strftime("%Y-%m-%d"), record_id))
                conn.commit()
                conn.close()
                print("✓")
                succeeded.append((record_id, source_id))
            else:
                # Cleanup orphan notebook
                print("⚠ Generation not confirmed, cleaning up")
                delete_notebook(client, notebook_id)
                failed.append((record_id, source_id, "Generation not confirmed"))

        except Exception as e:
            print(f"⚠ {str(e)[:60]}")
            # Cleanup if notebook was created
            if notebook_id:
                try:
                    delete_notebook(client, notebook_id)
                except Exception:
                    pass
            failed.append((record_id, source_id, str(e)[:80]))

    # Summary
    print(f"\n{'='*60}")
    print(f"GENERATION SUMMARY (MCP)")
    print(f"{'='*60}")
    print(f"Total: {total} | Succeeded: {len(succeeded)} | Failed: {len(failed)}")
    if failed:
        print(f"\n{'ID':<6} {'File':<20} {'Reason':<50}")
        print(f"{'-'*6} {'-'*20} {'-'*50}")
        for rid, sid, reason in failed:
            print(f"{rid:<6} {sid:<20} {reason:<50}")
    print(f"{'='*60}")

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    fire.Fire(main)
