from __future__ import annotations

from .attribution import compute_fault_allocation, initialize_attribution
from .matching import auto_match, confidence_band
from .schemas import (
    ChangeField,
    CompareResult,
    CompareSummary,
    MatchOverride,
    TaskDiff,
    TaskRecord,
)


COMPARE_FIELDS = [
    "start",
    "finish",
    "duration_minutes",
    "percent_complete",
    "predecessors",
]

BASELINE_FIELDS = ["baseline_start", "baseline_finish"]


def _serialize(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return sorted(value)
    return value


def _project_finish_delay_days(left_leaf: list[TaskRecord], right_leaf: list[TaskRecord]) -> float:
    left_finishes = [task.finish for task in left_leaf if task.finish is not None]
    right_finishes = [task.finish for task in right_leaf if task.finish is not None]

    if not left_finishes or not right_finishes:
        return 0.0

    delta = (max(right_finishes) - max(left_finishes)).days
    return float(max(0, delta))


def compare_tasks(
    left_tasks: list[TaskRecord],
    right_tasks: list[TaskRecord],
    include_baseline: bool,
    overrides: list[MatchOverride] | None = None,
    assignment_map: dict[str, dict] | None = None,
) -> CompareResult:
    left_leaf = [t for t in left_tasks if not t.is_summary]
    right_leaf = [t for t in right_tasks if not t.is_summary]

    matched, candidates = auto_match(left_leaf, right_leaf, overrides=overrides)
    right_by_uid = {t.uid: t for t in right_leaf}

    used_right = set(matched.values())
    diffs: list[TaskDiff] = []

    fields = COMPARE_FIELDS + (BASELINE_FIELDS if include_baseline else [])

    for left in left_leaf:
        right_uid = matched.get(left.uid)
        if right_uid is None:
            diffs.append(
                TaskDiff(
                    left_uid=left.uid,
                    right_uid=None,
                    left_name=left.name,
                    right_name=None,
                    left_finish=left.finish,
                    right_finish=None,
                    status="removed",
                    confidence=0,
                    confidence_band="red",
                )
            )
            continue

        right = right_by_uid[right_uid]
        candidate = next(c for c in candidates if c.left_uid == left.uid and c.right_uid == right_uid)

        evidence: list[ChangeField] = []
        for field in fields:
            left_val = _serialize(getattr(left, field))
            right_val = _serialize(getattr(right, field))
            if left_val != right_val:
                evidence.append(
                    ChangeField(
                        field=field,
                        left_value=left_val,
                        right_value=right_val,
                    )
                )

        status = "changed" if evidence else "unchanged"
        diffs.append(
            TaskDiff(
                left_uid=left.uid,
                right_uid=right.uid,
                left_name=left.name,
                right_name=right.name,
                left_finish=left.finish,
                right_finish=right.finish,
                status=status,
                confidence=candidate.confidence,
                confidence_band=confidence_band(candidate.confidence),
                evidence=evidence,
            )
        )

    for right in right_leaf:
        if right.uid not in used_right:
            diffs.append(
                TaskDiff(
                    left_uid=None,
                    right_uid=right.uid,
                    left_name=None,
                    right_name=right.name,
                    left_finish=None,
                    right_finish=right.finish,
                    status="added",
                    confidence=0,
                    confidence_band="red",
                )
            )

    summary = CompareSummary(
        total_left_leaf_tasks=len(left_leaf),
        total_right_leaf_tasks=len(right_leaf),
        matched_tasks=sum(1 for d in diffs if d.status in {"changed", "unchanged"}),
        changed_tasks=sum(1 for d in diffs if d.status == "changed"),
        added_tasks=sum(1 for d in diffs if d.status == "added"),
        removed_tasks=sum(1 for d in diffs if d.status == "removed"),
        unchanged_tasks=sum(1 for d in diffs if d.status == "unchanged"),
        project_finish_delay_days=_project_finish_delay_days(left_leaf, right_leaf),
    )

    diffs.sort(key=lambda d: (d.status, d.left_name or d.right_name or ""))
    diffs = initialize_attribution(diffs, assignment_map)

    result = CompareResult(summary=summary, candidates=candidates, diffs=diffs)
    result.fault_allocation = compute_fault_allocation(result)
    return result
