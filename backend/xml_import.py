from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime

from .schemas import TaskRecord

NS = {"p": "http://schemas.microsoft.com/project"}


def _text(node: ET.Element | None, tag: str) -> str | None:
    if node is None:
        return None
    child = node.find(f"p:{tag}", NS)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _parse_date(value: str | None):
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_int(value: str | None):
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_float(value: str | None):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_duration_minutes(value: str | None):
    if not value:
        return None
    # Handles ISO 8601 duration strings like PT56H0M0S
    match = re.fullmatch(r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return (hours * 60) + minutes


def parse_tasks_from_project_xml_bytes(data: bytes) -> list[TaskRecord]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc

    tasks_parent = root.find("p:Tasks", NS)
    if tasks_parent is None:
        raise ValueError("Invalid Project XML: <Tasks> section not found")

    tasks: list[TaskRecord] = []
    for task in tasks_parent.findall("p:Task", NS):
        uid = _parse_int(_text(task, "UID"))
        name = _text(task, "Name")

        if uid is None or not name:
            continue

        predecessors: list[int] = []
        for link in task.findall("p:PredecessorLink", NS):
            pred_uid = _parse_int(_text(link, "PredecessorUID"))
            if pred_uid is not None:
                predecessors.append(pred_uid)

        record = TaskRecord(
            uid=uid,
            name=name,
            wbs=_text(task, "WBS"),
            outline_level=_parse_int(_text(task, "OutlineLevel")),
            is_summary=(_text(task, "Summary") == "1"),
            start=_parse_date(_text(task, "Start")),
            finish=_parse_date(_text(task, "Finish")),
            duration_minutes=_parse_duration_minutes(_text(task, "Duration")),
            percent_complete=_parse_float(_text(task, "PercentComplete") or _text(task, "PercentageComplete")),
            predecessors=predecessors,
            baseline_start=_parse_date(_text(task, "BaselineStart")),
            baseline_finish=_parse_date(_text(task, "BaselineFinish")),
        )
        tasks.append(record)

    if not tasks:
        raise ValueError("No valid tasks found in XML")

    return tasks
