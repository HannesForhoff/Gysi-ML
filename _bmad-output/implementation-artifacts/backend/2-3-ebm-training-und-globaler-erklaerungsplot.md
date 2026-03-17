# Story 2.3: EBM Training und globaler Erklärungsplot

Status: done

## Story

Als ein Datenwissenschaftler,
möchte ich ein Explainable Boosting Machine (EBM) Regressionsmodell trainieren und einen globalen Erklärungsplot abrufen können,
damit ich die Modellentscheidungen auf Feature-Ebene interpretieren und dem Evaluator transparent erklären kann.

## Acceptance Criteria

1. **[train_ebm-Step registriert]** Ein Step mit `{"type": "train_ebm", "params": {"random_state": 42}}` ist über `@register_step("train_ebm")` verfügbar und erscheint in `GET /v1/capabilities`.

2. **[EBM-Training auf Trainingsdaten]** `fit(df_train)` trainiert einen `ExplainableBoostingRegressor` (InterpretML) mit dem konfigurierten `random_state`, ausschließlich auf Trainingsdaten (Zielvariable: `cnt`).

3. **[Metriken auf Testdaten]** `transform(df_train, df_test)` berechnet Vorhersagen auf `X_test` und persistiert RMSE, MAE und R² — identisches Schema wie Decision Tree (`{"rmse": ..., "mae": ..., "r2": ...}`).

4. **[Default random_state]** Wenn kein `random_state` angegeben, wird `42` verwendet.

5. **[EBM-Global-Explanation-Plot als PNG]** `generate_artifact()` erstellt einen EBM-Global-Explanation-Plot als PNG: horizontales Balkendiagramm der mittleren absoluten Feature-Wichtigkeiten (aus `ebm.explain_global()`). Die PNG-Datei wird unter `{artifacts_path}/ebm_global_explanation_{run_id}.png` gespeichert.

6. **[SQLite-Artefakt-Eintrag]** Artefakt mit `type: "ebm_global_explanation"` wird in der `artifacts`-Tabelle persistiert — via Executor (identischer Mechanismus wie Story 2.2).

7. **[Artefakt-Abruf]** `GET /v1/artifacts/{artifact_id}` für ein EBM-Artefakt gibt die PNG-Datei mit `Content-Type: image/png` zurück (bereits implementierte Route aus Story 2.2).

8. **[split_required-Fehler]** `train_ebm` ohne vorherigen `split`-Step → `{"error": "invalid_spec_order", ..., "code": "INVALID_SPEC_ORDER"}` (bereits in `spec_validator.REQUIRES_SPLIT` verankert).

9. **[NFR-P3 — Laufzeit]** EBM-Training + Plot-Erstellung auf dem vollständigen Bike-Datensatz (17.379 Zeilen) schließt in < 60 Sekunden ab.

10. **[interpret-Abhängigkeit]** `interpret>=0.7.7` ist explizit in `requirements.txt` und `pyproject.toml` eingetragen.

11. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — `interpret`-Abhängigkeit hinzufügen** (AC: 10)
  - [x] `backend/requirements.txt` ergänzen: `interpret>=0.7.7`
  - [x] `backend/pyproject.toml` unter `[project] dependencies` ergänzen: `"interpret>=0.7.7"`
  - [x] Dependency installieren: `uv pip install interpret>=0.7.7` (oder `uv sync`)
  - [x] Smoke-Test: `python -c "from interpret.glassbox import ExplainableBoostingRegressor; print('OK')"` muss erfolgreich sein

