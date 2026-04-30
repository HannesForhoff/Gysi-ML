"""Unit-Tests für proposal_service (Story 3.3)."""
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from gysi_ml.persistence.proposal_repository import create_proposal
from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.services.proposal_service import (
    _execute_single_step,
    _run_step_by_step,
    confirm_proposal,
)


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


# ---------------------------------------------------------------------------
# Bug 1.13 — Fix A + B: Merge + vollständige Response
# ---------------------------------------------------------------------------


def test_confirm_merges_with_current_spec(db, monkeypatch):
    """Confirm führt executor mit merged Spec aus (vorherige Steps + Proposal-Steps)."""
    from gysi_ml.persistence.spec_repository import create_spec_version

    prev_spec = {"steps": [{"type": "impute_missing", "params": {"strategy": "median"}}]}
    create_spec_version(session_id="s1", spec=prev_spec, db_path=db)

    proposal_spec = {"steps": [{"type": "correlation_filter", "params": {"threshold": 0.9}}]}
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(proposal_spec),
        explanation="Korrelationsfilter",
        db_path=db,
    )

    monkeypatch.setattr("gysi_ml.services.proposal_service.get_settings", lambda: _settings())
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {"run_id": "run-xyz"}
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor", lambda **kw: fake_executor
    )

    confirm_proposal(session_id="s1", proposal_id=row["proposal_id"], db_path=db)

    called_spec = fake_executor.execute.call_args[1]["spec"]
    step_types = [s["type"] for s in called_spec["steps"]]
    assert "impute_missing" in step_types
    assert "correlation_filter" in step_types
    assert step_types.index("impute_missing") < step_types.index("correlation_filter")


def test_confirm_response_includes_spec_and_version(db, monkeypatch):
    """Confirm-Response enthält 'spec', 'version', 'step_results', 'artifacts'."""
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(_SPEC),
        explanation="x",
        db_path=db,
    )

    monkeypatch.setattr("gysi_ml.services.proposal_service.get_settings", lambda: _settings())
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {
        "run_id": "run-1",
        "spec_version": "v1",
        "result": {
            "step_results": [{"step_type": "dedup", "metadata": {}}],
            "artifacts": [],
            "metrics": None,
        },
    }
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor", lambda **kw: fake_executor
    )

    result = confirm_proposal(session_id="s1", proposal_id=row["proposal_id"], db_path=db)

    assert result["type"] == "result"
    assert "spec" in result
    assert result["version"] == "v1"
    assert "step_results" in result
    assert "artifacts" in result


def test_confirm_step_results_contain_all_steps(db, monkeypatch):
    """Confirm-Response.step_results enthält Ergebnisse aller ausgeführten Steps."""
    from gysi_ml.persistence.spec_repository import create_spec_version

    prev_spec = {"steps": [{"type": "impute_missing", "params": {"strategy": "median"}}]}
    create_spec_version(session_id="s1", spec=prev_spec, db_path=db)

    proposal_spec = {"steps": [{"type": "correlation_filter", "params": {"threshold": 0.9}}]}
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(proposal_spec),
        explanation="x",
        db_path=db,
    )

    monkeypatch.setattr("gysi_ml.services.proposal_service.get_settings", lambda: _settings())
    fake_executor = MagicMock()
    fake_executor.execute.return_value = {
        "run_id": "run-1",
        "spec_version": "v2",
        "result": {
            "step_results": [
                {"step_type": "impute_missing", "metadata": {}},
                {"step_type": "correlation_filter", "metadata": {}},
            ],
            "artifacts": [],
        },
    }
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.PipelineExecutor", lambda **kw: fake_executor
    )

    result = confirm_proposal(session_id="s1", proposal_id=row["proposal_id"], db_path=db)

    assert result["type"] == "result"
    step_types = [sr["step_type"] for sr in result["step_results"]]
    assert "impute_missing" in step_types
    assert "correlation_filter" in step_types


# ---------------------------------------------------------------------------
# _execute_single_step — is_splitter=True Branch (L204–209)
# ---------------------------------------------------------------------------


def _make_step_mock(is_splitter: bool, metadata=None):
    """Erstellt ein Mock-Paar (cls, instance) für einen Pipeline-Step."""
    fake_df = pd.DataFrame({"a": [1, 2, 3]})
    instance = MagicMock()
    instance.transform.return_value = (fake_df.copy(), fake_df.copy())
    instance.get_metadata.return_value = metadata
    cls = MagicMock(return_value=instance)
    cls.is_splitter = is_splitter
    return cls, instance


def test_execute_single_step_splitter_branch(monkeypatch):
    """_execute_single_step: Splitter-Step setzt context.is_split=True."""
    fake_df = pd.DataFrame({"a": [1, 2, 3]})
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.load_bikes_dataset",
        lambda path: fake_df,
    )
    mock_cls, mock_instance = _make_step_mock(is_splitter=True)
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_step_class",
        lambda step_type: mock_cls,
    )

    result = _execute_single_step(
        current_step={"type": "split", "params": {}},
        completed_steps=[],
        data_path="/fake/path",
        artifacts_path="/fake/art",
    )

    assert "summary" in result
    # fit() und transform() müssen aufgerufen worden sein
    mock_instance.fit.assert_called_once()
    mock_instance.transform.assert_called_once()


# ---------------------------------------------------------------------------
# _execute_single_step — elif context.is_split Branch (L210–213)
# ---------------------------------------------------------------------------


