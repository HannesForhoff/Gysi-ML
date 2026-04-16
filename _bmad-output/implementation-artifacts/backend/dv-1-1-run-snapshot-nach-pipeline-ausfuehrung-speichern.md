# Story DV-1.1: Run-Snapshot nach Pipeline-Ausführung speichern

Status: done

## Story

Als Entwickler,
möchte ich, dass nach jedem erfolgreichen Run der transformierte Datensatz als Parquet-Datei und die Spalten-Statistiken als JSON persistent gespeichert werden,
damit die Datenansicht im Frontend versionssicher den tatsächlichen Zustand nach jedem Run anzeigen kann.

## Acceptance Criteria

1. **[Parquet-Snapshot wird gespeichert]** Bei erfolgreichem Run (Status `completed`) existiert anschließend unter `artifacts/{run_id}_snapshot.parquet` eine valide Parquet-Datei.

2. **[Column-Stats werden gespeichert]** Bei erfolgreichem Run existiert unter `artifacts/{run_id}_column_stats.json` eine JSON-Datei mit Stats pro Spalte.

3. **[Numerische Spalten-Stats vollständig]** Für jede numerische Spalte enthält die JSON-Datei: `missing_count`, `missing_pct`, `distinct_count`, `distinct_pct`, `min`, `max`, `histogram` (mit `bins` und `counts`, je 10 Einträge).

4. **[is_split-Flag]** Die `column_stats.json` enthält ein Top-Level-Feld `"is_split": true|false`.

5. **[Fire-and-Forget]** Schlägt das Speichern des Snapshots fehl (z. B. Disk voll), wird der Run-Status trotzdem auf `completed` gesetzt — kein HTTP 500, der Fehler wird nur geloggt.

6. **[df_full wird gespeichert]** Der Snapshot enthält `df_full` — den vollständigen Datensatz im Preprocessing-Zustand vor einem ggf. durchgeführten Split.

7. **[Test-Coverage ≥ 85%]** `SnapshotService` ist mit einem minimalen Test-DataFrame testbar — kein echter Bike-Datensatz nötig.

## Tasks / Subtasks

- [x] **T1 — `services/snapshot_service.py` anlegen** (AC: 1–4, 6)
  - [x] Datei: `backend/src/gysi_ml/services/snapshot_service.py` (neu)
  - [x] Implementierung:

    ```python
    """SnapshotService — Datensatz-Snapshot nach Pipeline-Run (Story DV-1.1)."""
    from __future__ import annotations

    import json
    import logging
    from pathlib import Path

    import numpy as np
    import pandas as pd

    logger = logging.getLogger(__name__)


    class SnapshotService:
        def save_snapshot(
            self,
            run_id: str,
            df: pd.DataFrame,
            is_split: bool,
            artifacts_path: str,
        ) -> None:
            """Speichert Parquet-Snapshot und Column-Stats für einen abgeschlossenen Run.

            Wirft keine Exception — Fehler werden nur geloggt (fire-and-forget).
            Diese Methode ist der einzige Public Entry Point der Klasse.
            """
            base = Path(artifacts_path)
            base.mkdir(parents=True, exist_ok=True)

            parquet_path = base / f"{run_id}_snapshot.parquet"
            df.to_parquet(parquet_path, index=False)

            stats = _compute_column_stats(df, is_split=is_split)
            stats_path = base / f"{run_id}_column_stats.json"
            stats_path.write_text(json.dumps(stats, allow_nan=False), encoding="utf-8")


    def _compute_column_stats(df: pd.DataFrame, *, is_split: bool) -> dict:
        """Berechnet Spalten-Statistiken für alle Spalten des DataFrames.

        Numerische Spalten erhalten zusätzlich min, max und Histogramm (10 Bins).
        Nicht-numerische Spalten erhalten min=null, max=null, histogram=null.
        """
        n = len(df)
        columns: dict[str, dict] = {}

        for col in df.columns:
            series = df[col]
            missing_count = int(series.isna().sum())
            missing_pct = round(missing_count / n * 100, 4) if n else 0.0
            distinct_count = int(series.nunique(dropna=False))
            distinct_pct = round(distinct_count / n * 100, 4) if n else 0.0

            col_stats: dict = {
                "missing_count": missing_count,
                "missing_pct": missing_pct,
                "distinct_count": distinct_count,
                "distinct_pct": distinct_pct,
                "min": None,
                "max": None,
                "histogram": None,
            }

            numeric_series = pd.to_numeric(series, errors="coerce").dropna()
            if not numeric_series.empty:
                col_stats["min"] = float(numeric_series.min())
                col_stats["max"] = float(numeric_series.max())
                counts, bin_edges = np.histogram(numeric_series, bins=10)
                col_stats["histogram"] = {
                    "bins": [round(float(b), 6) for b in bin_edges.tolist()],
                    "counts": counts.tolist(),
                }

            columns[col] = col_stats

        return {"is_split": is_split, "columns": columns}
    ```

