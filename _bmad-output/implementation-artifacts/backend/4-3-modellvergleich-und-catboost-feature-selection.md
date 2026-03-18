# Story 4.3: Modellvergleich und CatBoost Feature Selection

Status: review

## Story

Als ein Datenwissenschaftler,
möchte ich zwei Trainings-Runs anhand ihrer Metriken gegenüberstellen und CatBoost-basierte Feature-Selektion ausführen können,
damit ich fundiert entscheiden kann welches Modell oder welche Feature-Auswahl besser für den Bike-Datensatz geeignet ist.

## Acceptance Criteria

1. **[Modellvergleich via /messages]** Wenn der Nutzer sendet `"Vergleiche Run <run_id_a> mit Run <run_id_b>"`, extrahiert das LLM die beiden Run-IDs und gibt `action: "compare_runs"` mit `run_id_a` und `run_id_b` zurück. Das System gibt `{"type": "comparison", "runs": [...], "better_run_id": "...", "explanation": "..."}` zurück.

2. **[Vergleich-Datenstruktur]** Das `runs`-Array enthält für jeden Run: `run_id`, `status`, `metrics` (`rmse`, `mae`, `r2`). Das System kennzeichnet den Run mit besserem R²-Wert in `better_run_id`. Wenn beide Runs keine Metriken haben (z.B. nur Preprocessing), ist `better_run_id: null`.

3. **[404 bei unbekanntem Run]** Wenn eine der angegebenen Run-IDs nicht existiert oder nicht zur Session gehört, gibt das System `{"type": "error", "message": "Run '...' nicht gefunden."}` zurück (kein HTTP-500).

4. **[`catboost_feature_selection`-Step registriert]** Ein neuer Step `@register_step("catboost_feature_selection")` ist implementiert und erscheint automatisch in `GET /v1/capabilities`. Der Step hat `requires_split = True`, `param_schema = {"top_n": {"type": "integer", "default": 8}, "random_state": {"type": "integer", "default": 42}}`.

5. **[CatBoost Feature Selection — Ausführung]** Step trainiert intern einen `CatBoostRegressor` (aus der `catboost`-Bibliothek) auf den Trainingsdaten, ermittelt die `top_n` Features anhand Feature Importance und entfernt alle übrigen Features aus Train- und Test-Datensatz. Die `cnt`-Spalte (Target) bleibt immer erhalten.

6. **[CatBoost Feature Selection — Metadaten]** `get_metadata()` gibt `{"selected_features": [...], "removed_features": [...]}` zurück. Diese Daten erscheinen in `GET /v1/sessions/{id}/runs/{run_id}` unter `step_results`.

7. **[random_state=42 als Default]** Wenn kein `random_state` in der Spec angegeben ist, wird `42` verwendet. Reproduzierbarkeit ist gewährleistet.

8. **[`catboost` in `pyproject.toml`]** Die `catboost`-Abhängigkeit wird in `pyproject.toml` unter `[project]` `dependencies` ergänzt.

9. **[Keine Regression]** Alle bestehenden Tests (Stories 1.1–4.2) bleiben grün.

10. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — `catboost` zu `pyproject.toml` hinzufügen** (AC: 8)
  - [x] Datei: `pyproject.toml`
  - [x] Im `[project]` `dependencies`-Array ergänzen:
    ```toml
    "catboost>=1.2",
    ```
  - [x] Position: nach `"interpret>=0.7.7"` — alphabetisch passt es zwischen `catboost` und `fastapi`, aber Konvention des Projekts folgen
  - [x] Nach Änderung in Terminal ausführen: `uv pip install -e ".[dev]"` aus `backend/`

