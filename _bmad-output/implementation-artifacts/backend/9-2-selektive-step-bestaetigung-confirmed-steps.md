# Story 9.2: Selektive Step-Bestätigung (`confirmed_steps`)

Status: done

## Story

Als ein Nutzer,
möchte ich vor der Ausführung eines Proposals einzelne Steps an- oder abwählen können,
damit nur die von mir ausgewählten Schritte ausgeführt werden — ohne den restlichen Flow zu ändern.

## Acceptance Criteria

1. **[Selektive Ausführung]** `POST /confirm` mit `{"proposal_id": "...", "confirmed_steps": [0, 2]}` führt nur Steps mit Index 0 und 2 aus. Nicht ausgewählte Steps sind in der Spec als `enabled: false` markiert.

2. **[Rückwärtskompatibilität]** `POST /confirm` ohne `confirmed_steps` → alle Steps ausgeführt (unverändert).

3. **[Leeres Array — strukturierter Fehler]** `confirmed_steps: []` → HTTP 422 oder strukturierter Fehler (kein 500): „Mindestens ein Step muss ausgewählt sein".

4. **[Response enthält nur ausgeführte Steps]** Die Result-Response enthält nur die Ergebnisse der tatsächlich ausgeführten Steps.

5. **[Test-Coverage ≥ 85%]** Step-Filterung ist isoliert testbar.

## Tasks / Subtasks

- [x] **T1 — `ConfirmRequest` in `schemas.py` erweitern** (AC: 1, 2)
  - [x] Datei: `backend/src/gysi_ml/api/schemas.py`
  - [x] `ConfirmRequest` erweitern:
    ```python
    from typing import Literal, Optional
    
    class ConfirmRequest(BaseModel):
        proposal_id: str
        confirmed_steps: Optional[list[int]] = None    # NEU — None = alle Steps
        mode: Literal["all", "step_by_step"] = "all"   # NEU — für Story 9.3 vorbereiten
    ```
  - [x] `mode` hier schon vorbereiten — Story 9.3 baut darauf auf

- [x] **T2 — `proposal_service.confirm_proposal()` erweitern** (AC: 1–4)
  - [x] Datei: `backend/src/gysi_ml/services/proposal_service.py`
  - [x] Signatur erweitern:
    ```python
    def confirm_proposal(
        session_id: str,
        proposal_id: str,
        confirmed_steps: list[int] | None = None,
        mode: str = "all",
        db_path: str | None = None,
        data_path: str | None = None,
        artifacts_path: str | None = None,
    ) -> dict:
    ```
  - [ ] Nach Spec-Laden (Schritt 4) Step-Filterung einfügen:
    ```python
    # Selektive Step-Aktivierung
    if confirmed_steps is not None:
        if len(confirmed_steps) == 0:
            return {
                "type": "error",
                "message": "Mindestens ein Step muss ausgewählt sein.",
                "error_code": "no_steps_selected",
            }
        steps = spec.get("steps", [])
        for i, step in enumerate(steps):
            step["enabled"] = i in confirmed_steps
        spec["steps"] = steps
    ```
  - [x] Diese gefilterte Spec wird dann an `executor.execute()` übergeben

- [x] **T3 — `api/routes/confirm.py` anpassen** (AC: 1, 3)
  - [x] Datei: `backend/src/gysi_ml/api/routes/confirm.py`
  - [x] `confirmed_steps` und `mode` aus Request-Body an `proposal_service` weiterleiten:
    ```python
    result = proposal_service.confirm_proposal(
        session_id=session_id,
        proposal_id=body.proposal_id,
        confirmed_steps=body.confirmed_steps,
        mode=body.mode,
        db_path=db_path,
        data_path=...,
        artifacts_path=...,
    )
    ```

