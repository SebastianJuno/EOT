#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

MSP_NS = "http://schemas.microsoft.com/project"
TYPE_TO_CODE = {"FF": 0, "FS": 1, "SF": 2, "SS": 3}
CSV_HEADER = [
    "Unique ID",
    "Task Name",
    "Start",
    "Finish",
    "Duration (mins)",
    "% Complete",
    "Predecessors",
    "Summary",
    "Baseline Start",
    "Baseline Finish",
]


@dataclass(frozen=True)
class Predecessor:
    key: str
    uid: int
    relation_type: str


@dataclass
class Task:
    uid: int
    key: str
    name: str
    parent_key: str | None
    summary: bool
    outline_level: int
    wbs: str
    start: date
    finish: date
    baseline_start: date
    baseline_finish: date
    percent_complete: float | None
    start_activity: bool
    predecessors: list[Predecessor]
    id_number: int = 0

    @property
    def duration_minutes(self) -> int:
        return _working_minutes(self.start, self.finish)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _working_minutes(start: date, finish: date) -> int:
    if finish < start:
        raise ValueError(f"Finish {finish.isoformat()} is before start {start.isoformat()}")

    cursor = start
    weekdays = 0
    while cursor <= finish:
        if cursor.weekday() < 5:
            weekdays += 1
        cursor += timedelta(days=1)

    # Keep durations non-zero even if a task is set entirely on weekends.
    if weekdays == 0:
        weekdays = 1
    return weekdays * 8 * 60


def _iso_start(d: date) -> str:
    return f"{d.isoformat()}T08:00:00"


def _iso_finish(d: date) -> str:
    return f"{d.isoformat()}T17:00:00"


