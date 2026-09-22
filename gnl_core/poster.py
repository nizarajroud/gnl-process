"""Episode posters + PDF booklet for combined podcasts.

When episodes are combined into one MP3, this builds a companion PDF where each
page is the poster of one episode, in combination order, with a timecode footer
(e.g. "Épisode 3/10 · 12:40 → 18:05"). Read the PDF alongside the audio in a
player like Documents by Readdle to follow along, turning pages per episode.

Poster CONTENT is category-aware (a "provider" per category decides its source):
  - aws/aws-whats-new : news titles from the PDF chunk (Bedrock)
  - exams/*           : "Q{n} · <2-4 word problem>" from the .md chunk (Bedrock)
  - default           : news-style extraction from chunk text

Layout is portrait, 2-column cards (reuses coverart rendering primitives).
Respects TEST_MODE (no Bedrock / no real render).
"""

import os
import re
import json
from pathlib import Path


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


# --- Category content providers -------------------------------------------------

def poster_items(category, chunk_path):
    """Return the list of short strings to show on this episode's poster.

    Routes by category to the right source/extraction. Never raises.
    """
    try:
        if category == 'aws/aws-whats-new':
            return _items_whatsnew(chunk_path)
        theme = category.partition('/')[0]
        if theme == 'exams':
            return _items_exam(chunk_path)
        # default: treat chunk as generic text, extract news-style titles
        return _items_generic(chunk_path)
    except Exception:
        return []


def _read_pdf_text(path, limit=8000):
    if not path or not os.path.exists(path):
        return ""
    text = ""
    try:
        from PyPDF2 import PdfReader
        for page in PdfReader(path).pages:
            text += (page.extract_text() or "") + "\n"
            if len(text) > limit:
                break
    except Exception:
        pass
    return text


def _items_whatsnew(chunk_path):
    from gnl_core.coverart import extract_news_titles
    return extract_news_titles(_read_pdf_text(chunk_path))


def _items_generic(chunk_path):
    from gnl_core.coverart import extract_news_titles
    # chunk may be .md/.txt or .pdf
    if chunk_path and chunk_path.lower().endswith(('.md', '.txt')) and os.path.exists(chunk_path):
        text = Path(chunk_path).read_text(encoding='utf-8', errors='ignore')
    else:
        text = _read_pdf_text(chunk_path)
    return extract_news_titles(text)


def _items_exam(chunk_path):
    """For an exam chunk (.md with '## Question N:' blocks), return one label per
    question: 'Q{n} · <2-4 word problem>'. The problem is the essence of the
    question (what to solve), NOT the constraints/requirements.
    """
    if _is_test_mode():
        return ["Q1 · Test Problem", "Q2 · Sample Case"]
    if not chunk_path or not os.path.exists(chunk_path):
        return []
    md = Path(chunk_path).read_text(encoding='utf-8', errors='ignore')

    # Split into question blocks by "## Question N:"
    parts = re.split(r'##\s*Question\s+(\d+)\s*:', md)
    blocks = []  # (qnum, text)
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            blocks.append((parts[i].strip(), parts[i + 1].strip()))
    if not blocks:
        return []

    import boto3
    from gnl_core.config import get_config
    config = get_config()
    model_id = config.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-6')
    region = config.get('BEDROCK_REGION', 'us-east-1')
    client = boto3.client('bedrock-runtime', region_name=region)

    # One grouped call: give all question stems, get a 2-4 word problem label each.
    joined = "\n\n".join(f"Q{n}: {t[:600]}" for n, t in blocks)
    prompt = (
        "For each exam question below, output a 2 to 4 word label capturing the "
        "CORE problem to solve (the scenario's goal), NOT the constraints or the "
        "answer. Return ONLY a JSON array of strings, in order, one per question.\n\n"
        f"{joined}"
    )
    try:
        resp = client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        out = json.loads(resp['body'].read())['content'][0]['text'].strip()
        m = re.search(r'\[[\s\S]*\]', out)
        labels = json.loads(m.group(0)) if m else []
    except Exception:
        labels = []

    items = []
    for idx, (qnum, _) in enumerate(blocks):
        label = labels[idx].strip() if idx < len(labels) and isinstance(labels[idx], str) else ""
        items.append(f"Q{qnum} · {label}" if label else f"Q{qnum}")
    return items


