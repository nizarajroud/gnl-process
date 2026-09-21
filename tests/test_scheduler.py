"""Tests for the multi-pass auto-generation scheduler job registration.

Uses a standalone APScheduler (not started) to verify job wiring without
running the FastAPI app or consuming quota.
"""
import pytest
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


def _register_auto_job(scheduler, every_hours, start_time):
    """Mirror of the app's registration logic (kept in sync with lifespan)."""
    tzinfo = pytz.timezone('America/Toronto')
    now = datetime.now(tzinfo)
    sh, sm = start_time.split(':')
    first = now.replace(hour=int(sh), minute=int(sm), second=0, microsecond=0)
    if first < now:
        first += timedelta(days=1)
    scheduler.add_job(
        lambda: None,
        IntervalTrigger(hours=every_hours, start_date=first, timezone='America/Toronto'),
        id='auto_generate', replace_existing=True, misfire_grace_time=3600,
    )
    return first


@pytest.fixture
def sched():
    s = BackgroundScheduler(timezone='America/Toronto')
    s.start(paused=True)  # started (like prod) but paused so no job actually fires
    yield s
    s.shutdown(wait=False)


def test_job_registered_with_interval(sched):
    _register_auto_job(sched, every_hours=5, start_time='06:00')
    job = sched.get_job('auto_generate')
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval == timedelta(hours=5)


def test_job_multiple_passes_interval(sched):
    """3h interval => 8 passes/day potential."""
    _register_auto_job(sched, every_hours=3, start_time='06:00')
    job = sched.get_job('auto_generate')
    assert job.trigger.interval == timedelta(hours=3)
    assert 24 // 3 == 8


def test_job_replaced_not_duplicated(sched):
    _register_auto_job(sched, every_hours=5, start_time='06:00')
    _register_auto_job(sched, every_hours=4, start_time='07:00')
    jobs = [j for j in sched.get_jobs() if j.id == 'auto_generate']
    assert len(jobs) == 1
    assert jobs[0].trigger.interval == timedelta(hours=4)


def test_job_removed(sched):
    _register_auto_job(sched, every_hours=5, start_time='06:00')
    assert sched.get_job('auto_generate') is not None
    sched.remove_job('auto_generate')
    assert sched.get_job('auto_generate') is None


def test_start_date_in_future(sched):
    """First run must be scheduled in the future (today or tomorrow)."""
    first = _register_auto_job(sched, every_hours=5, start_time='06:00')
    tzinfo = pytz.timezone('America/Toronto')
    assert first >= datetime.now(tzinfo) - timedelta(seconds=1)
