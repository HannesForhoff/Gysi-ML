# Story 1.2: Step-Registry und Pipeline-Executor mit Spec-Validierung

Status: ready-for-dev

## Story

Als ein Entwickler,
möchte ich neue Preprocessing-Steps über einen `@register_step`-Decorator registrieren können und eine JSON-Spec über den Executor ausführen lassen,
damit das System erweiterbar bleibt (Open/Closed-Prinzip) und jede Ausführung auf einer validierten, versionierten Spec basiert.

## Acceptance Criteria

1. **[Registry]** Eine Python-Klasse mit `@register_step("step_type")` ist nach dem Service-Start unter dem registrierten Typ in der Registry verfügbar.

2. **[Executor — gültige Spec]** Der Executor validiert eine gültige Pipeline-Spec gegen das JSON-Schema (alle Step-Typen bekannt, Pflichtfelder vorhanden) und führt die Steps sequenziell in der definierten Reihenfolge aus.

3. **[Executor — unbekannter Step-Typ]** Bei einem unbekannten Step-Typ gibt der Executor einen strukturierten Fehler zurück (`{"error": "unknown_step_type", ...}`) — kein Absturz.

4. **[Run-Persistenz — completed]** Nach erfolgreicher Ausführung wird ein Run-Eintrag in SQLite `runs` mit `status: "completed"`, `spec_version`, `started_at`, `finished_at` angelegt und die Spec in `spec_versions` als `v1` gespeichert.

5. **[Run-Persistenz — failed]** Bei Exception in einem Step wird der Run mit `status: "failed"` und `error_message` persistiert. Kein Halb-State in SQLite (atomare Transaktion, NFR-R3).

6. **[HTTP-Endpunkt]** `POST /v1/sessions/{session_id}/execute` mit einem Spec-JSON im Body führt die Spec aus und gibt `{"run_id": "...", "status": "completed", "result": {...}}` mit HTTP 200 zurück (oder 4xx bei Fehler).

7. **[HTTP — Session nicht gefunden]** `POST /v1/sessions/{session_id}/execute` mit unbekannter Session-ID gibt HTTP 404 zurück.

8. **[HTTP — Session geschlossen]** `POST /v1/sessions/{session_id}/execute` auf einer geschlossenen Session gibt HTTP 409 zurück.

9. **[Test-Coverage]** `pytest --cov=src/gysi_ml` ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [ ] **T1 — Abhängigkeiten ergänzen** (AC: 9)
  - [ ] `requirements.txt`: `jsonschema>=4.0` hinzufügen
  - [ ] `uv pip install -r requirements-dev.txt`

- [ ] **T2 — BaseStep ABC** (AC: 1, 2)
  - [ ] `src/gysi_ml/steps/base.py` anlegen
  - [ ] `BaseStep` als `ABC` mit abstrakten Methoden `fit(df_train: pd.DataFrame) -> None` und `transform(df_train: pd.DataFrame, df_test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`
  - [ ] Optionale Methode `get_metadata() -> dict` (gibt leeres Dict zurück, Steps können überschreiben)
  - [ ] Optionales `description: str`-Klassenattribut für Capabilities-Endpunkt (Story 1.6)
  - [ ] Optionales `param_schema: dict`-Klassenattribut (JSON-Schema der `params`) für Capabilities-Endpunkt

- [ ] **T3 — Step-Registry** (AC: 1, 3)
  - [ ] `src/gysi_ml/steps/registry.py` anlegen
  - [ ] `_registry: dict[str, type[BaseStep]] = {}` als Modul-Level-Dict
  - [ ] `register_step(step_type: str)` als Decorator-Factory: registriert die Klasse unter `step_type`
  - [ ] `get_step_class(step_type: str) -> type[BaseStep]` — wirft `KeyError` bei unbekanntem Typ
  - [ ] `list_step_types() -> list[str]` — gibt alle registrierten Typen zurück
  - [ ] `get_all_steps() -> dict[str, type[BaseStep]]` — für Capabilities-Endpunkt (Story 1.6)

