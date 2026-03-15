# Story 1.1: FastAPI-Grundgerüst, SQLite-Schema und Session-Endpunkte

Status: ready-for-dev

## Story

Als ein API-Konsument (Entwickler oder HTTP-Client),
möchte ich Sessions erstellen, abrufen, auflisten und schließen sowie den Service-Status prüfen können,
damit ich den Lebenszyklus von Konversations-Sessions über die REST API verwalten kann und sicherstellen kann, dass der Service läuft.

## Acceptance Criteria

1. **[Health]** `GET /v1/health` liefert `{"status": "ok"}` mit HTTP 200.

2. **[Session erstellen]** `POST /v1/sessions` mit optionalem Body `{"name": "..."}` legt eine neue Session mit eindeutiger `session_id` (UUID4) in SQLite an und antwortet mit HTTP 201.
   Response enthält `session_id`, `name` (optional), `created_at` (ISO 8601 UTC), `status: "active"`.

3. **[Session abrufen]** `GET /v1/sessions/{session_id}` gibt Session-Metadaten mit HTTP 200 zurück.

4. **[Sessions auflisten]** `GET /v1/sessions` gibt alle Sessions als Array zurück (auch leer möglich).

5. **[Session schließen]** `DELETE /v1/sessions/{session_id}` setzt `status` auf `"closed"` (Soft-Delete) und antwortet HTTP 200.
   Session bleibt in SQLite erhalten — kein Hard-Delete.

6. **[404 bei unbekannter Session]** `GET /v1/sessions/{session_id}` mit nicht existierender ID gibt HTTP 404 zurück:
   `{"error": "session_not_found", "detail": "...", "code": "SESSION_NOT_FOUND"}`.

7. **[422 bei ungültiger Payload]** Jeder Endpunkt mit fehlerhafter Payload gibt HTTP 422 mit strukturierten Pydantic-Validierungsfehlern zurück — kein Absturz.

8. **[SQLite-Schema vollständig]** Alle 4 Tabellen (`sessions`, `runs`, `artifacts`, `spec_versions`) werden beim Start angelegt (CREATE TABLE IF NOT EXISTS) — auch wenn nur `sessions` in dieser Story aktiv genutzt wird.

9. **[Konfiguration]** DB-Pfad, Host und Port kommen ausschließlich aus `config.py` / `.env` — keine hartcodierten Werte.

10. **[Test-Coverage]** `pytest --cov=src/gysi_ml` erreicht ≥ 85 % für die in dieser Story implementierten Module.

## Tasks / Subtasks

