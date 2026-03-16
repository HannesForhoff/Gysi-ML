# Story 1.5: Train/Test-Split als Architekturgrenze und Run-Persistenz vollständig

Status: done

## Story

Als ein Datenwissenschaftler,
möchte ich den Datensatz reproduzierbar aufteilen und alle Run-Ergebnisse mit Input-Parametern und Artefakt-Referenzen abrufen können,
damit Experimente exakt wiederholbar sind und jede Pipeline-Ausführung vollständig auditierbar ist.

## Acceptance Criteria

1. **[Split-Step]** Spec-Step `{"type": "split", "params": {"test_size": 0.2, "random_state": 42}}` teilt den Datensatz in Train (80%) und Test (20%) auf mit `random_state=42`. Alle nachfolgenden fit/transform-Steps erhalten ausschließlich die Trainingsdaten für `fit()`.

2. **[Architektur-Constraint]** Ein Imputation-, Outlier-Handling- oder Encoding-Step **vor** einem Split-Step in der Spec gibt einen strukturierten Fehler zurück, bevor die Ausführung startet: `{"error": "invalid_spec_order", "detail": "Step 'impute_missing' benötigt einen vorherigen 'split'-Step", ...}`.

3. **[Reproduzierbarkeit]** Zwei identische Specs mit gleichen Parametern und `random_state=42` liefern identische Ergebnisse (Zeilenzahlen, imputierte Werte, entfernte Features).

4. **[Runs auflisten]** `GET /v1/sessions/{session_id}/runs` gibt alle Runs der Session zurück (Array) mit `run_id`, `status`, `started_at`, `spec_version`.

5. **[Run-Detail]** `GET /v1/sessions/{session_id}/runs/{run_id}` gibt vollständige Run-Daten zurück: Input-Spec, Step-Ergebnisse (Metadaten je Step), Metriken (leer wenn kein Training), Artefakt-Referenzen (leer wenn keine Artefakte), `status`, `started_at`, `finished_at`.

6. **[Fehlgeschlagener Run]** `GET /v1/sessions/{session_id}/runs/{run_id}` für einen fehlgeschlagenen Run gibt `status: "failed"` und `error_message` zurück.

7. **[404 — Run nicht gefunden]** `GET /v1/sessions/{session_id}/runs/{run_id}` mit unbekannter Run-ID gibt HTTP 404 zurück.

8. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — SplitStep** (AC: 1, 3)
  - [x] `src/gysi_ml/steps/preprocessing/split.py` anlegen
  - [x] `@register_step("split")` `class SplitStep(BaseStep):`
  - [x] `description = "Teilt den Datensatz reproduzierbar in Train/Test auf"`
  - [x] `param_schema = {"test_size": {"type": "number", "default": 0.2}, "random_state": {"type": "integer", "default": 42}}`
  - [x] `fit(df)`: no-op (Split ist zustandsfrei)
  - [x] `transform(df_full, _)`:
    - Verwendet `sklearn.model_selection.train_test_split` mit `test_size` und `random_state`
    - Gibt `(df_train, df_test)` zurück
  - [x] Setzt `context.is_split = True` und `context.df_train`, `context.df_test`
  - [x] `get_metadata()`: gibt `{"train_rows": <int>, "test_rows": <int>, "test_size": <float>, "random_state": <int>}` zurück
  - [x] `@register_step("split")` in `steps/preprocessing/__init__.py` importieren

- [x] **T2 — Spec-Order-Validierung im Executor** (AC: 2)
  - [x] `src/gysi_ml/executor/spec_validator.py` anlegen
  - [x] `validate_spec_order(steps: list[dict]) -> None`:
    - `REQUIRES_SPLIT = {"impute_missing", "outlier_handling", "encode_categorical", "correlation_filter", "rare_category_bucketing"}`
    - Iteriert Steps; merkt sich ob `"split"` bereits gesehen wurde
    - Bei einem Step in `REQUIRES_SPLIT` ohne vorherigen Split → wirft `SpecOrderError`
  - [x] `SpecOrderError` als eigene Exception-Klasse
  - [x] Executor ruft `validate_spec_order()` **vor** der Ausführung auf (nach `validate_spec()`)
  - [x] Fehlerformat: `{"error": "invalid_spec_order", "detail": "...", "code": "INVALID_SPEC_ORDER"}`

