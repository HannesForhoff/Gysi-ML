"""Integration-Test: Vollständige Preprocessing-Pipeline mit allen Story-1.4-Steps."""
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
    """
    Bikes-ähnlicher CSV mit:
    - dteday (ISO-Datum) → wird durch time_feature_encoding entfernt
    - season (kategorisch, string) → wird durch encode_categorical encodiert
    - weathersit (kategorisch mit seltener Kategorie) → rare_category_bucketing
    - cnt und cnt_dup (identisch = hohe Korrelation) → correlation_filter entfernt cnt_dup
    """
    n = 25  # genug Zeilen für 80/20-Split (>= 5 im Test)
    df = pd.DataFrame({
        "instant": range(1, n + 1),
        "dteday": pd.date_range("2020-01-01", periods=n, freq="D").astype(str),
        "season": ["spring"] * 12 + ["summer"] * 10 + ["fall"] * 2 + ["winter"] * 1,
        "weathersit": ["clear"] * 20 + ["cloudy"] * 4 + ["storm"] * 1,
        "cnt": [float(i * 100) for i in range(1, n + 1)],
        "cnt_dup": [float(i * 100) for i in range(1, n + 1)],  # identisch mit cnt
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
    resp = client.post("/v1/sessions", json={"name": "Full Pipeline Test 1.4"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Vollständige Pipeline — Empfohlene Reihenfolge aus Dev Notes
# ---------------------------------------------------------------------------


def test_full_preprocessing_pipeline_completes(client):
    """Pipeline mit allen 8 Steps läuft fehlerfrei durch."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "dedup"},
            {"type": "time_feature_encoding", "params": {"column": "dteday"}},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "impute_missing", "params": {"strategy": "median"}},
            {"type": "outlier_handling", "params": {"method": "iqr"}},
            {"type": "rare_category_bucketing", "params": {"min_frequency": 0.05}},
            {"type": "correlation_filter", "params": {"threshold": 0.9}},
            {"type": "encode_categorical", "params": {"method": "label"}},
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "run_id" in body


def test_full_pipeline_all_step_types_in_results(client):
    """Alle Step-Typen erscheinen in step_results."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "dedup"},
            {"type": "time_feature_encoding", "params": {"column": "dteday"}},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "rare_category_bucketing", "params": {"min_frequency": 0.05}},
            {"type": "correlation_filter", "params": {"threshold": 0.9}},
            {"type": "encode_categorical", "params": {"method": "label"}},
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 200
    step_results = resp.json()["result"]["step_results"]
    types = [s["step_type"] for s in step_results]
    assert "time_feature_encoding" in types
    assert "rare_category_bucketing" in types
    assert "correlation_filter" in types
    assert "encode_categorical" in types


def test_full_pipeline_all_metadata_present(client):
    """Alle Steps liefern Metadaten."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "dedup"},
            {"type": "time_feature_encoding", "params": {"column": "dteday"}},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "rare_category_bucketing", "params": {"min_frequency": 0.05}},
            {"type": "correlation_filter", "params": {"threshold": 0.9}},
            {"type": "encode_categorical", "params": {"method": "label"}},
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    step_results = resp.json()["result"]["step_results"]

    for step in step_results:
        assert "metadata" in step, f"Kein metadata in step: {step['step_type']}"


# ---------------------------------------------------------------------------
# dteday — nach time_feature_encoding nicht mehr im DataFrame
# ---------------------------------------------------------------------------


def test_dteday_dropped_metadata_confirms(client):
    """time_feature_encoding meldet dropped_column=dteday in Metadaten."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "time_feature_encoding", "params": {"column": "dteday"}},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "encode_categorical", "params": {"method": "label"}},
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 200
    step_results = resp.json()["result"]["step_results"]
    time_meta = next(
        s["metadata"] for s in step_results if s["step_type"] == "time_feature_encoding"
    )
    assert time_meta["dropped_column"] == "dteday"
    assert "weekday" in time_meta["derived_features"]
    assert "month" in time_meta["derived_features"]


def test_encode_categorical_does_not_encode_dteday(client):
    """Nach time_feature_encoding darf dteday nicht in encoded_columns erscheinen."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "time_feature_encoding", "params": {"column": "dteday"}},
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "encode_categorical", "params": {"method": "label"}},
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 200
    step_results = resp.json()["result"]["step_results"]
    enc_meta = next(
        s["metadata"] for s in step_results if s["step_type"] == "encode_categorical"
    )
    assert "dteday" not in enc_meta["encoded_columns"]


# ---------------------------------------------------------------------------
# correlation_filter — cnt_dup (identisch mit cnt) wird entfernt
# ---------------------------------------------------------------------------


def test_correlation_filter_drops_duplicate_feature(client):
    """cnt_dup ist identisch mit cnt (corr=1.0) → muss entfernt werden."""
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "correlation_filter", "params": {"threshold": 0.9}},
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 200
    step_results = resp.json()["result"]["step_results"]
    corr_meta = next(
        s["metadata"] for s in step_results if s["step_type"] == "correlation_filter"
    )
    assert len(corr_meta["dropped_features"]) >= 1


# ---------------------------------------------------------------------------
# rare_category_bucketing ohne vorherigen Split → INVALID_SPEC_ORDER (Story 1.5: Pre-Flight-Prüfung)
# ---------------------------------------------------------------------------


def test_rare_category_bucketing_without_split_returns_split_required(client):
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "rare_category_bucketing", "params": {"min_frequency": 0.01}}
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_spec_order"


def test_encode_categorical_without_split_returns_split_required(client):
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "encode_categorical", "params": {"method": "label"}}
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_spec_order"


def test_correlation_filter_without_split_returns_split_required(client):
    session_id = _create_session(client)
    spec = {
        "steps": [
            {"type": "correlation_filter", "params": {"threshold": 0.9}}
        ]
    }
    resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": spec})
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_spec_order"
