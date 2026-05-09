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
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.create_spec_version",
        lambda **kw: {"spec_id": "spec-auto", "version": "v1", "spec": kw.get("spec", {})},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.run_repository.update_run_spec_ref",
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
    # Persistente Steps → create_spec_version + execute_with_spec_id
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.create_spec_version",
        lambda **kw: {"spec_id": "spec-mock", "version": "v1", "spec": kw.get("spec", {})},
    )
    fake_executor = MagicMock()
    fake_executor.execute_with_spec_id.return_value = {"run_id": "run-123"}
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

    assert call_count["n"] == 3  # 1× ungültig, 1× retry-gültig, 1× post_run
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


# ---------------------------------------------------------------------------
# Tests für Rollback via Chat / LLM (Bug 1.15)
# ---------------------------------------------------------------------------

_VALID_ROLLBACK_WITH_VERSION_RESPONSE = json.dumps(
    {
        "action": "rollback",
        "target_version": "v2",
        "spec": {"steps": []},
        "explanation": "Rollback zu v2.",
    }
)

_VALID_ROLLBACK_WITH_SPEC_ID_RESPONSE = json.dumps(
    {
        "action": "rollback",
        "target_spec_id": "spec-id-v1",
        "spec": {"steps": []},
        "explanation": "Rollback zu spec-id-v1.",
    }
)

_ROLLBACK_MISSING_BOTH_RESPONSE = json.dumps(
    {
        "action": "rollback",
        "spec": {"steps": []},
        "explanation": "Rollback ohne Ziel.",
    }
)


def _common_rollback_patches(monkeypatch):
    """Setzt Standard-Patches für Rollback-Tests."""
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
        "gysi_ml.services.message_service.spec_repository.get_all_specs_for_session",
        lambda **kw: [],
    )


def test_rollback_with_target_version_resolves_to_spec_id(monkeypatch):
    """target_version wird über get_spec_id_by_version aufgelöst → rollback_to korrekt aufgerufen."""
    _common_rollback_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_ROLLBACK_WITH_VERSION_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_spec_id_by_version",
        lambda **kw: "resolved-spec-id-v2",
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.rollback_to",
        lambda **kw: {
            "spec_id": "new-spec-id",
            "version": "v3",
            "change_summary": "Rollback auf v2",
        },
    )

    result = handle_message(session_id="s1", text="Mach Rollback auf v2")

    assert result["type"] == "rollback"
    assert result["new_version"] == "v3"
    assert "Rollback" in result["change_summary"]


def test_rollback_with_target_version_not_found_returns_error(monkeypatch):
    """target_version existiert nicht in Session → type='error'."""
    _common_rollback_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_ROLLBACK_WITH_VERSION_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_spec_id_by_version",
        lambda **kw: None,
    )

    result = handle_message(session_id="s1", text="Rollback auf v2")

    assert result["type"] == "error"
    assert "v2" in result["message"]


def test_rollback_with_spec_id_backward_compat(monkeypatch):
    """target_spec_id ohne target_version → backward-kompatibel, rollback_to korrekt aufgerufen."""
    _common_rollback_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_ROLLBACK_WITH_SPEC_ID_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.rollback_to",
        lambda **kw: {
            "spec_id": "new-spec-id",
            "version": "v2",
            "change_summary": "Rollback auf v1",
        },
    )

    result = handle_message(session_id="s1", text="Rollback auf spec-id-v1")

    assert result["type"] == "rollback"
    assert result["new_version"] == "v2"


def test_rollback_missing_both_version_and_spec_id_returns_error(monkeypatch):
    """Weder target_version noch target_spec_id → type='error'."""
    _common_rollback_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _ROLLBACK_MISSING_BOTH_RESPONSE,
    )

    result = handle_message(session_id="s1", text="Rollback")

    assert result["type"] == "error"
    assert "target_version" in result["message"] or "target_spec_id" in result["message"]


def test_rollback_spec_id_not_found_after_version_resolution(monkeypatch):
    """rollback_to gibt None zurück (ungültige spec_id nach Auflösung) → type='error'."""
    _common_rollback_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_ROLLBACK_WITH_VERSION_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_spec_id_by_version",
        lambda **kw: "some-id",
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.rollback_to",
        lambda **kw: None,
    )

    result = handle_message(session_id="s1", text="Rollback auf v2")

    assert result["type"] == "error"
    assert "some-id" in result["message"]


# ---------------------------------------------------------------------------
# Tests: _step_result_is_effective und _new_persistent_steps_are_effective
# ---------------------------------------------------------------------------

