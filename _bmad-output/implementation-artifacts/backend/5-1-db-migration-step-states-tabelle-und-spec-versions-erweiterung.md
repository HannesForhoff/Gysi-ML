# Story 5.1: DB-Migration — `step_states`-Tabelle und `spec_versions`-Erweiterung

Status: done

## Story

Als ein Entwickler,
möchte ich eine neue `step_states`-Tabelle und erweiterte `spec_versions`-Spalten in SQLite anlegen,
damit die Step-by-Step-Ausführung (Epic 9) und der Versionsbaum (Epic 8) über HTTP-Requests hinweg persistiert werden können.

## Acceptance Criteria

1. **[step_states-Tabelle neu]** Nach `create_all_tables()` existiert die Tabelle `step_states` mit Spalten: `state_id TEXT PRIMARY KEY`, `session_id TEXT NOT NULL`, `proposal_id TEXT`, `remaining_steps_json TEXT`, `completed_steps_json TEXT`, `confirmed_indices_json TEXT`, `created_at TEXT`, `last_updated TEXT` und `FOREIGN KEY (session_id) REFERENCES sessions(session_id)`.

2. **[spec_versions erweitert]** `spec_versions` hat nach der Migration zwei neue Spalten: `parent_spec_id TEXT REFERENCES spec_versions(spec_id)` und `change_summary TEXT`.

3. **[Bestehende Daten unberührt]** Bestehende Zeilen in `spec_versions` erhalten `parent_spec_id = NULL` und `change_summary = NULL` — kein Datenverlust.

4. **[Idempotenz]** `create_all_tables()` kann mehrfach aufgerufen werden ohne Fehler (IF NOT EXISTS für neue Tabelle; try/except für ALTER TABLE falls Spalten bereits existieren).

5. **[Kein DataFrame in step_states]** Die Tabelle enthält ausschließlich Metadaten als JSON-Strings — kein serialisierter DataFrame.

6. **[Test-Coverage ≥ 85%]** Alle neuen SQL-Änderungen sind durch Unit-Tests abgedeckt.

## Tasks / Subtasks

- [x] **T1 — `step_states`-Tabelle in `schema.py` anlegen** (AC: 1, 4)
  - [x] Datei: `backend/src/gysi_ml/persistence/schema.py`
  - [x] Im `cursor.executescript(...)` Block NACH der `proposals`-Tabelle ergänzen:
    ```sql
    CREATE TABLE IF NOT EXISTS step_states (
        state_id               TEXT PRIMARY KEY,
        session_id             TEXT NOT NULL,
        proposal_id            TEXT,
        remaining_steps_json   TEXT,
        completed_steps_json   TEXT,
        confirmed_indices_json TEXT,
        created_at             TEXT,
        last_updated           TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    ```
  - [x] `executescript` läuft bereits in einem Block — `CREATE TABLE IF NOT EXISTS` genügt für Idempotenz

- [x] **T2 — `spec_versions` per ALTER TABLE erweitern** (AC: 2, 3, 4)
  - [x] Datei: `backend/src/gysi_ml/persistence/schema.py`
  - [x] NACH dem `conn.commit()` in `create_all_tables()` zwei separate try/except-Blöcke einfügen:
    ```python
    # Migration: spec_versions — parent_spec_id und change_summary
    for alter_sql in [
        "ALTER TABLE spec_versions ADD COLUMN parent_spec_id TEXT REFERENCES spec_versions(spec_id)",
        "ALTER TABLE spec_versions ADD COLUMN change_summary TEXT",
    ]:
        try:
            conn.execute(alter_sql)
            conn.commit()
        except Exception:
            pass  # Spalte existiert bereits — Idempotenz gewährleistet
    ```
  - [x] Muster ist konsistent mit SQLite-Praxis: ALTER TABLE ist nicht in `executescript` möglich (kein IF NOT EXISTS), daher try/except

