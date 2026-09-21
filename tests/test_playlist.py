"""Tests for gnl_core.playlist — playlist output mode.

TEST_MODE avoids ffmpeg/Bedrock; DB layer is monkeypatched.
"""
import os
import pytest
from pathlib import Path

from gnl_core import playlist as pl


@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    yield
    monkeypatch.delenv('TEST_MODE', raising=False)


def _setup(monkeypatch, tmp_path, records):
    """Wire folders + DB stubs. Creates source mp3s so copy path works."""
    audio = tmp_path / "audio"
    backlog = tmp_path / "backlog"
    monkeypatch.setenv('AUDIO_PARTS_FOLDER', str(audio))
    monkeypatch.setenv('GNL_BACKLOG', str(backlog))
    monkeypatch.setenv('PDF_PARTS_FOLDER', str(tmp_path / "parts"))

    theme, subfolder, parent_file = 'aws', 'aws-whats-new', 'whatsnew-test'
    src_dir = audio / theme / subfolder / parent_file
    src_dir.mkdir(parents=True)
    for r in records:
        (src_dir / f"{r['podcast_name']}.mp3").write_bytes(b'\x00' * 128)

    monkeypatch.setattr(pl, 'get_records', lambda pid, db=None, conversion_state=None: records)
    monkeypatch.setattr(pl, 'resolve_parent', lambda pid, db=None: (None, None, theme, subfolder))

    class _Conn:
        def execute(self, *a): return self
        def fetchone(self): return None
        def commit(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(pl, 'get_db', lambda db=None: _Conn())
    return backlog, theme, subfolder, parent_file


def _recs(n):
    return [{'podcast_name': f'p{i}', 'parent_file': 'whatsnew-test'} for i in range(1, n + 1)]


def test_playlist_creates_files_and_m3u(monkeypatch, tmp_path, test_mode):
    backlog, theme, sub, pf = _setup(monkeypatch, tmp_path, _recs(3))
    out = pl.make_playlist(1, 'whatsnew-test')
    assert out is not None
    out_dir = Path(out)
    mp3s = sorted(out_dir.glob("*.mp3"))
    assert len(mp3s) == 3
    assert (out_dir / "whatsnew-test.m3u").exists()


def test_playlist_files_numbered_in_order(monkeypatch, tmp_path, test_mode):
    _setup(monkeypatch, tmp_path, _recs(3))
    out = Path(pl.make_playlist(1, 'whatsnew-test'))
    names = sorted(p.name for p in out.glob("*.mp3"))
    assert names[0].startswith("01 - ")
    assert names[1].startswith("02 - ")
    assert names[2].startswith("03 - ")


def test_playlist_m3u_content(monkeypatch, tmp_path, test_mode):
    _setup(monkeypatch, tmp_path, _recs(2))
    out = Path(pl.make_playlist(1, 'whatsnew-test'))
    m3u = (out / "whatsnew-test.m3u").read_text()
    assert m3u.startswith("#EXTM3U")
    assert "#EXTINF:-1,01 - " in m3u
    assert m3u.count("#EXTINF") == 2


def test_playlist_orders_by_numeric_part(monkeypatch, tmp_path, test_mode):
    recs = [{'podcast_name': n, 'parent_file': 'whatsnew-test'} for n in ('p10', 'p2', 'p1')]
    _setup(monkeypatch, tmp_path, recs)
    out = Path(pl.make_playlist(1, 'whatsnew-test'))
    extinfs = [l for l in (out / "whatsnew-test.m3u").read_text().splitlines() if l.startswith("#EXTINF")]
    assert extinfs[0].endswith("p1")
    assert extinfs[1].endswith("p2")
    assert extinfs[2].endswith("p10")


def test_playlist_no_records_returns_none(monkeypatch, tmp_path, test_mode):
    _setup(monkeypatch, tmp_path, [])
    monkeypatch.setattr(pl, 'get_records', lambda pid, db=None, conversion_state=None: [])
    assert pl.make_playlist(1, 'x') is None


def test_safe_filename_strips_bad_chars():
    assert '/' not in pl._safe_filename('a/b:c*d')
    assert pl._safe_filename('') == 'episode'
