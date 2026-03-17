"""Integrationstests für Decision-Tree-Training (Story 2.1)."""
import time

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
    n = 50
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
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "DT Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _execute(client, session_id: str, steps: list) -> dict:
    return client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": steps}},
    )


# ---------------------------------------------------------------------------
# AC 5: Vollständige Pipeline — POST execute + GET run detail
# ---------------------------------------------------------------------------

def test_full_pipeline_with_decision_tree(client):
    session_id = _create_session(client)
    resp = _execute(client, session_id, [SPLIT_STEP, TRAIN_DT_STEP])
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "run_id" in body


def test_run_detail_contains_metrics(client):
    session_id = _create_session(client)
    exec_resp = _execute(client, session_id, [SPLIT_STEP, TRAIN_DT_STEP])
    assert exec_resp.status_code == 200
    run_id = exec_resp.json()["run_id"]

    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    assert resp.status_code == 200
    detail = resp.json()

    metrics = detail.get("metrics")
    assert metrics is not None
    assert "rmse" in metrics and "mae" in metrics and "r2" in metrics
    assert isinstance(metrics["rmse"], float)
    assert isinstance(metrics["mae"], float)
    assert isinstance(metrics["r2"], float)


# ---------------------------------------------------------------------------
# AC 6: split_required_before_training-Fehler
# ---------------------------------------------------------------------------

def test_split_required_error(client):
    session_id = _create_session(client)
    resp = _execute(client, session_id, [TRAIN_DT_STEP])
    body = resp.json()
    assert body.get("code") == "INVALID_SPEC_ORDER"


# ---------------------------------------------------------------------------
# AC 7: Performance < 10 s (pytest.mark.slow — läuft nur mit realem Datensatz)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_performance_under_10s(tmp_path):
    """Läuft nur mit realem Datensatz (17.379 Zeilen) — ggf. per -m slow aktivieren."""
    import os
    from pathlib import Path
    _project_root = Path(__file__).parents[3]
    real_csv = os.environ.get(
        "BIKES_CSV_PATH",
        str(_project_root / "data" / "raw" / "bikes.csv"),
    )
    if not os.path.exists(real_csv):
        pytest.skip("Realer Datensatz nicht verfügbar")

    settings = Settings(
        db_path=str(tmp_path / "perf_test.db"),
        data_path=real_csv,
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        resp = c.post("/v1/sessions", json={"name": "Perf"})
        session_id = resp.json()["session_id"]

        start = time.time()
        exec_resp = c.post(
            f"/v1/sessions/{session_id}/execute",
            json={"spec": {"steps": [SPLIT_STEP, TRAIN_DT_STEP]}},
        )
        elapsed = time.time() - start

    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "completed"
    assert elapsed < 10.0, f"Training dauerte {elapsed:.2f}s — Limit 10s überschritten"
