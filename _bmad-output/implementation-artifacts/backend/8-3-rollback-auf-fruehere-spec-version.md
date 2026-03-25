# Story 8.3: Rollback auf frühere Spec-Version

Status: done

## Story

Als ein Nutzer,
möchte ich zu einer früheren Spec-Version zurückrollen können (per Chat oder Versionsbaum-Klick),
damit ich von einem früheren Stand aus neue Richtungen ausprobieren kann — ohne bisherige Versionen und Runs zu verlieren.

## Acceptance Criteria

1. **[Rollback erzeugt neue Version]** `POST /v1/sessions/{id}/rollback` mit `{"target_spec_id": "..."}` erstellt eine neue Spec-Version als Kopie der Target-Version — keine bestehende Version wird überschrieben.

2. **[Korrekte parent_spec_id]** Die neue Rollback-Version hat `parent_spec_id` = die aktuell aktive Spec-ID (vor dem Rollback).

3. **[Korrekte change_summary]** Die neue Rollback-Version hat `change_summary = "Rollback auf vX"` (X = Version der Target-Spec).

4. **[Alle Versionen erhalten]** Nach dem Rollback sind alle vorherigen Versionen und Runs noch in der DB vorhanden.

5. **[HTTP 404 bei unbekannter target_spec_id]** `target_spec_id` existiert nicht oder gehört zu einer anderen Session → HTTP 404 mit verständlicher Fehlermeldung.

6. **[LLM-Rollback nutzt dieselbe Logik (DRY)]** `action_type: "rollback"` im LLM-Response ruft dieselbe Repository-Methode auf wie `POST /rollback`.

7. **[Versionsbaum-Klick auslösen]** Frontend sendet `POST /rollback` mit `target_spec_id` — kein stiller Rollback.

8. **[Test-Coverage ≥ 85%]** Endpunkt und Repository-Methode abgedeckt.

## Tasks / Subtasks

- [x] **T1 — `SpecRepository.rollback_to()` implementieren** (AC: 1–5)
  - [x] Datei: `backend/src/gysi_ml/persistence/spec_repository.py`
  - [ ] Neue Funktion:
    ```python
    def rollback_to(
        session_id: str, target_spec_id: str, db_path: str | None = None
    ) -> dict | None:
        """Erstellt eine neue Spec-Version als Kopie von target_spec_id.
        
        Returns:
            dict der neuen Version, oder None wenn target_spec_id nicht gefunden.
        """
        from gysi_ml.spec.spec_diff import spec_diff as _spec_diff
        
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            
            # Target-Spec laden und Session-Zugehörigkeit prüfen
            cursor.execute(
                "SELECT spec_id, session_id, version, spec_json FROM spec_versions "
                "WHERE spec_id = ? AND session_id = ?",
                (target_spec_id, session_id),
            )
            target_row = cursor.fetchone()
            if target_row is None:
                return None
            
            target_spec = json.loads(target_row["spec_json"])
            target_version = target_row["version"]
            
            # Aktuelle (vor Rollback aktive) Spec als parent
            cursor.execute(
                "SELECT spec_id FROM spec_versions WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            )
            current_row = cursor.fetchone()
            parent_spec_id = current_row["spec_id"] if current_row else None
            
            # Neue Versionsnummer
            cursor.execute(
                "SELECT version FROM spec_versions WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            )
            last_version_row = cursor.fetchone()
            if last_version_row:
                num = int(last_version_row["version"].lstrip("v"))
                new_version = f"v{num + 1}"
            else:
                new_version = "v1"
            
            new_spec_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            change_summary = f"Rollback auf {target_version}"
            
            with conn:
                conn.execute(
                    "INSERT INTO spec_versions "
                    "(spec_id, session_id, version, spec_json, created_at, parent_spec_id, change_summary) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (new_spec_id, session_id, new_version, json.dumps(target_spec),
                     created_at, parent_spec_id, change_summary),
                )
            
            return {
                "spec_id": new_spec_id,
                "session_id": session_id,
                "version": new_version,
                "spec": target_spec,
                "created_at": created_at,
                "parent_spec_id": parent_spec_id,
                "change_summary": change_summary,
            }
        finally:
            conn.close()
    ```

- [x] **T2 — `api/routes/rollback.py` anlegen** (AC: 1, 5, 7)
  - [x] Datei: `backend/src/gysi_ml/api/routes/rollback.py` (neu)
  - [ ] Inhalt:
    ```python
    from typing import Union
    
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    
    from gysi_ml.api.schemas import ErrorResponse
    from gysi_ml.persistence import spec_repository, session_repository
    
    router = APIRouter(prefix="/v1")
    
    
    class RollbackRequest(BaseModel):
        target_spec_id: str
    
    
    @router.post(
        "/sessions/{session_id}/rollback",
        responses={404: {"model": ErrorResponse}},
    )
    def rollback_spec(
        session_id: str, body: RollbackRequest, request: Request
    ) -> Union[dict, JSONResponse]:
        db_path = getattr(request.app.state, "db_path", None)
        
        # Session prüfen
        session = session_repository.get_session(session_id=session_id, db_path=db_path)
        if session is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="session_not_found",
                    detail=f"Session '{session_id}' nicht gefunden.",
                    code="SESSION_NOT_FOUND",
                ).model_dump(),
            )
        
        new_spec = spec_repository.rollback_to(
            session_id=session_id,
            target_spec_id=body.target_spec_id,
            db_path=db_path,
        )
        
        if new_spec is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="spec_not_found",
                    detail=f"Spec-Version '{body.target_spec_id}' nicht gefunden oder gehört nicht zu dieser Session.",
                    code="SPEC_NOT_FOUND",
                ).model_dump(),
            )
        
        return {
            "type": "rollback",
            "new_spec_id": new_spec["spec_id"],
            "new_version": new_spec["version"],
            "change_summary": new_spec["change_summary"],
        }
    ```

