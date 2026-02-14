from __future__ import annotations

import asyncio
import io
import time

from starlette.datastructures import UploadFile

import backend.app as app_module
from backend.app import (
    compare_auto_progress,
    preview_analyze_progress,
    preview_init,
    preview_init_progress,
    progress_job_status,
)
from backend.progress_jobs import ProgressJobStore
from backend.schemas import PreviewAnalyzeRequest


LEFT_CSV = """Unique ID,Task Name,Start,Finish,Duration (mins),% Complete,Predecessors,Summary,Baseline Start,Baseline Finish
1,Excavate,2025-01-01,2025-01-03,1440,100,,0,2025-01-01,2025-01-03
2,Pour Concrete,2025-01-04,2025-01-06,1440,50,1FS,0,2025-01-04,2025-01-06
"""

RIGHT_CSV = """Unique ID,Task Name,Start,Finish,Duration (mins),% Complete,Predecessors,Summary,Baseline Start,Baseline Finish
10,Excavate,2025-01-01,2025-01-03,1440,100,,0,2025-01-01,2025-01-03
20,Pour Concrete,2025-01-05,2025-01-07,1440,30,10FS,0,2025-01-05,2025-01-07
"""


def _upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


def _wait_job(job_id: str, timeout_seconds: float = 4.0):
    snapshots = []
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = progress_job_status(job_id)
        snapshots.append(payload)
        if payload["status"] in {"completed", "failed"}:
            return payload, snapshots
        time.sleep(0.02)
    raise AssertionError(f"Job did not complete in time: {job_id}")


def test_preview_init_progress_job_completes():
    started = asyncio.run(
        preview_init_progress(
            left_file=_upload("left.csv", LEFT_CSV.encode("utf-8")),
            right_file=_upload("right.csv", RIGHT_CSV.encode("utf-8")),
            include_baseline=False,
            include_summaries=False,
            offset=0,
            limit=200,
            left_column_map_json="",
            right_column_map_json="",
        )
    )
    payload, _snapshots = _wait_job(started["job_id"])
    assert payload["status"] == "completed"
    assert payload["result"]["session"]["file_kind"] == ".csv"
    assert "rows" in payload["result"]


def test_compare_progress_job_completes():
    started = asyncio.run(
        compare_auto_progress(
            left_file=_upload("left.csv", LEFT_CSV.encode("utf-8")),
            right_file=_upload("right.csv", RIGHT_CSV.encode("utf-8")),
            include_baseline=False,
            overrides_json="[]",
            left_column_map_json="",
            right_column_map_json="",
        )
    )
    payload, _snapshots = _wait_job(started["job_id"])
    assert payload["status"] == "completed"
    assert payload["result"]["summary"]["total_left_leaf_tasks"] == 2
    assert "fault_allocation" in payload["result"]


def test_preview_analyze_progress_job_completes():
    init_payload = asyncio.run(
        preview_init(
            left_file=_upload("left.csv", LEFT_CSV.encode("utf-8")),
            right_file=_upload("right.csv", RIGHT_CSV.encode("utf-8")),
            include_baseline=False,
            include_summaries=False,
            offset=0,
            limit=200,
            left_column_map_json="",
            right_column_map_json="",
        )
    )
    session_id = init_payload["session"]["session_id"]

    started = preview_analyze_progress(PreviewAnalyzeRequest(session_id=session_id))
    payload, _snapshots = _wait_job(started["job_id"])
    assert payload["status"] == "completed"
    assert payload["result"]["summary"]["total_left_leaf_tasks"] == 2


def test_progress_job_reports_failed_state_for_mixed_types():
    started = asyncio.run(
        compare_auto_progress(
            left_file=_upload("left.xml", b"<x></x>"),
            right_file=_upload("right.csv", b"a,b\n1,2\n"),
            include_baseline=False,
            overrides_json="[]",
            left_column_map_json="",
            right_column_map_json="",
        )
    )
    payload, _snapshots = _wait_job(started["job_id"])
    assert payload["status"] == "failed"
    assert "Both files must be the same type" in (payload["error"] or "")


def test_progress_states_are_monotonic_and_include_stage(monkeypatch):
    original_operation = app_module._compare_auto_operation

    def fake_operation(*, progress=None, **_kwargs):
        if progress is not None:
            progress(10, "Validating", "Checking filenames")
            time.sleep(0.05)
            progress(70, "Comparing", "Building evidence")
            time.sleep(0.05)
        return {"ok": True}

    monkeypatch.setattr(app_module, "_compare_auto_operation", fake_operation)
    try:
        started = asyncio.run(
            compare_auto_progress(
                left_file=_upload("left.csv", LEFT_CSV.encode("utf-8")),
                right_file=_upload("right.csv", RIGHT_CSV.encode("utf-8")),
                include_baseline=False,
                overrides_json="[]",
                left_column_map_json="",
                right_column_map_json="",
            )
        )
        payload, snapshots = _wait_job(started["job_id"])
    finally:
        monkeypatch.setattr(app_module, "_compare_auto_operation", original_operation)

    rank = {"queued": 0, "running": 1, "completed": 2, "failed": 2}
    observed = [rank[snapshot["status"]] for snapshot in snapshots]
    assert observed == sorted(observed)
    assert all(isinstance(snapshot["stage"], str) for snapshot in snapshots)
    assert all(isinstance(snapshot["progress_pct"], float) for snapshot in snapshots)
    assert payload["status"] == "completed"


def test_progress_store_ttl_cleanup():
    store = ProgressJobStore(ttl_seconds=1, max_jobs=8)
    job_id = store.create_job("test")
    assert store.get_job(job_id) is not None
    store._jobs[job_id].updated_at -= 2  # Force job to be older than TTL.
    store.cleanup()
    assert store.get_job(job_id) is None