- [x] **T2 — `steps/modeling/ebm.py` anlegen** (AC: 1, 2, 3, 4, 5, 9)
  - [x] `src/gysi_ml/steps/modeling/ebm.py` erstellen:
    - `@register_step("train_ebm")` `class EBMStep(BaseStep):`
    - Klassenattribute:
      - `description = "Trainiert ein Explainable Boosting Machine-Modell und erzeugt einen globalen Erklärungsplot"`
      - `param_schema = {"random_state": {"type": "integer", "default": 42}}`
      - `requires_split = True`
      - `is_splitter = False`
      - `TARGET_COL: str = "cnt"`
    - `__init__(params)`: ruft `super().__init__(params)` auf; initialisiert `self.model = None`, `self._metrics = {}`, `self._feature_names = []`
    - `fit(df_train)`:
      - `X_train = df_train.drop(columns=[TARGET_COL])`
      - `y_train = df_train[TARGET_COL]`
      - `self._feature_names = list(X_train.columns)`
      - `from interpret.glassbox import ExplainableBoostingRegressor`
      - `self.model = ExplainableBoostingRegressor(random_state=int(self.params.get("random_state", 42)))`
      - `self.model.fit(X_train, y_train)`
    - `transform(df_train, df_test)`:
      - `X_test = df_test.drop(columns=[TARGET_COL])`
      - `y_test = df_test[TARGET_COL]`
      - `y_pred = self.model.predict(X_test)`
      - Berechnet: `rmse`, `mae`, `r2` — identisch zu DecisionTreeStep
      - `self._metrics = {"rmse": rmse, "mae": mae, "r2": r2}`
      - Gibt `(df_train, df_test)` **unverändert** zurück
    - `get_metadata()`: gibt `{"metrics": self._metrics, "feature_names": self._feature_names}` zurück
    - `generate_artifact(artifacts_path, run_id)`:
      - Falls `self.model is None`: gibt `None` zurück
      - `import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt`
      - **Non-interactive Backend** — zwingend für Server-Betrieb
      - Extrahiert globale Feature-Wichtigkeiten:
        ```python
        ebm_global = self.model.explain_global()
        global_data = ebm_global.data()
        feature_names = global_data["names"]
        feature_scores = global_data["scores"]
        ```
      - Kombiniert, sortiert absteigend nach Score-Betrag, nimmt Top-20
      - Erstellt horizontales Balkendiagramm:
        - `fig, ax = plt.subplots(figsize=(10, 8))`
        - `ax.barh(names_top20, scores_top20)`
        - `ax.set_xlabel("Mittlere absolute Auswirkung")`
        - `ax.set_title("EBM — Globale Feature-Wichtigkeit (Top 20)")`
        - `ax.invert_yaxis()`
      - `os.makedirs(artifacts_path, exist_ok=True)`
      - `file_path = os.path.join(artifacts_path, f"ebm_global_explanation_{run_id}.png")`
      - `fig.savefig(file_path, bbox_inches="tight", dpi=150)`
      - `plt.close(fig)`
      - Gibt zurück: `{"type": "ebm_global_explanation", "file_path": file_path}`

- [x] **T3 — EBM-Step im Modeling-Package registrieren** (AC: 1)
  - [x] `src/gysi_ml/steps/modeling/__init__.py` erweitern:
    ```python
    from gysi_ml.steps.modeling import decision_tree  # noqa: F401
    from gysi_ml.steps.modeling import ebm            # noqa: F401
    __all__ = ["decision_tree", "ebm"]
    ```
  - [x] `steps/__init__.py` bleibt unverändert (importiert bereits `modeling`)

- [x] **T4 — requirements-dev.txt prüfen** (AC: 10)
  - [x] `backend/requirements-dev.txt` prüfen: keine interpret-spezifischen Dev-Abhängigkeiten nötig
  - [x] Sicherstellen dass `pytest-timeout` oder äquivalent verfügbar (für NFR-P3-Test) — falls nicht: als Dev-Abhängigkeit hinzufügen

- [x] **T5 — Unit Tests** (AC: 1–5, 11)
  - [x] `tests/unit/modeling/test_ebm_step.py` anlegen:
    - **Wichtig**: EBM-Training auf vollständigem Datensatz ist langsam; für Unit-Tests synthetischen kleinen DataFrame nutzen (ca. 100–200 Zeilen, `random_state=42`)
    - `test_step_is_registered()`: `get_step_class("train_ebm")` gibt `EBMStep` zurück
    - `test_fit_trains_on_train_data()`: nach `fit(df_train)` → `self.model` ist nicht `None`
    - `test_transform_returns_unchanged_dataframes()`: Shapes von `df_train`/`df_test` unverändert
    - `test_metrics_computed()`: `get_metadata()["metrics"]` enthält `rmse`, `mae`, `r2` als Floats
    - `test_default_random_state()`: ohne Param → `random_state=42`, identische Ergebnisse bei Wiederholung
    - `test_generate_artifact_creates_png(tmp_path)`: nach `fit` + `transform` → PNG-Datei existiert, `type == "ebm_global_explanation"`
    - `test_generate_artifact_none_before_fit()`: ohne `fit()` → `None`
    - `test_capabilities_contains_ebm()`: `get_capabilities()` enthält Step mit `type == "train_ebm"`

