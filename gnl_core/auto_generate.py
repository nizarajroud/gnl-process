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
    finalized: list = field(default_factory=list)  # [(category, output_path), ...]
    stopped_reason: Optional[str] = None
    next_recharge: Optional[str] = None
    dry_run: bool = False


# Circuit breaker: stop a pass after this many consecutive failures
MAX_CONSECUTIVE_FAILURES = 3


class _Skip:
    """Sentinel returned by generate_fn when an item is not applicable
    (e.g. category not wired yet). Does NOT count toward the circuit breaker."""
    def __repr__(self):
        return "SKIP"


SKIP = _Skip()


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
    finalize_fn=None,
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
    from gnl_core.quota import SessionExpiredError, NetworkTimeoutError

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
    except NetworkTimeoutError as e:
        report.stopped_reason = "network_timeout"
        log(f"⏳ Timeout réseau (transitoire): {str(e)[:80]}")
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
        except NetworkTimeoutError as e:
            report.stopped_reason = "network_timeout"
            log(f"⏳ Timeout réseau (transitoire): {str(e)[:80]}")
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
            result = generate_fn(item)
            if result is SKIP:
                report.skipped.append(item)
                log(f"  ⊘ {item.category} / {item.identifier} (skipped)")
            elif result:
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

    # 5. Finalize per category: combine + deliver the items generated THIS pass.
    # Only categories that produced at least one successful item are finalized.
    if finalize_fn and not dry_run and report.generated:
        by_category = {}
        for item in report.generated:
            by_category.setdefault(item.category, []).append(item)
        for category, items in by_category.items():
            try:
                output = finalize_fn(category, items)
                if output:
                    report.finalized.append((category, output))
                    log(f"  📦 Finalisé {category} → {output}")
            except Exception as e:
                log(f"  ⚠ Finalize {category} échoué: {str(e)[:60]}")

    return report


# Adaptive scheduling
# ---------------------
# On a 24/7 host we want to fire a pass right after each 5h-window recharge,
# not on a fixed clock. compute_next_delay_seconds inspects the quota status
# and returns how long to wait before the next pass.

# Small buffer after a reset so the recharge is definitely applied server-side.
RECHARGE_BUFFER_SECONDS = 120
# When budget is still available after a pass, wait a bit and go again
# (queue not empty, more can be produced within the current window).
CONTINUE_DELAY_SECONDS = 60
# Transient network timeout -> retry soon (the network usually recovers fast).
NETWORK_RETRY_DELAY_SECONDS = 150
# Safety floor / ceiling.
MIN_DELAY_SECONDS = 30
MAX_DELAY_SECONDS = 6 * 3600


def compute_next_delay_seconds(status, stopped_reason, min_percent=1):
    """Return seconds to wait before the next adaptive pass.

    Logic:
      - session_expired / quota_error -> back off MAX (nothing productive to do)
      - network_timeout -> retry soon (transient; the network recovers fast)
      - budget still available (stopped 'completed' with material left, or
        'no_material') -> short CONTINUE delay to drain remaining queue soon
      - budget exhausted ('no_budget') -> wait until the 5h window resets
        (resets_in_h) + buffer
      - fallback -> CONTINUE delay
    """
    if stopped_reason == "network_timeout":
        return NETWORK_RETRY_DELAY_SECONDS

    if stopped_reason in ("session_expired",) or (stopped_reason or "").startswith("quota_error"):
        return MAX_DELAY_SECONDS

    if stopped_reason == "no_budget":
        # Wait for the sooner of the two windows to recharge.
        candidates = []
        for key in ("window_5h", "window_weekly"):
            w = (status or {}).get(key) or {}
            rin = w.get("resets_in_h")
            rem = w.get("percent_remaining")
            # Only windows that are actually exhausted gate us; pick their reset.
            if rem is not None and rem <= min_percent and rin is not None:
                candidates.append(rin * 3600)
        if candidates:
            wait = min(candidates) + RECHARGE_BUFFER_SECONDS
            return int(max(MIN_DELAY_SECONDS, min(MAX_DELAY_SECONDS, wait)))
        # Exhausted but no reset info -> back off moderately
        return MAX_DELAY_SECONDS

    if stopped_reason == "no_material":
        # Nothing to do now; re-check after the next recharge window (5h) so we
        # pick up freshly fetched material without hammering.
        w = (status or {}).get("window_5h") or {}
        rin = w.get("resets_in_h")
        if rin is not None:
            return int(max(MIN_DELAY_SECONDS, min(MAX_DELAY_SECONDS, rin * 3600 + RECHARGE_BUFFER_SECONDS)))
        return MAX_DELAY_SECONDS

    # completed / circuit_breaker with budget likely remaining -> go again soon
    return CONTINUE_DELAY_SECONDS
