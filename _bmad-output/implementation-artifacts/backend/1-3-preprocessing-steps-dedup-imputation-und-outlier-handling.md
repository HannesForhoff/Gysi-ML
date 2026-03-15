# Story 1.3: Preprocessing Steps — Dedup, Imputation und Outlier Handling

Status: done

## Story

Als ein Datenwissenschaftler,
möchte ich Duplikate entfernen, fehlende Werte imputieren und Ausreißer behandeln lassen,
damit der Bike-Datensatz (mit künstlich eingebrachten fehlenden Werten in `mnth` und `weathersit`) für das Modelltraining vorbereitet ist.

## Acceptance Criteria

1. **[Dedup]** Spec-Step `{"type": "dedup"}` entfernt exakt duplizierte Zeilen. Anzahl entfernter Duplikate wird im Run-Ergebnis gespeichert.

2. **[Imputation — median]** Spec-Step `{"type": "impute_missing", "params": {"strategy": "median"}}` imputiert fehlende Werte numerischer Spalten mit dem Median der Trainingsdaten (`fit` nur auf Train-Split). Bei `strategy: "mean"` → Mittelwert, bei `"most_frequent"` → häufigster Wert. Anzahl imputierter Werte pro Spalte wird im Run-Ergebnis gespeichert.

3. **[Outlier — IQR]** Spec-Step `{"type": "outlier_handling", "params": {"method": "iqr"}}` identifiziert Ausreißer (außerhalb 1,5×IQR) anhand der Trainingsdaten (`fit`) und behandelt sie im gesamten Datensatz (`transform`). Bei `method: "zscore"` → Z-Score-Grenzwert (Standard: 3). Anzahl behandelter Ausreißer wird im Run-Ergebnis gespeichert.

4. **[fit/transform-Grenze — Imputation]** `fit()` berechnet Median/Mean/Mode ausschließlich auf Trainingsdaten. `transform()` verwendet diese Parameter — keine Neuberechnung auf Testdaten.

5. **[fit/transform-Grenze — Outlier]** IQR-Grenzen / Z-Score-Parameter werden ausschließlich auf Trainingsdaten berechnet. `transform()` wendet die gelernten Grenzen auf Train und Test an.

6. **[Registry]** Alle drei Steps sind über `@register_step` registriert und erscheinen nach Service-Start automatisch in der Registry.

7. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [ ] **T1 — Abhängigkeiten ergänzen** (AC: 2, 3)
  - [ ] `requirements.txt`: `scikit-learn>=1.4`, `scipy>=1.12` (für Z-Score)
  - [ ] `uv pip install -r requirements-dev.txt`

- [ ] **T2 — DeduplicationStep** (AC: 1, 6)
  - [ ] `src/gysi_ml/steps/preprocessing/dedup.py` anlegen
  - [ ] `@register_step("dedup")` `class DeduplicationStep(BaseStep):`
  - [ ] `description = "Entfernt exakt duplizierte Zeilen aus dem Datensatz"`
  - [ ] `param_schema = {}` (keine Parameter)
  - [ ] `fit(df_train)`: speichert nichts (kein gelernter State nötig)
  - [ ] `transform(df_train, df_test)`: entfernt Duplikate aus beiden Splits (`.drop_duplicates()`)
  - [ ] `get_metadata()`: gibt `{"removed_duplicates": <int>}` zurück
  - [ ] Wenn Dedup vor dem Split aufgerufen wird (auf `df_full`): nur ein DataFrame-Argument (Executor-Kompatibilität via `df_test=None`)

- [ ] **T3 — ImputationStep** (AC: 2, 4, 6)
  - [ ] `src/gysi_ml/steps/preprocessing/imputation.py` anlegen
  - [ ] `@register_step("impute_missing")` `class ImputationStep(BaseStep):`
  - [ ] `description = "Imputiert fehlende Werte numerischer Spalten"`
  - [ ] `param_schema = {"strategy": {"type": "string", "enum": ["median", "mean", "most_frequent"], "default": "median"}}`
  - [ ] `__init__(self, params: dict)`: liest `strategy` aus params (Default: `"median"`)
  - [ ] `fit(df_train)`: berechnet pro numerischer Spalte den Impute-Wert → speichert in `self._fill_values: dict[str, float]`
  - [ ] `transform(df_train, df_test)`: wendet `_fill_values` auf beide Splits an (`.fillna()`)
  - [ ] `get_metadata()`: gibt `{"imputed_values_per_column": {"col": count, ...}}` zurück (Anzahl imputierter Werte je Spalte je Split)

