"""Reproduzierbarkeits-Tests: Zwei identische Specs → identische Ergebnisse (Story 1.5, AC 3)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings


@pytest.fixture
def csv_file(tmp_path):
    """Synthetischer Bikes-Datensatz mit 50 Zeilen für Reproduzierbarkeitstests."""
    import numpy as np
    rng = np.random.default_rng(0)
    n = 50
    df = pd.DataFrame({
        "instant": range(1, n + 1),
        "dteday": pd.date_range("2011-01-01", periods=n, freq="D").astype(str),
        "season": rng.integers(1, 5, size=n),
        "yr": rng.integers(0, 2, size=n),
        "mnth": rng.integers(1, 13, size=n),
        "hr": rng.integers(0, 24, size=n),
        "holiday": rng.integers(0, 2, size=n),
        "weekday": rng.integers(0, 7, size=n),
        "workingday": rng.integers(0, 2, size=n),
        "weathersit": rng.integers(1, 5, size=n),
        "temp": rng.uniform(0, 1, size=n),
        "atemp": rng.uniform(0, 1, size=n),
        "hum": rng.uniform(0, 1, size=n),
        "windspeed": rng.uniform(0, 1, size=n),
        "casual": rng.integers(0, 100, size=n),
        "registered": rng.integers(0, 500, size=n),
        "cnt": rng.integers(0, 600, size=n),
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
    resp = client.post("/v1/sessions", json={"name": "Repro-Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# AC3: Zwei identische Specs → identische Ergebnisse
# ---------------------------------------------------------------------------


def test_identical_specs_produce_identical_run_results(client):
    """Zwei Läufe mit derselben Spec (inkl. random_state) liefern identische step_results."""
    spec = {
        "steps": [
            {"type": "split", "params": {"test_size": 0.2, "random_state": 42}},
        ]
    }
    session_id = _create_session(client)

    resp1 = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp1.status_code == 200
    run_id_1 = resp1.json()["run_id"]

    resp2 = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp2.status_code == 200
    run_id_2 = resp2.json()["run_id"]

    detail1 = client.get(f"/v1/sessions/{session_id}/runs/{run_id_1}").json()
    detail2 = client.get(f"/v1/sessions/{session_id}/runs/{run_id_2}").json()

    assert detail1["step_results"] == detail2["step_results"]


def test_identical_specs_same_train_test_row_counts(client):
    """Gleiche test_size+random_state → gleiche Zeilenzahlen."""
    spec = {
        "steps": [
            {"type": "split", "params": {"test_size": 0.2, "random_state": 42}},
        ]
    }
    session_id = _create_session(client)

    results = []
    for _ in range(2):
        resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
        run_id = resp.json()["run_id"]
        detail = client.get(f"/v1/sessions/{session_id}/runs/{run_id}").json()
        split_meta = detail["step_results"][0]["metadata"]
        results.append(split_meta)

    assert results[0]["train_rows"] == results[1]["train_rows"]
    assert results[0]["test_rows"] == results[1]["test_rows"]


def test_split_with_random_state_produces_correct_proportions(client):
    """Split-Step mit test_size=0.2 teilt 50 Zeilen in 40 und 10 auf."""
    spec = {
        "steps": [
            {"type": "split", "params": {"test_size": 0.2, "random_state": 42}},
        ]
    }
    session_id = _create_session(client)
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    run_id = resp.json()["run_id"]
    detail = client.get(f"/v1/sessions/{session_id}/runs/{run_id}").json()
    split_meta = detail["step_results"][0]["metadata"]

    assert split_meta["train_rows"] == 40
    assert split_meta["test_rows"] == 10
    assert split_meta["train_rows"] + split_meta["test_rows"] == 50


def test_split_metadata_random_state_stored(client):
    """random_state wird in den Metadaten gespeichert."""
    spec = {
        "steps": [
            {"type": "split", "params": {"test_size": 0.2, "random_state": 7}},
        ]
    }
    session_id = _create_session(client)
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    run_id = resp.json()["run_id"]
    detail = client.get(f"/v1/sessions/{session_id}/runs/{run_id}").json()
    split_meta = detail["step_results"][0]["metadata"]
    assert split_meta["random_state"] == 7


def test_result_json_format_includes_metrics_and_artifacts(client):
    """result_json enthält step_results, metrics (leer) und artifacts (leer)."""
    spec = {"steps": []}
    session_id = _create_session(client)
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    run_id = resp.json()["run_id"]
    detail = client.get(f"/v1/sessions/{session_id}/runs/{run_id}").json()

    assert "step_results" in detail
    assert "metrics" in detail
    assert "artifacts" in detail
    assert detail["metrics"] == {}
    assert detail["artifacts"] == []