- [ ] **T1 — Abhängigkeiten eintragen** (AC: 9)
  - [ ] `requirements.txt` befüllen: `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `python-dotenv`
  - [ ] `requirements-dev.txt` ergänzen: `httpx`, `pytest-asyncio`
  - [ ] Abhängigkeiten installieren: `uv pip install -r requirements-dev.txt`

- [ ] **T2 — Settings / Config** (AC: 9)
  - [ ] `src/gysi_ml/config.py` anlegen: `Settings`-Klasse mit pydantic-settings, liest aus `.env`
  - [ ] Felder: `db_path: str = "../.local/gysi_ml.db"`, `host: str = "0.0.0.0"`, `port: int = 8000`
  - [ ] `.env.example` um `DB_PATH`, `HOST`, `PORT` ergänzen

- [ ] **T3 — SQLite-Persistence-Layer** (AC: 8)
  - [ ] `src/gysi_ml/persistence/database.py`: `get_connection()` (liefert `sqlite3.Connection` mit `row_factory = sqlite3.Row`)
  - [ ] `src/gysi_ml/persistence/schema.py`: `create_all_tables()` — CREATE TABLE IF NOT EXISTS für alle 4 Tabellen (Schemas siehe Dev Notes)
  - [ ] Datenbank-Verzeichnis wird beim Start automatisch angelegt (`Path.mkdir(parents=True, exist_ok=True)`)

- [ ] **T4 — Pydantic v2 Schemas** (AC: 2, 3, 4, 5, 6, 7)
  - [ ] `src/gysi_ml/api/schemas.py` anlegen
  - [ ] `SessionCreateRequest`: optionales `name: str | None = None`
  - [ ] `SessionResponse`: `session_id: str`, `name: str | None`, `created_at: datetime`, `status: str`
  - [ ] `SessionListResponse`: `sessions: list[SessionResponse]`
  - [ ] `ErrorResponse`: `error: str`, `detail: str`, `code: str`
  - [ ] `HealthResponse`: `status: str`
  - [ ] Alle Datetimes immer UTC (`datetime.timezone.utc`)

- [ ] **T5 — Session-Repository** (AC: 2–5)
  - [ ] `src/gysi_ml/persistence/session_repository.py`
  - [ ] `create_session(name: str | None) -> dict`
  - [ ] `get_session(session_id: str) -> dict | None`
  - [ ] `list_sessions() -> list[dict]`
  - [ ] `close_session(session_id: str) -> dict | None` (setzt status → "closed")
  - [ ] Alle Queries ausschließlich als Parameterized Queries (`?`-Platzhalter) — kein f-String-SQL

- [ ] **T6 — API Endpoints** (AC: 1–7)
  - [ ] `src/gysi_ml/api/routes/sessions.py`: APIRouter mit prefix `/v1`
  - [ ] `src/gysi_ml/api/routes/health.py`: `GET /v1/health`
  - [ ] `src/gysi_ml/api/app.py`: FastAPI-App-Factory, registriert alle Router, startup-Hook für `create_all_tables()`
  - [ ] HTTP-Statuscodes: `POST /sessions` → 201, alle anderen → 200, Not Found → 404, Validation → 422
  - [ ] 404-Handler gibt `ErrorResponse` zurück (kein Pydantic-Standard-Fehler-Format)

- [ ] **T7 — Entry Point** (AC: 9)
  - [ ] `src/gysi_ml/main.py`: `uvicorn.run(create_app(), ...)` mit Settings aus config.py
  - [ ] `scripts/run_dev.sh`: `uv run python -m gysi_ml.main`

- [ ] **T8 — Unit Tests** (AC: 10)
  - [ ] `tests/unit/test_session_repository.py`: alle Repository-Methoden mit In-Memory-SQLite (`:memory:`)
  - [ ] `tests/unit/test_schemas.py`: Validierungsfehler bei ungültigen Inputs

- [ ] **T9 — Integration Tests** (AC: 1–7, 10)
  - [ ] `tests/integration/test_sessions_api.py`: FastAPI `TestClient` (httpx)
  - [ ] Testfälle: Health, CRUD Happy Path, 404, 422, Soft-Delete
  - [ ] Fixture: frische In-Memory-DB pro Test (kein globaler State, NFR-T4)

## Dev Notes

### Zielstruktur nach dieser Story

```
backend/
├── requirements.txt          # fastapi, uvicorn[standard], pydantic>=2.0, python-dotenv
├── requirements-dev.txt      # + httpx, pytest-asyncio
├── .env.example              # DB_PATH, HOST, PORT, OPENAI_API_KEY, LLM_MODEL
└── src/gysi_ml/
    ├── config.py             # NEU: Settings (pydantic-settings)
    ├── main.py               # NEU: Entry Point
    ├── api/
    │   ├── app.py            # NEU: FastAPI App Factory
    │   ├── schemas.py        # NEU: Pydantic v2 Request/Response-Modelle
    │   └── routes/
    │       ├── health.py     # NEU: GET /v1/health
    │       └── sessions.py   # NEU: Session CRUD /v1/sessions
    └── persistence/
        ├── database.py       # NEU: Connection Factory
        ├── schema.py         # NEU: CREATE TABLE IF NOT EXISTS
        └── session_repository.py  # NEU: CRUD-Queries
```

Tests:
```
backend/tests/
├── unit/
│   ├── test_session_repository.py   # NEU
│   └── test_schemas.py              # NEU
└── integration/
    └── test_sessions_api.py         # NEU
