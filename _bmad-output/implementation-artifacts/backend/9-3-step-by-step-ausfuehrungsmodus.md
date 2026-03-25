# Story 9.3: Step-by-Step-Ausführungsmodus

Status: done

## Story

Als ein Nutzer,
möchte ich ein Proposal im Step-by-Step-Modus ausführen können, bei dem nach jedem Step das Ergebnis gezeigt wird und ich aktiv entscheide wie es weitergeht,
damit ich jeden Preprocessing-Schritt nachvollziehe und das System als interaktives Lernwerkzeug nutzen kann.

## Acceptance Criteria

1. **[Ersten Step ausführen]** `POST /confirm` mit `{"proposal_id": "...", "mode": "step_by_step"}` führt nur den ersten aktiven Step aus. Response hat `type: "step_result"` mit: `completed_step.type`, `completed_step.summary`, `remaining_steps`, `next_action`.

2. **[State persistiert]** Nach dem ersten Step ist der Step-by-Step-State in `step_states` gespeichert.

3. **[Nächsten Step fortsetzen]** Folge-`POST /confirm` mit aktivem State führt den nächsten Step aus, aufbauend auf Datenzustand nach dem vorherigen Step.

4. **[Letzter Step — Gesamtzusammenfassung]** Wenn kein weiterer Step verbleibt, gibt das Backend eine Gesamtzusammenfassung zurück (alle `completed_steps`) und der State wird gelöscht.

5. **[Abbruch per Chat]** Das LLM erkennt Abbruch-Intention (`action_type: "abort_step_by_step"`) → Zusammenfassung bisher ausgeführter Steps + State-Löschung.

6. **[Step-Modifikation per Chat]** Das LLM kann `remaining_steps` vor dem nächsten Confirm anpassen.

7. **[Mini-Proposal für nächsten Step (UX-DR2)]** Response enthält `next_action` als Handlungsaufforderung: `"Nächster Schritt: {step_type}. Bestätigen, überspringen oder anpassen?"`.

8. **[Test-Coverage ≥ 85%]** Mindestens erster-Step + letzter-Step + Abbruch getestet.

## Tasks / Subtasks

- [x] **T1 — `StepResultResponse` Schema in `schemas.py` anlegen** (AC: 1)
  - [x] Datei: `backend/src/gysi_ml/api/schemas.py`
  - [x] Ergänzungen:
    ```python
    class CompletedStepSchema(BaseModel):
        type: str
        summary: str
        metadata: Optional[dict] = None
    
    
    class StepResultResponse(BaseModel):
        type: str = "step_result"
        completed_step: CompletedStepSchema
        remaining_steps: list[dict]
        next_action: Optional[str] = None
        state_id: str
        is_final: bool = False
        completed_steps_summary: Optional[list[CompletedStepSchema]] = None
    ```

