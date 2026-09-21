"""Playlist output mode (alternative to combine).

Instead of joining all episodes into one MP3, this delivers each episode as its
OWN file (kept separate), each with its OWN cover art, plus an .m3u playlist for
ordering. In a folder-as-playlist player (e.g. Documents by Readdle), the cover
changes as playback moves from one track to the next.

For aws/aws-whats-new, each episode's cover lists the news of THAT chunk
(Bedrock 2-word titles). Other categories get files copied + m3u without a
dynamic cover.

Respects TEST_MODE (no ffmpeg / Bedrock; deterministic).
"""

import os
import re
import shutil
from pathlib import Path

from .db import get_records, resolve_parent, get_db


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def _safe_filename(name):
    """Make a string safe for a filename (keep spaces, strip problem chars)."""
    name = re.sub(r'[\\/:*?"<>|]', '', name or '').strip()
    return name[:60] or 'episode'


def _chunk_text_for_record(theme, subfolder, parent_file, podcast_name):
    """Best-effort: read the source PDF chunk text for one episode.

    podcast_name maps to a chunk like 'p3'; the chunk PDF is p3.pdf under
    PDF_PARTS_FOLDER/theme/subfolder/parent_file/.
    """
    pdf_parts_folder = os.getenv('PDF_PARTS_FOLDER', '')
    parts_dir = Path(pdf_parts_folder) / theme / subfolder / parent_file
    if not parts_dir.is_dir():
        return ""
    # Try to find a chunk whose stem matches the episode number.
    m = re.search(r'\d+', podcast_name or '')
    candidates = []
    if m:
        n = m.group()
        candidates = [parts_dir / f"p{n}.pdf", parts_dir / f"{n}.pdf"]
    text = ""
    try:
        from PyPDF2 import PdfReader
        for c in candidates:
            if c.exists():
                for page in PdfReader(str(c)).pages:
                    text += (page.extract_text() or "") + "\n"
                break
    except Exception:
        pass
    return text


def make_playlist(parent_id, playlist_name=None, db_path=None):
    """Deliver episodes as separate files + an .m3u playlist.

    Returns the playlist directory path on success, None otherwise.
    """
    records = get_records(parent_id, db_path, conversion_state=1)
    if not records:
        return None

    _, _, theme, subfolder = resolve_parent(parent_id, db_path)
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    gnl_backlog = os.getenv('GNL_BACKLOG', '')

    parent_file = records[0]['parent_file']
    audio_dir = Path(audio_parts_folder) / theme / subfolder / parent_file

    # Order episodes by their numeric part (p1, p2, ...).
    def _order(rec):
        m = re.search(r'\d+', rec['podcast_name'] or '')
        return int(m.group()) if m else 0
    records = sorted(records, key=_order)

    name = playlist_name or parent_file
    out_dir = Path(gnl_backlog) / theme / subfolder / f"{name}-playlist"
    out_dir.mkdir(parents=True, exist_ok=True)

    from .coverart import add_cover_for_whatsnew, extract_news_titles, COVER_CATEGORY
    category = f"{theme}/{subfolder}"

    m3u_lines = ["#EXTM3U"]
    delivered = []
    for idx, rec in enumerate(records, start=1):
        src = audio_dir / f"{rec['podcast_name']}.mp3"
        if not src.exists():
            continue

        # Determine a readable title for this episode.
        title = rec['podcast_name']
        if not _is_test_mode() and category == COVER_CATEGORY:
            try:
                chunk_text = _chunk_text_for_record(theme, subfolder, parent_file, rec['podcast_name'])
                titles = extract_news_titles(chunk_text, max_titles=1) if chunk_text else []
                if titles:
                    title = titles[0]
            except Exception:
                pass

        fname = f"{idx:02d} - {_safe_filename(title)}.mp3"
        dst = out_dir / fname
        if _is_test_mode():
            dst.write_bytes(b'\x00' * 256)
        else:
            shutil.copyfile(str(src), str(dst))
            # Per-episode dynamic cover (aws-whats-new): titles of THIS chunk.
            if category == COVER_CATEGORY:
                try:
                    chunk_text = _chunk_text_for_record(theme, subfolder, parent_file, rec['podcast_name'])
                    add_cover_for_whatsnew(category, str(dst), chunk_text, f"{idx:02d} - {title}")
                except Exception:
                    pass

        m3u_lines.append(f"#EXTINF:-1,{idx:02d} - {title}")
        m3u_lines.append(fname)
        delivered.append(fname)

    if not delivered:
        return None

    (out_dir / f"{name}.m3u").write_text("\n".join(m3u_lines) + "\n", encoding='utf-8')

    # Mark parent combined (delivered) — same semantic as combine completion.
    with get_db(db_path) as conn:
        conn.execute("UPDATE parent_configuration SET combination_state = 1 WHERE id = ?", (parent_id,))
        conn.commit()

    return str(out_dir)
