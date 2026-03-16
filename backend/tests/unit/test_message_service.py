"""Unit-Tests fuer message_service."""
import json
from unittest.mock import patch, MagicMock

import pytest

from gysi_ml.llm.exceptions import LLMConnectionError, LLMResponseValidationError
from gysi_ml.services.message_service import handle_message


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

_VALID_EXECUTE_RESPONSE = json.dumps(
    {
        "action": "execute",
        "spec": {"steps": [{"type": "dedup", "params": {}}]},
        "explanation": "Duplikate entfernen.",
    }
)

_VALID_PROPOSE_RESPONSE = json.dumps(
    {
        "action": "propose",
        "spec": {"steps": [{"type": "split", "params": {"test_size": 0.2}}]},
        "explanation": "Ich schlage vor, die Daten zu splitten.",
    }
)


def _settings(api_key="sk-test", model="gpt-4o-mini", base_url=""):
    s = MagicMock()
    s.openai_api_key = api_key
    s.llm_model = model
    s.openai_base_url = base_url
    s.data_path = "/tmp/bikes.csv"
    s.artifacts_path = "/tmp/artifacts"
    return s


# ---------------------------------------------------------------------------
# Bestehende Tests (Regressions-Schutz)
# ---------------------------------------------------------------------------


def test_handle_message_no_llm_configured():
    """Ohne API-Key → type='error' mit 'nicht konfiguriert' und error_code."""
    with patch("gysi_ml.services.message_service.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = ""
        mock_settings.return_value.llm_model = ""
        result = handle_message(session_id="s1", text="Hallo")
    assert result["type"] == "error"
    assert "nicht konfiguriert" in result["message"]
    assert result["error_code"] == "llm_not_configured"


def test_handle_message_no_api_key_only():
    """Nur API-Key fehlt → type='error'."""
    with patch("gysi_ml.services.message_service.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = ""
        mock_settings.return_value.llm_model = "gpt-4"
        result = handle_message(session_id="s1", text="Test")
    assert result["type"] == "error"


def test_handle_message_no_model_only():
    """Nur Model fehlt → type='error'."""
    with patch("gysi_ml.services.message_service.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_settings.return_value.llm_model = ""
        result = handle_message(session_id="s1", text="Test")
    assert result["type"] == "error"


def test_handle_message_returns_dict_with_type():
    """Rückgabe hat immer 'type'-Feld."""
    with patch("gysi_ml.services.message_service.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = ""
        mock_settings.return_value.llm_model = ""
        result = handle_message(session_id="s1", text="Hello")
    assert "type" in result


# ---------------------------------------------------------------------------
# Neue Tests (Story 3.2)
# ---------------------------------------------------------------------------


def test_handle_message_execute_action(monkeypatch):
    """Mock LLM → execute action → type='result' mit run_id."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: _settings()
    )
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
        lambda **kw: _VALID_EXECUTE_RESPONSE,
    )
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-123"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    result = handle_message(session_id="s1", text="Entferne Duplikate")

    assert result["type"] == "result"
    assert result["run_id"] == "run-123"
    assert "explanation" in result


def test_handle_message_propose_action(monkeypatch):
    """Mock LLM → propose action → type='proposal' mit steps."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: _settings()
    )
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
        lambda **kw: _VALID_PROPOSE_RESPONSE,
    )

    result = handle_message(session_id="s1", text="Bereite die Daten vor")

    assert result["type"] == "proposal"
    assert "steps" in result
    assert result["confirmation_required"] is True


def test_handle_message_retry_on_invalid(monkeypatch):
    """Erstes LLM-Ergebnis ungültig, zweites gültig → Erfolg."""
    call_count = {"n": 0}

    def fake_call_llm(**kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "kein gültiges json"
        return _VALID_EXECUTE_RESPONSE

    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: _settings()
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_capabilities",
        lambda: {"steps": []},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )
    monkeypatch.setattr("gysi_ml.services.message_service.call_llm", fake_call_llm)
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-retry"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    result = handle_message(session_id="s1", text="Test")

    assert call_count["n"] == 2
    assert result["type"] == "result"


def test_handle_message_retry_exhausted(monkeypatch):
    """Beide LLM-Antworten ungültig → type='error' mit Retry-Meldung."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: _settings()
    )
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
        lambda **kw: "immer ungültig",
    )

    result = handle_message(session_id="s1", text="Test")

    assert result["type"] == "error"
    assert "gültige Aktion" in result["message"]


def test_handle_message_llm_connection_error(monkeypatch):
    """LLM nicht erreichbar → type='error' mit Verbindungsfehler-Meldung."""
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: _settings()
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_capabilities",
        lambda: {"steps": []},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )

    def raise_connection(**kw):
        raise LLMConnectionError("Timeout")

    monkeypatch.setattr("gysi_ml.services.message_service.call_llm", raise_connection)

    result = handle_message(session_id="s1", text="Test")

    assert result["type"] == "error"
    assert "LLM" in result["message"] or "Kommunikation" in result["message"]


def test_handle_message_includes_history(monkeypatch):
    """messages-Array enthält Gesprächshistorie aus der DB."""
    captured_messages: list = []

    def fake_call_llm(**kw):
        captured_messages.extend(kw.get("messages", []))
        return _VALID_EXECUTE_RESPONSE

    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_settings", lambda: _settings()
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.get_capabilities",
        lambda: {"steps": []},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [
            {"role": "user", "content": "erste Frage"},
            {"role": "assistant", "content": '{"type": "result"}'},
        ],
    )
    monkeypatch.setattr("gysi_ml.services.message_service.call_llm", fake_call_llm)
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-x"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    handle_message(session_id="s1", text="zweite Frage")

    roles = [m["role"] for m in captured_messages]
    assert "system" in roles
    assert roles.count("user") >= 1
    assert "assistant" in roles

