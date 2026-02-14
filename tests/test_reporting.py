from datetime import date

from backend.attribution import apply_assignments
from backend.comparison import compare_tasks
from backend.reporting import build_csv
from backend.schemas import AttributionAssignment, TaskRecord


def test_csv_contains_header_and_rows_with_attribution():
    left = [
        TaskRecord(
            uid=1,
            name="Task A",
            is_summary=False,
            start=date(2025, 1, 1),
            finish=date(2025, 1, 2),
            duration_minutes=60,
            percent_complete=0,
            predecessors=[],
        )
    ]
    right = [
        TaskRecord(
            uid=2,
            name="Task A",
            is_summary=False,
            start=date(2025, 1, 3),
            finish=date(2025, 1, 4),
            duration_minutes=60,
            percent_complete=0,
            predecessors=[],
        )
    ]

    result = compare_tasks(left, right, include_baseline=False)
    result, _ = apply_assignments(
        result,
        assignments=[
            AttributionAssignment(
                row_key=result.diffs[0].row_key,
                cause_tag="client",
                reason_code="late_information",
                confirm_low_confidence=True,
            )
        ],
    )

    csv_data = build_csv(result).decode("utf-8")

    assert "cause_tag" in csv_data
    assert "attribution_status" in csv_data
    assert "change_category" in csv_data
    assert "requires_user_input" in csv_data
    assert "auto_reason" in csv_data
    assert "Fault Allocation Summary" in csv_data
    assert "SCL Reference" in csv_data