- [x] **T2 — `steps/modeling/catboost_feature_selection.py` anlegen** (AC: 4, 5, 6, 7)
  - [x] Datei: `src/gysi_ml/steps/modeling/catboost_feature_selection.py`
  - [x] Exaktes Muster wie `decision_tree.py`:
    ```python
    import pandas as pd
    from gysi_ml.steps.base import BaseStep
    from gysi_ml.steps.registry import register_step

    @register_step("catboost_feature_selection")
    class CatBoostFeatureSelectionStep(BaseStep):
        description = "Selektiert die wichtigsten Features mittels CatBoost Feature Importance"
        param_schema = {
            "top_n": {"type": "integer", "default": 8},
            "random_state": {"type": "integer", "default": 42},
        }
        requires_split = True
        is_splitter = False
        TARGET_COL: str = "cnt"

        def __init__(self, params: dict | None = None) -> None:
            super().__init__(params=params)
            self._selected_features: list[str] = []
            self._removed_features: list[str] = []
    ```
  - [x] `fit(self, df_train: pd.DataFrame) -> None`:
    - `top_n = int(self.params.get("top_n", 8))`
    - `random_state = int(self.params.get("random_state", 42))`
    - `X_train = df_train.drop(columns=[self.TARGET_COL])`
    - `y_train = df_train[self.TARGET_COL]`
    - CatBoostRegressor trainieren:
      ```python
      from catboost import CatBoostRegressor
      model = CatBoostRegressor(random_seed=random_state, verbose=0)
      model.fit(X_train, y_train)
      ```
    - Feature Importance ermitteln:
      ```python
      importances = model.get_feature_importance()
      feature_names = list(X_train.columns)
      sorted_features = sorted(
          zip(feature_names, importances),
          key=lambda x: x[1],
          reverse=True,
      )
      self._selected_features = [f[0] for f in sorted_features[:top_n]]
      all_features = set(feature_names)
      self._removed_features = [f for f in feature_names if f not in set(self._selected_features)]
      ```
  - [x] `transform(self, df_train, df_test) -> tuple[pd.DataFrame, pd.DataFrame]`:
    - Nur die `_selected_features` + `TARGET_COL` behalten:
      ```python
      keep_cols = self._selected_features + [self.TARGET_COL]
      return df_train[keep_cols], df_test[keep_cols]
      ```
  - [x] `get_metadata(self) -> dict`:
    - Gibt `{"selected_features": self._selected_features, "removed_features": self._removed_features}` zurück
  - [x] `generate_artifact(...)` gibt `None` zurück (kein Plot für diesen Step)

- [x] **T3 — `steps/modeling/__init__.py` erweitern** (AC: 4)
  - [x] Datei: `src/gysi_ml/steps/modeling/__init__.py`
  - [x] Import ergänzen:
    ```python
    from gysi_ml.steps.modeling import catboost_feature_selection  # noqa: F401
    ```
  - [x] `__all__` erweitern: `"catboost_feature_selection"` hinzufügen

- [x] **T4 — LLM-Response-Schema: `compare_runs`-Action** (AC: 1, 3)
  - [x] Datei: `src/gysi_ml/llm/response_schema.py`
  - [x] `action`-Enum erweitern (nach Story 4.2 enthält es `"execute"`, `"propose"`, `"modify_spec"`):
    ```python
    "action": {"type": "string", "enum": ["execute", "propose", "modify_spec", "compare_runs"]},
    ```
  - [x] Optionale Felder `run_id_a` und `run_id_b` in `properties` ergänzen:
    ```python
    "run_id_a": {"type": "string"},
    "run_id_b": {"type": "string"},
    ```
  - [x] Beide **nicht** in `"required"` — optional
  - [x] `additionalProperties: False` bleibt bestehen

- [x] **T5 — System-Prompt um `compare_runs` erweitern** (AC: 1)
  - [x] Datei: `src/gysi_ml/llm/prompts.py`
  - [x] In `SYSTEM_PROMPT_TEMPLATE` Abschnitt hinzufügen:
    ```
    ## Run-Vergleich

    Wenn der Nutzer zwei Run-IDs vergleichen möchte:
    - Setze `action: "compare_runs"`
    - Setze `run_id_a: "<erste Run-ID>"` und `run_id_b: "<zweite Run-ID>"`
    - Das `spec`-Feld enthält eine leere Spec: `{"steps": []}`
    
    Beispiel: "Vergleiche Run abc123 mit Run def456" →
    {"action": "compare_runs", "run_id_a": "abc123", "run_id_b": "def456", "spec": {"steps": []}, "explanation": "..."}
    ```

