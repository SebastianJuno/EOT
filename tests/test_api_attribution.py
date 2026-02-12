from datetime import date

from fastapi.testclient import TestClient

import backend.app as app_module
from backend.comparison import compare_tasks
from backend.schemas import TaskRecord


client = TestClient(app_module.app)


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
    response = client.post(
        "/api/attribution/apply",
        json={
            "assignments": [
                {
                    "row_key": row_key,
                    "cause_tag": "client",
                    "reason_code": "late_information",
                    "confirm_low_confidence": True,
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["diffs"][0]["cause_tag"] == "client"
    assert payload["fault_allocation"]["task_slippage_days"]["client_days"] == 3.0
