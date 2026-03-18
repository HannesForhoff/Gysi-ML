"""Integrationstests für GET /v1/sessions/{id}/spec Endpunkte (Story 4.1)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame({
        "instant": range(1, 21),
        "cnt": range(100, 120),
        "temp": [0.5] * 20,
        "dteday": ["2012-01-01"] * 20,
    })
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def client(tmp_path, csv_file):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=csv_file,
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _execute(client, session_id: str, steps: list | None = None) -> dict:
    if steps is None:
        steps = []
    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": steps}},
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# AC1: GET /v1/sessions/{session_id}/spec — aktuelle Version
# ---------------------------------------------------------------------------


def test_get_latest_spec_returns_404_when_no_run(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/spec")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "spec_not_found"
    assert body["code"] == "SPEC_NOT_FOUND"


def test_get_latest_spec_after_execute(client):
    session_id = _create_session(client)
    _execute(client, session_id, [{"type": "dedup"}])
    resp = client.get(f"/v1/sessions/{session_id}/spec")
    assert resp.status_code == 200
    body = resp.json()
    assert body["spec"] == {"steps": [{"type": "dedup"}]}


def test_get_latest_spec_response_structure(client):
    session_id = _create_session(client)
    _execute(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/spec")
    assert resp.status_code == 200
    body = resp.json()
    assert "spec_id" in body
    assert body["session_id"] == session_id
    assert "version" in body
    assert "spec" in body
    assert "created_at" in body


# ---------------------------------------------------------------------------
# AC2: GET /v1/sessions/{session_id}/spec/{version} — spezifische Version
# ---------------------------------------------------------------------------


def test_get_spec_by_version_existing(client):
    session_id = _create_session(client)
    _execute(client, session_id)
    resp = client.get(f"/v1/sessions/{session_id}/spec/v1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v1"
    assert body["session_id"] == session_id


# ---------------------------------------------------------------------------
# AC5: 404 bei unbekannter Version
# ---------------------------------------------------------------------------


def test_get_spec_by_version_not_found(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/spec/v99")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "spec_version_not_found"
    assert body["code"] == "SPEC_VERSION_NOT_FOUND"