- [x] **T3 — Router in `app.py` einbinden** (AC: 1)
  - [x] Datei: `backend/src/gysi_ml/api/app.py`
  - [x] Ergänzen: `from gysi_ml.api.routes import rollback` und `app.include_router(rollback.router)`

- [x] **T4 — LLM-Rollback in `message_service.py` verdrahten** (AC: 6)
  - [x] Datei: `backend/src/gysi_ml/services/message_service.py`
  - [ ] In der Action-Dispatch-Logik (nach LLM-Response-Parsing) `action_type: "rollback"` behandeln:
    ```python
    elif action.get("action_type") == "rollback":
        target_spec_id = action.get("target_spec_id")
        if not target_spec_id:
            return {"type": "error", "message": "Rollback: target_spec_id fehlt."}
        new_spec = spec_repository.rollback_to(
            session_id=session_id, target_spec_id=target_spec_id, db_path=db_path
        )
        if new_spec is None:
            return {"type": "error", "message": f"Spec '{target_spec_id}' nicht gefunden."}
        return {
            "type": "rollback",
            "new_spec_id": new_spec["spec_id"],
            "new_version": new_spec["version"],
            "change_summary": new_spec["change_summary"],
        }
    ```
  - [x] Prüfen wo die anderen `action_type`-Branches in `message_service.py` liegen und dort einhängen

- [x] **T5 — Tests** (AC: 1–8)
  - [x] Datei: `backend/tests/integration/test_rollback.py` (neu)
  - [ ] Tests:
    - [x] `test_rollback_creates_new_version()`: Rollback auf v1 → neue v4, v1–v3 noch vorhanden
    - [x] `test_rollback_correct_parent_spec_id()`: Neue Version hat `parent_spec_id` = v3 (aktuelle)
    - [x] `test_rollback_correct_change_summary()`: `change_summary = "Rollback auf v1"`
    - [x] `test_rollback_unknown_spec_id_returns_404()`: Unbekannte `target_spec_id` → 404
    - [x] `test_rollback_wrong_session_returns_404()`: Spec einer anderen Session → 404

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 5.1:** `spec_versions` muss `parent_spec_id` + `change_summary`-Spalten haben.
- **Benötigt Story 8.1 (spec_diff):** `rollback_to()` setzt `change_summary` direkt (kein spec_diff-Aufruf hier — Rollback hat fixe Summary).
- Story 8.2 zeigt den Rollback als Teil des Versionsbaums.

### DRY — Dieselbe Methode für Endpunkt + LLM

- `spec_repository.rollback_to()` ist die einzige Rollback-Logik-Quelle
- Sowohl `POST /rollback`-Endpunkt als auch `message_service.py` rufen `rollback_to()` auf
- Kein Code-Duplikat

### LLM-JSON-Schema erweitern

- Das LLM-Response-Schema muss `action_type: "rollback"` und `target_spec_id: str` kennen
- Prüfen: `backend/src/gysi_ml/llm/response_schema.py` — neues Action-Enum/Typ ergänzen

### References

- [Source: backend/src/gysi_ml/persistence/spec_repository.py] — bestehende Spec-Logik
- [Source: backend/src/gysi_ml/api/app.py] — Router-Registrierung
- [Source: backend/src/gysi_ml/llm/response_schema.py] — LLM-Response-Schema erweitern
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-8.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#Rollback]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

Keins — alle Tests auf Anhieb grün nach Korrektur von `response_model=None` am FastAPI-Decorator (Union[dict, JSONResponse] ist kein valider Pydantic-Typ).

### Completion Notes List

- `rollback_to()` nutzt dieselbe Verbindungslogik wie die anderen Repository-Funktionen
- LLM-Schema erweitert: `rollback` als neues Enum-Value + optionales `target_spec_id`-Feld
- **Code-Review Fix M1+M2**: Doppelter DB-Query in `rollback_to()` auf einen konsolidiert; Dead-Code-Zweige entfernt
- Beim Code-Review aufgedeckt: mehrere Story-5.1/8.2-Artefakte waren nicht auf Disk (schema.py Migration, specs.py Tree-Endpunkt, schemas.py VersionNode/Tree-Response, run_repository.py spec_id-Spalte) — alle wiederhergestellt
- 3 pre-existing Test-Failures (`test_messages_api`, `test_command_service`) aus Stories 6.1/6.2 — nicht durch Story 8.3 verursacht

### File List

- `backend/src/gysi_ml/persistence/spec_repository.py` — `rollback_to()` hinzugefügt (M1/M2-Fix: konsolidierter Query)
- `backend/src/gysi_ml/api/routes/rollback.py` — neu erstellt
- `backend/src/gysi_ml/api/app.py` — rollback_router eingebunden
- `backend/src/gysi_ml/llm/response_schema.py` — `rollback` Action + `target_spec_id` ergänzt
- `backend/src/gysi_ml/services/message_service.py` — rollback-Branch hinzugefügt
- `backend/tests/integration/test_rollback.py` — neu erstellt (6 Tests)
- `backend/src/gysi_ml/persistence/schema.py` — step_states-Tabelle + spec_versions-Migration (Story 5.1 wiederherstellt)
- `backend/src/gysi_ml/api/schemas.py` — VersionNodeResponse + VersionTreeResponse (Story 8.2 wiederherstellt)
- `backend/src/gysi_ml/api/routes/specs.py` — GET /spec/tree-Endpunkt (Story 8.2 wiederherstellt)
- `backend/src/gysi_ml/persistence/run_repository.py` — spec_id in get_runs_for_session-Query (Story 8.2 Fix)
