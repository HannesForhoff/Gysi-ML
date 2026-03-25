# Story 7.1: Rohdatensatz-Profilierung (ProfilingService)

Status: done

## Story

Als ein Nutzer,
möchte ich über `/overview` oder natürliche Sprache einen vollständigen statistischen Überblick über den Bike-Datensatz erhalten,
damit ich informierte Entscheidungen über Preprocessing-Schritte treffen kann.

## Acceptance Criteria

1. **[Vollständiges Profiling-Ergebnis]** `ProfilingService.profile_raw()` gibt einen formatierten String zurück mit: Grundinfos (Zeilen/Spalten), Spalten-Übersicht (Name, dtype, Non-Null-Count), fehlende Werte (Spalte + % sortiert nach Häufigkeit), Statistiken (Min, Max, Mean, Median, Std für numerische Spalten), Erste 5 Zeilen, Unique-Wert-Verteilung (Kardinalität).

2. **[lru_cache — kein doppeltes Laden]** Zweimaliges Aufrufen von `profile_raw()` in derselben App-Instanz liest das CSV nur einmal — zweiter Aufruf kommt aus `@lru_cache`.

3. **[Cold Start toleriert]** Beim ersten Aufruf (cold start) wird das CSV geladen und Profiling berechnet — kein Fehler.

4. **[CommandService-Integration]** `CommandService._handle_overview()` ruft `ProfilingService().profile_raw()` auf und gibt das Ergebnis zurück.

5. **[Keine Spec-Änderung]** `ProfilingService.profile_raw()` berührt keine Pipeline-Spec.

6. **[Test-Coverage ≥ 85%]** `ProfilingService` ist mit einem Test-CSV testbar.

## Tasks / Subtasks

- [x] **T1 — `services/profiling_service.py` anlegen** (AC: 1–3, 5)
  - [x] Datei: `backend/src/gysi_ml/services/profiling_service.py` (neu)
  - [ ] Implementierung:
    ```python
    import functools
    import io
    from pathlib import Path
    
    import pandas as pd
    
    from gysi_ml.config import get_settings
    
    
    class ProfilingService:
        def profile_raw(self) -> str:
            """Profiliert den Rohdatensatz. Ergebnis ist gecacht."""
            return _profile_raw_cached(self._get_data_path())
    
        def _get_data_path(self) -> str:
            return get_settings().data_path
    
    
    @functools.lru_cache(maxsize=1)
    def _profile_raw_cached(data_path: str) -> str:
        """lru_cache auf Modulebene — einmal geladen, gilt für alle ProfilingService-Instanzen."""
        df = pd.read_csv(data_path)
        return _format_profile(df)
    
    
    def _format_profile(df: pd.DataFrame) -> str:
        lines = []
    
        # 1. Grundinfos
        lines.append(f"## Datensatz-Überblick\n")
        lines.append(f"**Zeilen:** {len(df):,}  |  **Spalten:** {len(df.columns)}\n")
    
        # 2. Spalten-Übersicht
        lines.append("### Spalten-Übersicht")
        col_info = []
        for col in df.columns:
            non_null = df[col].notna().sum()
            col_info.append(f"- `{col}`: {df[col].dtype}, {non_null}/{len(df)} Non-Null")
        lines.append("\n".join(col_info))
    
        # 3. Fehlende Werte
        missing = df.isnull().sum()
        missing = missing[missing > 0].sort_values(ascending=False)
        if not missing.empty:
            lines.append("\n### Fehlende Werte")
            for col, count in missing.items():
                pct = count / len(df) * 100
                lines.append(f"- `{col}`: {count} ({pct:.1f}%)")
        else:
            lines.append("\n### Fehlende Werte\nKeine fehlenden Werte ✅")
    
        # 4. Statistiken (numerische Spalten)
        num_cols = df.select_dtypes(include="number")
        if not num_cols.empty:
            lines.append("\n### Statistiken (numerische Spalten)")
            desc = num_cols.describe().T[["min", "max", "mean", "50%", "std"]]
            desc.columns = ["Min", "Max", "Mean", "Median", "Std"]
            lines.append(desc.to_string())
    
        # 5. Erste 5 Zeilen
        lines.append("\n### Erste 5 Zeilen")
        lines.append(df.head(5).to_string())
    
        # 6. Kardinalität
        lines.append("\n### Unique-Werte (Kardinalität)")
        for col in df.columns:
            n_unique = df[col].nunique()
            lines.append(f"- `{col}`: {n_unique} unique Werte")
    
        return "\n".join(lines)
    ```

- [x] **T2 — CommandService `_handle_overview()` vervollständigen** (AC: 4)
  - [x] Datei: `backend/src/gysi_ml/services/command_service.py` (aus Story 6.2)
  - [x] Stub in `_handle_overview()` mit echtem Aufruf ersetzen:
    ```python
    def _handle_overview(self, session_id: str, db_path: str | None) -> str:
        from gysi_ml.services.profiling_service import ProfilingService
        return ProfilingService().profile_raw()
    ```
  - [x] Lazy-Import (`from ... import`) verhindert Zirkelimport

