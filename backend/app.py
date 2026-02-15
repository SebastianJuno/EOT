from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable

from fastapi import Body, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .attribution import apply_assignments, build_assignment_map
from .comparison import compare_tasks
from .csv_import import parse_tasks_from_csv_bytes
from .parser_bridge import MppParseError, parse_mpp
from .preview import (
    apply_preview_match_edits,
    analyze_preview_session,
    build_preview_init_response,
    build_preview_rows_response,
    create_preview_session,
    get_preview_session,
)
from .progress_jobs import ProgressJobStore
from .reporting import build_csv, build_pdf
from .schemas import (
    AttributionApplyRequest,
    CsvImportDiagnostics,
    CompareResult,
    MatchOverride,
    PreviewAnalyzeRequest,
    PreviewMatchEditRequest,
)
from .versioning import read_version
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

ProgressCallback = Callable[[float, str, str], None]

app = FastAPI(title="EOT Programme Diff Tool", version=read_version())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_RESULT: CompareResult | None = None
LAST_ASSIGNMENTS: dict[str, dict] = {}
LAST_RESULT_LOCK = threading.Lock()
PROGRESS_JOBS = ProgressJobStore(ttl_seconds=600, max_jobs=64)


def _parse_overrides(overrides_json: str) -> list[MatchOverride]:
    return [MatchOverride.model_validate(item) for item in json.loads(overrides_json)]


def _set_last_result(result: CompareResult) -> CompareResult:
    global LAST_RESULT, LAST_ASSIGNMENTS
    with LAST_RESULT_LOCK:
        LAST_RESULT = result
        LAST_ASSIGNMENTS = build_assignment_map(result.diffs, LAST_ASSIGNMENTS)
        return LAST_RESULT


def _get_assignment_map() -> dict[str, dict]:
    with LAST_RESULT_LOCK:
        return dict(LAST_ASSIGNMENTS)


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


def _emit(progress: ProgressCallback | None, pct: float, stage: str, detail: str = "") -> None:
    if progress is not None:
        progress(pct, stage, detail)


async def _read_upload_pair_bytes(left_file: UploadFile, right_file: UploadFile) -> tuple[bytes, bytes]:
    left_bytes = await left_file.read()
    right_bytes = await right_file.read()
    return left_bytes, right_bytes


def _diagnostics_to_warnings(side_label: str, diagnostics: CsvImportDiagnostics) -> list[str]:
    warnings: list[str] = []
    for item in diagnostics.warnings:
        warnings.append(f"{side_label}: {item}")
    if diagnostics.inferred_fields:
        warnings.append(
            f"{side_label}: Auto-mapped columns for {', '.join(sorted(diagnostics.inferred_fields))}."
        )
    if diagnostics.skipped_duplicate_header_rows > 0:
        warnings.append(
            f"{side_label}: Skipped {diagnostics.skipped_duplicate_header_rows} duplicated header row(s)."
        )
    if diagnostics.skipped_invalid_rows > 0:
        warnings.append(
            f"{side_label}: Skipped {diagnostics.skipped_invalid_rows} row(s) with missing required task values."
        )
    return warnings


