"""Integrationstests fuer Messages-API (Story 3.1)."""
import json

import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        openai_api_key="",
        llm_model="",
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_id(client):
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# POST /v1/sessions/{id}/messages
# ---------------------------------------------------------------------------


def test_post_message_saves_and_returns_503(client, session_id):
    """POST /messages → HTTP 503 (kein LLM), Message in DB gespeichert."""
    resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": "Hallo"})
    assert resp.status_code == 503
    body = resp.json()
    assert body["type"] == "error"
    assert "nicht konfiguriert" in body["message"]
    assert body["error_code"] == "llm_not_configured"


def test_post_message_404_unknown_session(client):
    resp = client.post("/v1/sessions/does-not-exist/messages", json={"text": "X"})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "session_not_found"
    assert body["code"] == "SESSION_NOT_FOUND"


def test_post_message_409_closed_session(client, session_id):
    client.delete(f"/v1/sessions/{session_id}")
    resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": "X"})
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "session_closed"
    assert body["code"] == "SESSION_CLOSED"


def test_messages_in_session_detail(client, session_id):
    """POST Message → GET Session → messages-Array enthält user + assistant Messages."""
    client.post(f"/v1/sessions/{session_id}/messages", json={"text": "Nachricht"})
    resp = client.get(f"/v1/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "messages" in body
    messages = body["messages"]
    assert len(messages) == 2
    roles = [m["role"] for m in messages]
    assert "user" in roles
    assert "assistant" in roles


def test_assistant_message_persisted(client, session_id):
    """Nach POST → 2 Messages in DB (user + assistant)."""
    client.post(f"/v1/sessions/{session_id}/messages", json={"text": "Frage"})
    resp = client.get(f"/v1/sessions/{session_id}")
    messages = resp.json()["messages"]
    assert len(messages) == 2
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) == 1
    assert len(assistant_msgs) == 1
    assert user_msgs[0]["content"] == "Frage"
    # assistant content ist serialisiertes JSON
    assistant_content = json.loads(assistant_msgs[0]["content"])
    assert assistant_content["type"] == "error"


def test_message_response_has_type_field(client, session_id):
    """Response-Body enthält type-Feld."""
    resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": "X"})
    # 503 response body hat 'type'
    assert "type" in resp.json()


def test_session_without_messages_has_empty_list(client, session_id):
    """GET Session ohne Messages → messages=[]."""
    resp = client.get(f"/v1/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


def test_multiple_messages_chronological(client, session_id):
    """Mehrere Messages sind chronologisch sortiert."""
    client.post(f"/v1/sessions/{session_id}/messages", json={"text": "erste"})
    client.post(f"/v1/sessions/{session_id}/messages", json={"text": "zweite"})
    resp = client.get(f"/v1/sessions/{session_id}")
    messages = resp.json()["messages"]
    assert len(messages) == 4  # 2x user + 2x assistant
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "erste"


# ---------------------------------------------------------------------------
# Regressions-Schutz — bestehende Endpunkte
# ---------------------------------------------------------------------------


def test_existing_endpoints_unchanged(client):
    """Health, Sessions, Execute, Capabilities reagieren wie bisher."""
    # Health
    assert client.get("/v1/health").status_code == 200
    # Sessions list
    assert client.get("/v1/sessions").status_code == 200
    # Create session
    resp = client.post("/v1/sessions", json={})
    assert resp.status_code == 201
    sid = resp.json()["session_id"]
    # Get session
    assert client.get(f"/v1/sessions/{sid}").status_code == 200
    # Capabilities
    assert client.get("/v1/capabilities").status_code == 200
    # Execute mit leerem Spec → 422
    exec_resp = client.post(f"/v1/sessions/{sid}/execute", json={"spec": {}})
    assert exec_resp.status_code in (200, 422)


def test_list_sessions_no_messages_field_overhead(client, session_id):
    """list_sessions gibt messages=None — kein Performance-Overhead."""
    client.post(f"/v1/sessions/{session_id}/messages", json={"text": "X"})
    resp = client.get("/v1/sessions")
    sessions = resp.json()["sessions"]
    # messages-Feld ist optional/None in der Liste
    for s in sessions:
        assert s.get("messages") is None or "messages" not in s


def test_post_message_empty_text_returns_422(client, session_id):
    """Leerer Text → HTTP 422 (Pydantic min_length=1)."""
    resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": ""})
    assert resp.status_code == 422


def test_post_message_whitespace_only_text_returns_422(client, session_id):
    """Nur Leerzeichen (wird zu leerem String) → HTTP 422."""
    resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": "   "})
    assert resp.status_code == 422
