from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app)


def test_auto_compare_rejects_mixed_file_types():
    response = client.post(
        "/api/compare-auto",
        files={
            "left_file": ("a.xml", b"<x></x>", "application/xml"),
            "right_file": ("b.csv", b"a,b\n1,2\n", "text/csv"),
        },
        data={"include_baseline": "false", "overrides_json": "[]"},
    )

    assert response.status_code == 400
    assert "Both files must be the same type" in response.json()["error"]


def test_auto_compare_rejects_direct_pp():
    response = client.post(
        "/api/compare-auto",
        files={
            "left_file": ("a.pp", b"fake", "application/octet-stream"),
            "right_file": ("b.pp", b"fake", "application/octet-stream"),
        },
        data={"include_baseline": "false", "overrides_json": "[]"},
    )

    assert response.status_code == 400
    assert "Direct .pp parsing is not supported" in response.json()["error"]
