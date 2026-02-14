from __future__ import annotations

from collections import defaultdict, deque

from .attribution import compute_fault_allocation, initialize_attribution
from .matching import auto_match, confidence_band, has_identity_signature
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
DATE_FIELDS = {"start", "finish"}


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


def _classify_change(
    *,
    left: TaskRecord,
    right: TaskRecord,
    evidence: list[ChangeField],
    match_needs_review: bool,
) -> tuple[str, bool, str | None]:
    if match_needs_review:
        return (
            "identity_conflict",
            True,
            "Potential UID repurpose detected; manual review required.",
        )

    changed_fields = {item.field for item in evidence}
    if not changed_fields:
        if has_identity_signature(left, right):
            return (
                "identity_certain",
                False,
                "Certain identity signature (UID+name+duration) detected.",
            )
        return "unchanged", False, "No field-level variance detected."

    if has_identity_signature(left, right) and changed_fields.issubset(DATE_FIELDS):
        return (
            "identity_certain",
            False,
            "UID+name+duration matched; start/finish drift treated as non-actionable.",
        )

    if "duration_minutes" in changed_fields and "predecessors" in changed_fields:
        return "duration_predecessor_change", True, None
    if "duration_minutes" in changed_fields:
        return "duration_change", True, None
    if "predecessors" in changed_fields:
        return "predecessor_change", True, None

    if changed_fields.issubset(DATE_FIELDS):
        return "date_shift_unexplained", True, None

    return "progress_or_baseline_change", True, None


def _build_successor_graph(tasks: list[TaskRecord]) -> tuple[dict[int, set[int]], set[int]]:
    right_by_uid = {task.uid: task for task in tasks}
    successors: dict[int, set[int]] = defaultdict(set)
    missing_predecessors: set[int] = set()

    for task in tasks:
        for pred_uid in task.predecessors or []:
            if pred_uid not in right_by_uid:
                missing_predecessors.add(task.uid)
                continue
            successors[pred_uid].add(task.uid)

    return successors, missing_predecessors


def _flow_sources(
    successors: dict[int, set[int]],
    root_uids: set[int],
) -> dict[int, set[int]]:
    sources: dict[int, set[int]] = defaultdict(set)
    for root_uid in root_uids:
        queue: deque[int] = deque([root_uid])
        visited: set[int] = {root_uid}
        while queue:
            node = queue.popleft()
            for successor_uid in successors.get(node, set()):
                if successor_uid not in visited:
                    visited.add(successor_uid)
                    queue.append(successor_uid)
                sources[successor_uid].add(root_uid)
    return sources


def _apply_flow_on_classification(diffs: list[TaskDiff], right_tasks: list[TaskRecord]) -> None:
    successors, missing_predecessors = _build_successor_graph(right_tasks)

    root_change_right_uids = {
        diff.right_uid
        for diff in diffs
        if diff.right_uid is not None
        and any(field.field in {"duration_minutes", "predecessors"} for field in diff.evidence)
    }
    if not root_change_right_uids:
        return

    propagation_sources = _flow_sources(successors, {uid for uid in root_change_right_uids if uid is not None})

    for diff in diffs:
        if diff.change_category != "date_shift_unexplained":
            continue
        if diff.right_uid is None:
            continue

        upstream_sources = sorted(propagation_sources.get(diff.right_uid, set()))
        if upstream_sources:
            diff.change_category = "date_shift_flow_on"
            diff.requires_user_input = False
            diff.auto_reason = (
                "Start/finish drift propagated from upstream duration/predecessor changes."
            )
            diff.flow_on_from_right_uids = upstream_sources
            continue

        # Explicitly retain actionable status when dependency proof is ambiguous/missing.
        if diff.right_uid in missing_predecessors:
            diff.auto_reason = None
        diff.requires_user_input = True


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
    candidate_by_pair = {(candidate.left_uid, candidate.right_uid): candidate for candidate in candidates}
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
                    change_category="removed",
                    requires_user_input=True,
                )
            )
            continue

        right = right_by_uid[right_uid]
        candidate = candidate_by_pair.get((left.uid, right_uid))
        if candidate is None:
            # Defensive fallback: keep compare resilient even if candidate generation changes.
            candidate_confidence = 0.0
            candidate_band = "red"
        else:
            candidate_confidence = candidate.confidence
            candidate_band = confidence_band(candidate.confidence)

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
        change_category, requires_user_input, auto_reason = _classify_change(
            left=left,
            right=right,
            evidence=evidence,
            match_needs_review=bool(candidate and candidate.match_needs_review),
        )
        diffs.append(
            TaskDiff(
                left_uid=left.uid,
                right_uid=right.uid,
                left_name=left.name,
                right_name=right.name,
                left_finish=left.finish,
                right_finish=right.finish,
                status=status,
                confidence=candidate_confidence,
                confidence_band=candidate_band,
                evidence=evidence,
                change_category=change_category,
                requires_user_input=requires_user_input,
                auto_reason=auto_reason,
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
                    change_category="added",
                    requires_user_input=True,
                )
            )

    _apply_flow_on_classification(diffs, right_tasks)

    summary = CompareSummary(
        total_left_leaf_tasks=len(left_leaf),
        total_right_leaf_tasks=len(right_leaf),
        matched_tasks=sum(1 for d in diffs if d.status in {"changed", "unchanged"}),
        changed_tasks=sum(1 for d in diffs if d.status == "changed"),
        added_tasks=sum(1 for d in diffs if d.status == "added"),
        removed_tasks=sum(1 for d in diffs if d.status == "removed"),
        unchanged_tasks=sum(1 for d in diffs if d.status == "unchanged"),
        project_finish_delay_days=_project_finish_delay_days(left_leaf, right_leaf),
        action_required_tasks=sum(1 for d in diffs if d.requires_user_input),
        auto_resolved_tasks=sum(1 for d in diffs if not d.requires_user_input),
        auto_flow_on_tasks=sum(1 for d in diffs if d.change_category == "date_shift_flow_on"),
        identity_conflict_tasks=sum(1 for d in diffs if d.change_category == "identity_conflict"),
    )

    diffs.sort(key=lambda d: (d.status, d.left_name or d.right_name or ""))
    diffs = initialize_attribution(diffs, assignment_map)

    result = CompareResult(summary=summary, candidates=candidates, diffs=diffs)
    result.fault_allocation = compute_fault_allocation(result)
    return result