- [x] **T3 — Run-Repository erweitern** (AC: 4, 5, 6, 7)
  - [x] `persistence/run_repository.py` aus Story 1.2 erweitern:
  - [x] `get_runs_for_session(session_id: str) -> list[dict]` — alle Runs einer Session
  - [x] `get_run(run_id: str) -> dict | None` — einzelner Run mit vollständigen Daten
  - [x] `result_json` Feld enthält serialisiertes Ergebnis-Dict (Step-Metadaten + Metriken + Artefakte)
  - [x] Alle Queries parameterized

- [x] **T4 — Pydantic Schemas ergänzen** (AC: 4, 5, 6)
  - [x] `api/schemas.py` erweitern:
  - [x] `RunSummaryResponse`: `run_id`, `status`, `started_at`, `spec_version`
  - [x] `RunDetailResponse`: + `spec`, `step_results`, `metrics`, `artifacts`, `finished_at`, `error_message`
  - [x] `RunListResponse`: `runs: list[RunSummaryResponse]`

- [x] **T5 — Runs-Endpunkte** (AC: 4, 5, 6, 7)
  - [x] `src/gysi_ml/api/routes/runs.py` anlegen
  - [x] `GET /v1/sessions/{session_id}/runs` → `RunListResponse`
  - [x] `GET /v1/sessions/{session_id}/runs/{run_id}` → `RunDetailResponse` oder HTTP 404
  - [x] Router in `api/app.py` registrieren

- [x] **T6 — Executor-Integration: context.is_split + result_json** (AC: 1, 5)
  - [x] Executor nach Abschluss: `result_json = json.dumps({"step_results": ..., "metrics": {}, "artifacts": []})` → in `update_run_status` speichern
  - [x] `get_run()` deserialisiert `result_json` und gibt vollständiges Dict zurück
  - [x] Spec wird vor Ausführung gespeichert (auch für fehlgeschlagene Runs)

- [x] **T7 — Unit Tests** (AC: 1, 2, 3, 8)
  - [x] `tests/unit/preprocessing/test_split.py`: Zeilenzahlen, random_state-Reproduzierbarkeit, Metadata
  - [x] `tests/unit/test_spec_order_validator.py`: gültige Reihenfolge, ungültige Reihenfolge → SpecOrderError

- [x] **T8 — Integration Tests** (AC: 1–7, 8)
  - [x] `tests/integration/test_runs_api.py`: GET /runs, GET /runs/{id}, 404, fehlgeschlagener Run
  - [x] `tests/integration/test_reproducibility.py`: Zwei identische Specs → identische Ergebnisse

## Dev Notes

### Zielstruktur nach dieser Story

```
backend/src/gysi_ml/
├── steps/preprocessing/
│   └── split.py                     # NEU: SplitStep
├── executor/
│   ├── executor.py                  # aktualisiert: validate_spec_order, result_json, is_split
│   └── spec_validator.py            # NEU: validate_spec_order, SpecOrderError
├── persistence/
│   └── run_repository.py            # erweitert: get_runs_for_session, get_run
└── api/
    ├── schemas.py                   # + RunSummaryResponse, RunDetailResponse, RunListResponse
    └── routes/
        └── runs.py                  # NEU: GET /v1/sessions/{id}/runs[/{run_id}]
```

### fit/transform-Grenze — Architekturdiagramm

```
bikes.csv
    │
    ▼
[dedup] ─── arbeitet auf df_full (stateless, kein fit benötigt)
    │
    ▼
[time_feature_encoding] ─── arbeitet auf df_full (stateless)
    │
    ▼
[SPLIT] ──────────────── context.is_split = True
    │
    ├─── df_train (80%)
    │       │
    │       ▼ fit() ← NUR HIER lernen!
    │    [impute_missing]
    │    [outlier_handling]
    │    [encode_categorical]
    │    [correlation_filter]
    │
    └─── df_test (20%) ← nur transform(), nie fit()
```

