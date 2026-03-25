# Story 8.2: Versionsbaum-API-Endpunkt

Status: done

## Story

Als ein Nutzer,
möchte ich den vollständigen Versionsbaum meiner Pipeline-Specs über einen API-Endpunkt abrufen,
damit ich sehe welche Versionen existieren, wie sie zusammenhängen und welche gerade aktiv ist.

## Acceptance Criteria

1. **[Vollständige Baumstruktur]** `GET /v1/sessions/{id}/spec/tree` gibt ein JSON zurück mit: `session_id`, `active_spec_id`, und `versions`-Array. Jede Version enthält: `spec_id`, `version`, `parent_spec_id` (null für v1), `change_summary`, `created_at`, `has_runs`, `last_run_status`.

2. **[Korrekte Abzweigungen]** Wenn ein Rollback auf v1 eine neue v4 erzeugt hat, zeigt der Baum: v1→v2→v3 und v1→v4 korrekt über `parent_spec_id`.

3. **[Einzelne Version]** Session mit genau einer Spec-Version → `parent_spec_id: null`, kein Fehler.

4. **[Leere Session]** Session ohne jede Spec-Version → `{"session_id": "...", "active_spec_id": null, "versions": []}`.

5. **[HTTP 404 bei unbekannter Session]** Session existiert nicht → 404 mit strukturierter Fehlermeldung.

6. **[Test-Coverage ≥ 85%]** Endpunkt und Repository-Methode sind abgedeckt.

## Tasks / Subtasks

- [x] **T1 — `SpecRepository` um `get_all_specs_for_session()` erweitern** (AC: 1–4)
  - [ ] Datei: `backend/src/gysi_ml/persistence/spec_repository.py`
  - [ ] Neue Funktion:
    ```python
    def get_all_specs_for_session(session_id: str, db_path: str | None = None) -> list[dict]:
        """Gibt alle Spec-Versionen einer Session zurück, geordnet nach created_at ASC."""
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT spec_id, session_id, version, spec_json, created_at, "
                "parent_spec_id, change_summary "
                "FROM spec_versions WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    ```

- [x] **T2 — Neue Response-Schemas in `schemas.py` anlegen** (AC: 1)
  - [ ] Datei: `backend/src/gysi_ml/api/schemas.py`
  - [ ] Ergänzungen:
    ```python
    class VersionNodeResponse(BaseModel):
        spec_id: str
        version: str
        parent_spec_id: Optional[str] = None
        change_summary: Optional[str] = None
        created_at: str
        has_runs: bool
        last_run_status: Optional[str] = None
    
    
    class VersionTreeResponse(BaseModel):
        session_id: str
        active_spec_id: Optional[str] = None
        versions: list[VersionNodeResponse]
    ```

- [x] **T3 — Neuen Endpunkt in `api/routes/specs.py` ergänzen** (AC: 1–5)
  - [ ] Datei: `backend/src/gysi_ml/api/routes/specs.py` (bestehend — Endpunkt hinzufügen)
  - [ ] Neuer Route-Handler:
    ```python
    from gysi_ml.api.schemas import VersionNodeResponse, VersionTreeResponse
    from gysi_ml.persistence import run_repository, session_repository, spec_repository
    
    @router.get(
        "/sessions/{session_id}/spec/tree",
        response_model=VersionTreeResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def get_spec_tree(session_id: str, request: Request) -> Union[VersionTreeResponse, JSONResponse]:
        db_path = _get_db_path(request)
        
        # Session-Existenz prüfen
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
        
        # Alle Spec-Versionen laden
        specs = spec_repository.get_all_specs_for_session(session_id=session_id, db_path=db_path)
        
        # Runs für has_runs + last_run_status befüllen
        runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
        runs_by_spec: dict[str, list] = {}
        for run in runs:
            spec_id = run.get("spec_id")
            if spec_id:
                runs_by_spec.setdefault(spec_id, []).append(run)
        
        # Aktive Spec = neueste Version
        active_spec_id = specs[-1]["spec_id"] if specs else None
        
        nodes = []
        for spec in specs:
            spec_runs = runs_by_spec.get(spec["spec_id"], [])
            last_run = spec_runs[-1] if spec_runs else None
            nodes.append(VersionNodeResponse(
                spec_id=spec["spec_id"],
                version=spec["version"],
                parent_spec_id=spec.get("parent_spec_id"),
                change_summary=spec.get("change_summary"),
                created_at=spec["created_at"],
                has_runs=len(spec_runs) > 0,
                last_run_status=last_run["status"] if last_run else None,
            ))
        
        return VersionTreeResponse(
            session_id=session_id,
            active_spec_id=active_spec_id,
            versions=nodes,
        )
    ```