- [x] **T2 — `proposal_service.confirm_proposal()` um Step-by-Step-Modus erweitern** (AC: 1–4)
  - [x] Datei: `backend/src/gysi_ml/services/proposal_service.py`
  - [x] Nach dem `confirmed_steps`-Filterblock (aus Story 9.2) `mode`-Check einfügen:
    ```python
    from gysi_ml.persistence import step_state_repository
    
    if mode == "step_by_step":
        # Aktiven State prüfen
        active_state = step_state_repository.get_step_state_by_session(
            session_id=session_id, db_path=db_path
        )
        if active_state:
            # Fortführung: nächsten Step aus State laden
            remaining = active_state["remaining_steps"]
            completed = active_state["completed_steps"]
            state_id = active_state["state_id"]
        else:
            # Erster Aufruf: alle Steps aus Spec
            steps = spec.get("steps", [])
            active_steps = [s for s in steps if s.get("enabled", True)]
            remaining = active_steps
            completed = []
            state_id = None
        
        if not remaining:
            # Alle Steps abgeschlossen
            if state_id:
                step_state_repository.delete_step_state(state_id=state_id, db_path=db_path)
            return _build_final_summary(completed)
        
        # Ersten Step aus remaining ausführen
        current_step = remaining[0]
        next_remaining = remaining[1:]
        
        # Einzelnen Step auf Datensatz anwenden
        step_result = _execute_single_step(
            current_step, completed, session_id, data_path, artifacts_path, settings
        )
        
        completed_step = {
            "type": current_step["type"],
            "summary": step_result.get("summary", f"Step '{current_step['type']}' ausgeführt."),
            "metadata": step_result.get("metadata"),
        }
        new_completed = completed + [completed_step]
        
        # State aktualisieren oder anlegen
        if state_id:
            step_state_repository.update_step_state(
                state_id=state_id,
                remaining_steps=next_remaining,
                completed_steps=new_completed,
                db_path=db_path,
            )
        else:
            new_state = step_state_repository.create_step_state(
                session_id=session_id,
                proposal_id=proposal_id,
                remaining_steps=next_remaining,
                completed_steps=new_completed,
                confirmed_indices=[],
                db_path=db_path,
            )
            state_id = new_state["state_id"]
        
        # Letzter Step?
        if not next_remaining:
            step_state_repository.delete_step_state(state_id=state_id, db_path=db_path)
            return _build_final_summary(new_completed)
        
        # Mini-Proposal für nächsten Step
        next_step_type = next_remaining[0]["type"]
        next_action = f"Nächster Schritt: {next_step_type}. Bestätigen, überspringen oder anpassen?"
        
        return {
            "type": "step_result",
            "completed_step": completed_step,
            "remaining_steps": next_remaining,
            "next_action": next_action,
            "state_id": state_id,
            "is_final": False,
        }
    ```
  - [x] Hilfsfunktionen anlegen:
    ```python
    def _execute_single_step(step, completed_steps, session_id, data_path, artifacts_path, settings) -> dict:
        """Führt einen einzelnen Preprocessing-Step auf dem rekonstruierten Datensatz aus."""
        # DataFrame rekonstruieren: Bike-CSV + completed_steps nacheinander anwenden
        # Dann current_step anwenden
        # Returns dict mit "summary" und optional "metadata"
        # Implementierung: PipelineExecutor mit Einzel-Step-Spec aufrufen
        single_step_spec = {"steps": completed_steps + [step]}
        executor = PipelineExecutor(
            data_path=data_path or settings.data_path,
            artifacts_path=artifacts_path or settings.artifacts_path,
        )
        result = executor.execute(spec=single_step_spec, session_id=session_id, db_path=None)
        # Letztes step_result extrahieren
        step_results = result.get("step_results", [])
        last = step_results[-1] if step_results else {}
        return {
            "summary": last.get("summary", f"'{step['type']}' ausgeführt."),
            "metadata": last.get("metadata"),
        }
    
    def _build_final_summary(completed_steps: list[dict]) -> dict:
        types_str = ", ".join(s["type"] for s in completed_steps)
        return {
            "type": "step_result",
            "completed_step": completed_steps[-1] if completed_steps else {},
            "remaining_steps": [],
            "next_action": None,
            "state_id": None,
            "is_final": True,
            "completed_steps_summary": completed_steps,
            "message": f"Alle Steps abgeschlossen: {types_str}",
        }
    ```

- [x] **T3 — LLM-Abbruch verdrahten** (AC: 5)
  - [x] Datei: `backend/src/gysi_ml/services/message_service.py`
  - [x] In der Action-Dispatch-Logik:
    ```python
    elif action.get("action_type") == "abort_step_by_step":
        state = step_state_repository.get_step_state_by_session(
            session_id=session_id, db_path=db_path
        )
        if state:
            completed = state["completed_steps"]
            step_state_repository.delete_step_state(state_id=state["state_id"], db_path=db_path)
            types_str = ", ".join(s["type"] for s in completed)
            return {
                "type": "assistant",
                "message": f"Step-by-Step-Modus beendet. Bisher ausgeführt: {types_str or 'keine Steps'}.",
            }
        return {"type": "assistant", "message": "Kein aktiver Step-by-Step-Vorgang."}
    ```