- [x] **T6 — Integration Tests** (AC: 7, 8, 9, 11)
  - [x] `tests/integration/test_ebm_api.py` anlegen:
    - `test_full_pipeline_with_ebm()`: POST exec mit Spec (split + train_ebm) → Status 200, `run_id` vorhanden
    - `test_run_detail_contains_ebm_metrics()`: GET run detail → `metrics.rmse`, `.mae`, `.r2` vorhanden
    - `test_ebm_artifact_in_run_detail()`: `artifacts`-Array enthält Eintrag mit `type: "ebm_global_explanation"`
    - `test_ebm_artifact_retrieve()`: GET `/v1/artifacts/{artifact_id}` → HTTP 200, `Content-Type: image/png`
    - `test_split_required_before_ebm()`: Spec nur mit `train_ebm` → `code: "INVALID_SPEC_ORDER"`
    - `test_performance_under_60s()` (mit `@pytest.mark.slow` oder `pytest-timeout`): kompletter Preprocessing + EBM-Pipeline auf realem Datensatz < 60 s — **nur mit realem `bikes.csv`, daher bedingt in CI**

## Dev Notes

### Zielstruktur nach dieser Story

```text
backend/src/gysi_ml/
└── steps/
    └── modeling/
        ├── __init__.py       # ÄNDERN: + ebm-Import
        ├── decision_tree.py  # UNVERÄNDERT
        └── ebm.py            # NEU: EBMStep
```

### Architektur-Constraints (kritisch!)

- **InterpretML-Import lazy halten**: `from interpret.glassbox import ExplainableBoostingRegressor` innerhalb von `fit()` statt auf Modulebene. Begründung: Laden beim Modulimport kostet Zeit und kann in Test-Environments zu Problemen führen. Alternativ: top-level Import in `ebm.py` ist akzeptabel — einheitlich mit DT-Step Konvention entscheiden.
- **`ebm_global.data()` Struktur**: Das `data()`-Attribut des `GlobalExplanation`-Objekts gibt zurück: `{"names": [...], "scores": [...], "type": "univariate", "perf": <dict>}`. Die `scores` sind die mittleren absoluten Auswirkungen jedes Features (Shape Scalars, keine Listen). **Sorgfältig testen mit `assert isinstance(feature_scores[0], (int, float))`**.
- **Non-interactive Matplotlib** (Wiederholung, kritisch): `matplotlib.use("Agg")` **muss** verwendet werden. In Tests wird pytest headless in CI ausgeführt — fehlendes Agg-Backend führt zu `_tkinter`-Fehler auf Linux.
- **NFR-P3**: < 60 Sekunden auf realem Datensatz. InterpretML EBM ist mit Default-Parametern auf ca. 14.000 Trainingszeilen (80% von 17.379) deutlich schneller als 60 s. Falls überschritten: `max_bins=256` und `max_interaction_bins=32` als Params prüfen (sind InterpretML-Defaults, sollten ausreichen).
- **`TARGET_COL = "cnt"`**: Identisch zu `DecisionTreeStep` — kann ggf. als gemeinsame Konstante in `steps/modeling/__init__.py` definiert werden, muss aber kein Refactoring sein.

### EBM `explain_global()` Daten-Zugriff

```python
ebm_global = self.model.explain_global()
global_data = ebm_global.data()
# global_data["names"]: list[str] — Feature-Namen
# global_data["scores"]: list[float] — mittlere abs. Auswirkung (Mean Absolute Score)
# Hinweis: InterpretML v0.7.x - Struktur stabil seit v0.3

# Alternativ (falls obiges nicht funktioniert bei Versionsunterschied):
# scores = [abs(self.model.term_importances()[i]) for i in range(len(self.model.term_names_))]
# names = list(self.model.term_names_)
```

**Robustheit**: Im Zweifelsfall `term_importances()` und `term_names_` direkt auf dem Modell nutzen — diese sind garantiert verfügbar in InterpretML >= 0.3.

### Abhängigkeit auf Story 2.2

Diese Story setzt voraus, dass Story 2.2 vollständig implementiert ist:
- `BaseStep.generate_artifact()` existiert
- `artifact_repository.py` existiert
- `PipelineExecutor` hat `artifacts_path`-Parameter und Artefakt-Persistenz-Logik
- `artifacts_path` in Settings konfiguriert
- `GET /v1/artifacts/{id}` Route registriert

**Kein eigener Artefakt-Infrastruktur-Code** — alles wird von Story 2.2 bereitgestellt.

### Regressions-Schutz

