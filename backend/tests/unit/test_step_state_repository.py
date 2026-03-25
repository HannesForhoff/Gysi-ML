"""Unit-Tests für step_state_repository (Story 9.1)."""

import pytest

from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.persistence.step_state_repository import (
    create_step_state,
    delete_step_state,
    get_step_state_by_session,
    update_step_state,
)

_STEPS = [{"type": "dedup", "params": {}}, {"type": "impute", "params": {"strategy": "mean"}}]



@pytest.fixture
def db(tmp_path):
    """Frische dateibasierte Testdatenbank pro Test (tmp_path, nicht :memory:, da get_connection() pro Aufruf eine neue Verbindung öffnet)."""
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


# ---------------------------------------------------------------------------
# create_step_state  (AC 1)
# ---------------------------------------------------------------------------


def test_create_step_state_returns_all_fields(db):
    state = create_step_state(
        session_id="s1",
        proposal_id="p1",
        remaining_steps=_STEPS,
        completed_steps=[],
        confirmed_indices=[],
        db_path=db,
    )
    assert state["state_id"] is not None
    assert state["session_id"] == "s1"
    assert state["proposal_id"] == "p1"
    assert state["remaining_steps"] == _STEPS
    assert state["completed_steps"] == []
    assert state["confirmed_indices"] == []
    assert state["created_at"] is not None
    assert state["last_updated"] is not None


def test_create_step_state_state_id_is_uuid(db):
    import re

    state = create_step_state(
        session_id="s1",
        proposal_id="p1",
        remaining_steps=[],
        completed_steps=[],
        confirmed_indices=[],
        db_path=db,
    )
    uuid4_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    assert re.match(uuid4_pattern, state["state_id"])


# ---------------------------------------------------------------------------
# get_step_state_by_session  (AC 2)
# ---------------------------------------------------------------------------


def test_get_step_state_by_session_found(db):
    created = create_step_state(
        session_id="s1",
        proposal_id="p1",
        remaining_steps=_STEPS,
        completed_steps=[],
        confirmed_indices=[0],
        db_path=db,
    )
    result = get_step_state_by_session("s1", db_path=db)
    assert result is not None
    assert result["state_id"] == created["state_id"]
    assert result["remaining_steps"] == _STEPS   # deserialisiert
    assert result["confirmed_indices"] == [0]     # deserialisiert


def test_get_step_state_by_session_not_found(db):
    result = get_step_state_by_session("non-existent", db_path=db)
    assert result is None


def test_get_step_state_by_session_returns_latest(db):
    """Wenn zwei States für dieselbe Session existieren, wird der neuere zurückgegeben."""
    import time

    create_step_state(
        session_id="s1", proposal_id="p1",
        remaining_steps=[{"type": "old", "params": {}}],
        completed_steps=[], confirmed_indices=[], db_path=db,
    )
    time.sleep(0.01)
    second = create_step_state(
        session_id="s1", proposal_id="p2",
        remaining_steps=[{"type": "new", "params": {}}],
        completed_steps=[], confirmed_indices=[], db_path=db,
    )
    result = get_step_state_by_session("s1", db_path=db)
    assert result["state_id"] == second["state_id"]


# ---------------------------------------------------------------------------
# update_step_state  (AC 3)
# ---------------------------------------------------------------------------


def test_update_step_state_changes_remaining_and_completed(db):
    state = create_step_state(
        session_id="s1", proposal_id="p1",
        remaining_steps=_STEPS,
        completed_steps=[],
        confirmed_indices=[],
        db_path=db,
    )
    new_remaining = [_STEPS[1]]
    new_completed = [_STEPS[0]]
    update_step_state(
        state_id=state["state_id"],
        remaining_steps=new_remaining,
        completed_steps=new_completed,
        db_path=db,
    )
    updated = get_step_state_by_session("s1", db_path=db)
    assert updated["remaining_steps"] == new_remaining
    assert updated["completed_steps"] == new_completed


def test_update_step_state_updates_last_updated(db):
    import time

    state = create_step_state(
        session_id="s1", proposal_id="p1",
        remaining_steps=_STEPS, completed_steps=[], confirmed_indices=[],
        db_path=db,
    )
    original_ts = state["last_updated"]
    time.sleep(0.01)
    update_step_state(
        state_id=state["state_id"],
        remaining_steps=[], completed_steps=_STEPS,
        db_path=db,
    )
    updated = get_step_state_by_session("s1", db_path=db)
    assert updated["last_updated"] != original_ts


def test_update_step_state_preserves_other_fields(db):
    """proposal_id und confirmed_indices bleiben nach Update unverändert."""
    state = create_step_state(
        session_id="s1", proposal_id="p-original",
        remaining_steps=_STEPS, completed_steps=[], confirmed_indices=[1],
        db_path=db,
    )
    update_step_state(
        state_id=state["state_id"],
        remaining_steps=[], completed_steps=_STEPS,
        db_path=db,
    )
    updated = get_step_state_by_session("s1", db_path=db)
    assert updated["proposal_id"] == "p-original"
    assert updated["confirmed_indices"] == [1]


# ---------------------------------------------------------------------------
# delete_step_state  (AC 4)
# ---------------------------------------------------------------------------


def test_delete_step_state_removes_entry(db):
    state = create_step_state(
        session_id="s1", proposal_id="p1",
        remaining_steps=[], completed_steps=[], confirmed_indices=[],
        db_path=db,
    )
    delete_step_state(state["state_id"], db_path=db)
    result = get_step_state_by_session("s1", db_path=db)
    assert result is None


def test_delete_step_state_nonexistent_is_noop(db):
    """Löschen eines nicht-existenten State wirft keine Exception."""
    delete_step_state("non-existent-id", db_path=db)  # darf nicht werfen


# ---------------------------------------------------------------------------
# Kein DataFrame in step_states  (AC 5)
# ---------------------------------------------------------------------------


def test_no_dataframe_in_state(db):
    """Alle Felder des States sind JSON-serialisierbare Python-Typen — kein DataFrame."""
    import json

    state = create_step_state(
        session_id="s1", proposal_id="p1",
        remaining_steps=_STEPS,
        completed_steps=[{"type": "dedup", "params": {}}],
        confirmed_indices=[0],
        db_path=db,
    )
    # Muss ohne Exception serialisierbar sein
    serialized = json.dumps(state)
    assert serialized  # nicht-leer

    result = get_step_state_by_session("s1", db_path=db)
    assert isinstance(result["remaining_steps"], list)
    assert isinstance(result["completed_steps"], list)
    assert isinstance(result["confirmed_indices"], list)
