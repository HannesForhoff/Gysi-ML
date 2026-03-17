# Story 3.1: Message-Endpunkt und Gesprächsverlauf-Persistenz

Status: done

## Story

Als ein API-Konsument,
möchte ich Texteingaben an eine Session senden und den Gesprächsverlauf persistiert abrufen können,
damit alle Interaktionen auditierbar sind und das System auf frühere Nachrichten in der Session referenzieren kann.

## Acceptance Criteria

1. **[messages-Tabelle angelegt]** Beim Service-Start wird eine SQLite-Tabelle `messages` angelegt mit den Spalten `message_id` (TEXT PK), `session_id` (TEXT FK → sessions), `role` (TEXT, `"user"` oder `"assistant"`), `content` (TEXT), `created_at` (TEXT, ISO-Timestamp). Parameterized Queries, keine SQL-Injection.

2. **[Nutzernachricht persistiert]** `POST /v1/sessions/{id}/messages` mit Body `{"text": "..."}` speichert die Nachricht in `messages` mit `role: "user"` und gibt eine typisierte Response zurück.

3. **[Typisierte Response-Struktur]** Die Response ist immer ein JSON-Objekt mit Pflichtfeld `type`. Mögliche Werte: `"proposal"`, `"result"`, `"error"`. Kein unstrukturierter Freitext als primäre Response. In dieser Story (ohne LLM) gibt der Endpunkt `{"type": "error", "message": "LLM-Service nicht konfiguriert."}` mit HTTP 503 zurück, wenn `openai_api_key` oder `llm_model` nicht gesetzt sind.

4. **[Assistenten-Antwort persistiert]** Jede System-Antwort (auch Fehler-Responses) wird mit `role: "assistant"` und dem serialisierten Response-JSON als `content` in `messages` gespeichert.

5. **[Gesprächsverlauf abrufbar]** `GET /v1/sessions/{id}` enthält ein Feld `messages` als chronologisch sortiertes Array von `{"message_id", "role", "content", "created_at"}`.

6. **[409 bei geschlossener Session]** `POST /v1/sessions/{id}/messages` auf eine geschlossene Session gibt HTTP 409 mit `{"error": "session_closed", "detail": "...", "code": "SESSION_CLOSED"}` zurück.

7. **[404 bei unbekannter Session]** `POST /v1/sessions/{id}/messages` auf eine unbekannte Session-ID gibt HTTP 404 mit `{"error": "session_not_found", ...}` zurück.

8. **[Orchestrierungsschicht vorbereitet]** Ein `MessageService`-Modul (`services/message_service.py`) existiert mit Funktion `handle_message(session_id, text, db_path, ...) -> dict`, das den Nachrichtenfluss koordiniert. In dieser Story delegiert es an einen Platzhalter, der ab Story 3.2 durch die LLM-Integration ersetzt wird.

9. **[Keine Regression]** Alle bestehenden 284+ Tests bleiben grün. Kein Breaking Change an bestehenden Endpunkten.

10. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — SQLite-Schema erweitern: `messages`-Tabelle** (AC: 1)
  - [ ] `src/gysi_ml/persistence/schema.py` ergänzen — nach dem bestehenden `CREATE TABLE IF NOT EXISTS spec_versions`:
    ```sql
    CREATE TABLE IF NOT EXISTS messages (
        message_id  TEXT PRIMARY KEY,
        session_id  TEXT NOT NULL,
        role        TEXT NOT NULL,
        content     TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    ```
  - [ ] `role` enthält `"user"` oder `"assistant"` — keine ENUM-Constraint in SQLite, aber im Repository validieren
  - [ ] Parameterized Queries in allen Queries (NFR-S3)

- [x] **T2 — `persistence/message_repository.py` anlegen** (AC: 1, 2, 4, 5)
  - [ ] `src/gysi_ml/persistence/message_repository.py` erstellen:
    - `save_message(session_id: str, role: str, content: str, db_path: str | None = None) -> dict`
      - Generiert `message_id = str(uuid.uuid4())`
      - `created_at = datetime.now(timezone.utc).isoformat()`
      - INSERT mit Parameterized Query
      - Gibt `{"message_id", "session_id", "role", "content", "created_at"}` zurück
    - `get_messages_for_session(session_id: str, db_path: str | None = None) -> list[dict]`
      - SELECT alle Messages der Session, sortiert nach `created_at ASC`
      - Gibt Liste von `{"message_id", "role", "content", "created_at"}` zurück
  - [ ] Muster identisch zu `session_repository.py`: `get_connection(db_path)`, `try/finally conn.close()`

