"""Unit-Tests für proposal_repository (Story 3.3)."""
import pytest

from gysi_ml.persistence.proposal_repository import (
    create_proposal,
    get_pending_proposal,
    get_proposal,
    reject_pending_proposals,
    update_proposal_status,
)
from gysi_ml.persistence.schema import create_all_tables


@pytest.fixture
def db(tmp_path):
    """Frische DB pro Test."""
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


# ---------------------------------------------------------------------------
# create_proposal
# ---------------------------------------------------------------------------


def test_create_proposal_returns_dict(db):
    row = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="Test",
        db_path=db,
    )
    assert "proposal_id" in row
    assert row["status"] == "pending"
    assert row["session_id"] == "s1"
    assert row["explanation"] == "Test"


def test_create_proposal_proposal_id_is_uuid(db):
    import re

    row = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="x",
        db_path=db,
    )
    uuid4_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    assert re.match(uuid4_pattern, row["proposal_id"])


# ---------------------------------------------------------------------------
# get_pending_proposal
# ---------------------------------------------------------------------------


def test_get_pending_proposal(db):
    created = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="Test",
        db_path=db,
    )
    pending = get_pending_proposal(session_id="s1", db_path=db)
    assert pending is not None
    assert pending["proposal_id"] == created["proposal_id"]


def test_get_pending_proposal_none(db):
    result = get_pending_proposal(session_id="s1", db_path=db)
    assert result is None


def test_get_pending_proposal_not_pending(db):
    """Bereits confirmed → get_pending_proposal gibt None zurück."""
    row = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="x",
        db_path=db,
    )
    update_proposal_status(proposal_id=row["proposal_id"], status="confirmed", db_path=db)
    result = get_pending_proposal(session_id="s1", db_path=db)
    assert result is None


# ---------------------------------------------------------------------------
# get_proposal
# ---------------------------------------------------------------------------


def test_get_proposal_by_id(db):
    created = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="Test",
        db_path=db,
    )
    fetched = get_proposal(proposal_id=created["proposal_id"], db_path=db)
    assert fetched is not None
    assert fetched["proposal_id"] == created["proposal_id"]


def test_get_proposal_unknown_id(db):
    result = get_proposal(proposal_id="does-not-exist", db_path=db)
    assert result is None


# ---------------------------------------------------------------------------
# update_proposal_status
# ---------------------------------------------------------------------------


def test_update_proposal_status_confirmed(db):
    row = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="x",
        db_path=db,
    )
    update_proposal_status(proposal_id=row["proposal_id"], status="confirmed", db_path=db)
    updated = get_proposal(proposal_id=row["proposal_id"], db_path=db)
    assert updated["status"] == "confirmed"


def test_update_proposal_status_invalid(db):
    """Ungültiger Status → ValueError."""
    row = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="x",
        db_path=db,
    )
    with pytest.raises(ValueError, match="Ungültiger Proposal-Status"):
        update_proposal_status(proposal_id=row["proposal_id"], status="bogus", db_path=db)


def test_update_proposal_status_rejected(db):
    row = create_proposal(
        session_id="s1",
        spec_json='{"steps": []}',
        explanation="x",
        db_path=db,
    )
    update_proposal_status(proposal_id=row["proposal_id"], status="rejected", db_path=db)
    updated = get_proposal(proposal_id=row["proposal_id"], db_path=db)
    assert updated["status"] == "rejected"


# ---------------------------------------------------------------------------
# reject_pending_proposals
# ---------------------------------------------------------------------------


def test_reject_pending_proposals(db):
    create_proposal(session_id="s1", spec_json="{}", explanation="a", db_path=db)
    create_proposal(session_id="s1", spec_json="{}", explanation="b", db_path=db)
    count = reject_pending_proposals(session_id="s1", db_path=db)
    assert count == 2
    assert get_pending_proposal(session_id="s1", db_path=db) is None


def test_reject_pending_proposals_returns_zero_when_none(db):
    count = reject_pending_proposals(session_id="s1", db_path=db)
    assert count == 0


def test_reject_pending_proposals_no_effect_on_confirmed(db):
    row = create_proposal(session_id="s1", spec_json="{}", explanation="x", db_path=db)
    update_proposal_status(proposal_id=row["proposal_id"], status="confirmed", db_path=db)
    count = reject_pending_proposals(session_id="s1", db_path=db)
    assert count == 0
    updated = get_proposal(proposal_id=row["proposal_id"], db_path=db)
    assert updated["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Isolation zwischen Sessions
# ---------------------------------------------------------------------------


def test_isolation_between_sessions(db):
    """Proposal aus Session A nicht sichtbar für Session B."""
    create_proposal(session_id="s1", spec_json="{}", explanation="a", db_path=db)
    result = get_pending_proposal(session_id="s2", db_path=db)
    assert result is None