# --- Poster rendering (portrait) ------------------------------------------------

def render_poster(items, episode_no, total, timecode, out_png, size=(1240, 1748)):
    """Render one portrait poster: 2-column cards + footer 'Épisode n/total · timecode'.

    Reuses coverart's card grid, reserving a footer band. TEST_MODE writes a stub.
    """
    if _is_test_mode():
        with open(out_png, 'wb') as f:
            f.write(b'\x89PNG\r\n')
        return out_png

    from PIL import Image, ImageDraw, ImageFont
    W, H = size
    footer_h = 90
    bg = (13, 17, 23)

    # Render the cards into the area above the footer using coverart's renderer,
    # then paste + draw the footer. We render at (W, H-footer_h) then compose.
    from gnl_core.coverart import render_cover
    cards_png = out_png + '.cards.png'
    render_cover('', items, cards_png, size=(W, H - footer_h))

    img = Image.new('RGB', (W, H), bg)
    try:
        cards = Image.open(cards_png)
        img.paste(cards, (0, 0))
    except Exception:
        pass
    finally:
        try:
            os.unlink(cards_png)
        except Exception:
            pass

    draw = ImageDraw.Draw(img)
    fpath = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(fpath, 40) if os.path.exists(fpath) else ImageFont.load_default()
    footer = f"Épisode {episode_no}/{total}"
    if timecode:
        footer += f"  ·  {timecode}"
    draw.rectangle([0, H - footer_h, W, H], fill=(255, 153, 0))
    bbox = draw.textbbox((0, 0), footer, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - footer_h + (footer_h - (bbox[3] - bbox[1])) // 2 - bbox[1]),
              footer, font=font, fill=(13, 17, 23))

    img.save(out_png, 'PNG')
    return out_png


def _fmt_ts(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _episode_durations(mp3_files):
    """Return list of durations (seconds) for each mp3 via ffprobe (0 on failure)."""
    import subprocess
    durs = []
    for f in mp3_files:
        try:
            out = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', str(f)],
                capture_output=True, text=True, timeout=60)
            durs.append(float(out.stdout.strip() or 0))
        except Exception:
            durs.append(0.0)
    return durs


def build_episode_pdf(category, ordered_chunks, ordered_mp3s, out_pdf, on_progress=None):
    """Build the companion PDF: one poster page per episode, in order, with timecodes.

    Args:
        category: e.g. 'aws/aws-whats-new'
        ordered_chunks: list of chunk file paths (source text per episode), in order
        ordered_mp3s: list of per-episode mp3 paths, in order (for durations)
        out_pdf: output PDF path
    Returns out_pdf on success, None otherwise. Best-effort; never raises.
    """
    try:
        total = len(ordered_chunks)
        if total == 0:
            return None

        if _is_test_mode():
            # Write a tiny stub PDF-like file (no real rendering)
            with open(out_pdf, 'wb') as f:
                f.write(b'%PDF-1.4\n% test\n')
            return out_pdf

        durations = _episode_durations(ordered_mp3s) if ordered_mp3s else [0.0] * total

        from PIL import Image
        tmp_pngs = []
        cumulative = 0.0
        for i, chunk in enumerate(ordered_chunks):
            items = poster_items(category, chunk)
            start = cumulative
            dur = durations[i] if i < len(durations) else 0.0
            end = cumulative + dur
            cumulative = end
            timecode = f"{_fmt_ts(start)} → {_fmt_ts(end)}" if dur else ""
            png = f"{out_pdf}.p{i+1}.png"
            render_poster(items, i + 1, total, timecode, png)
            tmp_pngs.append(png)
            if on_progress:
                on_progress(f"  📄 Poster {i+1}/{total} ({len(items)} items)")

        pages = [Image.open(p).convert('RGB') for p in tmp_pngs if os.path.exists(p)]
        if not pages:
            return None
        pages[0].save(out_pdf, save_all=True, append_images=pages[1:])
        for p in tmp_pngs:
            try:
                os.unlink(p)
            except Exception:
                pass
        if on_progress:
            on_progress(f"  📕 Livret PDF: {out_pdf} ({len(pages)} pages)")
        return out_pdf
    except Exception as e:
        if on_progress:
            on_progress(f"  ⚠ Livret PDF échoué: {str(e)[:60]}")
        return None
