# Story 4.2: Parameter-Anpassung per Sprache und Step-Deaktivierung

Status: done

## Story

Als ein Datenwissenschaftler,
möchte ich Parameter einer bestehenden Pipeline-Spec per natürlicher Sprache anpassen und einzelne Steps deaktivieren können,
damit ich schnell Variationen ausprobieren kann ohne eine komplett neue Pipeline zu definieren.

## Acceptance Criteria

1. **[Neue Spec-Version via Parameteranpassung]** Wenn der Nutzer sendet `"Setze die Imputationsstrategie auf mean"`, erzeugt das LLM `action: "modify_spec"` mit dem vollständigen neuen Spec-JSON. Das System speichert diesen als neue Versionsnummer (v1 → v2) in `spec_versions`. Die alte Version `v1` bleibt unverändert in SQLite (Audit-Trail). Die API gibt `{"type": "spec_updated", "spec_id": "...", "version": "v2", "spec": {...}, "explanation": "..."}` zurück.

2. **[Step-Deaktivierung via Sprache]** Wenn der Nutzer sendet `"Deaktiviere den Outlier-Handling-Step"`, erzeugt das LLM `action: "modify_spec"` mit einem vollständigen Spec, in dem der betreffende Step `"enabled": false` enthält. Das System speichert diesen als neue Spec-Version. Die Antwort hat `type: "spec_updated"`.

3. **[Executor überspringt disabled Steps]** Wenn eine Spec mit `"enabled": false`-Steps ausgeführt wird, überspringt der Executor diese Steps ohne Fehler. (**Hinweis:** Bereits implementiert in `executor.py` via `if not enabled: continue` — kein Code-Änderung nötig.)

4. **[GET /spec zeigt enabled-Feld]** `GET /v1/sessions/{id}/spec` und `GET /v1/sessions/{id}/spec/{version}` geben `"enabled": false` für deaktivierte Steps in der `spec`-Property zurück. Deaktivierte Steps sind explizit aufgeführt (nicht gefiltert).

5. **[Korrekte Versionsnummern]** `executor.execute()` (neue Ausführung aus Spracheingabe) nutzt jetzt `spec_repository.create_spec_version()` für automatische Versionsnummervergabe. Erste Ausführung in einer Session: `"v1"`. Jede `modify_spec`-Operation erhöht die Versionsnummer um 1 (v1 → v2 → v3 ...). Re-Execution via `execute_with_spec_id()` (aus Story 4.1) erzeugt keine neue Version.

6. **[Ungültige Spec wird abgelehnt]** Wenn das LLM eine `modify_spec`-Antwort liefert die gegen `PIPELINE_SPEC_SCHEMA` (jsonschema) verstößt, gibt das System einen strukturierten Fehler zurück und legt **keine** neue Spec-Version an.

7. **[LLM kennt aktuellen Spec-Kontext]** Das LLM erhält die aktuelle (neueste) Spec der Session als Teil seines System-Prompts, damit es sinnvoll modifizieren kann (statt eine neue Spec von Grund auf zu bauen).

8. **[Keine Regression]** Alle bestehenden Tests (Stories 1.1–4.1) bleiben grün.

9. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten/geänderten Module.

## Tasks / Subtasks

- [x] **T1 — `persistence/spec_repository.py` erweitern** (AC: 1, 2, 5)
  - [x] Datei: `src/gysi_ml/persistence/spec_repository.py` (aus Story 4.1)
  - [x] `create_spec_version(session_id: str, spec: dict, db_path: str | None = None) -> dict`
    - Ermittelt die nächste Versionsnummer:
      ```sql
      SELECT version FROM spec_versions
      WHERE session_id = ?
      ORDER BY created_at DESC LIMIT 1
      ```
      → Parse z.B. `"v2"` → `2` → nächste wäre `"v3"`. Falls keine Zeile: → `"v1"`.
    - Generiert neue `spec_id = str(uuid.uuid4())`, `created_at = datetime.now(timezone.utc).isoformat()`
    - INSERT mit `json.dumps(spec)` als `spec_json`
    - Gibt zurück: `{"spec_id", "session_id", "version", "spec": <geparster dict>, "created_at"}`
    - Parameterized Queries, `conn.close()` in `finally`
  - [x] Muster exakt wie bestehende Funktionen in `spec_repository.py` (aus Story 4.1)

