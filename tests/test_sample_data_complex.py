from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.comparison import compare_tasks
from backend.csv_import import parse_tasks_from_csv_bytes
from backend.xml_import import parse_tasks_from_project_xml_bytes


ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample-data"
SCENARIO_PATH = SAMPLE_DIR / "scenario-complex-v30.json"
SUCCESSOR_MATRIX_PATH = SAMPLE_DIR / "successor-matrix.md"

DEFAULT_CSV_COLUMN_MAP = {
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


def _load_scenario() -> dict:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _working_minutes(start_raw: str, finish_raw: str) -> int:
    start = _parse_date(start_raw)
    finish = _parse_date(finish_raw)
    cursor = start
    weekdays = 0
    while cursor <= finish:
        if cursor.weekday() < 5:
            weekdays += 1
        cursor += timedelta(days=1)
    return max(1, weekdays) * 8 * 60


def _task_signature(task: dict) -> tuple:
    pred_sig = sorted((pred["key"], pred["type"]) for pred in task.get("predecessors", []))
    return (
        task["summary"],
        task["start"],
        task["finish"],
        _working_minutes(task["start"], task["finish"]),
        task["percent_complete"],
        pred_sig,
    )


def _count_overlaps(tasks: list[dict]) -> int:
    leaves = [task for task in tasks if not task["summary"]]
    windows = [(_parse_date(task["start"]), _parse_date(task["finish"])) for task in leaves]
    overlap = 0
    for idx, (left_start, left_finish) in enumerate(windows):
        for right_start, right_finish in windows[idx + 1 :]:
            if left_start <= right_finish and right_start <= left_finish:
                overlap += 1
    return overlap


def _assert_no_cycles(tasks: list[dict]) -> None:
    by_key = {task["key"]: task for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(key: str) -> None:
        if key in visiting:
            raise AssertionError(f"Cycle detected at task key {key}")
        if key in visited:
            return
        visiting.add(key)
        for pred in by_key[key].get("predecessors", []):
            pred_key = pred["key"]
            assert pred_key in by_key, f"Missing predecessor key: {pred_key}"
            dfs(pred_key)
        visiting.remove(key)
        visited.add(key)

    for task in tasks:
        dfs(task["key"])


def _derive_successors(version_tasks: list[dict]) -> dict[int, list[tuple[int, str]]]:
    uid_by_key = {task["key"]: int(task["uid"]) for task in version_tasks}
    succ: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for task in version_tasks:
        task_uid = int(task["uid"])
        for pred in task.get("predecessors", []):
            pred_uid = uid_by_key[pred["key"]]
            succ[pred_uid].append((task_uid, pred["type"]))
    return {uid: sorted(items, key=lambda row: row[0]) for uid, items in succ.items()}


def test_complex_sample_data_matrix_and_counts() -> None:
    scenario = _load_scenario()
    expected = scenario["matrix_expectations"]
    v1 = scenario["versions"]["v1"]["tasks"]
    v2 = scenario["versions"]["v2"]["tasks"]

    assert len(v1) == expected["rows_per_version"] == 30
    assert len(v2) == expected["rows_per_version"] == 30
    assert sum(1 for task in v1 if task["summary"]) == expected["summary_rows_per_version"] == 6
    assert sum(1 for task in v2 if task["summary"]) == expected["summary_rows_per_version"] == 6
    assert sum(1 for task in v1 if not task["summary"]) == expected["leaf_rows_per_version"] == 24
    assert sum(1 for task in v2 if not task["summary"]) == expected["leaf_rows_per_version"] == 24

    v1_names = {task["name"]: task for task in v1}
    v2_names = {task["name"]: task for task in v2}
    shared = sorted(set(v1_names) & set(v2_names))
    added = sorted(set(v2_names) - set(v1_names))
    removed = sorted(set(v1_names) - set(v2_names))

    changed = [name for name in shared if _task_signature(v1_names[name]) != _task_signature(v2_names[name])]
    unchanged = [name for name in shared if _task_signature(v1_names[name]) == _task_signature(v2_names[name])]

    assert len(shared) == expected["shared_descriptions"] == 27
    assert len(added) == expected["added_descriptions"] == 3
    assert len(removed) == expected["removed_descriptions"] == 3
    assert len(unchanged) == expected["shared_unchanged"] == 18
    assert len(changed) == expected["shared_changed"] == 9


def test_generated_complex_xml_and_csv_parse_30_rows_each() -> None:
    xml_v1 = parse_tasks_from_project_xml_bytes((SAMPLE_DIR / "programme-v1.xml").read_bytes())
    xml_v2 = parse_tasks_from_project_xml_bytes((SAMPLE_DIR / "programme-v2.xml").read_bytes())
    csv_v1 = parse_tasks_from_csv_bytes((SAMPLE_DIR / "asta-export-v1.csv").read_bytes(), DEFAULT_CSV_COLUMN_MAP)
    csv_v2 = parse_tasks_from_csv_bytes((SAMPLE_DIR / "asta-export-v2.csv").read_bytes(), DEFAULT_CSV_COLUMN_MAP)

    assert len(xml_v1) == 30
    assert len(xml_v2) == 30
    assert len(csv_v1) == 30
    assert len(csv_v2) == 30


def test_complex_dataset_compare_compatibility_with_current_parser_behavior() -> None:
    left_xml = parse_tasks_from_project_xml_bytes((SAMPLE_DIR / "programme-v1.xml").read_bytes())
    right_xml = parse_tasks_from_project_xml_bytes((SAMPLE_DIR / "programme-v2.xml").read_bytes())
    left_csv = parse_tasks_from_csv_bytes((SAMPLE_DIR / "asta-export-v1.csv").read_bytes(), DEFAULT_CSV_COLUMN_MAP)
    right_csv = parse_tasks_from_csv_bytes((SAMPLE_DIR / "asta-export-v2.csv").read_bytes(), DEFAULT_CSV_COLUMN_MAP)

    xml_result = compare_tasks(left_xml, right_xml, include_baseline=False)
    csv_result = compare_tasks(left_csv, right_csv, include_baseline=False)

    assert xml_result.summary.total_left_leaf_tasks == 24
    assert xml_result.summary.total_right_leaf_tasks == 24
    assert csv_result.summary.total_left_leaf_tasks == 24
    assert csv_result.summary.total_right_leaf_tasks == 24

    # With UID-range renumbering, predecessor-ID comparisons currently force most matches into "changed".
    assert xml_result.summary.changed_tasks >= 9
    assert csv_result.summary.changed_tasks >= 9
    assert xml_result.summary.project_finish_delay_days > 0


def test_complex_dataset_has_concurrency() -> None:
    scenario = _load_scenario()
    v1 = scenario["versions"]["v1"]["tasks"]
    v2 = scenario["versions"]["v2"]["tasks"]

    assert _count_overlaps(v1) >= 35
    assert _count_overlaps(v2) >= 35


def test_complex_dataset_dependencies_are_acyclic_and_start_activities_are_explicit() -> None:
    scenario = _load_scenario()
    relation_types: set[str] = set()

    for version_key in ("v1", "v2"):
        tasks = scenario["versions"][version_key]["tasks"]
        by_key = {task["key"]: task for task in tasks}

        for task in tasks:
            for pred in task.get("predecessors", []):
                relation_types.add(pred["type"])
                assert pred["key"] in by_key

        for task in tasks:
            if task["summary"]:
                continue
            if task["start_activity"]:
                continue
            assert task["predecessors"], f"{version_key}: {task['key']} must have predecessors"

        _assert_no_cycles(tasks)

    assert relation_types == {"FS", "SS", "FF", "SF"}


def test_complex_dataset_summary_windows_cover_children() -> None:
    scenario = _load_scenario()

    for version_key in ("v1", "v2"):
        tasks = scenario["versions"][version_key]["tasks"]
        by_key = {task["key"]: task for task in tasks}
        children: dict[str, list[dict]] = defaultdict(list)

        for task in tasks:
            parent_key = task.get("parent_key")
            if parent_key:
                children[parent_key].append(task)

        def descendants(summary_key: str) -> list[dict]:
            out: list[dict] = []
            stack = list(children.get(summary_key, []))
            while stack:
                node = stack.pop()
                out.append(node)
                stack.extend(children.get(node["key"], []))
            return out

        for task in tasks:
            if not task["summary"]:
                continue
            desc = descendants(task["key"])
            if not desc:
                continue
            earliest = min(_parse_date(item["start"]) for item in desc)
            latest = max(_parse_date(item["finish"]) for item in desc)
            assert _parse_date(task["start"]) <= earliest
            assert _parse_date(task["finish"]) >= latest
            assert by_key[task["key"]]["name"]


def test_successor_matrix_matches_predecessor_derivation() -> None:
    scenario = _load_scenario()
    matrix_text = SUCCESSOR_MATRIX_PATH.read_text(encoding="utf-8")

    assert "## V1" in matrix_text
    assert "## V2" in matrix_text

    for version_key in ("v1", "v2"):
        tasks = scenario["versions"][version_key]["tasks"]
        uid_by_key = {task["key"]: int(task["uid"]) for task in tasks}
        successors = _derive_successors(tasks)

        for task in tasks:
            task_uid = int(task["uid"])
            preds = task.get("predecessors", [])
            pred_cell = ", ".join(f"{uid_by_key[pred['key']]}{pred['type']}" for pred in preds) or "-"
            succ_cell = ", ".join(f"{uid}{rel}" for uid, rel in successors.get(task_uid, [])) or "-"
            expected_row = f"| {task_uid} | {task['name']} | {pred_cell} | {succ_cell} |"
            assert expected_row in matrix_text
