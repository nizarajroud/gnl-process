"""NotebookLM notebook cleanup."""

import os
from notebooklm_tools.mcp.tools._utils import get_client
from notebooklm_tools.services.notebooks import list_notebooks, delete_notebook

from .db import get_db


def clean(target="all", db_path=None):
    """Delete notebooks, files, and mark edition as deleted. Returns (deleted, failed) counts."""
    client = get_client()
    nb_result = list_notebooks(client)
    notebooks = nb_result['notebooks']

    if target != "all":
        parent_id = int(target)
        with get_db(db_path) as conn:
            rows = conn.execute("SELECT podcast_name FROM podcast_download WHERE parent_configuration_id = ?", (parent_id,)).fetchall()
            parent = conn.execute("SELECT parent_file, podcast_subtheme, podcast_theme FROM parent_configuration WHERE id = ?", (parent_id,)).fetchone()
        names = {r['podcast_name'] for r in rows}
        notebooks = [nb for nb in notebooks if nb['title'] in names]

        # Delete audio files
        import shutil
        audio_parts = os.getenv('AUDIO_PARTS_FOLDER', '')
        if audio_parts and parent:
            audio_dir = os.path.join(audio_parts, parent['podcast_subtheme'], parent['parent_file'])
            if os.path.exists(audio_dir):
                shutil.rmtree(audio_dir)

        # Delete combined file on cloud
        gnl_backlog = os.getenv('GNL_BACKLOG', '')
        if gnl_backlog and parent:
            import glob
            cloud_dir = os.path.join(gnl_backlog, parent['podcast_theme'], parent['podcast_subtheme'])
            for f in glob.glob(os.path.join(cloud_dir, f"{parent['parent_file']}*.mp3")):
                os.remove(f)

        # Mark as deleted (keep in DB for history)
        with get_db(db_path) as conn:
            conn.execute("UPDATE parent_configuration SET combination_state=-1 WHERE id=?", (parent_id,))
            conn.execute("DELETE FROM podcast_download WHERE parent_configuration_id=?", (parent_id,))
            conn.commit()
    else:
        with get_db(db_path) as conn:
            conn.execute("UPDATE parent_configuration SET combination_state=-1")
            conn.execute("DELETE FROM podcast_download")
            conn.commit()

    deleted, failed_count = 0, 0
    for nb in notebooks:
        try:
            delete_notebook(client, nb['id'])
            deleted += 1
        except Exception:
            failed_count += 1

    return deleted, failed_count