- [x] **T3 — Pydantic-Schemas für Messages** (AC: 2, 3, 5)
  - [ ] `src/gysi_ml/api/schemas.py` erweitern:
    ```python
    class MessageRequest(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)
        text: str

    class MessageSummary(BaseModel):
        message_id: str
        role: str
        content: str
        created_at: str

    class MessageResponse(BaseModel):
        """Typisierte Response für POST /messages."""
        type: str  # "proposal" | "result" | "error"
        # Optionale Felder je nach Typ:
        run_id: Optional[str] = None
        message: Optional[str] = None
        steps: Optional[list[dict]] = None
        explanation: Optional[str] = None
        confirmation_required: Optional[bool] = None
        proposal_id: Optional[str] = None
    ```
  - [ ] `SessionResponse` erweitern — neues optionales Feld:
    ```python
    messages: Optional[list[MessageSummary]] = None
    ```

- [x] **T4 — `services/message_service.py` anlegen** (AC: 8)
  - [ ] Neues Package: `src/gysi_ml/services/__init__.py` (leer)
  - [ ] `src/gysi_ml/services/message_service.py` erstellen:
    ```python
    from gysi_ml.config import get_settings

    def handle_message(
        session_id: str,
        text: str,
        db_path: str | None = None,
        data_path: str | None = None,
        artifacts_path: str | None = None,
    ) -> dict:
        """Koordiniert den Nachrichtenfluss: Text → LLM → Ausführung/Proposal.

        Returns:
            dict mit Pflichtfeld 'type' ('proposal', 'result', 'error')
        """
        settings = get_settings()
        if not settings.openai_api_key or not settings.llm_model:
            return {
                "type": "error",
                "message": "LLM-Service nicht konfiguriert. "
                "Bitte OPENAI_API_KEY und LLM_MODEL in .env setzen.",
            }
        # Platzhalter — wird in Story 3.2 durch LLM-Aufruf ersetzt
        return {
            "type": "error",
            "message": "LLM-Integration noch nicht implementiert.",
        }
    ```
  - [ ] Der Service empfängt alle Pfade (`db_path`, `data_path`, `artifacts_path`) als Parameter, damit er in 3.2/3.3 den Executor aufrufen kann

- [x] **T5 — `api/routes/messages.py` anlegen** (AC: 2, 3, 4, 6, 7)
  - [ ] `src/gysi_ml/api/routes/messages.py` erstellen:
    ```python
    router = APIRouter(prefix="/v1")

    @router.post(
        "/sessions/{session_id}/messages",
        response_model=MessageResponse,
        responses={
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"description": "LLM nicht konfiguriert"},
        },
    )
    def send_message(
        session_id: str,
        body: MessageRequest,
        request: Request,
    ) -> Union[MessageResponse, JSONResponse]:
        db_path = _get_db_path(request)

        # 1. Session validieren (404 / 409)
        session = session_repository.get_session(session_id=session_id, db_path=db_path)
        if session is None:
            return JSONResponse(status_code=404, content=ErrorResponse(...).model_dump())
        if session["status"] == "closed":
            return JSONResponse(status_code=409, content=ErrorResponse(
                error="session_closed",
                detail=f"Session '{session_id}' ist geschlossen.",
                code="SESSION_CLOSED",
            ).model_dump())

        # 2. User-Message speichern
        message_repository.save_message(
            session_id=session_id, role="user", content=body.text, db_path=db_path
        )

        # 3. An MessageService delegieren
        result = handle_message(
            session_id=session_id,
            text=body.text,
            db_path=db_path,
            data_path=_get_data_path(request),
            artifacts_path=_get_artifacts_path(request),
        )

        # 4. Assistenten-Antwort speichern
        import json
        message_repository.save_message(
            session_id=session_id,
            role="assistant",
            content=json.dumps(result, ensure_ascii=False),
            db_path=db_path,
        )

        # 5. Response zurückgeben
        if result.get("type") == "error" and "nicht konfiguriert" in result.get("message", ""):
            return JSONResponse(status_code=503, content=result)
        return MessageResponse(**result)
    ```

- [x] **T6 — `SessionResponse` um Messages erweitern** (AC: 5)
  - [ ] `api/routes/sessions.py` → `get_session()` erweitern:
    - Nach dem `session_repository.get_session()` Aufruf:
    ```python
    messages = message_repository.get_messages_for_session(
        session_id=session_id, db_path=db_path
    )
    return SessionResponse(**row, messages=[MessageSummary(**m) for m in messages])
    ```
  - [ ] Import `message_repository` und `MessageSummary` hinzufügen
  - [ ] **Achtung**: `list_sessions()` und `create_session()` geben `messages=None` zurück (kein Overhead)

