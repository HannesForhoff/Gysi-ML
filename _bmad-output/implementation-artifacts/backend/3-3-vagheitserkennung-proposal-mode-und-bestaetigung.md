# Story 3.3: Vagheits-Erkennung, Proposal-Mode und Bestätigungs-Endpunkt

Status: done

## Story

Als ein Nutzer,
möchte ich bei vagen Eingaben einen konkreten Vorschlag mit Steps und Parametern erhalten und diesen bestätigen oder ablehnen können, bevor das System ausführt,
damit ich immer Entscheider bleibe und das System keine stillen "Best-Guess"-Aktionen durchführt.

## Acceptance Criteria

1. **[proposals-Tabelle angelegt]** Beim Service-Start wird eine SQLite-Tabelle `proposals` angelegt mit den Spalten `proposal_id` (TEXT PK), `session_id` (TEXT FK → sessions), `spec_json` (TEXT, die vorgeschlagene Spec als JSON), `explanation` (TEXT), `status` (TEXT: `"pending"`, `"confirmed"`, `"rejected"`), `created_at` (TEXT). Parameterized Queries.

2. **[Proposal bei vager Eingabe]** Wenn das LLM `action: "propose"` zurückgibt, wird ein Proposal-Eintrag in der `proposals`-Tabelle mit `status: "pending"` angelegt. Die API-Response enthält: `{"type": "proposal", "proposal_id": "...", "steps": [...], "explanation": "...", "confirmation_required": true}`.

3. **[Direkte Ausführung bei eindeutiger Eingabe]** Wenn das LLM `action: "execute"` zurückgibt, wird die Spec direkt an den `PipelineExecutor` delegiert. Die API-Response enthält: `{"type": "result", "run_id": "...", "explanation": "..."}`. Kein Proposal wird angelegt.

4. **[Bestätigungs-Endpunkt]** `POST /v1/sessions/{id}/confirm` mit Body `{"proposal_id": "..."}` führt den im Proposal gespeicherten Spec aus:
   - Proposal-Status wird auf `"confirmed"` gesetzt
   - Spec wird an `PipelineExecutor` delegiert
   - Response: `{"type": "result", "run_id": "...", "explanation": "Proposal bestätigt und ausgeführt."}` mit HTTP 200

5. **[409 ohne offenen Proposal]** `POST /v1/sessions/{id}/confirm` ohne offenen (pending) Proposal → HTTP 409 mit `{"error": "no_pending_proposal", "detail": "Kein offener Vorschlag in dieser Session.", "code": "NO_PENDING_PROPOSAL"}`.

6. **[Implizite Ablehnung bei neuer Nachricht]** Wenn ein Nutzer eine neue Nachricht sendet (`POST /messages`) während ein Proposal pending ist, wird der offene Proposal auf `status: "rejected"` gesetzt und die neue Eingabe verarbeitet. Es existiert pro Session immer maximal ein offener Proposal.

7. **[Proposal-ID-Validierung]** `POST /confirm` mit einer `proposal_id` die nicht zur Session gehört oder nicht existiert → HTTP 404 mit `{"error": "proposal_not_found", ...}`.

8. **[409 bei geschlossener Session]** `POST /v1/sessions/{id}/confirm` auf eine geschlossene Session → HTTP 409 mit `{"error": "session_closed", ...}`.

9. **[Assistant-Messages bei Proposals]** Proposal-Responses und Confirm-Responses werden jeweils als `role: "assistant"` Message persistiert (via `message_repository`).

10. **[Keine Regression]** Alle bestehenden Tests (inkl. Story 3.1 + 3.2) bleiben grün.

11. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — SQLite-Schema erweitern: `proposals`-Tabelle** (AC: 1)
  - [x] `src/gysi_ml/persistence/schema.py` ergänzen — nach `messages`-Tabelle:
    ```sql
    CREATE TABLE IF NOT EXISTS proposals (
        proposal_id  TEXT PRIMARY KEY,
        session_id   TEXT NOT NULL,
        spec_json    TEXT NOT NULL,
        explanation  TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'pending',
        created_at   TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    ```

