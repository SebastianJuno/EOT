from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from .schemas import MatchCandidate, MatchOverride, TaskRecord


def _name_similarity(left_name: str, right_name: str) -> float:
    return SequenceMatcher(None, left_name.strip().lower(), right_name.strip().lower()).ratio()


def _date_proximity_score(left: TaskRecord, right: TaskRecord) -> float:
    if not left.start or not right.start:
        return 0.5
    day_delta = abs((left.start - right.start).days)
    if day_delta <= 3:
        return 1.0
    if day_delta <= 14:
        return 0.75
    if day_delta <= 30:
        return 0.5
    return 0.2


def _confidence(left: TaskRecord, right: TaskRecord) -> tuple[float, str]:
    name_score = _name_similarity(left.name, right.name)
    date_score = _date_proximity_score(left, right)
    blended = (name_score * 0.8) + (date_score * 0.2)

    if name_score > 0.98:
        reason = "Exact or near-exact description match"
    elif name_score > 0.90:
        reason = "Strong description similarity"
    else:
        reason = "Approximate description similarity"

    return round(blended * 100, 1), reason


def _band(confidence: float) -> str:
    if confidence >= 80:
        return "green"
    if confidence >= 50:
        return "amber"
    return "red"


def auto_match(
    left_tasks: list[TaskRecord],
    right_tasks: list[TaskRecord],
    overrides: list[MatchOverride] | None = None,
) -> tuple[dict[int, int], list[MatchCandidate]]:
    overrides = overrides or []
    right_by_uid = {task.uid: task for task in right_tasks}

    matched: dict[int, int] = {}
    locked_right_uids: set[int] = set()
    for override in overrides:
        if override.right_uid in right_by_uid:
            matched[override.left_uid] = override.right_uid
            locked_right_uids.add(override.right_uid)

    name_index: dict[str, list[TaskRecord]] = defaultdict(list)
    for task in right_tasks:
        name_index[task.name.strip().lower()].append(task)

    candidates: list[MatchCandidate] = []

    for left in left_tasks:
        if left.uid in matched:
            right = right_by_uid[matched[left.uid]]
            conf, reason = _confidence(left, right)
            candidates.append(
                MatchCandidate(
                    left_uid=left.uid,
                    right_uid=right.uid,
                    confidence=conf,
                    reason=f"Manual override. {reason}",
                )
            )
            continue

        pool = [t for t in name_index.get(left.name.strip().lower(), []) if t.uid not in locked_right_uids]
        if not pool:
            pool = [t for t in right_tasks if t.uid not in locked_right_uids]

        scored = []
        for right in pool:
            conf, reason = _confidence(left, right)
            scored.append((conf, reason, right))

        if not scored:
            continue

        scored.sort(key=lambda row: row[0], reverse=True)
        best_conf, reason, best_right = scored[0]
        matched[left.uid] = best_right.uid
        locked_right_uids.add(best_right.uid)
        candidates.append(
            MatchCandidate(
                left_uid=left.uid,
                right_uid=best_right.uid,
                confidence=best_conf,
                reason=reason,
            )
        )

    return matched, candidates


def confidence_band(confidence: float) -> str:
    return _band(confidence)
