# Story 1.4: Preprocessing Steps — Encoding, Correlation Filter, Rare Category und Time-Features

Status: done

## Story

Als ein Datenwissenschaftler,
möchte ich kategorische Features encodieren, hochkorrelierte Features filtern, seltene Kategorien bündeln und Datums-Features ableiten lassen,
damit der Datensatz vollständig für baumorientierte Modelle (Decision Tree, EBM) vorbereitet ist.

## Acceptance Criteria

1. **[Label Encoding]** Spec-Step `{"type": "encode_categorical", "params": {"method": "label"}}` transformiert kategorische Spalten mit Label Encoding (`fit` nur auf Train). Bei `method: "onehot"` → One-Hot Encoding. Unbekannte Kategorien im Test-Set → `-1` (Label) bzw. Null-Vektor (One-Hot).

2. **[Correlation Filter]** Spec-Step `{"type": "correlation_filter", "params": {"threshold": 0.9}}` entfernt Features mit Pearson-Korrelation ≥ Schwellwert. Grenzwert wird auf Trainingsdaten berechnet. Entfernte Features werden im Run-Ergebnis namentlich gelistet.

3. **[Rare Category Bucketing]** Spec-Step `{"type": "rare_category_bucketing", "params": {"min_frequency": 0.01}}` ersetzt Kategorien mit relativer Häufigkeit < `min_frequency` (berechnet auf Trainingsdaten) durch `"__rare__"`.

4. **[Time Feature Encoding]** Spec-Step `{"type": "time_feature_encoding", "params": {"column": "dteday"}}` leitet aus `dteday` (ISO-Datum) den Wochentag als Integer (0=Montag) und den Monat als Integer (1–12) ab. Die ursprüngliche `dteday`-Spalte wird entfernt.

5. **[fit/transform-Grenze]** `fit()` für alle Steps ausschließlich auf Trainingsdaten. `transform()` verwendet gelernte Parameter — keine Neuberechnung auf Testdaten.

6. **[Registry]** Alle vier Steps sind über `@register_step` registriert.

7. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — CategoricalEncodingStep** (AC: 1, 5, 6)
  - [x] `src/gysi_ml/steps/preprocessing/encoding.py` anlegen
  - [x] `@register_step("encode_categorical")` `class CategoricalEncodingStep(BaseStep):`
  - [x] `description = "Encodiert kategorische Features (Label oder One-Hot)"`
  - [x] `param_schema = {"method": {"type": "string", "enum": ["label", "onehot"], "default": "label"}}`
  - [x] `fit(df_train)`:
    - Automatisch kategorische Spalten erkennen: `df.select_dtypes(include=["object", "category"])`
    - Label: `self._label_encoders: dict[str, dict]` — Mapping `category → int` pro Spalte (aus Trainingsdaten)
    - One-Hot: `self._onehot_categories: dict[str, list]` — Liste bekannter Kategorien pro Spalte
  - [x] `transform(df_train, df_test)`:
    - Label: unbekannte Kategorien → `-1` (kein Fehler)
    - One-Hot: nur für bekannte Kategorien Spalten anlegen; unbekannte Kategorien → Zeile erhält alle 0
    - **Kein** `sklearn.LabelEncoder` — eigene dict-basierte Implementierung (kein externer State der serialisiert werden müsste, einfacher testbar)
  - [x] `get_metadata()`: gibt `{"encoded_columns": [..."]}` zurück

- [x] **T2 — CorrelationFilterStep** (AC: 2, 5, 6)
  - [x] `src/gysi_ml/steps/preprocessing/correlation_filter.py` anlegen
  - [x] `@register_step("correlation_filter")` `class CorrelationFilterStep(BaseStep):`
  - [x] `description = "Entfernt hochkorrelierte numerische Features (Pearson)"`
  - [x] `param_schema = {"threshold": {"type": "number", "default": 0.9}}`
  - [x] `fit(df_train)`:
    - Berechnet Pearson-Korrelationsmatrix auf `df_train` (nur numerische Spalten)
    - Identifiziert Paare mit `|corr| >= threshold`
    - Wählt für jedes Paar ein Feature zum Entfernen (das zweite im Paar — deterministisch)
    - Speichert `self._features_to_drop: list[str]`
  - [x] `transform(df_train, df_test)`: entfernt `_features_to_drop` aus beiden Splits (`.drop(columns=...)`)
  - [x] `get_metadata()`: gibt `{"dropped_features": [...]}` zurück

- [x] **T3 — RareCategoryBucketingStep** (AC: 3, 5, 6)
  - [x] `src/gysi_ml/steps/preprocessing/rare_category.py` anlegen
  - [x] `@register_step("rare_category_bucketing")` `class RareCategoryBucketingStep(BaseStep):`
  - [x] `description = "Bündelt seltene Kategorien zu '__rare__'"`
  - [x] `param_schema = {"min_frequency": {"type": "number", "default": 0.01}}`
  - [x] `fit(df_train)`:
    - Pro kategorischer Spalte: relative Häufigkeiten berechnen (auf df_train)
    - Speichert `self._rare_categories: dict[str, set[str]]` — Kategorien unter min_frequency
  - [x] `transform(df_train, df_test)`: ersetzt seltene Kategorien durch `"__rare__"` in beiden Splits
  - [x] `get_metadata()`: gibt `{"rare_categories_per_column": {"col": count, ...}}` zurück