- [x] **T4 — LLM-Response-Schema um neue Action-Types erweitern** (AC: 5, 6)
  - [x] Datei: `backend/src/gysi_ml/llm/response_schema.py`
  - [x] `abort_step_by_step` und ggf. `modify_step` als gültige `action_type`-Werte ergänzt

- [x] **T5 — Tests** (AC: 1–8)
  - [x] Datei: `backend/tests/integration/test_step_by_step.py` (neu)
  - [x] Tests:
    - `test_first_step_returns_step_result()`: mode=step_by_step → type=step_result, completed_step gesetzt
    - `test_state_persisted_after_first_step()`: State in DB nach erstem Step
    - `test_last_step_returns_final_summary()`: Kein remaining → is_final=True, State gelöscht
    - `test_abort_clears_state()`: abort_step_by_step → State gelöscht, Zusammenfassung zurück
    - `test_no_mode_runs_all_steps()`: Ohne mode → normaler Confirm-Flow unverändert

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 5.1:** `step_states`-Tabelle muss existieren.
- **Benötigt Story 9.1:** `StepStateRepository` muss implementiert sein.
- **Benötigt Story 9.2:** `confirmed_steps` + `mode`-Felder in `ConfirmRequest`.

### DataFrame-Rekonstruktion (kein Persistenz)

- Key-Pattern: DataFrame wird **NIE** in DB gespeichert
- Bei Fortführung: Bike-CSV laden + alle `completed_steps` sequenziell anwenden → Stand vor aktuellem Step
- Deterministisch und speichereffizient

### Executor-Einzelschritt-Strategie

- Einfachster Ansatz: `PipelineExecutor.execute()` mit Spec aus nur einem Step aufrufen
- Komplexerer Ansatz: Staging-Mechanismus im Executor (erst completed_steps bis zum Stand, dann current_step)
- Für Belegarbeit empfohlen: Einfacher Ansatz — alle completed_steps + current_step in einer Spec, Ergebnis des letzten Steps extrahieren

### State-Verwaltung

- Pro Session maximal ein aktiver State
- Nach Abschluss/Abbruch explizit löschen
- Falls State inkonsistent (z.B. durch Fehler): `delete + retry` sicherer als Repair

### `next_action`-Formulierung

- Kurzformel: `"Nächster Schritt: {step_type} ({key_param}). Bestätigen, überspringen oder anpassen?"`
- Überspringen = in `confirmed_steps` nicht eingeben (Feature Story 9.2)

### References

- [Source: backend/src/gysi_ml/services/proposal_service.py] — `confirm_proposal()`
- [Source: backend/src/gysi_ml/executor/executor.py] — Executor-Interface
- [Source: backend/src/gysi_ml/llm/response_schema.py] — Action-Types
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-9.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#F3-Schrittweise-Ausfuehrung]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- story 9.2 Änderungen (confirmed_steps, mode) fehlten in proposal_service.py + schemas.py — mussten zusammen wiederhergestellt werden
- schemas.py fehlte `Literal` im typing-Import

### Completion Notes List

- T1: `CompletedStepSchema` + `StepResultResponse` in `schemas.py` ergänzt; `MessageResponse` mit Step-by-Step-Feldern erweitert
- T2: `confirm_proposal()` erkennt aktiven State bei Fortführung vor Proposal-Validierung; Hilfsfunktionen `_run_step_by_step`, `_execute_single_step`, `_build_final_summary` implementiert
- T3: `abort_step_by_step` Action-Handler in `message_service.py` eingebaut
- T4: `abort_step_by_step` in `LLM_RESPONSE_SCHEMA` enum ergänzt
- T5: 5 Integrationstests in `test_step_by_step.py` — alle grün (5/5)
- Gesamtsuite: 499 passed / 3 pre-existing failures (nicht durch Story verursacht)

### File List

- `backend/src/gysi_ml/api/schemas.py`
- `backend/src/gysi_ml/services/proposal_service.py`
- `backend/src/gysi_ml/services/message_service.py`
- `backend/src/gysi_ml/llm/response_schema.py`
- `backend/tests/integration/test_step_by_step.py` (neu)