- [x] **T2 — `persistence/proposal_repository.py` anlegen** (AC: 1, 2, 4, 5, 6, 7)
  - [x] `src/gysi_ml/persistence/proposal_repository.py` erstellen:
    - `create_proposal(session_id: str, spec_json: str, explanation: str, db_path: str | None = None) -> dict`
      - Generiert `proposal_id = str(uuid.uuid4())`
      - `created_at = datetime.now(timezone.utc).isoformat()`
      - INSERT mit `status: "pending"`
      - Gibt `{"proposal_id", "session_id", "spec_json", "explanation", "status", "created_at"}` zurück
    - `get_pending_proposal(session_id: str, db_path: str | None = None) -> dict | None`
      - SELECT WHERE `session_id = ? AND status = 'pending'`
      - Gibt den offenen Proposal zurück oder `None`
    - `get_proposal(proposal_id: str, db_path: str | None = None) -> dict | None`
      - SELECT WHERE `proposal_id = ?`
      - Gibt den Proposal zurück oder `None`
    - `update_proposal_status(proposal_id: str, status: str, db_path: str | None = None) -> None`
      - UPDATE `status` WHERE `proposal_id = ?`
      - `status` in `{"confirmed", "rejected"}`
    - `reject_pending_proposals(session_id: str, db_path: str | None = None) -> int`
      - UPDATE alle pending Proposals der Session auf `status: "rejected"`
      - Gibt Anzahl aktualisierter Rows zurück
  - [x] Muster identisch zu `session_repository.py`: `get_connection(db_path)`, Parameterized Queries

- [x] **T3 — Pydantic-Schemas erweitern** (AC: 2, 4, 5)
  - [x] `src/gysi_ml/api/schemas.py` ergänzen:
    ```python
    class ConfirmRequest(BaseModel):
        proposal_id: str
    ```
  - [x] `MessageResponse` benötigt keine Änderung — `proposal_id`-Feld ist bereits optional vorhanden (aus Story 3.1)

- [x] **T4 — `services/message_service.py` erweitern** (AC: 2, 3, 6)
  - [x] `handle_message()` um Proposal-Logik ergänzen:
    ```python
    from gysi_ml.persistence import proposal_repository
    import json

    def handle_message(...) -> dict:
        # ... (bestehende LLM-Aufruf-Logik aus Story 3.2) ...

        # VOR dem LLM-Aufruf: offenen Proposal ablehnen (implizite Ablehnung)
        proposal_repository.reject_pending_proposals(
            session_id=session_id, db_path=db_path
        )

        # ... (LLM-Aufruf + Validierung + Retry) ...

        action = parsed["action"]
        spec = parsed["spec"]
        explanation = parsed["explanation"]

        if action == "execute":
            executor = PipelineExecutor(
                data_path=data_path or settings.data_path,
                artifacts_path=artifacts_path or settings.artifacts_path,
            )
            result = executor.execute(
                spec=spec, session_id=session_id, db_path=db_path
            )
            if "error" in result:
                return {
                    "type": "error",
                    "message": result.get("detail", result.get("error")),
                }
            return {
                "type": "result",
                "run_id": result["run_id"],
                "explanation": explanation,
            }

        # action == "propose"
        proposal = proposal_repository.create_proposal(
            session_id=session_id,
            spec_json=json.dumps(spec),
            explanation=explanation,
            db_path=db_path,
        )
        return {
            "type": "proposal",
            "proposal_id": proposal["proposal_id"],
            "steps": spec.get("steps", []),
            "explanation": explanation,
            "confirmation_required": True,
        }
    ```