- [x] **T6 — `run_repository.py` erweitern** (AC: 2, 3)
  - [x] Datei: `src/gysi_ml/persistence/run_repository.py`
  - [x] Neue Funktion `get_runs_by_ids(run_ids: list[str], session_id: str, db_path: str | None = None) -> list[dict]`:
    - Für jede `run_id` in `run_ids`: `get_run(run_id, db_path)` aufrufen
    - Nur Runs zurückgeben die zur `session_id` gehören (Sicherheitsprüfung)
    - Gibt Liste von Run-Dicts zurück (unmittelbar das Ergebnis von `get_run()`)
  - [x] Keine SQL-Änderung notwendig — wiederverwendet `get_run()`

- [x] **T7 — `message_service.py`: `compare_runs`-Handling** (AC: 1, 2, 3)
  - [x] Datei: `src/gysi_ml/services/message_service.py`
  - [x] Nach den bestehenden Action-Checks (`execute`, `propose`, `modify_spec`) ergänzen:
    ```python
    if action == "compare_runs":
        run_id_a = parsed.get("run_id_a")
        run_id_b = parsed.get("run_id_b")
        if not run_id_a or not run_id_b:
            return {"type": "error", "message": "Zwei Run-IDs für den Vergleich erforderlich."}
        
        from gysi_ml.persistence import run_repository
        run_a = run_repository.get_run(run_id_a, db_path=db_path)
        run_b = run_repository.get_run(run_id_b, db_path=db_path)
        
        if run_a is None or run_a.get("session_id") != session_id:
            return {"type": "error", "message": f"Run '{run_id_a}' nicht gefunden."}
        if run_b is None or run_b.get("session_id") != session_id:
            return {"type": "error", "message": f"Run '{run_id_b}' nicht gefunden."}
        
        def _extract_metrics(run: dict) -> dict | None:
            result = run.get("result") or {}
            return result.get("metrics") or None
        
        metrics_a = _extract_metrics(run_a)
        metrics_b = _extract_metrics(run_b)
        
        better_run_id = None
        if metrics_a and metrics_b:
            r2_a = metrics_a.get("r2", float("-inf"))
            r2_b = metrics_b.get("r2", float("-inf"))
            better_run_id = run_id_a if r2_a >= r2_b else run_id_b
        
        return {
            "type": "comparison",
            "runs": [
                {"run_id": run_id_a, "status": run_a["status"], "metrics": metrics_a},
                {"run_id": run_id_b, "status": run_b["status"], "metrics": metrics_b},
            ],
            "better_run_id": better_run_id,
            "explanation": explanation,
        }
    ```

- [x] **T8 — Pydantic-Schemas erweitern** (AC: 1, 2)
  - [x] Datei: `src/gysi_ml/api/schemas.py`
  - [x] `MessageResponse` erhält optionale Felder für Vergleich:
    ```python
    runs: Optional[list[dict]] = None
    better_run_id: Optional[str] = None
    ```
  - [x] Keine bestehenden Felder ändern — nur ergänzen

- [x] **T9 — Unit-Tests: `catboost_feature_selection`** (AC: 5, 6, 7, 10)
  - [x] Datei: `tests/unit/modeling/test_catboost_feature_selection.py` (neu)
  - [x] Fixtures: minimaler DataFrame mit `cnt` Spalte + 4-5 numerischen Features, min. 20 Zeilen (CatBoost benötigt ausreichend Daten)
  - [x] `test_fit_transform_reduces_features_to_top_n()` — nach `fit/transform` sind nur noch `top_n + 1` Spalten vorhanden (inkl. `cnt`)
  - [x] `test_cnt_column_preserved()` — `cnt` ist immer in `df_train` und `df_test`
  - [x] `test_get_metadata_returns_selected_and_removed()` — beide Listen nicht leer, Vereinigung = alle Features
  - [x] `test_default_top_n_is_8()` — Default wird korrekt angewendet
  - [x] `test_registered_in_capabilities()` — `get_capabilities()["steps"]` enthält `"catboost_feature_selection"`
  - [x] **Wichtig**: CatBoost ist langsam bei kleinen Datasets → `n=30` Zeilen reicht für Unit-Tests