### Spec-Order-Validierung — Steps die Split benötigen

```python
REQUIRES_SPLIT = {
    "impute_missing",
    "outlier_handling",
    "encode_categorical",
    "correlation_filter",
    "rare_category_bucketing",
    # Modeling Steps (Epic 2) ebenfalls:
    "train_decision_tree",
    "train_ebm",
    "catboost_feature_selection",
}
```

Diese Konstante in `spec_validator.py` definieren, nicht hardcoded im Executor.

### result_json — Format

Das `result_json`-Feld im `runs`-Table speichert:
```json
{
  "step_results": [
    {"step_type": "dedup", "metadata": {"removed_duplicates": 0}},
    {"step_type": "split", "metadata": {"train_rows": 13903, "test_rows": 3476, "test_size": 0.2, "random_state": 42}},
    {"step_type": "impute_missing", "metadata": {"imputed_values_per_column": {"mnth": 12, "weathersit": 8}}}
  ],
  "metrics": {},
  "artifacts": []
}
```

`metrics` und `artifacts` werden in Epics 2 befüllt.

### Default random_state (NFR — Reproduzierbarkeit)

`random_state=42` ist der projektweite Standard für alle nichtdeterministischen Operationen. Der Split-Step verwendet ihn als Default wenn nicht in der Spec angegeben.

### Referenzen

- [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 1.5]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#FR24, FR35, FR36, FR37]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#NFR-R3, NFR-T2]
- [Source: backend/AGENTS.md#Pipeline-Scope Preprocessing (Data Splitting)]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

- Executor.py: Replaced old string required a 2-step edit (leftover orphan fragment `elif context.is_split:` removed in 2nd pass)
- 5 existing integration tests updated: `split_required` → `invalid_spec_order` after pre-flight spec-order validation added
- `scikit-learn>=1.0` added to `pyproject.toml` dependencies

### Completion Notes List

- `schema.py`: `spec_id TEXT` in `runs` table; `import sqlite3` und überflüssiger ALTER TABLE entfernt (M1-fix)
- `run_repository.py`: `create_run()` — `spec_id` als optionaler Parameter ans Ende verschoben (M2-fix)
- `executor.py`: spec wird vor Ausführung gespeichert; Runtime-Fallback `requires_split`-Check nutzt jetzt einheitlich `invalid_spec_order`/`INVALID_SPEC_ORDER` (H1-fix)
- Coverage: split.py 97%, spec_validator.py 100%, run_repository.py 100%, runs.py 100%, overall 96%

### File List

- `backend/src/gysi_ml/steps/preprocessing/split.py` — rewritten (sklearn, random_state, metadata)
- `backend/src/gysi_ml/executor/spec_validator.py` — new
- `backend/src/gysi_ml/executor/executor.py` — updated (spec_order validation, spec saved before run, result_json format)
- `backend/src/gysi_ml/persistence/schema.py` — updated (spec_id column + migration)
- `backend/src/gysi_ml/persistence/run_repository.py` — extended (create_run+spec_id, get_runs_for_session, get_run)
- `backend/src/gysi_ml/api/schemas.py` — extended (RunSummaryResponse, RunDetailResponse, RunListResponse)
- `backend/src/gysi_ml/api/routes/runs.py` — new
- `backend/src/gysi_ml/api/app.py` — updated (runs_router included)
- `backend/src/gysi_ml/steps/preprocessing/__init__.py` — updated (split/encoding/correlation_filter/rare_category/time_features imports)
- `backend/pyproject.toml` — updated (scikit-learn dependency)
- `backend/tests/unit/preprocessing/test_split.py` — new (17 tests)
- `backend/tests/unit/test_spec_order_validator.py` — new (15 tests)
- `backend/tests/integration/test_runs_api.py` — new (13 tests)
- `backend/tests/integration/test_reproducibility.py` — new (5 tests)
- `backend/tests/integration/test_preprocessing_pipeline.py` — updated (split_required → invalid_spec_order)
- `backend/tests/integration/test_full_preprocessing_pipeline.py` — updated (split_required → invalid_spec_order)
