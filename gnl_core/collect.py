"""Collect split files and save to database."""

import os
import shutil
from .db import get_db


def collect(split_result, db_path=None):
    """Insert split result into DB. Returns parent_configuration_id."""
    files = split_result.get('files', [])
    if not files:
        raise ValueError("No files in split result")

    generation_mode = split_result.get('mode', 'bulk')
    split_configuration = split_result.get('splitConfiguration', '')
    parent_file = files[0].get('parentDir', '')
    source_path = os.path.dirname(files[0].get('fullPath', ''))
    source_type = files[0].get('sourceType', '')
    podcast_theme = files[0].get('podcastTheme', '')
    podcast_subtheme = files[0].get('podcastSubfolder', '').lower()

    # Clean existing audio parts
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    if audio_parts_folder and podcast_subtheme and parent_file:
        audio_dir = os.path.join(audio_parts_folder, podcast_theme, podcast_subtheme, parent_file)
        if os.path.exists(audio_dir):
            shutil.rmtree(audio_dir)

    with get_db(db_path) as conn:
        # Check existing (not deleted)
        row = conn.execute(
            "SELECT id FROM parent_configuration WHERE parent_file = ? AND podcast_subtheme = ? AND combination_state != -1",
            (parent_file, podcast_subtheme)
        ).fetchone()

        if row:
            parent_id = row['id']
            conn.execute("DELETE FROM podcast_download WHERE parent_configuration_id = ?", (parent_id,))
            conn.execute("""UPDATE parent_configuration 
                SET source_path=?, source_type=?, podcast_theme=?, split_configuration=?, generation_mode=?, combination_state=0
                WHERE id=?""",
                (source_path, source_type, podcast_theme, split_configuration, generation_mode, parent_id))
        else:
            cursor = conn.execute("""INSERT INTO parent_configuration 
                (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, split_configuration, generation_mode, combination_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (parent_file, source_path, source_type, podcast_theme, podcast_subtheme, split_configuration, generation_mode))
            parent_id = cursor.lastrowid

        for f in files:
            conn.execute("""INSERT INTO podcast_download 
                (parent_configuration_id, source_id, podcast_name, generation_state, download_state, conversion_state, date)
                VALUES (?, ?, '', 0, 0, 0, NULL)""",
                (parent_id, f.get('fileName', '')))

        conn.commit()

    return parent_id