```

### SQLite-Schema (alle 4 Tabellen)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    name        TEXT,
    created_at  TEXT NOT NULL,   -- ISO 8601 UTC, z.B. "2026-03-15T10:00:00+00:00"
    status      TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'closed'
);

CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    spec_version TEXT,
    status       TEXT NOT NULL,   -- 'running' | 'completed' | 'failed'
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    error_message TEXT,
    result_json  TEXT,            -- serialisiertes Ergebnis-Dict (JSON)
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    type        TEXT NOT NULL,    -- z.B. 'feature_importance', 'ebm_global_explanation'
    file_path   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS spec_versions (
    spec_id     TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    version     TEXT NOT NULL,    -- 'v1', 'v2', ...
    spec_json   TEXT NOT NULL,    -- serialisierte Pipeline-Spec (JSON)
    created_at  TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

> ⚠️ `runs`, `artifacts` und `spec_versions` werden jetzt angelegt, aber erst in späteren Stories befüllt.

### Technischer Stack (diese Story)

| Technologie | Version | Hinweis |
|---|---|---|
| Python | 3.10 / 3.11 | Gemäß AGENTS.md, bereits im .venv |
| FastAPI | ≥ 0.110 | Stabile aktuelle Version, async-fähig |
| Uvicorn | ≥ 0.29 | `uvicorn[standard]` für WebSocket-Support (später benötigt) |
| Pydantic | ≥ 2.0 | v2 Pflicht — **kein** Pydantic v1 Style |
| python-dotenv | ≥ 1.0 | Lädt `.env` für lokale Entwicklung |
| httpx | ≥ 0.27 | FastAPI `TestClient` verwendet httpx intern |
| sqlite3 | stdlib | Kein ORM — direkte Parameterized Queries |

### FastAPI App Factory Pattern

`api/app.py` soll eine Factory-Funktion `create_app() -> FastAPI` exportieren, damit Tests eine isolierte App-Instanz erzeugen können:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="gysi-ml", version="0.1.0")
    
    @app.on_event("startup")
    def startup():
        create_all_tables(settings.db_path)
    
    app.include_router(health_router)
    app.include_router(sessions_router)
    return app
```

### Pydantic v2 Wichtige Unterschiede

- `model_config = ConfigDict(...)` statt innerer `Config`-Klasse
- `model_validator` statt `validator` (v1)
- `Field(default=...)` statt `Field(...)` ohne Keyword
- `model_dump()` statt `.dict()`

### Parameterized Queries — Pflicht (NFR-S3)

```python
# ✅ KORREKT
cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))

# ❌ VERBOTEN — SQL Injection
cursor.execute(f"SELECT * FROM sessions WHERE session_id = '{session_id}'")
```

### Test-Fixture-Pattern (NFR-T4: kein globaler State)

Jeder Test bekommt eine frische In-Memory-SQLite-DB:

```python
import pytest
from fastapi.testclient import TestClient
from gysi_ml.api.app import create_app
from gysi_ml.config import Settings

@pytest.fixture
def client(tmp_path):
    settings = Settings(db_path=str(tmp_path / "test.db"))
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c
```

### Fehler-Response-Format

Alle 4xx-Fehler folgen diesem Schema (kein FastAPI-Default-Fehlerformat nach außen):

```json
{
  "error": "session_not_found",
  "detail": "Session mit ID 'xyz' nicht gefunden.",
  "code": "SESSION_NOT_FOUND"
}
```

HTTP 422 von Pydantic darf im Standard-Format bleiben (FastAPI-eigenes Detail-Array ist akzeptiert).

### Artefakt-Pfad und DB-Pfad

- DB: `../.local/gysi_ml.db` (relativ vom Backend-Root, konfigurierbar via `DB_PATH` in `.env`)
- Artefakte (spätere Stories): `../artifacts/` — Ordner jetzt noch nicht anlegen

### Keine Business-Logik in Route-Handlern

Route-Handler rufen ausschließlich Repository-Methoden auf — keine SQL direkt in `routes/sessions.py`.

### Coverage-Ziel (NFR-T1)

```bash
cd backend
uv run pytest tests/ --cov=src/gysi_ml --cov-report=term-missing
```

Ziel: ≥ 85 % für alle in dieser Story neu angelegten Module.

### Nicht in Scope dieser Story

- LLM-Integration (Story 3.2)
- Pipeline-Executor (Story 1.2)
- Runs/Artifacts befüllen (Story 1.5)
- Capabilities-Endpunkt (Story 1.6)
- Authentifizierung (kein Scope im MVP)

### Referenzen

- [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 1.1]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#NonFunctional Requirements — NFR-S3, NFR-T1–T4, NFR-M3, NFR-M4]
- [Source: _bmad-output/planning-artifacts/backend/prd.md#FR1–FR4, FR43]
- [Source: backend/AGENTS.md#Architektur-Schichten]
- [Source: backend/AGENTS.md#Konventionen]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

### File List
