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


def extract_news_titles(text, max_titles=12):
    """Return a list of short (~2-word) titles, one per AWS news found in `text`.

    Uses a single grouped Bedrock call (efficient). In TEST_MODE returns a
    deterministic stub without calling Bedrock.
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

    snippet = text[:6000]
    prompt = (
        "This text contains several AWS 'What's New' announcements. "
        "For EACH distinct announcement, produce a punchy title of AT MOST 2 words "
        "(service or feature name). Return ONLY a JSON array of strings, most "
        f"important first, max {max_titles} items. No prose.\n\nTEXT:\n{snippet}"
    )
    client = boto3.client('bedrock-runtime', region_name=region)
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
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
    """Render a simple cover PNG: solid background, episode title, bulleted titles.

    Returns out_png on success. In TEST_MODE, writes a tiny placeholder file.
    """
    if _is_test_mode():
        with open(out_png, 'wb') as f:
            f.write(b'\x89PNG\r\n')  # minimal sentinel header
        return out_png

    from PIL import Image, ImageDraw, ImageFont

    W, H = size
    bg = (13, 17, 23)        # dark slate
    accent = (255, 153, 0)   # AWS orange
    fg = (230, 236, 241)

    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)

    def _font(sz, bold=False):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for p in candidates:
            if os.path.exists(p):
                return ImageFont.truetype(p, sz)
        return ImageFont.load_default()

    # Header band
    draw.rectangle([0, 0, W, 200], fill=accent)
    draw.text((60, 60), "AWS What's New", font=_font(72, bold=True), fill=(13, 17, 23))

    # Episode subtitle
    draw.text((60, 240), episode_title[:40], font=_font(48, bold=True), fill=fg)

    # Bulleted list of news titles
    y = 360
    line_h = 90
    for t in titles[:12]:
        draw.ellipse([64, y + 20, 92, y + 48], fill=accent)
        draw.text((120, y), t, font=_font(52), fill=fg)
        y += line_h
        if y > H - line_h:
            break

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
