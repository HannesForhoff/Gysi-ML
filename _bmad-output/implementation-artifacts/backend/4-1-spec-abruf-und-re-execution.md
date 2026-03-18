# Story 4.1: Spec-Abruf und Re-Execution

Status: review

## Story

Als ein Datenwissenschaftler,
möchte ich eine gespeicherte Pipeline-Spec-Version abrufen und identisch erneut ausführen können,
damit ich frühere Experimente exakt reproduzieren und mit neuen Runs vergleichen kann.

## Acceptance Criteria

1. **[GET /spec — aktuelle Version]** `GET /v1/sessions/{session_id}/spec` gibt die neueste Spec der Session zurück als JSON mit `spec_id`, `session_id`, `version`, `spec` (geparst, nicht als String), `created_at`. HTTP 404 wenn keine Spec vorhanden.

2. **[GET /spec/{version} — spezifische Version]** `GET /v1/sessions/{session_id}/spec/{version}` gibt exakt die Spec-Version zurück (z.B. `"v1"`). HTTP 404 wenn Version nicht existiert. Struktur identisch zu AC1.

3. **[Re-Execution via /messages]** Wenn der Nutzer per `/messages` eine Anfrage wie `"Führe Spec v1 erneut aus"` sendet, erkennt das LLM (via System-Prompt) dies und antwortet mit `spec_version: "v1"` im JSON. Der `message_service` lädt die Spec aus der DB (per `spec_repository`), erstellt keinen neuen Spec-Eintrag, und ruft den Executor mit der bestehenden `spec_id` auf.

4. **[Reproduzierbarkeit]** Der neue Run aus Re-Execution liefert identische Ergebnisse wie der originale Run (bei gleichem Datensatz und `random_state=42`). Im Run-Eintrag in SQLite zeigt `spec_version: "v1"` und `spec_id` referenziert die originale `spec_versions`-Zeile.

5. **[404 bei unbekannter Version]** `GET /v1/sessions/{session_id}/spec/{version}` mit einer nicht vorhandenen Version (z.B. `"v99"`) gibt HTTP 404 zurück: `{"error": "spec_version_not_found", "detail": "...", "code": "SPEC_VERSION_NOT_FOUND"}`.

6. **[Keine Regression]** Alle bestehenden Tests (Stories 1.1–3.3) bleiben grün.

7. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — `persistence/spec_repository.py` anlegen** (AC: 1, 2, 3, 4)
  - [x] Datei: `src/gysi_ml/persistence/spec_repository.py`
  - [x] `get_latest_spec(session_id: str, db_path: str | None = None) -> dict | None`
    - `SELECT * FROM spec_versions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1`
    - Gibt `spec_json` als geparsten `dict` zurück (key: `spec`), nicht als String
    - Gibt `None` zurück wenn keine Spec für Session vorhanden
  - [x] `get_spec_by_version(session_id: str, version: str, db_path: str | None = None) -> dict | None`
    - `SELECT * FROM spec_versions WHERE session_id = ? AND version = ?`
    - Gibt `spec_json` als geparsten `dict` zurück (key: `spec`)
    - Gibt `None` zurück wenn nicht gefunden
  - [x] Muster exakt wie `session_repository.py`: `get_connection(db_path)`, Parameterized Queries, `conn.close()` in `finally`
  - [x] `row_factory = sqlite3.Row` wird über `get_connection()` bereits gesetzt  → `dict(row)` reicht

- [x] **T2 — Pydantic-Schemas erweitern** (AC: 1, 2)
  - [x] Datei: `src/gysi_ml/api/schemas.py`
  - [x] Klasse `SpecVersionResponse` hinzufügen:
    ```python
    class SpecVersionResponse(BaseModel):
        spec_id: str
        session_id: str
        version: str
        spec: dict
        created_at: str
    ```
  - [x] Keine Änderung an bestehenden Klassen — nur ergänzen

- [x] **T3 — Route `api/routes/specs.py` anlegen** (AC: 1, 2, 5)
  - [x] Datei: `src/gysi_ml/api/routes/specs.py`
  - [x] `router = APIRouter(prefix="/v1")`
  - [x] `_get_db_path(request)` — Muster identisch zu `runs.py` und `sessions.py`
  - [x] `GET /sessions/{session_id}/spec` → `get_latest_spec()`
    - 404 mit `{"error": "spec_not_found", ..., "code": "SPEC_NOT_FOUND"}` wenn `None`
  - [x] `GET /sessions/{session_id}/spec/{version}` → `get_spec_by_version()`
    - 404 mit `{"error": "spec_version_not_found", ..., "code": "SPEC_VERSION_NOT_FOUND"}` wenn `None`
  - [x] Beide Endpunkte geben `SpecVersionResponse` zurück

