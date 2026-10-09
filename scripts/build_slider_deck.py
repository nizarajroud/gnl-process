#!/usr/bin/env python3
"""Build a single-card 'slider' video deck .apkg for an exam's questions.

ONE Anki card contains all questions. A tiny JS slider shows one architecture
image + plays its audio at a time, navigated ONLY by on-screen Prev/Next
buttons (no swipe → no accidental change at the gym). Lazy-load: a single
<img>/<audio> whose src changes on navigation, so the card opens instantly and
never preloads all media.

Usage: build_slider_deck.py <exam> <qnum1> <qnum2> ... [--subtheme=<slug>]
Media (QN.png, QN.mp3) must already exist in the video-assets/<exam>/ folder.
"""
import hashlib
import json
import os
import sys

import genanki

# Args: build_slider_deck.py <exam> <qnum...> [--subtheme=<slug>]
# The subtheme (certification slug, e.g. sap-c02 / saa-c03) selects the assets
# folder and the exam markdown. Defaults to sap-c02 to preserve existing usage.
_argv = sys.argv[1:]
SUBTHEME = "sap-c02"
_rest = []
for _a in _argv:
    if _a.startswith("--subtheme="):
        SUBTHEME = _a.split("=", 1)[1] or SUBTHEME
    else:
        _rest.append(_a)
EXAM = _rest[0]
QNUMS = _rest[1:]

BASE = (
    "/mnt/d/PERSONAL/SKILLS/Technical/GNL-PROCESS/Main-docs/exams/"
    f"{SUBTHEME}/assets"
)
VDIR = os.path.join(BASE, "Anki-generation", "video-assets", EXAM)
ANKI = os.path.join(BASE, "Anki-generation", "anki")


def _ver(path):
    """Short content hash → used to make the in-deck media name unique, so Anki
    never serves a stale cached file that happens to share the old name."""
    return hashlib.md5(open(path, "rb").read()).hexdigest()[:8]


# For each question, compute a CONTENT-VERSIONED media name. The file on disk
# stays QN.png / QN.mp3, but inside the deck it is referenced (and stored in the
# media map) as QN-<hash>.png / QN-<hash>.mp3. A changed file => new hash =>
# new name => Anki is forced to load the new version (fixes the "no change
# visible on device" caching problem).
items = []
media_map = {}  # disk_path -> in_deck_name
for q in QNUMS:
    png = os.path.join(VDIR, f"Q{q}.png")
    mp3 = os.path.join(VDIR, f"Q{q}.mp3")
    img_name = f"Q{q}-{_ver(png)}.png"
    aud_name = f"Q{q}-{_ver(mp3)}.mp3"
    items.append({"q": q, "img": img_name, "aud": aud_name})
    media_map[png] = img_name
    media_map[mp3] = aud_name
items_json = json.dumps(items)

# Load the question text (statement + options + explanation) per question from
# the exam markdown, so the Copy button can copy the full content of the shown
# question. Best-effort: empty if the source can't be parsed.
def _load_texts():
    try:
        import sys as _sys
        _sys.path.insert(0, "/mnt/d/PERSONAL/SKILLS/Technical/workspace/gnl-process")
        os.environ.setdefault("GNL_DB_PATH", "/home/nizar/.gnl-process-prod/gnl.db")
        from gnl_core.anki_review import _find_exam_markdown, parse_exam_questions
        md = _find_exam_markdown(EXAM, "exams", SUBTHEME)
        if not md:
            return {}
        q = parse_exam_questions(str(md))
        out = {}
        for n in QNUMS:
            qd = q.get(int(n))
            if qd:
                txt = f"Question {n}\n\n{qd.get('body','').strip()}"
                if qd.get("explanation"):
                    txt += f"\n\nExplanation:\n{qd['explanation'].strip()}"
                out[n] = txt
        return out
    except Exception:
        return {}

texts = _load_texts()

# Build the FULL Meta AI copy text per question, identical in shape to the
# classic exam-card Copy button: <voice prompt> + "\n\n---\n" + <body>.
# The video deck is a review deck (these are the user's failed questions), and
# it has no per-user answer state, so we use the WRONG voice prompt with
# MY_ANSWER = "not answered" and CORRECT = "see explanation below". QNUM is the
# question number. Prompts come from the dashboard config (same source as the
# classic button) with the exact same defaults as a fallback.
def _voice_prompt():
    _exam_label = SUBTHEME.upper()
    default_wrong_voice = (
        f"I'm studying for the AWS {_exam_label} exam. Here is a question I answered.\n"
        "My answer(s):\n{MY_ANSWER}\n"
        "Correct answer(s):\n{CORRECT}\n\n"
        "My answer was WRONG. For now, just RECEIVE and KEEP everything below in "
        "memory and reply ONLY \"OK, received \u2014 Question {QNUM}. Say 'go' when "
        "ready.\" Do NOT explain yet. Then, the moment I say ANYTHING (even just "
        "\"go\"), IMMEDIATELY give ONE complete spoken-style explanation \u2014 no "
        "further questions, no waiting: (1) why my option is wrong, (2) why the "
        "correct option(s) are right, (3) briefly why each other option is wrong. "
        "Plain, flowing, easy to listen to, no tables. (Question {QNUM})"
    )
    try:
        from gnl_core.config import get_config
        c = get_config()
        return c.get("META_PROMPT_WRONG_VOICE") or default_wrong_voice
    except Exception:
        return default_wrong_voice

_pw = _voice_prompt()


def _full_copy(qnum, body):
    preamble = (
        _pw.replace("{MY_ANSWER}", "not answered")
        .replace("{CORRECT}", "see explanation below")
        .replace("{QNUM}", str(qnum))
    )
    return preamble + "\n\n---\n" + body