def test_execute_single_step_post_split_branch(monkeypatch):
    """_execute_single_step: Step nach Splitter läuft im post-split-Modus."""
    fake_df = pd.DataFrame({"a": [1, 2, 3]})
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.load_bikes_dataset",
        lambda path: fake_df,
    )

    splitter_cls, splitter_instance = _make_step_mock(is_splitter=True)
    regular_cls, regular_instance = _make_step_mock(is_splitter=False, metadata={"n": 1})

    def fake_get_step_class(step_type):
        return splitter_cls if step_type == "split" else regular_cls

    monkeypatch.setattr(
        "gysi_ml.services.proposal_service.get_step_class",
        fake_get_step_class,
    )

    # completed_steps enthält bereits einen Splitter → context.is_split wird True
    result = _execute_single_step(
        current_step={"type": "dedup", "params": {}},
        completed_steps=[{"type": "split", "params": {}}],
        data_path="/fake/path",
        artifacts_path="/fake/art",
    )

    assert "summary" in result
    # Der reguläre Step muss im post-split-Modus mit df_train aufgerufen worden sein
    regular_instance.fit.assert_called_once()
    regular_instance.transform.assert_called_once()
    assert result.get("metadata") == {"n": 1}


# ---------------------------------------------------------------------------
# _run_step_by_step — else-Branch (kein aktiver State, L140–142)
# ---------------------------------------------------------------------------


def test_run_step_by_step_no_active_state_creates_state(monkeypatch, tmp_path):
    """_run_step_by_step ohne aktiven State legt neuen State an und gibt step_result zurück."""
    db_file = str(tmp_path / "test.db")
    from gysi_ml.persistence.schema import create_all_tables

    create_all_tables(db_file)

    # Kein aktiver State in der DB → else-Branch wird durchlaufen
    monkeypatch.setattr(
        "gysi_ml.services.proposal_service._execute_single_step",
        lambda **kw: {"summary": "Step ok", "metadata": None},
    )

    spec = {
        "steps": [
            {"type": "dedup", "params": {}},
            {"type": "split", "params": {}},
        ]
    }

    result = _run_step_by_step(
        session_id="s-new",
        proposal_id="p-new",
        spec=spec,
        db_path=db_file,
        data_path="/fake/path",
        artifacts_path="/fake/art",
    )

    assert result["type"] == "step_result"
    assert result["is_final"] is False
    # Erster Step wurde abgeschlossen, zweiter steht noch aus
    assert len(result["remaining_steps"]) == 1
    assert result["remaining_steps"][0]["type"] == "split"


# ---------------------------------------------------------------------------
# Bug 1.14 — confirm_proposal(mode="step_by_step") merged Session-Spec
# ---------------------------------------------------------------------------


def test_confirm_step_by_step_merges_with_session_spec(db, monkeypatch):
    """Bug 1.14: confirm_proposal(mode='step_by_step') übergibt gemergede Spec an
    _run_step_by_step, sodass Session-Steps + Proposal-Steps als remaining landen."""
    from gysi_ml.persistence.spec_repository import create_spec_version

    # Vorheriger Session-Zustand: impute_missing bereits ausgeführt
    prev_spec = {"steps": [{"type": "impute_missing", "params": {"strategy": "median"}}]}
    create_spec_version(session_id="s1", spec=prev_spec, db_path=db)

    # Proposal enthält nur den neuen Step
    proposal_spec = {"steps": [{"type": "correlation_filter", "params": {"threshold": 0.9}}]}
    row = create_proposal(
        session_id="s1",
        spec_json=json.dumps(proposal_spec),
        explanation="Korrelationsfilter",
        db_path=db,
    )

    monkeypatch.setattr("gysi_ml.services.proposal_service.get_settings", lambda: _settings())

    captured: dict = {}

    def fake_run_step_by_step(session_id, proposal_id, spec, db_path, data_path, artifacts_path):
        captured["spec"] = spec
        return {"type": "step_result", "is_final": False, "remaining_steps": []}

    monkeypatch.setattr(
        "gysi_ml.services.proposal_service._run_step_by_step",
        fake_run_step_by_step,
    )

    confirm_proposal(
        session_id="s1",
        proposal_id=row["proposal_id"],
        mode="step_by_step",
        db_path=db,
    )

    # Die gemergede Spec muss BEIDE Steps enthalten
    step_types = [s["type"] for s in captured["spec"]["steps"]]
    assert "impute_missing" in step_types, "Session-Step fehlt in gemergeter Spec"
    assert "correlation_filter" in step_types, "Proposal-Step fehlt in gemergeter Spec"
    assert step_types.index("impute_missing") < step_types.index("correlation_filter"), (
        "Reihenfolge: Session-Steps müssen vor Proposal-Steps kommen"
    )


def test_confirm_step_by_step_no_session_spec_passes_proposal_spec(db, monkeypatch):
    """Bug 1.14: Ohne vorherige Session-Spec übergibt confirm_proposal die reine Proposal-Spec."""
    proposal_spec = {"steps": [{"type": "dedup", "params": {}}]}
    row = create_proposal(
        session_id="s-fresh",
        spec_json=json.dumps(proposal_spec),
        explanation="Erstausführung",
        db_path=db,
    )

    monkeypatch.setattr("gysi_ml.services.proposal_service.get_settings", lambda: _settings())

    captured: dict = {}

    def fake_run_step_by_step(session_id, proposal_id, spec, db_path, data_path, artifacts_path):
        captured["spec"] = spec
        return {"type": "step_result", "is_final": False, "remaining_steps": []}

    monkeypatch.setattr(
        "gysi_ml.services.proposal_service._run_step_by_step",
        fake_run_step_by_step,
    )

    confirm_proposal(
        session_id="s-fresh",
        proposal_id=row["proposal_id"],
        mode="step_by_step",
        db_path=db,
    )

    step_types = [s["type"] for s in captured["spec"]["steps"]]
    assert step_types == ["dedup"]
