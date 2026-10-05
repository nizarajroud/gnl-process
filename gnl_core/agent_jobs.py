"""Agent job queue (file-based) for tasks that require the Kiro agent.

Some features (e.g. the 'video deck' of failed questions: AWS draw.io
architecture per question + narrated speech) need the AGENT's skills, not just
server code. The web button enqueues a job here; the agent later processes the
queue (reads jobs, does the work, marks them done).

Jobs are JSON files under JOBS_DIR:
  <JOBS_DIR>/<status>/<job_id>.json   where status in {pending, done}
Job schema:
  {id, type, exam, failed_nums, theme, subtheme, created_at, status}
"""
import json
import os
import time
import uuid
from pathlib import Path

JOBS_DIR = Path(os.environ.get(
    'GNL_JOBS_DIR',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.agent-jobs')))


def _dir(status):
    d = JOBS_DIR / status
    d.mkdir(parents=True, exist_ok=True)
    return d


def enqueue(job_type, **fields):
    """Create a pending job. Returns the job dict."""
    job = {
        'id': uuid.uuid4().hex[:12],
        'type': job_type,
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'status': 'pending',
    }
    job.update(fields)
    path = _dir('pending') / f"{job['id']}.json"
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
    return job


def list_jobs(status='pending'):
    """Return the list of jobs with the given status, oldest first."""
    out = []
    for p in sorted(_dir(status).glob('*.json')):
        try:
            out.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            pass
    return out


def mark_done(job_id, result=None):
    """Move a pending job to done, attaching an optional result. Returns bool."""
    src = _dir('pending') / f"{job_id}.json"
    if not src.exists():
        return False
    try:
        job = json.loads(src.read_text(encoding='utf-8'))
    except Exception:
        job = {'id': job_id}
    job['status'] = 'done'
    job['done_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    if result is not None:
        job['result'] = result
    (_dir('done') / f"{job_id}.json").write_text(
        json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
    src.unlink()
    return True
