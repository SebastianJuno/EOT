from datetime import date

from backend.comparison import compare_tasks
from backend.schemas import MatchOverride, TaskRecord


def task(uid: int, name: str, start: date, finish: date, summary: bool = False):
    return TaskRecord(
        uid=uid,
        name=name,
        is_summary=summary,
        start=start,
        finish=finish,
        duration_minutes=480,
        percent_complete=50,
        predecessors=[],
    )


def test_leaf_task_filtering():
    left = [
        task(1, "Summary", date(2025, 1, 1), date(2025, 1, 10), summary=True),
        task(2, "Excavate", date(2025, 1, 1), date(2025, 1, 4)),
    ]
    right = [
        task(10, "Summary", date(2025, 1, 1), date(2025, 1, 10), summary=True),
        task(20, "Excavate", date(2025, 1, 2), date(2025, 1, 5)),
    ]

    result = compare_tasks(left, right, include_baseline=False)

    assert result.summary.total_left_leaf_tasks == 1
    assert result.summary.total_right_leaf_tasks == 1
    assert result.summary.changed_tasks == 1


def test_override_controls_match():
    left = [task(1, "Install steel", date(2025, 1, 1), date(2025, 1, 10))]
    right = [
        task(20, "Install steel", date(2025, 1, 1), date(2025, 1, 10)),
        task(30, "Install steel", date(2025, 2, 1), date(2025, 2, 10)),
    ]

    result = compare_tasks(
        left,
        right,
        include_baseline=False,
        overrides=[MatchOverride(left_uid=1, right_uid=30)],
    )

    changed = [d for d in result.diffs if d.status == "changed"]
    assert len(changed) == 1
    assert changed[0].right_uid == 30


def test_added_and_removed_detection():
    left = [task(1, "Old task", date(2025, 1, 1), date(2025, 1, 2))]
    right = [task(2, "New task", date(2025, 1, 1), date(2025, 1, 2))]

    result = compare_tasks(left, right, include_baseline=False, overrides=[])

    statuses = sorted(d.status for d in result.diffs)
    assert statuses == ["added", "removed"]
