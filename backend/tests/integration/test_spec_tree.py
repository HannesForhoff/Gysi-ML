"""Integrationstests für GET /v1/sessions/{id}/spec/tree (Story 8.2)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings
from gysi_ml.persistence import spec_repository


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame(
        {
            "instant": range(1, 21),
            "cnt": range(100, 120),
            "temp": [0.5] * 20,
            "dteday": ["2012-01-01"] * 20,
        }
    )
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def settings(tmp_path, csv_file):
    return Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=csv_file,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _add_spec(settings, session_id: str, steps: list | None = None) -> dict:
    """Erstellt eine Spec-Version direkt über das Repository."""
    return spec_repository.create_spec_version(
        session_id=session_id,
        spec={"steps": steps or []},
        db_path=settings.db_path,
    )


# ---------------------------------------------------------------------------
# AC4: Leere Session → versions: [], active_spec_id: null
# ---------------------------------------------------------------------------


def test_spec_tree_empty_session(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["active_spec_id"] is None
    assert body["versions"] == []


# ---------------------------------------------------------------------------
# AC3: Einzelne Version → parent_spec_id: null
# ---------------------------------------------------------------------------


def test_spec_tree_single_version(client, settings):
    session_id = _create_session(client)
    _add_spec(settings, session_id)

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert len(body["versions"]) == 1

    node = body["versions"][0]
    assert node["version"] == "v1"
    assert node["parent_spec_id"] is None
    assert "spec_id" in node
    assert "created_at" in node
    assert node["has_runs"] is False
    assert body["active_spec_id"] == node["spec_id"]


# ---------------------------------------------------------------------------
# AC1 + AC2: Mehrere Versionen → korrekte parent_spec_id-Kette
# ---------------------------------------------------------------------------


def test_spec_tree_multiple_versions(client, settings):
    session_id = _create_session(client)
    _add_spec(settings, session_id, steps=[])
    _add_spec(settings, session_id, steps=[{"type": "a"}])
    _add_spec(settings, session_id, steps=[{"type": "a"}, {"type": "b"}])

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    body = resp.json()
    versions = body["versions"]
    assert len(versions) == 3

    assert versions[0]["version"] == "v1"
    assert versions[0]["parent_spec_id"] is None

    assert versions[1]["version"] == "v2"
    assert versions[1]["parent_spec_id"] == versions[0]["spec_id"]

    assert versions[2]["version"] == "v3"
    assert versions[2]["parent_spec_id"] == versions[1]["spec_id"]

    # active_spec_id zeigt auf neueste Version
    assert body["active_spec_id"] == versions[2]["spec_id"]


# ---------------------------------------------------------------------------
# AC1: has_runs und last_run_status korrekt befüllt
# ---------------------------------------------------------------------------


def test_spec_tree_has_runs_and_last_run_status(client, settings):
    import uuid
    from datetime import datetime, timezone

    from gysi_ml.persistence import run_repository

    session_id = _create_session(client)
    spec = _add_spec(settings, session_id)
    spec_id = spec["spec_id"]

    run_id = str(uuid.uuid4())
    run_repository.create_run(
        session_id=session_id,
        run_id=run_id,
        spec_version=spec["version"],
        status="completed",
        started_at=datetime.now(timezone.utc).isoformat(),
        spec_id=spec_id,
        db_path=settings.db_path,
    )

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    node = resp.json()["versions"][0]
    assert node["has_runs"] is True
    assert node["last_run_status"] == "completed"


# ---------------------------------------------------------------------------
# AC5: HTTP 404 bei unbekannter Session
# ---------------------------------------------------------------------------


def test_spec_tree_404_unknown_session(client):
    resp = client.get("/v1/sessions/does-not-exist/spec/tree")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "SESSION_NOT_FOUND"
    assert "does-not-exist" in body["detail"]
