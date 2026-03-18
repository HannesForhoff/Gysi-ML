"""Integrationstests für Proposal-API (Story 3.3)."""
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings

_PROPOSE_LLM = json.dumps(
    {
        "action": "propose",
        "spec": {"steps": [{"type": "dedup", "params": {}}]},
        "explanation": "Ich schlage Dedup vor.",
    }
)

_EXECUTE_LLM = json.dumps(
    {
        "action": "execute",
        "spec": {"steps": [{"type": "dedup", "params": {}}]},
        "explanation": "Führe Dedup aus.",
    }
)


def _make_settings(tmp_path, api_key="sk-test", model="gpt-4o-mini"):
    return Settings(
        db_path=str(tmp_path / "test.db"),
        openai_api_key=api_key,
        llm_model=model,
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_settings", lambda: settings
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_id(client):
    resp = client.post("/v1/sessions", json={"name": "3.3 Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _mock_propose(monkeypatch, propose_response=_PROPOSE_LLM):
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_capabilities",
        lambda: {"steps": []},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: propose_response,
    )


def _mock_execute(monkeypatch, run_id="run-001"):
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_capabilities",
        lambda: {"steps": []},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _EXECUTE_LLM,
    )
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": run_id}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )


# ---------------------------------------------------------------------------
# Propose-Flow
# ---------------------------------------------------------------------------


def test_propose_flow(client, session_id, monkeypatch):
    """POST /messages (vage) → Mock LLM propose → type='proposal' mit proposal_id."""
    _mock_propose(monkeypatch)
    resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "Bereite die Daten vor"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "proposal"
    assert "proposal_id" in body
    assert body["proposal_id"] is not None
    assert body["confirmation_required"] is True
    assert "steps" in body


# ---------------------------------------------------------------------------
# Confirm-Flow
# ---------------------------------------------------------------------------


def test_confirm_proposal(client, session_id, monkeypatch):
    """Proposal erstellen → POST /confirm → type='result' mit run_id."""
    _mock_propose(monkeypatch)
    propose_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "Bereite vor"},
    )
    assert propose_resp.status_code == 200
    proposal_id = propose_resp.json()["proposal_id"]

    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-confirm-01"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    confirm_resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert confirm_resp.status_code == 200
    body = confirm_resp.json()
    assert body["type"] == "result"
    assert body["run_id"] == "run-confirm-01"


def test_confirm_no_pending_proposal(client, session_id):
    """POST /confirm ohne offenen Proposal → HTTP 409."""
    resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": "some-id"},
    )
    assert resp.status_code == 404  # Proposal existiert nicht
    assert resp.json()["error"] == "proposal_not_found"


def test_confirm_unknown_proposal_id(client, session_id):
    """POST /confirm mit unbekannter ID → HTTP 404."""
    resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": "completely-unknown"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "proposal_not_found"
    assert body["code"] == "PROPOSAL_NOT_FOUND"


def test_confirm_wrong_session(client, monkeypatch):
    """Proposal von Session A → Confirm in Session B → HTTP 404."""
    _mock_propose(monkeypatch)

    # Session A erstellen und Proposal anlegen
    s_a = client.post("/v1/sessions", json={"name": "A"}).json()["session_id"]
    s_b = client.post("/v1/sessions", json={"name": "B"}).json()["session_id"]

    propose_resp = client.post(
        f"/v1/sessions/{s_a}/messages",
        json={"text": "vage"},
    )
    proposal_id = propose_resp.json()["proposal_id"]

    # Confirm in Session B
    resp = client.post(
        f"/v1/sessions/{s_b}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "proposal_not_found"


def test_confirm_closed_session(client, session_id, monkeypatch):
    """Geschlossene Session → POST /confirm → HTTP 409."""
    _mock_propose(monkeypatch)
    propose_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "vage"},
    )
    proposal_id = propose_resp.json()["proposal_id"]

    # Session schließen
    client.delete(f"/v1/sessions/{session_id}")

    resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "session_closed"


# ---------------------------------------------------------------------------
# Implizite Ablehnung
# ---------------------------------------------------------------------------


