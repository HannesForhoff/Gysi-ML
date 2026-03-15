"""Unit-Tests fuer Pydantic v2 Schemas."""
import pytest
from pydantic import ValidationError

from gysi_ml.api.schemas import (
    ErrorResponse,
    HealthResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
)
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TestSessionCreateRequest:
    def test_name_optional_default_none(self):
        req = SessionCreateRequest()
        assert req.name is None

    def test_name_provided(self):
        req = SessionCreateRequest(name="Test")
        assert req.name == "Test"

    def test_extra_fields_ignored(self):
        # Pydantic v2 ignoriert unbekannte Felder mit extra='ignore' oder wirft Fehler
        # SessionCreateRequest hat kein extra konfiguriert => default ignore
        req = SessionCreateRequest.model_validate({"name": "OK", "unknown": "x"})
        assert req.name == "OK"


class TestSessionResponse:
    def test_valid(self):
        r = SessionResponse(
            session_id="abc",
            name="test",
            created_at=_utc_now(),
            status="active",
        )
        assert r.session_id == "abc"
        assert r.status == "active"

    def test_name_none_allowed(self):
        r = SessionResponse(
            session_id="abc",
            name=None,
            created_at=_utc_now(),
            status="active",
        )
        assert r.name is None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            SessionResponse(
                name="x",
                created_at=_utc_now(),
                status="active",
                # session_id fehlt
            )


class TestSessionListResponse:
    def test_empty_list(self):
        r = SessionListResponse(sessions=[])
        assert r.sessions == []

    def test_with_sessions(self):
        s = SessionResponse(
            session_id="x",
            name=None,
            created_at=_utc_now(),
            status="active",
        )
        r = SessionListResponse(sessions=[s])
        assert len(r.sessions) == 1


class TestErrorResponse:
    def test_valid(self):
        e = ErrorResponse(error="not_found", detail="Nicht da.", code="NOT_FOUND")
        assert e.code == "NOT_FOUND"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            ErrorResponse(error="x", detail="y")  # code fehlt


class TestHealthResponse:
    def test_ok(self):
        h = HealthResponse(status="ok")
        assert h.status == "ok"

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            HealthResponse()