- [x] **T2 — `executor.execute()` auf `create_spec_version()` umstellen** (AC: 5)
  - [x] Datei: `src/gysi_ml/executor/executor.py`
  - [x] In `execute()` (bzw. dem neuen `_run_pipeline()` aus Story 4.1) `run_repository.save_spec_version()` ersetzen durch:
    ```python
    from gysi_ml.persistence import spec_repository
    spec_entry = spec_repository.create_spec_version(
        session_id=session_id, spec=spec, db_path=db_path
    )
    spec_id = spec_entry["spec_id"]
    spec_version = spec_entry["version"]
    ```
  - [x] `run_repository.create_run()` bekommt `spec_version=spec_entry["version"]` (statt hartkodiertem `"v1"`)
  - [x] `execute_with_spec_id()` (aus Story 4.1) bleibt unverändert — erzeugt keine neue Version
  - [x] **Breaking-Change-Prüfung**: Bestehende Unit-Tests die `spec_version == "v1"` prüfen, bleiben grün weil erste Ausführung in einer Session weiterhin `"v1"` ergibt

- [x] **T3 — LLM-Response-Schema: `modify_spec`-Action** (AC: 1, 2, 6)
  - [x] Datei: `src/gysi_ml/llm/response_schema.py`
  - [x] `action`-Enum um `"modify_spec"` erweitern:
    ```python
    "action": {"type": "string", "enum": ["execute", "propose", "modify_spec"]},
    ```
  - [x] Optionales Feld `base_spec_version` in properties ergänzen (bereits `additionalProperties: False` → muss explizit gelistet sein):
    ```python
    "base_spec_version": {"type": "string"}
    ```
  - [x] `"base_spec_version"` **nicht** in `"required"` — optional
  - [x] Alle bestehenden Tests bleiben grün (bestehende Actions weiterhin gültig)

- [x] **T4 — System-Prompt um `modify_spec` und aktuellen Spec-Kontext erweitern** (AC: 7)
  - [x] Datei: `src/gysi_ml/llm/prompts.py`
  - [x] `build_system_prompt(capabilities: list[dict], current_spec: dict | None = None) -> str` — optionaler Parameter
  - [x] In `SYSTEM_PROMPT_TEMPLATE` einen Abschnitt hinzufügen:
    ```
    ## Spec-Modifikation

    Wenn der Nutzer eine bestehende Pipeline-Spec modifizieren möchte
    (Parameter ändern, Step deaktivieren, Step-Reihenfolge anpassen):
    - Setze `action: "modify_spec"`
    - Das `spec`-Feld enthält die vollständige neue Spec (nicht nur die Änderung!)
    - Das `base_spec_version`-Feld (optional) enthält die Version der Ausgangs-Spec (z.B. "v1")
    - Deaktiviere Steps mit `"enabled": false` — nicht mit Löschen des Steps!
    
    Beispiele:
    - "Setze Imputationsstrategie auf mean" → modify_spec (vollständige neue Spec mit geändertem param)
    - "Deaktiviere den Outlier-Handling-Step" → modify_spec (Step mit "enabled": false)
    - "Füge Correlation-Filter hinzu" → modify_spec (neuer Step in der Spec)
    ```
  - [x] Wenn `current_spec is not None`, dynamisch einfügen:
    ```
    ## Aktuelle Session-Spec (Ausgangs-Spec für Modifikationen)
    
    {current_spec_json}
    ```
  - [x] `build_system_prompt()` muss **rückwärtskompatibel** bleiben — `current_spec=None` erzeugt identischen Output wie bisher (für alle Tests)

