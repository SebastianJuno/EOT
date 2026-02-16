from __future__ import annotations

import csv
import re
from datetime import date, datetime
from io import StringIO

from .schemas import CsvImportDiagnostics, TaskRecord

INFER_FIELDS = [
    "uid",
    "name",
    "start",
    "finish",
    "duration_minutes",
    "percent_complete",
    "predecessors",
    "is_summary",
    "baseline_start",
    "baseline_finish",
]

REQUIRED_FIELDS = ["name", "start", "finish"]

FIELD_ALIASES: dict[str, list[str]] = {
    "uid": ["unique id", "uid", "id", "task id", "activity id"],
    "name": ["task name", "name", "activity name", "description"],
    "start": ["start", "start date", "planned start"],
    "finish": ["finish", "finish date", "end", "end date"],
    "duration_minutes": ["duration", "duration mins", "duration minutes", "planned duration"],
    "percent_complete": ["percent complete", "% complete", "actual percent complete", "progress"],
    "predecessors": ["predecessor", "predecessors", "dependencies", "dependency"],
    "is_summary": ["summary", "is summary"],
    "baseline_start": ["baseline start"],
    "baseline_finish": ["baseline finish"],
}

PERCENT_ACTUAL_ALIASES = {"percent complete", "% complete", "actual percent complete"}
PERCENT_PLANNED_ALIASES = {"planned percent complete", "planned percent complete ppc", "ppc", "planned % complete"}

DURATION_TOKEN = re.compile(r"([0-9]*\.?[0-9]+)\s*([wdhm])", re.IGNORECASE)


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

    # Handle ISO values that include timezone suffixes.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass
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


