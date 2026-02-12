from backend.csv_import import parse_tasks_from_csv_bytes


def test_parse_tasks_from_csv_bytes():
    csv_text = """Unique ID,Task Name,Start,Finish,Duration (mins),% Complete,Predecessors,Summary,Baseline Start,Baseline Finish
10,Groundworks,2026-01-10,2026-01-20,480,50,5FS,0,2026-01-08,2026-01-18
"""

    column_map = {
        "uid": "Unique ID",
        "name": "Task Name",
        "start": "Start",
        "finish": "Finish",
        "duration_minutes": "Duration (mins)",
        "percent_complete": "% Complete",
        "predecessors": "Predecessors",
        "is_summary": "Summary",
        "baseline_start": "Baseline Start",
        "baseline_finish": "Baseline Finish",
    }

    tasks = parse_tasks_from_csv_bytes(csv_text.encode("utf-8"), column_map)

    assert len(tasks) == 1
    assert tasks[0].uid == 10
    assert tasks[0].name == "Groundworks"
    assert tasks[0].predecessors == [5]
    assert tasks[0].is_summary is False


def test_parse_tasks_from_csv_bytes_missing_mapping():
    csv_text = "UID,Task Name,Start,Finish\n1,Task,2026-01-01,2026-01-02\n"

    try:
        parse_tasks_from_csv_bytes(csv_text.encode("utf-8"), {"uid": "UID"})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Missing required column mapping keys" in str(exc)
