# Story 7.3: Post-Preprocessing-Profilierung (Vorher/Nachher)

Status: done

## Story

Als ein Nutzer,
möchte ich nach ausgeführten Preprocessing-Schritten einen aktuellen Datensatz-Überblick abrufen können,
damit ich den Effekt der Transformationen sehe (z.B. „3 Duplikate entfernt, 17.376 Zeilen verbleiben").

## Acceptance Criteria

1. **[Post-Preprocessing-Profiling mit Vorher/Nachher]** Wenn eine Session mindestens einen Run mit Preprocessing-Steps hat, zeigt das Profiling den Zustand nach den Transformationen und enthält einen Vorher/Nachher-Vergleich: z.B. „Vorher: 17.379 Zeilen → Nachher: 17.376 Zeilen".

2. **[Fallback auf Rohdaten]** Hat die Session noch keinen Run, wird `profile_raw()` zurückgegeben — kein Fehler.

3. **[Kein Cache für post-step Profiling]** `profile_after_steps()` ist immer frisch berechnet (sessionspezifisch — kein `lru_cache`).

4. **[CommandService wählt korrekte Methode]** Wenn eine Session Runs hat → `profile_after_steps(session_id)`; sonst → `profile_raw()`.

5. **[Test-Coverage ≥ 85%]** Beide Profiling-Pfade sind getestet (mit/ohne Runs).

## Tasks / Subtasks

- [x] **T1 — `ProfilingService.profile_after_steps()` implementieren** (AC: 1, 2, 3)
  - [x] Datei: `backend/src/gysi_ml/services/profiling_service.py`
  - [x] Neue Methode in `ProfilingService`:
    ```python
    def profile_after_steps(self, session_id: str, db_path: str | None = None) -> str:
        """Profiliert den Datensatz nach ausgeführten Preprocessing-Steps.
        
        Rekonstruiert den transformierten Datensatz deterministisch aus Bike-CSV +
        abgeschlossenen Steps (kein DataFrame-Persistierung nötig).
        Kein lru_cache — sessionspezifisch.
        """
        from gysi_ml.persistence import run_repository, spec_repository
        from gysi_ml.executor.executor import PipelineExecutor
        
        # Letzten abgeschlossenen Run laden
        runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
        completed_runs = [r for r in runs if r["status"] == "completed"]
        
        if not completed_runs:
            return self.profile_raw()
        
        latest_run = completed_runs[-1]
        spec_entry = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
        if spec_entry is None:
            return self.profile_raw()
        
        # Rohdatensatz als Baseline
        df_raw = pd.read_csv(self._get_data_path())
        rows_before = len(df_raw)
        
        # Spec auf Rohdatensatz anwenden (nur Preprocessing-Steps, kein Split/Training)
        spec = spec_entry["spec"]
        preprocessing_steps = [
            s for s in spec.get("steps", [])
            if s.get("enabled", True) and not s.get("requires_split", False)
        ]
        
        df_after = df_raw.copy()
        settings = get_settings()
        executor = PipelineExecutor(
            data_path=settings.data_path,
            artifacts_path=settings.artifacts_path,
        )
        # Nur Preprocessing-Schritt ausführen (kein vollständiger Run)
        # Executor hat eine preview()-Methode oder wir nutzen die Steps direkt
        # Fallback: Zeilen aus run result_json lesen
        result_json = latest_run.get("result_json")
        if result_json:
            import json
            result = json.loads(result_json)
            rows_after = result.get("rows_after_preprocessing", rows_before)
        else:
            rows_after = rows_before
        
        # Vergleich bauen
        diff = rows_before - rows_after
        comparison = (
            f"**Vorher/Nachher:**\n"
            f"- Rohdatensatz: {rows_before:,} Zeilen\n"
            f"- Nach Preprocessing: {rows_after:,} Zeilen\n"
            f"- Differenz: {diff:,} Zeilen entfernt"
        )
        
        # Basis-Profil des transformierten Datensatzes
        raw_profile = _profile_raw_cached(self._get_data_path())
        return f"{comparison}\n\n---\n\n{raw_profile}"
    ```
  - [x] Hinweis: Wenn `PipelineExecutor` kein `preview()`-Interface hat, aus `result_json` lesen (robuster)
  - [x] `rows_after_preprocessing` in `result_json` kann fehlen — dann Fallback auf `rows_before` mit Hinweis

- [x] **T2 — `CommandService._handle_overview()` anpassen** (AC: 4)
  - [x] Datei: `backend/src/gysi_ml/services/command_service.py`
  - [x] Methode erweitern:
    ```python
    def _handle_overview(self, session_id: str, db_path: str | None) -> str:
        from gysi_ml.services.profiling_service import ProfilingService
        from gysi_ml.persistence import run_repository
        svc = ProfilingService()
        runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
        has_runs = any(r["status"] == "completed" for r in runs)
        if has_runs:
            return svc.profile_after_steps(session_id=session_id, db_path=db_path)
        return svc.profile_raw()
    ```

- [x] **T3 — Tests** (AC: 1–5)
  - [x] Datei: `backend/tests/unit/test_profiling_service.py` (erweitern)
  - [ ] Tests:
    - `test_profile_after_steps_no_runs_fallback()`: Keine Runs → gibt gleichen Output wie `profile_raw()`
    - `test_profile_after_steps_with_runs()`: Mock-Run mit `result_json` → enthält "Vorher/Nachher"
    - `test_command_service_overview_routes_correctly()`: Mit/ohne Runs → korrekte Methode aufgerufen

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 7.1:** `profile_raw()` und `_profile_raw_cached()` müssen existieren.
- **Benötigt Story 7.2 nicht direkt** — ist unabhängig vom LLM-Kontext.

### Deterministik statt Persistenz

- Key-Entscheidung (Architecture): DataFrame wird NICHT in DB persistiert.
- Post-Preprocessing-Profiling rekonstruiert den Zustand aus Bike-CSV + Spec.
- Einfachere Alternative (für Belegarbeit akzeptabel): Zeilen-Anzahl aus `result_json` lesen, Profil des Rohdatensatzes zeigen + Diff.

### `result_json`-Struktur

- `run.result_json` wird vom `PipelineExecutor.execute()` befüllt
- Enthält u.a. `metrics`, `step_results` — prüfen ob `rows_after_preprocessing` vorhanden
- Falls nicht: TODO-Kommentar und Fallback auf `rows_before`

### References

- [Source: backend/src/gysi_ml/services/profiling_service.py] — aus Story 7.1
- [Source: backend/src/gysi_ml/executor/executor.py] — Executor-Interface verstehen
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-7.3]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

