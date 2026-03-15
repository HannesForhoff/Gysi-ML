# Story 1.2: Step-Registry und Pipeline-Executor mit Spec-Validierung

Status: done

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

- [x] **T1 — Abhängigkeiten ergänzen** (AC: 9)
  - [x] `requirements.txt`: `jsonschema>=4.0` hinzufügen
  - [x] `uv pip install -r requirements-dev.txt`

- [x] **T2 — BaseStep ABC** (AC: 1, 2)
  - [x] `src/gysi_ml/steps/base.py` anlegen
  - [x] `BaseStep` als `ABC` mit abstrakten Methoden `fit` und `transform`
  - [x] Optionale Methode `get_metadata() -> dict`
  - [x] Optionales `description` und `param_schema` Klassenattribut

- [x] **T3 — Step-Registry** (AC: 1, 3)
  - [x] `src/gysi_ml/steps/registry.py` anlegen
  - [x] `_registry` als Modul-Level-Dict
  - [x] `register_step()` Decorator-Factory
  - [x] `get_step_class()`, `list_step_types()`, `get_all_steps()`

- [x] **T4 — Pipeline-Spec JSON-Schema** (AC: 2, 3)
  - [x] `src/gysi_ml/spec/schema.py` anlegen
  - [x] `PIPELINE_SPEC_SCHEMA` mit `additionalProperties: false`
  - [x] `validate_spec()` — wirft `jsonschema.ValidationError`

- [x] **T5 — Pipeline-Context** (AC: 2)
  - [x] `src/gysi_ml/executor/pipeline_context.py` anlegen
  - [x] `PipelineContext` Dataclass mit allen Feldern
  - [x] `add_step_result()`

- [x] **T6 — Executor** (AC: 2, 3, 4, 5)
  - [x] `src/gysi_ml/executor/executor.py` anlegen
  - [x] `PipelineExecutor.execute()` mit vollständigem Ablauf
  - [x] Atomare SQLite-Transaktionen via `with conn:`

- [x] **T7 — Run-Repository** (AC: 4, 5)
  - [x] `src/gysi_ml/persistence/run_repository.py` anlegen
  - [x] `create_run()`, `update_run_status()`, `save_spec_version()`
  - [x] Alle Queries parameterized

- [x] **T8 — Pydantic Schemas ergänzen** (AC: 6, 7, 8)
  - [x] `ExecuteRequest` und `ExecuteResponse` in `api/schemas.py`

- [x] **T9 — Execute-Endpunkt** (AC: 6, 7, 8)
  - [x] `src/gysi_ml/api/routes/execute.py` anlegen
  - [x] 404/409-Prüfung, Executor-Aufruf
  - [x] Router in `api/app.py` registriert

- [x] **T10 — Datensatz-Loader** (AC: 2)
  - [x] `src/gysi_ml/utils/data_loader.py` anlegen
  - [x] `Settings.data_path` ergänzt

- [x] **T11 — Unit Tests** (AC: 9)
  - [x] `tests/unit/test_registry.py`
  - [x] `tests/unit/test_spec_schema.py`
  - [x] `tests/unit/test_executor.py`

- [x] **T12 — Integration Tests** (AC: 6, 7, 8, 9)
  - [x] `tests/integration/test_execute_api.py`: Happy Path, 404, 409, 422

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

- pandas und jsonschema bereits im venv vorhanden (via Notebooks) — `pip install` als no-op.
- `executor.py` lines 50-59 (data-load-Fehlerast) und 97-98 (post-Split-Ast) nicht durch Tests abgedeckt — nicht in Scope dieser Story, da keine echte bikes.csv in Tests. Coverage 95% ≥ 85% ✅.

### Completion Notes List

- T1: `requirements.txt` um `pandas>=2.0` + `jsonschema>=4.0` ergänzt.
- T2: `steps/base.py` — `BaseStep` ABC mit `fit`, `transform`, `get_metadata`, `description`, `param_schema`.
- T3: `steps/registry.py` — `@register_step`, `get_step_class`, `list_step_types`, `get_all_steps`.
- T4: `spec/schema.py` — `PIPELINE_SPEC_SCHEMA` mit `additionalProperties: false`, `validate_spec()`.
- T5: `executor/pipeline_context.py` — `PipelineContext` Dataclass.
- T6: `executor/executor.py` — `PipelineExecutor.execute()`: validate → create_run(running) → load_data → steps → update(completed/failed) → save_spec_version.
- T7: `persistence/run_repository.py` — `create_run`, `update_run_status`, `save_spec_version`, alle parameterized.
- T8: `api/schemas.py` — `ExecuteRequest` + `ExecuteResponse` ergänzt.
- T9: `api/routes/execute.py` — 404/409-Checks, Executor-Call; `app.py` + `data_path` in `app.state`.
- T10: `utils/data_loader.py` — `load_bikes_dataset()`; `config.py` + `data_path`.
- T11: 25 Unit-Tests (registry: 8, spec_schema: 10, executor: 10) — alle grün.
- T12: 6 Integrationstests (execute_api) — alle grün.
- Ergebnis: **70/70 Tests grün, Coverage 95%** ✅

**Code Review Fixes (CR):**
- M1: `from typing import Optional` entfernt; `Optional[str]` → `str | None` in `run_repository.py`
- M2: Spurious Dateien `backend/=2.0` und `backend/=4.0` gelöscht (Shell-Redirect-Artefakte)
- M3: Leeres `src/gysi_ml/spec/schema/`-Verzeichnis gelöscht (Namespace-Konflikt-Risiko)
- L1: `result_test` → `_` in `executor.py` (ungenutzte Variable)

### File List

- `backend/requirements.txt` — GEÄNDERT
- `backend/src/gysi_ml/config.py` — GEÄNDERT (+ data_path)
- `backend/src/gysi_ml/api/schemas.py` — GEÄNDERT (+ ExecuteRequest, ExecuteResponse)
- `backend/src/gysi_ml/api/app.py` — GEÄNDERT (+ execute_router, app.state.data_path)
- `backend/src/gysi_ml/api/routes/execute.py` — NEU
- `backend/src/gysi_ml/steps/base.py` — NEU
- `backend/src/gysi_ml/steps/registry.py` — NEU
- `backend/src/gysi_ml/spec/schema.py` — NEU
- `backend/src/gysi_ml/executor/pipeline_context.py` — NEU
- `backend/src/gysi_ml/executor/executor.py` — NEU
- `backend/src/gysi_ml/persistence/run_repository.py` — NEU
- `backend/src/gysi_ml/utils/data_loader.py` — NEU
- `backend/tests/unit/test_registry.py` — NEU
- `backend/tests/unit/test_spec_schema.py` — NEU
- `backend/tests/unit/test_executor.py` — NEU
- `backend/tests/integration/test_execute_api.py` — NEU
