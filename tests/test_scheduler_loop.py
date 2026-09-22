"""Regression test for the scheduler event-loop bug.

APScheduler runs jobs in worker threads that have no current event loop.
_scheduled_auto_generate must NOT raise 'There is no current event loop'
in that context (bug seen in prod at the 06:00 pass).
"""
import threading


def test_scheduled_auto_generate_no_loop_thread(monkeypatch):
    # Import inside test so app import happens under test env
    from gnl_core.web import app as appmod

    # Ensure no captured main loop and simulate worker-thread (no running loop)
    monkeypatch.setattr(appmod, '_MAIN_LOOP', None)

    errors = []

    def worker():
        try:
            # In a fresh thread there is no event loop; the function must
            # handle this gracefully (return early), not raise.
            appmod._scheduled_auto_generate()
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=10)

    assert not errors, f"scheduled job raised in no-loop thread: {errors}"


def test_get_main_loop_returns_none_without_loop(monkeypatch):
    from gnl_core.web import app as appmod
    monkeypatch.setattr(appmod, '_MAIN_LOOP', None)
    result = {}

    def worker():
        # get_event_loop() raises in a bare thread on 3.12+, helper must swallow
        result['loop'] = appmod._get_main_loop()

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=5)
    # Either None or a loop, but never an exception escaping
    assert 'loop' in result
