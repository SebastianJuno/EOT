from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

CauseTag = Literal["client", "contractor", "neutral", "unassigned"]
AttributionStatus = Literal["ready", "pending_low_confidence", "unassigned"]
ReasonCode = Literal[
    "instruction_change",
    "late_information",
    "contractor_productivity",
    "weather",
    "third_party_statutory",
    "other",
    "",
]


class TaskRecord(BaseModel):
    uid: int
    name: str
    wbs: str | None = None
    outline_level: int | None = None
    is_summary: bool = False
    start: date | None = None
    finish: date | None = None
    duration_minutes: int | None = None
    percent_complete: float | None = None
    predecessors: list[int] = Field(default_factory=list)
    baseline_start: date | None = None
    baseline_finish: date | None = None


class MatchCandidate(BaseModel):
    left_uid: int
    right_uid: int
    confidence: float
    reason: str
    match_needs_review: bool = False
    match_flags: list[str] = Field(default_factory=list)


class MatchOverride(BaseModel):
    left_uid: int
    right_uid: int


class ChangeField(BaseModel):
    field: Literal[
        "start",
        "finish",
        "duration_minutes",
        "percent_complete",
        "predecessors",
        "baseline_start",
        "baseline_finish",
    ]
    left_value: str | float | int | list[int] | None
    right_value: str | float | int | list[int] | None


class TaskDiff(BaseModel):
    row_key: str = ""
    left_uid: int | None
    right_uid: int | None
    left_name: str | None
    right_name: str | None
    left_finish: date | None = None
    right_finish: date | None = None
    status: Literal["changed", "added", "removed", "unchanged"]
    confidence: float
    confidence_band: Literal["green", "amber", "red"]
    evidence: list[ChangeField] = Field(default_factory=list)
    cause_tag: CauseTag = "unassigned"
    reason_code: ReasonCode = ""
    attribution_status: AttributionStatus = "unassigned"
    task_slippage_days: float = 0.0
    included_in_totals: bool = False
    protocol_hint: str = (
        "Classify the dominant cause under SCL concepts: client risk event, contractor risk event, or neutral event."
    )
    change_category: Literal[
        "unchanged",
        "identity_certain",
        "identity_conflict",
        "duration_change",
        "predecessor_change",
        "duration_predecessor_change",
        "date_shift_flow_on",
        "date_shift_unexplained",
        "progress_or_baseline_change",
        "added",
        "removed",
        "manual_override_actionable",
    ] = "unchanged"
    requires_user_input: bool = True
    auto_reason: str | None = None
    flow_on_from_right_uids: list[int] = Field(default_factory=list)
    auto_overridden: bool = False


class CompareSummary(BaseModel):
    total_left_leaf_tasks: int
    total_right_leaf_tasks: int
    matched_tasks: int
    changed_tasks: int
    added_tasks: int
    removed_tasks: int
    unchanged_tasks: int
    project_finish_delay_days: float = 0.0
    action_required_tasks: int = 0
    auto_resolved_tasks: int = 0
    auto_flow_on_tasks: int = 0
    identity_conflict_tasks: int = 0


class FaultMetric(BaseModel):
    client_days: float = 0.0
    contractor_days: float = 0.0
    neutral_days: float = 0.0
    unassigned_days: float = 0.0
    excluded_low_confidence_days: float = 0.0
    assigned_total_days: float = 0.0
    client_pct: float = 0.0
    contractor_pct: float = 0.0
    neutral_pct: float = 0.0


class FaultAllocation(BaseModel):
    project_finish_impact_days: FaultMetric = Field(default_factory=FaultMetric)
    task_slippage_days: FaultMetric = Field(default_factory=FaultMetric)


class CompareResult(BaseModel):
    summary: CompareSummary
    candidates: list[MatchCandidate]
    diffs: list[TaskDiff]
    fault_allocation: FaultAllocation = Field(default_factory=FaultAllocation)


class AttributionAssignment(BaseModel):
    row_key: str
    cause_tag: CauseTag
    reason_code: ReasonCode = ""
    confirm_low_confidence: bool = False
    override_auto: bool = False


class AttributionBulkFilter(BaseModel):
    row_keys: list[str] | None = None
    statuses: list[Literal["changed", "added", "removed", "unchanged"]] | None = None
    confidence_bands: list[Literal["green", "amber", "red"]] | None = None
    cause_tag: CauseTag = "unassigned"
    reason_code: ReasonCode = ""
    confirm_low_confidence: bool = False


class AttributionApplyRequest(BaseModel):
    assignments: list[AttributionAssignment] = Field(default_factory=list)
    bulk: AttributionBulkFilter | None = None


class PreviewTask(BaseModel):
    uid: int
    name: str
    is_summary: bool = False
    outline_level: int | None = None
    start: date | None = None
    finish: date | None = None
    baseline_start: date | None = None
    baseline_finish: date | None = None
    predecessors: list[int] = Field(default_factory=list)
    percent_complete: float | None = None


class PreviewTaskOption(BaseModel):
    uid: int
    name: str


class PreviewRow(BaseModel):
    row_key: str
    left: PreviewTask | None = None
    right: PreviewTask | None = None
    confidence: float = 0.0
    confidence_band: Literal["green", "amber", "red"] = "red"
    match_reason: str = ""
    status: Literal["matched", "left_only", "right_only"] = "matched"
    match_needs_review: bool = False
    match_flags: list[str] = Field(default_factory=list)


class PreviewSessionMeta(BaseModel):
    session_id: str
    file_kind: Literal[".mpp", ".xml", ".csv"]
    include_baseline: bool = False
    include_summaries: bool = False
    offset: int = 0
    limit: int = 200
    total_rows: int = 0
    has_more: bool = False
    timeline_start: date | None = None
    timeline_finish: date | None = None
    overrides: list[MatchOverride] = Field(default_factory=list)


class PreviewRowsResponse(BaseModel):
    session: PreviewSessionMeta
    rows: list[PreviewRow] = Field(default_factory=list)


class PreviewInitResponse(PreviewRowsResponse):
    left_leaf_options: list[PreviewTaskOption] = Field(default_factory=list)
    right_leaf_options: list[PreviewTaskOption] = Field(default_factory=list)


class PreviewMatchEdit(BaseModel):
    left_uid: int
    right_uid: int | None = None


class PreviewMatchEditRequest(BaseModel):
    session_id: str
    edits: list[PreviewMatchEdit] = Field(default_factory=list)
    include_summaries: bool = False
    offset: int = 0
    limit: int = 200


class PreviewAnalyzeRequest(BaseModel):
    session_id: str