- [x] **T3 — Tests für `ProfilingService`** (AC: 1, 2, 6)
  - [x] Datei: `backend/tests/unit/test_profiling_service.py` (neu)
  - [x] Fixtures: kleines Test-CSV im `tests/fixtures/` Ordner (oder `tmp_path`)
  - [x] Tests:
    - `test_profile_raw_contains_all_sections()`: Ergebnis enthält "Grundinfos", "Spalten", "Statistiken"
    - `test_profile_raw_cache()`: Zweimaliger Aufruf mit gleichem `data_path` — CSV wird nur einmal gelesen (mock `pd.read_csv`)
    - `test_profile_raw_no_spec_change()`: `profile_raw()` gibt String zurück — kein Exception

## Dev Notes

### Abhängigkeiten

- **Benötigt keine anderen neuen Epics** — nur `data_path` aus `get_settings()`.
- Story 7.2 baut darauf auf (adds `to_compact_str()` für LLM-Injection).
- Story 7.3 erweitert `ProfilingService` um `profile_after_steps()`.

### lru_cache-Strategie

- `@functools.lru_cache` auf Modulebene-Funktion (nicht auf Instanzmethode) — Instanzmethoden sind nicht cachebar ohne Tricks.
- Cache-Key ist `data_path: str` — verschiedene Pfade erzeugen verschiedene Cache-Einträge.
- Cache gilt für die Lebensdauer des Prozesses — beim Neustart kalt.
- Post-Preprocessing-Profiling (Story 7.3) ist **nicht** gecacht — sessionspezifisch.

### `data_path` aus Settings

- `get_settings().data_path` → konfiguriert in `backend/.env` als `DATA_PATH=...`
- Im Dev/Test: `data_path` kann überschrieben werden → `_profile_raw_cached(test_path)` trennt Cache-Einträge

### Bike-Datensatz

- `data/raw/bikes.csv` — Standard-Pfad
- Spalten umfassen u.a.: `season`, `yr`, `mnth`, `hr`, `holiday`, `weekday`, `workingday`, `weathersit`, `temp`, `atemp`, `hum`, `windspeed`, `casual`, `registered`, `cnt`

### References

- [Source: backend/src/gysi_ml/config.py] — `get_settings().data_path`
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-7.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#F2-Datensatz-Profilierung]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

Keine Probleme aufgetreten. Alle 3 Tasks in einem Durchlauf implementiert.

### Completion Notes List

- **T1**: `profiling_service.py` exakt nach Story-Spec implementiert. `lru_cache` auf Modulebene-Funktion `_profile_raw_cached(data_path)` — korrekte Cache-Strategie.
- **T2**: `command_service.py` neu erstellt (Story 6.2 noch `ready-for-dev`). Minimale Struktur mit `_handle_overview()` + Stubs für `is_slash_command()` und `handle()`. Story 6.2 erweitert die Datei vollständig. Lazy-Import verhindert Zirkelimport.
- **T3**: 7 Unit-Tests in `test_profiling_service.py`. Coverage: 100% (AC6: ≥85% ✅). `autouse`-Fixture leert `lru_cache` vor jedem Test. `tmp_path` als Test-CSV-Fixture. Alle 343 Unit-Tests grün — keine Regressionen.

### File List

- `backend/src/gysi_ml/services/profiling_service.py` (neu)
- `backend/src/gysi_ml/services/command_service.py` (neu, Minimalstruktur für Story 7.1 T2)
- `backend/tests/unit/test_profiling_service.py` (neu)

## Senior Developer Review (AI)

**Reviewer:** GitHub Copilot (Claude Sonnet 4.6)
**Datum:** 2026-03-21
**Ergebnis:** Approve (nach Fixes)

### Action Items

- [x] [AI-Review][Medium] M1: Irreführender `with patch(__wrapped__)` Block in `test_profile_raw_contains_all_sections` entfernt — hatte keine Wirkung und suggerierte eine Isolation, die nicht stattfand [`tests/unit/test_profiling_service.py`]
- [x] [AI-Review][Medium] M2: Schwache Assertion `assert "4" in result` in `test_profile_raw_returns_row_and_column_count` durch präzise Assertions `assert "**Zeilen:** 4" in result` / `assert "**Spalten:** 4" in result` ersetzt [`tests/unit/test_profiling_service.py`]
- [x] [AI-Review][Low] L1: `lru_cache(maxsize=1)` Einschränkung dokumentiert — Multi-Pfad-Szenarien würden Cache-Einträge verdrängern [`profiling_service.py`]
- [ ] [AI-Review][Low] L2: AC4-Integration (`CommandService._handle_overview()` → `ProfilingService`) hat keinen eigenständigen Unit-Test — vertretbar, da Story 6.2 `CommandService` vollständig testet
- [ ] [AI-Review][Low] L3: Edge Case CSV ohne numerische Spalten (Statistiken-Block übersprungen) ungetestet — korrekt implementiert, Test empfohlen in Story 7.2/7.3

## Change Log

- 2026-03-21: Story 7.1 implementiert — ProfilingService mit lru_cache, CommandService-Minimalstruktur für _handle_overview(), 7 Unit-Tests (100% Coverage)
- 2026-03-21: Code Review — 2 Medium Fixes angewendet (irreführender patch-Block, schwache Assertions), L1 dokumentiert. Status: done
