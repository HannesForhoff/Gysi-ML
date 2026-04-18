"""Integrationstests für LLM-Integration (Story 3.2)."""
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings


_VALID_EXECUTE_RESPONSE = json.dumps(
    {
        "action": "execute",
        "spec": {"steps": [{"type": "dedup", "params": {}}]},
        "explanation": "Duplikate werden entfernt.",
    }
)

_VALID_PROPOSE_RESPONSE = json.dumps(
    {
        "action": "propose",
        "spec": {"steps": [{"type": "split", "params": {"test_size": 0.2}}]},
        "explanation": "Ich schlage Split vor.",
    }
)


def _make_settings(tmp_path, api_key="", model=""):
    return Settings(
        db_path=str(tmp_path / "test.db"),
        openai_api_key=api_key,
        llm_model=model,
    )


@pytest.fixture
def client_no_llm(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: settings
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_with_llm(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path, api_key="sk-test", model="gpt-4o-mini")
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: settings
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_no_llm(client_no_llm):
    resp = client_no_llm.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


@pytest.fixture
def session_with_llm(client_with_llm):
    resp = client_with_llm.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# AC 8: 503 ohne LLM-Konfiguration
# ---------------------------------------------------------------------------


def test_message_flow_503_no_llm(client_no_llm, session_no_llm):
    """Kein LLM konfiguriert -> HTTP 503."""
    resp = client_no_llm.post(
        f"/v1/sessions/{session_no_llm}/messages", json={"text": "Hallo"}
    )
    assert resp.status_code == 503
    body = resp.json()
    assert body["type"] == "error"
    assert "nicht konfiguriert" in body["message"]


# ---------------------------------------------------------------------------
# AC 9: execute action -> type='result'
# ---------------------------------------------------------------------------


def test_message_flow_execute(monkeypatch, client_with_llm, session_with_llm):
    """Mock LLM execute -> HTTP 200, type='result', run_id vorhanden."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_EXECUTE_RESPONSE,
    )
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-int-123"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    resp = client_with_llm.post(
        f"/v1/sessions/{session_with_llm}/messages",
        json={"text": "Entferne Duplikate"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "result"
    assert body["run_id"] == "run-int-123"


# ---------------------------------------------------------------------------
# AC 9: propose action -> type='proposal'
# ---------------------------------------------------------------------------


def test_message_flow_propose(monkeypatch, client_with_llm, session_with_llm):
    """Mock LLM propose -> HTTP 200, type='proposal'."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_PROPOSE_RESPONSE,
    )

    resp = client_with_llm.post(
        f"/v1/sessions/{session_with_llm}/messages",
        json={"text": "Bereite die Daten vor"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "proposal"
    assert body["confirmation_required"] is True


# ---------------------------------------------------------------------------
# AC 6/7: Retry
# ---------------------------------------------------------------------------


def test_message_flow_retry_success(monkeypatch, client_with_llm, session_with_llm):
    """Mock: erst ungültiges JSON, dann gültiges -> Erfolg."""
    call_count = {"n": 0}

    def fake_call(**kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "kein json"
        return _VALID_EXECUTE_RESPONSE

    monkeypatch.setattr("gysi_ml.services.message_service.call_llm", fake_call)
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-retry-ok"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    resp = client_with_llm.post(
        f"/v1/sessions/{session_with_llm}/messages",
        json={"text": "Test"},
    )
    assert resp.status_code == 200
    assert resp.json()["type"] == "result"
    assert call_count["n"] == 3  # 1× ungültig, 1× retry-gültig, 1× post_run


def test_message_flow_retry_exhausted(monkeypatch, client_with_llm, session_with_llm):
    """Mock: beide LLM-Antworten ungültig -> HTTP 422, type='error'."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: "immer ungültig",
    )

    resp = client_with_llm.post(
        f"/v1/sessions/{session_with_llm}/messages",
        json={"text": "Test"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"] == "error"
    assert "gültige Aktion" in body["message"]


# ---------------------------------------------------------------------------
# AC 5: Gesprächshistorie wird an LLM gesendet
# ---------------------------------------------------------------------------


def test_conversation_history_sent_to_llm(
    monkeypatch, client_with_llm, session_with_llm
):
    """Mehrere Nachrichten -> LLM erhält vollständige Konversationshistorie."""
    captured_calls: list = []

    def fake_call(**kw):
        captured_calls.append(kw.get("messages", []))
        return _VALID_EXECUTE_RESPONSE

    monkeypatch.setattr("gysi_ml.services.message_service.call_llm", fake_call)
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-hist"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    # Erste Nachricht
    client_with_llm.post(
        f"/v1/sessions/{session_with_llm}/messages",
        json={"text": "erste Frage"},
    )
    # Zweite Nachricht
    client_with_llm.post(
        f"/v1/sessions/{session_with_llm}/messages",
        json={"text": "zweite Frage"},
    )

    assert len(captured_calls) == 4  # 2× execute + 2× post_run
    # captured_calls: [execute_1, post_run_1, execute_2, post_run_2]
    second_execute_messages = captured_calls[2]
    roles = [m["role"] for m in second_execute_messages]
    assert roles[0] == "system"
    assert "user" in roles
    assert "assistant" in roles
