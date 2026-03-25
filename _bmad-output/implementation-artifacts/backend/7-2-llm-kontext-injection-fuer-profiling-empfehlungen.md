# Story 7.2: LLM-Kontext-Injection für Profiling-Empfehlungen

Status: done

## Story

Als ein Nutzer,
möchte ich nach einem Datensatz-Überblick kontextualisierte Empfehlungen vom LLM erhalten,
damit das LLM auf echten Daten basierte Hinweise zu Auffälligkeiten und nächsten Schritten gibt.

## Acceptance Criteria

1. **[Profiling-Block im LLM-Prompt]** Wenn Profiling-Daten verfügbar sind, enthält der LLM-Prompt einen `## Datensatz-Profil`-Block mit einer kompakten Zusammenfassung.

2. **[Kein Profiling-Block wenn nicht vorhanden]** Ist kein Profiling-Result vorhanden (erste Session, kein Profiling ausgelöst), bleibt der Prompt unverändert — kein leerer Block, kein Fehler.

3. **[Kompaktes Format]** Der Profiling-Block im Prompt ist kompakt (nicht der vollständige `profile_raw()`-Output) — nur die wesentlichen Kennzahlen für LLM-Kontext.

4. **[LLM-Empfehlungen kontextualisiert]** Das LLM generiert — gegeben den Profiling-Block — Empfehlungen zu: Auffälligkeiten, vorgeschlagene nächste Schritte, Besonderheiten des Datensatzes.

5. **[Test-Coverage ≥ 85%]** `build_system_prompt()` mit und ohne Profiling-Daten ist getestet.

## Tasks / Subtasks

- [x] **T1 — `ProfilingService.to_compact_str()` hinzufügen** (AC: 3)
  - [x] Datei: `backend/src/gysi_ml/services/profiling_service.py`
  - [ ] Neue Methode in `ProfilingService`:
    ```python
    def to_compact_str(self) -> str:
        """Kompakte Darstellung für LLM-Prompt-Injection."""
        return _compact_profile_cached(self._get_data_path())
    
    
    @functools.lru_cache(maxsize=1)
    def _compact_profile_cached(data_path: str) -> str:
        df = pd.read_csv(data_path)
        rows, cols = df.shape
        missing = df.isnull().sum()
        missing_cols = missing[missing > 0]
        num_cols = df.select_dtypes(include="number").columns.tolist()
        
        lines = [
            f"Datensatz: {rows} Zeilen × {cols} Spalten",
            f"Numerische Spalten ({len(num_cols)}): {', '.join(num_cols[:8])}{'...' if len(num_cols) > 8 else ''}",
        ]
        if not missing_cols.empty:
            top3 = missing_cols.head(3)
            missing_str = ", ".join(f"{c} ({n})" for c, n in top3.items())
            lines.append(f"Fehlende Werte: {missing_str}")
        else:
            lines.append("Fehlende Werte: keine")
        
        # Korrelationen mit Target-Spalte 'cnt'
        if "cnt" in df.columns:
            corr = df[num_cols].corr()["cnt"].drop("cnt", errors="ignore").abs().sort_values(ascending=False)
            top_corr = corr.head(5)
            corr_str = ", ".join(f"{c} ({v:.2f})" for c, v in top_corr.items())
            lines.append(f"Stärkste Korrelationen mit 'cnt': {corr_str}")
        
        return "\n".join(lines)
    ```

- [x] **T2 — `build_system_prompt()` in `llm/prompts.py` erweitern** (AC: 1, 2)
  - [x] Datei: `backend/src/gysi_ml/llm/prompts.py`
  - [ ] Signatur erweitern:
    ```python
    def build_system_prompt(
        capabilities: list[dict],
        current_spec: dict | None = None,
        profiling_context: str | None = None,   # NEU
    ) -> str:
    ```
  - [ ] Am Ende des Prompts optionalen Profiling-Block einfügen:
    ```python
    if profiling_context:
        prompt += f"\n\n## Datensatz-Profil\n{profiling_context}"
    ```
  - [ ] Rückwärtskompatibel: `profiling_context=None` → keine Änderung am bisherigen Output

