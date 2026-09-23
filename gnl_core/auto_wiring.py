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
        # Option A: batch articles so 1 WorkItem = 1 notebook = 1 audio = 1 quota unit.
        # The identifier is a tuple of article ids; generate_linkedin_batch consumes it.
        from gnl_core.db import get_db
        batch_size = int(config.get('ARTICLES_NLM_BATCH_SIZE', '5'))
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id FROM saved_articles WHERE source='linkedin' AND processed=0 ORDER BY id"
            ).fetchall()
        ids = [r[0] for r in rows]
        batches = [tuple(ids[i:i + batch_size]) for i in range(0, len(ids), batch_size)]
        return batches

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


def generate_linkedin_batch(item, on_progress=None):
    """Generate one NLM audio for a batch of LinkedIn articles.

    item.identifier is a tuple of saved_articles ids. Produces one notebook,
    adds each article as a text source, generates + polls + downloads the audio,
    converts to mp3, marks articles processed, and deletes the notebook.

    THIS CONSUMES NLM COMPUTE QUOTA. Respects TEST_MODE (simulates, no calls).

    Returns the mp3 path on success, None on failure.
    """
    import subprocess
    from datetime import datetime
    from gnl_core.config import get_config
    from gnl_core.db import get_db

    article_ids = list(item.identifier) if isinstance(item.identifier, (tuple, list)) else [item.identifier]

    if _is_test_mode():
        if on_progress:
            on_progress(f"  [TEST] NLM batch of {len(article_ids)} articles (no quota consumed)")
        return "/tmp/test-batch.mp3"  # sentinel path, not created

    config = get_config()
    customize_path = Path(__file__).parent.parent / 'prompts' / 'articles-nlm-customize.txt'
    customize_prompt = customize_path.read_text(encoding='utf-8').strip() if customize_path.exists() else ''
    audio_dir = os.path.join(config.get('AUDIO_PARTS_FOLDER', ''), 'saved-articles', 'linkedin')
    os.makedirs(audio_dir, exist_ok=True)
    language = config.get('NOTEBOOKLM_LANGUAGE', 'en')
    download_timeout = int(config.get('MCP_DOWNLOAD_TIMEOUT', '10800'))

    from notebooklm_tools.mcp.tools._utils import get_client
    client = get_client()

    # Load article rows
    with get_db() as conn:
        placeholders = ','.join('?' * len(article_ids))
        rows = conn.execute(
            f"SELECT id, title, content FROM saved_articles WHERE id IN ({placeholders})",
            article_ids
        ).fetchall()
    if not rows:
        if on_progress:
            on_progress("  ✗ Aucun article trouvé pour ce batch")
        return None

    date_str = datetime.now().strftime('%Y%m%d-%H%M%S')
    nb_name = f"articles-batch-{date_str}"

    # Delete a stale notebook with the same name (defensive)
    try:
        for nb in client.list_notebooks():
            if nb.title == nb_name:
                client.delete_notebook(nb.id)
                break
    except Exception:
        pass

    nb = client.create_notebook(title=nb_name)
    nb_id = nb.notebook_id if hasattr(nb, 'notebook_id') else nb.id

    source_ids = []
    for i, row in enumerate(rows):
        src = client.add_text_source(
            notebook_id=nb_id,
            text=f"{row['content'] or ''}",
            title=f"Article {i+1}: {row['title'] or ''}"[:100],
            wait=True,
        )
        if src and src.get('source_id'):
            source_ids.append(src['source_id'])

    if on_progress:
        on_progress(f"  🎙️ Génération audio ({len(rows)} articles)…")

    audio_result = client.create_audio_overview(
        notebook_id=nb_id,
        source_ids=source_ids or None,
        language=language,
        focus_prompt=customize_prompt,
    )

    audio_path = None
    if audio_result:
        m4a_path = os.path.join(audio_dir, f"batch-{date_str}.m4a")
        import time as _t
        from notebooklm_tools.services.studio import get_studio_status
        poll_start = _t.time()
        ready = False
        while _t.time() - poll_start < download_timeout:
            try:
                status = get_studio_status(client, nb_id)
                arts = status.get('artifacts', []) if isinstance(status, dict) else []
                if next((a for a in arts if a.get('type') == 'audio' and a.get('status') == 'completed'), None):
                    ready = True
                    break
                if next((a for a in arts if a.get('type') == 'audio' and a.get('status') == 'failed'), None):
                    break
            except Exception:
                pass
            _t.sleep(15)

        if ready:
            client.download_audio(notebook_id=nb_id, output_path=m4a_path)
            if os.path.exists(m4a_path):
                audio_path = os.path.join(audio_dir, f"batch-{date_str}.mp3")
                subprocess.run(['ffmpeg', '-y', '-i', m4a_path, audio_path], capture_output=True)
                if os.path.exists(m4a_path):
                    os.unlink(m4a_path)

    if audio_path and os.path.exists(audio_path):
        # Success: mark processed, THEN delete the notebook (audio is safely saved locally)
        with get_db() as conn:
            for row in rows:
                conn.execute(
                    "UPDATE saved_articles SET processed=1, audio_path=? WHERE id=?",
                    (audio_path, row['id']),
                )
            conn.commit()
        try:
            client.delete_notebook(nb_id)
        except Exception:
            pass
        if on_progress:
            on_progress(f"  ✓ Batch OK → {audio_path}")
        return audio_path

    # FAILURE / TIMEOUT / INTERRUPTION:
    # Do NOT delete the notebook — the audio may still be generating in NotebookLM.
    # Leaving it intact lets a later pass recover the audio instead of losing it.
    if on_progress:
        on_progress(
            f"  ⚠ Audio non récupéré — notebook '{nb_name}' CONSERVÉ pour récupération "
            f"(nb_id={nb_id})"
        )
    return None


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
                audio_path = generate_linkedin_batch(item, on_progress=on_progress)
                return audio_path is not None
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


