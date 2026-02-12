from datetime import date

from backend.attribution import apply_assignments
from backend.comparison import compare_tasks
from backend.schemas import AttributionAssignment, TaskRecord


def task(uid: int, name: str, start: date, finish: date):
    return TaskRecord(
        uid=uid,
        name=name,
        is_summary=False,
        start=start,
        finish=finish,
        duration_minutes=480,
        percent_complete=0,
        predecessors=[],
    )


def test_default_attribution_initialization():
    left = [task(1, "Concrete pour section A", date(2025, 1, 1), date(2025, 1, 5))]
    right = [task(2, "Utility shutdown permit", date(2025, 1, 1), date(2025, 1, 8))]

    result = compare_tasks(left, right, include_baseline=False)
    diff = result.diffs[0]

    assert diff.cause_tag == "unassigned"
    assert diff.attribution_status == "pending_low_confidence"
    assert result.fault_allocation.task_slippage_days.excluded_low_confidence_days == 3


def test_red_confidence_excluded_until_confirmed():
    left = [task(1, "Concrete pour section A", date(2025, 1, 1), date(2025, 1, 5))]
    right = [task(2, "Utility shutdown permit", date(2025, 1, 1), date(2025, 1, 8))]
    result = compare_tasks(left, right, include_baseline=False)

    row_key = result.diffs[0].row_key
    updated, _ = apply_assignments(
        result,
        assignments=[
            AttributionAssignment(
                row_key=row_key,
                cause_tag="client",
                reason_code="late_information",
                confirm_low_confidence=True,
            )
        ],
    )

    assert updated.diffs[0].attribution_status == "ready"
    assert updated.fault_allocation.task_slippage_days.client_days == 3


def test_unassigned_excluded_from_percentages():
    left = [
        task(1, "Task A", date(2025, 1, 1), date(2025, 1, 5)),
        task(2, "Task B", date(2025, 1, 1), date(2025, 1, 6)),
    ]
    right = [
        task(11, "Task A", date(2025, 1, 1), date(2025, 1, 8)),
        task(12, "Task B", date(2025, 1, 1), date(2025, 1, 9)),
    ]
    result = compare_tasks(left, right, include_baseline=False)

    assignments = [
        AttributionAssignment(
            row_key=result.diffs[0].row_key,
            cause_tag="client",
            confirm_low_confidence=True,
        )
    ]
    updated, _ = apply_assignments(result, assignments)

    metric = updated.fault_allocation.task_slippage_days
    assert metric.client_days >= 0
    assert metric.unassigned_days >= 0
    assert metric.client_pct in (0.0, 100.0)


def test_project_finish_proportional_split():
    left = [
        task(1, "Task A", date(2025, 1, 1), date(2025, 1, 5)),
        task(2, "Task B", date(2025, 1, 1), date(2025, 1, 5)),
    ]
    right = [
        task(11, "Task A", date(2025, 1, 1), date(2025, 1, 9)),
        task(12, "Task B", date(2025, 1, 1), date(2025, 1, 7)),
    ]

    result = compare_tasks(left, right, include_baseline=False)

    # Sort for deterministic assignment by task name
    rows = sorted(result.diffs, key=lambda d: d.left_name or "")
    updated, _ = apply_assignments(
        result,
        assignments=[
            AttributionAssignment(row_key=rows[0].row_key, cause_tag="client", confirm_low_confidence=True),
            AttributionAssignment(row_key=rows[1].row_key, cause_tag="contractor", confirm_low_confidence=True),
        ],
    )

    project_metric = updated.fault_allocation.project_finish_impact_days
    assert project_metric.client_days > project_metric.contractor_days
    assert round(project_metric.client_days + project_metric.contractor_days, 3) == 4.0


def test_added_removed_zero_slippage():
    left = [task(1, "Old task", date(2025, 1, 1), date(2025, 1, 2))]
    right = [task(2, "New task", date(2025, 1, 1), date(2025, 1, 2))]

    result = compare_tasks(left, right, include_baseline=False)
    metric = result.fault_allocation.task_slippage_days

    assert metric.client_days == 0
    assert metric.contractor_days == 0
    assert metric.neutral_days == 0
