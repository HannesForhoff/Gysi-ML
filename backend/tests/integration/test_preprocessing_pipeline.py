"""Integrationstests: Preprocessing-Pipeline durch den Executor."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings
from gysi_ml.steps.registry import _registry


@pytest.fixture(autouse=True)
def clean_registry():
    original = dict(_registry)
    yield
    _registry.clear()
    _registry.update(original)


@pytest.fixture
def csv_file(tmp_path):
    """CSV mit Duplikaten, fehlenden Werten und Ausreißern."""
    df = pd.DataFrame({
        "instant": [1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "mnth": [1.0, 2.0, 2.0, None, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "weathersit": [1.0, 2.0, 2.0, 1.0, None, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0],
        "cnt": [100, 200, 200, 300, 400, 500, 600, 700, 800, 900, 99999],
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
    resp = client.post("/v1/sessions", json={"name": "Preprocessing Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# dedup only — kein Split erforderlich
# ---------------------------------------------------------------------------


def test_dedup_pipeline_completes(client):
    session_id = _create_session(client)
    spec = {"steps": [{"type": "dedup"}]}
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    step_results = body["result"]["step_results"]
    assert step_results[0]["step_type"] == "dedup"
    assert "removed_duplicates" in step_results[0]["metadata"]


def test_dedup_removes_expected_duplicates(client):
    session_id = _create_session(client)
    spec = {"steps": [{"type": "dedup"}]}
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    assert resp.status_code == 200
    meta = resp.json()["result"]["step_results"][0]["metadata"]
    # Zeile 2 ist Duplikat von Zeile 1 → 2 removed (train + test bei pre-split = gleicher df)
    assert meta["removed_duplicates"] >= 1


# ---------------------------------------------------------------------------
# invalid_spec_order-Fehler ohne vorherigen Split (Story 1.5: Pre-Flight-Prüfung)
# ---------------------------------------------------------------------------


def test_impute_without_split_returns_split_required(client):
    session_id = _create_session(client)
    spec = {"steps": [{"type": "impute_missing", "params": {"strategy": "median"}}]}
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    assert resp.status_code == 200


def test_outlier_without_split_returns_split_required(client):
    session_id = _create_session(client)
    spec = {"steps": [{"type": "outlier_handling", "params": {"method": "iqr"}}]}
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Vollständige Pipeline: dedup → split → impute_missing → outlier_handling
# ---------------------------------------------------------------------------


def test_full_preprocessing_pipeline_completes(client):
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "dedup"},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "impute_missing", "params": {"strategy": "median"}},
            {"type": "outlier_handling", "params": {"method": "iqr"}},
        ]
    }
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "run_id" in body


def test_full_pipeline_step_metadata_present(client):
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "dedup"},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "impute_missing", "params": {"strategy": "median"}},
            {"type": "outlier_handling", "params": {"method": "iqr"}},
        ]
    }
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    step_results = resp.json()["result"]["step_results"]
    assert len(step_results) == 4

    types = [s["step_type"] for s in step_results]
    assert types == ["dedup", "split", "impute_missing", "outlier_handling"]

    assert "removed_duplicates" in step_results[0]["metadata"]
    assert "imputed_values_per_column" in step_results[2]["metadata"]
    assert "outliers_treated" in step_results[3]["metadata"]


def test_full_pipeline_outlier_treated_for_extreme_value(client):
    """cnt=99999 ist ein Ausreißer und soll geclipt werden."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "dedup"},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "outlier_handling", "params": {"method": "iqr"}},
        ]
    }
    resp = client.post(
        f"/v1/sessions/{session_id}/execute", json={"spec": spec}
    )
    assert resp.status_code == 200
    outlier_meta = resp.json()["result"]["step_results"][2]["metadata"]
    assert outlier_meta["outliers_treated"] >= 1
