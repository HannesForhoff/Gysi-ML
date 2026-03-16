from typing import Optional

from gysi_ml.persistence.database import get_connection


def create_artifact(
    artifact_id: str,
    run_id: str,
    artifact_type: str,
    file_path: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO artifacts (artifact_id, run_id, type, file_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (artifact_id, run_id, artifact_type, file_path, created_at),
            )
    finally:
        conn.close()


def get_artifact(artifact_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_artifacts_for_run(run_id: str, db_path: Optional[str] = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT artifact_id, type, created_at FROM artifacts WHERE run_id = ? ORDER BY created_at ASC",
            (run_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]
