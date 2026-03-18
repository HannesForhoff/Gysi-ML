"""Unit-Tests fuer spec_repository mit In-Memory-SQLite."""
import json
import time

import pytest

from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.persistence.spec_repository import (
    create_spec_version,
    get_latest_spec,
    get_spec_by_version,
)
from gysi_ml.persistence.database import get_connection


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


def _insert_session(db: str, session_id: str = "sess-1") -> str:
    conn = get_connection(db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO sessions (session_id, name, created_at, status) VALUES (?, ?, ?, ?)",
                (session_id, "Test", "2025-01-01T00:00:00+00:00", "active"),
            )
    finally:
        conn.close()
    return session_id


def _insert_spec(
    db: str, spec_id: str, session_id: str, version: str, spec: dict, created_at: str
) -> None:
    conn = get_connection(db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO spec_versions (spec_id, session_id, version, spec_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (spec_id, session_id, version, json.dumps(spec), created_at),
            )
    finally:
        conn.close()


def test_get_latest_spec_returns_none_when_no_specs(db):
    _insert_session(db)
    result = get_latest_spec(session_id="sess-1", db_path=db)
    assert result is None


def test_get_latest_spec_returns_most_recent_entry(db):
    session_id = _insert_session(db)
    spec_v1 = {"steps": [{"type": "dedup"}]}
    spec_v2 = {"steps": [{"type": "dedup"}, {"type": "split", "params": {"test_size": 0.2}}]}

    _insert_spec(db, "id-1", session_id, "v1", spec_v1, "2025-01-01T00:00:00+00:00")
    _insert_spec(db, "id-2", session_id, "v2", spec_v2, "2025-01-01T01:00:00+00:00")

    result = get_latest_spec(session_id=session_id, db_path=db)
    assert result is not None
    assert result["version"] == "v2"
    assert result["spec"] == spec_v2
    assert result["spec_id"] == "id-2"
    assert result["session_id"] == session_id


def test_get_spec_by_version_existing(db):
    session_id = _insert_session(db)
    spec_v1 = {"steps": [{"type": "dedup"}]}
    _insert_spec(db, "id-1", session_id, "v1", spec_v1, "2025-01-01T00:00:00+00:00")

    result = get_spec_by_version(session_id=session_id, version="v1", db_path=db)
    assert result is not None
    assert result["version"] == "v1"
    assert result["spec"] == spec_v1
    assert result["spec_id"] == "id-1"
    assert result["session_id"] == session_id
    assert "created_at" in result


def test_get_spec_by_version_not_found_returns_none(db):
    _insert_session(db)
    result = get_spec_by_version(session_id="sess-1", version="v99", db_path=db)
    assert result is None


# ---------------------------------------------------------------------------
# Tests für create_spec_version (Story 4.2 / T7)
# ---------------------------------------------------------------------------


def test_create_spec_version_first_returns_v1(db):
    """Erste Version einer Session ergibt 'v1'."""
    session_id = _insert_session(db)
    spec = {"steps": [{"type": "dedup"}]}
    entry = create_spec_version(session_id=session_id, spec=spec, db_path=db)
    assert entry["version"] == "v1"
    assert entry["session_id"] == session_id
    assert "spec_id" in entry
    assert "created_at" in entry


def test_create_spec_version_increments_to_v2(db):
    """Zweite Version = 'v2'."""
    session_id = _insert_session(db)
    spec_v1 = {"steps": [{"type": "dedup"}]}
    spec_v2 = {"steps": [{"type": "dedup"}, {"type": "split", "params": {"test_size": 0.2}}]}

    entry1 = create_spec_version(session_id=session_id, spec=spec_v1, db_path=db)
    assert entry1["version"] == "v1"

    entry2 = create_spec_version(session_id=session_id, spec=spec_v2, db_path=db)
    assert entry2["version"] == "v2"
    assert entry2["spec_id"] != entry1["spec_id"]


def test_create_spec_version_returns_parsed_spec(db):
    """spec-Feld ist dict, nicht String."""
    session_id = _insert_session(db)
    spec = {"steps": [{"type": "dedup", "params": {}}]}
    entry = create_spec_version(session_id=session_id, spec=spec, db_path=db)
    assert isinstance(entry["spec"], dict)
    assert entry["spec"] == spec


def test_create_spec_version_old_version_preserved(db):
    """v1 ist nach v2-Anlage noch abfragbar (Audit-Trail)."""
    session_id = _insert_session(db)
    spec_v1 = {"steps": [{"type": "dedup"}]}
    spec_v2 = {"steps": [{"type": "split", "params": {"test_size": 0.2}}]}

    create_spec_version(session_id=session_id, spec=spec_v1, db_path=db)
    create_spec_version(session_id=session_id, spec=spec_v2, db_path=db)

    v1 = get_spec_by_version(session_id=session_id, version="v1", db_path=db)
    assert v1 is not None
    assert v1["spec"] == spec_v1

    v2 = get_spec_by_version(session_id=session_id, version="v2", db_path=db)
    assert v2 is not None
    assert v2["spec"] == spec_v2