from gysi_ml.services.message_service import (  # noqa: E402
    _step_result_is_effective,
    _new_persistent_steps_are_effective,
)


class TestStepResultIsEffective:
    def test_encode_empty_columns_is_noop(self):
        sr = {"step_type": "encode_categorical", "metadata": {"encoded_columns": []}}
        assert _step_result_is_effective(sr) is False

    def test_encode_with_columns_is_effective(self):
        sr = {"step_type": "encode_categorical", "metadata": {"encoded_columns": ["season_1", "season_2"]}}
        assert _step_result_is_effective(sr) is True

    def test_encode_missing_metadata_is_noop(self):
        """Fehlendes metadata-Dict → encoded_columns fehlt → False."""
        sr = {"step_type": "encode_categorical"}
        assert _step_result_is_effective(sr) is False

    def test_correlation_filter_analysis_only_is_noop(self):
        sr = {"step_type": "correlation_filter", "metadata": {"analysis_only": True}}
        assert _step_result_is_effective(sr) is False

    def test_correlation_filter_not_analysis_only_is_effective(self):
        sr = {"step_type": "correlation_filter", "metadata": {"analysis_only": False}}
        assert _step_result_is_effective(sr) is True

    def test_unknown_step_type_defaults_to_effective(self):
        sr = {"step_type": "dedup", "metadata": {}}
        assert _step_result_is_effective(sr) is True

    def test_cast_dtype_is_effective(self):
        sr = {"step_type": "cast_dtype", "metadata": {}}
        assert _step_result_is_effective(sr) is True


class TestNewPersistentStepsAreEffective:
    def test_empty_step_types_is_rerun_always_true(self):
        """Re-Run: neue Typen leer → immer wirksam."""
        assert _new_persistent_steps_are_effective([], set()) is True

    def test_empty_results_with_step_types_is_conservative_true(self):
        """Keine Metadaten (z.B. Test-Mocks ohne step_results) → konservativ wirksam."""
        assert _new_persistent_steps_are_effective([], {"encode_categorical"}) is True

    def test_encode_noop_returns_false(self):
        results = [{"step_type": "encode_categorical", "metadata": {"encoded_columns": []}}]
        assert _new_persistent_steps_are_effective(results, {"encode_categorical"}) is False

    def test_encode_effective_returns_true(self):
        results = [{"step_type": "encode_categorical", "metadata": {"encoded_columns": ["season_1"]}}]
        assert _new_persistent_steps_are_effective(results, {"encode_categorical"}) is True

    def test_mixed_effective_and_noop_returns_true(self):
        """Mindestens ein wirksamer Step → Gesamt-Ergebnis wirksam."""
        results = [
            {"step_type": "encode_categorical", "metadata": {"encoded_columns": []}},
            {"step_type": "dedup", "metadata": {}},
        ]
        assert _new_persistent_steps_are_effective(results, {"encode_categorical", "dedup"}) is True

    def test_all_noops_returns_false(self):
        """Alle Steps sind No-Ops → False."""
        results = [
            {"step_type": "encode_categorical", "metadata": {"encoded_columns": []}},
            {"step_type": "correlation_filter", "metadata": {"analysis_only": True}},
        ]
        assert _new_persistent_steps_are_effective(
            results, {"encode_categorical", "correlation_filter"}
        ) is False


# ---------------------------------------------------------------------------
# Integrations-Tests: handle_message — encode_categorical No-Op-Erkennung
# ---------------------------------------------------------------------------

_VALID_ENCODE_EXECUTE_RESPONSE = json.dumps({
    "action": "execute",
    "spec": {"steps": [{"type": "encode_categorical", "params": {"method": "onehot", "columns": ["season"]}}]},
    "explanation": "One-Hot-Encoding für season.",
})

_EXISTING_SPLIT_SPEC = {
    "spec_id": "old-spec-id",
    "version": "v2",
    "spec": {"steps": [{"type": "split", "params": {"test_size": 0.2}}]},
    "change_summary": None,
}


def _setup_encode_patches(monkeypatch, current_spec=_EXISTING_SPLIT_SPEC):
    """Gemeinsame Patches für encode-Integrationstests."""
    monkeypatch.setattr("gysi_ml.services.message_service.get_settings", lambda: _settings())
    monkeypatch.setattr("gysi_ml.services.message_service.get_capabilities", lambda: {"steps": []})
    monkeypatch.setattr(
        "gysi_ml.services.message_service.message_repository.get_messages_for_session",
        lambda **kw: [],
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.call_llm",
        lambda **kw: _VALID_ENCODE_EXECUTE_RESPONSE,
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.get_latest_spec",
        lambda **kw: current_spec,
    )