- [x] **T4 — TimeFeatureEncodingStep** (AC: 4, 6)
  - [x] `src/gysi_ml/steps/preprocessing/time_features.py` anlegen
  - [x] `@register_step("time_feature_encoding")` `class TimeFeatureEncodingStep(BaseStep):`
  - [x] `description = "Leitet Wochentag und Monat aus Datumsspalte ab"`
  - [x] `param_schema = {"column": {"type": "string", "default": "dteday"}}`
  - [x] `fit(df_train)`: kein State zu lernen — speichert nur `self._column`
  - [x] `transform(df_train, df_test)`:
    - Liest `params["column"]` (Default: `"dteday"`)
    - Konvertiert Spalte zu `pd.Timestamp` via `pd.to_datetime`
    - Erzeugt `weekday` (0=Montag, `.dt.dayofweek`) und `month` (1–12, `.dt.month`)
    - Entfernt Original-Spalte (`dteday`) aus beiden Splits
  - [x] `get_metadata()`: gibt `{"derived_features": ["weekday", "month"], "dropped_column": "dteday"}` zurück
  - [x] Hinweis: `TimeFeatureEncodingStep` kann **vor** dem Split ausgeführt werden (kein `fit`-State nötig) — Executor behandelt ihn wie `DeduplicationStep`

- [x] **T5 — Preprocessing-Paket erweitern** (AC: 6)
  - [x] `src/gysi_ml/steps/preprocessing/__init__.py`: neue Modules importieren
    ```python
    from . import dedup, imputation, outlier_handling  # aus Story 1.3
    from . import encoding, correlation_filter, rare_category, time_features  # NEU
    ```

- [x] **T6 — Unit Tests** (AC: 1–6, 7)
  - [x] `tests/unit/preprocessing/test_encoding.py`: Label + One-Hot, unbekannte Kategorien, fit-nur-auf-Train
  - [x] `tests/unit/preprocessing/test_correlation_filter.py`: hochkorrelierte Features werden entfernt, Threshold-Grenzwerte
  - [x] `tests/unit/preprocessing/test_rare_category.py`: seltene Kategorien → `"__rare__"`, Frequenzgrenze
  - [x] `tests/unit/preprocessing/test_time_features.py`: Wochentag/Monat korrekt, `dteday` entfernt

- [x] **T7 — Integration Test** (AC: 1–6, 7)
  - [x] `tests/integration/test_full_preprocessing_pipeline.py`
  - [x] Vollständige Spec auf bikes.csv: `[dedup, time_feature_encoding, split, impute_missing, outlier_handling, rare_category_bucketing, correlation_filter, encode_categorical]`
  - [x] Prüft: Run `completed`, alle Step-Metadaten vorhanden, `dteday` nicht mehr im df_train

## Dev Notes

### Zielstruktur nach dieser Story

```
backend/src/gysi_ml/steps/preprocessing/
├── __init__.py                      # + encoding, correlation_filter, rare_category, time_features
├── dedup.py                         # aus Story 1.3
├── imputation.py                    # aus Story 1.3
├── outlier_handling.py              # aus Story 1.3
├── encoding.py                      # NEU: CategoricalEncodingStep
├── correlation_filter.py            # NEU: CorrelationFilterStep
├── rare_category.py                 # NEU: RareCategoryBucketingStep
└── time_features.py                 # NEU: TimeFeatureEncodingStep
```

### Bikes-Datensatz — kategorische Features

Bekannte kategorische Spalten (typ `object` oder explizit):
- `season` (1–4), `mnth` (1–12), `holiday`, `weekday`, `workingday`, `weathersit`
- `dteday` — wird durch `TimeFeatureEncodingStep` zu `weekday` + `month` expandiert und dann entfernt

> ⚠️ `dteday` enthält redundante Information mit `mnth` und `weekday` aus dem bikes.csv. Nach `time_feature_encoding` ist `dteday` zu entfernen.

### Empfohlene Spec-Reihenfolge für vollständige Pipeline

```json
[
  {"type": "dedup"},
  {"type": "time_feature_encoding", "params": {"column": "dteday"}},
  {"type": "split", "params": {"test_size": 0.2, "random_state": 42}},
  {"type": "impute_missing", "params": {"strategy": "median"}},
  {"type": "outlier_handling", "params": {"method": "iqr"}},
  {"type": "rare_category_bucketing", "params": {"min_frequency": 0.01}},
  {"type": "correlation_filter", "params": {"threshold": 0.9}},
  {"type": "encode_categorical", "params": {"method": "label"}}
]
```

### Eigene Encoder statt sklearn

