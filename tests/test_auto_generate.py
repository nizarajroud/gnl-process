"""Unit tests for gnl_core.auto_generate — orchestrator decision logic.

Zero quota consumption: all dependencies are injected mocks.
"""
import pytest

from gnl_core.auto_generate import (
    run_auto_generation, build_work_queue, WorkItem,
    MAX_CONSECUTIVE_FAILURES,
)
from gnl_core.quota import SessionExpiredError


# --- Fixtures / helpers ---

DEFAULTS = {
    "exams/sap-c02": {"enabled": True, "priority": 1},
    "saved-articles/linkedin": {"enabled": True, "priority": 2},
    "aws/aws-papers": {"enabled": True, "priority": 3},
    "misc/projects": {"enabled": False, "priority": 7},  # disabled
}


def make_pending(mapping):
    """mapping: {category: [identifiers]} -> list_pending_fn"""
    def _fn(category, cfg):
        return mapping.get(category, [])
    return _fn


def always_budget(status, min_percent=1):
    return True


def never_budget(status, min_percent=1):
    return False


def ok_status():
    return {"ok": True, "window_5h": {"percent_remaining": 100}, "window_weekly": {"percent_remaining": 100}}


# --- build_work_queue ---

def test_queue_skips_disabled_categories():
    pending = make_pending({"exams/sap-c02": ["e1"], "misc/projects": ["p1"]})
    queue = build_work_queue(DEFAULTS, pending)
    cats = {w.category for w in queue}
    assert "misc/projects" not in cats
    assert "exams/sap-c02" in cats


def test_queue_ordered_by_priority():
    pending = make_pending({
        "aws/aws-papers": ["a1"],
        "exams/sap-c02": ["e1"],
        "saved-articles/linkedin": ["l1"],
    })
    queue = build_work_queue(DEFAULTS, pending)
    assert [w.category for w in queue] == [
        "exams/sap-c02",           # priority 1
        "saved-articles/linkedin", # priority 2
        "aws/aws-papers",          # priority 3
    ]


def test_queue_empty_when_no_pending():
    queue = build_work_queue(DEFAULTS, make_pending({}))
    assert queue == []


# --- run_auto_generation: happy path ---

def test_generates_all_when_budget_available():
    pending = make_pending({"exams/sap-c02": ["e1", "e2"]})
    generated_calls = []
    def gen(item):
        generated_calls.append(item.identifier)
        return True
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=pending,
        quota_status_fn=ok_status,
        has_budget_fn=always_budget,
        generate_fn=gen,
    )
    assert report.stopped_reason == "completed"
    assert len(report.generated) == 2
    assert generated_calls == ["e1", "e2"]


# --- no budget ---

def test_stops_immediately_when_no_budget():
    pending = make_pending({"exams/sap-c02": ["e1"]})
    gen_called = []
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=pending,
        quota_status_fn=ok_status,
        has_budget_fn=never_budget,
        generate_fn=lambda i: gen_called.append(i) or True,
        next_recharge_fn=lambda s: "2026-09-16 12:00 EDT",
    )
    assert report.stopped_reason == "no_budget"
    assert report.generated == []
    assert gen_called == []
    assert report.next_recharge == "2026-09-16 12:00 EDT"


def test_stops_mid_queue_when_budget_runs_out():
    pending = make_pending({"exams/sap-c02": ["e1", "e2", "e3"]})
    # Budget available for first 2 checks, then exhausted
    calls = {"n": 0}
    def budget(status, min_percent=1):
        calls["n"] += 1
        return calls["n"] <= 2  # first 2 checks pass
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=pending,
        quota_status_fn=ok_status,
        has_budget_fn=budget,
        generate_fn=lambda i: True,
    )
    assert report.stopped_reason == "no_budget"
    assert len(report.generated) == 1  # only e1 generated (check1=initial, check2=e1 ok, check3=stop)


# --- session expired ---

def test_session_expired_stops_cleanly():
    def raise_expired():
        raise SessionExpiredError("code 16")
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=make_pending({"exams/sap-c02": ["e1"]}),
        quota_status_fn=raise_expired,
        has_budget_fn=always_budget,
        generate_fn=lambda i: True,
    )
    assert report.stopped_reason == "session_expired"
    assert report.generated == []


# --- no material ---

def test_no_material():
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=make_pending({}),
        quota_status_fn=ok_status,
        has_budget_fn=always_budget,
        generate_fn=lambda i: True,
    )
    assert report.stopped_reason == "no_material"


# --- circuit breaker ---

def test_circuit_breaker_after_consecutive_failures():
    pending = make_pending({"exams/sap-c02": [f"e{i}" for i in range(10)]})
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=pending,
        quota_status_fn=ok_status,
        has_budget_fn=always_budget,
        generate_fn=lambda i: False,  # always fail
    )
    assert report.stopped_reason == "circuit_breaker"
    assert len(report.failed) == MAX_CONSECUTIVE_FAILURES


def test_failures_reset_on_success():
    pending = make_pending({"exams/sap-c02": ["e1", "e2", "e3", "e4", "e5"]})
    # Fail, fail, succeed (resets), fail, fail — should NOT trip breaker
    results = iter([False, False, True, False, False])
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=pending,
        quota_status_fn=ok_status,
        has_budget_fn=always_budget,
        generate_fn=lambda i: next(results),
    )
    assert report.stopped_reason == "completed"
    assert len(report.generated) == 1
    assert len(report.failed) == 4


# --- dry run ---

def test_dry_run_does_not_call_generate():
    pending = make_pending({"exams/sap-c02": ["e1", "e2"]})
    gen_called = []
    report = run_auto_generation(
        category_defaults=DEFAULTS,
        list_pending_fn=pending,
        quota_status_fn=ok_status,
        has_budget_fn=always_budget,
        generate_fn=lambda i: gen_called.append(i) or True,
        dry_run=True,
    )
    assert report.dry_run is True
    assert gen_called == []            # generate never called
    assert len(report.generated) == 2  # but planned items reported