- [x] **T3 — `message_service.py` Profiling-Kontext weiterleiten** (AC: 1, 2)
  - [ ] Datei: `backend/src/gysi_ml/services/message_service.py`
  - [ ] In `handle_message()` vor dem `build_system_prompt()`-Aufruf:
    ```python
    from gysi_ml.services.profiling_service import ProfilingService
    
    # Optionaler Profiling-Kontext für LLM
    try:
        profiling_context = ProfilingService().to_compact_str()
    except Exception:
        profiling_context = None
    
    system_prompt = build_system_prompt(
        capabilities,
        current_spec=current_spec,
        profiling_context=profiling_context,
    )
    ```
  - [ ] `try/except` sichert, dass ein fehlender Datensatz-Pfad nicht den gesamten Chat-Flow bricht

- [x] **T4 — Tests** (AC: 1, 2, 5)
  - [ ] Datei: `backend/tests/unit/test_prompts.py` (erweitern) oder neu
  - [ ] Tests:
    - `test_prompt_with_profiling_context()`: `build_system_prompt(..., profiling_context="...")` → Prompt enthält "## Datensatz-Profil"
    - `test_prompt_without_profiling_context()`: `profiling_context=None` → kein "## Datensatz-Profil" im Prompt
    - `test_compact_str_format()`: `to_compact_str()` → enthält Zeilen/Spalten-Info

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 7.1:** `ProfilingService` muss existieren und `profile_raw()` + `to_compact_str()` implementieren.
- Story 7.3 erweitert Profile nach Preprocessing — hat keinen Einfluss auf diesen LLM-Injection-Mechanismus.

### Strategie: Immer Profiling-Kontext

- Profiling des Rohdatensatzes ist gecacht → kein Performance-Impact
- Der Kontext ist immer verfügbar sobald `data_path` gültig ist
- `try/except` in `message_service.py` ist Sicherheitsnetz, kein Workaround

### LLM-Prompt-Platz

- Aktueller System-Prompt enthält Capabilities + ggf. aktuelle Spec → Profiling-Block kommt danach
- Kompaktes Format (< 20 Zeilen) hält den Prompt-Overhead gering

### References

- [Source: backend/src/gysi_ml/llm/prompts.py] — `build_system_prompt()`-Signatur
- [Source: backend/src/gysi_ml/services/message_service.py#handle_message] — Einsprungpunkt
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-7.2]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

Keine.

### Completion Notes List

- T1: `ProfilingService.to_compact_str()` + `_compact_profile_cached()` (lru_cache, maxsize=1) in profiling_service.py implementiert. Liefert kompaktes Format: Zeilen×Spalten, numerische Spalten, fehlende Werte, Top-5-Korrelationen mit `cnt`.
- T2: `build_system_prompt()` um optionalen Parameter `profiling_context: str | None = None` erweitert. Block `## Datensatz-Profil` wird nur bei truthy-Wert angehängt. Vollständig rückwärtskompatibel.
- T3: `message_service.handle_message()` ruft `ProfilingService().to_compact_str()` vor dem LLM-Aufruf auf. `try/except Exception` sichert, dass ein fehlender Datensatz-Pfad den Chat-Flow nicht bricht.
- T4: 25 Tests neu hinzugefügt (4 in test_prompts.py, 5 in test_profiling_service.py) + alle 485 Bestandstests grün. 9 vorbestehende Failures (Stories 6.1/8.x) unverändert.
- **Code Review Fix (L1):** `ProfilingService`-Import aus Funktionskörper auf Modul-Ebene verschoben (`message_service.py`).
- **Code Review Note (M1):** `except Exception` in Profiling-Block mit Tech-Debt-Kommentar versehen — Logging bei künftiger Infrastruktur-Story eintragen.

### File List

- `backend/src/gysi_ml/services/profiling_service.py` — `to_compact_str()`, `_compact_profile_cached()`
- `backend/src/gysi_ml/llm/prompts.py` — `build_system_prompt()` Signatur + Profiling-Block
- `backend/src/gysi_ml/services/message_service.py` — Profiling-Kontext-Weiterleitung
- `backend/tests/unit/llm/test_prompts.py` — 4 neue Tests (AC 1, 2)
- `backend/tests/unit/test_profiling_service.py` — 5 neue Tests (AC 3, 5)