def _parse_pair_from_bytes(
    *,
    left_filename: str | None,
    right_filename: str | None,
    left_bytes: bytes,
    right_bytes: bytes,
    left_kind: str,
    left_column_map_json: str,
    right_column_map_json: str,
    progress: ProgressCallback | None = None,
) -> tuple[list, list, list[str]]:
    _emit(progress, 20, "Parsing inputs", "Normalizing file payloads")

    if left_kind == ".mpp":
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            left_safe = left_filename or "left.mpp"
            right_safe = right_filename or "right.mpp"
            left_path = tmp / f"left_{Path(left_safe).name}"
            right_path = tmp / f"right_{Path(right_safe).name}"
            left_path.write_bytes(left_bytes)
            right_path.write_bytes(right_bytes)

            _emit(progress, 35, "Parsing inputs", "Parsing Programme A .mpp")
            left_tasks = parse_mpp(left_path, PARSER_JAR)
            _emit(progress, 55, "Parsing inputs", "Parsing Programme B .mpp")
            right_tasks = parse_mpp(right_path, PARSER_JAR)
            return left_tasks, right_tasks, []

    if left_kind == ".xml":
        _emit(progress, 40, "Parsing inputs", "Parsing Programme A XML")
        left_tasks = parse_tasks_from_project_xml_bytes(left_bytes)
        _emit(progress, 60, "Parsing inputs", "Parsing Programme B XML")
        right_tasks = parse_tasks_from_project_xml_bytes(right_bytes)
        return left_tasks, right_tasks, []

    if left_kind == ".csv":
        left_map = _parse_csv_map(left_column_map_json, "left")
        right_map = _parse_csv_map(right_column_map_json, "right")
        _emit(progress, 40, "Parsing inputs", "Parsing Programme A CSV")
        left_tasks, left_diag = parse_tasks_from_csv_bytes(
            left_bytes,
            left_map,
            allow_inference=True,
            return_diagnostics=True,
        )
        _emit(progress, 60, "Parsing inputs", "Parsing Programme B CSV")
        right_tasks, right_diag = parse_tasks_from_csv_bytes(
            right_bytes,
            right_map,
            allow_inference=True,
            return_diagnostics=True,
        )
        warnings = _diagnostics_to_warnings("Programme A", left_diag) + _diagnostics_to_warnings("Programme B", right_diag)
        return left_tasks, right_tasks, warnings

    raise ValueError(f"Unsupported file type: {left_kind}")


async def _parse_uploaded_pair(
    *,
    left_file: UploadFile,
    right_file: UploadFile,
    left_kind: str,
    left_column_map_json: str,
    right_column_map_json: str,
) -> tuple[list, list, list[str]]:
    left_bytes, right_bytes = await _read_upload_pair_bytes(left_file, right_file)
    return _parse_pair_from_bytes(
        left_filename=left_file.filename,
        right_filename=right_file.filename,
        left_bytes=left_bytes,
        right_bytes=right_bytes,
        left_kind=left_kind,
        left_column_map_json=left_column_map_json,
        right_column_map_json=right_column_map_json,
    )


def _compare_auto_operation(
    *,
    left_filename: str | None,
    right_filename: str | None,
    left_bytes: bytes,
    right_bytes: bytes,
    include_baseline: bool,
    overrides_json: str,
    left_column_map_json: str,
    right_column_map_json: str,
    progress: ProgressCallback | None = None,
) -> dict:
    _emit(progress, 5, "Validating inputs", "Checking file extensions")
    left_kind = _file_kind(left_filename)
    right_kind = _file_kind(right_filename)
    if left_kind != right_kind:
        raise ValueError(f"Both files must be the same type. Received {left_kind} and {right_kind}.")

    overrides = _parse_overrides(overrides_json)

    left_tasks, right_tasks, import_warnings = _parse_pair_from_bytes(
        left_filename=left_filename,
        right_filename=right_filename,
        left_bytes=left_bytes,
        right_bytes=right_bytes,
        left_kind=left_kind,
        left_column_map_json=left_column_map_json,
        right_column_map_json=right_column_map_json,
        progress=progress,
    )

    _emit(progress, 80, "Comparing programmes", "Running task matching and diff")
    result = compare_tasks(
        left_tasks=left_tasks,
        right_tasks=right_tasks,
        include_baseline=include_baseline,
        overrides=overrides,
        assignment_map=_get_assignment_map(),
    )
    result.import_warnings = import_warnings

    _emit(progress, 95, "Finalizing", "Preparing compare result")
    return _set_last_result(result).model_dump()


