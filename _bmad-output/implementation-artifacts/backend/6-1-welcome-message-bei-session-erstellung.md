# Story 6.1: Welcome-Message bei Session-Erstellung

Status: done

## Story

Als ein Nutzer,
möchte ich beim Erstellen einer neuen Session automatisch eine strukturierte Willkommensnachricht erhalten,
damit ich sofort weiß, was das System kann, wie ich interagieren soll und wie ich Hilfe bekomme.

## Acceptance Criteria

1. **[welcome_message im Response]** `POST /v1/sessions` gibt in der Response ein Feld `welcome_message: str` mit einer nicht-leeren Begrüßung zurück. Die Begrüßung enthält: Kurzanleitung, Beispiel-Prompts, Hinweis auf `/help` und `/overview`.

2. **[Welcome-Message als erste Session-Message persistiert]** Nach Session-Erstellung existiert die Welcome-Message als Message mit `role: "assistant"` in der `messages`-Tabelle, abrufbar über die Session-History.

3. **[Kein zweiter API-Call nötig]** Frontend erhält die Welcome-Message direkt aus dem `welcome_message`-Feld — kein separater GET-Request erforderlich.

4. **[Kein Frontend-Hardcoding]** Der Welcome-Text kommt aus `configs/help_texts.yaml` (Schlüssel `welcome_message`) — nicht im Python-Code oder Frontend hartcodiert.

5. **[Test-Coverage ≥ 85%]** Neue Logik in `sessions.py` und Help-Text-Laden ist abgedeckt.

## Tasks / Subtasks

- [x] **T1 — `configs/help_texts.yaml` anlegen** (AC: 4)
  - [x] Datei: `backend/configs/help_texts.yaml` (neu)
  - [ ] Inhalt:
    ```yaml
    welcome_message: |
      Willkommen bei Gysi — deinem ML-Assistenten für den Bike-Datensatz! 🚲

      **Was ich kann:**
      - Preprocessing-Schritte konfigurieren (Dedup, Imputation, Encoding, ...)
      - Modelle trainieren (Decision Tree, EBM, CatBoost)
      - Ergebnisse erklären und Runs vergleichen

      **Beispiele:**
      - „Entferne Duplikate und impute fehlende Werte mit Median"
      - „Trainiere einen Decision Tree mit max_depth=5"
      - „Vergleiche Run A mit Run B"

      **Hilfe:** `/help` → Alle Funktionen  |  `/overview` → Datensatz-Überblick  |  `/status` → Session-Status

    help:
      categories:
        daten: "Datensatz erkunden: /overview, Profiling"
        preprocessing: "Dedup, Imputation, Encoding, Outlier Handling, Correlation Filter, Rare Category, Time Features"
        modellierung: "Decision Tree, EBM, CatBoost Feature Selection"
        pipeline: "Spec-Abruf, Re-Execution, Parameter-Anpassung, Modellvergleich"
        grenzen: "Nur Bike-Datensatz, kein Code-Upload, kein Deployment"
    ```

- [x] **T2 — `SessionResponse` um `welcome_message` erweitern** (AC: 1, 3)
  - [x] Datei: `backend/src/gysi_ml/api/schemas.py`
  - [x] `SessionResponse` um optionales Feld ergänzen:
    ```python
    welcome_message: Optional[str] = None
    ```
  - [x] `Optional[str] = None` damit GET /sessions/{id} weiterhin ohne dieses Feld funktioniert (nur POST /sessions füllt es)

- [x] **T3 — Help-Text-Lade-Funktion anlegen** (AC: 4)
  - [x] Datei: `backend/src/gysi_ml/utils/help_loader.py` (neu)
  - [ ] Funktion:
    ```python
    import yaml
    from pathlib import Path
    
    def load_help_text(key: str) -> str:
        config_path = Path(__file__).parent.parent.parent.parent / "configs" / "help_texts.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get(key, "")
    ```
  - [ ] Pfad relativ zum Package-Root (4 Ebenen hoch von `gysi_ml/utils/`)