def _parse_duration_minutes(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None

    numeric = _parse_int(raw)
    if numeric is not None:
        return numeric

    total_minutes = 0.0
    matched = False
    for number_text, unit in DURATION_TOKEN.findall(raw):
        matched = True
        qty = float(number_text)
        unit_key = unit.lower()
        if unit_key == "w":
            total_minutes += qty * 5 * 8 * 60
        elif unit_key == "d":
            total_minutes += qty * 8 * 60
        elif unit_key == "h":
            total_minutes += qty * 60
        elif unit_key == "m":
            total_minutes += qty

    if not matched:
        return None
    return int(round(total_minutes))


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


def _normalize_header(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.strip().strip('"').strip("'").lower()
    normalized = re.sub(r"[%_()/.-]+", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def _safe_get(row: dict[str, str], header_name: str | None) -> str | None:
    if not header_name:
        return None
    return row.get(header_name)


def _is_empty_row(row: list[str]) -> bool:
    return not any((cell or "").strip() for cell in row)


def _is_duplicate_header_row(row: list[str], headers: list[str]) -> bool:
    if len(headers) == 0:
        return False
    matches = 0
    comparable = 0
    for idx, header in enumerate(headers):
        header_norm = _normalize_header(header)
        cell_norm = _normalize_header(row[idx] if idx < len(row) else "")
        if not header_norm and not cell_norm:
            continue
        comparable += 1
        if header_norm == cell_norm:
            matches += 1
    if comparable == 0:
        return False
    return (matches / comparable) >= 0.8


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _pick_best(items: list[tuple[str, float]]) -> tuple[str | None, float, float]:
    if not items:
        return None, 0.0, 0.0
    ranked = sorted(items, key=lambda item: item[1], reverse=True)
    best_header, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    return best_header, best_score, second_score


def _value_score(field: str, values: list[str]) -> float:
    non_empty = [value.strip() for value in values if value is not None and value.strip()]
    if not non_empty:
        return 0.0

    if field in {"uid", "outline_level"}:
        return sum(1 for value in non_empty if _parse_int(value) is not None) / len(non_empty)
    if field in {"start", "finish", "baseline_start", "baseline_finish"}:
        return sum(1 for value in non_empty if _parse_date(value) is not None) / len(non_empty)
    if field == "duration_minutes":
        return sum(1 for value in non_empty if _parse_duration_minutes(value) is not None) / len(non_empty)
    if field == "percent_complete":
        return sum(1 for value in non_empty if _parse_float(value) is not None) / len(non_empty)
    if field == "predecessors":
        return sum(1 for value in non_empty if bool(_parse_predecessors(value))) / len(non_empty)
    if field == "is_summary":
        truthy = {"1", "0", "true", "false", "yes", "no", "y", "n"}
        return sum(1 for value in non_empty if value.strip().lower() in truthy) / len(non_empty)
    if field == "name":
        return sum(
            1
            for value in non_empty
            if _parse_date(value) is None and _parse_int(value) is None
        ) / len(non_empty)
    return 0.0


def _header_score(field: str, normalized_header: str) -> float:
    if field == "percent_complete":
        if normalized_header in PERCENT_ACTUAL_ALIASES:
            return 1.0
        if normalized_header in PERCENT_PLANNED_ALIASES:
            return 0.8
        if "percent complete" in normalized_header:
            return 0.76

    aliases = FIELD_ALIASES.get(field, [])
    if normalized_header in aliases:
        return 1.0
    if any(alias in normalized_header for alias in aliases):
        return 0.75

    header_tokens = set(normalized_header.split())
    if not header_tokens:
        return 0.0
    best_overlap = 0.0
    for alias in aliases:
        alias_tokens = set(alias.split())
        if not alias_tokens:
            continue
        overlap = len(header_tokens & alias_tokens) / len(alias_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
    return round(best_overlap * 0.6, 4)


def _resolve_requested_header(requested: str, headers: list[str]) -> str | None:
    requested_norm = _normalize_header(requested)
    if not requested_norm:
        return None
    for header in headers:
        if _normalize_header(header) == requested_norm:
            return header
    return None


def _inference_threshold(field: str) -> float:
    if field in {"name", "start", "finish"}:
        return 0.45
    if field == "uid":
        return 0.70
    return 0.35


def _build_sample_rows(headers: list[str], rows: list[list[str]], sample_limit: int = 200) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    for row in rows:
        padded = list(row[: len(headers)]) + [""] * max(0, len(headers) - len(row))
        if _is_empty_row(padded):
            continue
        if _is_duplicate_header_row(padded, headers):
            continue
        samples.append({headers[idx]: padded[idx] for idx in range(len(headers))})
        if len(samples) >= sample_limit:
            break
    return samples


def _resolve_column_map(
    headers: list[str],
    rows: list[list[str]],
    provided_map: dict[str, str] | None,
    *,
    allow_inference: bool,
) -> tuple[dict[str, str], list[str], list[str], list[tuple[str, float]]]:
    provided_map = provided_map or {}
    resolved: dict[str, str] = {}
    inferred_fields: list[str] = []
    warnings: list[str] = []
    used_headers: set[str] = set()

    samples = _build_sample_rows(headers, rows)
    column_values: dict[str, list[str]] = {header: [sample.get(header, "") for sample in samples] for header in headers}
    normalized_headers = {header: _normalize_header(header) for header in headers}

    for field, requested in provided_map.items():
        if not requested:
            continue
        actual = _resolve_requested_header(str(requested), headers)
        if actual is None:
            warnings.append(f"Configured column for '{field}' not found: '{requested}'. Falling back to auto-detection.")
            continue
        resolved[field] = actual
        used_headers.add(actual)

    scored_best: list[tuple[str, float]] = []
    if allow_inference:
        for field in INFER_FIELDS:
            if field in resolved:
                continue

            if field == "percent_complete":
                actual_header = next(
                    (header for header in headers if normalized_headers[header] in PERCENT_ACTUAL_ALIASES),
                    None,
                )
                planned_header = next(
                    (header for header in headers if normalized_headers[header] in PERCENT_PLANNED_ALIASES),
                    None,
                )
                if actual_header and planned_header:
                    warnings.append(
                        "Both actual and planned percent columns detected; using actual percent complete."
                    )
                preferred_header = actual_header or planned_header
                if preferred_header and preferred_header not in used_headers:
                    resolved[field] = preferred_header
                    inferred_fields.append(field)
                    used_headers.add(preferred_header)
                    continue

            candidates: list[tuple[str, float]] = []
            for header in headers:
                if header in used_headers:
                    continue
                h_score = _header_score(field, normalized_headers[header])
                v_score = _value_score(field, column_values[header])
                total = round((0.7 * h_score) + (0.3 * v_score), 4)
                candidates.append((header, total))

            best_header, best_score, second_score = _pick_best(candidates)
            scored_best.append((field, best_score))
            if best_header is None or best_score < _inference_threshold(field):
                continue

            resolved[field] = best_header
            inferred_fields.append(field)
            used_headers.add(best_header)
            if abs(best_score - second_score) < 0.08 and second_score > 0:
                warnings.append(
                    f"Ambiguous mapping for '{field}'; selected '{best_header}' using best-confidence match."
                )
    else:
        scored_best = [(field, 0.0) for field in INFER_FIELDS if field not in resolved]

    return resolved, inferred_fields, warnings, scored_best


def _build_tasks_from_rows(
    headers: list[str],
    data_rows: list[list[str]],
    resolved_map: dict[str, str],
) -> tuple[list[TaskRecord], int, int, bool, int]:
    tasks: list[TaskRecord] = []
    skipped_duplicate_header_rows = 0
    skipped_invalid_rows = 0
    synthetic_uid = not bool(resolved_map.get("uid"))
    synthetic_uid_rows = 0
    seen_uids: set[int] = set()
    next_uid = 1

    for row_cells in data_rows:
        row = list(row_cells[: len(headers)]) + [""] * max(0, len(headers) - len(row_cells))
        if _is_empty_row(row):
            continue

        if _is_duplicate_header_row(row, headers):
            skipped_duplicate_header_rows += 1
            continue

        row_dict = {headers[idx]: row[idx] for idx in range(len(headers))}
        name = (_safe_get(row_dict, resolved_map.get("name")) or "").strip()
        start = _parse_date(_safe_get(row_dict, resolved_map.get("start")))
        finish = _parse_date(_safe_get(row_dict, resolved_map.get("finish")))

        if not name or start is None or finish is None:
            skipped_invalid_rows += 1
            continue

        uid = _parse_int(_safe_get(row_dict, resolved_map.get("uid")))
        uid_inferred = False
        if uid is None:
            uid_inferred = True
            synthetic_uid_rows += 1
            while next_uid in seen_uids:
                next_uid += 1
            uid = next_uid
            next_uid += 1
        else:
            next_uid = max(next_uid, uid + 1)
        seen_uids.add(uid)

        task = TaskRecord(
            uid=uid,
            uid_inferred=uid_inferred,
            name=name,
            wbs=(_safe_get(row_dict, resolved_map.get("wbs")) or None) if resolved_map.get("wbs") else None,
            outline_level=_parse_int(_safe_get(row_dict, resolved_map.get("outline_level")))
            if resolved_map.get("outline_level")
            else None,
            is_summary=_parse_bool(_safe_get(row_dict, resolved_map.get("is_summary")))
            if resolved_map.get("is_summary")
            else False,
            start=start,
            finish=finish,
            duration_minutes=_parse_duration_minutes(_safe_get(row_dict, resolved_map.get("duration_minutes")))
            if resolved_map.get("duration_minutes")
            else None,
            percent_complete=_parse_float(_safe_get(row_dict, resolved_map.get("percent_complete")))
            if resolved_map.get("percent_complete")
            else None,
            predecessors=_parse_predecessors(_safe_get(row_dict, resolved_map.get("predecessors")))
            if resolved_map.get("predecessors")
            else [],
            baseline_start=_parse_date(_safe_get(row_dict, resolved_map.get("baseline_start")))
            if resolved_map.get("baseline_start")
            else None,
            baseline_finish=_parse_date(_safe_get(row_dict, resolved_map.get("baseline_finish")))
            if resolved_map.get("baseline_finish")
            else None,
        )
        tasks.append(task)

    return tasks, skipped_duplicate_header_rows, skipped_invalid_rows, synthetic_uid, synthetic_uid_rows


def _format_inference_hint(scored_best: list[tuple[str, float]]) -> str:
    items = [f"{field}={score:.2f}" for field, score in scored_best if score > 0]
    if not items:
        return "none"
    return ", ".join(items[:6])


def parse_tasks_from_csv_bytes(
    data: bytes,
    column_map: dict[str, str] | None = None,
    *,
    allow_inference: bool = True,
    return_diagnostics: bool = False,
) -> list[TaskRecord] | tuple[list[TaskRecord], CsvImportDiagnostics]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV appears empty")
    headers = [header.strip() for header in rows[0]]
    if not any(headers):
        raise ValueError("CSV header row is empty")

    resolved_map, inferred_fields, warnings, scored_best = _resolve_column_map(
        headers,
        rows[1:],
        column_map,
        allow_inference=allow_inference,
    )

    missing_required = [field for field in REQUIRED_FIELDS if not resolved_map.get(field)]
    if missing_required:
        hints = _format_inference_hint(scored_best)
        raise ValueError(
            "Unable to resolve required CSV columns: "
            f"{', '.join(missing_required)}. Available headers: {headers}. Inference hints: {hints}"
        )

    tasks, skipped_duplicate_header_rows, skipped_invalid_rows, synthetic_uid, synthetic_uid_rows = _build_tasks_from_rows(
        headers,
        rows[1:],
        resolved_map,
    )

    provided_map = column_map or {}
    has_explicit_required_mappings = any((provided_map.get(field) or "").strip() for field in REQUIRED_FIELDS)
    if not tasks and allow_inference and has_explicit_required_mappings:
        fallback_map = dict(provided_map)
        dropped_required_fields: list[str] = []
        for field in REQUIRED_FIELDS:
            if (fallback_map.get(field) or "").strip():
                dropped_required_fields.append(field)
                fallback_map.pop(field, None)

        if dropped_required_fields:
            fallback_resolved, fallback_inferred, fallback_warnings, fallback_scored = _resolve_column_map(
                headers,
                rows[1:],
                fallback_map,
                allow_inference=allow_inference,
            )
            fallback_missing_required = [field for field in REQUIRED_FIELDS if not fallback_resolved.get(field)]
            if not fallback_missing_required:
                (
                    fallback_tasks,
                    fallback_skipped_duplicate_header_rows,
                    fallback_skipped_invalid_rows,
                    fallback_synthetic_uid,
                    fallback_synthetic_uid_rows,
                ) = _build_tasks_from_rows(
                    headers,
                    rows[1:],
                    fallback_resolved,
                )
                if fallback_tasks:
                    tasks = fallback_tasks
                    resolved_map = fallback_resolved
                    inferred_fields = _unique_non_empty(inferred_fields + fallback_inferred)
                    scored_best = fallback_scored
                    warnings = _unique_non_empty(warnings + fallback_warnings)
                    warnings.append(
                        "Configured required-column mappings produced no valid rows; "
                        "auto-detected required fields and recovered task rows."
                    )
                    skipped_duplicate_header_rows = fallback_skipped_duplicate_header_rows
                    skipped_invalid_rows = fallback_skipped_invalid_rows
                    synthetic_uid = fallback_synthetic_uid
                    synthetic_uid_rows = fallback_synthetic_uid_rows

    if not tasks:
        hints = _format_inference_hint(scored_best)
        raise ValueError(
            "No valid tasks found in CSV using resolved column mappings. "
            f"Available headers: {headers}. Inference hints: {hints}"
        )

    if synthetic_uid:
        warnings.append("No reliable UID column found; using synthetic sequential UIDs for CSV rows.")
    elif synthetic_uid_rows > 0:
        warnings.append(
            f"{synthetic_uid_rows} row(s) had missing/invalid UID values and were assigned synthetic UIDs."
        )

    diagnostics = CsvImportDiagnostics(
        resolved_column_map=resolved_map,
        inferred_fields=_unique_non_empty(inferred_fields),
        warnings=_unique_non_empty(warnings),
        synthetic_uid=synthetic_uid or synthetic_uid_rows > 0,
        skipped_duplicate_header_rows=skipped_duplicate_header_rows,
        skipped_invalid_rows=skipped_invalid_rows,
    )

    if return_diagnostics:
        return tasks, diagnostics
    return tasks
