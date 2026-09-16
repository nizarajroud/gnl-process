"""Auto-generation orchestrator (Epic #43).

Consumes unprocessed material and generates podcasts automatically while
budget is available, respecting the compute-based quota model.

Designed with dependency injection so the decision logic can be unit-tested
without touching NLM/Bedrock or consuming any quota.

Core flow (per pass):
  1. Health-check: read quota (distinguish session-expired vs no-budget)
  2. If no budget -> stop cleanly, report next recharge
  3. Build work queue (unprocessed material) ordered by category priority
  4. Generate items while budget remains and circuit breaker not tripped
  5. Return a structured report
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class WorkItem:
    """One unit of material to convert to a podcast."""
    category: str          # e.g. "aws/aws-papers"
    identifier: str        # file name / article id / etc.
    priority: int          # lower = higher priority
    config: dict = field(default_factory=dict)  # per-category defaults


@dataclass
class GenerationReport:
    generated: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    stopped_reason: Optional[str] = None
    next_recharge: Optional[str] = None
    dry_run: bool = False


# Circuit breaker: stop a pass after this many consecutive failures
MAX_CONSECUTIVE_FAILURES = 3


def build_work_queue(category_defaults, list_pending_fn):
    """Build an ordered list of WorkItem from enabled categories.

    Args:
        category_defaults: dict {category: {enabled, priority, ...}}
        list_pending_fn: callable(category, config) -> list[identifier]
                         returns unprocessed material identifiers for a category
    Returns:
        list[WorkItem] sorted by (priority, category)
    """
    items = []
    for category, cfg in (category_defaults or {}).items():
        if not cfg.get('enabled'):
            continue
        pending = list_pending_fn(category, cfg) or []
        for ident in pending:
            items.append(WorkItem(
                category=category,
                identifier=ident,
                priority=cfg.get('priority', 99),
                config=cfg,
            ))
    items.sort(key=lambda w: (w.priority, w.category, str(w.identifier)))
    return items


def run_auto_generation(
    *,
    category_defaults,
    list_pending_fn,
    quota_status_fn,
    has_budget_fn,
    generate_fn,
    next_recharge_fn=lambda s: None,
    dry_run=False,
    on_progress=None,
    min_percent=1,
):
    """Run one auto-generation pass.

    All external dependencies are injected for testability:
      - quota_status_fn() -> status dict (may raise SessionExpiredError)
      - has_budget_fn(status, min_percent) -> bool
      - generate_fn(WorkItem) -> True on success, False on failure
      - list_pending_fn(category, cfg) -> list of identifiers
      - next_recharge_fn(status) -> str | None

    Returns GenerationReport.
    """
    from gnl_core.quota import SessionExpiredError

    report = GenerationReport(dry_run=dry_run)

    def log(msg):
        if on_progress:
            on_progress(msg)

    # 1. Health-check / read quota
    try:
        status = quota_status_fn()
    except SessionExpiredError as e:
        report.stopped_reason = "session_expired"
        log(f"⚠ {e}")
        return report
    except Exception as e:
        report.stopped_reason = f"quota_error: {str(e)[:80]}"
        log(f"⚠ Erreur quota: {str(e)[:80]}")
        return report

    report.next_recharge = next_recharge_fn(status)

    # 2. Budget check
    if not has_budget_fn(status, min_percent):
        report.stopped_reason = "no_budget"
        log(f"⏸ Budget épuisé — prochaine recharge: {report.next_recharge}")
        return report

    # 3. Build work queue
    queue = build_work_queue(category_defaults, list_pending_fn)
    if not queue:
        report.stopped_reason = "no_material"
        log("✓ Aucune matière à traiter")
        return report

    log(f"▶ {len(queue)} items en file")

    # 4. Generate loop
    consecutive_failures = 0
    for item in queue:
        # Re-check budget before each generation
        try:
            status = quota_status_fn()
        except SessionExpiredError as e:
            report.stopped_reason = "session_expired"
            log(f"⚠ {e}")
            break
        if not has_budget_fn(status, min_percent):
            report.stopped_reason = "no_budget"
            report.next_recharge = next_recharge_fn(status)
            log(f"⏸ Budget épuisé — prochaine recharge: {report.next_recharge}")
            break

        if dry_run:
            report.generated.append(item)
            log(f"  [dry-run] {item.category} / {item.identifier}")
            continue

        try:
            ok = generate_fn(item)
            if ok:
                report.generated.append(item)
                consecutive_failures = 0
                log(f"  ✓ {item.category} / {item.identifier}")
            else:
                report.failed.append(item)
                consecutive_failures += 1
                log(f"  ✗ {item.category} / {item.identifier}")
        except Exception as e:
            report.failed.append(item)
            consecutive_failures += 1
            log(f"  ✗ {item.category} / {item.identifier}: {str(e)[:60]}")

        # Circuit breaker
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            report.stopped_reason = "circuit_breaker"
            log(f"⛔ Circuit breaker: {MAX_CONSECUTIVE_FAILURES} échecs consécutifs")
            break

    if report.stopped_reason is None:
        report.stopped_reason = "completed"

    return report