def _duration_iso(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    return f"PT{hours}H{mins}M0S"


def _load_scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_version(raw_tasks: list[dict]) -> list[Task]:
    by_key = {task["key"]: task for task in raw_tasks}
    if len(by_key) != len(raw_tasks):
        raise ValueError("Task keys must be unique per version")

    by_name = {task["name"]: task for task in raw_tasks}
    if len(by_name) != len(raw_tasks):
        raise ValueError("Task names must be unique per version")

    tasks: list[Task] = []
    for idx, raw in enumerate(raw_tasks, start=1):
        parent_key = raw.get("parent_key")
        if parent_key is not None and parent_key not in by_key:
            raise ValueError(f"Unknown parent key: {parent_key} for task {raw['key']}")

        preds: list[Predecessor] = []
        for pred in raw.get("predecessors", []):
            pred_key = pred["key"]
            relation = pred["type"]
            if pred_key not in by_key:
                raise ValueError(f"Unknown predecessor key: {pred_key} for task {raw['key']}")
            if relation not in TYPE_TO_CODE:
                raise ValueError(f"Unsupported dependency type {relation} on {raw['key']}")
            preds.append(
                Predecessor(
                    key=pred_key,
                    uid=int(by_key[pred_key]["uid"]),
                    relation_type=relation,
                )
            )

        tasks.append(
            Task(
                uid=int(raw["uid"]),
                key=raw["key"],
                name=raw["name"],
                parent_key=parent_key,
                summary=bool(raw["summary"]),
                outline_level=int(raw["outline_level"]),
                wbs=raw["wbs"],
                start=_parse_date(raw["start"]),
                finish=_parse_date(raw["finish"]),
                baseline_start=_parse_date(raw["baseline_start"]),
                baseline_finish=_parse_date(raw["baseline_finish"]),
                percent_complete=(float(raw["percent_complete"]) if raw["percent_complete"] is not None else None),
                start_activity=bool(raw.get("start_activity", False)),
                predecessors=preds,
                id_number=idx,
            )
        )

    uids = [task.uid for task in tasks]
    if len(uids) != len(set(uids)):
        raise ValueError("UID values must be unique per version")
    return tasks


def _task_signature(task: Task) -> tuple:
    pred_signature = sorted((pred.key, pred.relation_type) for pred in task.predecessors)
    return (
        task.summary,
        task.start.isoformat(),
        task.finish.isoformat(),
        task.duration_minutes,
        task.percent_complete,
        pred_signature,
    )


def _validate_matrix(scenario: dict, v1: list[Task], v2: list[Task]) -> None:
    expected = scenario["matrix_expectations"]

    v1_summaries = sum(1 for t in v1 if t.summary)
    v2_summaries = sum(1 for t in v2 if t.summary)
    v1_leaves = len(v1) - v1_summaries
    v2_leaves = len(v2) - v2_summaries

    if len(v1) != expected["rows_per_version"] or len(v2) != expected["rows_per_version"]:
        raise ValueError("Row count expectation failed")
    if v1_summaries != expected["summary_rows_per_version"] or v2_summaries != expected["summary_rows_per_version"]:
        raise ValueError("Summary row count expectation failed")
    if v1_leaves != expected["leaf_rows_per_version"] or v2_leaves != expected["leaf_rows_per_version"]:
        raise ValueError("Leaf row count expectation failed")

    v1_by_name = {t.name: t for t in v1}
    v2_by_name = {t.name: t for t in v2}
    shared_names = sorted(set(v1_by_name) & set(v2_by_name))
    added_names = sorted(set(v2_by_name) - set(v1_by_name))
    removed_names = sorted(set(v1_by_name) - set(v2_by_name))

    changed = []
    unchanged = []
    for name in shared_names:
        if _task_signature(v1_by_name[name]) == _task_signature(v2_by_name[name]):
            unchanged.append(name)
        else:
            changed.append(name)

    if len(shared_names) != expected["shared_descriptions"]:
        raise ValueError("Shared-description count expectation failed")
    if len(added_names) != expected["added_descriptions"]:
        raise ValueError("Added-description count expectation failed")
    if len(removed_names) != expected["removed_descriptions"]:
        raise ValueError("Removed-description count expectation failed")
    if len(unchanged) != expected["shared_unchanged"] or len(changed) != expected["shared_changed"]:
        raise ValueError("Shared changed/unchanged expectation failed")


def _validate_dependencies(tasks: list[Task], version_name: str) -> None:
    by_key = {task.key: task for task in tasks}

    for task in tasks:
        if task.summary:
            continue
        if not task.start_activity and not task.predecessors:
            raise ValueError(f"{version_name}: non-start leaf {task.key} has no predecessors")

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visiting:
            raise ValueError(f"{version_name}: cycle detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for pred in by_key[node].predecessors:
            if pred.key in by_key:
                dfs(pred.key)
        visiting.remove(node)
        visited.add(node)

    for task in tasks:
        dfs(task.key)


def _validate_summary_coverage(tasks: list[Task], version_name: str) -> None:
    children: dict[str, list[Task]] = {}
    for task in tasks:
        if task.parent_key:
            children.setdefault(task.parent_key, []).append(task)

    def descendants(summary_key: str) -> list[Task]:
        out: list[Task] = []
        stack = list(children.get(summary_key, []))
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(children.get(node.key, []))
        return out

    summaries = [task for task in tasks if task.summary]
    for summary in summaries:
        desc = descendants(summary.key)
        if not desc:
            continue
        earliest = min(task.start for task in desc)
        latest = max(task.finish for task in desc)
        if summary.start > earliest or summary.finish < latest:
            raise ValueError(
                f"{version_name}: summary {summary.key} does not envelope child dates ({earliest} - {latest})"
            )


def _write_xml(output_path: Path, version_name: str, version_title: str, tasks: list[Task]) -> None:
    ET.register_namespace("", MSP_NS)
    root = ET.Element(f"{{{MSP_NS}}}Project")
    ET.SubElement(root, f"{{{MSP_NS}}}Name").text = version_name
    ET.SubElement(root, f"{{{MSP_NS}}}Title").text = version_title
    ET.SubElement(root, f"{{{MSP_NS}}}ScheduleFromStart").text = "1"
    ET.SubElement(root, f"{{{MSP_NS}}}StartDate").text = _iso_start(min(task.start for task in tasks))

    tasks_el = ET.SubElement(root, f"{{{MSP_NS}}}Tasks")
    for task in tasks:
        task_el = ET.SubElement(tasks_el, f"{{{MSP_NS}}}Task")
        ET.SubElement(task_el, f"{{{MSP_NS}}}UID").text = str(task.uid)
        ET.SubElement(task_el, f"{{{MSP_NS}}}ID").text = str(task.id_number)
        ET.SubElement(task_el, f"{{{MSP_NS}}}Name").text = task.name
        ET.SubElement(task_el, f"{{{MSP_NS}}}WBS").text = task.wbs
        ET.SubElement(task_el, f"{{{MSP_NS}}}Summary").text = "1" if task.summary else "0"
        ET.SubElement(task_el, f"{{{MSP_NS}}}OutlineLevel").text = str(task.outline_level)
        ET.SubElement(task_el, f"{{{MSP_NS}}}Start").text = _iso_start(task.start)
        ET.SubElement(task_el, f"{{{MSP_NS}}}Finish").text = _iso_finish(task.finish)
        ET.SubElement(task_el, f"{{{MSP_NS}}}Duration").text = _duration_iso(task.duration_minutes)
        if task.percent_complete is not None:
            value = int(task.percent_complete) if task.percent_complete.is_integer() else task.percent_complete
            ET.SubElement(task_el, f"{{{MSP_NS}}}PercentComplete").text = str(value)
        ET.SubElement(task_el, f"{{{MSP_NS}}}BaselineStart").text = _iso_start(task.baseline_start)
        ET.SubElement(task_el, f"{{{MSP_NS}}}BaselineFinish").text = _iso_finish(task.baseline_finish)

        for pred in task.predecessors:
            link = ET.SubElement(task_el, f"{{{MSP_NS}}}PredecessorLink")
            ET.SubElement(link, f"{{{MSP_NS}}}PredecessorUID").text = str(pred.uid)
            ET.SubElement(link, f"{{{MSP_NS}}}Type").text = str(TYPE_TO_CODE[pred.relation_type])

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def _write_csv(output_path: Path, tasks: list[Task]) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for task in tasks:
            predecessors = ",".join(f"{pred.uid}{pred.relation_type}" for pred in task.predecessors)
            percent = ""
            if task.percent_complete is not None:
                percent = int(task.percent_complete) if task.percent_complete.is_integer() else task.percent_complete
            writer.writerow(
                [
                    task.uid,
                    task.name,
                    task.start.isoformat(),
                    task.finish.isoformat(),
                    task.duration_minutes,
                    percent,
                    predecessors,
                    1 if task.summary else 0,
                    task.baseline_start.isoformat(),
                    task.baseline_finish.isoformat(),
                ]
            )


def _derive_successors(tasks: list[Task]) -> dict[int, list[tuple[int, str]]]:
    successors: dict[int, list[tuple[int, str]]] = {task.uid: [] for task in tasks}
    for task in tasks:
        for pred in task.predecessors:
            successors.setdefault(pred.uid, []).append((task.uid, pred.relation_type))
    return successors


def _write_successor_matrix(output_path: Path, v1: list[Task], v2: list[Task]) -> None:
    lines: list[str] = []
    lines.append("# Successor Matrix")
    lines.append("")
    lines.append("Derived directly from predecessor links in `scenario-complex-v30.json`.")
    lines.append("")

    for version_label, tasks in (("V1", v1), ("V2", v2)):
        successors = _derive_successors(tasks)
        lines.append(f"## {version_label}")
        lines.append("")
        lines.append("| UID | Task Name | Predecessors | Successors |")
        lines.append("| --- | --- | --- | --- |")
        for task in tasks:
            pred_cell = ", ".join(f"{pred.uid}{pred.relation_type}" for pred in task.predecessors) or "-"
            succ_rows = sorted(successors.get(task.uid, []), key=lambda item: item[0])
            succ_cell = ", ".join(f"{uid}{rel}" for uid, rel in succ_rows) or "-"
            lines.append(f"| {task.uid} | {task.name} | {pred_cell} | {succ_cell} |")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def generate() -> None:
    sample_dir = Path(__file__).resolve().parent
    scenario_path = sample_dir / "scenario-complex-v30.json"
    scenario = _load_scenario(scenario_path)

    v1_raw = scenario["versions"]["v1"]["tasks"]
    v2_raw = scenario["versions"]["v2"]["tasks"]

    v1 = _build_version(v1_raw)
    v2 = _build_version(v2_raw)

    _validate_matrix(scenario, v1, v2)
    _validate_dependencies(v1, "v1")
    _validate_dependencies(v2, "v2")
    _validate_summary_coverage(v1, "v1")
    _validate_summary_coverage(v2, "v2")

    _write_xml(
        sample_dir / "programme-v1.xml",
        scenario["versions"]["v1"]["name"],
        scenario["versions"]["v1"]["title"],
        v1,
    )
    _write_xml(
        sample_dir / "programme-v2.xml",
        scenario["versions"]["v2"]["name"],
        scenario["versions"]["v2"]["title"],
        v2,
    )
    _write_csv(sample_dir / "asta-export-v1.csv", v1)
    _write_csv(sample_dir / "asta-export-v2.csv", v2)
    _write_successor_matrix(sample_dir / "successor-matrix.md", v1, v2)

    print("Generated:")
    print(" - programme-v1.xml")
    print(" - programme-v2.xml")
    print(" - asta-export-v1.csv")
    print(" - asta-export-v2.csv")
    print(" - successor-matrix.md")


if __name__ == "__main__":
    generate()