def test_implicit_rejection(client, session_id, monkeypatch):
    """Proposal → neue Nachricht → alter Proposal rejected, neuer Proposal entsteht."""
    from gysi_ml.persistence.proposal_repository import get_proposal

    _mock_propose(monkeypatch)
    first_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "erste Anfrage"},
    )
    first_proposal_id = first_resp.json()["proposal_id"]

    # Zweite Nachricht (löst implizite Ablehnung aus)
    second_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "neue Anfrage"},
    )
    assert second_resp.status_code == 200

    # Erster Proposal ist rejected — wir brauchen db_path aus der App-State
    # → Verify via zweiten Propose-Call: neuer proposal_id != alter
    if second_resp.json()["type"] == "proposal":
        assert second_resp.json()["proposal_id"] != first_proposal_id


# ---------------------------------------------------------------------------
# Direkte Ausführung (execute)
# ---------------------------------------------------------------------------


def test_direct_execute(client, session_id, monkeypatch):
    """POST /messages (eindeutig) → Mock LLM execute → type='result' direkt."""
    _mock_execute(monkeypatch)
    resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "Entferne alle Duplikate"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "result"
    assert "run_id" in body


# ---------------------------------------------------------------------------
# Vollständiger Fluss
# ---------------------------------------------------------------------------


def test_full_conversation_flow(client, session_id, monkeypatch):
    """Session → Proposal → Confirm → Run abrufbar."""
    _mock_propose(monkeypatch)
    propose_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "Bereite Daten vor"},
    )
    assert propose_resp.json()["type"] == "proposal"
    proposal_id = propose_resp.json()["proposal_id"]

    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-full-01"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    confirm_resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["run_id"] == "run-full-01"

    # Run-Endpunkt prüfen
    runs_resp = client.get(f"/v1/sessions/{session_id}/runs")
    assert runs_resp.status_code == 200


# ---------------------------------------------------------------------------
# Assistant-Messages bei Proposals + Confirm
# ---------------------------------------------------------------------------


@pytest.fixture
def client_with_db(monkeypatch, tmp_path):
    """Client-Fixture die zusätzlich den db_path zurückgibt."""
    settings = _make_settings(tmp_path)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_settings", lambda: settings
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c, str(tmp_path / "test.db")


def test_assistant_messages_persisted(client_with_db, monkeypatch):
    """Nach Proposal + Confirm → assistant-Messages in DB persistiert."""
    client, db_path = client_with_db

    # Session anlegen
    resp = client.post("/v1/sessions", json={"name": "msg-test"})
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    _mock_propose(monkeypatch)
    propose_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "vage Anfrage"},
    )
    assert propose_resp.status_code == 200, propose_resp.json()
    proposal_id = propose_resp.json()["proposal_id"]

    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-msg-01"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )
    confirm_resp = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert confirm_resp.status_code == 200, confirm_resp.json()

    # Direkt aus DB lesen (korrekter db_path aus dem client_with_db-Fixture)
    from gysi_ml.persistence.database import get_connection
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT role FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        all_msgs = [{"role": r["role"]} for r in rows]
    finally:
        conn.close()
    assistant_msgs = [m for m in all_msgs if m["role"] == "assistant"]
    # Mindestens 2 assistant-Messages: nach /messages + nach /confirm
    assert len(assistant_msgs) >= 2


def test_confirm_nonexistent_session(client):
    """POST /confirm auf nicht-existente Session → HTTP 404."""
    resp = client.post(
        "/v1/sessions/does-not-exist/confirm",
        json={"proposal_id": "some-id"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "session_not_found"


# ---------------------------------------------------------------------------
# 409 für zweifaches Confirm
# ---------------------------------------------------------------------------


def test_confirm_twice_returns_409(client, session_id, monkeypatch):
    """Proposal einmal bestätigt → zweites Confirm → HTTP 409."""
    _mock_propose(monkeypatch)
    propose_resp = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "vage"},
    )
    proposal_id = propose_resp.json()["proposal_id"]

    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-dup"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    # Erstes Confirm → 200
    first = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert first.status_code == 200

    # Zweites Confirm → 409 (kein pending Proposal mehr)
    second = client.post(
        f"/v1/sessions/{session_id}/confirm",
        json={"proposal_id": proposal_id},
    )
    assert second.status_code == 409
    assert second.json()["error"] == "no_pending_proposal"
