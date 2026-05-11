"""Download podcast audio from NotebookLM."""

import os
import time
import asyncio
from .db import get_records, update_state, resolve_parent

POLL_INTERVAL = 60
MAX_STALE_POLLS = 3  # Stop if no progress after 3 consecutive polls


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def download(parent_id, db_path=None, timeout=None):
    """Download completed audio for a parent. Polls until all done or stale. Returns (succeeded, failed)."""
    timeout = timeout or int(os.getenv('MCP_DOWNLOAD_TIMEOUT', '10800'))  # 3h default

    records = get_records(parent_id, db_path, generation_state=1, download_state=0)
    if not records:
        return [], []

    if _is_test_mode():
        return _download_test(records, parent_id, db_path)

    from notebooklm_tools.mcp.tools._utils import get_client
    from notebooklm_tools.services.notebooks import list_notebooks
    from notebooklm_tools.services.studio import get_studio_status
    from notebooklm_tools.services.downloads import download_async

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
    stale_count = 0

    while pending and (time.time() - start_time) < timeout:
        downloaded_this_round = 0
        still_pending = []

        for rec in pending:
            try:
                status = get_studio_status(client, rec['notebook_id'])
                audio = next((a for a in status.get('artifacts', []) if a.get('type') == 'audio' and a.get('status') == 'completed'), None)
            except Exception:
                still_pending.append(rec)
                continue

            if not audio:
                # Check if generation failed
                failed_audio = next((a for a in status.get('artifacts', []) if a.get('type') == 'audio' and a.get('status') == 'failed'), None)
                if failed_audio:
                    max_retries = int(os.getenv('MAX_GENERATION_RETRIES', '3'))
                    # Get current retry_count
                    from .db import get_db
                    with get_db(db_path) as conn:
                        row = conn.execute("SELECT retry_count FROM podcast_download WHERE id=?", (rec['id'],)).fetchone()
                        retry_count = (row['retry_count'] or 0) if row else 0

                    if retry_count < max_retries:
                        # Reset for retry
                        update_state(rec['id'], db_path, generation_state=0)
                        with get_db(db_path) as conn:
                            conn.execute("UPDATE podcast_download SET retry_count=? WHERE id=?", (retry_count + 1, rec['id']))
                            conn.commit()
                        try:
                            from notebooklm_tools.services.notebooks import delete_notebook as del_nb
                            del_nb(client, rec['notebook_id'])
                        except Exception:
                            pass
                    else:
                        # Max retries exhausted
                        failed.append({**rec, 'reason': f'Generation failed after {max_retries} retries'})
                else:
                    still_pending.append(rec)
                continue

            dest_dir = os.path.join(audio_parts_folder, subfolder, rec['parent_file'])
            dest_file = os.path.join(dest_dir, f"{rec['podcast_name']}.m4a")
            os.makedirs(dest_dir, exist_ok=True)

            try:
                asyncio.run(download_async(client, rec['notebook_id'], "audio", dest_file, artifact_id=audio.get('artifact_id')))
                update_state(rec['id'], db_path, download_state=1)
                succeeded.append(rec)
                downloaded_this_round += 1
            except Exception as e:
                failed.append({**rec, 'reason': str(e)[:80]})

        pending = still_pending

        if not pending:
            break

        # Stale detection
        if downloaded_this_round == 0:
            stale_count += 1
            if stale_count >= MAX_STALE_POLLS:
                for rec in pending:
                    failed.append({**rec, 'reason': 'Stale - no progress'})
                break
        else:
            stale_count = 0

        time.sleep(POLL_INTERVAL)

    # Timeout remaining
    for rec in pending:
        if not any(f.get('id') == rec['id'] for f in failed):
            failed.append({**rec, 'reason': 'Timeout'})

    return succeeded, failed


def _download_test(records, parent_id, db_path):
    """Test mode: simulate download with delay then create dummy file."""
    _, _, _, subfolder = resolve_parent(parent_id, db_path)
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    delay = int(os.getenv('TEST_GENERATION_DELAY', '5'))

    time.sleep(delay)

    succeeded = []
    for rec in records:
        dest_dir = os.path.join(audio_parts_folder, subfolder, rec['parent_file'])
        dest_file = os.path.join(dest_dir, f"{rec['podcast_name']}.m4a")
        os.makedirs(dest_dir, exist_ok=True)
        # Create a small dummy file
        with open(dest_file, 'wb') as f:
            f.write(b'\x00' * 1024)
        update_state(rec['id'], db_path, download_state=1)
        succeeded.append(rec)

    return succeeded, []
