import sqlite3
import uuid
from datetime import datetime, timezone

from gysi_ml.persistence.database import get_connection

_VALID_ROLES = {"user", "assistant"}


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def save_message(
    session_id: str,
    role: str,
    content: str,
    db_path: str | None = None,
) -> dict:
    if role not in _VALID_ROLES:
        raise ValueError(f"role muss 'user' oder 'assistant' sein, erhalten: {role!r}")
    message_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (message_id, session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, created_at),
        )
        conn.commit()
        return {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        }
    finally:
        conn.close()


def get_messages_for_session(
    session_id: str,
    db_path: str | None = None,
) -> list[dict]:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message_id, role, content, created_at"
            " FROM messages WHERE session_id = ?"
            " ORDER BY created_at ASC",
            (session_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
