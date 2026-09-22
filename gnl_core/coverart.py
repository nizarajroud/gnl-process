"""Dynamic cover art for AWS What's New episodes.

Each episode groups several AWS news. This module:
  1. extract_news_titles(text): asks Bedrock for a short (~2-word) title per news
  2. render_cover(episode_title, titles, out_png): draws a simple cover (Pillow)
  3. embed_cover(mp3_path, png_path, metadata): attaches cover + ID3 tags (ffmpeg)

Only used for the aws/aws-whats-new category. All functions respect TEST_MODE
(no Bedrock / no external calls; deterministic sentinels) so the pipeline stays
testable without cost.
"""

import os
import json
import subprocess


# Only this category gets dynamic cover art (per product decision).
COVER_CATEGORY = "aws/aws-whats-new"


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def extract_news_titles(text, max_titles=30):
    """Return a list of short titles, one per AWS news found in `text`.

    Extracts EVERY distinct announcement (not just the top few). Uses a single
    grouped Bedrock call. In TEST_MODE returns a deterministic stub.
    """
    if _is_test_mode():
        return ["Test News", "Sample Item"]

    if not text or not text.strip():
        return []

    import boto3
    from gnl_core.config import get_config
    config = get_config()
    model_id = config.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-6')
    region = config.get('BEDROCK_REGION', 'us-east-1')

    snippet = text[:8000]
    prompt = (
        "This text contains AWS 'What's New' announcements. List EVERY SINGLE "
        "distinct announcement/feature — do NOT skip any, do NOT summarize. "
        "For each, produce a concise title of 2 to 4 words (service + feature). "
        "Return ONLY a JSON array of strings, in the order they appear. No prose, "
        f"no limit below the actual count (up to {max_titles}).\n\nTEXT:\n{snippet}"
    )
    client = boto3.client('bedrock-runtime', region_name=region)
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    out = json.loads(resp['body'].read())['content'][0]['text'].strip()
    import re
    m = re.search(r'\[[\s\S]*\]', out)
    if not m:
        return []
    try:
        titles = json.loads(m.group(0))
    except Exception:
        return []
    # Normalize: strings, trimmed, non-empty, capped
    clean = []
    for t in titles:
        if isinstance(t, str) and t.strip():
            clean.append(t.strip()[:30])
    return clean[:max_titles]