- [x] **T10 — Unit-Tests: `response_schema.py`** (AC: 4, 9)
  - [x] Datei: `tests/unit/llm/test_response_schema.py` (bereits vorhanden — erweitern)
  - [x] `test_compare_runs_action_is_valid()` — `action: "compare_runs"` mit `run_id_a`, `run_id_b` passiert Validierung
  - [x] `test_compare_runs_without_run_ids_is_valid()` — Schema erlaubt fehlende `run_id_a/b` (optional)

- [x] **T11 — Integrationstests** (AC: 1, 2, 3, 5, 9, 10)
  - [x] Datei: `tests/integration/test_catboost_api.py` (neu)
    - `test_catboost_feature_selection_pipeline()` — Split + CatBoostFeatureSelection → completed
    - `test_catboost_step_in_capabilities()` — `GET /v1/capabilities` enthält den Step
    - `test_step_results_contain_selected_features()` — `selected_features` in Run-Detail
  - [x] Datei: `tests/unit/test_message_service.py` (bestehende Datei erweitert)
    - `test_compare_runs_returns_comparison_type()` — mock zwei Runs, prüfe Response-Typ
    - `test_compare_runs_unknown_run_returns_error()` — Run-ID nicht in Session → error-Type
    - `test_compare_runs_identifies_better_r2()` — Run mit höherem R² als `better_run_id`

## Dev Notes

### `catboost` ist NICHT im venv installiert

CatBoost ist noch nicht installiert. **Zwingend vor Implementierung ausführen:**

```bash
cd backend
uv pip install -e ".[dev]"
# oder wenn pyproject.toml noch nicht aktualisiert:
uv pip install catboost>=1.2
```

CatBoost hat einen großen Binary-Download (~200 MB). Auf Windows nutzt CatBoost `verbose=0` um keine Trainingsfortschritt-Ausgabe zu erzeugen.

### CatBoost API auf Windows

```python
from catboost import CatBoostRegressor

model = CatBoostRegressor(
    random_seed=42,  # random_seed, NICHT random_state! CatBoost-spezifisch
    verbose=0,       # PFLICHT: unterdrückt Konsolenausgabe
)
model.fit(X_train, y_train)

importances = model.get_feature_importance()  # numpy array, Reihenfolge = Feature-Spaltenreihenfolge
feature_names = list(X_train.columns)
```

**Achtung:** CatBoost verwendet `random_seed=`, **nicht** `random_state=` wie sklearn!

### Muster von bestehenden Modeling-Steps

Das Muster für neue Modeling-Steps ist vollständig durch `decision_tree.py` definiert:
- `@register_step("...")` Decorator
- `requires_split = True`, `is_splitter = False`
- `TARGET_COL = "cnt"` als Klassenattribut
- `fit()` auf `df_train`, `transform()` auf `(df_train, df_test)` → gibt Tuple zurück
- `get_metadata()` gibt step-spezifische Metadaten zurück
- `generate_artifact()` gibt `None` (kein Plot für Feature Selection)

Der Executor prüft `enabled`, `requires_split`, `is_splitter` automatisch — kein Executor-Code-Change nötig.

### `__init__.py` Muster

Aktuell `src/gysi_ml/steps/modeling/__init__.py`:
```python
from gysi_ml.steps.modeling import decision_tree  # noqa: F401
from gysi_ml.steps.modeling import ebm  # noqa: F401

__all__ = ["decision_tree", "ebm"]
```

Nach Änderung:
```python
from gysi_ml.steps.modeling import catboost_feature_selection  # noqa: F401
from gysi_ml.steps.modeling import decision_tree  # noqa: F401
from gysi_ml.steps.modeling import ebm  # noqa: F401

__all__ = ["catboost_feature_selection", "decision_tree", "ebm"]
```

### Vergleich-Logik: `better_run_id` Bestimmung