copy_texts = {q: _full_copy(q, texts.get(q, "")) for q in QNUMS}

# Single-card front: slider UI. Prev/Next are real buttons in the top corners.
# One <img> + one <audio>; navigation only via buttons; audio plays on nav
# (user tap → iOS allows autoplay). Lazy: only current media is loaded.
slides = ""
import html as _html
for idx, it in enumerate(items):
    disp = "block" if idx == 0 else "none"
    qtext = _html.escape(copy_texts.get(it["q"], ""))
    slides += (
        f"<div class='gnlSlide' style='display:{disp};text-align:center;'>"
        f"<img src='{it['img']}' style='max-width:100%;'>"
        f"<audio class='gnlAud' src='{it['aud']}'></audio>"
        f"<textarea class='gnlTxt' style='display:none;'>{qtext}</textarea>"
        f"</div>"
    )

front = (
    "<div style='text-align:center;'>"
    "<div style='display:flex;justify-content:center;align-items:center;gap:10px;margin-bottom:6px;'>"
    "<button id='gnlPrev' type='button' style='background:#4b5563;color:#fff;border:none;"
    "padding:6px 12px;border-radius:8px;font-size:15px;cursor:pointer;'>&#9664;</button>"
    "<button id='gnlPlay' type='button' style='background:#059669;color:#fff;border:none;"
    "padding:6px 14px;border-radius:8px;font-size:15px;cursor:pointer;'>&#9654;&#65039;/&#9208;&#65039;</button>"
    "<button id='gnlNext' type='button' style='background:#4f46e5;color:#fff;border:none;"
    "padding:6px 12px;border-radius:8px;font-size:15px;cursor:pointer;'>&#9654;</button>"
    "<button id='gnlCopy' type='button' style='background:#4f46e5;color:#fff;border:none;"
    "padding:6px 12px;border-radius:8px;font-size:15px;cursor:pointer;'>&#128203; Copier</button>"
    "<span id='gnlCount' style='font-size:13px;color:#9ca3af;margin-left:8px;'></span>"
    "</div>"
    + slides +
    "<textarea id='gnlCopyArea' readonly style='position:absolute;left:-9999px;top:0;opacity:0;height:1px;width:1px;'></textarea>"
    "</div>"
    "<script>(function(){"
    "var slides=document.getElementsByClassName('gnlSlide');"
    "var n=slides.length;var i=0;"
    "var cnt=document.getElementById('gnlCount');"
    "function curAud(){return slides[i].getElementsByClassName('gnlAud')[0];}"
    "function stopAll(){Array.prototype.forEach.call(slides,function(s){var a=s.getElementsByClassName('gnlAud')[0];if(a){a.pause();}});}"
    "function show(play){"
    "Array.prototype.forEach.call(slides,function(s,k){s.style.display=(k===i)?'block':'none';});"
    "cnt.textContent=(i+1)+' / '+n;"
    "if(play){var a=curAud();if(a){try{a.play();}catch(e){}}}"
    "}"
    "document.getElementById('gnlPrev').addEventListener('click',function(){"
    "var j=Math.max(0,i-1);if(j!==i){stopAll();i=j;show(true);}});"
    "document.getElementById('gnlNext').addEventListener('click',function(){"
    "var j=Math.min(n-1,i+1);if(j!==i){stopAll();i=j;show(true);}});"
    "document.getElementById('gnlPlay').addEventListener('click',function(){"
    "var a=curAud();if(!a)return;if(a.paused){try{a.play();}catch(e){}}else{a.pause();}});"
    "document.getElementById('gnlCopy').addEventListener('click',function(){"
    "var t=slides[i].getElementsByClassName('gnlTxt')[0];if(!t)return;"
    "var area=document.getElementById('gnlCopyArea');area.value=t.value;"
    "area.style.position='static';area.style.opacity='1';area.focus();area.select();"
    "var ok=false;try{ok=document.execCommand('copy');}catch(e){ok=false;}"
    "if(!ok&&navigator.clipboard&&navigator.clipboard.writeText){try{navigator.clipboard.writeText(area.value);ok=true;}catch(e){}}"
    "area.style.position='absolute';area.style.left='-9999px';area.style.opacity='0';"
    "var b=document.getElementById('gnlCopy');b.textContent=ok?'\\u2705 Copi\\u00e9':'\\u26a0 R\\u00e9essaie';"
    "setTimeout(function(){b.innerHTML='&#128203; Copier';},1800);});"
    "show(false);"
    "})();</script>"
)

model = genanki.Model(
    1607392950, "GNL Video Slider",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Front}}"}],
)
deck = genanki.Deck(1990002001, f"{EXAM} — Video Slider (failed)")
deck.add_note(genanki.Note(model=model, fields=[front, EXAM],
                           guid=f"{EXAM}-video-slider"))
# genanki names media by basename; create versioned temp copies so the in-deck
# names match the hashed names referenced in the card (QN-<hash>.ext).
import shutil
import tempfile
tmpdir = tempfile.mkdtemp(prefix="gnl-slider-")
media = []
for disk_path, in_deck_name in media_map.items():
    dst = os.path.join(tmpdir, in_deck_name)
    shutil.copy2(disk_path, dst)
    media.append(dst)
pkg = genanki.Package(deck)
pkg.media_files = media
out = os.path.join(ANKI, f"{EXAM}-video.apkg")
pkg.write_to_file(out)
shutil.rmtree(tmpdir, ignore_errors=True)
print(f"  apkg: {out} ({os.path.getsize(out)} octets) — {len(items)} questions dans 1 carte slider")