- [x] **T4 — Router in `app.py` registrieren** (AC: 1, 2)
  - [x] Datei: `src/gysi_ml/api/app.py`
  - [x] `from gysi_ml.api.routes.specs import router as specs_router` importieren
  - [x] `app.include_router(specs_router)` — nach dem `runs_router`-Eintrag einfügen

- [x] **T5 — LLM-Response-Schema um `spec_version` erweitern** (AC: 3)
  - [x] Datei: `src/gysi_ml/llm/response_schema.py`
  - [x] Optionales Feld `spec_version` in `LLM_RESPONSE_SCHEMA` ergänzen:
    ```python
    "spec_version": {"type": "string"}
    ```
    → in `"properties"` hinzufügen; **nicht** in `"required"` — damit bleibt es optional
  - [x] `additionalProperties: False` bleibt bestehen — `spec_version` ist nun explizit erlaubt
  - [x] Bestehende Tests bleiben grün, da `spec_version` optional ist

- [x] **T6 — System-Prompt für Re-Execution erweitern** (AC: 3)
  - [x] Datei: `src/gysi_ml/llm/prompts.py`
  - [x] Im `SYSTEM_PROMPT_TEMPLATE` (Abschnitt "Regeln für action-Wahl" oder neuer Abschnitt) hinzufügen:
    ```
    ## Re-Execution einer gespeicherten Spec

    Wenn der Nutzer eine bestehende Spec-Version erneut ausführen möchte
    (z.B. "Führe Spec v1 erneut aus", "Wiederhole Spec v2", "Re-Run von v1"):
    - Setze `action: "execute"`
    - Setze `spec_version: "<version>"` (z.B. "v1") im JSON
    - Das `spec`-Feld enthält eine leere Spec: `{"steps": []}`
    - Das System lädt die Spec automatisch aus der Datenbank
    ```

- [x] **T7 — `message_service.py` für Re-Execution erweitern** (AC: 3, 4)
  - [x] Datei: `src/gysi_ml/services/message_service.py`
  - [x] Nach `parsed = validate_llm_response(...)` prüfen ob `spec_version` gesetzt ist:
    ```python
    spec_version_ref = parsed.get("spec_version")
    ```
  - [x] Wenn `spec_version_ref` gesetzt und `action == "execute"`:
    - `from gysi_ml.persistence import spec_repository`
    - `existing_spec = spec_repository.get_spec_by_version(session_id=session_id, version=spec_version_ref, db_path=db_path)`
    - Wenn `None`: Error-Response `{"type": "error", "message": f"Spec-Version '{spec_version_ref}' nicht gefunden."}`
    - Sonst: `executor.execute_with_spec_id(spec=existing_spec["spec"], spec_id=existing_spec["spec_id"], session_id=session_id, db_path=db_path)`
  - [x] Normaler `execute`-Pfad (ohne `spec_version_ref`) bleibt unverändert

- [x] **T8 — `executor.py` um `execute_with_spec_id()` erweitern** (AC: 3, 4)
  - [x] Datei: `src/gysi_ml/executor/executor.py`
  - [x] Neue Methode `execute_with_spec_id(self, spec: dict, spec_id: str, session_id: str, db_path: str | None = None) -> dict`
    - Überspringt `save_spec_version()` (spec_id bereits vorhanden)
    - Ruft `run_repository.create_run()` mit dem bestehenden `spec_id` auf
    - Führt Pipeline-Steps aus — identischer Code-Pfad wie in `execute()`
    - Setzt `spec_version = "v1"` (wie bisher)
  - [x] Bestehende `execute()`-Methode bleibt unverändert (keine Breaking Change)
  - [x] **Code-Duplikation minimieren**: Gemeinsame Pipeline-Logik in private `_run_pipeline(spec, run_id, spec_id, session_id, db_path)` extrahieren, die von beiden Methoden aufgerufen wird

- [x] **T9 — Unit-Tests anlegen** (AC: 1–5, 7)
  - [x] `tests/unit/test_spec_repository.py`
    - `test_get_latest_spec_returns_none_when_no_specs()`
    - `test_get_latest_spec_returns_most_recent_entry()`
    - `test_get_spec_by_version_existing()`
    - `test_get_spec_by_version_not_found_returns_none()`
    - Fixtures: `tmp_path` + `create_all_tables()` (wie in `test_session_repository.py`)

