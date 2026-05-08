#!/usr/bin/env python3
"""Orchestrator: generate → download → convert → combine.

Handles daily quota limits gracefully. Idempotent — safe to re-run daily.

Usage:
    python generate_and_deliver.py --parent_id=1
    python generate_and_deliver.py --all
"""

import os
import sys
import sqlite3
import subprocess
import fire
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_active_parents(db_path):
    """Find all parent_ids with pending work."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT parent_configuration_id FROM podcast_download
        WHERE generation_state = 0 OR download_state = 0 OR conversion_state = 0
    """)
    parents = [row[0] for row in cursor.fetchall()]
    conn.close()
    return parents


def parent_status(db_path, parent_id):
    """Return counts for a parent: total, generated, downloaded, converted."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN generation_state = 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN download_state = 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN conversion_state = 1 THEN 1 ELSE 0 END)
        FROM podcast_download WHERE parent_configuration_id = ?
    """, (parent_id,))
    row = cursor.fetchone()
    conn.close()
    return {'total': row[0], 'generated': row[1], 'downloaded': row[2], 'converted': row[3]}


def run_step(script, parent_id):
    """Run a sub-script, return True if exit code 0."""
    cmd = f"python {os.path.join(SCRIPT_DIR, script)} --parent_id={parent_id}"
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def process_parent(db_path, parent_id):
    """Process a single parent through all stages."""
    status = parent_status(db_path, parent_id)
    total = status['total']
    print(f"\n{'='*60}")
    print(f"Parent {parent_id}: {status['generated']}/{total} generated, {status['downloaded']}/{total} downloaded, {status['converted']}/{total} converted")
    print(f"{'='*60}")

    # Step 1: Generate (if pending)
    if status['generated'] < total:
        print("\n▶ GENERATE")
        run_step("generate_via_mcp.py", parent_id)
        status = parent_status(db_path, parent_id)

    # Step 2: Download (if any generated but not downloaded)
    if status['downloaded'] < status['generated']:
        print("\n▶ DOWNLOAD")
        run_step("download_via_mcp.py", parent_id)
        status = parent_status(db_path, parent_id)

    # Step 3: Convert + Combine only if ALL downloaded
    if status['downloaded'] == total:
        if status['converted'] < total:
            print("\n▶ CONVERT")
            run_step("batch_convert_to_mp3_v2.py", parent_id)
            status = parent_status(db_path, parent_id)

        if status['converted'] == total:
            print("\n▶ COMBINE")
            run_step("combine_mp3_v2.py", parent_id)
            print(f"\n✓ Parent {parent_id} COMPLETE")
            return True
    else:
        remaining = total - status['downloaded']
        print(f"\n⏳ Parent {parent_id}: {remaining}/{total} still pending. Re-run tomorrow.")

    return False


def main(parent_id: int = None, all: bool = False):
    db_path = os.path.join(SCRIPT_DIR, 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    if all:
        parents = get_active_parents(db_path)
        if not parents:
            print("✓ No active parents with pending work.")
            sys.exit(0)
        print(f"Processing {len(parents)} active parent(s): {parents}")
        for pid in parents:
            process_parent(db_path, pid)
    elif parent_id:
        process_parent(db_path, parent_id)
    else:
        print("Usage: python generate_and_deliver.py --parent_id=1 or --all")
        sys.exit(1)


if __name__ == "__main__":
    fire.Fire(main)