Für `CategoricalEncodingStep` wird **keine** `sklearn.LabelEncoder` verwendet, sondern ein eigenes dict-Mapping. Begründung:
- Kein sklearn-Serialisierungsoverhead
- Einfacher testbar (reiner Python-Dict)
- Unbekannte Kategorien direkt kontrollierbar (`-1` statt Exception)

Beispiel Label-Mapping:
```python
self._label_encoders = {
    "season": {"spring": 0, "summer": 1, "fall": 2, "winter": 3}
}
# transform: df[col].map(_label_encoders[col]).fillna(-1).astype(int)
```

### One-Hot Encoding: Spalten-Konsistenz sicherstellen

Nach `fit()` ist `self._onehot_categories` bekannt. Im `transform()`:
- Für Train: `pd.get_dummies(df_train[col])` — alle bekannten Kategorien als Spalten
- Für Test: `pd.get_dummies(df_test[col]).reindex(columns=known_cols, fill_value=0)`

Wichtig: Die Spaltenreihenfolge muss identisch sein (sonst scheitert Modelltraining in Epic 2).

### Correlation Filter — Determinismus

Bei mehreren korrelierten Paaren wird deterministisch nach Spalten-Reihenfolge entschieden (das alphabetisch spätere Feature eines Paares wird entfernt). Kein zufälliger Auswahlmechanismus.

### TimeFeatureEncodingStep — Pre-Split-Ausführung

`TimeFeatureEncodingStep` lernt nichts aus dem Datensatz (`fit()` ist no-op). Er kann daher vor dem Split-Step ausgeführt werden. Der Executor erkennt das an `step.stateless = True` (optionales Klassenattribut in BaseStep).

### Referenzen

- [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 1.4]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#FR20, FR21, FR22, FR23]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#NFR-M1, NFR-M2]
- [Source: backend/AGENTS.md#Pipeline-Scope Preprocessing]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

Keine Blocker. Alle 4 Steps wurden ohne Abweichungen von der Story-Spec implementiert.

### Completion Notes List

- **T1 CategoricalEncodingStep**: Eigene dict-Implementierung (kein sklearn). Label: sortiertes Alphabet-Mapping, unbekannt → -1. One-Hot: `pd.get_dummies` + `reindex` für konsistente Spaltenreihenfolge. 18 Unit-Tests: 95% Coverage.
- **T2 CorrelationFilterStep**: Pearson-Korrelationsmatrix aus Trainingsdaten, oberes Dreieck iteriert. Deterministisch: `max(col_a, col_b)` = alphabetisch späteres Feature wird entfernt. 14 Unit-Tests: 94% Coverage.
- **T3 RareCategoryBucketingStep**: `value_counts(normalize=True)` auf Trainingsdaten. Kategorien < `min_frequency` → `__rare__`. Unbekannte Test-Kategorien bleiben unverändert. 14 Unit-Tests: 100% Coverage.
- **T4 TimeFeatureEncodingStep**: Stateless (`fit` ist No-Op). Läuft vor Split auf `df_full`. `pd.to_datetime` + `.dt.dayofweek` (0=Montag) + `.dt.month`. Graceful handling wenn Spalte fehlt. 17 Unit-Tests: 100% Coverage.
- **T5**: `__init__.py` mit allen 4 neuen Modulen erweitert.
- **T6**: 63 Unit-Tests — alle grün.
- **T7**: 9 Integration-Tests inkl. `split_required`-Prüfungen für T1–T3, `dteday`-Entfernung via Metadaten, Korrelations-Drop von `cnt_dup`.
- Vollständige Regressionssuite: **180/180 Tests grün**.

### File List

- `src/gysi_ml/steps/preprocessing/encoding.py` (neu)
- `src/gysi_ml/steps/preprocessing/correlation_filter.py` (neu)
- `src/gysi_ml/steps/preprocessing/rare_category.py` (neu)
- `src/gysi_ml/steps/preprocessing/time_features.py` (neu)
- `src/gysi_ml/steps/preprocessing/__init__.py` (geändert)
- `tests/unit/preprocessing/test_encoding.py` (neu)
- `tests/unit/preprocessing/test_correlation_filter.py` (neu)
- `tests/unit/preprocessing/test_rare_category.py` (neu)
- `tests/unit/preprocessing/test_time_features.py` (neu)
- `tests/integration/test_full_preprocessing_pipeline.py` (neu)
- `tests/unit/preprocessing/test_encoding.py` (aktualisiert — int-Dtype-Test)

## Change Log

- 2026-03-15: Story implementiert (Amelia / Claude Sonnet 4.6) — CategoricalEncodingStep, CorrelationFilterStep, RareCategoryBucketingStep, TimeFeatureEncodingStep, Preprocessing-Paket aktualisiert, 63 Unit-Tests + 9 Integration-Tests. 180/180 Tests grün. Status: ready-for-dev → review.
- 2026-03-15: Code Review abgeschlossen — H1 (Lambda late-binding defensive fix), M1 (One-Hot dtype=int explizit), L1 (Pandas4Warning behoben: select_dtypes auf ["object","category","string"] erweitert). 181/181 Tests grün. Status: review → done.
