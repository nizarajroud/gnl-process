"""Podcast generation via NotebookLM MCP library."""

import os
import time
from .db import get_records, update_state

CONFIRM_TIMEOUT = int(os.getenv('CONFIRM_TIMEOUT', '300'))
CONFIRM_POLL_INTERVAL = int(os.getenv('CONFIRM_POLL_INTERVAL', '10'))


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def _confirm_generation(client, notebook_id):
    """Poll until audio is in_progress or completed."""
    from notebooklm_tools.services.studio import get_studio_status
    start = time.time()
    while (time.time() - start) < CONFIRM_TIMEOUT:
        try:
            status = get_studio_status(client, notebook_id)
            audio = next((a for a in status.get('artifacts', []) if a.get('type') == 'audio'), None)
            if audio and audio.get('status') in ('in_progress', 'completed'):
                return True
        except Exception:
            pass
        time.sleep(CONFIRM_POLL_INTERVAL)
    return False


def generate(parent_id, db_path=None, prompt_dir=None, language=None, max_count=None, on_progress=None, should_stop=None):
    """Generate podcasts for pending records. Returns (succeeded, failed) lists.
    on_progress: optional callback called after each successful generation.
    should_stop: optional callable returning True to abort.
    """
    language = language or os.getenv('NOTEBOOKLM_LANGUAGE', 'en')
    prompt_dir = prompt_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prompts')

    records = get_records(parent_id, db_path, generation_state=0)
    if not records:
        return [], []

    if max_count is not None:
        records = records[:max_count]

    if _is_test_mode():
        return _generate_test(records, db_path, on_progress, should_stop)

    from notebooklm_tools.mcp.tools._utils import get_client
    from notebooklm_tools.services.notebooks import create_notebook, delete_notebook
    from notebooklm_tools.services.sources import add_source
    from notebooklm_tools.services.studio import create_artifact

    client = get_client()

    # Load prompt from DB (series_catalog) or fallback to file
    from .db import resolve_parent, get_db
    _, _, _, subfolder = resolve_parent(parent_id, db_path)
    audio_prompt = ""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT prompt FROM series_catalog WHERE subtheme=?", (subfolder,)).fetchone()
        if row and row['prompt']:
            audio_prompt = row['prompt']
    if not audio_prompt:
        prompt_file = os.path.join(prompt_dir, f"{subfolder}.txt")
        if not os.path.exists(prompt_file):
            prompt_file = os.path.join(prompt_dir, "default.txt")
        with open(prompt_file) as f:
            audio_prompt = f.read().strip()

    succeeded, failed = [], []

    for rec in records:
        if should_stop and should_stop():
            break
        full_path = f"{rec['source_path']}/{rec['source_id']}"
        if not os.path.exists(full_path):
            failed.append({**rec, 'reason': 'File not found'})
            continue

        notebook_id = None
        try:
            nb = create_notebook(client, title=rec['podcast_name'])
            notebook_id = nb['notebook_id']
            add_source(client, notebook_id, source_type="file", file_path=full_path, wait=True)
            create_artifact(client, notebook_id, artifact_type="audio", focus_prompt=audio_prompt, language=language)

            if _confirm_generation(client, notebook_id):
                update_state(rec['id'], db_path, generation_state=1, date=time.strftime("%Y-%m-%d"))
                succeeded.append(rec)
                if on_progress:
                    on_progress(rec)
            else:
                delete_notebook(client, notebook_id)
                failed.append({**rec, 'reason': 'Generation not confirmed'})
        except Exception as e:
            if notebook_id:
                try:
                    delete_notebook(client, notebook_id)
                except Exception:
                    pass
            # Stop on quota error (code 8)
            if 'code 8' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
                failed.append({**rec, 'reason': 'Quota exhausted'})
                break
            failed.append({**rec, 'reason': str(e)[:80]})

    return succeeded, failed


def _generate_test(records, db_path, on_progress=None, should_stop=None):
    """Test mode: simulate generation without API calls."""
    delay = int(os.getenv('TEST_GENERATION_DELAY', '1'))
    succeeded = []
    for rec in records:
        if should_stop and should_stop():
            break
        time.sleep(delay)
        update_state(rec['id'], db_path, generation_state=1, date=time.strftime("%Y-%m-%d"))
        succeeded.append(rec)
        if on_progress:
            on_progress(rec)
    return succeeded, []