- [x] **T4 — Tests für selektive Bestätigung** (AC: 1–5)
  - [x] Datei: `backend/tests/unit/test_proposal_service_selective.py` (neu) oder bestehende erweitern
  - [x] Tests:
    - `test_confirmed_steps_filters_spec()`: `confirmed_steps=[0, 2]` → Step 1 hat `enabled: false`
    - `test_no_confirmed_steps_runs_all()`: `confirmed_steps=None` → Spec unverändert
    - `test_empty_confirmed_steps_error()`: `confirmed_steps=[]` → Error-Response
    - `test_confirmed_steps_index_0_only()`: Nur Step 0 → Steps 1+ haben `enabled: false`

## Dev Notes

### Abhängigkeiten

- **Benötigt Epic 5 nicht direkt** — filtert nur Spec vor Ausführung.
- Story 9.3 erweitert `ConfirmRequest` um `mode: "step_by_step"` — `mode`-Feld hier schon vorbereiten.

### Step-Aktivierung vs. Entfernen

- Nicht ausgewählte Steps werden **nicht entfernt** — sie erhalten `enabled: false`
- Vorteil: Spec bleibt vollständig, Nutzer sieht welche Steps existierten
- Executor ignoriert Steps mit `enabled: false` bereits (prüfen in `executor.py`)

### Executor-Behavior bei `enabled: false`

- Prüfen: `backend/src/gysi_ml/executor/executor.py` — ignoriert er bereits `enabled: false` Steps?
- Falls nicht: im Executor `if step.get("enabled", True):` vorbered einfügen

### Index-Validierung

- `confirmed_steps = [0, 2]` bei 2 Steps → Index 2 out of range → strukturierter Fehler (kein 500)
- Optional: bounds-Check vor Filterung

### References

- [Source: backend/src/gysi_ml/api/schemas.py#ConfirmRequest] — aktuelles Schema
- [Source: backend/src/gysi_ml/services/proposal_service.py] — `confirm_proposal()`
- [Source: backend/src/gysi_ml/api/routes/confirm.py] — Route-Handler
- [Source: backend/src/gysi_ml/executor/executor.py] — `enabled`-Handling prüfen
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-9.2]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

_keine_

### Completion Notes List

- T1: `ConfirmRequest` um `confirmed_steps: Optional[list[int]]` und `mode: Literal["all", "step_by_step"]` erweitert. Import `Literal` zu `schemas.py` hinzugefügt.
- T2: `confirm_proposal()` akzeptiert nun `confirmed_steps` und `mode`. Vor Executor-Ausführung: leeres Array → `error_code: no_steps_selected`, Out-of-range-Index → `error_code: step_index_out_of_range`, sonst Step-Filterung per `enabled: false`.
- T3: Route leitet `body.confirmed_steps` und `body.mode` an Service weiter. Neuer Fehler-Handler für `no_steps_selected` / `step_index_out_of_range` → HTTP 422.
- T4: 6 Unit-Tests in `test_proposal_service_selective.py` — alle grün. Gesamte Unit-Suite: 343 passed, keine Regressions.
- Executor unterstützt `enabled` bereits (Zeile 144 in `executor.py`) — kein Executor-Änderungsbedarf.

**Code Review (2026-03-21) — 2 Issues gefunden und behoben:**
- ✅ [HIGH] Validierung von `confirmed_steps` in `proposal_service.py` vor `update_proposal_status` verschoben — Proposal bleibt `pending` bei Fehler und kann erneut bestätigt werden.
- ✅ [MEDIUM] HTTP 422 in OpenAPI-Response-Deklaration der `/confirm`-Route ergänzt.
- 2 neue Tests: `test_proposal_stays_pending_after_empty_steps_error`, `test_proposal_stays_pending_after_out_of_range_error`
- Gesamte Unit-Suite nach Fixes: 350 passed, keine Regressions.

### File List

- `backend/src/gysi_ml/api/schemas.py` (geändert)
- `backend/src/gysi_ml/services/proposal_service.py` (geändert)
- `backend/src/gysi_ml/api/routes/confirm.py` (geändert)
- `backend/tests/unit/test_proposal_service_selective.py` (neu)
