"""Repository für Step-by-Step-State (Story 9.1)."""

import json
import uuid
from datetime import datetime, timezone

from gysi_ml.persistence.database import get_connection


def create_step_state(
    session_id: str,
    proposal_id: str,
    remaining_steps: list[dict],
    completed_steps: list[dict],
    confirmed_indices: list[int],
    db_path: str | None = None,
) -> dict:
    """Legt einen neuen Step-by-Step-State an."""
    state_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO step_states "
                "(state_id, session_id, proposal_id, remaining_steps_json, "
                "completed_steps_json, confirmed_indices_json, created_at, last_updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    state_id,
                    session_id,
                    proposal_id,
                    json.dumps(remaining_steps),
                    json.dumps(completed_steps),
                    json.dumps(confirmed_indices),
                    now,
                    now,
                ),
            )
        return _build_state_dict(
            state_id, session_id, proposal_id,
            remaining_steps, completed_steps, confirmed_indices, now, now,
        )
    finally:
        conn.close()


def get_step_state_by_session(session_id: str, db_path: str | None = None) -> dict | None:
    """Gibt den aktuellen Step-by-Step-State einer Session zurück (oder None)."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM step_states WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "state_id": row["state_id"],
            "session_id": row["session_id"],
            "proposal_id": row["proposal_id"],
            "remaining_steps": json.loads(row["remaining_steps_json"] or "[]"),
            "completed_steps": json.loads(row["completed_steps_json"] or "[]"),
            "confirmed_indices": json.loads(row["confirmed_indices_json"] or "[]"),
            "created_at": row["created_at"],
            "last_updated": row["last_updated"],
        }
    finally:
        conn.close()


def update_step_state(
    state_id: str,
    remaining_steps: list[dict],
    completed_steps: list[dict],
    db_path: str | None = None,
) -> None:
    """Aktualisiert remaining_steps, completed_steps und last_updated eines States."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE step_states "
                "SET remaining_steps_json = ?, completed_steps_json = ?, last_updated = ? "
                "WHERE state_id = ?",
                (json.dumps(remaining_steps), json.dumps(completed_steps), now, state_id),
            )
    finally:
        conn.close()


def delete_step_state(state_id: str, db_path: str | None = None) -> None:
    """Entfernt einen Step-by-Step-State."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM step_states WHERE state_id = ?", (state_id,))
    finally:
        conn.close()


def _build_state_dict(
    state_id: str,
    session_id: str,
    proposal_id: str,
    remaining_steps: list[dict],
    completed_steps: list[dict],
    confirmed_indices: list[int],
    created_at: str,
    last_updated: str,
) -> dict:
    return {
        "state_id": state_id,
        "session_id": session_id,
        "proposal_id": proposal_id,
        "remaining_steps": remaining_steps,
        "completed_steps": completed_steps,
        "confirmed_indices": confirmed_indices,
        "created_at": created_at,
        "last_updated": last_updated,
    }