- [x] **T5 — `services/proposal_service.py` anlegen** (AC: 4, 5, 7, 8, 9)
  - [x] `src/gysi_ml/services/proposal_service.py` erstellen:
    ```python
    import json
    from gysi_ml.config import get_settings
    from gysi_ml.executor.executor import PipelineExecutor
    from gysi_ml.persistence import proposal_repository

    def confirm_proposal(
        session_id: str,
        proposal_id: str,
        db_path: str | None = None,
        data_path: str | None = None,
        artifacts_path: str | None = None,
    ) -> dict:
        """Bestätigt und führt einen offenen Proposal aus.

        Returns:
            dict mit 'type' und 'run_id' bei Erfolg, oder Fehler-dict.
        """
        settings = get_settings()

        # 1. Proposal laden
        proposal = proposal_repository.get_proposal(
            proposal_id=proposal_id, db_path=db_path
        )
        if proposal is None or proposal["session_id"] != session_id:
            return {"error": "proposal_not_found"}

        if proposal["status"] != "pending":
            return {"error": "no_pending_proposal"}

        # 2. Proposal bestätigen
        proposal_repository.update_proposal_status(
            proposal_id=proposal_id, status="confirmed", db_path=db_path
        )

        # 3. Spec ausführen
        spec = json.loads(proposal["spec_json"])
        executor = PipelineExecutor(
            data_path=data_path or settings.data_path,
            artifacts_path=artifacts_path or settings.artifacts_path,
        )
        result = executor.execute(
            spec=spec, session_id=session_id, db_path=db_path
        )

        if "error" in result:
            return {
                "type": "error",
                "message": result.get("detail", result.get("error")),
            }
        return {
            "type": "result",
            "run_id": result["run_id"],
            "explanation": "Proposal bestätigt und ausgeführt.",
        }
    ```

- [x] **T6 — `api/routes/confirm.py` anlegen** (AC: 4, 5, 7, 8, 9)
  - [x] `src/gysi_ml/api/routes/confirm.py` erstellen:
    ```python
    import json
    from typing import Union
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
    from gysi_ml.api.schemas import ConfirmRequest, ErrorResponse, MessageResponse
    from gysi_ml.persistence import session_repository, message_repository
    from gysi_ml.services.proposal_service import confirm_proposal

    router = APIRouter(prefix="/v1")

    @router.post(
        "/sessions/{session_id}/confirm",
        response_model=MessageResponse,
        responses={
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
        },
    )
    def confirm(
        session_id: str,
        body: ConfirmRequest,
        request: Request,
    ) -> Union[MessageResponse, JSONResponse]:
        db_path = _get_db_path(request)

        # 1. Session validieren
        session = session_repository.get_session(
            session_id=session_id, db_path=db_path
        )
        if session is None:
            return JSONResponse(status_code=404, content=ErrorResponse(
                error="session_not_found",
                detail=f"Session '{session_id}' nicht gefunden.",
                code="SESSION_NOT_FOUND",
            ).model_dump())
        if session["status"] == "closed":
            return JSONResponse(status_code=409, content=ErrorResponse(
                error="session_closed",
                detail=f"Session '{session_id}' ist geschlossen.",
                code="SESSION_CLOSED",
            ).model_dump())

        # 2. Proposal bestätigen + ausführen
        result = confirm_proposal(
            session_id=session_id,
            proposal_id=body.proposal_id,
            db_path=db_path,
            data_path=_get_data_path(request),
            artifacts_path=_get_artifacts_path(request),
        )

        # 3. Fehlerbehandlung
        if result.get("error") == "proposal_not_found":
            return JSONResponse(status_code=404, content=ErrorResponse(
                error="proposal_not_found",
                detail=f"Proposal '{body.proposal_id}' nicht gefunden.",
                code="PROPOSAL_NOT_FOUND",
            ).model_dump())
        if result.get("error") == "no_pending_proposal":
            return JSONResponse(status_code=409, content=ErrorResponse(
                error="no_pending_proposal",
                detail="Kein offener Vorschlag in dieser Session.",
                code="NO_PENDING_PROPOSAL",
            ).model_dump())

        # 4. Assistant-Message persistieren
        message_repository.save_message(
            session_id=session_id,
            role="assistant",
            content=json.dumps(result, ensure_ascii=False),
            db_path=db_path,
        )

        return MessageResponse(**result)
    ```