- [x] **T5 — `message_service.py`: mod_spec-Handling** (AC: 1, 2, 6, 7)
  - [x] Datei: `src/gysi_ml/services/message_service.py`
  - [x] Vor dem LLM-Aufruf: aktuelle Spec laden und an `build_system_prompt()` übergeben:
    ```python
    from gysi_ml.persistence import spec_repository
    current_spec_entry = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
    current_spec = current_spec_entry["spec"] if current_spec_entry else None
    system_prompt = build_system_prompt(capabilities, current_spec=current_spec)
    ```
  - [x] Nach `parsed = validate_llm_response(...)`: Check auf `action == "modify_spec"`:
    ```python
    if action == "modify_spec":
        # 1. neue Spec validieren
        try:
            validate_spec(spec)
        except jsonschema.ValidationError as exc:
            return {"type": "error", "message": f"Ungültige Spec: {exc.message}"}
        # 2. Spec-Reihenfolge validieren
        try:
            validate_spec_order(spec.get("steps", []))
        except SpecOrderError as exc:
            return {"type": "error", "message": str(exc)}
        # 3. Neue Spec-Version anlegen
        spec_entry = spec_repository.create_spec_version(
            session_id=session_id, spec=spec, db_path=db_path
        )
        return {
            "type": "spec_updated",
            "spec_id": spec_entry["spec_id"],
            "version": spec_entry["version"],
            "spec": spec_entry["spec"],
            "explanation": explanation,
        }
    ```
  - [x] Imports ergänzen: `import jsonschema`, `from gysi_ml.spec.schema import validate_spec`, `from gysi_ml.executor.spec_validator import SpecOrderError, validate_spec_order`

- [x] **T6 — Pydantic-Schemas erweitern** (AC: 1, 2)
  - [x] Datei: `src/gysi_ml/api/schemas.py`
  - [x] `MessageResponse` erhält optionale Felder:
    ```python
    spec_id: Optional[str] = None
    version: Optional[str] = None
    spec: Optional[dict] = None
    ```
  - [x] Keine bestehenden Felder ändern — nur ergänzen

- [x] **T7 — Unit-Tests: `spec_repository.py`** (Story-4.1-Datei erweitern) (AC: 5, 9)
  - [x] Datei: `tests/unit/test_spec_repository.py` (aus Story 4.1)
  - [x] `test_create_spec_version_first_returns_v1()` — erste Version einer Session = "v1"
  - [x] `test_create_spec_version_increments_to_v2()` — zweite Version = "v2"
  - [x] `test_create_spec_version_returns_parsed_spec()` — `spec`-Feld ist dict, nicht String
  - [x] `test_create_spec_version_old_version_preserved()` — v1 ist nach v2-Anlage noch abfragbar

- [x] **T8 — Unit-Tests: `llm/response_schema.py`** (AC: 3, 6, 9)
  - [x] Datei: `tests/unit/llm/test_response_schema.py` (bereits vorhanden aus Story 3.2)
  - [x] `test_modify_spec_action_is_valid()` — `action: "modify_spec"` passiert Schema-Validierung
  - [x] `test_modify_spec_with_base_spec_version()` — optionales Feld `base_spec_version` erlaubt
  - [x] `test_invalid_action_rejected()` — neue ungültige Action schlägt fehl

- [x] **T9 — Integration-Tests** (AC: 1, 2, 4, 5, 8, 9)
  - [x] Datei: `tests/integration/test_spec_modification_api.py` (neu)
  - [x] Fixtures: `client` + `client_with_spec` (Session + Execute, gibt session_id + spec_entry zurück)
  - [x] `test_executor_creates_v1_on_first_execute()` — `spec_version == "v1"` nach erstem Execute
  - [x] `test_executor_creates_v2_on_second_execute()` — zweiter Execute → neue Session braucht v1, ABER selbe Session → v2 (Depends on versioning fix)
  - [x] `test_get_spec_shows_enabled_false()` — nach modify_spec mit `enabled: false` zeigt GET/spec den disabled Step
  - [x] `test_get_spec_v1_still_accessible_after_v2()` — Audit-Trail: v1 abrufbar nach Erstellung v2

## Dev Notes

### Abhängigkeit zu Story 4.1