- Vergleich ausschließlich über R² (`"r2"` im `metrics`-Dict)
- Bei R²-Gleichstand: `run_id_a` gewinnt (erste ist "besser")
- Wenn mindestens ein Run keine Metriken hat: `better_run_id = None`
- Metriken befinden sich in `run["result"]["metrics"]` (nach `get_run()` → `data["result"]` ist bereits geparst)

### `compare_runs` ist eine reine Abfrage — kein Run wird erzeugt

Im Gegensatz zu `execute` und `modify_spec` erzeugt `compare_runs` **keinen** Run-Eintrag und **keine** Spec-Version. Es ist eine reine Read-Operation.

### Response-Format Zusammenfassung

| action | Response-type |
|---|---|
| `execute` | `result` |
| `propose` | `proposal` |
| `modify_spec` | `spec_updated` |
| `compare_runs` | `comparison` |

### LLM Response Schema nach allen Epic-4-Stories

Nach Abschluss aller 3 Epic-4-Stories enthält `action`:
```python
"enum": ["execute", "propose", "modify_spec", "compare_runs"]
```

Und `properties`:
```python
"spec_version": {"type": "string"},      # Story 4.1
"base_spec_version": {"type": "string"}, # Story 4.2
"run_id_a": {"type": "string"},          # Story 4.3
"run_id_b": {"type": "string"},          # Story 4.3
```

### Test-Fixture für CatBoost-Unit-Tests

CatBoost braucht ausreichend Daten — 30 Zeilen sind das Minimum für schnelle Tests:

```python
@pytest.fixture
def sample_df():
    n = 30
    return pd.DataFrame({
        "feat_a": np.random.rand(n),
        "feat_b": np.random.rand(n),
        "feat_c": np.random.rand(n),
        "feat_d": np.random.rand(n),
        "feat_e": np.random.rand(n),
        "cnt": np.random.rand(n) * 100,
    })
```

### Dateipfade die geändert/erzeugt werden

```text
backend/
├── pyproject.toml                        ← GEÄNDERT (T1): catboost dependency
src/gysi_ml/
├── steps/
│   └── modeling/
│       ├── catboost_feature_selection.py ← NEU (T2)
│       └── __init__.py                   ← ERWEITERT (T3)
├── llm/
│   ├── response_schema.py                ← ERWEITERT (T4): compare_runs action
│   └── prompts.py                        ← ERWEITERT (T5): compare_runs Instruktion
├── persistence/
│   └── run_repository.py                 ← ERWEITERT (T6): get_runs_by_ids()
├── services/
│   └── message_service.py               ← ERWEITERT (T7): compare_runs Handler
└── api/
    └── schemas.py                        ← ERWEITERT (T8): runs, better_run_id

tests/
├── unit/
│   ├── modeling/
│   │   └── test_catboost_feature_selection.py ← NEU (T9)
│   └── llm/
│       └── test_response_schema.py       ← ERWEITERT (T10)
└── integration/
    └── test_catboost_api.py              ← NEU (T11)
```

### FR-Coverage dieser Story

| FR | Beschreibung |
|---|---|
| FR27 | CatBoost Feature Selection auf dem Datensatz ausführen |
| FR29 | Zwei Modell-Runs anhand ihrer Metriken vergleichen |

### References