- [x] **T7 — Router registrieren** (AC: 4)
  - [x] `src/gysi_ml/api/app.py` erweitern:
    ```python
    from gysi_ml.api.routes.confirm import router as confirm_router
    # ...
    app.include_router(confirm_router)
    ```

- [x] **T8 — Unit Tests** (AC: 1, 2, 4, 5, 6, 7, 11)
  - [x] `tests/unit/test_proposal_repository.py` anlegen (13 Tests, alle grün):
    - `test_create_proposal_returns_dict()`: Rückgabe enthält `proposal_id`, `status: "pending"`
    - `test_get_pending_proposal()`: Nach Create → `get_pending_proposal()` gibt den Proposal zurück
    - `test_get_pending_proposal_none()`: Keine Proposals → `None`
    - `test_get_proposal_by_id()`: Nach Create → `get_proposal(id)` gibt den Proposal zurück
    - `test_get_proposal_unknown_id()`: Unbekannte ID → `None`
    - `test_update_proposal_status_confirmed()`: Status wechselt auf `"confirmed"`
    - `test_update_proposal_status_rejected()`: Status wechselt auf `"rejected"`
    - `test_reject_pending_proposals()`: 2 pending Proposals → beide rejected, Rückgabe `2`
    - `test_reject_pending_proposals_no_effect_on_confirmed()`: confirmed Proposal bleibt confirmed
    - `test_isolation_between_sessions()`: Proposal Session A nicht sichtbar für Session B
  - [x] `tests/unit/test_proposal_service.py` anlegen (5 Tests, alle grün):
    - `test_confirm_proposal_success(monkeypatch)`: Gültiger Proposal → `type: "result"` mit `run_id`
    - `test_confirm_proposal_not_found()`: Unbekannter Proposal → `error: "proposal_not_found"`
    - `test_confirm_proposal_wrong_session()`: Proposal gehört anderer Session → `error: "proposal_not_found"`
    - `test_confirm_proposal_already_confirmed()`: Bereits bestätigter Proposal → `error: "no_pending_proposal"`
    - `test_confirm_proposal_executor_error(monkeypatch)`: Executor gibt Fehler zurück → `type: "error"`
  - [x] `tests/unit/test_message_service.py` erweitern (3 neue Tests, autouse-Fixture):
    - `test_handle_message_propose_creates_proposal(monkeypatch)`: Mock LLM → propose → Proposal in DB vorhanden
    - `test_handle_message_implicit_rejection(monkeypatch)`: Offener Proposal → neue Nachricht → Proposal rejected
    - `test_handle_message_execute_no_proposal(monkeypatch)`: Execute-Aktion → kein Proposal in DB

- [x] **T9 — Integration Tests** (AC: 2, 3, 4, 5, 6, 7, 8, 10, 11)
  - [x] `tests/integration/test_proposal_api.py` anlegen (11 Tests, alle grün):
    - **Hinweis**: LLM-Aufrufe werden gemockt.
    - `test_propose_flow(monkeypatch)`: POST /messages (vage) → Mock LLM propose → Response `type: "proposal"` mit `proposal_id`
    - `test_confirm_proposal(monkeypatch)`: Proposal erstellen → POST /confirm → `type: "result"` mit `run_id`
    - `test_confirm_no_pending_proposal()`: POST /confirm ohne offenen Proposal → HTTP 409
    - `test_confirm_unknown_proposal_id()`: POST /confirm mit unbekannter ID → HTTP 404
    - `test_confirm_wrong_session()`: Proposal von Session A → Confirm in Session B → HTTP 404
    - `test_confirm_closed_session()`: Geschlossene Session → POST /confirm → HTTP 409
    - `test_implicit_rejection(monkeypatch)`: Proposal erstellen → neue Nachricht → alter Proposal rejected → neuer Proposal oder Result
    - `test_direct_execute(monkeypatch)`: POST /messages (eindeutig) → Mock LLM execute → `type: "result"` direkt
    - `test_full_conversation_flow(monkeypatch)`: Session → vage Nachricht → Proposal → Confirm → Run-Ergebnis abrufbar
    - `test_assistant_messages_persisted(monkeypatch)`: Nach Proposal + Confirm → GET Session → assistant-Messages vorhanden

