from backend.csv_import import parse_tasks_from_csv_bytes


def test_parse_tasks_from_csv_bytes_with_explicit_mapping():
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
    assert tasks[0].uid_inferred is False
    assert tasks[0].name == "Groundworks"
    assert tasks[0].duration_minutes == 480
    assert tasks[0].predecessors == [5]
    assert tasks[0].is_summary is False


def test_parse_tasks_from_csv_bytes_infers_columns_and_synthetic_uids():
    csv_text = """Name,Duration,Start,Finish,Planned percent complete (PPC),Percent complete
Name,Duration,Start,Finish,Planned percent complete (PPC),Percent complete
Contract Programme,88w 1d,01/11/2024,21/08/2026,7.14,6.82
Concrete Works,33w 4h,01/12/2024,21/01/2025,99.00,55.00
"""

    tasks, diagnostics = parse_tasks_from_csv_bytes(
        csv_text.encode("utf-8"),
        column_map={},
        return_diagnostics=True,
    )

    assert len(tasks) == 2
    assert tasks[0].uid == 1
    assert tasks[0].uid_inferred is True
    assert tasks[0].duration_minutes == 211680  # 88w 1d
    assert tasks[1].duration_minutes == 79440  # 33w 4h
    assert tasks[0].percent_complete == 6.82  # actual takes precedence over planned

    assert diagnostics.synthetic_uid is True
    assert diagnostics.skipped_duplicate_header_rows == 1
    assert diagnostics.resolved_column_map["name"] == "Name"
    assert diagnostics.resolved_column_map["duration_minutes"] == "Duration"
    assert diagnostics.resolved_column_map["percent_complete"] == "Percent complete"
    assert any("synthetic sequential UIDs" in warning for warning in diagnostics.warnings)


def test_parse_tasks_from_csv_bytes_parses_decimal_duration_days():
    csv_text = """Name,Duration,Start,Finish,Percent complete
Task A,13w 2.5d,01/01/2025,10/04/2025,50
"""

    tasks = parse_tasks_from_csv_bytes(csv_text.encode("utf-8"), column_map={})

    assert len(tasks) == 1
    assert tasks[0].duration_minutes == 32400


def test_parse_tasks_from_csv_bytes_missing_mapping_when_inference_disabled():
    csv_text = "UID,Task Name,Start,Finish\n1,Task,2026-01-01,2026-01-02\n"

    try:
        parse_tasks_from_csv_bytes(
            csv_text.encode("utf-8"),
            {"uid": "UID"},
            allow_inference=False,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unable to resolve required CSV columns" in str(exc)


def test_parse_tasks_from_csv_bytes_warns_on_ambiguous_name_candidates():
    csv_text = """Task Name,Activity Name,Start,Finish,Percent complete
Task A,Task A,2026-01-01,2026-01-02,25
"""

    tasks, diagnostics = parse_tasks_from_csv_bytes(
        csv_text.encode("utf-8"),
        column_map={},
        return_diagnostics=True,
    )

    assert len(tasks) == 1
    assert any("Ambiguous mapping for 'name'" in warning for warning in diagnostics.warnings)