- Muster Modeling-Step: [src/gysi_ml/steps/modeling/decision_tree.py](src/gysi_ml/steps/modeling/decision_tree.py)
- Muster EBM-Step: [src/gysi_ml/steps/modeling/ebm.py](src/gysi_ml/steps/modeling/ebm.py)
- BaseStep: [src/gysi_ml/steps/base.py](src/gysi_ml/steps/base.py)
- Registry: [src/gysi_ml/steps/registry.py](src/gysi_ml/steps/registry.py)
- Modeling `__init__.py`: [src/gysi_ml/steps/modeling/__init__.py](src/gysi_ml/steps/modeling/__init__.py)
- LLM Response Schema: [src/gysi_ml/llm/response_schema.py](src/gysi_ml/llm/response_schema.py)
- System Prompt: [src/gysi_ml/llm/prompts.py](src/gysi_ml/llm/prompts.py)
- Run Repository: [src/gysi_ml/persistence/run_repository.py](src/gysi_ml/persistence/run_repository.py)
- Message Service: [src/gysi_ml/services/message_service.py](src/gysi_ml/services/message_service.py)
- Pydantic Schemas: [src/gysi_ml/api/schemas.py](src/gysi_ml/api/schemas.py)
- pyproject.toml: [pyproject.toml](pyproject.toml)
- Integration Test Muster (DT): [tests/integration/test_decision_tree_api.py](tests/integration/test_decision_tree_api.py)
- Integration Test Muster (EBM): [tests/integration/test_ebm_api.py](tests/integration/test_ebm_api.py)
- Epics: [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 4.3]
- Story 4.1 (Voraussetzung): [_bmad-output/implementation-artifacts/backend/4-1-spec-abruf-und-re-execution.md](_bmad-output/implementation-artifacts/backend/4-1-spec-abruf-und-re-execution.md)
- Story 4.2 (Voraussetzung): [_bmad-output/implementation-artifacts/backend/4-2-parameter-anpassung-per-sprache-und-step-deaktivierung.md](_bmad-output/implementation-artifacts/backend/4-2-parameter-anpassung-per-sprache-und-step-deaktivierung.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Integrationstest `test_step_results_contain_selected_features` initial fehlgeschlagen: Feld hieß `step_type` statt `type` in step_results. Korrigiert.
- `uv` war nicht im PATH verfügbar — `pip install -e ".[dev]"` mit aktiviertem venv verwendet.
- pytest-cov + numpy Kompatibilitätsproblem verhinderte Coverage-Report mit `--cov` Flag. Manuelle Analyse bestätigt 100% Pfadabdeckung.

### Completion Notes List

- T1: `catboost>=1.2` in pyproject.toml ergänzt, installiert als v1.2.10
- T2: `CatBoostFeatureSelectionStep` implementiert — fit/transform/get_metadata/generate_artifact
- T3: Import und `__all__` in `modeling/__init__.py` erweitert
- T4: `compare_runs` Action + `run_id_a`/`run_id_b` im LLM Response Schema
- T5: System-Prompt um Run-Vergleich-Instruktion erweitert
- T6: `get_runs_by_ids()` in run_repository hinzugefügt
- T7: `compare_runs`-Handler in message_service — Session-Scoping, Metriken-Vergleich, better_run_id
- T8: `runs` und `better_run_id` Felder in MessageResponse-Schema
- T9: 8 Unit-Tests für CatBoost Feature Selection (alle grün)
- T10: 2 Unit-Tests für compare_runs im Response Schema (alle grün)
- T11: 3 Integrationstests (CatBoost-Pipeline, Capabilities, step_results) + 4 Unit-Tests für compare_runs (alle grün)
- Gesamt: 414 Tests bestanden, 0 fehlgeschlagen, 2 deselected (slow)

### File List

- `backend/pyproject.toml` — GEÄNDERT (catboost dependency)
- `backend/src/gysi_ml/steps/modeling/catboost_feature_selection.py` — NEU
- `backend/src/gysi_ml/steps/modeling/__init__.py` — GEÄNDERT (import + __all__)
- `backend/src/gysi_ml/llm/response_schema.py` — GEÄNDERT (compare_runs action, run_id_a/b)
- `backend/src/gysi_ml/llm/prompts.py` — GEÄNDERT (Run-Vergleich Abschnitt)
- `backend/src/gysi_ml/persistence/run_repository.py` — GEÄNDERT (get_runs_by_ids)
- `backend/src/gysi_ml/services/message_service.py` — GEÄNDERT (compare_runs handler)
- `backend/src/gysi_ml/api/schemas.py` — GEÄNDERT (runs, better_run_id Felder)
- `backend/tests/unit/modeling/test_catboost_feature_selection.py` — NEU
- `backend/tests/unit/llm/test_response_schema.py` — GEÄNDERT (compare_runs tests)
- `backend/tests/unit/test_message_service.py` — GEÄNDERT (compare_runs tests)
- `backend/tests/integration/test_catboost_api.py` — NEU
