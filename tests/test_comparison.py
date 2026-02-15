from datetime import date

from backend.comparison import compare_tasks
from backend.schemas import MatchOverride, TaskRecord


def task(
    uid: int,
    name: str,
    start: date,
    finish: date,
    *,
    summary: bool = False,
    duration: int = 480,
    predecessors: list[int] | None = None,
):
    return TaskRecord(
        uid=uid,
        uid_inferred=False,
        name=name,
        is_summary=summary,
        start=start,
        finish=finish,
        duration_minutes=duration,
        percent_complete=50,
        predecessors=predecessors or [],
    )


def test_leaf_task_filtering_and_summary_counts():
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
    assert result.summary.action_required_tasks == 1


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


def test_uid_name_duration_signature_date_shift_is_identity_certain():
    left = [task(10, "Pour concrete", date(2025, 1, 1), date(2025, 1, 3), duration=960)]
    right = [task(10, "Pour concrete", date(2025, 1, 2), date(2025, 1, 4), duration=960)]

    result = compare_tasks(left, right, include_baseline=False)

    assert len(result.diffs) == 1
    diff = result.diffs[0]
    assert diff.change_category == "identity_certain"
    assert diff.requires_user_input is False
    assert result.summary.action_required_tasks == 0


def test_uid_name_duration_signature_not_certain_when_uid_is_inferred():
    left = [
        TaskRecord(
            uid=10,
            uid_inferred=True,
            name="Pour concrete",
            is_summary=False,
            start=date(2025, 1, 1),
            finish=date(2025, 1, 3),
            duration_minutes=960,
            percent_complete=50,
            predecessors=[],
        )
    ]
    right = [
        TaskRecord(
            uid=10,
            uid_inferred=True,
            name="Pour concrete",
            is_summary=False,
            start=date(2025, 1, 2),
            finish=date(2025, 1, 4),
            duration_minutes=960,
            percent_complete=50,
            predecessors=[],
        )
    ]

    result = compare_tasks(left, right, include_baseline=False)
    diff = result.diffs[0]
    assert diff.change_category != "identity_certain"
    assert diff.requires_user_input is True


def test_same_uid_with_material_rename_is_identity_conflict():
    left = [task(1, "Install piles", date(2025, 1, 1), date(2025, 1, 2))]
    right = [task(1, "Airport handover closeout", date(2025, 1, 1), date(2025, 1, 2))]

    result = compare_tasks(left, right, include_baseline=False)
    diff = result.diffs[0]

    assert diff.change_category == "identity_conflict"
    assert diff.requires_user_input is True
    assert result.summary.identity_conflict_tasks == 1


def test_duration_and_predecessor_changes_are_actionable():
    left = [task(1, "Task A", date(2025, 1, 1), date(2025, 1, 2), duration=480, predecessors=[7])]
    right = [task(10, "Task A", date(2025, 1, 1), date(2025, 1, 3), duration=960, predecessors=[9])]

    result = compare_tasks(left, right, include_baseline=False)
    diff = result.diffs[0]

    assert diff.change_category == "duration_predecessor_change"
    assert diff.requires_user_input is True


def test_start_finish_only_shift_downstream_of_root_change_is_auto_flow_on():
    left = [
        task(1, "Root", date(2025, 1, 1), date(2025, 1, 2), duration=480),
        task(2, "Downstream", date(2025, 1, 3), date(2025, 1, 4), duration=480, predecessors=[1]),
    ]
    right = [
        task(1, "Root", date(2025, 1, 1), date(2025, 1, 4), duration=960),
        task(20, "Downstream", date(2025, 1, 5), date(2025, 1, 6), duration=480, predecessors=[1]),
    ]

    result = compare_tasks(left, right, include_baseline=False)
    downstream = next(diff for diff in result.diffs if diff.left_name == "Downstream")

    assert downstream.change_category == "date_shift_flow_on"
    assert downstream.requires_user_input is False
    assert downstream.flow_on_from_right_uids == [1]


def test_start_finish_only_shift_with_ambiguous_graph_stays_actionable():
    left = [
        task(2, "Downstream", date(2025, 1, 3), date(2025, 1, 4), duration=480, predecessors=[999]),
        task(3, "Root", date(2025, 1, 1), date(2025, 1, 2), duration=480),
    ]
    right = [
        task(20, "Downstream", date(2025, 1, 4), date(2025, 1, 5), duration=480, predecessors=[999]),
        task(30, "Root", date(2025, 1, 1), date(2025, 1, 3), duration=960),
    ]

    result = compare_tasks(left, right, include_baseline=False)
    downstream = next(diff for diff in result.diffs if diff.left_name == "Downstream")

    assert downstream.change_category == "date_shift_unexplained"
    assert downstream.requires_user_input is True


def test_added_and_removed_detection_and_actionable_flags():
    left_for_removed = [
        task(1, "Task A", date(2025, 1, 1), date(2025, 1, 2)),
        task(2, "Task B", date(2025, 1, 3), date(2025, 1, 4)),
    ]
    right_for_removed = [task(10, "Task A", date(2025, 1, 1), date(2025, 1, 2))]
    removed_result = compare_tasks(left_for_removed, right_for_removed, include_baseline=False, overrides=[])
    removed_diff = next(diff for diff in removed_result.diffs if diff.status == "removed")
    assert removed_diff.requires_user_input is True
    assert removed_diff.change_category == "removed"

    left_for_added = [task(1, "Task A", date(2025, 1, 1), date(2025, 1, 2))]
    right_for_added = [
        task(10, "Task A", date(2025, 1, 1), date(2025, 1, 2)),
        task(20, "Task C", date(2025, 1, 5), date(2025, 1, 6)),
    ]
    added_result = compare_tasks(left_for_added, right_for_added, include_baseline=False, overrides=[])
    added_diff = next(diff for diff in added_result.diffs if diff.status == "added")
    assert added_diff.requires_user_input is True
    assert added_diff.change_category == "added"
