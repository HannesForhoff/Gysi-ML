import json

from gysi_ml.persistence.database import get_connection


def create_run(
    session_id: str,
    run_id: str,
    spec_version: str,
    status: str,
    started_at: str,
    spec_id: str | None = None,
    db_path: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (run_id, session_id, spec_id, spec_version, status, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, session_id, spec_id, spec_version, status, started_at),
            )
    finally:
        conn.close()


def update_run_status(
    run_id: str,
    status: str,
    finished_at: str,
    error_message: str | None = None,
    result_json: str | None = None,
    db_path: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ?, error_message = ?, result_json = ? WHERE run_id = ?",
                (status, finished_at, error_message, result_json, run_id),
            )
    finally:
        conn.close()


def get_runs_for_session(session_id: str, db_path: str | None = None) -> list[dict]:
    """Gibt alle Runs einer Session zurück (Summary-Felder)."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT run_id, status, started_at, spec_version FROM runs "
            "WHERE session_id = ? ORDER BY started_at ASC",
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_run(run_id: str, db_path: str | None = None) -> dict | None:
    """Gibt einen einzelnen Run mit vollständigen Daten zurück (inkl. Spec).

    Returns:
        Dict mit run-Feldern oder None wenn nicht gefunden.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT r.run_id, r.session_id, r.spec_version, r.status,
                   r.started_at, r.finished_at, r.error_message, r.result_json,
                   sv.spec_json
            FROM runs r
            LEFT JOIN spec_versions sv ON sv.spec_id = r.spec_id
            WHERE r.run_id = ?
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        raw_result = data.pop("result_json", None)
        data["result"] = json.loads(raw_result) if raw_result else None
        raw_spec = data.pop("spec_json", None)
        data["spec"] = json.loads(raw_spec) if raw_spec else None
        return data
    finally:
        conn.close()