- `steps/modeling/__init__.py` erhält neuen Import → `GET /v1/capabilities` gibt jetzt auch `train_ebm` zurück → `test_capabilities_api.py` muss ggf. ergänzt werden (nicht gebrochen, aber erweiterbar)
- Alle bestehenden Tests (249+ Stück) müssen weiterhin grün sein

### Smoke-Check nach Integration

```bash
# Im backend-Verzeichnis
uv run pytest tests/unit/modeling/test_ebm_step.py -v
uv run pytest tests/integration/test_ebm_api.py -v
uv run pytest tests/ --cov=src/gysi_ml --cov-report=term-missing
```

### Referenzen

- EBM-Dokumentation: InterpretML v0.7.x — `ExplainableBoostingRegressor.explain_global()`
- DecisionTreeStep (Story 2.1): `backend/src/gysi_ml/steps/modeling/decision_tree.py`
- Artefakt-Infrastruktur (Story 2.2): `backend/src/gysi_ml/persistence/artifact_repository.py`, `backend/src/gysi_ml/steps/base.py`
- Executor (Story 2.2): [backend/src/gysi_ml/executor/executor.py](backend/src/gysi_ml/executor/executor.py)
- FR26, FR28, FR31, FR32: [epics.md](_bmad-output/planning-artifacts/backend/epics.md)
- NFR-P3: [prd.md](_bmad-output/planning-artifacts/backend/prd.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Baseline: 270 tests passed
- Nach T5 (Unit): 8/8 EBM Unit-Tests grün
- Nach T6 (Integration): 5/5 EBM Integration-Tests grün (1 slow deselected)
- Final: 283 passed, 2 deselected, keine Regressionen
- EBM-Modul Coverage: 98% (Zeile 43 — RuntimeError-Pfad uncovered)
- Code Review Fixes: 284 passed, 2 deselected, keine Regressionen

### Completion Notes List

- `interpret>=0.7.7` als Dependency hinzugefügt (requirements.txt + pyproject.toml)
- EBMStep folgt exakt dem DecisionTreeStep-Pattern: `fit()` → `transform()` → `get_metadata()` → `generate_artifact()`
- Lazy import von `interpret.glassbox` in `fit()` wie in Story-Dev-Notes empfohlen
- `matplotlib.use("Agg")` jetzt auf Modulebene (nicht in `generate_artifact()`) — verhindert wiederholte UserWarning
- `plt.close(fig)` in `try/finally` — Figure-Objekt wird auch bei `savefig()`-Exceptions freigegeben
- `feature_scores` explizit zu `float` konvertiert via `[float(s) for s in ...]` für numpy-Robustheit
- Typ-Annotation `self.model: "ExplainableBoostingRegressor | None"` für Code-Klarheit
- `train_ebm` war bereits in `spec_validator.REQUIRES_SPLIT` registriert
- Kein `pytest-timeout` nötig — Performance-Test nutzt `time.time()` analog zu DT

### Senior Developer Review (AI)

**Ergebnis:** Approved nach Fixes
**Datum:** 2026-03-15
**Reviewer:** Claude Sonnet 4.6

**Gefundene Issues (alle behoben):**
- [x] [M1] `plt.close(fig)` ohne `try/finally` → jetzt in `try/finally`-Block [ebm.py]
- [x] [M2] Fehlender Test für `transform()` vor `fit()` → `test_transform_before_fit_raises_error` hinzugefügt [test_ebm_step.py]
- [x] [M3] Fehlende `feature_scores`-Type-Assertion → Test + explizite `float()`-Konvertierung [ebm.py + test_ebm_step.py]
- [x] [L1] `matplotlib.use("Agg")` wiederholter Aufruf → auf Modulebene verschoben [ebm.py]
- [x] [L2] Fehlende Typ-Annotation für `self.model` → `"ExplainableBoostingRegressor | None"` [ebm.py]

### File List

- `backend/requirements.txt` — GEÄNDERT: `interpret>=0.7.7` hinzugefügt
- `backend/pyproject.toml` — GEÄNDERT: `"interpret>=0.7.7"` in dependencies
- `backend/src/gysi_ml/steps/modeling/ebm.py` — NEU: EBMStep (inkl. Review-Fixes)
- `backend/src/gysi_ml/steps/modeling/__init__.py` — GEÄNDERT: ebm-Import hinzugefügt
- `backend/tests/unit/modeling/test_ebm_step.py` — NEU: 9 Unit-Tests (inkl. Review-Fixes)
- `backend/tests/integration/test_ebm_api.py` — NEU: 6 Integration-Tests (5 + 1 slow)