- [x] **T7 — Router registrieren** (AC: 2)
  - [ ] `src/gysi_ml/api/app.py` erweitern:
    ```python
    from gysi_ml.api.routes.messages import router as messages_router
    # ...
    app.include_router(messages_router)
    ```

- [x] **T8 — Unit Tests** (AC: 1, 2, 4, 5, 10)
  - [ ] `tests/unit/test_message_repository.py` anlegen:
    - `test_save_message_returns_dict()`: Rückgabe enthält `message_id`, `role`, `content`, `created_at`
    - `test_save_message_user_role()`: `role == "user"` korrekt gespeichert
    - `test_save_message_assistant_role()`: `role == "assistant"` korrekt gespeichert
    - `test_get_messages_for_session_chronological()`: 3 Messages anlegen → Reihenfolge korrekt
    - `test_get_messages_for_session_empty()`: Session ohne Messages → leere Liste
    - `test_get_messages_for_session_isolation()`: Messages einer Session tauchen nicht bei anderer Session auf
  - [ ] `tests/unit/test_message_service.py` anlegen:
    - `test_handle_message_no_llm_configured()`: ohne API-Key → `{"type": "error", ...}` mit "nicht konfiguriert"
    - `test_handle_message_returns_dict_with_type()`: Rückgabe hat immer `type`-Feld

- [x] **T9 — Integration Tests** (AC: 2, 3, 5, 6, 7, 9, 10)
  - [ ] `tests/integration/test_messages_api.py` anlegen:
    - `test_post_message_saves_and_returns()`: POST /messages → HTTP 503 (kein LLM), Message in DB gespeichert
    - `test_post_message_404_unknown_session()`: unbekannte Session → HTTP 404
    - `test_post_message_409_closed_session()`: geschlossene Session → HTTP 409
    - `test_messages_in_session_detail()`: POST Message → GET Session → `messages`-Array enthält user + assistant Messages
    - `test_assistant_message_persisted()`: Nach POST → 2 Messages in DB (user + assistant)
    - `test_message_response_has_type_field()`: Response-Body enthält `type`-Feld
    - `test_existing_endpoints_unchanged()`: Health, Sessions, Execute, Runs, Capabilities, Artifacts reagieren wie bisher (Regressions-Schutz)

## Dev Notes

### Zielstruktur nach dieser Story

```text
backend/src/gysi_ml/
├── api/
│   ├── schemas.py          # ÄNDERN: + MessageRequest, MessageSummary, MessageResponse; SessionResponse + messages
│   ├── app.py              # ÄNDERN: + messages_router registrieren
│   └── routes/
│       ├── messages.py     # NEU: POST /v1/sessions/{id}/messages
│       └── sessions.py     # ÄNDERN: GET /sessions/{id} mit messages-Array
├── persistence/
│   ├── schema.py           # ÄNDERN: + CREATE TABLE messages
│   └── message_repository.py  # NEU: save_message, get_messages_for_session
└── services/
    ├── __init__.py         # NEU (leer)
    └── message_service.py  # NEU: handle_message() Platzhalter
```

### Architektur-Constraints (kritisch!)

- **Services-Schicht ist neu**: Das `services/`-Package wird hier erstmals eingeführt. Es koordiniert die Interaktion zwischen Persistence, LLM-Client (Story 3.2) und Executor. Die Route (`messages.py`) ruft den Service auf — nicht umgekehrt. Die Route kümmert sich um HTTP-Belange (Statuscodes, Serialisierung), der Service um Geschäftslogik.
- **Message-Persistenz vor LLM-Aufruf**: Die User-Message wird **vor** dem Service-Aufruf gespeichert, damit sie auch bei LLM-Fehlern im Verlauf erscheint.
- **Assistenten-Antwort nach Service-Aufruf**: Die System-Antwort wird **nach** dem Service-Aufruf gespeichert — auch bei Fehlern. Der `content` der Assistenten-Nachricht ist das serialisierte Response-JSON.
- **SessionResponse bleibt abwärtskompatibel**: `messages` ist `Optional` — bestehende Endpunkte (`list_sessions`, `create_session`, `delete_session`) geben `messages=None` zurück. Nur `get_session` befüllt das Feld — kein Performance-Overhead für Listen-Endpunkte.
- **Kein freier Text als primäre Response** (NFR): Die `MessageResponse` hat immer ein `type`-Feld. Downstream (Story 3.2/3.3) kommen weitere Felder hinzu (`run_id`, `steps`, `proposal_id` etc.).
- **Parameterized Queries (NFR-S3)**: Alle SQL-Statements nutzen `?`-Platzhalter — keine String-Interpolation.
- **`_get_db_path` / `_get_data_path` / `_get_artifacts_path` Helfer**: Identisches Muster wie in `execute.py` und `runs.py` — über `request.app.state` auflösen.

