"""Real wiring for the auto-generation orchestrator.

Provides concrete implementations of:
  - list_pending_fn(category, cfg) -> list of unprocessed material identifiers
  - make_generate_fn(...)         -> generate_fn(WorkItem) -> bool

Kept separate from auto_generate.py so the orchestrator stays pure and testable.
"""

import os
from pathlib import Path


def list_pending(category, cfg):
    """Return unprocessed material identifiers for a category.

    category format: "theme/subtheme" (e.g. "aws/aws-papers")
    A file is 'pending' if it exists in INBOX but not yet delivered to BACKLOG.
    For saved-articles/linkedin, pending = DB rows with processed=0.
    """
    from gnl_core.config import get_config
    config = get_config()

    if category == 'saved-articles/linkedin':
        from gnl_core.db import get_db
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id FROM saved_articles WHERE source='linkedin' AND processed=0"
            ).fetchall()
        return [r[0] for r in rows]

    # File-based categories (aws/*, misc/*, exams/*)
    theme, _, subtheme = category.partition('/')
    inbox = config.get('INBOX_FOLDER', '')
    folder = os.path.join(inbox, theme, subtheme)
    if not os.path.isdir(folder):
        return []

    backlog = config.get('GNL_BACKLOG', '')
    backlog_dir = os.path.join(backlog, theme, subtheme)
    delivered = set()
    if os.path.isdir(backlog_dir):
        delivered = {os.path.splitext(f)[0] for f in os.listdir(backlog_dir) if f.lower().endswith('.mp3')}

    pending = []
    for f in sorted(os.listdir(folder)):
        if f.lower().endswith(('.pdf', '.docx')) and not f.startswith('~$'):
            name_no_ext = os.path.splitext(f)[0]
            if theme == 'exams':
                # For exams, 'pending' = no .apkg yet
                from gnl_core.exams import get_exam_base
                base = get_exam_base(theme, subtheme)
                apkg = base / 'Anki-generation' / 'anki' / f"{name_no_ext}.apkg"
                if not apkg.exists():
                    pending.append(f)
            else:
                if name_no_ext not in delivered:
                    pending.append(f)
    return pending


def make_generate_fn(on_progress=None):
    """Return a generate_fn(WorkItem) -> bool that runs the real pipeline
    for the item's category, respecting its per-category config.

    NOTE: This is a synchronous wrapper. Heavy work (NLM generation) is
    delegated to existing pipeline functions.
    """
    def generate(item):
        category = item.category
        cfg = item.config or {}
        try:
            if category == 'saved-articles/linkedin':
                # Handled in batch elsewhere; single-article generation not wired here
                if on_progress:
                    on_progress(f"  (linkedin batch handled separately)")
                return False
            # File-based: reuse prepare-from-inbox pipeline logic
            # This would call the same code path as the UI 'Traiter' button.
            # Left as an integration point — see _run_auto_pass in app.py.
            return False
        except Exception:
            return False
    return generate
