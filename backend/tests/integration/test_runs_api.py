"""Integrationstests für GET /v1/sessions/{session_id}/runs (Story 1.5, AC 4-7)."""
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


def _execute(client, session_id: str, steps: list) -> dict:
    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": steps}},
    )
    return resp


# ---------------------------------------------------------------------------
# AC4: GET /v1/sessions/{session_id}/runs gibt alle Runs zurück
# ---------------------------------------------------------------------------


def test_list_runs_empty_for_new_session(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["runs"] == []


def test_list_runs_returns_run_after_execute(client):
    session_id = _create_session(client)
    _execute(client, session_id, [])
    resp = client.get(f"/v1/sessions/{session_id}/runs")
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert len(runs) == 1
    assert "run_id" in runs[0]
    assert runs[0]["status"] == "completed"


def test_list_runs_summary_fields(client):
    session_id = _create_session(client)
    _execute(client, session_id, [])
    resp = client.get(f"/v1/sessions/{session_id}/runs")
    run = resp.json()["runs"][0]
    assert "run_id" in run
    assert "status" in run
    assert "started_at" in run
    assert "spec_version" in run


def test_list_runs_multiple_runs_ordered(client):
    session_id = _create_session(client)
    _execute(client, session_id, [])
    _execute(client, session_id, [])
    resp = client.get(f"/v1/sessions/{session_id}/runs")
    runs = resp.json()["runs"]
    assert len(runs) == 2


# ---------------------------------------------------------------------------
# AC5: GET /v1/sessions/{session_id}/runs/{run_id} gibt vollständige Daten
# ---------------------------------------------------------------------------


def test_get_run_detail_after_execute(client):
    session_id = _create_session(client)
    exec_resp = _execute(client, session_id, [])
    run_id = exec_resp.json()["run_id"]
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["status"] == "completed"
    assert body["started_at"] is not None
    assert body["finished_at"] is not None


def test_get_run_detail_contains_spec(client):
    session_id = _create_session(client)
    spec = {"steps": [{"type": "dedup"}]}
    exec_resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": spec},
    )
    run_id = exec_resp.json()["run_id"]
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    body = resp.json()
    assert body["spec"] == spec


def test_get_run_detail_contains_step_results(client):
    session_id = _create_session(client)
    exec_resp = _execute(client, session_id, [{"type": "dedup"}])
    run_id = exec_resp.json()["run_id"]
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    body = resp.json()
    assert isinstance(body["step_results"], list)
    assert len(body["step_results"]) == 1
    assert body["step_results"][0]["step_type"] == "dedup"


def test_get_run_detail_metrics_and_artifacts_empty(client):
    session_id = _create_session(client)
    exec_resp = _execute(client, session_id, [])
    run_id = exec_resp.json()["run_id"]
    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    body = resp.json()
    assert body["metrics"] == {}
    assert body["artifacts"] == []


# ---------------------------------------------------------------------------
# AC6: Fehlgeschlagener Run enthält status: "failed" und error_message
# ---------------------------------------------------------------------------


def test_get_run_detail_failed_run(client):
    session_id = _create_session(client)
    # Trigger a failed run with unknown step type — run is created then failed
    client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": [{"type": "nonexistent_step"}]}},
    )
    # The run was created in the DB (status=failed); retrieve via list
    runs_resp = client.get(f"/v1/sessions/{session_id}/runs")
    runs = runs_resp.json()["runs"]
    assert len(runs) == 1
    run_id = runs[0]["run_id"]

    resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error_message"] is not None
    assert len(body["error_message"]) > 0


# ---------------------------------------------------------------------------
# AC7: 404 für unbekannte Run-ID
# ---------------------------------------------------------------------------


def test_get_run_returns_404_for_unknown_run_id(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/runs/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "run_not_found"
    assert body["code"] == "RUN_NOT_FOUND"


def test_get_run_returns_404_for_wrong_session(client):
    session_id_1 = _create_session(client)
    session_id_2 = _create_session(client)
    exec_resp = _execute(client, session_id_1, [])
    run_id = exec_resp.json()["run_id"]
    # Query run from session_id_2 — should return 404
    resp = client.get(f"/v1/sessions/{session_id_2}/runs/{run_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC2: Spec-Order-Fehler vor Ausführung → 422 mit invalid_spec_order
# ---------------------------------------------------------------------------


def test_invalid_spec_order_returns_error_before_execution(client):
    session_id = _create_session(client)
    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": [{"type": "train_decision_tree"}]}},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "invalid_spec_order"
    assert body["code"] == "INVALID_SPEC_ORDER"
    assert "train_decision_tree" in body["detail"]


def test_invalid_spec_order_does_not_create_run(client):
    session_id = _create_session(client)
    client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": [{"type": "train_decision_tree"}]}},
    )
    resp = client.get(f"/v1/sessions/{session_id}/runs")
    # Spec-order errors happen before run creation → no run in DB
    assert resp.json()["runs"] == []