- [x] **T3 — Unit-Tests für Schema-Migration** (AC: 1–6)
  - [x] Datei: `backend/tests/unit/test_schema_migration.py` (neu) oder in existierende Schema-Testdatei
  - [x] Tests:
    - `test_step_states_table_created()`: Nach `create_all_tables()` existiert `step_states`-Tabelle mit allen Spalten
    - `test_spec_versions_has_new_columns()`: `parent_spec_id` und `change_summary` in `PRAGMA table_info(spec_versions)`
    - `test_idempotency()`: Zweimaliges Aufrufen von `create_all_tables()` wirft keine Exception
    - `test_existing_rows_have_null_new_columns()`: Bestehende Zeile hat `parent_spec_id IS NULL`
  - [x] Alle Tests mit `tmp_path`-Fixture (In-Memory nicht geeignet da `get_connection` neue Verbindung pro Aufruf öffnet)

## Dev Notes

### Kontext

- **Voraussetzung für alle anderen neuen Epics (6–9):** Ohne diese Migration können `StepStateRepository` (Epic 9) und `SpecRepository.rollback_to()` (Epic 8) nicht arbeiten.
- Diese Story ändert **keine Logik** — ausschließlich Schema.

### Zu ändernde Datei

- `backend/src/gysi_ml/persistence/schema.py` — Einzige Datei, die angefasst wird.
- Aktuelle Schema-Funktion: `create_all_tables(db_path: str | None = None)` — ein `executescript`-Block + anschließendes `commit()`.

### SQLite-Einschränkungen

- `alter table ... IF NOT EXISTS` gibt es in SQLite nicht → try/except ist die Standard-Lösung.
- `executescript` committed automatisch nach jeder Anweisung und unterstützt kein ALTER TABLE mit Constraints → ALTER TABLE separat nach dem executescript-Block ausführen.

### Konventionen

- Alle Tabellennamen: `snake_case`, Singular (z.B. `step_states`, nicht `step_state`)
- Foreign Keys konsequent: `FOREIGN KEY (x) REFERENCES y(id)`
- JSON-Felder enden auf `_json` (z.B. `remaining_steps_json`)

### References

- [Source: backend/src/gysi_ml/persistence/schema.py] — aktuelle `create_all_tables()`
- [Source: _bmad-output/planning-artifacts/architecture.md#Schema-Änderungen] — exaktes SQL-Schema
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-5.1]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- SQLite `:memory:` nicht geeignet für Tests die `get_connection()` mehrfach aufrufen — `tmp_path`-Fixture verwendet.

### Completion Notes List

- T1: `step_states`-Tabelle mit allen 8 Spalten + FK in `executescript`-Block eingefügt (nach `proposals`).
- T2: ALTER TABLE-Migration für `spec_versions` via try/except-Schleife nach `conn.commit()` — idempotent.
- T3: 4 Unit-Tests in `test_schema_migration.py` — alle 4 grün. Coverage: alle SQL-Änderungen abgedeckt.
- Regressionen: 358 Unit + Session-Integration-Tests grün. Message-API-Failures (5 Stk.) pre-existing (Story 6.1 Welcome-Message bereits aktiv), kein Regression durch Schema-Änderungen.

### File List

- `backend/src/gysi_ml/persistence/schema.py` (geändert)
- `backend/tests/unit/test_schema_migration.py` (neu)

## Senior Developer Review (AI)

**Datum:** 2026-03-21
**Ergebnis:** Approve (nach Fix)

### Action Items

- [x] [Med] `except Exception: pass` → `except sqlite3.OperationalError: pass` in `schema.py` Migration-Schleife [schema.py:88]
- [x] [Low] `f"PRAGMA table_info({table})"` in Test-Hilfsfunktion mit Kommentar zur Intentionalität (PRAGMA unterstützt kein Binding) [test_schema_migration.py:12] — als Low akzeptiert, kein Fix nötig
- [x] [Low] Redundantes `conn.commit()` nach `executescript` — als Low akzeptiert, kein Fix nötig

**Gesamtergebnis:** Alle ACs implementiert, Tests grün, MEDIUM-Finding behoben. Story freigegeben.

---

## Change Log

- 2026-03-21: Story 5.1 implementiert — `step_states`-Tabelle angelegt, `spec_versions` um `parent_spec_id` und `change_summary` erweitert, 4 Unit-Tests hinzugefügt.
- 2026-03-21: Code Review — `except Exception` → `except sqlite3.OperationalError` in Migration-Schleife (MEDIUM-Fix). Story auf done gesetzt.
