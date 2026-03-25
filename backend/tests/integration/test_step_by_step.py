"""Integrationstests für Step-by-Step-Ausführungsmodus (Story 9.3)."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings
from gysi_ml.persistence import proposal_repository, step_state_repository

_PROPOSE_LLM = json.dumps(
    {
        "action": "propose",
        "spec": {
            "steps": [
                {"type": "dedup", "params": {}},
                {"type": "imputation", "params": {"strategy": "mean"}},
            ]
        },
        "explanation": "Ich schlage Dedup + Imputation vor.",
    }
)

_ABORT_LLM = json.dumps(
    {
        "action": "abort_step_by_step",
        "spec": {"steps": []},
        "explanation": "Abbruch des Step-by-Step-Modus.",
    }
)


def _make_settings(tmp_path):
    return Settings(
        db_path=str(tmp_path / "test.db"),
        openai_api_key="sk-test",
        llm_model="gpt-4o-mini",
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path)
    monkeypatch.setattr("gysi_ml.services.message_service.get_settings", lambda: settings)
    monkeypatch.setattr("gysi_ml.services.proposal_service.get_settings", lambda: settings)
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_id(client):
    resp = client.post("/v1/sessions", json={"name": "9.3 Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _mock_propose(monkeypatch):
    monkeypatch.setattr("gysi_ml.services.message_service.get_capabilities", lambda: {"steps": []})
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _PROPOSE_LLM,
    )


def _create_proposal(client, session_id, monkeypatch) -> str:
    _mock_propose(monkeypatch)
    resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": "Bereite vor"})
    assert resp.status_code == 200
    return resp.json()["proposal_id"]


def _mock_execute_single_step(monkeypatch, summary="Step ausgeführt."):
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service._execute_single_step",
        lambda current_step, completed_steps, data_path, artifacts_path: {
            "summary": summary,
            "metadata": None,
        },
    )


# ---------------------------------------------------------------------------
# T5: test_first_step_returns_step_result (AC 1)
# ---------------------------------------------------------------------------


def test_first_step_returns_step_result(client, session_id, monkeypatch):
    """mode=step_by_step → type='step_result' mit completed_step und remaining_steps."""
    proposal_id = _create_proposal(client, session_id, monkeypatch)
    _mock_execute_single_step(monkeypatch)

    resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id, "mode": "step_by_step"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["type"] == "step_result"
    assert body["is_final"] is False
    assert body["completed_step"] is not None
    assert body["completed_step"]["type"] == "dedup"
    assert len(body["remaining_steps"]) == 1
    assert body["remaining_steps"][0]["type"] == "imputation"
    assert body["next_action"] is not None
    assert "imputation" in body["next_action"]
    assert body["state_id"] is not None


# ---------------------------------------------------------------------------
# T5: test_state_persisted_after_first_step (AC 2)
# ---------------------------------------------------------------------------


def test_state_persisted_after_first_step(client, session_id, monkeypatch, tmp_path):
    """Nach erstem Step ist State in step_states gespeichert."""
    settings = _make_settings(tmp_path)
    proposal_id = _create_proposal(client, session_id, monkeypatch)
    _mock_execute_single_step(monkeypatch)

    resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id, "mode": "step_by_step"},
    )
    assert resp.status_code == 200

    db_path = str(tmp_path / "test.db")
    state = step_state_repository.get_step_state_by_session(
        session_id=session_id, db_path=db_path
    )
    assert state is not None
    assert state["session_id"] == session_id
    assert len(state["remaining_steps"]) == 1
    assert len(state["completed_steps"]) == 1
    assert state["completed_steps"][0]["type"] == "dedup"


# ---------------------------------------------------------------------------
# T5: test_last_step_returns_final_summary (AC 4)
# ---------------------------------------------------------------------------


def test_last_step_returns_final_summary(client, session_id, monkeypatch, tmp_path):
    """Letzter Step → is_final=True, State gelöscht."""
    settings = _make_settings(tmp_path)
    db_path = str(tmp_path / "test.db")

    proposal_id = _create_proposal(client, session_id, monkeypatch)
    _mock_execute_single_step(monkeypatch)

    # Schritt 1: erster Step
    resp1 = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id, "mode": "step_by_step"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["is_final"] is False

    # Schritt 2: zweiter und letzter Step — gleicher Proposal (State im gleichen Confirm-Lauf)
    resp2 = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id, "mode": "step_by_step"},
    )
    assert resp2.status_code == 200
    body = resp2.json()

    assert body["type"] == "step_result"
    assert body["is_final"] is True
    assert body["completed_steps_summary"] is not None
    assert len(body["completed_steps_summary"]) == 2
    assert body["state_id"] is None

    # State muss gelöscht sein
    state = step_state_repository.get_step_state_by_session(
        session_id=session_id, db_path=db_path
    )
    assert state is None


# ---------------------------------------------------------------------------
# T5: test_abort_clears_state (AC 5)
# ---------------------------------------------------------------------------


def test_abort_clears_state(client, session_id, monkeypatch, tmp_path):
    """abort_step_by_step → State gelöscht, Zusammenfassung zurück."""
    db_path = str(tmp_path / "test.db")

    # State manuell anlegen
    state = step_state_repository.create_step_state(
        session_id=session_id,
        proposal_id="prop-abort-test",
        remaining_steps=[{"type": "imputation", "params": {}}],
        completed_steps=[{"type": "dedup", "summary": "dedup done", "metadata": None}],
        confirmed_indices=[],
        db_path=db_path,
    )
    assert state is not None

    # LLM gibt abort_step_by_step zurück
    monkeypatch.setattr("gysi_ml.services.message_service.get_capabilities", lambda: {"steps": []})
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _ABORT_LLM,
    )

    resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "Abbrechen"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["type"] == "assistant"
    assert "dedup" in body["message"]
    assert "beendet" in body["message"].lower()

    # State muss gelöscht sein
    remaining_state = step_state_repository.get_step_state_by_session(
        session_id=session_id, db_path=db_path
    )
    assert remaining_state is None


# ---------------------------------------------------------------------------
# T5: test_no_mode_runs_all_steps (AC —, Regression)
# ---------------------------------------------------------------------------


def test_no_mode_runs_all_steps(client, session_id, monkeypatch):
    """Ohne mode (default 'all') → normaler Confirm-Flow unverändert."""
    proposal_id = _create_proposal(client, session_id, monkeypatch)

    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-9-3-all"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["type"] == "result"
    assert body["run_id"] == "run-9-3-all"