**Diese Story setzt Story 4.1 als vollständig implementiert voraus.** Folgende Dateien müssen existieren:
- `src/gysi_ml/persistence/spec_repository.py` (mit `get_latest_spec()` und `get_spec_by_version()`)
- Refactored `executor.py` mit `_run_pipeline()` Methode
- `src/gysi_ml/api/routes/specs.py` (GET /spec Endpunkte)

### Versionsnummern-Logik (T1)

```python
def _next_version(session_id: str, db_path: str | None = None) -> str:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT version FROM spec_versions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return "v1"
        last_version = row["version"]  # z.B. "v2"
        num = int(last_version.lstrip("v"))
        return f"v{num + 1}"
    finally:
        conn.close()
```

### `enabled: false` ist bereits vollständig unterstützt

Der Executor in `executor.py` enthält bereits:
```python
enabled = step_spec.get("enabled", True)
if not enabled:
    continue
```

Das `PIPELINE_SPEC_SCHEMA` in `spec/schema.py` erlaubt `"enabled": {"type": "boolean", "default": True}` bereits.

**Kein Executor-Code-Change für Step-Deaktivierung nötig** — nur das LLM muss lernen `"enabled": false` zu setzen.

### `modify_spec` vs. `execute` — Response-Semantik

| action | Was passiert | Response-Type |
|---|---|---|
| `execute` | Neue Spec gespeichert + Pipeline ausgeführt | `result` |
| `propose` | Neuer Proposal angelegt, keine Ausführung | `proposal` |
| `modify_spec` | Neue Spec-Version gespeichert, keine Ausführung | `spec_updated` |

Der Nutzer erhält nach `modify_spec` den Hinweis in `explanation`, dass die Spec gespeichert wurde. Um sie auszuführen muss er explizit einen neuen Execute/Message senden.

### Rückwärtskompatibilität `build_system_prompt()`

**WICHTIG:** Der existierende Aufruf in `message_service.py` lautet:
```python
system_prompt = build_system_prompt(capabilities)
```

Nach Refactoring:
```python
system_prompt = build_system_prompt(capabilities, current_spec=current_spec)
```

Der Defaultwert `current_spec=None` sorgt dafür, dass alle bestehenden Tests die `build_system_prompt()` ohne `current_spec` aufrufen weiterhin funktionieren.

### Test-Fixture für `client_with_spec`

Wiederverwendung des Musters aus Story 4.1 / `test_runs_api.py`:

```python
@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame({
        "instant": range(1, 21),
        "cnt": range(100, 120),
        "temp": [0.5] * 20,
        "dteday": ["2012-01-01"] * 20,
    })
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)

@pytest.fixture
def client(tmp_path, csv_file):
    settings = Settings(db_path=str(tmp_path / "test.db"), data_path=csv_file)
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c

@pytest.fixture
def client_with_spec(client):
    resp = client.post("/v1/sessions", json={})
    session_id = resp.json()["session_id"]
    exec_resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": []}},
    )
    assert exec_resp.status_code == 200
    spec_resp = client.get(f"/v1/sessions/{session_id}/spec")
    return client, session_id, spec_resp.json()
```

### Dateipfade die geändert werden

```text
src/gysi_ml/
├── executor/
│   └── executor.py              ← GEÄNDERT (T2): save_spec_version → create_spec_version
├── llm/
│   ├── prompts.py               ← GEÄNDERT (T4): current_spec Parameter + modify_spec Instruktion
│   └── response_schema.py       ← GEÄNDERT (T3): modify_spec Action + base_spec_version
├── persistence/
│   └── spec_repository.py       ← ERWEITERT (T1): create_spec_version()
├── services/
│   └── message_service.py       ← GEÄNDERT (T5): current_spec Kontext + modify_spec Handling
└── api/
    └── schemas.py               ← ERWEITERT (T6): MessageResponse + spec_id/version/spec

tests/
├── unit/
│   ├── test_spec_repository.py  ← ERWEITERT (T7)
│   └── llm/
│       └── test_response_schema.py ← ERWEITERT (T8)
└── integration/
    └── test_spec_modification_api.py ← NEU (T9)
```

