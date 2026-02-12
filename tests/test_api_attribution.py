from datetime import date

import backend.app as app_module
from backend.app import attribution_apply
from backend.comparison import compare_tasks
from backend.schemas import AttributionApplyRequest, TaskRecord


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


def test_apply_attribution_endpoint_updates_result():
    left = [task(1, "Task A", date(2025, 1, 1), date(2025, 1, 3))]
    right = [task(2, "Task A", date(2025, 1, 1), date(2025, 1, 6))]

    result = compare_tasks(left, right, include_baseline=False)
    app_module.LAST_RESULT = result
    app_module.LAST_ASSIGNMENTS = {}

    row_key = result.diffs[0].row_key
    response = attribution_apply(
        AttributionApplyRequest(
            assignments=[
                {
                    "row_key": row_key,
                    "cause_tag": "client",
                    "reason_code": "late_information",
                    "confirm_low_confidence": True,
                }
            ]
        )
    )

    assert response["diffs"][0]["cause_tag"] == "client"
    assert response["fault_allocation"]["task_slippage_days"]["client_days"] == 3.0