- [x] **T4 — Router registrieren** (AC: 1)
  - [ ] Datei: `backend/src/gysi_ml/api/app.py`
  - [ ] Prüfen ob `specs.py`-Router bereits eingebunden ist: `app.include_router(specs.router)` — falls ja, kein zusätzlicher Schritt nötig
  - [ ] Falls `specs.py` keinen eigenen Router hat: neues `router = APIRouter(prefix="/v1")` anlegen und registrieren

- [x] **T5 — Tests** (AC: 1–6)
  - [ ] Datei: `backend/tests/integration/test_spec_tree.py` (neu)
  - [ ] Tests über `TestClient`:
    - `test_spec_tree_empty_session()`: Leere Session → `{"versions": [], "active_spec_id": null}`
    - `test_spec_tree_single_version()`: Eine Version → `parent_spec_id: null`
    - `test_spec_tree_multiple_versions()`: Mehrere Versionen → korrekte `parent_spec_id`-Kette
    - `test_spec_tree_404_unknown_session()`: Unbekannte Session → 404

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 5.1:** `spec_versions` muss `parent_spec_id` und `change_summary`-Spalten haben.
- **Benötigt Story 8.1 (spec_diff):** Die neuen Spalten werden beim Anlegen der Spec-Version befüllt.
- Story 8.3 (Rollback) ergänzt die Rollback-Logik, ändert nichts am Tree-Endpunkt.

### `active_spec_id`-Ermittlung

- Aktuell: neueste Spec nach `created_at` gilt als aktiv.
- Dies entspricht dem bestehenden `get_latest_spec()` in `spec_repository.py`.
- Kein separates `active`-Flag nötig (KISS).

### `run_repository.get_runs_for_session()`

- Gibt alle Runs einer Session zurück, je mit `spec_id`, `status`, etc.
- `spec_id` pro Run verknüpft Run mit Spec-Version.

### Bestehende `specs.py`-Router-Struktur

- Prüfen ob `api/routes/specs.py` bereits existiert und welchen Prefix/Router es hat
- Falls kein `router`-Objekt in `specs.py`: anlegen und in `app.py` einbinden

### References

- [Source: backend/src/gysi_ml/api/routes/specs.py] — bestehende Spec-Routen
- [Source: backend/src/gysi_ml/api/app.py] — Router-Registrierung
- [Source: backend/src/gysi_ml/persistence/spec_repository.py] — bestehende Spec-Queries
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-8.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#GET-spec-tree]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Route-Reihenfolge: `/spec/tree` muss vor `/spec/{version}` definiert werden, da FastAPI sonst `tree` als `version`-Parameter matcht.
- `get_runs_for_session()` musste um `spec_id` in der SELECT-Clause erweitert werden.

### Completion Notes List

- Alle ACs (1–5) implementiert und getestet.
- `get_runs_for_session` in `run_repository.py` um `spec_id`-Spalte erweitert (kein Breaking Change für bestehende Aufrufer).
- 478 Tests grün (1 pre-existierender Fehler in `test_messages_api.py` nicht durch diese Story verursacht).
- Code-Review-Fixes: Doppelte Funktionsdefinitionen in `specs.py` entfernt; `spec_json` aus `get_all_specs_for_session` entfernt (ungenutzt); Test für `has_runs=true` / `last_run_status` ergänzt.
- Coverage `specs.py` + `spec_repository.py` gemeinsam: 100%.

### File List

- `backend/src/gysi_ml/persistence/spec_repository.py` — `get_all_specs_for_session()` hinzugefügt
- `backend/src/gysi_ml/persistence/run_repository.py` — `get_runs_for_session()` um `spec_id` erweitert
- `backend/src/gysi_ml/api/schemas.py` — `VersionNodeResponse`, `VersionTreeResponse` hinzugefügt
- `backend/src/gysi_ml/api/routes/specs.py` — `GET /v1/sessions/{id}/spec/tree` hinzugefügt (vor `{version}`-Route)
- `backend/tests/integration/test_spec_tree.py` — neu erstellt (4 Tests)
