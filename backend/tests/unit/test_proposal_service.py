"""Unit-Tests für proposal_service (Story 3.3)."""
import json
from unittest.mock import MagicMock

import pytest

from gysi_ml.persistence.proposal_repository import create_proposal
from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.services.proposal_service import confirm_proposal


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


_SPEC = {"steps": [{"type": "dedup", "params": {}}]}


def test_confirm_proposal_success(db, monkeypatch):
    """Gültiger pending Proposal → type='result' mit run_id."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC),
        explanation="Test",
        db_path=db,
    )

    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_settings",
        lambda: _settings(),
    )
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-abc"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        db_path=db,
    )

    assert result["type"] == "result"
    assert result["run_id"] == "run-abc"
    assert "explanation" in result


def test_confirm_proposal_not_found(db):
    """Unbekannter Proposal → error: proposal_not_found."""
    result = confirm_proposal(
        session_id="s1",
        proposal_id="does-not-exist",
        db_path=db,
    )
    assert result["error"] == "proposal_not_found"


def test_confirm_proposal_wrong_session(db):
    """Proposal gehört anderer Session → error: proposal_not_found."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC),
        explanation="x",
        db_path=db,
    )
    result = confirm_proposal(
        session_id="s_other",
        proposal_id=row["proposal_id"],
        db_path=db,
    )
    assert result["error"] == "proposal_not_found"


def test_confirm_proposal_already_confirmed(db, monkeypatch):
    """Bereits bestätigter Proposal → error: no_pending_proposal."""
    from gysi_ml.persistence.proposal_repository import update_proposal_status

    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC),
        explanation="x",
        db_path=db,
    )
    update_proposal_status(
        proposal_id=row["proposal_id"], status="confirmed", db_path=db
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        db_path=db,
    )
    assert result["error"] == "no_pending_proposal"


def test_confirm_proposal_executor_error(db, monkeypatch):
    """Executor gibt Fehler zurück → type='error'."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC),
        explanation="x",
        db_path=db,
    )

    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_settings",
        lambda: _settings(),
    )
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"error": "step_failed", "detail": "Fehler im Step"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor",
        lambda **kw: fake_executor,
    )

    result = confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        db_path=db,
    )
    assert result["type"] == "error"
