#!/usr/bin/env python3
"""Process all matching records by calling the main script once per record."""

import subprocess
import sys
import sqlite3
import os
import logging
from datetime import datetime
import fire
from dotenv import load_dotenv
from resolve_parent import resolve_parent

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

TRACING = os.getenv('TRACING', '0') == '1'


def setup_logging(parent_id):
    """Setup file logging if TRACING is enabled."""
    if not TRACING:
        return None
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, f"generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}_parent{parent_id or 'all'}.log")
    logger = logging.getLogger('gnl_generation')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
    logger.addHandler(handler)
    logger.info(f"Tracing started — log file: {log_file}")
    return logger


def log_print(msg, logger=None):
    """Print to stdout and optionally to log file."""
    print(msg)
    if logger:
        logger.info(msg)


def main(source_type: str = None, generation_mode: str = None, theme: str = None, subfolder: str = None, parent_id: int = None):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gnl.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    source_type, generation_mode, theme, subfolder = resolve_parent(db_path, source_type, generation_mode, theme, subfolder, parent_id)
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nllm-aws-asl-add-generate-gnl_v2.py')
    logger = setup_logging(parent_id)

    # Get all pending records
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """SELECT pd.id, pd.source_id FROM podcast_download pd
        JOIN parent_configuration pc ON pd.parent_configuration_id = pc.id
        WHERE pc.source_type = ? AND pc.generation_mode = ? AND pc.podcast_theme = ? AND pc.podcast_subtheme = ?
        AND pd.generation_state = 0"""
    params = [source_type, generation_mode, theme, subfolder]
    if parent_id:
        query += " AND pd.parent_configuration_id = ?"
        params.append(parent_id)
    query += " ORDER BY CAST(REPLACE(REPLACE(REPLACE(pd.source_id, 'p', ''), 'q', ''), '.pdf', '') AS INTEGER) ASC"
    cursor.execute(query, params)
    records = cursor.fetchall()
    conn.close()

    if not records:
        log_print("\n✓ No records to process.", logger)
        sys.exit(0)

    total = len(records)
    succeeded = []
    failed = []

    log_print(f"\nStarting generation for {total} records (parent_id={parent_id})", logger)

    for i, (record_id, source_id) in enumerate(records, 1):
        log_print(f"\n{'='*60}", logger)
        log_print(f"[{i}/{total}] Processing record {record_id} ({source_id})", logger)
        log_print(f"{'='*60}\n", logger)

        cmd = ['python', script_path, source_type, generation_mode, theme, subfolder]
        if parent_id:
            cmd += ['--parent_id', str(parent_id)]

        GENERATION_TIMEOUT = int(os.getenv('GENERATION_TIMEOUT_SECONDS', '300'))

        if TRACING and logger:
            log_file_path = logger.handlers[0].baseFilename
            with open(log_file_path, 'a') as log_f:
                try:
                    result = subprocess.run(cmd, stdout=log_f, stderr=log_f, text=True, timeout=GENERATION_TIMEOUT)
                except subprocess.TimeoutExpired:
                    log_print(f"⏱ Record {record_id} ({source_id}) timed out after {GENERATION_TIMEOUT}s.", logger)
                    result = type('Result', (), {'returncode': 1})()
        else:
            try:
                result = subprocess.run(cmd, timeout=GENERATION_TIMEOUT)
            except subprocess.TimeoutExpired:
                log_print(f"⏱ Record {record_id} ({source_id}) timed out after {GENERATION_TIMEOUT}s.", logger)
                result = type('Result', (), {'returncode': 1})()

        # Cleanup Chrome between records to prevent SingletonLock issues
        subprocess.run(['pkill', '-9', '-f', 'Clone-Chrome-profile'], capture_output=True)
        lock_path = os.path.join(os.getenv('USER_DATA_DIR', ''), 'SingletonLock')
        try:
            os.unlink(lock_path)
        except OSError:
            pass

        if result.returncode == 0:
            succeeded.append((record_id, source_id))
            log_print(f"✓ Record {record_id} ({source_id}) succeeded.", logger)
        else:
            failed.append((record_id, source_id))
            log_print(f"⚠ Record {record_id} ({source_id}) failed. Moving to next.", logger)

    # Summary
    summary = f"""
{'='*60}
GENERATION SUMMARY
{'='*60}
Total: {total} | Succeeded: {len(succeeded)} | Failed: {len(failed)}"""
    if failed:
        summary += f"\n\nFailed records:\n{'ID':<6} {'File':<20}\n{'-'*6} {'-'*20}"
        for rid, sid in failed:
            summary += f"\n{rid:<6} {sid:<20}"
    summary += f"\n{'='*60}"
    log_print(summary, logger)

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    fire.Fire(main)
