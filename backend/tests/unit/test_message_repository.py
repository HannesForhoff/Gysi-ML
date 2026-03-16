"""Unit-Tests fuer message_repository mit In-Memory-SQLite."""
import time

import pytest

from gysi_ml.persistence.message_repository import get_messages_for_session, save_message
from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.persistence.session_repository import create_session


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


@pytest.fixture
def session_id(db):
    row = create_session(name="Test", db_path=db)
    return row["session_id"]


def test_save_message_returns_dict(db, session_id):
    row = save_message(session_id=session_id, role="user", content="Hallo", db_path=db)
    assert isinstance(row, dict)
    assert "message_id" in row
    assert "role" in row
    assert "content" in row
    assert "created_at" in row


def test_save_message_user_role(db, session_id):
    row = save_message(session_id=session_id, role="user", content="Test", db_path=db)
    assert row["role"] == "user"
    assert row["content"] == "Test"
    assert row["session_id"] == session_id


def test_save_message_assistant_role(db, session_id):
    row = save_message(
        session_id=session_id, role="assistant", content='{"type":"error"}', db_path=db
    )
    assert row["role"] == "assistant"


def test_save_message_invalid_role_raises(db, session_id):
    with pytest.raises(ValueError, match="role muss"):
        save_message(session_id=session_id, role="system", content="X", db_path=db)


def test_get_messages_for_session_chronological(db, session_id):
    save_message(session_id=session_id, role="user", content="erste", db_path=db)
    time.sleep(0.01)
    save_message(session_id=session_id, role="assistant", content="zweite", db_path=db)
    time.sleep(0.01)
    save_message(session_id=session_id, role="user", content="dritte", db_path=db)

    msgs = get_messages_for_session(session_id=session_id, db_path=db)
    assert len(msgs) == 3
    assert msgs[0]["content"] == "erste"
    assert msgs[1]["content"] == "zweite"
    assert msgs[2]["content"] == "dritte"


def test_get_messages_for_session_empty(db, session_id):
    msgs = get_messages_for_session(session_id=session_id, db_path=db)
    assert msgs == []


def test_get_messages_for_session_isolation(db):
    s1 = create_session(name="S1", db_path=db)["session_id"]
    s2 = create_session(name="S2", db_path=db)["session_id"]
    save_message(session_id=s1, role="user", content="fuer s1", db_path=db)
    save_message(session_id=s2, role="user", content="fuer s2", db_path=db)

    msgs1 = get_messages_for_session(session_id=s1, db_path=db)
    msgs2 = get_messages_for_session(session_id=s2, db_path=db)
    assert len(msgs1) == 1
    assert msgs1[0]["content"] == "fuer s1"
    assert len(msgs2) == 1
    assert msgs2[0]["content"] == "fuer s2"


def test_get_messages_fields(db, session_id):
    save_message(session_id=session_id, role="user", content="X", db_path=db)
    msgs = get_messages_for_session(session_id=session_id, db_path=db)
    assert set(msgs[0].keys()) == {"message_id", "role", "content", "created_at"}
