from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from .schemas import (
    AttributionAssignment,
    AttributionBulkFilter,
    AttributionStatus,
    CauseTag,
    CompareResult,
    FaultAllocation,
    FaultMetric,
    TaskDiff,
)

ATTRIBUTION_SCOPE = {"changed", "added", "removed"}


def _safe_days(left: date | None, right: date | None) -> float:
    if left is None or right is None:
        return 0.0
    return float(max(0, (right - left).days))


def row_key_for_diff(diff: TaskDiff) -> str:
    left = diff.left_uid if diff.left_uid is not None else "none"
    right = diff.right_uid if diff.right_uid is not None else "none"
    return f"{left}|{right}|{diff.status}"


def _update_percentages(metric: FaultMetric) -> FaultMetric:
    assigned_total = metric.client_days + metric.contractor_days + metric.neutral_days
    metric.assigned_total_days = round(assigned_total, 3)
    if assigned_total > 0:
        metric.client_pct = round((metric.client_days / assigned_total) * 100, 2)
        metric.contractor_pct = round((metric.contractor_days / assigned_total) * 100, 2)
        metric.neutral_pct = round((metric.neutral_days / assigned_total) * 100, 2)
    else:
        metric.client_pct = 0.0
        metric.contractor_pct = 0.0
        metric.neutral_pct = 0.0
    return metric


def _bucket_metric(metric: FaultMetric, cause_tag: CauseTag, days: float) -> None:
    if cause_tag == "client":
        metric.client_days += days
    elif cause_tag == "contractor":
        metric.contractor_days += days
    elif cause_tag == "neutral":
        metric.neutral_days += days
    else:
        metric.unassigned_days += days


def _determine_status(diff: TaskDiff, confirmed_low_confidence: bool) -> tuple[AttributionStatus, bool]:
    if diff.status not in ATTRIBUTION_SCOPE:
        return "ready", False

    if diff.confidence < 50 and not confirmed_low_confidence:
        return "pending_low_confidence", False

    if diff.cause_tag == "unassigned":
        return "unassigned", False

    return "ready", True


def initialize_attribution(diffs: list[TaskDiff], assignment_map: dict[str, dict] | None = None) -> list[TaskDiff]:
    assignment_map = assignment_map or {}

    for diff in diffs:
        diff.row_key = row_key_for_diff(diff)
        diff.task_slippage_days = _safe_days(diff.left_finish, diff.right_finish)

        prev = assignment_map.get(diff.row_key, {})
        diff.cause_tag = prev.get("cause_tag", diff.cause_tag)
        diff.reason_code = prev.get("reason_code", diff.reason_code)
        confirmed_low_confidence = bool(prev.get("confirm_low_confidence", False))

        status, included = _determine_status(diff, confirmed_low_confidence)
        diff.attribution_status = status
        diff.included_in_totals = included

    return diffs


def build_assignment_map(diffs: list[TaskDiff], previous: dict[str, dict] | None = None) -> dict[str, dict]:
    previous = previous or {}
    out: dict[str, dict] = {}
    for diff in diffs:
        prev = previous.get(diff.row_key, {})
        out[diff.row_key] = {
            "cause_tag": diff.cause_tag,
            "reason_code": diff.reason_code,
            "confirm_low_confidence": prev.get("confirm_low_confidence", False),
        }
    return out


def apply_assignments(
    result: CompareResult,
    assignments: list[AttributionAssignment],
    bulk: AttributionBulkFilter | None = None,
    assignment_map: dict[str, dict] | None = None,
) -> tuple[CompareResult, dict[str, dict]]:
    assignment_map = assignment_map or build_assignment_map(result.diffs)

    diff_by_key = {diff.row_key: diff for diff in result.diffs}

    for item in assignments:
        diff = diff_by_key.get(item.row_key)
        if diff is None:
            continue
        diff.cause_tag = item.cause_tag
        diff.reason_code = item.reason_code
        assignment_map[item.row_key] = {
            "cause_tag": item.cause_tag,
            "reason_code": item.reason_code,
            "confirm_low_confidence": item.confirm_low_confidence,
        }

    if bulk is not None:
        for diff in result.diffs:
            if bulk.row_keys and diff.row_key not in bulk.row_keys:
                continue
            if bulk.statuses and diff.status not in bulk.statuses:
                continue
            if bulk.confidence_bands and diff.confidence_band not in bulk.confidence_bands:
                continue

            diff.cause_tag = bulk.cause_tag
            diff.reason_code = bulk.reason_code
            assignment_map[diff.row_key] = {
                "cause_tag": bulk.cause_tag,
                "reason_code": bulk.reason_code,
                "confirm_low_confidence": bulk.confirm_low_confidence,
            }

    initialize_attribution(result.diffs, assignment_map)
    result.fault_allocation = compute_fault_allocation(result)
    return result, assignment_map


def _project_share_by_row(result: CompareResult) -> dict[str, float]:
    base_delay = result.summary.project_finish_delay_days
    contributors = [
        diff
        for diff in result.diffs
        if diff.status == "changed" and diff.task_slippage_days > 0
    ]

    total_weight = sum(diff.task_slippage_days for diff in contributors)
    if base_delay <= 0 or total_weight <= 0:
        return {}

    shares: dict[str, float] = {}
    for diff in contributors:
        shares[diff.row_key] = base_delay * (diff.task_slippage_days / total_weight)
    return shares


def compute_fault_allocation(result: CompareResult) -> FaultAllocation:
    task_metric = FaultMetric()
    project_metric = FaultMetric()

    project_shares = _project_share_by_row(result)

    for diff in result.diffs:
        if diff.status not in ATTRIBUTION_SCOPE:
            continue

        task_days = diff.task_slippage_days
        project_days = project_shares.get(diff.row_key, 0.0)

        if diff.attribution_status == "pending_low_confidence":
            task_metric.excluded_low_confidence_days += task_days
            project_metric.excluded_low_confidence_days += project_days
            continue

        if diff.cause_tag == "unassigned":
            task_metric.unassigned_days += task_days
            project_metric.unassigned_days += project_days
            continue

        _bucket_metric(task_metric, diff.cause_tag, task_days)
        _bucket_metric(project_metric, diff.cause_tag, project_days)

    _update_percentages(task_metric)
    _update_percentages(project_metric)

    for metric in (task_metric, project_metric):
        metric.client_days = round(metric.client_days, 3)
        metric.contractor_days = round(metric.contractor_days, 3)
        metric.neutral_days = round(metric.neutral_days, 3)
        metric.unassigned_days = round(metric.unassigned_days, 3)
        metric.excluded_low_confidence_days = round(metric.excluded_low_confidence_days, 3)

    return FaultAllocation(
        project_finish_impact_days=project_metric,
        task_slippage_days=task_metric,
    )


def assignment_rows_for_result(result: CompareResult) -> Iterable[dict]:
    for diff in result.diffs:
        yield {
            "row_key": diff.row_key,
            "cause_tag": diff.cause_tag,
            "reason_code": diff.reason_code,
            "attribution_status": diff.attribution_status,
        }