## Dev Notes

### Zielstruktur nach dieser Story

```text
backend/src/gysi_ml/
├── persistence/
│   ├── schema.py               # ÄNDERN: + CREATE TABLE proposals
│   └── proposal_repository.py  # NEU: create, get, update, reject
├── services/
│   ├── message_service.py      # ÄNDERN: + Proposal-Erstellung + implizite Ablehnung
│   └── proposal_service.py     # NEU: confirm_proposal()
└── api/
    ├── schemas.py              # ÄNDERN: + ConfirmRequest
    ├── app.py                  # ÄNDERN: + confirm_router registrieren
    └── routes/
        └── confirm.py          # NEU: POST /v1/sessions/{id}/confirm
```

### Architektur-Constraints (kritisch!)

- **Maximal ein offener Proposal pro Session**: `reject_pending_proposals()` wird **vor** jedem neuen LLM-Aufruf aufgerufen. Das stellt sicher, dass nie zwei pending Proposals gleichzeitig existieren. Race Conditions sind bei synchroner Ausführung (kein Background-Task-Framework) kein Problem.
- **Proposal-Spec wird gespeichert, nicht die LLM-Response**: `spec_json` in der `proposals`-Tabelle enthält das Pipeline-Spec-Objekt (`{"steps": [...]}`), nicht die gesamte LLM-Response. Das Spec wird bei Confirm an den `PipelineExecutor` übergeben.
- **Implizite Ablehnung ist still**: Wenn ein neuer Message einen alten Proposal ablehnt, wird das nicht explizit in der Response erwähnt. Der alte Proposal wird auf `"rejected"` gesetzt, der neue Nachrichtenfluss startet normal. Kein 409-Error.
- **Bestätigungsprinzip**: Dieses Feature ist das didaktische Kernprinzip des Systems (siehe PRD). Der Nutzer muss vage Aktionen explizit bestätigen — das System darf bei Vagheit **nie** von sich aus ausführen.
- **Kein Timeout für Proposals**: Ein pending Proposal bleibt offen bis er bestätigt, explizit oder implizit abgelehnt wird. Kein TTL.
- **Assistant-Messages bei Confirm**: Auch die Confirm-Response wird als Assistant-Message persistiert, damit der Gesprächsverlauf vollständig ist.

### Flussdiagramm: Message → Proposal → Confirm

```text
POST /sessions/{id}/messages {"text": "Bereite die Daten vor"}
│
├── Offene Proposals ablehnen (reject_pending_proposals)
├── User-Message speichern
├── LLM aufrufen
├── LLM-Response validieren
│
├── action == "execute":
│   ├── PipelineExecutor.execute(spec)
│   ├── Assistant-Message speichern
│   └── Response: {"type": "result", "run_id": "..."}
│
└── action == "propose":
    ├── Proposal in proposals-Tabelle speichern (status: "pending")
    ├── Assistant-Message speichern
    └── Response: {"type": "proposal", "proposal_id": "...", "steps": [...]}

POST /sessions/{id}/confirm {"proposal_id": "..."}
│
├── Session validieren (404 / 409-closed)
├── Proposal laden + validieren (404 / 409-no_pending)
├── Proposal-Status → "confirmed"
├── PipelineExecutor.execute(spec aus Proposal)
├── Assistant-Message speichern
└── Response: {"type": "result", "run_id": "..."}
```

### Vagheits-Erkennung

Die Vagheits-Erkennung liegt **beim LLM**, nicht im Python-Code. Der System-Prompt (aus Story 3.2) instruiert das LLM, `action: "propose"` zu wählen wenn:
- Der Nutzer keine konkreten Steps benennt ("Bereite die Daten vor")
- Parameter fehlen ("Trainiere ein Modell" — welches?)
- Mehrere Interpretationen möglich sind

