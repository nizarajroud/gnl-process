"""Tests for the Meta Topics module (persistent Doc→Meta library)."""
import os
import tempfile
import pytest

from gnl_core import topics


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv('INBOX_FOLDER', str(tmp_path / 'inbox'))
    return str(tmp_path / 'topics.db')


def test_create_and_list(db):
    tid = topics.create_topic('Topic A', db_path=db)
    assert tid > 0
    lst = topics.list_topics(db_path=db)
    assert len(lst) == 1 and lst[0]['title'] == 'Topic A' and lst[0]['sources'] == 0


def test_add_sources_and_detail(db):
    tid = topics.create_topic('T', db_path=db)
    topics.add_file_source(tid, 'cours.txt', content=b'file body content', db_path=db)
    topics.add_link_source(tid, 'https://x.com/a', db_path=db)
    sid = topics.add_text_source(tid, 'hello pasted', label='N1', db_path=db)
    d = topics.get_topic(tid, db_path=db)
    kinds = sorted(s['type'] for s in d['sources'])
    assert kinds == ['file', 'link', 'text']
    # file & link have no stored_path; text has a saved .txt
    txt = [s for s in d['sources'] if s['type'] == 'text'][0]
    assert txt['stored_path'] and os.path.exists(txt['stored_path'])
    assert open(txt['stored_path']).read() == 'hello pasted'
    # journal recorded each action
    actions = [l['action'] for l in d['log']]
    assert 'created' in actions and actions.count('source_added') == 3


def test_rename_and_remove(db):
    tid = topics.create_topic('Old', db_path=db)
    sid = topics.add_text_source(tid, 'content', db_path=db)
    path = [s['stored_path'] for s in topics.get_topic(tid, db_path=db)['sources']][0]
    topics.rename_topic(tid, 'New', db_path=db)
    topics.remove_source(tid, sid, db_path=db)
    d = topics.get_topic(tid, db_path=db)
    assert d['title'] == 'New'
    assert len(d['sources']) == 0
    assert not os.path.exists(path)  # .txt removed
    assert any(l['action'] == 'renamed' for l in d['log'])
    assert any(l['action'] == 'source_removed' for l in d['log'])


def test_delete_topic(db):
    tid = topics.create_topic('ToDelete', db_path=db)
    topics.add_file_source(tid, 'f.txt', content=b'x', db_path=db)
    topics.delete_topic(tid, db_path=db)
    assert topics.get_topic(tid, db_path=db) is None
    assert topics.list_topics(db_path=db) == []


def test_get_missing_topic(db):
    assert topics.get_topic(9999, db_path=db) is None


def test_ensure_schema_idempotent(db):
    topics.ensure_schema(db)
    topics.ensure_schema(db)  # second call must not fail
    assert topics.list_topics(db_path=db) == []


def test_generate_topic_markdown_plan_b(tmp_path):
    """Plan B: writes the whole corpus as one .md into the iCloud dir."""
    import os
    from gnl_core import topics as T
    db = str(tmp_path / "pb.db")
    icloud = tmp_path / "icloud"
    tid = T.create_topic("Mon Topic PlanB", db_path=db)
    T.add_text_source(tid, "Un contenu de test suffisant. " * 20, db_path=db)
    res = T.generate_topic_markdown(tid, icloud_dir=str(icloud), db_path=db)
    assert os.path.exists(res["path"])
    assert res["path"].endswith(".md")
    content = open(res["path"], encoding="utf-8").read()
    assert "Un contenu de test" in content          # corpus included
    assert res["chars"] == len(content)
    assert "Mon Topic PlanB" == res["name"]