def test_no_spec_version_when_encode_is_noop(monkeypatch):
    """encode_categorical auf int64-Spalte (encoded_columns=[]) → keine neue Spec-Version."""
    create_calls: list[dict] = []
    _setup_encode_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.create_spec_version",
        lambda **kw: create_calls.append(kw) or {"spec_id": "new", "version": "v3", "spec": kw.get("spec", {})},
    )

    fake_executor = MagicMock()
    fake_executor.execute_with_spec_id.return_value = {
        "run_id": "run-encode-noop",
        "result": {
            "step_results": [
                {
                    "step_type": "encode_categorical",
                    "status": "completed",
                    "metadata": {
                        "encoded_columns": [],
                        "warnings": ["season: Kein kategorischer Dtype (int64), wird übersprungen."],
                    },
                }
            ]
        },
    }
    monkeypatch.setattr("gysi_ml.services.message_service.PipelineExecutor", lambda **kw: fake_executor)

    result = handle_message(session_id="s1", text="OneHot Encoding für season")

    assert result["type"] == "result"
    assert create_calls == [], "Keine neue Spec-Version erwartet wenn encode_categorical ein No-Op war"


def test_spec_version_created_when_encode_is_effective(monkeypatch):
    """encode_categorical auf category-Spalte (encoded_columns nicht leer) → neue Spec-Version."""
    create_calls: list[dict] = []

    cast_spec = {
        "spec_id": "cast-spec-id",
        "version": "v3",
        "spec": {"steps": [
            {"type": "split", "params": {"test_size": 0.2}},
            {"type": "cast_dtype", "params": {"columns": {"season": "category"}}},
        ]},
        "change_summary": "+ cast_dtype: season → category",
    }
    _setup_encode_patches(monkeypatch, current_spec=cast_spec)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.create_spec_version",
        lambda **kw: create_calls.append(kw) or {"spec_id": "enc-spec", "version": "v4", "spec": kw.get("spec", {})},
    )
    monkeypatch.setattr(
        "gysi_ml.services.message_service.run_repository.update_run_spec_ref",
        lambda **kw: None,
    )

    fake_executor = MagicMock()
    fake_executor.execute_with_spec_id.return_value = {
        "run_id": "run-encode-ok",
        "result": {
            "step_results": [
                {"step_type": "split", "status": "completed", "metadata": {}},
                {"step_type": "cast_dtype", "status": "completed", "metadata": {}},
                {
                    "step_type": "encode_categorical",
                    "status": "completed",
                    "metadata": {"encoded_columns": ["season_1", "season_2", "season_3", "season_4"], "method": "onehot"},
                },
            ]
        },
    }
    monkeypatch.setattr("gysi_ml.services.message_service.PipelineExecutor", lambda **kw: fake_executor)

    result = handle_message(session_id="s1", text="OneHot Encoding für season")

    assert result["type"] == "result"
    assert len(create_calls) == 1, "Neue Spec-Version erwartet wenn encode_categorical wirksam war"


def test_no_spec_version_preserves_current_spec_in_response(monkeypatch):
    """Bei No-Op-Encode: spec_for_response zeigt aktuelle Spec (ohne no-op Step), nicht merged_persistent."""
    _setup_encode_patches(monkeypatch)
    monkeypatch.setattr(
        "gysi_ml.services.message_service.spec_repository.create_spec_version",
        lambda **kw: {"spec_id": "new", "version": "v3", "spec": kw.get("spec", {})},
    )

    fake_executor = MagicMock()
    fake_executor.execute_with_spec_id.return_value = {
        "run_id": "run-noop",
        "result": {
            "step_results": [
                {
                    "step_type": "encode_categorical",
                    "status": "completed",
                    "metadata": {"encoded_columns": []},
                }
            ]
        },
    }
    monkeypatch.setattr("gysi_ml.services.message_service.PipelineExecutor", lambda **kw: fake_executor)

    result = handle_message(session_id="s1", text="OneHot Encoding für season")

    assert result["type"] == "result"
    # Die zurückgegebene Spec darf encode_categorical nicht enthalten (war No-Op)
    returned_steps = result.get("spec", {}).get("steps", [])
    step_types = [s.get("type") for s in returned_steps]
    assert "encode_categorical" not in step_types, (
        "spec_for_response darf encode_categorical nicht enthalten wenn es ein No-Op war"
    )

