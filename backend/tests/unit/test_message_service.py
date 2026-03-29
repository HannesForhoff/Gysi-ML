"""Unit-Tests fuer message_service."""
import json
from unittest.mock import patch, MagicMock

import pytest

from gysi_ml.llm.exceptions import LLMConnectionError, LLMResponseValidationError
from gysi_ml.services.message_service import handle_message

# Echte Repository-Funktionen VOR jedem Mocking cachen (Modul-Ebene)
import gysi_ml.persistence.proposal_repository as _pr
_REAL_REJECT_PENDING = _pr.reject_pending_proposals
_REAL_CREATE_PROPOSAL = _pr.create_proposal
_REAL_GET_PROPOSAL = _pr.get_proposal
_REAL_GET_PENDING = _pr.get_pending_proposal


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


@pytest.fixture(autouse=True)
def patch_proposal_repository(monkeypatch):
    """Globaler Noop-Patch für proposal_repository in message_service.

    Verhindert, dass Tests ohne DB-Fixture auf eine nicht-initialisierte
    proposals-Tabelle treffen. Tests die echte Proposal-Logik prüfen
    (Story 3.3), übergeben db_path und initialisieren die DB selbst.
    """
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.reject_pending_proposals",
        lambda **kw: 0,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.create_proposal",
        lambda **kw: {"proposal_id": "mock-proposal-id"},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_latest_spec",
        lambda **kw: None,
    )


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


# ---------------------------------------------------------------------------
# Neue Tests (Story 3.3) — Proposal-Logik in message_service
# ---------------------------------------------------------------------------


def test_handle_message_propose_creates_proposal(monkeypatch, tmp_path):
    """Mock LLM → propose → Proposal wird in DB angelegt."""
    from gysi_ml.persistence.schema import create_all_tables

    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)

    # Echte Proposal-Repository-Funktionen verwenden (gecachte Referenzen aus Modul-Ebene)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.reject_pending_proposals",
        _REAL_REJECT_PENDING,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.create_proposal",
        _REAL_CREATE_PROPOSAL,
    )

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

    result = handle_message(session_id="s1", text="Bereite die Daten vor", db_path=db_file)

    assert result["type"] == "proposal"
    assert "proposal_id" in result
    assert result["proposal_id"] is not None
    # Proposal in DB vorhanden
    pending = _REAL_GET_PENDING(session_id="s1", db_path=db_file)
    assert pending is not None
    assert pending["proposal_id"] == result["proposal_id"]


def test_handle_message_implicit_rejection(monkeypatch, tmp_path):
    """Offener Proposal + neue Nachricht → alter Proposal wird rejected."""
    from gysi_ml.persistence.schema import create_all_tables

    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)

    # Echte Proposals verwenden (gecachte Referenzen aus Modul-Ebene)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.reject_pending_proposals",
        _REAL_REJECT_PENDING,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.create_proposal",
        _REAL_CREATE_PROPOSAL,
    )

    # Bestehenden Proposal mit gecachter echter Funktion anlegen
    old = _REAL_CREATE_PROPOSAL(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="alter Vorschlag",
        db_path=db_file,
    )

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

    handle_message(session_id="s1", text="neue Anfrage", db_path=db_file)

    # Alter Proposal ist rejected
    updated = _REAL_GET_PROPOSAL(proposal_id=old["proposal_id"], db_path=db_file)
    assert updated["status"] == "rejected"


