"""Integrationstests fuer Session-API-Endpunkte."""
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(db_path=str(tmp_path / "test.db"))
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "llm_model" in data


# ---------------------------------------------------------------------------
# Session erstellen
# ---------------------------------------------------------------------------


def test_create_session_without_name(client):
    resp = client.post("/v1/sessions", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["name"] is None
    assert "session_id" in body
    assert "created_at" in body


def test_create_session_with_name(client):
    resp = client.post("/v1/sessions", json={"name": "Mein Test"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Mein Test"


def test_create_session_no_body(client):
    resp = client.post("/v1/sessions")
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Session abrufen
# ---------------------------------------------------------------------------


def test_get_session_existing(client):
    create_resp = client.post("/v1/sessions", json={"name": "Fetch Me"})
    session_id = create_resp.json()["session_id"]

    resp = client.get(f"/v1/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["name"] == "Fetch Me"
    assert body["status"] == "active"


def test_get_session_not_found(client):
    resp = client.get("/v1/sessions/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "session_not_found"
    assert body["code"] == "SESSION_NOT_FOUND"
    assert "detail" in body


# ---------------------------------------------------------------------------
# Sessions auflisten
# ---------------------------------------------------------------------------


def test_list_sessions_empty(client):
    resp = client.get("/v1/sessions")
    assert resp.status_code == 200
    assert resp.json()["sessions"] == []


def test_list_sessions_multiple(client):
    client.post("/v1/sessions", json={"name": "A"})
    client.post("/v1/sessions", json={"name": "B"})
    resp = client.get("/v1/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) == 2


# ---------------------------------------------------------------------------
# Session schliessen (Soft-Delete)
# ---------------------------------------------------------------------------


def test_close_session_soft_delete(client):
    create_resp = client.post("/v1/sessions", json={"name": "ToClose"})
    session_id = create_resp.json()["session_id"]

    delete_resp = client.delete(f"/v1/sessions/{session_id}")
    assert delete_resp.status_code == 200
    body = delete_resp.json()
    assert body["status"] == "closed"
    assert body["session_id"] == session_id

    # Session existiert noch (kein Hard-Delete)
    get_resp = client.get(f"/v1/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "closed"


def test_close_session_not_found(client):
    resp = client.delete("/v1/sessions/no-such-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "SESSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# 422 Validierungsfehler
# ---------------------------------------------------------------------------


def test_create_session_invalid_name_type(client):
    # name muss ein String oder null sein — eine tiefgeschachtelte Zahl sollte 422 liefern
    resp = client.post("/v1/sessions", json={"name": {"nested": "object"}})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Isolation: separate Tests nutzen frische DB
# ---------------------------------------------------------------------------


def test_isolation_fresh_db(tmp_path):
    settings = Settings(db_path=str(tmp_path / "isolated.db"))
    app = create_app(settings=settings)
    with TestClient(app) as c:
        resp = c.get("/v1/sessions")
        assert resp.json()["sessions"] == []


# ---------------------------------------------------------------------------
# Generischer 404-Handler
# ---------------------------------------------------------------------------


def test_generic_404_handler(client):
    """Unbekannte Route liefert 404 im ErrorResponse-Format."""
    resp = client.get("/v1/route-does-not-exist-at-all")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "not_found"
    assert body["code"] == "NOT_FOUND"
    assert "detail" in body