- [x] **T4 — Welcome-Message in `POST /sessions` persistieren und zurückgeben** (AC: 1, 2, 3)
  - [x] Datei: `backend/src/gysi_ml/api/routes/sessions.py`
  - [ ] `create_session()`-Handler anpassen:
    ```python
    from gysi_ml.utils.help_loader import load_help_text
    
    @router.post("/sessions", response_model=SessionResponse, status_code=201)
    def create_session(request: Request, body: Optional[SessionCreateRequest] = Body(default=None)) -> SessionResponse:
        db_path = _get_db_path(request)
        name = body.name if body else None
        row = session_repository.create_session(name=name, db_path=db_path)
        
        # Welcome-Message laden und als erste Message persistieren
        welcome_text = load_help_text("welcome_message")
        message_repository.create_message(
            session_id=row["session_id"],
            role="assistant",
            content=welcome_text,
            db_path=db_path,
        )
        
        return SessionResponse(**row, welcome_message=welcome_text)
    ```
  - [x] `message_repository` ist bereits importiert in `sessions.py`
  - [x] Signatur geprüft: Funktion heißt `save_message()` (nicht `create_message()`) — angepasst

- [x] **T5 — Tests** (AC: 1–5)
  - [x] Bestehende Session-Tests geprüft — keine Breaking Changes
  - [x] Neuer Test: `test_create_session_has_welcome_message()` — POST /sessions → `welcome_message` not empty
  - [x] Neuer Test: `test_welcome_message_persisted_as_first_message()` — nach Session-Create existiert assistant-Message

## Dev Notes

### Abhängigkeit

- **Benötigt Epic 5 (Story 5.1) nicht direkt** — `messages`-Tabelle existiert bereits.
- Story 6.2 baut auf `configs/help_texts.yaml` und der neuen `load_help_text()`-Funktion auf.

### Bestehende Infrastruktur

- `session_repository.create_session()` gibt ein `dict` mit `session_id`, `name`, `created_at`, `status` zurück
- `message_repository` bereits in `sessions.py` importiert — `create_message()` existiert (Referenz: message_repository.py)
- `SessionResponse` in `schemas.py` hat `Optional[list["MessageSummary"]] = None` für messages — `welcome_message` analog hinzufügen

### Pfad-Konvention

- `configs/` liegt unter `backend/configs/` — nicht im Python-Package
- Pfad muss relativ zum Package aufgelöst werden: `Path(__file__).parents[N] / "configs"`
- Alternativ über `get_settings()` wenn `configs_path` konfigurierbar sein soll

### Rückwärtskompatibilität

- GET /sessions, GET /sessions/{id}: `welcome_message` ist `Optional[str] = None` → keine Breaking Changes

### References

- [Source: backend/src/gysi_ml/api/routes/sessions.py] — aktueller `create_session()`-Handler
- [Source: backend/src/gysi_ml/api/schemas.py#SessionResponse] — zu erweiterndes Schema
- [Source: _bmad-output/planning-artifacts/architecture.md#Entscheidung-2] — Welcome-Message: Response + persistierte Message
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-6.1]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- `message_repository.create_message()` existiert nicht — tatsächliche Funktion heißt `save_message()` (angepasst)

### Completion Notes List

- T1–T5 vollständig implementiert und getestet
- 352 Unit- und Integrationstests bestanden (15 Session-Tests inkl. 2 neuer)
- Code-Review durchgeführt, 3 Issues behoben (M1: Error-Handling + L1: Caching + L2: KeyError bei fehlendem Schlüssel)
- Hinweis: `test_post_message_saves_and_returns_503` in test_messages_api.py schlägt fehl — pre-existing, nicht durch Story 6.1 verursacht

### File List

- `backend/configs/help_texts.yaml` (neu)
- `backend/src/gysi_ml/utils/help_loader.py` (neu — inkl. Caching + Error-Handling)
- `backend/src/gysi_ml/api/schemas.py` (geändert: `welcome_message` zu `SessionResponse`)
- `backend/src/gysi_ml/api/routes/sessions.py` (geändert: `create_session()` mit Welcome-Message)
- `backend/tests/integration/test_sessions_api.py` (geändert: 2 neue Tests)
- `backend/tests/unit/test_help_loader.py` (neu: 5 Unit-Tests für help_loader)