def test_handle_message_execute_no_proposal(monkeypatch, tmp_path):
    """Execute-Aktion → kein Proposal in DB angelegt."""
    from gysi_ml.persistence.schema import create_all_tables

    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)

    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.reject_pending_proposals",
        _REAL_REJECT_PENDING,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.proposal_repository.create_proposal",
        _REAL_CREATE_PROPOSAL,
    )

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
    fake_executor.execute.return_value = {"run_id": "run-xyz"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    result = handle_message(session_id="s1", text="Entferne Duplikate", db_path=db_file)

    assert result["type"] == "result"
    # Kein Proposal in DB
    pending = _REAL_GET_PENDING(session_id="s1", db_path=db_file)
    assert pending is None


# ---------------------------------------------------------------------------
# Tests für compare_runs (Story 4.3)
# ---------------------------------------------------------------------------

_VALID_COMPARE_RESPONSE = json.dumps(
    {
        "action": "compare_runs",
        "spec": {"steps": []},
        "explanation": "Vergleiche zwei Runs.",
        "run_id_a": "run-aaa",
        "run_id_b": "run-bbb",
    }
)


def _mock_get_run(run_id, db_path=None):
    """Erzeugt Mock-Runs mit Metriken für Vergleichstests."""
    runs = {
        "run-aaa": {
            "run_id": "run-aaa",
            "session_id": "s1",
            "status": "completed",
            "result": {"metrics": {"rmse": 50.0, "mae": 40.0, "r2": 0.85}},
        },
        "run-bbb": {
            "run_id": "run-bbb",
            "session_id": "s1",
            "status": "completed",
            "result": {"metrics": {"rmse": 60.0, "mae": 45.0, "r2": 0.78}},
        },
    }
    return runs.get(run_id)


def test_compare_runs_returns_comparison_type(monkeypatch):
    """compare_runs → type='comparison' mit runs-Array."""
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
        lambda **kw: _VALID_COMPARE_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.persistence.run_repository.get_run", _mock_get_run
    )

    result = handle_message(session_id="s1", text="Vergleiche Run aaa mit bbb")

    assert result["type"] == "comparison"
    assert len(result["runs"]) == 2
    assert result["runs"][0]["run_id"] == "run-aaa"
    assert result["runs"][1]["run_id"] == "run-bbb"


def test_compare_runs_unknown_run_returns_error(monkeypatch):
    """Run-ID nicht in Session → error-Type."""
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
    compare_unknown = json.dumps(
        {
            "action": "compare_runs",
            "spec": {"steps": []},
            "explanation": "Vergleich.",
            "run_id_a": "run-unknown",
            "run_id_b": "run-bbb",
        }
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: compare_unknown,
    )
    monkeypatch.setattr(
        "gysi_ml.persistence.run_repository.get_run", _mock_get_run
    )

    result = handle_message(session_id="s1", text="Vergleiche")

    assert result["type"] == "error"
    assert "run-unknown" in result["message"]


def test_compare_runs_identifies_better_r2(monkeypatch):
    """Run mit höherem R² als better_run_id identifiziert."""
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
        lambda **kw: _VALID_COMPARE_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.persistence.run_repository.get_run", _mock_get_run
    )

    result = handle_message(session_id="s1", text="Vergleiche")

    assert result["better_run_id"] == "run-aaa"  # R² 0.85 > 0.78


def test_compare_runs_no_metrics_returns_null_better(monkeypatch):
    """Runs ohne Metriken → better_run_id ist None."""
    def _mock_no_metrics(run_id, db_path=None):
        runs = {
            "run-aaa": {"run_id": "run-aaa", "session_id": "s1", "status": "completed", "result": {}},
            "run-bbb": {"run_id": "run-bbb", "session_id": "s1", "status": "completed", "result": {}},
        }
        return runs.get(run_id)

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
        lambda **kw: _VALID_COMPARE_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.persistence.run_repository.get_run", _mock_no_metrics
    )

    result = handle_message(session_id="s1", text="Vergleiche")

    assert result["type"] == "comparison"
    assert result["better_run_id"] is None


# ---------------------------------------------------------------------------
# Tests für modify_spec (Story 4.2)
# ---------------------------------------------------------------------------

_VALID_MODIFY_SPEC_RESPONSE = json.dumps(
    {
        "action": "modify_spec",
        "spec": {"steps": [{"type": "dedup", "params": {}}]},
        "explanation": "Spec modifiziert.",
    }
)

_INVALID_MODIFY_SPEC_RESPONSE = json.dumps(
    {
        "action": "modify_spec",
        "spec": {"steps": [{"type": "dedup", "unknown_field": True}]},
        "explanation": "Kaputte Spec.",
    }
)


