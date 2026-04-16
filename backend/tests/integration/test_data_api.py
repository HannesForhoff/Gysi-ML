"""Integrationstests für GET /v1/sessions/{session_id}/runs/{run_id}/data (Story DV-1.2, DV-1.3)."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame({
        "instant": range(1, 201),   # 200 Zeilen für Paginierungstest
        "cnt": range(100, 300),
        "temp": [0.5] * 200,
        "dteday": ["2012-01-01"] * 200,
    })
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def client(tmp_path, csv_file):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=csv_file,
        artifacts_path=str(tmp_path / "artifacts"),
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "DataTest"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _run_pipeline(client, session_id: str) -> str:
    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": []}},
    )
    assert resp.status_code == 200
    return resp.json()["run_id"]


# ---------------------------------------------------------------------------
# AC1: HTTP 200 + korrekte Response-Felder
# ---------------------------------------------------------------------------

def test_get_data_returns_200_with_required_fields(client):
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "columns" in body
    assert "rows" in body
    assert "total_rows" in body
    assert "offset" in body
    assert "limit" in body
    assert "is_split" in body
    assert "column_stats" in body  # L1-Fix: AC1 verlangt column_stats im Response


# ---------------------------------------------------------------------------
# AC2: Korrekte Paginierung
# ---------------------------------------------------------------------------

def test_get_data_pagination_offset_0(client):
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) == 10
    assert body["offset"] == 0
    assert body["limit"] == 10


def test_get_data_pagination_offset_10(client):
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    r0 = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10").json()
    r1 = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=10&limit=10").json()
    # Zeilen dürfen sich nicht überschneiden
    assert r0["rows"][0] != r1["rows"][0]
    assert r1["offset"] == 10


# ---------------------------------------------------------------------------
# AC3: column_stats nur bei offset==0
# ---------------------------------------------------------------------------

def test_column_stats_present_at_offset_0(client):
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10")
    body = resp.json()
    assert body["column_stats"] is not None


def test_column_stats_absent_at_offset_nonzero(client):
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=10&limit=10")
    body = resp.json()
    assert body["column_stats"] is None


# ---------------------------------------------------------------------------
# AC4: limit wird auf 1000 geclampt
# ---------------------------------------------------------------------------

def test_limit_is_clamped_to_1000(client):
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=9999")
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 1000


# ---------------------------------------------------------------------------
# AC5: 404 bei fehlendem Run / Snapshot
# ---------------------------------------------------------------------------

def test_returns_404_if_run_not_found(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/runs/nonexistent-run-id/data")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] in ("RUN_NOT_FOUND", "SNAPSHOT_NOT_FOUND")


def test_returns_404_if_snapshot_missing(client, tmp_path):
    """M2-Fix: Run ist in DB, aber Parquet-Snapshot fehlt → SNAPSHOT_NOT_FOUND."""
    import sqlite3
    import uuid
    from gysi_ml.persistence.schema import create_all_tables

    db_path = str(tmp_path / "test_snap.db")
    create_all_tables(db_path)
    run_id = str(uuid.uuid4())
    session_id_direct = str(uuid.uuid4())

    con = sqlite3.connect(db_path)
    now = "2026-01-01T00:00:00"
    con.execute(
        "INSERT INTO sessions (session_id, name, created_at) VALUES (?, ?, ?)",
        (session_id_direct, "snap-test", now),
    )
    con.execute(
        "INSERT INTO runs (run_id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
        (run_id, session_id_direct, "completed", now),
    )
    con.commit()
    con.close()

    settings = __import__("gysi_ml.config", fromlist=["Settings"]).Settings(
        db_path=db_path,
        data_path=str(tmp_path / "bikes.csv"),
        artifacts_path=str(tmp_path / "no_artifacts"),
    )
    from gysi_ml.api.app import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app(settings=settings)) as c:
        resp = c.get(f"/v1/sessions/{session_id_direct}/runs/{run_id}/data")
    assert resp.status_code == 404
    assert resp.json()["code"] == "SNAPSHOT_NOT_FOUND"


# ---------------------------------------------------------------------------
# AC6: 404 bei falscher Session
# ---------------------------------------------------------------------------

def test_returns_404_for_wrong_session(client):
    session_a = _create_session(client)
    session_b = _create_session(client)
    run_id = _run_pipeline(client, session_a)
    # Run gehört zu session_a, aber wir fragen session_b
    resp = client.get(f"/v1/sessions/{session_b}/runs/{run_id}/data?offset=0&limit=10")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC7: Performance < 500 ms bei limit=100
# ---------------------------------------------------------------------------

def test_response_time_under_500ms(client):
    """H1-Fix: AC7 — Endpunkt muss bei limit=100 in <500ms antworten."""
    import time

    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    start = time.monotonic()
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=100")
    elapsed_ms = (time.monotonic() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 500, f"Response dauerte {elapsed_ms:.0f} ms — AC7 verlangt < 500 ms"


# ---------------------------------------------------------------------------
# DV-1.3: CSV-Download-Endpunkt
# ---------------------------------------------------------------------------

def test_csv_download_returns_200_with_csv_content_type(client):
    """AC1: HTTP 200 + Content-Type text/csv."""
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data/download")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_csv_download_has_content_disposition_header(client):
    """AC2: Content-Disposition mit korrektem Dateinamen."""
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data/download")
    assert resp.status_code == 200
    content_disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in content_disposition
    assert f"gysi_data_{run_id[:8]}.csv" in content_disposition


def test_csv_download_body_is_valid_csv_with_header(client):
    """AC3: Body enthält valides CSV mit Header-Zeile und Datensatz."""
    session_id = _create_session(client)
    run_id = _run_pipeline(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data/download")
    assert resp.status_code == 200
    lines = resp.text.strip().splitlines()
    assert len(lines) >= 2
    header = lines[0].split(",")
    assert "instant" in header
    assert "cnt" in header


def test_csv_download_returns_404_if_no_snapshot(client):
    """AC4: 404 wenn kein Run / Snapshot existiert."""
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/runs/nonexistent-run-id/data/download")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] in ("RUN_NOT_FOUND", "SNAPSHOT_NOT_FOUND")


def test_csv_download_returns_404_for_wrong_session(client):
    """AC5: 404 wenn Run zu anderer Session gehört."""
    session_a = _create_session(client)
    session_b = _create_session(client)
    run_id = _run_pipeline(client, session_a)
    resp = client.get(f"/v1/sessions/{session_b}/runs/{run_id}/data/download")
    assert resp.status_code == 404


def test_csv_download_returns_404_if_snapshot_missing(client, tmp_path):
    """AC4 (SNAPSHOT_NOT_FOUND): Run existiert in DB, aber .parquet-Datei fehlt."""
    import sqlite3
    import uuid
    from gysi_ml.persistence.schema import create_all_tables

    db_path = str(tmp_path / "test_dl_snap.db")
    create_all_tables(db_path)
    run_id = str(uuid.uuid4())
    session_id_direct = str(uuid.uuid4())

    con = sqlite3.connect(db_path)
    now = "2026-01-01T00:00:00"
    con.execute(
        "INSERT INTO sessions (session_id, name, created_at) VALUES (?, ?, ?)",
        (session_id_direct, "dl-snap-test", now),
    )
    con.execute(
        "INSERT INTO runs (run_id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
        (run_id, session_id_direct, "completed", now),
    )
    con.commit()
    con.close()

    settings = __import__("gysi_ml.config", fromlist=["Settings"]).Settings(
        db_path=db_path,
        data_path=str(tmp_path / "bikes.csv"),
        artifacts_path=str(tmp_path / "no_artifacts"),
    )
    from gysi_ml.api.app import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app(settings=settings)) as c:
        resp = c.get(f"/v1/sessions/{session_id_direct}/runs/{run_id}/data/download")
    assert resp.status_code == 404
    assert resp.json()["code"] == "SNAPSHOT_NOT_FOUND"
