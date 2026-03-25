"""Unit-Tests fuer Schema-Migration: step_states-Tabelle und spec_versions-Erweiterung."""
import sqlite3

import pytest

from gysi_ml.persistence.database import get_connection
from gysi_ml.persistence.schema import create_all_tables


def _get_column_names(db_file: str, table: str) -> list[str]:
    conn = get_connection(db_file)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [row["name"] for row in rows]
    finally:
        conn.close()


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


def test_step_states_table_created(db):
    """Nach create_all_tables() existiert step_states mit allen Spalten."""
    cols = _get_column_names(db, "step_states")
    expected = {
        "state_id",
        "session_id",
        "proposal_id",
        "remaining_steps_json",
        "completed_steps_json",
        "confirmed_indices_json",
        "created_at",
        "last_updated",
    }
    assert expected.issubset(set(cols))


def test_spec_versions_has_new_columns(db):
    """parent_spec_id und change_summary existieren in spec_versions nach Migration."""
    cols = _get_column_names(db, "spec_versions")
    assert "parent_spec_id" in cols
    assert "change_summary" in cols


def test_idempotency(tmp_path):
    """Zweimaliges Aufrufen von create_all_tables() wirft keine Exception."""
    db_file = str(tmp_path / "idempotent.db")
    create_all_tables(db_file)
    create_all_tables(db_file)  # darf keinen Fehler werfen


def test_existing_rows_have_null_new_columns(tmp_path):
    """Bestehende spec_versions-Zeilen erhalten NULL fuer parent_spec_id und change_summary."""
    db_file = str(tmp_path / "migration.db")

    # Altes Schema aufbauen (ohne neue Spalten)
    conn = sqlite3.connect(db_file)
    try:
        conn.executescript("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                name       TEXT,
                created_at TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'active'
            );

            CREATE TABLE spec_versions (
                spec_id    TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                version    TEXT NOT NULL,
                spec_json  TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            ("sess-1", "Alt", "2025-01-01T00:00:00+00:00", "active"),
        )
        conn.execute(
            "INSERT INTO spec_versions VALUES (?, ?, ?, ?, ?)",
            ("spec-1", "sess-1", "1", '{"steps":[]}', "2025-01-01T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    # Migration ausfuehren
    create_all_tables(db_file)

    # Bestehende Zeile pruefen — neue Spalten muessen NULL sein
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM spec_versions WHERE spec_id = 'spec-1'"
        ).fetchone()
        assert row["parent_spec_id"] is None
        assert row["change_summary"] is None
    finally:
        conn.close()