### Konvention: Fehler-Response-Schema

Bestehende Endpunkte nutzen `ErrorResponse(error=..., detail=..., code=...)`. Die `MessageResponse` hat ein eigenes Schema mit `type: "error"`, `message: "..."`. Das sind zwei unterschiedliche Felder:
- `ErrorResponse` → für HTTP-Fehler (404, 409, 422) — vom Router direkt zurückgegeben
- `MessageResponse` mit `type: "error"` → für Geschäftslogik-Fehler (LLM nicht verfügbar, ungültiger Output) — als Teil des normalen Nachrichtenflusses zurückgegeben

### Vorbereitung für Story 3.2 und 3.3

Der `handle_message()`-Service hat absichtlich alle benötigten Parameter (`session_id`, `text`, `db_path`, `data_path`, `artifacts_path`), damit in Story 3.2 der LLM-Client und in Story 3.3 der `PipelineExecutor` aufgerufen werden können, ohne die Signatur ändern zu müssen.

### Regressions-Schutz

- Alle bestehenden Tests (284+) müssen weiterhin grün sein
- `GET /v1/sessions/{id}` hat jetzt ein zusätzliches optionales `messages`-Feld — bestehende Tests die die Response parsen könnten minimal angepasst werden (z.B. wenn sie `model_dump()` und exakte Keys prüfen)
- `POST /v1/sessions/{id}/execute` bleibt unverändert — der neue `/messages`-Endpunkt ist additiv

### Smoke-Check nach Integration

```bash
# Im backend-Verzeichnis
uv run pytest tests/unit/test_message_repository.py -v
uv run pytest tests/unit/test_message_service.py -v
uv run pytest tests/integration/test_messages_api.py -v
uv run pytest tests/ --cov=src/gysi_ml --cov-report=term-missing
```

### Referenzen

- FR5: Nutzereingabe an Session senden — [epics.md](../../planning-artifacts/backend/epics.md)
- FR38: Gesprächsverlauf persistieren — [epics.md](../../planning-artifacts/backend/epics.md)
- NFR-S3: Parameterized Queries — [prd.md](../../planning-artifacts/backend/prd.md)
- NFR-R1: Strukturierte Fehler-Response — [prd.md](../../planning-artifacts/backend/prd.md)
- Session-Repository-Pattern: [backend/src/gysi_ml/persistence/session_repository.py](../../../backend/src/gysi_ml/persistence/session_repository.py)
- Execute-Route als Muster: [backend/src/gysi_ml/api/routes/execute.py](../../../backend/src/gysi_ml/api/routes/execute.py)
- Pydantic-Schemas: [backend/src/gysi_ml/api/schemas.py](../../../backend/src/gysi_ml/api/schemas.py)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

Keine Probleme — alle 23 neuen Tests grün, 307 gesamt (0 Regressions).

### Completion Notes List

- `services/`-Package erstmals eingeführt (`services/__init__.py` + `message_service.py`)
- `MessageSummary` in `SessionResponse` als Optional ergänzt — vollständig abwärtskompatibel
- `role`-Validierung im Repository (ValueError bei ungültigem Wert)
- Parameterized Queries in allen SQL-Statements (NFR-S3 eingehalten)
- `get_settings()` über `lru_cache` — in Tests via `unittest.mock.patch` überschrieben
- **[CR-Fix M1]** 503-Erkennung auf `error_code == "llm_not_configured"` umgestellt (Konstante `LLM_NOT_CONFIGURED` in `message_service.py`) — kein fragiles String-Matching mehr
- **[CR-Fix M2]** `MessageRequest.text` hat `min_length=1` — leere/Whitespace-only Texte geben HTTP 422 zurück

### File List

**Geändert:**

- `backend/src/gysi_ml/persistence/schema.py` — `messages`-Tabelle hinzugefügt
- `backend/src/gysi_ml/api/schemas.py` — `MessageSummary`, `MessageRequest`, `MessageResponse` hinzugefügt; `SessionResponse` um `messages: Optional[list[MessageSummary]]` erweitert
- `backend/src/gysi_ml/api/routes/sessions.py` — `get_session()` gibt jetzt `messages`-Array zurück
- `backend/src/gysi_ml/api/app.py` — `messages_router` registriert

**Neu erstellt:**

- `backend/src/gysi_ml/persistence/message_repository.py`
- `backend/src/gysi_ml/services/__init__.py`
- `backend/src/gysi_ml/services/message_service.py`
- `backend/src/gysi_ml/api/routes/messages.py`
- `backend/tests/unit/test_message_repository.py`
- `backend/tests/unit/test_message_service.py`
- `backend/tests/integration/test_messages_api.py`