def test_modify_spec_returns_spec_updated(monkeypatch, tmp_path):
    """modify_spec → type='spec_updated' mit spec_id, version, spec."""
    from gysi_ml.persistence.schema import create_all_tables

    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)

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
        lambda **kw: _VALID_MODIFY_SPEC_RESPONSE,
    )

    result = handle_message(session_id="s1", text="Ändere Strategie", db_path=db_file)

    assert result["type"] == "spec_updated"
    assert "spec_id" in result
    assert result["version"] == "v1"
    assert result["spec"] == {"steps": [{"type": "dedup", "params": {}}]}
    assert "explanation" in result


def test_modify_spec_invalid_spec_returns_error(monkeypatch):
    """modify_spec mit ungültiger Spec → type='error'."""
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
        lambda **kw: _INVALID_MODIFY_SPEC_RESPONSE,
    )

    result = handle_message(session_id="s1", text="Kaputte Spec")

    assert result["type"] == "error"
    assert "Ungültige Spec" in result["message"]


def test_modify_spec_invalid_order_returns_error(monkeypatch):
    """modify_spec mit ungültiger Step-Reihenfolge → type='error'."""
    bad_order = json.dumps(
        {
            "action": "modify_spec",
            "spec": {"steps": [
                {"type": "train_decision_tree", "params": {}},
                {"type": "split", "params": {"test_size": 0.2}},
            ]},
            "explanation": "Falsche Reihenfolge.",
        }
    )
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
        lambda **kw: bad_order,
    )

    result = handle_message(session_id="s1", text="Bad order")

    assert result["type"] == "error"


# ---------------------------------------------------------------------------
# Tests für Re-Execution / spec_version_ref (Story 4.1)
# ---------------------------------------------------------------------------


def test_re_execution_calls_execute_with_spec_id(monkeypatch):
    """execute mit spec_version → execute_with_spec_id aufgerufen."""
    re_exec_response = json.dumps(
        {
            "action": "execute",
            "spec": {"steps": []},
            "explanation": "Re-Execute Spec v1.",
            "spec_version": "v1",
        }
    )
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
        lambda **kw: re_exec_response,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_spec_by_version",
        lambda **kw: {"spec_id": "spec-abc", "spec": {"steps": [{"type": "dedup"}]}, "version": "v1"},
    )
    fake_executor = MagicMock()
    fake_executor.execute_with_spec_id.return_value = {"run_id": "run-re"}
    monkeypatch.setattr(
        "gysi_ml.services.message_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    result = handle_message(session_id="s1", text="Führe Spec v1 erneut aus")

    assert result["type"] == "result"
    assert result["run_id"] == "run-re"
    fake_executor.execute_with_spec_id.assert_called_once()


def test_re_execution_unknown_version_returns_error(monkeypatch):
    """execute mit unbekannter spec_version → type='error'."""
    re_exec_response = json.dumps(
        {
            "action": "execute",
            "spec": {"steps": []},
            "explanation": "Re-Execute Spec v99.",
            "spec_version": "v99",
        }
    )
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
        lambda **kw: re_exec_response,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_spec_by_version",
        lambda **kw: None,
    )

    result = handle_message(session_id="s1", text="Führe Spec v99 aus")

    assert result["type"] == "error"
    assert "v99" in result["message"]


def test_compare_runs_missing_run_ids_returns_error(monkeypatch):
    """compare_runs ohne run_id_a/b → type='error'."""
    no_ids = json.dumps(
        {
            "action": "compare_runs",
            "spec": {"steps": []},
            "explanation": "Vergleich ohne IDs.",
        }
    )
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
        lambda **kw: no_ids,
    )

    result = handle_message(session_id="s1", text="Vergleiche")

    assert result["type"] == "error"
    assert "Zwei Run-IDs" in result["message"]


def test_compare_runs_run_b_not_found_returns_error(monkeypatch):
    """compare_runs: run_b nicht in Session → error."""
    compare_b_bad = json.dumps(
        {
            "action": "compare_runs",
            "spec": {"steps": []},
            "explanation": "Vergleich.",
            "run_id_a": "run-aaa",
            "run_id_b": "run-missing",
        }
    )
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
        lambda **kw: compare_b_bad,
    )
    monkeypatch.setattr(
        "gysi_ml.persistence.run_repository.get_run", _mock_get_run
    )

    result = handle_message(session_id="s1", text="Vergleiche")

    assert result["type"] == "error"
    assert "run-missing" in result["message"]