- [x] **T2 — `executor.py` anpassen** (AC: 1, 5)
  - [x] Datei: `backend/src/gysi_ml/executor/executor.py`
  - [x] `import logging` auf Modulebene ergänzen
  - [x] `logger = logging.getLogger(__name__)` auf Modulebene (nach den Imports) ergänzen
  - [x] Import ergänzen: `from gysi_ml.services.snapshot_service import SnapshotService`
  - [x] **Eingriffspunkt:** in `_run_pipeline()`, nach `run_repository.update_run_status(..., status="completed")`, **VOR dem `return`**:

    ```python
    # 8. Snapshot speichern (fire-and-forget — darf Run nicht zum Scheitern bringen)
    try:
        SnapshotService().save_snapshot(
            run_id=run_id,
            df=context.df_full,
            is_split=context.is_split,
            artifacts_path=self._artifacts_path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Snapshot konnte nicht gespeichert werden (run_id=%s): %s", run_id, exc)
    ```

  - [x] ⚠️ Der return-Block BLEIBT unverändert:

    ```python
    return {
        "run_id": run_id,
        "status": "completed",
        "result": result,
    }
    ```

- [x] **T3 — Unit-Tests anlegen** (AC: 7)
  - [x] Datei: `backend/tests/unit/test_snapshot_service.py` (neu)
  - [x] Folgende Tests:
    - `test_save_snapshot_creates_parquet`: `tmp_path`-Fixture, minimaler DataFrame → Parquet-Datei existiert und ist lesbar
    - `test_save_snapshot_creates_column_stats_json`: Column-Stats-JSON existiert und enthält Top-Level-Feld `is_split`
    - `test_column_stats_numeric_fields`: Numerische Spalte → `min`, `max` nicht null; `histogram["bins"]` hat 11 Einträge, `histogram["counts"]` hat 10 Einträge
    - `test_column_stats_missing_values`: DataFrame mit NaN → `missing_count` und `missing_pct` korrekt berechnet
    - `test_column_stats_is_split_true`: `is_split=True` → JSON-Datei enthält `"is_split": true`
    - `test_column_stats_non_numeric_column`: Nicht-numerische Spalte → `min`, `max`, `histogram` sind `None` in der deserialisierten JSON
    - `test_save_snapshot_creates_artifacts_dir`: Wenn `artifacts_path` noch nicht existiert → wird automatisch angelegt
    ✅ Alle 7 Tests PASSED

## Dev Notes

### Eingriffspunkt in `executor.py` — exakte Position

Der einzige Eingriff in bestehenden Code ist ein **rein additiver Block** in `_run_pipeline()`.
Aktuell sieht das Ende der Methode so aus (ab Zeile ~258):

```python
        # 7. Run auf completed setzen
        finished_at = _utc_now()
        result = {
            "step_results": context.step_results,
            "metrics": context.metrics,
            "artifacts": context.artifacts,
        }
        run_repository.update_run_status(
            run_id=run_id,
            status="completed",
            finished_at=finished_at,
            result_json=json.dumps(result),
            db_path=db_path,
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "result": result,
        }
```

**Nach der Änderung** wird der Snapshot-Call zwischen `update_run_status` und `return` eingefügt.
Run-Status-Update kommt immer **vor** dem Snapshot-Call → ein Snapshot-Fehler setzt den Status nicht zurück.

### Welches DataFrame wird gespeichert?

`context.df_full` wird stets gespeichert. Das ist der transformierte Datensatz:

- **Vor Split:** `df_full` wird durch jeden nicht-splitting Step (`context.df_full = result_train`) aktualisiert — enthält das Preprocessing-Ergebnis auf dem Gesamtdatensatz.
- **Nach Split:** der Split-Step setzt `context.is_split = True` und befüllt `context.df_train` / `context.df_test`, verändert aber `context.df_full` **nicht** — `df_full` bleibt der Zustand unmittelbar vor dem Split.

Quelle: `executor.py`, Zeilen ~191–208.

### JSON-Struktur `column_stats.json`

```json
{
  "is_split": false,
  "columns": {
    "season": {
      "missing_count": 0,
      "missing_pct": 0.0,
      "distinct_count": 4,
      "distinct_pct": 0.023,
      "min": 1.0,
      "max": 4.0,
      "histogram": {
        "bins": [1.0, 1.3, 1.6, 1.9, 2.2, 2.5, 2.8, 3.1, 3.4, 3.7, 4.0],
        "counts": [4394, 0, 0, 4409, 0, 0, 4496, 0, 0, 4080]
      }
    },
    "dteday": {
      "missing_count": 0,
      "missing_pct": 0.0,
      "distinct_count": 731,
      "distinct_pct": 4.206,
      "min": null,
      "max": null,
      "histogram": null
    }
  }
}
```

### Histogramm-Details