### FR-Coverage dieser Story

| FR | Beschreibung |
|---|---|
| FR15 | Parameter einer Pipeline-Spec per Spracheingabe anpassen (neue Version) |
| FR16 | Einzelne Steps in einer Pipeline-Spec deaktivieren |

### References

- Bestehende Spec-Repository-Funktionen (Story 4.1): [src/gysi_ml/persistence/spec_repository.py](src/gysi_ml/persistence/spec_repository.py)
- Executor (bereits `enabled`-Handling): [src/gysi_ml/executor/executor.py](src/gysi_ml/executor/executor.py)
- Spec-JSON-Schema (bereits `enabled` unterstützt): [src/gysi_ml/spec/schema.py](src/gysi_ml/spec/schema.py)
- LLM Response Schema: [src/gysi_ml/llm/response_schema.py](src/gysi_ml/llm/response_schema.py)
- System Prompt: [src/gysi_ml/llm/prompts.py](src/gysi_ml/llm/prompts.py)
- Message Service: [src/gysi_ml/services/message_service.py](src/gysi_ml/services/message_service.py)
- Spec-Order-Validator: [src/gysi_ml/executor/spec_validator.py](src/gysi_ml/executor/spec_validator.py)
- Epics: [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 4.2]
- Story 4.1 (Voraussetzung): [_bmad-output/implementation-artifacts/backend/4-1-spec-abruf-und-re-execution.md](_bmad-output/implementation-artifacts/backend/4-1-spec-abruf-und-re-execution.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Bestehende message_service Unit-Tests schlugen fehl wegen fehlender `spec_versions`-Tabelle → autouse-Fixture um `spec_repository.get_latest_spec`-Patch erweitert

### Completion Notes List

- T1: `create_spec_version()` mit automatischer Versionsnummervergabe implementiert
- T2: `executor.execute()` nutzt jetzt `spec_repository.create_spec_version()`, `_run_pipeline()` erhält dynamische `spec_version`
- T2: `execute_with_spec_id()` resolves Spec-Version aus DB bei Re-Execution
- T3: `modify_spec` als dritte gültige Action in `LLM_RESPONSE_SCHEMA`, `base_spec_version` als optionales Feld
- T4: `build_system_prompt()` mit optionalem `current_spec`-Parameter, Spec-Modifikation-Instruktionen im Template
- T5: `message_service.handle_message()` lädt aktuelle Spec vor LLM-Aufruf, handelt `modify_spec` mit Schema+Order-Validierung
- T6: `MessageResponse` um `spec_id`, `version`, `spec` erweitert
- T7: 4 neue Unit-Tests für `create_spec_version()`
- T8: 3 neue Unit-Tests für `modify_spec`-Action im Response-Schema
- T9: 4 neue Integration-Tests (Versionierung, enabled=false, Audit-Trail)

### File List

- `src/gysi_ml/persistence/spec_repository.py` — ERWEITERT (create_spec_version)
- `src/gysi_ml/executor/executor.py` — GEÄNDERT (create_spec_version statt save_spec_version, dynamische spec_version)
- `src/gysi_ml/llm/response_schema.py` — GEÄNDERT (modify_spec Action, base_spec_version)
- `src/gysi_ml/llm/prompts.py` — GEÄNDERT (current_spec Parameter, Spec-Modifikation-Instruktionen)
- `src/gysi_ml/services/message_service.py` — GEÄNDERT (current_spec Kontext, modify_spec Handling)
- `src/gysi_ml/api/schemas.py` — ERWEITERT (MessageResponse: spec_id, version, spec)
- `tests/unit/test_spec_repository.py` — ERWEITERT (4 neue Tests)
- `tests/unit/llm/test_response_schema.py` — ERWEITERT (3 neue Tests)
- `tests/unit/test_message_service.py` — GEÄNDERT (autouse Fixture: spec_repository Patch)
- `tests/integration/test_spec_modification_api.py` — NEU (4 Integration-Tests)