- [x] **T10 — Integrationstests anlegen** (AC: 1, 2, 5, 6, 7)
  - [x] `tests/integration/test_specs_api.py`
    - Fixtures: `client` (wie in `test_sessions_api.py`), `client_with_run` (führt einen Run aus, gibt session_id + run-Objekt zurück)
    - `test_get_latest_spec_returns_404_when_no_run()` — Session ohne Run
    - `test_get_latest_spec_after_execute()` — Spec vorhanden nach Execute
    - `test_get_latest_spec_response_structure()` — alle Felder (spec_id, session_id, version, spec, created_at)
    - `test_get_spec_by_version_existing()` — `GET /v1/sessions/{id}/spec/v1`
    - `test_get_spec_by_version_not_found()` — 404 mit `"code": "SPEC_VERSION_NOT_FOUND"`

## Dev Notes

### Wichtige Architektur-Constraints

- **`spec_versions`-Tabelle** ist bereits vorhanden (angelegt seit Story 1.2) — kein Schema-Change nötig
- **Muster für Repository**: Exakt wie `session_repository.py` — `get_connection(db_path)` aus `persistence/database.py`, `conn.close()` in `finally`, Parameterized Queries (SQL-Injection-Schutz)
- **Kein `with conn:`** für SELECTs (nur für INSERT/UPDATE/DELETE im `with conn:` Context Manager)
- **`row_factory`**: Wird in `get_connection()` bereits auf `sqlite3.Row` gesetzt → `dict(row)` funktioniert direkt
- **`spec_json`-Parsing**: In Repository-Funktionen `json.loads(row["spec_json"])` einsetzen und als `"spec"` zurückgeben (nicht den Raw-String)

### Executor-Refactoring (T8)

Der aktuelle `execute()`-Code in `executor.py` enthält die gesamte Pipeline-Logik. Für `execute_with_spec_id()` muss diese **nicht dupliziert** werden. Stattdessen:

```python
def execute(self, spec: dict, session_id: str, db_path: str | None = None) -> dict:
    # Validation, spec_id/run_id generieren, save_spec_version() aufrufen
    ...
    spec_id = str(uuid.uuid4())
    run_repository.save_spec_version(...)
    return self._run_pipeline(spec=spec, spec_id=spec_id, session_id=session_id, db_path=db_path)

def execute_with_spec_id(self, spec: dict, spec_id: str, session_id: str, db_path: str | None = None) -> dict:
    # Nur Spec-Reihenfolge validieren, kein save_spec_version()
    try:
        validate_spec_order(spec.get("steps", []))
    except SpecOrderError as exc:
        return {"error": "invalid_spec_order", "detail": str(exc), "code": "INVALID_SPEC_ORDER"}
    return self._run_pipeline(spec=spec, spec_id=spec_id, session_id=session_id, db_path=db_path)

def _run_pipeline(self, spec: dict, spec_id: str, session_id: str, db_path: str | None = None) -> dict:
    # Alle bisherigen Schritte ab "run_id generieren, create_run(), Datensatz laden, Steps ausführen"
    ...
```

### LLM-Schema-Erweiterung (T5)

Die Erweiterung ist rückwärtskompatibel:
- `spec_version` ist **optional** (nicht in `"required"`)
- `additionalProperties: False` bleibt — `spec_version` ist in `properties` explizit gelistet
- Alle bestehenden LLM-Responses die kein `spec_version` haben, bleiben gültig
- `validate_llm_response()` gibt das `spec_version`-Feld in `parsed` zurück wenn vorhanden

### Kein separater `/re-execute`-Endpunkt

Re-Execution läuft ausschließlich über `POST /v1/sessions/{id}/messages` — der existierende Message-Flow wird genutzt. **Kein neuer API-Endpunkt** wird hinzugefügt.

### Dateipfade im Projekt

```text
src/gysi_ml/
├── api/
│   ├── routes/
│   │   ├── specs.py            ← NEU (T3)
│   │   └── ...
│   └── schemas.py              ← ERWEITERT (T2)
├── executor/
│   └── executor.py             ← ERWEITERT (T8)
├── llm/
│   ├── prompts.py              ← ERWEITERT (T6)
│   └── response_schema.py      ← ERWEITERT (T5)
├── persistence/
│   ├── spec_repository.py      ← NEU (T1)
│   └── ...
├── services/
│   └── message_service.py      ← ERWEITERT (T7)
└── main.py / api/app.py        ← ERWEITERT (T4)
```

