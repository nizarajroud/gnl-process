"""NotebookLM notebook cleanup."""

from notebooklm_tools.mcp.tools._utils import get_client
from notebooklm_tools.services.notebooks import list_notebooks, delete_notebook

from .db import get_db


def clean(target="all", db_path=None):
    """Delete notebooks and reset DB states. target='all' or a parent_id number. Returns (deleted, failed) counts."""
    client = get_client()
    nb_result = list_notebooks(client)
    notebooks = nb_result['notebooks']

    if target != "all":
        parent_id = int(target)
        with get_db(db_path) as conn:
            rows = conn.execute("SELECT podcast_name FROM podcast_download WHERE parent_configuration_id = ?", (parent_id,)).fetchall()
        names = {r['podcast_name'] for r in rows}
        notebooks = [nb for nb in notebooks if nb['title'] in names]

        # Reset DB states
        with get_db(db_path) as conn:
            conn.execute("UPDATE podcast_download SET generation_state=0, download_state=0, conversion_state=0 WHERE parent_configuration_id=?", (parent_id,))
            conn.commit()
    else:
        # Reset all
        with get_db(db_path) as conn:
            conn.execute("UPDATE podcast_download SET generation_state=0, download_state=0, conversion_state=0")
            conn.commit()

    deleted, failed_count = 0, 0
    for nb in notebooks:
        try:
            delete_notebook(client, nb['id'])
            deleted += 1
        except Exception:
            failed_count += 1

    return deleted, failed_count
