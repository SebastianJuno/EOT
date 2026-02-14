from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from .comparison import compare_tasks
from .matching import auto_match, confidence_band
from .schemas import (
    CompareResult,
    MatchOverride,
    PreviewInitResponse,
    PreviewMatchEdit,
    PreviewRow,
    PreviewRowsResponse,
    PreviewSessionMeta,
    PreviewTask,
    PreviewTaskOption,
    TaskRecord,
)

SESSION_TTL_SECONDS = 60 * 60
MAX_SESSIONS = 12


@dataclass
class PreviewSession:
    session_id: str
    file_kind: Literal[".mpp", ".xml", ".csv"]
    include_baseline: bool
    left_tasks: list[TaskRecord]
    right_tasks: list[TaskRecord]
    manual_overrides: dict[int, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    _left_leaf: list[TaskRecord] = field(init=False, repr=False)
    _right_leaf: list[TaskRecord] = field(init=False, repr=False)
    _left_summaries: list[TaskRecord] = field(init=False, repr=False)
    _right_summaries: list[TaskRecord] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._left_leaf = [task for task in self.left_tasks if not task.is_summary]
        self._right_leaf = [task for task in self.right_tasks if not task.is_summary]
        self._left_summaries = [task for task in self.left_tasks if task.is_summary]
        self._right_summaries = [task for task in self.right_tasks if task.is_summary]

    @property
    def left_leaf(self) -> list[TaskRecord]:
        return self._left_leaf

    @property
    def right_leaf(self) -> list[TaskRecord]:
        return self._right_leaf

    @property
    def left_summaries(self) -> list[TaskRecord]:
        return self._left_summaries

    @property
    def right_summaries(self) -> list[TaskRecord]:
        return self._right_summaries

    def touch(self) -> None:
        self.updated_at = time.time()


PREVIEW_SESSIONS: dict[str, PreviewSession] = {}


def cleanup_preview_sessions(now: float | None = None) -> None:
    now = now or time.time()
    expired = [
        session_id
        for session_id, session in PREVIEW_SESSIONS.items()
        if now - session.updated_at > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        PREVIEW_SESSIONS.pop(session_id, None)

    while len(PREVIEW_SESSIONS) > MAX_SESSIONS:
        oldest = min(PREVIEW_SESSIONS.values(), key=lambda item: item.updated_at)
        PREVIEW_SESSIONS.pop(oldest.session_id, None)


def create_preview_session(
    *,
    file_kind: Literal[".mpp", ".xml", ".csv"],
    include_baseline: bool,
    left_tasks: list[TaskRecord],
    right_tasks: list[TaskRecord],
) -> PreviewSession:
    cleanup_preview_sessions()
    session_id = uuid.uuid4().hex[:16]
    session = PreviewSession(
        session_id=session_id,
        file_kind=file_kind,
        include_baseline=include_baseline,
        left_tasks=left_tasks,
        right_tasks=right_tasks,
    )
    PREVIEW_SESSIONS[session_id] = session
    return session


def get_preview_session(session_id: str) -> PreviewSession:
    cleanup_preview_sessions()
    session = PREVIEW_SESSIONS.get(session_id)
    if session is None:
        raise KeyError("Preview session not found or expired")
    session.touch()
    return session


def _sort_tasks(tasks: list[TaskRecord]) -> list[TaskRecord]:
    max_date = date(2100, 1, 1)
    return sorted(
        tasks,
        key=lambda task: (
            task.start or max_date,
            task.finish or max_date,
            task.outline_level or 99,
            task.name.lower(),
            task.uid,
        ),
    )


def _task_to_preview(task: TaskRecord) -> PreviewTask:
    return PreviewTask(
        uid=task.uid,
        name=task.name,
        is_summary=task.is_summary,
        outline_level=task.outline_level,
        start=task.start,
        finish=task.finish,
        baseline_start=task.baseline_start,
        baseline_finish=task.baseline_finish,
        predecessors=list(task.predecessors or []),
        percent_complete=task.percent_complete,
    )


def _manual_override_models(session: PreviewSession) -> list[MatchOverride]:
    return [
        MatchOverride(left_uid=left_uid, right_uid=right_uid)
        for left_uid, right_uid in sorted(session.manual_overrides.items())
    ]


def _timeline_bounds(session: PreviewSession) -> tuple[date | None, date | None]:
    starts: list[date] = []
    finishes: list[date] = []
    for task in session.left_leaf + session.right_leaf:
        if task.start is not None:
            starts.append(task.start)
        if task.finish is not None:
            finishes.append(task.finish)
    if not starts and not finishes:
        return None, None

    low = min(starts) if starts else min(finishes)
    high = max(finishes) if finishes else max(starts)
    return low, high


def _build_leaf_rows(session: PreviewSession) -> list[PreviewRow]:
    left_leaf = _sort_tasks(session.left_leaf)
    right_by_uid = {task.uid: task for task in session.right_leaf}
    matched, candidates = auto_match(
        session.left_leaf,
        session.right_leaf,
        overrides=_manual_override_models(session),
    )
    candidate_map = {(item.left_uid, item.right_uid): item for item in candidates}
    used_right: set[int] = set()
    rows: list[PreviewRow] = []

    for left in left_leaf:
        right_uid = matched.get(left.uid)
        right = right_by_uid.get(right_uid) if right_uid is not None else None
        if right is not None:
            used_right.add(right.uid)
            candidate = candidate_map.get((left.uid, right.uid))
            confidence = candidate.confidence if candidate else 0.0
            reason = candidate.reason if candidate else "Provisional match"
            band = confidence_band(confidence)
            status: Literal["matched", "left_only", "right_only"] = "matched"
            row_key = f"leaf:{left.uid}:{right.uid}"
        else:
            confidence = 0.0
            reason = "No right-side match"
            band = "red"
            status = "left_only"
            row_key = f"leaf:{left.uid}:none"

        rows.append(
            PreviewRow(
                row_key=row_key,
                left=_task_to_preview(left),
                right=_task_to_preview(right) if right is not None else None,
                confidence=confidence,
                confidence_band=band,
                match_reason=reason,
                status=status,
            )
        )

    for right in _sort_tasks(session.right_leaf):
        if right.uid in used_right:
            continue
        rows.append(
            PreviewRow(
                row_key=f"leaf:none:{right.uid}",
                left=None,
                right=_task_to_preview(right),
                confidence=0.0,
                confidence_band="red",
                match_reason="No left-side match",
                status="right_only",
            )
        )

    return rows


def _build_summary_rows(session: PreviewSession) -> list[PreviewRow]:
    right_by_name: dict[str, list[TaskRecord]] = {}
    for task in _sort_tasks(session.right_summaries):
        key = task.name.strip().lower()
        right_by_name.setdefault(key, []).append(task)

    used_right: set[int] = set()
    rows: list[PreviewRow] = []

    for left in _sort_tasks(session.left_summaries):
        key = left.name.strip().lower()
        match = None
        for candidate in right_by_name.get(key, []):
            if candidate.uid not in used_right:
                match = candidate
                break

        if match is not None:
            used_right.add(match.uid)
            rows.append(
                PreviewRow(
                    row_key=f"summary:{left.uid}:{match.uid}",
                    left=_task_to_preview(left),
                    right=_task_to_preview(match),
                    confidence=100.0,
                    confidence_band="green",
                    match_reason="Summary name match",
                    status="matched",
                )
            )
        else:
            rows.append(
                PreviewRow(
                    row_key=f"summary:{left.uid}:none",
                    left=_task_to_preview(left),
                    right=None,
                    confidence=0.0,
                    confidence_band="red",
                    match_reason="No right-side summary match",
                    status="left_only",
                )
            )

    for right in _sort_tasks(session.right_summaries):
        if right.uid in used_right:
            continue
        rows.append(
            PreviewRow(
                row_key=f"summary:none:{right.uid}",
                left=None,
                right=_task_to_preview(right),
                confidence=0.0,
                confidence_band="red",
                match_reason="No left-side summary match",
                status="right_only",
            )
        )

    return rows


def _build_rows(session: PreviewSession, include_summaries: bool) -> list[PreviewRow]:
    leaf_rows = _build_leaf_rows(session)
    if not include_summaries:
        return leaf_rows
    return _build_summary_rows(session) + leaf_rows


def _build_meta(
    session: PreviewSession,
    *,
    include_summaries: bool,
    offset: int,
    limit: int,
    total_rows: int,
) -> PreviewSessionMeta:
    start, finish = _timeline_bounds(session)
    return PreviewSessionMeta(
        session_id=session.session_id,
        file_kind=session.file_kind,
        include_baseline=session.include_baseline,
        include_summaries=include_summaries,
        offset=offset,
        limit=limit,
        total_rows=total_rows,
        has_more=offset + limit < total_rows,
        timeline_start=start,
        timeline_finish=finish,
        overrides=_manual_override_models(session),
    )


def build_preview_rows_response(
    session: PreviewSession,
    *,
    include_summaries: bool = False,
    offset: int = 0,
    limit: int = 200,
) -> PreviewRowsResponse:
    offset = max(0, offset)
    limit = max(1, min(limit, 1000))

    rows = _build_rows(session, include_summaries=include_summaries)
    total_rows = len(rows)
    page_rows = rows[offset : offset + limit]
    meta = _build_meta(
        session,
        include_summaries=include_summaries,
        offset=offset,
        limit=limit,
        total_rows=total_rows,
    )
    return PreviewRowsResponse(session=meta, rows=page_rows)


def build_preview_init_response(
    session: PreviewSession,
    *,
    include_summaries: bool = False,
    offset: int = 0,
    limit: int = 200,
) -> PreviewInitResponse:
    rows_response = build_preview_rows_response(
        session,
        include_summaries=include_summaries,
        offset=offset,
        limit=limit,
    )
    left_options = [
        PreviewTaskOption(uid=task.uid, name=task.name) for task in _sort_tasks(session.left_leaf)
    ]
    right_options = [
        PreviewTaskOption(uid=task.uid, name=task.name) for task in _sort_tasks(session.right_leaf)
    ]
    return PreviewInitResponse(
        session=rows_response.session,
        rows=rows_response.rows,
        left_leaf_options=left_options,
        right_leaf_options=right_options,
    )


def apply_preview_match_edits(session: PreviewSession, edits: list[PreviewMatchEdit]) -> None:
    left_uids = {task.uid for task in session.left_leaf}
    right_uids = {task.uid for task in session.right_leaf}

    for edit in edits:
        if edit.left_uid not in left_uids:
            raise ValueError(f"Unknown left leaf UID: {edit.left_uid}")

        if edit.right_uid is None:
            session.manual_overrides.pop(edit.left_uid, None)
            continue

        if edit.right_uid not in right_uids:
            raise ValueError(f"Unknown right leaf UID: {edit.right_uid}")

        # Keep right-side assignments unique.
        for left_uid, right_uid in list(session.manual_overrides.items()):
            if right_uid == edit.right_uid and left_uid != edit.left_uid:
                session.manual_overrides.pop(left_uid, None)

        session.manual_overrides[edit.left_uid] = edit.right_uid

    session.touch()


def analyze_preview_session(
    session: PreviewSession,
    *,
    assignment_map: dict[str, dict] | None = None,
) -> CompareResult:
    result = compare_tasks(
        left_tasks=session.left_tasks,
        right_tasks=session.right_tasks,
        include_baseline=session.include_baseline,
        overrides=_manual_override_models(session),
        assignment_map=assignment_map,
    )
    session.touch()
    return result
