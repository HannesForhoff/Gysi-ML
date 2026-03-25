# Story 6.2: Slash-Command-Router mit `/help`, `/overview`, `/status`

Status: done

## Story

Als ein Nutzer,
möchte ich Slash-Commands (`/help`, `/overview`, `/status`) über den normalen Chat-Endpunkt senden können,
damit ich ohne Umwege strukturierte Systeminformationen bekomme — ohne LLM-Aufruf und ohne extra Endpunkte.

## Acceptance Criteria

1. **[Slash-Command-Erkennung ohne LLM]** Jede Nachricht an `POST /v1/sessions/{id}/messages`, die mit `/` beginnt, wird von `CommandService` verarbeitet — ohne LLM-Aufruf. Response hat `type: "assistant"`.

2. **[/help — kategorisierte Übersicht]** `/help` gibt eine Übersicht mit den Kategorien: Daten erkunden, Preprocessing, Modellierung, Pipeline-Verwaltung, Grenzen. Inhalt kommt aus `configs/help_texts.yaml`.

3. **[/help <thema> — gefilterte Ausgabe]** `/help preprocessing` gibt nur die Preprocessing-Kategorie zurück.

4. **[/overview — delegiert an ProfilingService]** `/overview` delegiert an `ProfilingService.profile_raw()` (aus Story 7.1) und gibt das Ergebnis zurück. Kein LLM-Aufruf.

