"""Unit-Tests für llm/response_schema.py."""
import json

import pytest

from gysi_ml.llm.exceptions import LLMResponseValidationError
from gysi_ml.llm.response_schema import validate_llm_response


def _valid_execute() -> str:
    return json.dumps(
        {
            "action": "execute",
            "spec": {"steps": [{"type": "dedup", "params": {}}]},
            "explanation": "Duplikate entfernen.",
        }
    )


def _valid_propose() -> str:
    return json.dumps(
        {
            "action": "propose",
            "spec": {"steps": [{"type": "split", "params": {"test_size": 0.2}}]},
            "explanation": "Ich schlage vor, die Daten zu splitten.",
        }
    )


def test_valid_execute_response():
    """Gültiges execute-JSON → dict mit action='execute' wird zurückgegeben."""
    result = validate_llm_response(_valid_execute())
    assert result["action"] == "execute"
    assert "spec" in result
    assert "explanation" in result


def test_valid_propose_response():
    """Gültiges propose-JSON → dict mit action='propose' wird zurückgegeben."""
    result = validate_llm_response(_valid_propose())
    assert result["action"] == "propose"


def test_valid_response_strips_markdown_codeblock():
    """LLM-Antwort in Markdown-Codeblock wird bereinigt."""
    wrapped = "```json\n" + _valid_execute() + "\n```"
    result = validate_llm_response(wrapped)
    assert result["action"] == "execute"


def test_valid_response_strips_bare_codeblock():
    """LLM-Antwort in ``` (ohne json) wird ebenfalls bereinigt."""
    wrapped = "```\n" + _valid_execute() + "\n```"
    result = validate_llm_response(wrapped)
    assert result["action"] == "execute"


def test_none_response():
    """None als Eingabe → LLMResponseValidationError (kein TypeError)."""
    with pytest.raises(LLMResponseValidationError, match="Ungültiges JSON"):
        validate_llm_response(None)


def test_invalid_json():
    """Kein gültiges JSON → LLMResponseValidationError."""
    with pytest.raises(LLMResponseValidationError, match="Ungültiges JSON"):
        validate_llm_response("das ist kein json")


def test_missing_action():
    """Fehlendes 'action'-Feld → LLMResponseValidationError."""
    payload = json.dumps(
        {
            "spec": {"steps": [{"type": "dedup"}]},
            "explanation": "Test",
        }
    )
    with pytest.raises(LLMResponseValidationError, match="Schema-Verletzung"):
        validate_llm_response(payload)


def test_invalid_action_value():
    """Ungültiger action-Wert → LLMResponseValidationError."""
    payload = json.dumps(
        {
            "action": "something_else",
            "spec": {"steps": [{"type": "dedup"}]},
            "explanation": "Test",
        }
    )
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)


def test_missing_spec():
    """Fehlendes 'spec'-Feld → LLMResponseValidationError."""
    payload = json.dumps({"action": "execute", "explanation": "Test"})
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)


def test_missing_explanation():
    """Fehlendes 'explanation'-Feld → LLMResponseValidationError."""
    payload = json.dumps(
        {"action": "execute", "spec": {"steps": [{"type": "dedup"}]}}
    )
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)


def test_invalid_spec_structure():
    """spec ohne 'steps'-Array → LLMResponseValidationError."""
    payload = json.dumps(
        {"action": "execute", "spec": {}, "explanation": "Test"}
    )
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)


def test_additional_properties_rejected():
    """Zusätzliche Top-Level-Felder → LLMResponseValidationError."""
    payload = json.dumps(
        {
            "action": "execute",
            "spec": {"steps": [{"type": "dedup"}]},
            "explanation": "Test",
            "unknown_field": "should fail",
        }
    )
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)


# ---------------------------------------------------------------------------
# modify_spec wurde entfernt (Bugfix): Spec-Versionen dürfen nur über eine
# echte Pipeline-Ausführung entstehen, nie über eine reine Spec-Beschriftung.
# ---------------------------------------------------------------------------


def test_modify_spec_action_is_rejected():
    """action: 'modify_spec' existiert nicht mehr → LLMResponseValidationError."""
    payload = json.dumps(
        {
            "action": "modify_spec",
            "spec": {"steps": [{"type": "dedup", "params": {}}]},
            "explanation": "Imputationsstrategie geändert.",
        }
    )
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)


# ---------------------------------------------------------------------------
# Tests für compare_runs Action (Story 4.3 / T10)
# ---------------------------------------------------------------------------


def test_compare_runs_action_is_valid():
    """action: 'compare_runs' mit run_id_a und run_id_b passiert Validierung."""
    payload = json.dumps(
        {
            "action": "compare_runs",
            "spec": {"steps": []},
            "explanation": "Vergleiche zwei Runs.",
            "run_id_a": "run-aaa",
            "run_id_b": "run-bbb",
        }
    )
    result = validate_llm_response(payload)
    assert result["action"] == "compare_runs"
    assert result["run_id_a"] == "run-aaa"
    assert result["run_id_b"] == "run-bbb"


def test_compare_runs_without_run_ids_is_valid():
    """Schema erlaubt fehlende run_id_a/b (optional)."""
    payload = json.dumps(
        {
            "action": "compare_runs",
            "spec": {"steps": []},
            "explanation": "Vergleich ohne IDs.",
        }
    )
    result = validate_llm_response(payload)
    assert result["action"] == "compare_runs"
    assert "run_id_a" not in result


def test_invalid_action_still_rejected():
    """Ungültige Action (nicht execute/propose/compare_runs/rollback/abort_step_by_step/info) schlägt fehl."""
    payload = json.dumps(
        {
            "action": "delete_everything",
            "spec": {"steps": [{"type": "dedup"}]},
            "explanation": "Test",
        }
    )
    with pytest.raises(LLMResponseValidationError):
        validate_llm_response(payload)
