"""Amazon Polly TTS for Anki cards (optional, flag-gated).

Generates an MP3 for a piece of text using Amazon Polly (neural). Used by
step5_anki to embed audio in cards via [sound:...] tags. Disabled unless
ANKI_TTS=1. Uses a dedicated AWS profile (POLLY_PROFILE) so it can run on the
user's PERSONAL account, independent of the work profile.

Polly neural has a 3000-character limit per SynthesizeSpeech call, so long text
is split into chunks and the resulting MP3s are concatenated (MP3 frames can be
naively concatenated and still play).
"""
import os
import re
import html as _html

_POLLY_MAX = 2900  # keep under Polly's 3000-char neural limit, with margin


def _strip_html(text):
    """Turn card HTML into clean plain text suitable for TTS."""
    if not text:
        return ""
    t = re.sub(r'(?is)<(script|style|textarea).*?</\1>', ' ', text)
    t = t.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    t = re.sub(r'(?s)<[^>]+>', ' ', t)          # drop remaining tags
    t = _html.unescape(t)
    t = re.sub(r'[\u2605\u2691]', '', t)        # ★ ⚑ markers
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r' *\n *', '\n', t)              # trim spaces around newlines
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _chunks(text, size=_POLLY_MAX):
    """Split text into <=size pieces at sentence/line boundaries."""
    if len(text) <= size:
        return [text] if text else []
    out, buf = [], ""
    for piece in re.split(r'(\n|(?<=[.!?]) )', text):
        if len(buf) + len(piece) > size and buf:
            out.append(buf)
            buf = ""
        buf += piece
    if buf.strip():
        out.append(buf)
    return out


def _client(profile=None, region=None):
    import boto3
    profile = profile or os.getenv('POLLY_PROFILE') or None
    region = region or os.getenv('POLLY_REGION', 'us-east-1')
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client('polly', region_name=region)


def synthesize(text, out_path, voice=None, engine=None, profile=None,
               region=None):
    """Synthesize `text` to an MP3 at out_path. Returns out_path or None.

    Honors TEST_MODE (writes a tiny stub instead of calling AWS).
    """
    clean = _strip_html(text)
    if not clean:
        return None
    if os.getenv('TEST_MODE', '0') == '1':
        with open(out_path, 'wb') as f:
            f.write(b'\x00' * 64)      # stub mp3
        return out_path

    voice = voice or os.getenv('POLLY_VOICE', 'Matthew')
    engine = engine or os.getenv('POLLY_ENGINE', 'neural')
    client = _client(profile=profile, region=region)
    audio = b''
    for chunk in _chunks(clean):
        resp = client.synthesize_speech(
            Text=chunk, OutputFormat='mp3', VoiceId=voice, Engine=engine)
        audio += resp['AudioStream'].read()
    if not audio:
        return None
    with open(out_path, 'wb') as f:
        f.write(audio)
    return out_path
