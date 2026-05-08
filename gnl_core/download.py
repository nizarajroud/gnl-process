"""Download podcast audio from NotebookLM."""

import os
import time
import asyncio
from notebooklm_tools.mcp.tools._utils import get_client
from notebooklm_tools.services.notebooks import list_notebooks
from notebooklm_tools.services.studio import get_studio_status
from notebooklm_tools.services.downloads import download_async

from .db import get_records, update_state, resolve_parent

POLL_INTERVAL = 60


def download(parent_id, db_path=None, timeout=None):
    """Download completed audio for a parent. Polls until all done or timeout. Returns (succeeded, failed)."""
    timeout = timeout or int(os.getenv('MCP_DOWNLOAD_TIMEOUT', '2700'))

    records = get_records(parent_id, db_path, generation_state=1, download_state=0)
    if not records:
        return [], []

    client = get_client()
    nb_result = list_notebooks(client)
    notebooks = {nb['title']: nb for nb in nb_result['notebooks']}

    _, _, _, subfolder = resolve_parent(parent_id, db_path)
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')

    succeeded, failed = [], []

    # Build pending list
    pending = []
    for rec in records:
        if rec['podcast_name'] not in notebooks:
            failed.append({**rec, 'reason': 'Notebook not found'})
        else:
            pending.append({**rec, 'notebook_id': notebooks[rec['podcast_name']]['id']})

    start_time = time.time()

    while pending and (time.time() - start_time) < timeout:
        still_pending = []

        for rec in pending:
            try:
                status = get_studio_status(client, rec['notebook_id'])
                audio = next((a for a in status.get('artifacts', []) if a.get('type') == 'audio' and a.get('status') == 'completed'), None)
            except Exception:
                still_pending.append(rec)
                continue

            if not audio:
                still_pending.append(rec)
                continue

            dest_dir = os.path.join(audio_parts_folder, subfolder, rec['parent_file'])
            dest_file = os.path.join(dest_dir, f"{rec['podcast_name']}.m4a")
            os.makedirs(dest_dir, exist_ok=True)

            try:
                asyncio.run(download_async(client, rec['notebook_id'], "audio", dest_file, artifact_id=audio.get('artifact_id')))
                update_state(rec['id'], db_path, download_state=1)
                succeeded.append(rec)
            except Exception as e:
                failed.append({**rec, 'reason': str(e)[:80]})

        pending = still_pending
        if pending:
            time.sleep(POLL_INTERVAL)

    # Timeout remaining
    for rec in pending:
        failed.append({**rec, 'reason': 'Timeout'})

    return succeeded, failed
