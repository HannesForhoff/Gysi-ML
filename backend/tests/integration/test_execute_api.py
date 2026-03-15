"""Integrationstests fuer POST /v1/sessions/{session_id}/execute."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings
from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import _registry, register_step


@pytest.fixture(autouse=True)
def clean_registry():
    original = dict(_registry)
    yield
    _registry.clear()
    _registry.update(original)


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame({
        "instant": [1, 2, 3],
        "cnt": [100, 200, 300],
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


def _create_active_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _register_dummy():
    @register_step("dummy")
    class DummyStep(BaseStep):
        def fit(self, df):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    return DummyStep


# ---------------------------------------------------------------------------
# Happy Path
# ---------------------------------------------------------------------------


def test_execute_empty_spec_happy_path(client):
    _register_dummy()
    session_id = _create_active_session(client)

    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": []}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "run_id" in body
    assert "result" in body


def test_execute_with_dummy_step(client):
    _register_dummy()
    session_id = _create_active_session(client)

    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": [{"type": "dummy"}]}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# 404: Session nicht gefunden
# ---------------------------------------------------------------------------


def test_execute_session_not_found(client):
    resp = client.post(
        "/v1/sessions/does-not-exist/execute",
        json={"spec": {"steps": []}},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "session_not_found"
    assert body["code"] == "SESSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# 409: Session geschlossen
# ---------------------------------------------------------------------------


def test_execute_closed_session_returns_409(client):
    session_id = _create_active_session(client)
    client.delete(f"/v1/sessions/{session_id}")  # Session schliessen

    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": []}},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "session_closed"
    assert body["code"] == "SESSION_CLOSED"


# ---------------------------------------------------------------------------
# 422: Ungültige Spec
# ---------------------------------------------------------------------------


def test_execute_invalid_spec_returns_422(client):
    session_id = _create_active_session(client)

    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"invalid_key": []}},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "invalid_spec"


def test_execute_unknown_step_type_returns_422(client):
    session_id = _create_active_session(client)

    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": [{"type": "not_a_real_step"}]}},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "unknown_step_type"
