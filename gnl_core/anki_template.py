"""Empty 'reflection template' image for Anki cards (one per question).

Each card gets a blank template the user fills in by hand while reasoning about
the question: dark panel, orange left bar, a Bedrock-generated title
'Q{num} · <concept>', empty Internet/On-premise + AWS zones, and three empty
boxes (Func. Req. | Non-Func. Req. | Constraints).

The title concept is produced by the EXISTING poster._items_exam() (Bedrock),
so we don't duplicate prompt logic. TEST_MODE renders without any AWS call.
"""
import os
import re
from pathlib import Path

_BG = (20, 24, 33)
_CARD = (30, 36, 48)
_ORANGE = (255, 153, 0)
_WHITE = (240, 242, 245)
_DARK = (20, 24, 33)


def _is_test_mode():
    return os.getenv('TEST_MODE', '0') == '1'


def _font(size, bold=True):
    from PIL import ImageFont
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    for p in (f'/usr/share/fonts/truetype/dejavu/{name}',):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_template(title, out_png, size=(1240, 760)):
    """Render ONE empty template PNG with `title` at the top. Returns out_png."""
    from PIL import Image, ImageDraw
    W, H = size
    img = Image.new('RGB', (W, H), _BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([30, 30, W - 30, H - 30], radius=18, fill=_CARD)
    d.rounded_rectangle([55, 70, 80, H - 70], radius=8, fill=_ORANGE)
    # Title (truncate very long titles to keep one line)
    t = (title or '').strip()
    tf = _font(44)
    while d.textlength(t, font=tf) > (W - 180) and len(t) > 8:
        t = t[:-2]
    d.text((110, 80), t, font=tf, fill=_WHITE)
    # Inner white panel
    px, py, pw, ph = 110, 170, W - 170, H - 210
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=14, fill=(255, 255, 255))
    d.text((px + 90, py + 20), 'Internet', font=_font(30), fill=_DARK)
    d.text((px + pw - 260, py + 20), 'AWS', font=_font(30), fill=_DARK)
    d.line([(px + pw // 2, py + 70), (px + pw // 2, py + ph - 150)], fill=_DARK, width=4)
    d.rectangle([px + 50, py + 80, px + 320, py + 150], outline=(120, 120, 120), width=2)
    d.text((px + 95, py + 100), 'On-premise\n  Datacenter', font=_font(20), fill=_DARK)
    by = py + ph - 110
    bw = (pw - 120) // 3
    for i, lab in enumerate(['Func. Req.', 'Non-Func. Req.', 'Constraints']):
        bx = px + 30 + i * (bw + 15)
        d.rectangle([bx, by, bx + bw, by + 70], outline=_DARK, width=2)
        tw = d.textlength(lab, font=_font(22))
        d.text((bx + (bw - tw) // 2, by + 22), lab, font=_font(22), fill=_DARK)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return out_png


def _titles_for_questions(md_path, answers):
    """Return {num: 'Q{num} · <concept>'} using the existing Bedrock labeler.

    Falls back to 'Q{num}' if Bedrock yields nothing. TEST_MODE -> no AWS call.
    """
    nums = sorted(answers.keys(), key=lambda x: int(x))
    titles = {n: f"Q{n}" for n in nums}
    if _is_test_mode():
        return {n: f"Q{n} · Test Concept" for n in nums}
    try:
        from gnl_core.poster import _items_exam
        items = _items_exam(str(md_path)) or []
        # items are like 'Q3 · KMS key deletion alert' — map by leading Q number.
        for it in items:
            m = re.match(r'\s*Q\s*(\d+)\s*·\s*(.*)', it)
            if m:
                n, label = m.group(1), m.group(2).strip()
                if n in titles:
                    titles[n] = f"Q{n} · {label}" if label else f"Q{n}"
    except Exception:
        pass
    return titles


def generate_question_templates(md_path, answers, out_dir, on_progress=None):
    """Render one template PNG per question. Returns {num: png_path}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    titles = _titles_for_questions(md_path, answers)
    result = {}
    for num in sorted(answers.keys(), key=lambda x: int(x)):
        png = out / f"template_Q{num}.png"
        render_template(titles.get(num, f"Q{num}"), str(png))
        result[num] = str(png)
        if on_progress:
            on_progress(f"  🖼 template Q{num}: {titles.get(num, '')}")
    return result