- [ ] **T4 — OutlierHandlingStep** (AC: 3, 5, 6)
  - [ ] `src/gysi_ml/steps/preprocessing/outlier_handling.py` anlegen
  - [ ] `@register_step("outlier_handling")` `class OutlierHandlingStep(BaseStep):`
  - [ ] `description = "Behandelt Ausreißer via IQR oder Z-Score"`
  - [ ] `param_schema = {"method": {"type": "string", "enum": ["iqr", "zscore"], "default": "iqr"}, "zscore_threshold": {"type": "number", "default": 3.0}}`
  - [ ] `fit(df_train)`:
    - IQR: berechnet Q1, Q3, IQR-Grenzen (1.5×IQR) pro numerischer Spalte → `self._bounds: dict[str, tuple[float, float]]`
    - Z-Score: berechnet `mean` und `std` pro numerischer Spalte → `self._stats`
  - [ ] `transform(df_train, df_test)`: Ausreißer werden auf Grenzwerte geclipt (Winsorization — kein Zeilenentfernen, da sonst Train/Test-Größen inkonsistent werden)
  - [ ] `get_metadata()`: gibt `{"outliers_treated": <int>}` zurück (Summe über beide Splits)

- [ ] **T5 — Preprocessing-Paket registrieren** (AC: 6)
  - [ ] `src/gysi_ml/steps/preprocessing/__init__.py`: importiert alle drei Modules damit die `@register_step`-Decorators beim Import ausgeführt werden
  - [ ] `src/gysi_ml/steps/__init__.py`: importiert `preprocessing`-Paket (Sicherstellung Auto-Discovery)

- [ ] **T6 — Executor: Steps Before/After Split** (AC: 4, 5)
  - [ ] `executor.py` anpassen: `DeduplicationStep` kann vor dem Split auf `df_full` arbeiten (ist stateless)
  - [ ] Für `ImputationStep` und `OutlierHandlingStep`: Executor prüft ob `context.is_split == True` bevor er sie aufruft — falls nicht, strukturierten Fehler zurückgeben: `{"error": "split_required", "detail": "Step 'impute_missing' benötigt einen vorherigen 'split'-Step"}`
  - [ ] Diese Prüfung ist Teil des Executors, nicht des Steps selbst

- [ ] **T7 — Unit Tests** (AC: 1–6, 7)
  - [ ] `tests/unit/preprocessing/test_dedup.py`: mit/ohne Duplikate, Metadata
  - [ ] `tests/unit/preprocessing/test_imputation.py`: alle drei Strategien, fit-only-auf-Train, transform-auf-Test, Metadata
  - [ ] `tests/unit/preprocessing/test_outlier_handling.py`: IQR + Z-Score, Capping-Verhalten, Metadata
  - [ ] Testdaten: kleine synthetische DataFrames (kein echter bikes.csv-Zugriff in Unit Tests)

- [ ] **T8 — Integration Test (Executor + Steps)** (AC: 1–6, 7)
  - [ ] `tests/integration/test_preprocessing_pipeline.py`
  - [ ] Vollständige Spec: `[dedup, split, impute_missing, outlier_handling]` auf bikes.csv
  - [ ] Prüft Run-Status `completed`, prüft Step-Metadaten im Ergebnis

## Dev Notes

### Zielstruktur nach dieser Story

```
backend/src/gysi_ml/steps/
├── base.py                          # aus Story 1.2
├── registry.py                      # aus Story 1.2
├── __init__.py                      # NEU: importiert preprocessing/
└── preprocessing/
    ├── __init__.py                  # NEU: importiert dedup, imputation, outlier_handling
    ├── dedup.py                     # NEU: DeduplicationStep
    ├── imputation.py                # NEU: ImputationStep
    └── outlier_handling.py          # NEU: OutlierHandlingStep
```

Tests:
```
backend/tests/unit/preprocessing/
├── __init__.py                      # NEU
├── test_dedup.py                    # NEU
├── test_imputation.py               # NEU
└── test_outlier_handling.py         # NEU
```

### fit/transform-Grenze — Kernregel (NFR-M1, NFR-T2)

```
df_full  →  [dedup]  →  [split]  →  df_train / df_test
                                         │
                          fit(df_train) ─┘  ← NUR Trainingsdaten!
                          transform(df_train, df_test)  ← beide Splits
```

**Niemals `fit()` auf Testdaten!** Der Executor erzwingt dies (Story 1.2 / T6 dieser Story).

### Bikes-Datensatz — bekannte fehlende Werte

Gemäß Projektspezifikation wurden künstlich fehlende Werte eingebracht:
- `mnth` (Monat): einige Zeilen fehlen
- `weathersit` (Wettersituation): einige Zeilen fehlen

Der `ImputationStep` soll diese Spalten zuverlässig behandeln.

### Outlier-Behandlung: Capping statt Entfernen