### Test-Fixtures-Muster

Aus `test_sessions_api.py` und `test_runs_api.py` ableiten:

```python
@pytest.fixture
def client(tmp_path, csv_file):
    settings = Settings(db_path=str(tmp_path / "test.db"), data_path=csv_file)
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c

@pytest.fixture
def client_with_run(client):
    # Session + Execute → gibt (client, session_id, run_id) zurück
    resp = client.post("/v1/sessions", json={})
    session_id = resp.json()["session_id"]
    exec_resp = client.post(f"/v1/sessions/{session_id}/execute", json={"spec": {"steps": []}})
    run_id = exec_resp.json()["run_id"]
    return client, session_id, run_id
```

### FR-Coverage dieser Story

| FR | Beschreibung |
|---|---|
| FR13 | Gespeicherte Pipeline-Spec abrufen |
| FR14 | Pipeline-Spec erneut ausführen (Reproduzierbarkeit) |

### References

- Bestehende Repository-Muster: [src/gysi_ml/persistence/session_repository.py](src/gysi_ml/persistence/session_repository.py)
- Bestehende Route-Muster: [src/gysi_ml/api/routes/runs.py](src/gysi_ml/api/routes/runs.py)
- Schema-Tabelle: [src/gysi_ml/persistence/schema.py](src/gysi_ml/persistence/schema.py)
- Executor (zu refactoren): [src/gysi_ml/executor/executor.py](src/gysi_ml/executor/executor.py)
- LLM Response Schema: [src/gysi_ml/llm/response_schema.py](src/gysi_ml/llm/response_schema.py)
- System Prompt: [src/gysi_ml/llm/prompts.py](src/gysi_ml/llm/prompts.py)
- Message Service: [src/gysi_ml/services/message_service.py](src/gysi_ml/services/message_service.py)
- App-Registrierung: [src/gysi_ml/api/app.py](src/gysi_ml/api/app.py)
- Test-Fixtures aus: [tests/integration/test_sessions_api.py](tests/integration/test_sessions_api.py), [tests/integration/test_runs_api.py](tests/integration/test_runs_api.py)
- Epics: [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 4.1]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fix: `SYSTEM_PROMPT_TEMPLATE` Format-String-Escaping — `{"steps": []}` → `{{"steps": []}}` um `KeyError` in `.format()` zu vermeiden

### Completion Notes List

- T1: `spec_repository.py` — `get_latest_spec()` + `get_spec_by_version()` nach `session_repository.py`-Muster
- T2: `SpecVersionResponse` Pydantic-Schema ergänzt
- T3: `routes/specs.py` — 2 GET-Endpunkte mit 404-Handling
- T4: `specs_router` in `app.py` nach `runs_router` registriert
- T5: `spec_version` als optionales Feld in `LLM_RESPONSE_SCHEMA` ergänzt
- T6: Re-Execution-Abschnitt im System-Prompt mit `{{`-Escaping
- T7: `message_service.py` — `spec_version_ref`-Branch ruft `execute_with_spec_id()` auf
- T8: Executor-Refactoring — `_run_pipeline()` extrahiert, `execute_with_spec_id()` neu
- T9: 4 Unit-Tests für `spec_repository`
- T10: 5 Integrationstests für Spec-API-Endpunkte
- Alle 386 Tests grün (377 bestehend + 9 neu), 100% Coverage auf neuen Modulen

### File List

- `src/gysi_ml/persistence/spec_repository.py` — NEU
- `src/gysi_ml/api/routes/specs.py` — NEU
- `src/gysi_ml/api/schemas.py` — `SpecVersionResponse` ergänzt
- `src/gysi_ml/api/app.py` — `specs_router` registriert
- `src/gysi_ml/llm/response_schema.py` — `spec_version` in `LLM_RESPONSE_SCHEMA`
- `src/gysi_ml/llm/prompts.py` — Re-Execution-Abschnitt im System-Prompt
- `src/gysi_ml/services/message_service.py` — Re-Execution-Branch
- `src/gysi_ml/executor/executor.py` — `execute_with_spec_id()` + `_run_pipeline()`
- `tests/unit/test_spec_repository.py` — NEU
- `tests/integration/test_specs_api.py` — NEU