def _preview_init_operation(
    *,
    left_filename: str | None,
    right_filename: str | None,
    left_bytes: bytes,
    right_bytes: bytes,
    include_baseline: bool,
    include_summaries: bool,
    offset: int,
    limit: int,
    left_column_map_json: str,
    right_column_map_json: str,
    progress: ProgressCallback | None = None,
) -> dict:
    _emit(progress, 5, "Validating inputs", "Checking file extensions")
    left_kind = _file_kind(left_filename)
    right_kind = _file_kind(right_filename)
    if left_kind != right_kind:
        raise ValueError(f"Both files must be the same type. Received {left_kind} and {right_kind}.")

    left_tasks, right_tasks, import_warnings = _parse_pair_from_bytes(
        left_filename=left_filename,
        right_filename=right_filename,
        left_bytes=left_bytes,
        right_bytes=right_bytes,
        left_kind=left_kind,
        left_column_map_json=left_column_map_json,
        right_column_map_json=right_column_map_json,
        progress=progress,
    )

    _emit(progress, 82, "Building preview", "Creating preview session")
    session = create_preview_session(
        file_kind=left_kind,
        include_baseline=include_baseline,
        left_tasks=left_tasks,
        right_tasks=right_tasks,
        import_warnings=import_warnings,
    )
    response = build_preview_init_response(
        session,
        include_summaries=include_summaries,
        offset=offset,
        limit=limit,
    )
    _emit(progress, 95, "Finalizing", "Preparing preview payload")
    return response.model_dump()


def _preview_analyze_operation(
    payload: PreviewAnalyzeRequest,
    progress: ProgressCallback | None = None,
) -> dict:
    _emit(progress, 10, "Resolving session", "Loading preview session")
    session = get_preview_session(payload.session_id)
    _emit(progress, 65, "Analyzing preview", "Running full compare with selected matches")
    result = analyze_preview_session(session, assignment_map=_get_assignment_map())
    result.import_warnings = list(session.import_warnings)
    _emit(progress, 95, "Finalizing", "Preparing analysis result")
    return _set_last_result(result).model_dump()


def _start_progress_job(operation: str, runner: Callable[[ProgressCallback], dict]) -> str:
    job_id = PROGRESS_JOBS.create_job(operation)

    def target() -> None:
        def progress(pct: float, stage: str, detail: str) -> None:
            PROGRESS_JOBS.update_job(
                job_id,
                status="running",
                progress_pct=pct,
                stage=stage,
                detail=detail,
            )

        try:
            progress(2, "Starting", "Initializing background job")
            result = runner(progress)
            PROGRESS_JOBS.complete_job(job_id, result)
        except (ValueError, KeyError, MppParseError, json.JSONDecodeError) as exc:
            PROGRESS_JOBS.fail_job(job_id, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            PROGRESS_JOBS.fail_job(job_id, f"Unexpected error: {exc}")

    thread = threading.Thread(target=target, name=f"progress-job-{job_id}", daemon=True)
    thread.start()
    return job_id


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/progress/jobs/{job_id}")
def progress_job_status(job_id: str):
    payload = PROGRESS_JOBS.get_job(job_id)
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "Progress job not found or expired"})
    return payload


@app.post("/api/progress/compare-auto")
async def compare_auto_progress(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    include_baseline: bool = Form(False),
    overrides_json: str = Form("[]"),
    left_column_map_json: str = Form(""),
    right_column_map_json: str = Form(""),
):
    left_bytes, right_bytes = await _read_upload_pair_bytes(left_file, right_file)
    job_id = _start_progress_job(
        "compare_auto",
        lambda progress: _compare_auto_operation(
            left_filename=left_file.filename,
            right_filename=right_file.filename,
            left_bytes=left_bytes,
            right_bytes=right_bytes,
            include_baseline=include_baseline,
            overrides_json=overrides_json,
            left_column_map_json=left_column_map_json,
            right_column_map_json=right_column_map_json,
            progress=progress,
        ),
    )
    return {"job_id": job_id}