Ausreißer werden **geclipt** (Winsorization), nicht entfernt. Begründung:
- Zeilenentfernung würde Train- und Test-Größen inkonsistent machen
- Für Regressionsmodelle ist Capping stabiler
- Implementierung: `df.clip(lower=lower_bound, upper=upper_bound)` pro Spalte

### Strategie für `most_frequent` bei numerischen Spalten

`most_frequent` ist primär für kategorische Spalten gedacht, kann aber auch auf numerische Spalten angewendet werden (häufigster Wert aus `value_counts().idxmax()`).

### Step-Parameter-Defaults

Steps sollen defensiv mit fehlenden Params umgehen:
```python
def __init__(self, params: dict):
    self.strategy = params.get("strategy", "median")
```

### Wichtig: Steps-Import beim App-Start

Damit alle `@register_step`-Decorators beim Serverstart ausgeführt werden, muss in `api/app.py`:
```python
import gysi_ml.steps  # triggert alle __init__.py-Importe und damit die Registrierungen
```
Dieser Import muss **vor** dem Executor-Aufruf stehen.

### Referenzen

- [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 1.3]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#FR17, FR18, FR19]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#NFR-M1, NFR-T2]
- [Source: backend/AGENTS.md#Pipeline-Scope Preprocessing]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

- scikit-learn und scipy frisch installiert (waren nicht im venv).
- `executor.py` lines 50-59 (data-load-Fehlerast): unverändert aus Story 1.2, keine echte bikes.csv in Tests.
- `imputation.py` line 43, `outlier_handling.py` lines 52/64: `most_frequent`-Pfad bzw. `zscore`-Sonderfall (std==0) nicht durch alle Testpfade abgedeckt → Coverage 96% ≥ 85% ✅.
- Minimaler `SplitStep` in `steps/preprocessing/split.py` implementiert (T6/T8), wird in Story 1.5 vollständig ausgebaut.
- `requires_split` + `is_splitter` als neue Klassen-Attribute in `BaseStep` ergänzt (kein Breaking Change zu Story 1.2).

### Completion Notes List

- T1: `scikit-learn>=1.4` + `scipy>=1.12` in requirements.txt, installiert via pip.
- T2: `dedup.py` — DeduplicationStep, `requires_split=False`, zählt entfernte Duplikate.
- T3: `imputation.py` — ImputationStep, `requires_split=True`, median/mean/most_frequent, fit-on-train only.
- T4: `outlier_handling.py` — OutlierHandlingStep, `requires_split=True`, IQR+Z-Score Capping.
- T5: `steps/preprocessing/__init__.py` importiert alle 4 Step-Module; `steps/__init__.py` importiert preprocessing-Paket; `api/app.py` importiert `gysi_ml.steps` beim Start.
- T6: BaseStep + `requires_split`/`is_splitter`; Executor prüft `requires_split` → split_required; Executor erkennt `is_splitter` → setzt context.df_train/df_test/is_split. Minimaler `SplitStep` angelegt.
- T7: 38 neue Unit-Tests (dedup: 10, imputation: 13, outlier: 15) — alle grün.
- T8: 7 Integrationstests (dedup-only, split_required-Fehler, vollständige Pipeline) — alle grün.
- Ergebnis: **108/108 Tests grün, Coverage 96%** ✅

### File List

- `backend/requirements.txt` — GEÄNDERT (+ scikit-learn, scipy)
- `backend/src/gysi_ml/steps/base.py` — GEÄNDERT (+ requires_split, is_splitter)
- `backend/src/gysi_ml/steps/__init__.py` — GEÄNDERT (+ preprocessing import)
- `backend/src/gysi_ml/steps/preprocessing/__init__.py` — GEÄNDERT (+ alle Step-Imports)
- `backend/src/gysi_ml/steps/preprocessing/dedup.py` — NEU
- `backend/src/gysi_ml/steps/preprocessing/imputation.py` — NEU
- `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py` — NEU
- `backend/src/gysi_ml/steps/preprocessing/split.py` — NEU (minimal, Story 1.5 baut aus)
- `backend/src/gysi_ml/executor/executor.py` — GEÄNDERT (+ requires_split-Check, is_splitter-Handling)
- `backend/src/gysi_ml/api/app.py` — GEÄNDERT (+ import gysi_ml.steps)
- `backend/tests/unit/preprocessing/__init__.py` — NEU
- `backend/tests/unit/preprocessing/test_dedup.py` — NEU
- `backend/tests/unit/preprocessing/test_imputation.py` — NEU
- `backend/tests/unit/preprocessing/test_outlier_handling.py` — NEU
- `backend/tests/integration/test_preprocessing_pipeline.py` — NEU