def render_cover(episode_title, titles, out_png, size=(1400, 1400)):
    """Render a cover PNG as a 2-column grid of news cards, no header/title.

    The whole image is filled with cards (one per news). Card size and font
    scale adaptively so ALL news fit and occupy the space well.

    Returns out_png on success. In TEST_MODE, writes a tiny placeholder file.
    """
    if _is_test_mode():
        with open(out_png, 'wb') as f:
            f.write(b'\x89PNG\r\n')  # minimal sentinel header
        return out_png

    from PIL import Image, ImageDraw, ImageFont

    W, H = size
    bg = (13, 17, 23)          # dark slate
    card_bg = (22, 27, 34)     # slightly lighter card
    accent = (255, 153, 0)     # AWS orange (left bar of each card)
    fg = (233, 237, 243)

    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)

    def _font(sz, bold=True):
        path = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if os.path.exists(path):
            return ImageFont.truetype(path, sz)
        return ImageFont.load_default()

    items = [t for t in (titles or []) if t and t.strip()]
    if not items:
        img.save(out_png, 'PNG')
        return out_png

    # --- Layout: 2 columns, N rows. Fill the full canvas. ---
    margin = 40
    gap = 24
    cols = 2 if len(items) > 1 else 1
    rows = (len(items) + cols - 1) // cols

    grid_w = W - 2 * margin
    grid_h = H - 2 * margin
    card_w = (grid_w - (cols - 1) * gap) // cols
    card_h = (grid_h - (rows - 1) * gap) // rows

    # Adaptive font: fit BOTH card height and the widest title's width, so
    # titles are shown in full (no ellipsis) whenever possible.
    text_w_budget = card_w - (max(8, card_w // 40) + 24) - 20
    # Start from a height-based size, then shrink until the longest title fits width.
    font_sz = max(22, min(88, int(card_h * 0.40)))
    def _mk(sz):
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        return ImageFont.truetype(path, sz) if os.path.exists(path) else ImageFont.load_default()
    longest = max(items, key=len)
    font = _mk(font_sz)
    while font_sz > 22 and draw.textlength(longest, font=font) > text_w_budget:
        font_sz -= 2
        font = _mk(font_sz)

    def _wrap(text, max_w, max_lines=2):
        """Wrap text to <=max_lines lines within max_w; ellipsize last line if needed."""
        words = text.split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
                if len(lines) == max_lines:
                    break
        if cur and len(lines) < max_lines:
            lines.append(cur)
        # Ellipsize if content remains beyond max_lines
        if lines and draw.textlength(lines[-1], font=font) > max_w:
            s = lines[-1]
            while s and draw.textlength(s + "…", font=font) > max_w:
                s = s[:-1]
            lines[-1] = s + "…"
        return lines[:max_lines]

    bar_w = max(8, card_w // 40)
    text_pad = bar_w + 24

    for idx, title in enumerate(items):
        r = idx // cols
        c = idx % cols
        x0 = margin + c * (card_w + gap)
        y0 = margin + r * (card_h + gap)
        x1 = x0 + card_w
        y1 = y0 + card_h
        draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=card_bg)
        draw.rounded_rectangle([x0, y0, x0 + bar_w, y1], radius=6, fill=accent)
        lines = _wrap(title.strip(), card_w - text_pad - 20, max_lines=2)
        line_h = font_sz + 6
        block_h = line_h * len(lines)
        ty = y0 + (card_h - block_h) // 2
        for ln in lines:
            draw.text((x0 + text_pad, ty), ln, font=font, fill=fg)
            ty += line_h

    img.save(out_png, 'PNG')
    return out_png


def embed_cover(mp3_path, png_path, metadata=None):
    """Attach `png_path` as cover art to `mp3_path` (in place) + optional ID3 tags.

    metadata: dict with optional keys title/artist/album/date.
    Returns True on success. In TEST_MODE, no-op returns True.
    """
    if _is_test_mode():
        return True
    if not (os.path.exists(mp3_path) and os.path.exists(png_path)):
        return False

    metadata = metadata or {}
    tmp_out = mp3_path + '.cover.mp3'
    cmd = [
        'ffmpeg', '-y', '-i', mp3_path, '-i', png_path,
        '-map', '0:a', '-map', '1:v', '-c', 'copy', '-id3v2_version', '3',
        '-metadata:s:v', 'title=Album cover', '-metadata:s:v', 'comment=Cover (front)',
        '-disposition:v', 'attached_pic',
    ]
    for key in ('title', 'artist', 'album', 'date'):
        if metadata.get(key):
            cmd += ['-metadata', f'{key}={metadata[key]}']
    cmd.append(tmp_out)

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(tmp_out):
        os.replace(tmp_out, mp3_path)
        return True
    if os.path.exists(tmp_out):
        os.unlink(tmp_out)
    return False


def add_cover_for_whatsnew(category, mp3_path, source_text, episode_title, on_progress=None):
    """High-level entry: for aws-whats-new only, generate + embed a dynamic cover.

    Returns True if a cover was embedded, False otherwise (incl. other categories).
    Never raises — cover art is best-effort and must not break delivery.
    """
    if category != COVER_CATEGORY:
        return False
    try:
        titles = extract_news_titles(source_text)
        if not titles:
            if on_progress:
                on_progress("  ⚠ Cover: aucun titre extrait")
            return False
        png = mp3_path + '.cover.png'
        render_cover(episode_title, titles, png)
        ok = embed_cover(mp3_path, png, metadata={
            'title': episode_title, 'artist': "AWS What's New", 'album': "GNL",
        })
        try:
            if os.path.exists(png):
                os.unlink(png)
        except Exception:
            pass
        if on_progress:
            on_progress(f"  🖼️ Cover ajoutée ({len(titles)} news)" if ok else "  ⚠ Cover: embed échoué")
        return ok
    except Exception as e:
        if on_progress:
            on_progress(f"  ⚠ Cover échouée: {str(e)[:60]}")
        return False
