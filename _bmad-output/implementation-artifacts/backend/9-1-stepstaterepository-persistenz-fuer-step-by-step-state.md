# Story 9.1: `StepStateRepository` — Persistenz für Step-by-Step-State

Status: done

## Story

Als ein Entwickler,
möchte ich CRUD-Operationen für den Step-by-Step-State in der `step_states`-Tabelle,
damit der Fortschritt einer Step-by-Step-Session über HTTP-Requests hinweg erhalten bleibt.

## Acceptance Criteria

1. **[create()]** `StepStateRepository.create(state)` persistiert alle Felder in `step_states`: `state_id`, `session_id`, `proposal_id`, `remaining_steps_json`, `completed_steps_json`, `confirmed_indices_json`, `created_at`, `last_updated`.

2. **[get_by_session()]** `StepStateRepository.get_by_session(session_id)` gibt den deserialisierte State zurück (JSON-Felder als Python-Objekte) oder `None` wenn keiner existiert.

3. **[update()]** `StepStateRepository.update(state)` aktualisiert `remaining_steps_json`, `completed_steps_json` und `last_updated`. Alle anderen Felder bleiben unverändert.

4. **[delete()]** `StepStateRepository.delete(state_id)` entfernt den State aus `step_states`.

5. **[Kein DataFrame in step_states]** Nur Metadaten als JSON-Strings — kein serialisierter DataFrame.

6. **[Test-Coverage ≥ 85%]** Alle 4 CRUD-Operationen sind mit In-Memory-DB getestet.

## Tasks / Subtasks

- [x] **T1 — `persistence/step_state_repository.py` anlegen** (AC: 1–5)
  - [x] Datei: `backend/src/gysi_ml/persistence/step_state_repository.py` (neu)
  - [x] Implementierung — Muster analog zu `proposal_repository.py`:
    ```python
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
                        state_id, session_id, proposal_id,
                        json.dumps(remaining_steps),
                        json.dumps(completed_steps),
                        json.dumps(confirmed_indices),
                        now, now,
                    ),
                )
            return _build_state_dict(
                state_id, session_id, proposal_id,
                remaining_steps, completed_steps, confirmed_indices, now, now
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
        """Aktualisiert remaining_steps und completed_steps eines States."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE step_states SET remaining_steps_json = ?, completed_steps_json = ?, last_updated = ? "
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
        state_id, session_id, proposal_id,
        remaining_steps, completed_steps, confirmed_indices, created_at, last_updated
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
    ```

- [x] **T2 — Tests für `StepStateRepository`** (AC: 1–6)
  - [x] Datei: `backend/tests/unit/test_step_state_repository.py` (neu)
  - [x] Setup: `schema.create_all_tables(db_path=":memory:")` in Test-Fixture
  - [x] Tests:
    - [x] `test_create_step_state()`: State wird erstellt, alle Felder korrekt
    - [x] `test_get_step_state_by_session_found()`: State abrufbar nach Erstellung — JSON deserialisiert
    - [x] `test_get_step_state_by_session_not_found()`: Leere Session → `None`
    - [x] `test_update_step_state()`: `remaining_steps` und `last_updated` aktualisiert
    - [x] `test_delete_step_state()`: State gelöscht → `get_by_session` gibt `None` zurück
    - [x] `test_no_dataframe_in_state()`: State-Felder sind alle JSON-serialisierbare Python-Typen

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 5.1:** `step_states`-Tabelle muss existieren.
- Story 9.2 und 9.3 nutzen dieses Repository.

### Muster: Analog zu bestehenden Repositories

- `proposal_repository.py` als Referenz-Implementierung verwenden
- `get_connection(db_path)` aus `persistence/database.py` — mit `try/finally conn.close()`
- `with conn:` für Auto-Commit/Rollback bei Schreiboperationen

### JSON-Felder

- `remaining_steps` und `completed_steps`: `list[dict]` — jeder Step = `{"type": "...", "params": {}}`
- `confirmed_indices`: `list[int]` — Indices der vom Nutzer bestätigten Steps
- `json.dumps([])` wenn leer, `json.loads("[]")` als Fallback beim Lesen

### Eindeutigkeit pro Session

- Maximal ein aktiver State pro Session
- `get_step_state_by_session` gibt den neuesten zurück (LIMIT 1 ORDER BY created_at DESC)
- Bei Abschluss/Abbruch wird der State explizit gelöscht (Story 9.3)

### References

- [Source: backend/src/gysi_ml/persistence/proposal_repository.py] — Referenz-Muster für Repository
- [Source: backend/src/gysi_ml/persistence/database.py] — `get_connection()`
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-9.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#step_states]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- T1: `step_state_repository.py` implementiert — 4 CRUD-Funktionen (create, get_by_session, update, delete) + `_build_state_dict` Helper. Muster exakt analog zu `proposal_repository.py`.
- T2: 11 Unit-Tests erstellt, alle bestanden (100%). Pre-existierende Integrationsfehler in `test_messages_api.py` (5 Tests, Story-6.1-Regression) wurden nicht durch diese Story verursacht.
- Code Review (2026-03-21): MEDIUM-1 und LOW-2 behoben. Fixture-Docstring korrigiert (tmp_path ≠ :memory:). Mutable Modulkonstanten `_COMPLETED`/`_INDICES` entfernt — alle Tests verwenden jetzt direkte `[]`-Literale.

### Review Follow-ups (AI)

- [ ] [AI-Review][LOW-1] `update_step_state()` gibt kein Ergebnis zurück — stilles No-Op bei ungültiger `state_id`. Ggf. `rowcount`-Prüfung für Story 9.3 relevant. [`step_state_repository.py:72`](backend/src/gysi_ml/persistence/step_state_repository.py)
- [ ] [AI-Review][LOW-3] `time.sleep(0.01)` in `test_update_step_state_updates_last_updated` und `test_get_step_state_by_session_returns_latest` — Flakiness-Risiko auf langsamen Systemen. Robustere Alternative: `freezegun` oder expliziter Timestamp-Inject. [`test_step_state_repository.py:115`](backend/tests/unit/test_step_state_repository.py)

### File List

- `backend/src/gysi_ml/persistence/step_state_repository.py` (neu)
- `backend/tests/unit/test_step_state_repository.py` (neu)
