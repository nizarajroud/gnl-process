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


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def prepare_file_item(item, on_progress=None):
    """Prepare one file-based work item into the production DB.

    This is the QUOTA-FREE phase: split the PDF/DOCX into episodes, insert
    into parent_configuration, and generate titles. It makes the material
    ready for the (separate) NLM audio generation step.

    Returns parent_id on success, None on failure.
    """
    from gnl_core.config import get_config

    if _is_test_mode():
        # Simulate a successful prepare without touching disk/DB
        if on_progress:
            on_progress(f"  [TEST] prepare {item.category}/{item.identifier}")
        return -1  # sentinel parent_id for tests

    config = get_config()

    theme, _, subtheme = item.category.partition('/')
    inbox = config.get('INBOX_FOLDER', '')
    folder = os.path.join(inbox, theme, subtheme)
    pdf_path = os.path.join(folder, item.identifier)
    if not os.path.isfile(pdf_path):
        if on_progress:
            on_progress(f"  ✗ Introuvable: {pdf_path}")
        return None

    name = os.path.splitext(item.identifier)[0]
    cfg = item.config or {}
    pages_per_episode = int(cfg.get('pages_per_episode', 0) or 0)

    if pages_per_episode <= 0:
        import math
        if item.identifier.lower().endswith('.docx'):
            from docx import Document
            doc = Document(pdf_path)
            total = max(1, len(doc.paragraphs) // 30)
        else:
            from PyPDF2 import PdfReader
            total = len(PdfReader(pdf_path).pages)
        pages_per_episode = math.ceil(total / 20)

    from gnl_core.split import split
    from gnl_core.collect import collect
    from gnl_core.titles import generate_titles

    result = split(pdf_path, pages_per_episode, name,
                    podcast_theme=theme, podcast_subtheme=subtheme, mode='pages')
    parent_id = collect(result)
    generate_titles(parent_id)
    if on_progress:
        on_progress(f"  ✓ {item.category}/{item.identifier} → parent_id={parent_id}")
    return parent_id


def make_generate_fn(on_progress=None):
    """Return a generate_fn(WorkItem) -> bool for the orchestrator.

    Current scope: the QUOTA-FREE prepare phase for file-based categories
    (aws/*, misc/*). Exams and saved-articles have distinct pipelines and are
    skipped here (returned False) until wired explicitly.

    Respects TEST_MODE via prepare_file_item.
    """
    def generate(item):
        from gnl_core.auto_generate import SKIP
        category = item.category
        try:
            if category == 'saved-articles/linkedin':
                if on_progress:
                    on_progress("  (linkedin: batch NLM pipeline, not wired here)")
                return SKIP
            theme = category.partition('/')[0]
            if theme == 'exams':
                if on_progress:
                    on_progress("  (exams: dedicated pipeline, not wired here)")
                return SKIP
            parent_id = prepare_file_item(item, on_progress=on_progress)
            return parent_id is not None
        except Exception as e:
            if on_progress:
                on_progress(f"  ✗ {item.category}/{item.identifier}: {str(e)[:60]}")
            return False
    return generate