def finalize_category(category, items, on_progress=None):
    """Combine the audio produced THIS pass for a category into one final file
    delivered to the Drive backlog. Returns the output path, or None.

    Currently implemented for saved-articles/linkedin: concatenates the batch
    MP3s (with 3s silence between) into GNL_BACKLOG/saved-articles/linkedin/.
    File-based categories (aws/*) don't need combining here (each becomes its
    own production edition), so they return None.

    Respects TEST_MODE (returns a sentinel path without touching disk).
    """
    import subprocess
    from datetime import datetime
    from gnl_core.config import get_config

    if category != 'saved-articles/linkedin':
        return None  # aws/* handled by the production/deliver pipeline

    if _is_test_mode():
        if on_progress:
            on_progress(f"  [TEST] finalize {category} ({len(items)} batches)")
        return "/tmp/test-final.mp3"

    config = get_config()

    # Collect the audio paths generated this pass, in order, from the DB.
    from gnl_core.db import get_db
    article_ids = []
    for it in items:
        ids = it.identifier if isinstance(it.identifier, (tuple, list)) else [it.identifier]
        article_ids.extend(ids)
    if not article_ids:
        return None

    with get_db() as conn:
        placeholders = ','.join('?' * len(article_ids))
        rows = conn.execute(
            f"SELECT DISTINCT audio_path FROM saved_articles "
            f"WHERE id IN ({placeholders}) AND audio_path IS NOT NULL AND audio_path != ''",
            article_ids,
        ).fetchall()
    audio_paths = [r['audio_path'] for r in rows if os.path.exists(r['audio_path'])]
    # Preserve batch order (sorted by filename timestamp)
    audio_paths = sorted(set(audio_paths))
    if not audio_paths:
        if on_progress:
            on_progress("  ⚠ Finalize: aucun audio de batch trouvé")
        return None

    backlog_dir = os.path.join(config.get('GNL_BACKLOG', ''), 'saved-articles', 'linkedin')
    # Ensure the Drive is really accessible before writing (self-heal zombie mount).
    try:
        from gnl_core.drive import ensure_drive, DRIVE_MOUNT
        if backlog_dir.startswith(DRIVE_MOUNT) and not ensure_drive(on_progress=on_progress):
            if on_progress:
                on_progress("  ⚠ Finalize: Drive inaccessible — livraison impossible")
            return None
    except Exception:
        pass
    os.makedirs(backlog_dir, exist_ok=True)
    final_date = datetime.now().strftime('%Y-%m-%d')
    output_file = os.path.join(backlog_dir, f"batch-{final_date}.mp3")
    counter = 1
    while os.path.exists(output_file):
        counter += 1
        output_file = os.path.join(backlog_dir, f"batch-{final_date}-{counter}.mp3")

    import tempfile
    silence_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'silence-3s.mp3'
    )
    concat_path = os.path.join(tempfile.gettempdir(), f'nlm_finalize_{final_date}.txt')
    with open(concat_path, 'w') as f:
        for idx, p in enumerate(audio_paths):
            f.write(f"file '{p}'\n")
            if idx < len(audio_paths) - 1 and os.path.exists(silence_file):
                f.write(f"file '{silence_file}'\n")
    subprocess.run(
        ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_path, '-c', 'copy', output_file],
        capture_output=True,
    )
    try:
        os.unlink(concat_path)
    except Exception:
        pass

    if os.path.exists(output_file):
        if on_progress:
            on_progress(f"  ✓ Combiné sur Drive: {output_file}")
        return output_file
    if on_progress:
        on_progress("  ⚠ Combine échoué")
    return None


def make_finalize_fn(on_progress=None):
    """Return finalize_fn(category, items) -> output_path | None for the orchestrator."""
    def finalize(category, items):
        return finalize_category(category, items, on_progress=on_progress)
    return finalize
