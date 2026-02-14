from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from difflib import SequenceMatcher

from .schemas import MatchCandidate, MatchOverride, TaskRecord

MAX_FALLBACK_POOL = 120


def normalize_task_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _name_similarity(left_name: str, right_name: str) -> float:
    return SequenceMatcher(None, normalize_task_name(left_name), normalize_task_name(right_name)).ratio()


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
    if has_identity_signature(left, right):
        return 100.0, "Certain identity signature"

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


def has_identity_signature(left: TaskRecord, right: TaskRecord) -> bool:
    return (
        left.uid == right.uid
        and normalize_task_name(left.name) == normalize_task_name(right.name)
        and left.duration_minutes == right.duration_minutes
    )


def uid_repurpose_risk(left: TaskRecord, right: TaskRecord) -> bool:
    if left.uid != right.uid:
        return False
    if normalize_task_name(left.name) == normalize_task_name(right.name):
        return False
    return _name_similarity(left.name, right.name) < 0.85


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
    unmatched_right_uids = set(right_by_uid) - locked_right_uids

    name_index: dict[str, list[TaskRecord]] = defaultdict(list)
    for task in right_tasks:
        name_index[normalize_task_name(task.name)].append(task)

    dated_right = sorted(
        ((task.start.toordinal(), task.uid, task) for task in right_tasks if task.start is not None),
        key=lambda row: row[0],
    )
    dated_ordinals = [row[0] for row in dated_right]

    def fallback_pool(left: TaskRecord, available: set[int]) -> list[TaskRecord]:
        if not available:
            return []

        pool: list[TaskRecord] = []
        if left.start is not None and dated_right:
            target = left.start.toordinal()
            for window in (14, 30, 60, 120):
                lo = bisect_left(dated_ordinals, target - window)
                hi = bisect_right(dated_ordinals, target + window)
                pool = [task for _, uid, task in dated_right[lo:hi] if uid in available]
                if pool:
                    break

        if not pool:
            pool = [task for task in right_tasks if task.uid in available]

        if len(pool) <= MAX_FALLBACK_POOL:
            return pool

        if left.start is None:
            return pool[:MAX_FALLBACK_POOL]

        target = left.start.toordinal()
        pool.sort(key=lambda task: abs(task.start.toordinal() - target) if task.start is not None else 10**9)
        return pool[:MAX_FALLBACK_POOL]

    candidates: list[MatchCandidate] = []

    for left in left_tasks:
        same_uid_candidate = right_by_uid.get(left.uid)

        if left.uid in matched:
            right = right_by_uid[matched[left.uid]]
            conf, reason = _confidence(left, right)
            flags = []
            if same_uid_candidate is not None and uid_repurpose_risk(left, same_uid_candidate):
                flags.append("uid_repurpose_risk")
            candidates.append(
                MatchCandidate(
                    left_uid=left.uid,
                    right_uid=right.uid,
                    confidence=conf,
                    reason=f"Manual override. {reason}",
                    match_needs_review=bool(flags),
                    match_flags=flags,
                )
            )
            continue

        if (
            same_uid_candidate is not None
            and same_uid_candidate.uid in unmatched_right_uids
            and has_identity_signature(left, same_uid_candidate)
        ):
            matched[left.uid] = same_uid_candidate.uid
            locked_right_uids.add(same_uid_candidate.uid)
            unmatched_right_uids.discard(same_uid_candidate.uid)
            candidates.append(
                MatchCandidate(
                    left_uid=left.uid,
                    right_uid=same_uid_candidate.uid,
                    confidence=100.0,
                    reason="Certain identity signature",
                    match_needs_review=False,
                    match_flags=[],
                )
            )
            continue

        pool = [t for t in name_index.get(normalize_task_name(left.name), []) if t.uid in unmatched_right_uids]
        if (
            same_uid_candidate is not None
            and same_uid_candidate.uid in unmatched_right_uids
            and all(candidate.uid != same_uid_candidate.uid for candidate in pool)
        ):
            pool.append(same_uid_candidate)
        if not pool:
            pool = fallback_pool(left, unmatched_right_uids)
            if (
                same_uid_candidate is not None
                and same_uid_candidate.uid in unmatched_right_uids
                and all(candidate.uid != same_uid_candidate.uid for candidate in pool)
            ):
                pool.append(same_uid_candidate)

        scored: list[tuple[float, float, str, TaskRecord]] = []
        for right in pool:
            conf, reason = _confidence(left, right)
            score = conf
            if left.uid == right.uid and conf < 100:
                score += 2.5
                reason = f"{reason}. UID aligns (non-certainty)"
            scored.append((score, conf, reason, right))

        if not scored:
            continue

        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        _, best_conf, reason, best_right = scored[0]
        matched[left.uid] = best_right.uid
        locked_right_uids.add(best_right.uid)
        unmatched_right_uids.discard(best_right.uid)
        flags = []
        if same_uid_candidate is not None and uid_repurpose_risk(left, same_uid_candidate):
            flags.append("uid_repurpose_risk")
            if "Possible UID repurpose detected" not in reason:
                reason = f"{reason}. Possible UID repurpose detected"
        candidates.append(
            MatchCandidate(
                left_uid=left.uid,
                right_uid=best_right.uid,
                confidence=best_conf,
                reason=reason,
                match_needs_review=bool(flags),
                match_flags=flags,
            )
        )

    return matched, candidates


def confidence_band(confidence: float) -> str:
    return _band(confidence)
