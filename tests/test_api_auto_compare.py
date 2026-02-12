import asyncio
import io
import json

from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from backend.app import compare_auto


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


def _as_error_text(response: JSONResponse) -> str:
    return json.loads(response.body.decode("utf-8"))["error"]


def test_auto_compare_rejects_mixed_file_types():
    response = asyncio.run(
        compare_auto(
            left_file=_upload("a.xml", b"<x></x>"),
            right_file=_upload("b.csv", b"a,b\n1,2\n"),
            include_baseline=False,
            overrides_json="[]",
        )
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    assert "Both files must be the same type" in _as_error_text(response)


def test_auto_compare_rejects_direct_pp():
    response = asyncio.run(
        compare_auto(
            left_file=_upload("a.pp", b"fake"),
            right_file=_upload("b.pp", b"fake"),
            include_baseline=False,
            overrides_json="[]",
        )
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    assert "Direct .pp parsing is not supported" in _as_error_text(response)


def test_auto_compare_accepts_csv_pair():
    response = asyncio.run(
        compare_auto(
            left_file=_upload("left.csv", LEFT_CSV.encode("utf-8")),
            right_file=_upload("right.csv", RIGHT_CSV.encode("utf-8")),
            include_baseline=False,
            overrides_json="[]",
            left_column_map_json="",
            right_column_map_json="",
        )
    )

    assert isinstance(response, dict)
    assert response["summary"]["total_left_leaf_tasks"] == 2
    assert response["summary"]["total_right_leaf_tasks"] == 2
    assert "fault_allocation" in response
