import asyncio
import io
import json

from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from backend.app import preview_analyze, preview_init, preview_matches_apply, preview_rows
from backend.schemas import PreviewAnalyzeRequest, PreviewMatchEditRequest


LEFT_CSV = """Unique ID,Task Name,Start,Finish,Duration (mins),% Complete,Predecessors,Summary,Baseline Start,Baseline Finish
100,Summary A,2025-01-01,2025-01-10,0,0,,1,2025-01-01,2025-01-10
1,Excavate,2025-01-01,2025-01-03,1440,100,,0,2025-01-01,2025-01-03
2,Pour Concrete,2025-01-04,2025-01-06,1440,50,1FS,0,2025-01-04,2025-01-06
"""

RIGHT_CSV = """Unique ID,Task Name,Start,Finish,Duration (mins),% Complete,Predecessors,Summary,Baseline Start,Baseline Finish
200,Summary A,2025-01-01,2025-01-11,0,0,,1,2025-01-01,2025-01-11
10,Excavate,2025-01-01,2025-01-03,1440,100,,0,2025-01-01,2025-01-03
20,Pour Concrete,2025-01-05,2025-01-07,1440,30,10FS,0,2025-01-05,2025-01-07
"""


def _upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


def _as_error_text(response: JSONResponse) -> str:
    return json.loads(response.body.decode("utf-8"))["error"]


def _init_preview(include_summaries: bool = False):
    return asyncio.run(
        preview_init(
            left_file=_upload("left.csv", LEFT_CSV.encode("utf-8")),
            right_file=_upload("right.csv", RIGHT_CSV.encode("utf-8")),
            include_baseline=False,
            include_summaries=include_summaries,
            offset=0,
            limit=200,
            left_column_map_json="",
            right_column_map_json="",
        )
    )


def test_preview_init_accepts_csv_pair_and_returns_session():
    response = _init_preview()
    assert isinstance(response, dict)
    assert response["session"]["file_kind"] == ".csv"
    assert response["session"]["include_summaries"] is False
    assert len(response["rows"]) >= 2
    assert len(response["left_leaf_options"]) == 2
    assert len(response["right_leaf_options"]) == 2

    matched = [row for row in response["rows"] if row["left"] and row["right"]]
    assert any(row["left"]["uid"] == 1 and row["right"]["uid"] == 10 for row in matched)


def test_preview_rows_can_include_summary_rows():
    init_response = _init_preview(include_summaries=False)
    session_id = init_response["session"]["session_id"]

    rows_response = preview_rows(
        session_id=session_id,
        include_summaries=True,
        offset=0,
        limit=200,
    )
    assert isinstance(rows_response, dict)
    assert rows_response["session"]["include_summaries"] is True
    assert any(row["row_key"].startswith("summary:") for row in rows_response["rows"])


def test_preview_apply_edit_updates_alignment_and_analyze_uses_override():
    init_response = _init_preview()
    session_id = init_response["session"]["session_id"]

    apply_response = preview_matches_apply(
        PreviewMatchEditRequest(
            session_id=session_id,
            edits=[{"left_uid": 1, "right_uid": 20}],
            include_summaries=False,
            offset=0,
            limit=200,
        )
    )
    assert isinstance(apply_response, dict)
    matched = [row for row in apply_response["rows"] if row["left"] and row["right"]]
    assert any(row["left"]["uid"] == 1 and row["right"]["uid"] == 20 for row in matched)

    analyze_response = preview_analyze(PreviewAnalyzeRequest(session_id=session_id))
    assert isinstance(analyze_response, dict)
    assert "summary" in analyze_response
    assert "fault_allocation" in analyze_response
    assert any(
        diff["left_uid"] == 1 and diff["right_uid"] == 20 and diff["status"] == "changed"
        for diff in analyze_response["diffs"]
    )


def test_preview_init_rejects_mixed_file_types():
    response = asyncio.run(
        preview_init(
            left_file=_upload("a.xml", b"<x></x>"),
            right_file=_upload("b.csv", b"a,b\n1,2\n"),
            include_baseline=False,
            include_summaries=False,
            offset=0,
            limit=200,
            left_column_map_json="",
            right_column_map_json="",
        )
    )
    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    assert "Both files must be the same type" in _as_error_text(response)


def test_preview_init_rejects_direct_pp():
    response = asyncio.run(
        preview_init(
            left_file=_upload("a.pp", b"fake"),
            right_file=_upload("b.pp", b"fake"),
            include_baseline=False,
            include_summaries=False,
            offset=0,
            limit=200,
            left_column_map_json="",
            right_column_map_json="",
        )
    )
    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    assert "Direct .pp parsing is not supported" in _as_error_text(response)
