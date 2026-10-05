"""Tests for the file-based agent job queue."""


def test_enqueue_list_done(tmp_path, monkeypatch):
    monkeypatch.setenv('GNL_JOBS_DIR', str(tmp_path / 'jobs'))
    import importlib
    from gnl_core import agent_jobs
    importlib.reload(agent_jobs)  # pick up GNL_JOBS_DIR
    j = agent_jobs.enqueue('video_deck', exam='Exam-1', failed_nums=[1, 2, 3])
    assert j['status'] == 'pending' and j['exam'] == 'Exam-1'
    pending = agent_jobs.list_jobs('pending')
    assert len(pending) == 1 and pending[0]['id'] == j['id']
    assert agent_jobs.mark_done(j['id'], result={'apkg': '/x.apkg'}) is True
    assert agent_jobs.list_jobs('pending') == []
    done = agent_jobs.list_jobs('done')
    assert len(done) == 1 and done[0]['result']['apkg'] == '/x.apkg'