@app.post("/api/progress/preview/init")
async def preview_init_progress(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    include_baseline: bool = Form(False),
    include_summaries: bool = Form(False),
    offset: int = Form(0),
    limit: int = Form(200),
    left_column_map_json: str = Form(""),
    right_column_map_json: str = Form(""),
):
    left_bytes, right_bytes = await _read_upload_pair_bytes(left_file, right_file)
    job_id = _start_progress_job(
        "preview_init",
        lambda progress: _preview_init_operation(
            left_filename=left_file.filename,
            right_filename=right_file.filename,
            left_bytes=left_bytes,
            right_bytes=right_bytes,
            include_baseline=include_baseline,
            include_summaries=include_summaries,
            offset=offset,
            limit=limit,
            left_column_map_json=left_column_map_json,
            right_column_map_json=right_column_map_json,
            progress=progress,
        ),
    )
    return {"job_id": job_id}


@app.post("/api/progress/preview/analyze")
def preview_analyze_progress(payload: PreviewAnalyzeRequest = Body(...)):
    job_id = _start_progress_job(
        "preview_analyze",
        lambda progress: _preview_analyze_operation(payload, progress=progress),
    )
    return {"job_id": job_id}


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
        left_bytes, right_bytes = await _read_upload_pair_bytes(left_file, right_file)
        return _compare_auto_operation(
            left_filename=left_file.filename,
            right_filename=right_file.filename,
            left_bytes=left_bytes,
            right_bytes=right_bytes,
            include_baseline=include_baseline,
            overrides_json=overrides_json,
            left_column_map_json=left_column_map_json,
            right_column_map_json=right_column_map_json,
        )
    except (json.JSONDecodeError, ValueError, MppParseError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/preview/init")
async def preview_init(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    include_baseline: bool = Form(False),
    include_summaries: bool = Form(False),
    offset: int = Form(0),
    limit: int = Form(200),
    left_column_map_json: str = Form(""),
    right_column_map_json: str = Form(""),
):
    try:
        left_bytes, right_bytes = await _read_upload_pair_bytes(left_file, right_file)
        return _preview_init_operation(
            left_filename=left_file.filename,
            right_filename=right_file.filename,
            left_bytes=left_bytes,
            right_bytes=right_bytes,
            include_baseline=include_baseline,
            include_summaries=include_summaries,
            offset=offset,
            limit=limit,
            left_column_map_json=left_column_map_json,
            right_column_map_json=right_column_map_json,
        )
    except (ValueError, MppParseError, KeyError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/api/preview/rows")
def preview_rows(
    session_id: str,
    include_summaries: bool = False,
    offset: int = 0,
    limit: int = 200,
):
    try:
        session = get_preview_session(session_id)
        response = build_preview_rows_response(
            session,
            include_summaries=include_summaries,
            offset=offset,
            limit=limit,
        )
        return response.model_dump()
    except (ValueError, KeyError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/preview/matches/apply")
def preview_matches_apply(payload: PreviewMatchEditRequest = Body(...)):
    try:
        session = get_preview_session(payload.session_id)
        apply_preview_match_edits(session, payload.edits)
        response = build_preview_rows_response(
            session,
            include_summaries=payload.include_summaries,
            offset=payload.offset,
            limit=payload.limit,
        )
        return response.model_dump()
    except (ValueError, KeyError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/preview/analyze")
def preview_analyze(payload: PreviewAnalyzeRequest = Body(...)):
    try:
        return _preview_analyze_operation(payload)
    except (ValueError, KeyError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/attribution/apply")
def attribution_apply(payload: AttributionApplyRequest = Body(...)):
    global LAST_RESULT, LAST_ASSIGNMENTS

    with LAST_RESULT_LOCK:
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
    with LAST_RESULT_LOCK:
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
    with LAST_RESULT_LOCK:
        if LAST_RESULT is None:
            return JSONResponse(status_code=400, content={"error": "No comparison result available"})
        result = LAST_RESULT

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        pdf_path = Path(tmp_file.name)

    build_pdf(result, pdf_path)
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename="evidence-pack.pdf",
    )


FRONTEND_DIR = Path(os.environ.get("EOT_FRONTEND_DIR", str(BASE_DIR / "frontend")))
if FRONTEND_DIR.exists():
    # Serve the frontend from the same process to avoid running a second local server.
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
