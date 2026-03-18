import json
import uuid
from datetime import datetime, timezone

from gysi_ml.persistence.database import get_connection


def create_spec_version(
    session_id: str, spec: dict, db_path: str | None = None
) -> dict:
    """Erzeugt eine neue Spec-Version mit automatischer Versionsnummervergabe.

    Returns:
        dict mit spec_id, session_id, version, spec (dict), created_at.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT version FROM spec_versions WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        row = cursor.fetchone()
        if row is None:
            version = "v1"
        else:
            num = int(row["version"].lstrip("v"))
            version = f"v{num + 1}"

        spec_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        spec_json = json.dumps(spec)

        with conn:
            conn.execute(
                "INSERT INTO spec_versions (spec_id, session_id, version, spec_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (spec_id, session_id, version, spec_json, created_at),
            )

        return {
            "spec_id": spec_id,
            "session_id": session_id,
            "version": version,
            "spec": spec,
            "created_at": created_at,
        }
    finally:
        conn.close()


def get_latest_spec(session_id: str, db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT spec_id, session_id, version, spec_json, created_at "
            "FROM spec_versions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        data["spec"] = json.loads(data.pop("spec_json"))
        return data
    finally:
        conn.close()


def get_spec_by_version(
    session_id: str, version: str, db_path: str | None = None
) -> dict | None:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT spec_id, session_id, version, spec_json, created_at "
            "FROM spec_versions WHERE session_id = ? AND version = ?",
            (session_id, version),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        data["spec"] = json.loads(data.pop("spec_json"))
        return data
    finally:
        conn.close()