- [ ] **T4 — Pipeline-Spec JSON-Schema** (AC: 2, 3)
  - [ ] `src/gysi_ml/spec/schema.py` anlegen
  - [ ] `PIPELINE_SPEC_SCHEMA`: JSON-Schema (dict) das eine Spec validiert:
    ```json
    {
      "type": "object",
      "required": ["steps"],
      "properties": {
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["type"],
            "properties": {
              "type": {"type": "string"},
              "params": {"type": "object"},
              "enabled": {"type": "boolean", "default": true}
            }
          }
        }
      }
    }
    ```
  - [ ] `validate_spec(spec: dict) -> None` — wirft `jsonschema.ValidationError` bei ungültigem Schema

- [ ] **T5 — Pipeline-Context** (AC: 2)
  - [ ] `src/gysi_ml/executor/pipeline_context.py` anlegen
  - [ ] `PipelineContext` als Dataclass:
    - `df_full: pd.DataFrame` — Original-Datensatz
    - `df_train: pd.DataFrame | None = None` — nach Split
    - `df_test: pd.DataFrame | None = None` — nach Split
    - `step_results: list[dict] = field(default_factory=list)` — Ergebnisse je Step
    - `is_split: bool = False`
  - [ ] Methode `add_step_result(step_type: str, metadata: dict) -> None`

- [ ] **T6 — Executor** (AC: 2, 3, 4, 5)
  - [ ] `src/gysi_ml/executor/executor.py` anlegen
  - [ ] `class PipelineExecutor`
  - [ ] `execute(spec: dict, session_id: str, db_path: str) -> dict`:
    1. `validate_spec(spec)` — bei Fehler: `{"error": "invalid_spec", ...}`
    2. `run_id` generieren (UUID4)
    3. Run in SQLite als `status: "running"` anlegen (atomar)
    4. Datensatz laden: `../data/raw/bikes.csv` (Pfad aus Settings)
    5. `PipelineContext` mit `df_full` initialisieren
    6. Steps sequenziell durchlaufen:
       - Step `enabled: false` → überspringen (für Story 4.2)
       - `get_step_class(step["type"])` — bei `KeyError`: Run auf `failed` setzen, `{"error": "unknown_step_type", ...}` zurückgeben
       - Step instanziieren mit `params` (oder leerem Dict)
       - `step.fit(...)` und `step.transform(...)` aufrufen (Details je nach Split-Status)
       - `context.add_step_result(...)`
    7. Run auf `status: "completed"` aktualisieren (atomar)
    8. Spec in `spec_versions` als `"v1"` speichern
    9. Ergebnis-Dict zurückgeben
  - [ ] Bei jeder Exception: Run auf `status: "failed"` mit `error_message` setzen (atomar — kein Halb-State)

- [ ] **T7 — Run-Repository** (AC: 4, 5)
  - [ ] `src/gysi_ml/persistence/run_repository.py` anlegen
  - [ ] `create_run(session_id, run_id, spec_version, status, started_at) -> None`
  - [ ] `update_run_status(run_id, status, finished_at, error_message, result_json) -> None`
  - [ ] `save_spec_version(spec_id, session_id, version, spec_json, created_at) -> None`
  - [ ] Alle Queries parameterized (`?`-Platzhalter)

- [ ] **T8 — Pydantic Schemas ergänzen** (AC: 6, 7, 8)
  - [ ] `api/schemas.py`: `ExecuteRequest(spec: dict)`, `ExecuteResponse(run_id, status, result)`
  - [ ] `ErrorResponse` aus Story 1.1 wiederverwenden

- [ ] **T9 — Execute-Endpunkt** (AC: 6, 7, 8)
  - [ ] `src/gysi_ml/api/routes/execute.py`: `POST /v1/sessions/{session_id}/execute`
  - [ ] Handler prüft: Session existiert → 404, Session aktiv → 409 wenn closed, dann Executor aufrufen
  - [ ] Router in `api/app.py` registrieren

- [ ] **T10 — Datensatz-Loader** (AC: 2)
  - [ ] `src/gysi_ml/utils/data_loader.py`: `load_bikes_dataset(path: str) -> pd.DataFrame`
  - [ ] Liest `bikes.csv` (Komma-separiert, Header in Zeile 0)
  - [ ] Pfad aus Settings (`Settings.data_path`, Default: `"../data/raw/bikes.csv"`)

- [ ] **T11 — Unit Tests** (AC: 9)
  - [ ] `tests/unit/test_registry.py`: Register/Retrieve, unbekannter Typ
  - [ ] `tests/unit/test_spec_schema.py`: gültige und ungültige Specs
  - [ ] `tests/unit/test_executor.py`: Executor mit Dummy-Steps (In-Memory-SQLite)

