# Story 1.1: FastAPI-Grundgerüst, SQLite-Schema und Session-Endpunkte

Status: done

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

- [x] **T1 — Abhängigkeiten eintragen** (AC: 9)
  - [x] `requirements.txt` befüllen: `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `python-dotenv`
  - [x] `requirements-dev.txt` ergänzen: `httpx`, `pytest-asyncio`
  - [x] Abhängigkeiten installieren: `uv pip install -r requirements-dev.txt`

- [x] **T2 — Settings / Config** (AC: 9)
  - [x] `src/gysi_ml/config.py` anlegen: `Settings`-Klasse mit pydantic-settings, liest aus `.env`
  - [x] Felder: `db_path: str = "../.local/gysi_ml.db"`, `host: str = "0.0.0.0"`, `port: int = 8000`
  - [x] `.env.example` um `DB_PATH`, `HOST`, `PORT` ergänzen

- [x] **T3 — SQLite-Persistence-Layer** (AC: 8)
  - [x] `src/gysi_ml/persistence/database.py`: `get_connection()` (liefert `sqlite3.Connection` mit `row_factory = sqlite3.Row`)
  - [x] `src/gysi_ml/persistence/schema.py`: `create_all_tables()` — CREATE TABLE IF NOT EXISTS für alle 4 Tabellen (Schemas siehe Dev Notes)
  - [x] Datenbank-Verzeichnis wird beim Start automatisch angelegt (`Path.mkdir(parents=True, exist_ok=True)`)

- [x] **T4 — Pydantic v2 Schemas** (AC: 2, 3, 4, 5, 6, 7)
  - [x] `src/gysi_ml/api/schemas.py` anlegen
  - [x] `SessionCreateRequest`: optionales `name: str | None = None`
  - [x] `SessionResponse`: `session_id: str`, `name: str | None`, `created_at: datetime`, `status: str`
  - [x] `SessionListResponse`: `sessions: list[SessionResponse]`
  - [x] `ErrorResponse`: `error: str`, `detail: str`, `code: str`
  - [x] `HealthResponse`: `status: str`
  - [x] Alle Datetimes immer UTC (`datetime.timezone.utc`)

- [x] **T5 — Session-Repository** (AC: 2–5)
  - [x] `src/gysi_ml/persistence/session_repository.py`
  - [x] `create_session(name: str | None) -> dict`
  - [x] `get_session(session_id: str) -> dict | None`
  - [x] `list_sessions() -> list[dict]`
  - [x] `close_session(session_id: str) -> dict | None` (setzt status → "closed")
  - [x] Alle Queries ausschließlich als Parameterized Queries (`?`-Platzhalter) — kein f-String-SQL

- [x] **T6 — API Endpoints** (AC: 1–7)
  - [x] `src/gysi_ml/api/routes/sessions.py`: APIRouter mit prefix `/v1`
  - [x] `src/gysi_ml/api/routes/health.py`: `GET /v1/health`
  - [x] `src/gysi_ml/api/app.py`: FastAPI-App-Factory, registriert alle Router, startup-Hook für `create_all_tables()`
  - [x] HTTP-Statuscodes: `POST /sessions` → 201, alle anderen → 200, Not Found → 404, Validation → 422
  - [x] 404-Handler gibt `ErrorResponse` zurück (kein Pydantic-Standard-Fehler-Format)

- [x] **T7 — Entry Point** (AC: 9)
  - [x] `src/gysi_ml/main.py`: `uvicorn.run(create_app(), ...)` mit Settings aus config.py
  - [x] `scripts/run_dev.sh`: `uv run python -m gysi_ml.main`

- [x] **T8 — Unit Tests** (AC: 10)
  - [x] `tests/unit/test_session_repository.py`: alle Repository-Methoden mit In-Memory-SQLite (`:memory:`)
  - [x] `tests/unit/test_schemas.py`: Validierungsfehler bei ungültigen Inputs

- [x] **T9 — Integration Tests** (AC: 1–7, 10)
  - [x] `tests/integration/test_sessions_api.py`: FastAPI `TestClient` (httpx)
  - [x] Testfälle: Health, CRUD Happy Path, 404, 422, Soft-Delete
  - [x] Fixture: frische In-Memory-DB pro Test (kein globaler State, NFR-T4)

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

### Senior Developer Review (AI)

**Review Datum:** 2026-03-15
**Reviewer:** Amelia (Developer Agent)
**Outcome:** Changes Requested → Fixed

#### Action Items

- [x] **[High]** M1: Return-Typ `-> SessionResponse` in `get_session` und `close_session`-Routen korrekt als `Union[SessionResponse, JSONResponse]` deklariert; `responses={404: {"model": ErrorResponse}}` zu Dekoratoren hinzugefügt. [sessions.py]
- [x] **[Medium]** M2: Ungenutzter Import `create_all_tables` aus `session_repository.py` entfernt. [session_repository.py]
- [x] **[Medium]** M3: Ungenutzter `import sqlite3` aus `test_session_repository.py` entfernt. [test_session_repository.py]
- [x] **[Medium]** M4: Test `test_generic_404_handler` für generischen 404-Handler hinzugefügt — deckt jetzt `app.py:30` ab (vorher missed). [test_sessions_api.py]
- [x] **[Medium]** M5: Redundanter `get_session()`-Aufruf in `close_session`-Route entfernt; `rowcount`-Optimierung in `session_repository.close_session` ergänzt. [sessions.py, session_repository.py]
- [x] **[Low]** L2: `.coverage` und `htmlcov/` zur `.gitignore` hinzugefügt. [.gitignore]

**Post-Fix Ergebnis:** 36/36 Tests ✅ | Coverage 93% | app.py 100%

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

- `POST /v1/sessions` ohne Body → 422: Body-Parameter auf `Optional[SessionCreateRequest] = Body(default=None)` umgestellt.
- `on_event("startup")` deprecated: auf `lifespan`-Contextmanager (FastAPI ≥ 0.110) migriert.
- `ModuleNotFoundError: No module named 'gysi_ml'`: `pyproject.toml` erstellt + `pip install -e .` ausgeführt (kein uv im PATH).

### Completion Notes List

- T1: `requirements.txt`, `requirements-dev.txt`, `.env.example` befüllt; `pip install -r requirements-dev.txt` erfolgreich.
- T2: `config.py` mit `pydantic-settings` `BaseSettings`; `get_settings()` mit `@lru_cache`.
- T3: `database.py` (Connection Factory mit `row_factory`), `schema.py` (alle 4 Tabellen per `executescript`), Auto-Mkdir.
- T4: Alle 5 Pydantic-v2-Schemas mit `ConfigDict`; datetimes UTC.
- T5: `session_repository.py` — alle 4 CRUD-Methoden, ausschließlich Parameterized Queries (`?`).
- T6: `health.py`, `sessions.py` (Router), `app.py` (Factory mit lifespan + 404-Handler); Body optional.
- T7: `main.py` Entry Point, `scripts/run_dev.sh`.
- T8: 11 Unit-Tests (repository) + 12 Unit-Tests (schemas).
- T9: 12 Integrationstests, frische DB-Fixture per `tmp_path`.
- Ergebnis: **35/35 Tests grün, Coverage 93%** (Ziel ≥85% ✅).

### File List

- `backend/pyproject.toml` — NEU (Packaging, pytest-Konfiguration)
- `backend/requirements.txt` — GEÄNDERT
- `backend/requirements-dev.txt` — GEÄNDERT
- `backend/.env.example` — GEÄNDERT
- `backend/src/gysi_ml/config.py` — NEU
- `backend/src/gysi_ml/main.py` — NEU
- `backend/src/gysi_ml/api/app.py` — NEU
- `backend/src/gysi_ml/api/schemas.py` — NEU
- `backend/src/gysi_ml/api/routes/__init__.py` — NEU
- `backend/src/gysi_ml/api/routes/health.py` — NEU
- `backend/src/gysi_ml/api/routes/sessions.py` — NEU
- `backend/src/gysi_ml/persistence/database.py` — NEU
- `backend/src/gysi_ml/persistence/schema.py` — NEU
- `backend/src/gysi_ml/persistence/session_repository.py` — NEU
- `backend/scripts/run_dev.sh` — NEU
- `backend/tests/unit/test_session_repository.py` — NEU
- `backend/tests/unit/test_schemas.py` — NEU
- `backend/tests/integration/test_sessions_api.py` — NEU
