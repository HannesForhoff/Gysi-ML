"""Integrationstests für Artefakt-Abruf (Story 2.2)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPLIT_STEP = {"type": "split", "params": {"test_size": 0.2, "random_state": 42}}
TRAIN_DT_STEP = {"type": "train_decision_tree", "params": {"max_depth": 5, "random_state": 42}}


@pytest.fixture
def csv_file(tmp_path):
    """Bikes-ähnlicher CSV mit cnt-Spalte und numerischen Features."""
    n = 60
    df = pd.DataFrame({
        "instant": range(1, n + 1),
        "temp": [0.3 + i * 0.01 for i in range(n)],
        "hum": [0.6 + (i % 10) * 0.01 for i in range(n)],
        "windspeed": [0.1 + (i % 7) * 0.02 for i in range(n)],
        "cnt": [float(100 + i * 10) for i in range(n)],
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
    resp = client.post("/v1/sessions", json={"name": "Artifact Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _execute_training(client, session_id: str) -> dict:
    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": [SPLIT_STEP, TRAIN_DT_STEP]}},
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# AC 4, 6: Vollständiger Flow — Training → Run Detail → Artefakt-Abruf
# ---------------------------------------------------------------------------

def test_artifact_retrieve_after_training(client):
    session_id = _create_session(client)
    exec_body = _execute_training(client, session_id)
    run_id = exec_body["run_id"]

    # Run-Detail abrufen
    run_resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    assert run_resp.status_code == 200
    run_body = run_resp.json()
    artifacts = run_body.get("artifacts", [])
    assert len(artifacts) >= 1, "Nach Training muss mindestens ein Artefakt vorhanden sein"

    # Feature-Importance-Artefakt nach Typ suchen (Split-Artefakte kommen zuerst)
    fi_artifacts = [a for a in artifacts if a["type"] == "feature_importance"]
    assert len(fi_artifacts) >= 1, "Nach Training muss ein Feature-Importance-Artefakt vorhanden sein"
    artifact_id = fi_artifacts[0]["artifact_id"]

    # Artefakt als PNG abrufen
    art_resp = client.get(f"/v1/artifacts/{artifact_id}")
    assert art_resp.status_code == 200
    assert art_resp.headers["content-type"] == "image/png"


# ---------------------------------------------------------------------------
# AC 5: 404 bei unbekannter Artefakt-ID
# ---------------------------------------------------------------------------

def test_artifact_404_unknown_id(client):
    resp = client.get("/v1/artifacts/nonexistent-id-xyz")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "artifact_not_found"
    assert body["code"] == "ARTIFACT_NOT_FOUND"


# ---------------------------------------------------------------------------
# AC 6: artifacts-Array in Run-Detail nach Training nicht leer
# ---------------------------------------------------------------------------

def test_run_detail_artifacts_array(client):
    session_id = _create_session(client)
    exec_body = _execute_training(client, session_id)
    run_id = exec_body["run_id"]

    run_resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    assert run_resp.status_code == 200
    artifacts = run_resp.json().get("artifacts", [])
    assert len(artifacts) >= 1
    art = artifacts[0]
    assert "artifact_id" in art
    assert "type" in art
    assert "created_at" in art
