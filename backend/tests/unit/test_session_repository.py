"""Unit-Tests fuer session_repository mit In-Memory-SQLite."""
import pytest

from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.persistence.session_repository import (
    close_session,
    create_session,
    get_session,
    list_sessions,
)


@pytest.fixture
def db(tmp_path):
    """Frische In-Memory-DB pro Test."""
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


def test_create_session_without_name(db):
    row = create_session(name=None, db_path=db)
    assert row["status"] == "active"
    assert row["name"] is None
    assert "session_id" in row
    assert "created_at" in row


def test_create_session_with_name(db):
    row = create_session(name="Mein Test", db_path=db)
    assert row["name"] == "Mein Test"
    assert row["status"] == "active"


def test_get_session_existing(db):
    created = create_session(name="X", db_path=db)
    fetched = get_session(session_id=created["session_id"], db_path=db)
    assert fetched is not None
    assert fetched["session_id"] == created["session_id"]
    assert fetched["name"] == "X"


def test_get_session_not_found(db):
    result = get_session(session_id="does-not-exist", db_path=db)
    assert result is None


def test_list_sessions_empty(db):
    rows = list_sessions(db_path=db)
    assert rows == []


def test_list_sessions_multiple(db):
    create_session(name="A", db_path=db)
    create_session(name="B", db_path=db)
    rows = list_sessions(db_path=db)
    assert len(rows) == 2


def test_close_session(db):
    created = create_session(name="ToClose", db_path=db)
    closed = close_session(session_id=created["session_id"], db_path=db)
    assert closed is not None
    assert closed["status"] == "closed"


def test_close_session_not_found(db):
    result = close_session(session_id="no-such-id", db_path=db)
    assert result is None


def test_session_id_is_uuid4_format(db):
    import re

    row = create_session(name=None, db_path=db)
    uuid4_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    assert re.match(uuid4_pattern, row["session_id"])


def test_created_at_is_utc_iso(db):
    row = create_session(name=None, db_path=db)
    assert "+00:00" in row["created_at"] or "Z" in row["created_at"]


def test_create_session_sql_injection_safe(db):
    """Parameterized Queries verhindern SQL-Injection in name-Feld."""
    row = create_session(name="'; DROP TABLE sessions;--", db_path=db)
    assert row["name"] == "'; DROP TABLE sessions;--"
    # Tabelle muss noch existieren
    rows = list_sessions(db_path=db)
    assert len(rows) == 1
