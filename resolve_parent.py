"""Resolve parent configuration parameters from parent_id."""

import sqlite3
import sys


def resolve_parent(db_path, source_type=None, generation_mode=None, theme=None, subfolder=None, parent_id=None):
    """Resolve source_type, generation_mode, theme, subfolder from parent_id if needed."""
    if not parent_id and not all([source_type, generation_mode, theme, subfolder]):
        print("Error: provide either all 4 params or --parent_id")
        sys.exit(1)

    if parent_id and not all([source_type, generation_mode, theme, subfolder]):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source_type, generation_mode, podcast_theme, podcast_subtheme FROM parent_configuration WHERE id = ?", (parent_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            print(f"Error: Parent ID {parent_id} not found")
            sys.exit(1)
        source_type, generation_mode, theme, subfolder = row

    if generation_mode:
        generation_mode = generation_mode.lower()
    if subfolder:
        subfolder = subfolder.lower()

    return source_type, generation_mode, theme, subfolder