Python-Code prüft nur das `action`-Feld der validierten LLM-Response und verzweigt entsprechend. Keine eigene Vagheits-Heuristik im Backend.

### Regressions-Schutz

- Alle bestehenden Tests (284+ aus Epic 1+2, plus Story 3.1 + 3.2 Tests) müssen weiterhin grün sein
- `PipelineExecutor` wird unverändert genutzt
- `message_service.handle_message()` wird erweitert aber das Interface bleibt gleich (Eingabe-Signatur und Return-Typ-Struktur sind seit Story 3.1 stabil)

### Smoke-Check nach Integration

```bash
# Im backend-Verzeichnis
uv run pytest tests/unit/test_proposal_repository.py -v
uv run pytest tests/unit/test_proposal_service.py -v
uv run pytest tests/integration/test_proposal_api.py -v
uv run pytest tests/ --cov=src/gysi_ml --cov-report=term-missing
```

### Referenzen

- FR6: Vagheits-Erkennung — [epics.md](../../planning-artifacts/backend/epics.md)
- FR7: Direkte Ausführung bei Klarheit — [epics.md](../../planning-artifacts/backend/epics.md)
- FR8: Proposal-Response bei Vagheit — [epics.md](../../planning-artifacts/backend/epics.md)
- FR9: Proposal bestätigen — [epics.md](../../planning-artifacts/backend/epics.md)
- FR10: Proposal ablehnen/modifizieren — [epics.md](../../planning-artifacts/backend/epics.md)
- Bestätigungsprinzip als didaktisches Design: [prd.md](../../planning-artifacts/backend/prd.md) → Innovation & Novel Patterns
- NFR-S3: Parameterized Queries — [prd.md](../../planning-artifacts/backend/prd.md)
- PipelineExecutor: [backend/src/gysi_ml/executor/executor.py](../../../backend/src/gysi_ml/executor/executor.py)
- Message-Service (Story 3.2): [backend/src/gysi_ml/services/message_service.py](../../../backend/src/gysi_ml/services/message_service.py)
- Session-Repository-Pattern: [backend/src/gysi_ml/persistence/session_repository.py](../../../backend/src/gysi_ml/persistence/session_repository.py)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

Keine externen Debug-Logs.

### Completion Notes List

- T8/T9: autouse-Fixture-Pattern notwendig, da `reject_pending_proposals` in `message_service.py` existierende Tests (db_path=None) brechen würde. Modul-Level `_REAL_*`-Caches lösen das Problem mit der Fixture-Reihenfolge.
- Integration-Test `test_assistant_messages_persisted`: `_mock_propose` überschreibt `message_repository.get_messages_for_session` global (Python-Modul-Aliasing). Gelöst durch eigene `client_with_db`-Fixture die den `db_path` exponiert und direkte DB-Abfrage statt API-Abfrage.
- Gesamt: 375 Tests bestanden, 97% Coverage.

### File List

**Neu:**
- `backend/src/gysi_ml/persistence/proposal_repository.py`
- `backend/src/gysi_ml/services/proposal_service.py`
- `backend/src/gysi_ml/api/routes/confirm.py`
- `backend/tests/unit/test_proposal_repository.py`
- `backend/tests/unit/test_proposal_service.py`
- `backend/tests/integration/test_proposal_api.py`

**Geändert:**
- `backend/src/gysi_ml/persistence/schema.py`
- `backend/src/gysi_ml/services/message_service.py`
- `backend/src/gysi_ml/api/schemas.py`
- `backend/src/gysi_ml/api/app.py`
- `backend/tests/unit/test_message_service.py`

## Change Log

| Datum | Version | Beschreibung | Autor |
| --- | --- | --- | --- |
| 2025-06-17 | 1.0 | Story implementiert, alle Tests grün, 97% Coverage | Dev Agent |
| 2026-03-18 | 1.1 | Code Review: M1–M4 + L1 gefixt, 377 Tests, 100% Coverage auf neuen Modulen | Dev Agent |