5. **[/status — Session-Überblick]** `/status` gibt zurück: aktuelle Spec-Version (oder „Keine Pipeline konfiguriert"), Anzahl Runs, letzter Run-Status + Metriken (falls vorhanden), aktive Steps.

6. **[Unbekannte Commands — strukturierter Fehler]** Unbekannte Commands (z.B. `/foo`) geben eine Fehlermeldung mit Liste verfügbarer Commands zurück — kein 500, kein Absturz.

7. **[Alle Slash-Command-Antworten persistiert]** Jede Command-Response wird als `role: "assistant"`-Message in der Session-History gespeichert.

8. **[Test-Coverage ≥ 85%]** `CommandService` ist isoliert testbar (kein DB-Aufruf in `is_slash_command()`).

## Tasks / Subtasks

- [x] **T1 — `services/command_service.py` anlegen** (AC: 1–7)
  - [x] Datei: `backend/src/gysi_ml/services/command_service.py` (neu)
  - [x] Klassen-Struktur:
    ```python
    from __future__ import annotations
    import yaml
    from pathlib import Path
    
    KNOWN_COMMANDS = ["/help", "/overview", "/status"]
    
    
    class CommandService:
        def is_slash_command(self, content: str) -> bool:
            return content.strip().startswith("/")
    
        def handle(self, content: str, session_id: str, db_path: str | None = None) -> str:
            parts = content.strip().split(maxsplit=1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else None
    
            if command == "/help":
                return self._handle_help(arg)
            elif command == "/overview":
                return self._handle_overview(session_id, db_path)
            elif command == "/status":
                return self._handle_status(session_id, db_path)
            else:
                return (
                    f"Unbekannter Command: `{command}`\n\n"
                    f"Verfügbare Commands: {', '.join(KNOWN_COMMANDS)}"
                )
    
        def _handle_help(self, topic: str | None) -> str:
            texts = self._load_help_texts()
            categories = texts.get("help", {}).get("categories", {})
            if topic:
                key = topic.lower()
                if key in categories:
                    return f"**{key}:** {categories[key]}"
                return f"Unbekanntes Thema: `{topic}`. Verfügbar: {', '.join(categories.keys())}"
            lines = ["**Gysi-Hilfe:**\n"]
            for cat, desc in categories.items():
                lines.append(f"- **{cat}:** {desc}")
            return "\n".join(lines)
    
        def _handle_overview(self, session_id: str, db_path: str | None) -> str:
            # ProfilingService wird in Story 7.1 implementiert
            # Hier: Stub der später durch echten Service ersetzt wird
            from gysi_ml.services.profiling_service import ProfilingService
            svc = ProfilingService()
            return svc.profile_raw()
    
        def _handle_status(self, session_id: str, db_path: str | None) -> str:
            from gysi_ml.persistence import spec_repository, run_repository
            spec = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
            if spec is None:
                spec_info = "Keine Pipeline konfiguriert"
                active_steps: list = []
            else:
                spec_info = f"Version {spec['version']} ({spec['spec_id'][:8]}...)"
                active_steps = [s["type"] for s in spec["spec"].get("steps", []) if s.get("enabled", True)]
    
            runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
            run_count = len(runs)
            if runs:
                last = runs[-1]
                last_status = last["status"]
                metrics = last.get("metrics") or {}
                metrics_str = ", ".join(f"{k}: {v:.4f}" for k, v in metrics.items()) if metrics else "keine Metriken"
                last_run_info = f"Letzter Run: {last_status} ({metrics_str})"
            else:
                last_run_info = "Noch keine Runs ausgeführt"
    
            steps_str = ", ".join(active_steps) if active_steps else "keine"
            return (
                f"**Session-Status:**\n"
                f"- Spec: {spec_info}\n"
                f"- Runs: {run_count}\n"
                f"- {last_run_info}\n"
                f"- Aktive Steps: {steps_str}"
            )
    
        def _load_help_texts(self) -> dict:
            path = Path(__file__).parents[4] / "configs" / "help_texts.yaml"
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    ```
  - [x] `run_repository.get_runs_for_session()` prüfen ob Signatur stimmt — Referenz: `persistence/run_repository.py`

- [x] **T2 — `message_service.py` anpassen: Slash-Command-Check vorschalten** (AC: 1, 7)
  - [x] Datei: `backend/src/gysi_ml/services/message_service.py`
  - [ ] Am Anfang von `handle_message()` nach dem `settings`-Import einfügen:
    ```python
    from gysi_ml.services.command_service import CommandService
    
    # Slash-Command-Check VOR LLM-Aufruf
    _command_service = CommandService()
    if _command_service.is_slash_command(text):
        response_text = _command_service.handle(text, session_id=session_id, db_path=db_path)
        # User-Message persistieren
        message_repository.create_message(
            session_id=session_id, role="user", content=text, db_path=db_path
        )
        # Command-Response als assistant persistieren
        message_repository.create_message(
            session_id=session_id, role="assistant", content=response_text, db_path=db_path
        )
        return {"type": "assistant", "message": response_text}
    ```
  - [x] Dieser Block kommt VOR dem LLM-Konfigurations-Check (damit auch ohne LLM-Key nutzbar)

- [x] **T3 — `help_texts.yaml` Kategorien ergänzen** (AC: 2, 3)
  - [x] Datei: `backend/configs/help_texts.yaml` (aus Story 6.1, falls bereits erstellt — ergänzen)
  - [x] Sicherstellen, dass `help.categories` alle 5 Kategorien enthält: `daten`, `preprocessing`, `modellierung`, `pipeline`, `grenzen`

- [x] **T4 — Tests für `CommandService`** (AC: 1–8)
  - [x] Datei: `backend/tests/unit/test_command_service.py` (neu)
  - [x] Tests:
    - `test_is_slash_command_true()`: `/help` → True
    - `test_is_slash_command_false()`: `"normale Nachricht"` → False
    - `test_help_all_categories()`: `handle("/help", ...)` → enthält alle 5 Kategorien
    - `test_help_filtered()`: `handle("/help preprocessing", ...)` → nur Preprocessing
    - `test_unknown_command()`: `handle("/foo", ...)` → enthält "Unbekannter Command"
    - `test_status_no_spec()`: Mock-Session ohne Spec → "Keine Pipeline konfiguriert"
  - [x] Mocking: `ProfilingService`, `spec_repository`, `run_repository` mit `unittest.mock`

## Dev Notes

### Abhängigkeiten

- **Epic 5 (Story 5.1):** Nicht direkt benötigt — `spec_versions` und `messages` existieren bereits.
- **Epic 7 (Story 7.1 — ProfilingService):** `_handle_overview()` ruft `ProfilingService.profile_raw()` auf. Story 7.1 muss implementiert sein bevor `/overview` voll funktioniert. Stub mit `# TODO: Story 7.1` ist akzeptabel.
- **Story 6.1:** `configs/help_texts.yaml` und `load_help_text()` sollten bereits existieren.

### MessageService-Stelle

- `handle_message()` beginnt aktuell mit LLM-Key-Check, dann Capabilities/Prompt, dann History laden.
- Slash-Command-Block kommt **VOR** dem LLM-Key-Check — Commands funktionieren auch ohne konfiguriertes LLM.

### run_repository

- `run_repository.get_runs_for_session()` existiert — Rückgabe: Liste von dicts mit `run_id`, `status`, `result_json`.
- `result_json` enthält ggf. `metrics` als JSON-String — parsen mit `json.loads()`.

### ResponseType

- Slash-Command-Response hat `type: "assistant"` (nicht `type: "proposal"` oder `type: "result"`)
- Das ist ein neuer Typ — `MessageResponse` in `schemas.py` hat `type: str` (frei) → kein Schema-Break.

### References

- [Source: backend/src/gysi_ml/services/message_service.py] — Einsprungpunkt für Slash-Command-Check
- [Source: backend/src/gysi_ml/persistence/run_repository.py] — `get_runs_for_session()`-Signatur prüfen
- [Source: _bmad-output/planning-artifacts/architecture.md#Entscheidung-1] — CommandService-Architektur
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-6.2]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- T1: `_load_help_texts()` Pfad auf `parents[3]` korrigiert (Story-Spec hatte `parents[4]` — falsch).
- T1: `_handle_status()` nutzt `run_repository.get_run()` für den letzten Run, da `get_runs_for_session()` kein `result_json` enthält. Metriken via `result.get("metrics")`.
- T2: Persistenz-Calls aus `message_service.py` entfernt — die Route in `messages.py` übernimmt bereits User-Message (Schritt 2) und Assistant-Response (Schritt 4). Doppelte Persistenz hätte Duplikat-Messages erzeugt.
- T1: `command_service.py` existierte bereits als Stub aus Story 7.1 — vollständig ersetzt.

### Completion Notes List

- T1: `CommandService` vollständig implementiert: `is_slash_command()`, `handle()`, `_handle_help()`, `_handle_overview()`, `_handle_status()`, `_load_help_texts()`.
- T2: Slash-Command-Block in `handle_message()` eingefügt — **VOR** LLM-Konfigurations-Check. Keine eigene Persistenz, Route übernimmt das.
- T3: `help_texts.yaml` bereits vollständig mit allen 5 Kategorien (`daten`, `preprocessing`, `modellierung`, `pipeline`, `grenzen`) aus Story 6.1 ✅.
- T4: 12 Tests in `test_command_service.py`, alle bestanden. Integrations-Test für AC 7 ergänzt.
- Regression: 492 Tests bestanden, 5 Fehler — alle pre-existing.

**Code-Review-Korrekturen (2026-03-22):**
- M1: `_handle_overview()` auf `profile_raw()` korrigiert (AC 4 explizit). `profile_after_steps()` entfernt.
- M2 (durch M1 behoben): Test-Mock passt jetzt korrekt auf `profile_raw()`.
- M3: Integrationstest `test_slash_command_response_persisted` für AC 7 ergänzt.
- L1: `CommandService`-Import an Top-Level verschoben.
- L2: Redundanten `wraps`-Patch in `test_status_no_spec_no_runs` entfernt.
- L3: Fehler-Handling in `_load_help_texts()` für fehlende `help_texts.yaml`.
- `test_profiling_service.py::test_command_service_overview_routes_correctly` angepasst (Story-7.1-Test stimmte nicht mehr mit AC 4 überein).

### File List

- `backend/src/gysi_ml/services/command_service.py` (ersetzt/vollständig implementiert)
- `backend/src/gysi_ml/services/message_service.py` (geändert: Slash-Command-Block + Top-Level-Import)
- `backend/tests/unit/test_command_service.py` (neu, 12 Tests)
- `backend/tests/unit/test_profiling_service.py` (geändert: `test_command_service_overview_routes_correctly` angepasst)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (Status 6.2: ready-for-dev → done)

### Change Log

- 2026-03-22: Story 6.2 implementiert — CommandService (Slash-Command-Router), MessageService-Integration, 12 Tests
- 2026-03-22: Code-Review-Korrekturen — M1 (profile_raw), M3 (AC-7-Test), L1–L3 behoben
