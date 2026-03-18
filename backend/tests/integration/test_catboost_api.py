"""Integrationstests für CatBoost Feature Selection und Modellvergleich (Story 4.3)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPLIT_STEP = {"type": "split", "params": {"test_size": 0.2, "random_state": 42}}
CATBOOST_FS_STEP = {"type": "catboost_feature_selection", "params": {"top_n": 3, "random_state": 42}}
TRAIN_DT_STEP = {"type": "train_decision_tree", "params": {"max_depth": 5, "random_state": 42}}


@pytest.fixture
def csv_file(tmp_path):
    """Bikes-ähnlicher CSV mit cnt-Spalte und numerischen Features."""
    n = 50
    df = pd.DataFrame({
        "instant": range(1, n + 1),
        "temp": [0.3 + i * 0.01 for i in range(n)],
        "hum": [0.6 + (i % 10) * 0.01 for i in range(n)],
        "windspeed": [0.1 + (i % 7) * 0.02 for i in range(n)],
        "season": [float(i % 4 + 1) for i in range(n)],
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
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "CatBoost Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _execute(client, session_id: str, steps: list) -> dict:
    return client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": steps}},
    )


# ---------------------------------------------------------------------------
# CatBoost Feature Selection Pipeline
# ---------------------------------------------------------------------------

def test_catboost_feature_selection_pipeline(client):
    """Split + CatBoostFeatureSelection → completed."""
    session_id = _create_session(client)
    resp = _execute(client, session_id, [SPLIT_STEP, CATBOOST_FS_STEP])
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "run_id" in body


def test_catboost_step_in_capabilities(client):
    """GET /v1/capabilities enthält catboost_feature_selection."""
    resp = client.get("/v1/capabilities")
    assert resp.status_code == 200
    step_types = [s["type"] for s in resp.json()["steps"]]
    assert "catboost_feature_selection" in step_types


def test_step_results_contain_selected_features(client):
    """selected_features erscheint in Run-Detail step_results."""
    session_id = _create_session(client)
    exec_resp = _execute(client, session_id, [SPLIT_STEP, CATBOOST_FS_STEP])
    assert exec_resp.status_code == 200
    run_id = exec_resp.json()["run_id"]

    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    assert resp.status_code == 200
    detail = resp.json()

    step_results = detail.get("step_results", [])
    catboost_result = None
    for sr in step_results:
        if sr.get("step_type") == "catboost_feature_selection":
            catboost_result = sr
            break

    assert catboost_result is not None
    metadata = catboost_result.get("metadata", {})
    assert "selected_features" in metadata
    assert "removed_features" in metadata
    assert len(metadata["selected_features"]) == 3
