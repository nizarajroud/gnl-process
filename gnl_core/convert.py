"""Convert M4A to MP3."""

import os
import subprocess
from pathlib import Path

from .db import get_records, update_state, resolve_parent


def convert(parent_id, db_path=None):
    """Convert all pending m4a files to mp3. Returns (succeeded, failed)."""
    records = get_records(parent_id, db_path, download_state=1, conversion_state=0)
    if not records:
        return [], []

    test_mode = os.getenv('TEST_MODE', '0') == '1'
    _, _, theme, subfolder = resolve_parent(parent_id, db_path)
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    succeeded, failed = [], []

    for rec in records:
        audio_dir = Path(audio_parts_folder) / theme / subfolder / rec['parent_file']
        input_file = audio_dir / f"{rec['podcast_name']}.m4a"
        output_file = audio_dir / f"{rec['podcast_name']}.mp3"

        if output_file.exists() and not input_file.exists():
            update_state(rec['id'], db_path, conversion_state=1)
            succeeded.append(rec)
            continue

        if not input_file.exists():
            failed.append({**rec, 'reason': 'File not found'})
            continue

        if test_mode:
            input_file.rename(output_file)
        else:
            result = subprocess.run(['ffmpeg', '-y', '-i', str(input_file), str(output_file)],
                                   capture_output=True, text=True)
            if result.returncode != 0:
                failed.append({**rec, 'reason': 'FFmpeg error'})
                continue
            input_file.unlink()

        update_state(rec['id'], db_path, conversion_state=1)
        succeeded.append(rec)

    return succeeded, failed