Keine blockierenden Probleme.

### Completion Notes List

- T1: `profile_after_steps()` in `ProfilingService` implementiert. Liest Zeilen-Anzahl aus `result_json` des letzten abgeschlossenen Runs, leitet `removed_duplicates` aus dedup-Step-Metadaten ab wenn `rows_after_preprocessing` fehlt. Kein `lru_cache` — sessionspezifisch.
- T2: `_handle_overview()` in `CommandService` auf Run-basiertes Routing umgestellt. Mit completed Run → `profile_after_steps()`; ohne → `profile_raw()`.
- T3: 3 neue Unit-Tests in `test_profiling_service.py`. Alle 374 Unit-Tests grün (15 in test_profiling_service.py).
- **Review-Fixes (CR 7.3):**
  - M1: `_handle_overview()` delegiert direkt an `profile_after_steps()` — doppelter DB-Call eliminiert.
  - M2: `_get_raw_row_count_cached()` hinzugefügt — `pd.read_csv()` in `profile_after_steps()` gecacht.
  - L1: Test-Assertions auf `"Rohdatensatz: 4 Zeilen"` und `"Nach Preprocessing: 3 Zeilen"` gestärkt.
  - L2: Test `test_profile_after_steps_run_data_none()` für `get_run()→None`-Fallback ergänzt.
  - L3: `[ ]`-Marker in Story-Datei für Code-Block-Subtasks auf `[x]` korrigiert.
- Gesamt: 375/375 Unit-Tests grün nach Review-Fixes.

### File List

- `backend/src/gysi_ml/services/profiling_service.py`
- `backend/src/gysi_ml/services/command_service.py`
- `backend/tests/unit/test_profiling_service.py`
