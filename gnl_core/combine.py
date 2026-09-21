"""Combine MP3 files into final podcast."""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .db import get_records, resolve_parent, get_db


def combine(parent_id, output_file, db_path=None, suffix=None):
    """Combine all converted mp3s into one file. Returns output path or None."""
    test_mode = os.getenv('TEST_MODE', '0') == '1'
    records = get_records(parent_id, db_path, conversion_state=1)
    if not records:
        return None

    _, _, theme, subfolder = resolve_parent(parent_id, db_path)
    audio_parts_folder = os.getenv('AUDIO_PARTS_FOLDER', '')
    gnl_backlog = os.getenv('GNL_BACKLOG', '')
    default_speed = float(os.getenv('DEFAULT_SPEED', '1'))

    parent_file = records[0]['parent_file']
    audio_dir = Path(audio_parts_folder) / theme / subfolder / parent_file

    mp3_files = [audio_dir / f"{rec['podcast_name']}.mp3" for rec in records if (audio_dir / f"{rec['podcast_name']}.mp3").exists()]
    if not mp3_files:
        return None

    mp3_files.sort(key=lambda f: int(re.search(r'\d+', f.stem).group()) if re.search(r'\d+', f.stem) else 0)

    if not output_file.endswith('.mp3'):
        output_file = f"{output_file}.mp3"

    # Add part suffix if partial
    if suffix:
        output_file = output_file.replace('.mp3', f'-part{suffix}.mp3')

    output_dir = Path(gnl_backlog) / theme / subfolder
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_file

    # Remove any partial files with same base name
    base_name = output_file.replace('.mp3', '')
    for existing in output_dir.glob(f"{base_name}-part*.mp3"):
        existing.unlink()
    if output_path.exists():
        output_path.unlink()

    if test_mode:
        with open(output_path, 'wb') as f:
            f.write(b'\x00' * 2048)
    else:
        if default_speed != 1:
            adjusted = []
            for f in mp3_files:
                adj = audio_dir / f"adjusted_{f.name}"
                subprocess.run(['ffmpeg', '-y', '-i', str(f), '-filter:a', f'atempo={default_speed}', str(adj)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                adjusted.append(adj)
            mp3_files = adjusted

        local_tmp = Path(tempfile.gettempdir()) / output_file
        list_file = Path(tempfile.gettempdir()) / "concat_list.txt"
        with open(list_file, 'w') as f:
            for mp3 in mp3_files:
                f.write(f"file '{mp3.absolute()}'\n")

        subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c', 'copy', str(local_tmp)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        list_file.unlink()

        shutil.copyfile(str(local_tmp), str(output_path))
        local_tmp.unlink()

        if default_speed != 1:
            for f in mp3_files:
                if f.name.startswith("adjusted_"):
                    f.unlink()

    # Mark parent as combined only if full (no suffix = complete)
    if not suffix:
        with get_db(db_path) as conn:
            conn.execute("UPDATE parent_configuration SET combination_state = 1 WHERE id = ?", (parent_id,))
            conn.commit()

    # Dynamic cover art (aws/aws-whats-new only) — best-effort, never blocks delivery.
    category = f"{theme}/{subfolder}"
    if not test_mode:
        try:
            from .coverart import add_cover_for_whatsnew, COVER_CATEGORY
            if category == COVER_CATEGORY:
                # Gather source text from the split chunks for this parent.
                # Chunks are PDFs (p1.pdf, p2.pdf, ...) produced by split().
                pdf_parts_folder = os.getenv('PDF_PARTS_FOLDER', '')
                parts_dir = Path(pdf_parts_folder) / theme / subfolder / parent_file
                source_text = ""
                if parts_dir.is_dir():
                    try:
                        from PyPDF2 import PdfReader
                        pdfs = sorted(
                            parts_dir.glob("*.pdf"),
                            key=lambda f: int(re.search(r'\d+', f.stem).group()) if re.search(r'\d+', f.stem) else 0,
                        )
                        for pdf in pdfs:
                            try:
                                reader = PdfReader(str(pdf))
                                for page in reader.pages:
                                    source_text += (page.extract_text() or "") + "\n"
                            except Exception:
                                pass
                            if len(source_text) > 8000:
                                break  # enough context for title extraction
                    except Exception:
                        pass
                    # Fallback: any .txt chunks (other pipelines)
                    if not source_text.strip():
                        for txt in sorted(parts_dir.glob("*.txt")):
                            try:
                                source_text += txt.read_text(encoding='utf-8', errors='ignore') + "\n"
                            except Exception:
                                pass
                episode_title = os.path.splitext(os.path.basename(output_file))[0]
                add_cover_for_whatsnew(category, str(output_path), source_text, episode_title)
        except Exception:
            pass  # cover art must never break the combine

    return str(output_path)
