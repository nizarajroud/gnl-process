#!/usr/bin/env python3
"""List available parent configurations for a given phase.

Usage:
    python list_parents.py <phase>

Phases:
    process  - parents with pending generation (generation_state = 0)
    deliver  - parents with all generated and downloaded (ready for convert/combine)
"""

import fire
import os
import sys
import json
import sqlite3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


def main(phase: str):
    phase = phase.lower()
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')

    if not os.path.exists(db_path):
        print(json.dumps([]))
        sys.exit(0)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if phase == 'process':
        cursor.execute("""
            SELECT pc.id, pc.podcast_theme, pc.podcast_subtheme, pc.source_type, pc.generation_mode,
                   COUNT(pd.id) as total,
                   SUM(CASE WHEN pd.generation_state = 1 THEN 1 ELSE 0 END) as generated,
                   SUM(CASE WHEN pd.download_state = 1 THEN 1 ELSE 0 END) as downloaded
            FROM parent_configuration pc
            JOIN podcast_download pd ON pd.parent_configuration_id = pc.id
            GROUP BY pc.id
            HAVING generated < total
        """)
    elif phase == 'deliver':
        cursor.execute("""
            SELECT pc.id, pc.podcast_theme, pc.podcast_subtheme, pc.source_type, pc.generation_mode,
                   COUNT(pd.id) as total,
                   SUM(CASE WHEN pd.generation_state = 1 THEN 1 ELSE 0 END) as generated,
                   SUM(CASE WHEN pd.download_state = 1 THEN 1 ELSE 0 END) as downloaded
            FROM parent_configuration pc
            JOIN podcast_download pd ON pd.parent_configuration_id = pc.id
            WHERE pc.combination_state = 0
            GROUP BY pc.id
            HAVING generated = total AND downloaded = total
        """)
    else:
        print(f"Unknown phase: {phase}")
        sys.exit(1)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "label": f"{row[1]}/{row[2]} ({row[5]} files, {row[6]} generated, {row[7]} downloaded)",
            "theme": row[1],
            "subtheme": row[2],
            "source_type": row[3],
            "generation_mode": row[4]
        })

    print(json.dumps(results))


if __name__ == "__main__":
    fire.Fire(main)