- [ ] **T12 — Integration Tests** (AC: 6, 7, 8, 9)
  - [ ] `tests/integration/test_execute_api.py`: Happy Path, 404, 409

## Dev Notes

### Zielstruktur nach dieser Story

```
backend/src/gysi_ml/
├── config.py                        # + data_path: str
├── steps/
│   ├── base.py                      # NEU: BaseStep ABC
│   └── registry.py                  # NEU: @register_step, get_step_class
├── spec/
│   └── schema.py                    # NEU: PIPELINE_SPEC_SCHEMA, validate_spec
├── executor/
│   ├── pipeline_context.py          # NEU: PipelineContext Dataclass
│   └── executor.py                  # NEU: PipelineExecutor
├── persistence/
│   └── run_repository.py            # NEU: Run- und Spec-Persistenz
├── utils/
│   └── data_loader.py               # NEU: load_bikes_dataset
└── api/
    ├── schemas.py                   # + ExecuteRequest, ExecuteResponse
    └── routes/
        └── execute.py               # NEU: POST /v1/sessions/{id}/execute
```

### Datensatz-Details (bikes.csv)

- Pfad: `../data/raw/bikes.csv` (relativ vom `backend/`-Verzeichnis)
- Trennzeichen: Komma
- 17.379 Zeilen, ~16 Features
- Zielvariable für spätere Stories: `cnt` (Gesamtanzahl Fahrradverleihungen)
- Datumsspalte: `dteday` (ISO-Format, z.B. `"2011-01-01"`)

### Step-Ausführungs-Semantik im Executor (fit/transform-Grenze)

Vor dem Split-Step (noch kein Train/Test vorhanden):
- Steps die auf dem vollen Datensatz arbeiten (z.B. `dedup`) rufen `step.fit(context.df_full)` und dann `step.transform(context.df_full, context.df_full)` auf — das erste Ergebnis-df wird als neues `df_full` gesetzt
- Für Steps die fit/transform benötigen MUSS ein Split vorangehen → Executor wirft Fehler (Story 1.5 implementiert die Prüfung)

Nach dem Split-Step (`context.is_split == True`):
- `step.fit(context.df_train)`
- `context.df_train, context.df_test = step.transform(context.df_train, context.df_test)`

> ⚠️ Diese Semantik wird ab Story 1.3 relevant. Story 1.2 implementiert nur die Infrastruktur, Tests können mit Dummy-Steps (die nichts verändern) arbeiten.

### Spec-Format (Referenz für alle weiteren Stories)

```json
{
  "steps": [
    {"type": "dedup", "params": {}, "enabled": true},
    {"type": "impute_missing", "params": {"strategy": "median"}, "enabled": true},
    {"type": "split", "params": {"test_size": 0.2, "random_state": 42}, "enabled": true}
  ]
}
```

### Atomare SQLite-Transaktionen (NFR-R3)

```python
conn = get_connection(db_path)
try:
    with conn:  # context manager: commit bei Erfolg, rollback bei Exception
        conn.execute("INSERT INTO runs ...", (...))
except Exception as e:
    # Rollback erfolgt automatisch durch context manager
    raise
```

### Dummy-Step für Tests

```python
from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step

@register_step("dummy")
class DummyStep(BaseStep):
    description = "Test step"
    param_schema = {}
    
    def fit(self, df_train):
        pass
    
    def transform(self, df_train, df_test):
        return df_train, df_test
```

### Abhängigkeiten (ergänzt)

| Paket | Version | Verwendung |
|---|---|---|
| pandas | ≥ 2.0 | DataFrame-Operationen |
| jsonschema | ≥ 4.0 | Spec-Validierung |

> `pandas` muss ebenfalls in `requirements.txt` eingetragen werden.

### Nicht in Scope dieser Story

- Echte Preprocessing-Steps (Stories 1.3–1.4)
- Split-Step (Story 1.5)
- Capabilities-Endpunkt (Story 1.6)
- LLM-getriggerte Execution (Story 3)

### Referenzen

- [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 1.2]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#NFR-M1, NFR-M2, NFR-R3, NFR-S1]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#FR12, FR35]
- [Source: backend/AGENTS.md#Architektur-Schichten]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

### File List
