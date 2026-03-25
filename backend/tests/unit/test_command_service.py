"""Unit-Tests für CommandService (Story 6.2)."""
from unittest.mock import MagicMock, patch

import pytest

from gysi_ml.services.command_service import KNOWN_COMMANDS, CommandService


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

MOCK_HELP_TEXTS = {
    "help": {
        "categories": {
            "daten": "Datensatz erkunden: /overview, Profiling",
            "preprocessing": "Dedup, Imputation, Encoding, Outlier Handling",
            "modellierung": "Decision Tree, EBM, CatBoost",
            "pipeline": "Spec-Abruf, Re-Execution, Parameter-Anpassung",
            "grenzen": "Nur Bike-Datensatz, kein Code-Upload",
        }
    }
}


@pytest.fixture()
def svc():
    return CommandService()


@pytest.fixture()
def svc_with_mock_help(svc):
    """CommandService mit gemocktem _load_help_texts."""
    svc._load_help_texts = lambda: MOCK_HELP_TEXTS
    return svc


# ---------------------------------------------------------------------------
# AC 8 — is_slash_command() ohne DB isoliert testbar
# ---------------------------------------------------------------------------


def test_is_slash_command_true(svc):
    assert svc.is_slash_command("/help") is True


def test_is_slash_command_true_with_whitespace(svc):
    assert svc.is_slash_command("  /status  ") is True


def test_is_slash_command_false(svc):
    assert svc.is_slash_command("normale Nachricht") is False


def test_is_slash_command_false_empty(svc):
    assert svc.is_slash_command("") is False


# ---------------------------------------------------------------------------
# AC 2 — /help gibt alle Kategorien zurück
# ---------------------------------------------------------------------------


def test_help_all_categories(svc_with_mock_help):
    result = svc_with_mock_help.handle("/help", session_id="s1")
    for category in ("daten", "preprocessing", "modellierung", "pipeline", "grenzen"):
        assert category in result


# ---------------------------------------------------------------------------
# AC 3 — /help <thema> filtert auf eine Kategorie
# ---------------------------------------------------------------------------


def test_help_filtered(svc_with_mock_help):
    result = svc_with_mock_help.handle("/help preprocessing", session_id="s1")
    assert "preprocessing" in result
    assert "Dedup" in result
    # Andere Kategorien dürfen nicht im Ergebnis stehen
    assert "modellierung" not in result


def test_help_filtered_unknown_topic(svc_with_mock_help):
    result = svc_with_mock_help.handle("/help unbekannt", session_id="s1")
    assert "Unbekanntes Thema" in result
    assert "unbekannt" in result


# ---------------------------------------------------------------------------
# AC 6 — Unbekannter Command → strukturierter Fehler
# ---------------------------------------------------------------------------


def test_unknown_command(svc):
    result = svc.handle("/foo", session_id="s1")
    assert "Unbekannter Command" in result
    assert "/foo" in result
    for cmd in KNOWN_COMMANDS:
        assert cmd in result


# ---------------------------------------------------------------------------
# AC 5 — /status ohne Spec und ohne Runs
# ---------------------------------------------------------------------------


def test_status_no_spec_no_runs(svc):
    with (
        patch("gysi_ml.persistence.spec_repository.get_latest_spec", return_value=None),
        patch(
            "gysi_ml.persistence.run_repository.get_runs_for_session", return_value=[]
        ),
    ):
        result = svc.handle("/status", session_id="s1", db_path=None)

    assert "Keine Pipeline konfiguriert" in result
    assert "Noch keine Runs ausgeführt" in result


# ---------------------------------------------------------------------------
# AC 5 — /status mit Spec und einem Run (mit Metriken)
# ---------------------------------------------------------------------------


def test_status_with_spec_and_run(svc):
    mock_spec = {
        "spec_id": "abcd1234-5678-0000-0000-000000000000",
        "version": "v3",
        "spec": {"steps": [{"type": "dedup", "enabled": True}]},
    }
    mock_runs = [{"run_id": "run-1", "status": "success"}]
    mock_full_run = {"result": {"metrics": {"r2": 0.85, "rmse": 12.3456}}}

    with (
        patch("gysi_ml.persistence.spec_repository.get_latest_spec", return_value=mock_spec),
        patch(
            "gysi_ml.persistence.run_repository.get_runs_for_session",
            return_value=mock_runs,
        ),
        patch(
            "gysi_ml.persistence.run_repository.get_run", return_value=mock_full_run
        ),
    ):
        result = svc.handle("/status", session_id="s1", db_path=None)

    assert "v3" in result
    assert "abcd1234" in result
    assert "success" in result
    assert "r2: 0.8500" in result
    assert "dedup" in result


# ---------------------------------------------------------------------------
# AC 4 — /overview delegiert an ProfilingService
# ---------------------------------------------------------------------------


def test_overview_delegates_to_profiling_service(svc):
    with patch(
        "gysi_ml.services.profiling_service.ProfilingService.profile_raw",
        return_value="## Datensatz-Überblick\n**Zeilen:** 1000",
    ) as mock_raw:
        result = svc.handle("/overview", session_id="s1")

    mock_raw.assert_called_once()
    assert "Datensatz-Überblick" in result


# ---------------------------------------------------------------------------
# AC 7 — Slash-Command-Responses werden persistiert (Integration)
# ---------------------------------------------------------------------------


def test_slash_command_response_persisted(tmp_path):
    """POST /help → HTTP 200, User- und Assistant-Message in Session-History (AC 7)."""
    from fastapi.testclient import TestClient

    from gysi_ml.api.app import create_app
    from gysi_ml.config import Settings

    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        openai_api_key="",
        llm_model="",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        session_id = client.post("/v1/sessions", json={"name": "T"}).json()["session_id"]

        resp = client.post(f"/v1/sessions/{session_id}/messages", json={"text": "/help"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "assistant"
        assert "Gysi-Hilfe" in body["message"]

        # Session-History: user-Message mit "/help" ist gespeichert
        messages = client.get(f"/v1/sessions/{session_id}").json()["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0]["content"] == "/help"

        # Assistant-Antwort auf /help ist in History (Welcome + /help-Response)
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 2
        # Letzte assistant-Message enthält help-Response (JSON-serialisiert in DB)
        import json as _json
        last_assistant = assistant_msgs[-1]["content"]
        parsed = _json.loads(last_assistant)
        assert parsed["type"] == "assistant"
        assert "Gysi-Hilfe" in parsed["message"]
