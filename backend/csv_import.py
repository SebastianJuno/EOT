from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO

from .schemas import TaskRecord


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    raw = value.strip().replace("%", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _parse_predecessors(value: str | None) -> list[int]:
    if not value:
        return []

    cleaned = value.replace(";", ",").replace("|", ",")
    out: list[int] = []
    for token in cleaned.split(","):
        token = token.strip()
        if not token:
            continue
        # handles values like "12FS" by taking the leading numeric part
        num = ""
        for ch in token:
            if ch.isdigit():
                num += ch
            else:
                break
        if num:
            out.append(int(num))
    return out


def parse_tasks_from_csv_bytes(
    data: bytes,
    column_map: dict[str, str],
) -> list[TaskRecord]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text))

    required = ["uid", "name", "start", "finish"]
    missing_required = [key for key in required if not column_map.get(key)]
    if missing_required:
        raise ValueError(f"Missing required column mapping keys: {', '.join(missing_required)}")

    tasks: list[TaskRecord] = []
    for row in reader:
        uid = _parse_int(row.get(column_map["uid"]))
        name = (row.get(column_map["name"]) or "").strip()

        if uid is None or not name:
            continue

        task = TaskRecord(
            uid=uid,
            name=name,
            wbs=(row.get(column_map.get("wbs", "")) or None) if column_map.get("wbs") else None,
            outline_level=_parse_int(row.get(column_map.get("outline_level", ""))) if column_map.get("outline_level") else None,
            is_summary=_parse_bool(row.get(column_map.get("is_summary", ""))) if column_map.get("is_summary") else False,
            start=_parse_date(row.get(column_map["start"])),
            finish=_parse_date(row.get(column_map["finish"])),
            duration_minutes=_parse_int(row.get(column_map.get("duration_minutes", ""))) if column_map.get("duration_minutes") else None,
            percent_complete=_parse_float(row.get(column_map.get("percent_complete", ""))) if column_map.get("percent_complete") else None,
            predecessors=_parse_predecessors(row.get(column_map.get("predecessors", ""))) if column_map.get("predecessors") else [],
            baseline_start=_parse_date(row.get(column_map.get("baseline_start", ""))) if column_map.get("baseline_start") else None,
            baseline_finish=_parse_date(row.get(column_map.get("baseline_finish", ""))) if column_map.get("baseline_finish") else None,
        )
        tasks.append(task)

    if not tasks:
        raise ValueError("No valid tasks found in CSV using current column mappings")

    return tasks
