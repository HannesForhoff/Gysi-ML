"""Unit-Tests für selektive Step-Bestätigung (Story 9.2)."""
import json
from unittest.mock import MagicMock

import pytest

from gysi_ml.persistence.proposal_repository import create_proposal
from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.services.proposal_service import confirm_proposal

_SPEC_3_STEPS = {
    "steps": [
        {"type": "dedup", "params": {}},
        {"type": "imputation", "params": {"strategy": "mean"}},
        {"type": "encoding", "params": {"method": "onehot"}},
    ]
}

_SPEC_1_STEP = {
    "steps": [
        {"type": "dedup", "params": {}},
    ]
}


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


def _settings(data_path="/tmp/bikes.csv", artifacts_path="/tmp/art"):
    s = MagicMock()
    s.data_path = data_path
    s.artifacts_path = artifacts_path
    return s


def _patch_executor(monkeypatch, return_value=None):
    if return_value is None:
        return_value = {"run_id": "run-sel-abc"}
    fake_executor = MagicMock()
    fake_executor.execute.return_value = return_value
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_settings",
        lambda: _settings(),
    )
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )
    return fake_executor


# ---------------------------------------------------------------------------
# AC 1 — Selektive Ausführung: confirmed_steps filtert die Spec
# ---------------------------------------------------------------------------


def test_confirmed_steps_filters_spec(db, monkeypatch):
    """confirmed_steps=[0, 2] → Step 1 erhält enabled=False, Steps 0+2 enabled=True."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_3_STEPS),
        explanation="Test",
        db_path=db,
    )
    fake_executor = _patch_executor(monkeypatch)

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=[0, 2],
        db_path=db,
    )

    assert result["type"] == "result"
    executed_spec = fake_executor.execute.call_args.kwargs["spec"]
    steps = executed_spec["steps"]
    assert steps[0].get("enabled", True) is True
    assert steps[1]["enabled"] is False
    assert steps[2].get("enabled", True) is True


def test_confirmed_steps_index_0_only(db, monkeypatch):
    """Nur Step 0 ausgewählt → Steps 1 und 2 haben enabled=False."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_3_STEPS),
        explanation="Test",
        db_path=db,
    )
    fake_executor = _patch_executor(monkeypatch)

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=[0],
        db_path=db,
    )

    assert result["type"] == "result"
    executed_spec = fake_executor.execute.call_args.kwargs["spec"]
    steps = executed_spec["steps"]
    assert steps[0].get("enabled", True) is True
    assert steps[1]["enabled"] is False
    assert steps[2]["enabled"] is False


# ---------------------------------------------------------------------------
# AC 2 — Rückwärtskompatibilität: confirmed_steps=None → alle Steps
# ---------------------------------------------------------------------------


def test_no_confirmed_steps_runs_all(db, monkeypatch):
    """Kein confirmed_steps-Parameter → Spec unverändert, alle Steps ausgeführt."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_3_STEPS),
        explanation="Test",
        db_path=db,
    )
    fake_executor = _patch_executor(monkeypatch)

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=None,
        db_path=db,
    )

    assert result["type"] == "result"
    executed_spec = fake_executor.execute.call_args.kwargs["spec"]
    steps = executed_spec["steps"]
    # Kein 'enabled'-Feld gesetzt worden → alle Steps aktiv
    for step in steps:
        assert "enabled" not in step or step["enabled"] is True


def test_confirmed_steps_omitted_runs_all(db, monkeypatch):
    """Ohne confirmed_steps-Argument (Default None) → Spec unverändert."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_3_STEPS),
        explanation="Test",
        db_path=db,
    )
    fake_executor = _patch_executor(monkeypatch)

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        db_path=db,  # confirmed_steps nicht übergeben
    )

    assert result["type"] == "result"
    fake_executor.execute.assert_called_once()


# ---------------------------------------------------------------------------
# AC 3 — Leeres Array → strukturierter Fehler
# ---------------------------------------------------------------------------


def test_empty_confirmed_steps_error(db):
    """confirmed_steps=[] → error_code='no_steps_selected', kein 500."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_3_STEPS),
        explanation="Test",
        db_path=db,
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=[],
        db_path=db,
    )

    assert result["type"] == "error"
    assert result["error_code"] == "no_steps_selected"
    assert "Mindestens" in result["message"]


# ---------------------------------------------------------------------------
# Bounds-Check — Out-of-range Index → strukturierter Fehler
# ---------------------------------------------------------------------------


def test_confirmed_steps_out_of_range(db):
    """Index außerhalb gültigen Bereichs → error_code='step_index_out_of_range'."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_1_STEP),
        explanation="Test",
        db_path=db,
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=[0, 5],  # Index 5 existiert nicht
        db_path=db,
    )

    assert result["type"] == "error"
    assert result["error_code"] == "step_index_out_of_range"


# ---------------------------------------------------------------------------
# HIGH Fix — Proposal bleibt pending nach Validierungsfehler
# ---------------------------------------------------------------------------


def test_proposal_stays_pending_after_empty_steps_error(db):
    """confirmed_steps=[] → Fehler, aber Proposal bleibt pending (nicht 'confirmed')."""
    from gysi_ml.persistence import proposal_repository

    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_3_STEPS),
        explanation="Test",
        db_path=db,
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=[],
        db_path=db,
    )

    assert result["error_code"] == "no_steps_selected"
    # Proposal muss noch pending sein — kann erneut bestätigt werden
    proposal = proposal_repository.get_proposal(
        proposal_id=row["proposal_id"], db_path=db
    )
    assert proposal["status"] == "pending"


def test_proposal_stays_pending_after_out_of_range_error(db):
    """confirmed_steps=[0, 99] → Fehler, aber Proposal bleibt pending."""
    from gysi_ml.persistence import proposal_repository

    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC_1_STEP),
        explanation="Test",
        db_path=db,
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        confirmed_steps=[0, 99],
        db_path=db,
    )

    assert result["error_code"] == "step_index_out_of_range"
    proposal = proposal_repository.get_proposal(
        proposal_id=row["proposal_id"], db_path=db
    )
    assert proposal["status"] == "pending"