`np.histogram(numeric_series, bins=10)` liefert:
- `bin_edges`: 11 Float-Werte (Grenzen der 10 Bins)
- `counts`: 10 Integer-Werte (Häufigkeiten je Bin)

Bike-Datensatz hat keine fehlenden Werte (laut Profiling-Story 7.1: "Keine fehlenden Werte ✅").
Falls Preprocessing-Steps NaN erzeugen, werden diese per `.dropna()` vor der Histogramm-Berechnung herausgefiltert.

### `allow_nan=False` in JSON-Serialisierung

Python's Standard-`json.dumps` serialisiert `float('nan')` als `NaN` (invalides JSON-Literal).
`allow_nan=False` erzwingt valides JSON und wirft einen `ValueError` wenn unerwartet NaN entsteht.
Da wir `.dropna()` vor Histogramm-Berechnung ausführen, tritt dieser Fall praktisch nicht auf —
das Flag dient als Sicherheitsnetz und Kommunikationskonvention.

### Artifact-Naming-Konvention

```
artifacts/{run_id}_snapshot.parquet
artifacts/{run_id}_column_stats.json
```

Konsistent mit dem bestehenden Pattern in `executor.py` (z. B. Plots von Modeling-Steps).
`artifacts_path` kommt aus `PipelineExecutor.__init__` (`self._artifacts_path`, Default: `"../artifacts"`).
Laut `config.py`: `Settings.artifacts_path = "../artifacts"`.

### Project Structure Notes

```
backend/src/gysi_ml/
├── executor/
│   └── executor.py               ← MODIFIZIEREN: 3 Änderungen (logging, Import, fire-and-forget-Block)
└── services/
    ├── command_service.py         ← Referenz für Service-Struktur
    ├── message_service.py
    ├── profiling_service.py       ← Referenz für Service-Pattern (ähnliche Struktur)
    └── snapshot_service.py        ← NEU ANLEGEN

backend/tests/unit/
└── test_snapshot_service.py       ← NEU ANLEGEN (Referenz: test_profiling_service.py)
```

Konventionen laut Architecture-Dokument:
- Service-Dateien: `services/<name>_service.py`, PascalCase-Klasse `SnapshotService`
- Private Hilfsfunktionen auf Modulebene mit `_`-Präfix: `_compute_column_stats`
- `snake_case` für Methoden: `save_snapshot`

### References

- [Source: _bmad-output/planning-artifacts/shared/epics-data-view-tab.md — Story DV-1.1 (Vollständige Anforderungen)]
- [Source: _bmad-output/planning-artifacts/shared/epics-data-view-tab.md — NFR-DV1 (fire-and-forget), NFR-DV2 (Parquet-Pfad)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Naming-Konventionen, Service-Pattern]
- [Source: backend/src/gysi_ml/executor/executor.py — _run_pipeline() Eingriffspunkt, df_full/is_split-Kontext]
- [Source: backend/src/gysi_ml/executor/pipeline_context.py — PipelineContext (df_full, is_split)]
- [Source: backend/src/gysi_ml/services/profiling_service.py — Service-Muster, Referenzimplementierung]
- [Source: backend/src/gysi_ml/config.py — artifacts_path Default-Wert]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- pyarrow bereits im venv (v23.0.1) vorhanden — fehlende requirements.txt-Deklaration ergänzt
- 3 pre-existing Integrationstests schlagen weiterhin fehl (LLM-Auth, EBM-Content-Type) — kein Zusammenhang mit DV-1.1

### Completion Notes List

- T1: `SnapshotService.save_snapshot()` und `_compute_column_stats()` implementiert gemäß Story-Spec
- T2: `executor.py` um `import logging`, `logger`, SnapshotService-Import und fire-and-forget-Block erweitert
- T3: 7 Unit-Tests — alle 7 PASSED (100 %); kein echter Bike-Datensatz benötigt
- AC 1–7 vollständig erfüllt; Regression-Suite: 527 passed (3 pre-existing failures unverändert)
- Code Review (2026-04-14): M1 Docstring korrigiert (fire-and-forget-Zusage entfernt), M2 Debug-Logging ergänzt, M3 Subtask-Checkbox korrigiert, M4 pyarrow in pyproject.toml deklariert

### File List

- `backend/src/gysi_ml/services/snapshot_service.py` (neu, modifiziert durch Code Review)
- `backend/src/gysi_ml/executor/executor.py` (modifiziert)
- `backend/tests/unit/test_snapshot_service.py` (neu)
- `backend/requirements.txt` (modifiziert — pyarrow>=15.0 ergänzt)
- `backend/pyproject.toml` (modifiziert — pyarrow>=15.0 in dependencies ergänzt)

## Change Log

- 2026-04-14: DV-1.1 implementiert — SnapshotService (Parquet + Column-Stats), fire-and-forget in executor.py, 7 Unit-Tests (Claude Sonnet 4.6)
- 2026-04-14: Code Review abgeschlossen — 4 Medium-Issues gefixed, Status → done (Claude Sonnet 4.6)
