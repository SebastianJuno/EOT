from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .attribution import apply_assignments, build_assignment_map
from .comparison import compare_tasks
from .csv_import import parse_tasks_from_csv_bytes
from .parser_bridge import MppParseError, parse_mpp
from .reporting import build_csv, build_pdf
from .schemas import AttributionApplyRequest, CompareResult, MatchOverride
from .xml_import import parse_tasks_from_project_xml_bytes

BASE_DIR = Path(__file__).resolve().parent.parent
PARSER_JAR = Path(
    os.environ.get(
        "EOT_PARSER_JAR",
        str(BASE_DIR / "java-parser" / "target" / "mpp-extractor-1.0.0-jar-with-dependencies.jar"),
    )
)

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

app = FastAPI(title="EOT Programme Diff Tool", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_RESULT: CompareResult | None = None
LAST_ASSIGNMENTS: dict[str, dict] = {}


def _parse_overrides(overrides_json: str) -> list[MatchOverride]:
    return [MatchOverride.model_validate(item) for item in json.loads(overrides_json)]


def _set_last_result(result: CompareResult) -> CompareResult:
    global LAST_RESULT, LAST_ASSIGNMENTS
    LAST_RESULT = result
    LAST_ASSIGNMENTS = build_assignment_map(result.diffs, LAST_ASSIGNMENTS)
    return LAST_RESULT


def _file_kind(filename: str | None) -> str:
    if not filename or "." not in filename:
        raise ValueError("File extension missing. Supported: .mpp, .xml, .csv")
    ext = Path(filename).suffix.lower()
    if ext in {".mpp", ".xml", ".csv"}:
        return ext
    if ext == ".pp":
        raise ValueError("Direct .pp parsing is not supported in v1. Export Asta programmes to CSV and upload .csv files.")
    raise ValueError(f"Unsupported file extension: {ext}. Supported: .mpp, .xml, .csv")


def _parse_csv_map(raw: str | None, side: str) -> dict:
    if not raw:
        return dict(DEFAULT_CSV_COLUMN_MAP)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {side} CSV mapping JSON: {exc}") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/compare-auto")
async def compare_auto(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    include_baseline: bool = Form(False),
    overrides_json: str = Form("[]"),
    left_column_map_json: str = Form(""),
    right_column_map_json: str = Form(""),
):
    try:
        left_kind = _file_kind(left_file.filename)
        right_kind = _file_kind(right_file.filename)
        if left_kind != right_kind:
            raise ValueError(
                f"Both files must be the same type. Received {left_kind} and {right_kind}."
            )

        overrides = _parse_overrides(overrides_json)
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    try:
        if left_kind == ".mpp":
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp = Path(tmp_dir)
                left_path = tmp / f"left_{left_file.filename}"
                right_path = tmp / f"right_{right_file.filename}"
                left_path.write_bytes(await left_file.read())
                right_path.write_bytes(await right_file.read())
                left_tasks = parse_mpp(left_path, PARSER_JAR)
                right_tasks = parse_mpp(right_path, PARSER_JAR)
        elif left_kind == ".xml":
            left_tasks = parse_tasks_from_project_xml_bytes(await left_file.read())
            right_tasks = parse_tasks_from_project_xml_bytes(await right_file.read())
        elif left_kind == ".csv":
            left_map = _parse_csv_map(left_column_map_json, "left")
            right_map = _parse_csv_map(right_column_map_json, "right")
            left_tasks = parse_tasks_from_csv_bytes(await left_file.read(), left_map)
            right_tasks = parse_tasks_from_csv_bytes(await right_file.read(), right_map)
        else:
            return JSONResponse(status_code=400, content={"error": f"Unsupported file type: {left_kind}"})

        result = compare_tasks(
            left_tasks=left_tasks,
            right_tasks=right_tasks,
            include_baseline=include_baseline,
            overrides=overrides,
            assignment_map=LAST_ASSIGNMENTS,
        )
        return _set_last_result(result).model_dump()
    except (ValueError, MppParseError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/attribution/apply")
def attribution_apply(payload: AttributionApplyRequest = Body(...)):
    global LAST_RESULT, LAST_ASSIGNMENTS

    if LAST_RESULT is None:
        return JSONResponse(status_code=400, content={"error": "No comparison result available"})

    LAST_RESULT, LAST_ASSIGNMENTS = apply_assignments(
        LAST_RESULT,
        assignments=payload.assignments,
        bulk=payload.bulk,
        assignment_map=LAST_ASSIGNMENTS,
    )
    return LAST_RESULT.model_dump()


@app.get("/api/export/csv")
def export_csv():
    if LAST_RESULT is None:
        return JSONResponse(status_code=400, content={"error": "No comparison result available"})
    data = build_csv(LAST_RESULT)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="evidence-pack.csv"'},
    )


@app.get("/api/export/pdf")
def export_pdf():
    if LAST_RESULT is None:
        return JSONResponse(status_code=400, content={"error": "No comparison result available"})

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        pdf_path = Path(tmp_file.name)

    build_pdf(LAST_RESULT, pdf_path)
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename="evidence-pack.pdf",
    )


FRONTEND_DIR = Path(os.environ.get("EOT_FRONTEND_DIR", str(BASE_DIR / "frontend")))
if FRONTEND_DIR.exists():
    # Serve the frontend from the same process to avoid running a second local server.
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
