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

REAL_STYLE_LEFT = """Name,Duration,Start,Finish,Planned percent complete (PPC),Percent complete
Name,Duration,Start,Finish,Planned percent complete (PPC),Percent complete
Contract Programme,88w 1d,01/11/2024,21/08/2026,7.14,6.82
Enabling Works,41w 3d,31/03/2025,04/02/2026,87.39,85.29
"""

REAL_STYLE_RIGHT = """Name,Duration,Start,Finish,Planned percent complete (PPC),Percent complete
Name,Duration,Start,Finish,Planned percent complete (PPC),Percent complete
Contract Programme,89w 0d,01/11/2024,22/08/2026,7.14,6.90
Enabling Works,41w 3d,31/03/2025,04/02/2026,87.39,86.00
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


def test_auto_compare_accepts_real_style_csv_and_emits_import_warnings():
    response = asyncio.run(
        compare_auto(
            left_file=_upload("left.csv", REAL_STYLE_LEFT.encode("utf-8")),
            right_file=_upload("right.csv", REAL_STYLE_RIGHT.encode("utf-8")),
            include_baseline=False,
            overrides_json="[]",
            left_column_map_json="",
            right_column_map_json="",
        )
    )

    assert isinstance(response, dict)
    assert response["summary"]["total_left_leaf_tasks"] == 2
    assert response["summary"]["total_right_leaf_tasks"] == 2
    assert "import_warnings" in response
    assert any("synthetic sequential UIDs" in warning for warning in response["import_warnings"])
    assert any("duplicated header row" in warning for warning in response["import_warnings"])
