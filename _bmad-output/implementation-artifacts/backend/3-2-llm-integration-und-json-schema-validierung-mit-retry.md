# Story 3.2: LLM-Integration und JSON-Schema-Validierung mit Retry

Status: done

## Story

Als ein Entwickler,
möchte ich dass Nutzereingaben an ein LLM (OpenAI-kompatibel) gesendet werden, die Antwort gegen ein JSON-Schema validiert wird und bei Fehler ein Retry-Prompt ausgelöst wird,
damit das System robust gegen fehlerhafte LLM-Outputs ist und kein ungültiges JSON die Ausführungskette erreicht.

## Acceptance Criteria

1. **[openai-Abhängigkeit]** `openai>=1.0` ist in `requirements.txt` und `pyproject.toml` eingetragen. Der LLM-Client nutzt die offizielle `openai` Python-Library mit konfigurierbarer `base_url` (OpenAI-kompatible Endpunkte).

2. **[LLM-Client-Modul]** Ein Modul `llm/client.py` existiert mit einer Funktion `call_llm(messages: list[dict], model: str, api_key: str, base_url: str | None) -> str`, die einen Chat-Completion-Aufruf macht und den Antwort-Content als String zurückgibt.

3. **[Strukturierter System-Prompt]** Ein Modul `llm/prompts.py` existiert mit einer Funktion `build_system_prompt(capabilities: list[dict]) -> str`, die einen System-Prompt erzeugt, der:
   - Die verfügbaren Steps mit Parametern auflistet (aus Step-Registry/Capabilities)
   - Das gewünschte JSON-Ausgabeformat definiert (LLM-Response-Schema)
   - Instruktionen zur Vagheits-Erkennung enthält (`"action": "propose"` bei Vagheit, `"action": "execute"` bei Klarheit)
   - Den Bike-Datensatz-Kontext benennt (Zielvariable `cnt`, Spalten)
   - Auf Deutsch antwortet (Erklärungen)

4. **[LLM-Response JSON-Schema]** Ein Modul `llm/response_schema.py` definiert das erwartete LLM-Antwort-Schema und eine Validierungsfunktion `validate_llm_response(response_str: str) -> dict`. Das Schema:
   ```json
   {
     "action": "execute" | "propose",
     "spec": {
       "steps": [{"type": "...", "params": {...}}]
     },
     "explanation": "Menschenlesbare Erklärung"
   }
   ```
   - `action` ist Pflicht: `"execute"` oder `"propose"`
   - `spec` ist Pflicht: muss ein gültiges Spec-Objekt sein (kompatibel mit `PIPELINE_SPEC_SCHEMA`)
   - `explanation` ist Pflicht: String, dient als menschenlesbare Zusammenfassung
   - Validierung wirft `LLMResponseValidationError` bei ungültigem JSON oder Schema-Verletzung.

5. **[Gesprächshistorie im Prompt]** `handle_message()` lädt die bisherigen Messages der Session (`message_repository.get_messages_for_session()`) und übergibt sie als Konversationshistorie an den LLM-Aufruf (OpenAI `messages`-Format: `[{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}, ...]`).

6. **[Retry bei ungültigem LLM-Output]** Wenn die LLM-Antwort das Schema nicht erfüllt, wird ein korrigierender Retry-Prompt gesendet (max. 1 Retry). Der Retry-Prompt enthält den Validierungsfehler und das erwartete Schema.

7. **[Fehlermeldung bei Retry-Erschöpfung]** Wenn der Retry-Output erneut ungültig ist, gibt das System zurück: `{"type": "error", "message": "Das Sprachmodell konnte keine gültige Aktion erzeugen. Bitte formuliere deine Anfrage neu."}`. Kein Absturz, kein 500-Error.

8. **[503 ohne LLM-Konfiguration]** Wenn `OPENAI_API_KEY` oder `LLM_MODEL` leer sind, gibt `POST /messages` HTTP 503 mit `{"type": "error", "message": "LLM-Service nicht konfiguriert."}` zurück. Der Service startet trotzdem ohne Absturz.

9. **[Valide Aktion → Durchleitung]** Bei gültigem LLM-Output mit `action: "execute"` wird die Spec an den `PipelineExecutor` delegiert und `{"type": "result", "run_id": "..."}` zurückgegeben. Bei `action: "propose"` wird `{"type": "proposal", "steps": [...], "explanation": "...", "confirmation_required": true}` zurückgegeben (Proposal-Logik wird in Story 3.3 verfeinert).

10. **[Konfiguration erweitert]** `config.py` enthält `openai_base_url: str = ""` als neues Setting. `.env.example` wird um `OPENAI_BASE_URL=` ergänzt.

11. **[NFR-S1: Kein Code-Ausführung]** LLM-Outputs werden niemals direkt als Code ausgeführt — ausschließlich JSON-Schema-validierte Strukturen werden an den Executor weitergeleitet.

12. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module. LLM-Aufrufe werden in Tests durch Mocks ersetzt.

## Tasks / Subtasks

- [x] **T1 — `openai`-Abhängigkeit hinzufügen** (AC: 1)
  - [x] `backend/requirements.txt` ergänzen: `openai>=1.0`
  - [x] `backend/pyproject.toml` unter `[project] dependencies` ergänzen: `"openai>=1.0"`
  - [x] Dependency installieren: `uv pip install openai>=1.0` (oder `uv sync`)
  - [x] Smoke-Test: `python -c "from openai import OpenAI; print('OK')"` muss erfolgreich sein

- [x] **T2 — `config.py` erweitern** (AC: 10)
  - [x] `src/gysi_ml/config.py` → neues Feld:
    ```python
    openai_base_url: str = ""
    ```
  - [x] `.env.example` ergänzen:
    ```
    OPENAI_BASE_URL=
    ```

- [x] **T3 — LLM-Package aufbauen** (AC: 2, 3, 4)
  - [x] `src/gysi_ml/llm/__init__.py` erstellen (leer)
  - [x] **`src/gysi_ml/llm/client.py`** erstellen:
    ```python
    from openai import OpenAI

    def call_llm(
        messages: list[dict],
        model: str,
        api_key: str,
        base_url: str | None = None,
    ) -> str:
        """Sendet Chat-Completion-Anfrage an OpenAI-kompatiblen Endpunkt.

        Args:
            messages: OpenAI messages-Format [{"role": "...", "content": "..."}]
            model: Modellname (z.B. "gpt-4o-mini")
            api_key: API-Key
            base_url: Optionaler alternativer Endpunkt (für kompatible APIs)

        Returns:
            Content-String der LLM-Antwort.

        Raises:
            LLMConnectionError: Bei Netzwerk-/API-Fehlern.
        """
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,  # Niedrig für konsistente JSON-Outputs
        )
        return response.choices[0].message.content
    ```
  - [x] **Fehlerbehandlung**: API-Fehler (`openai.APIError`, `openai.APIConnectionError`) als `LLMConnectionError` wrappen — definiert in `llm/exceptions.py`
  - [x] **`src/gysi_ml/llm/exceptions.py`** erstellen:
    ```python
    class LLMConnectionError(Exception):
        """Fehler bei der Kommunikation mit dem LLM-Endpunkt."""

    class LLMResponseValidationError(Exception):
        """LLM-Antwort erfüllt das erwartete JSON-Schema nicht."""
    ```

  - [x] **`src/gysi_ml/llm/prompts.py`** erstellen:
    ```python
    import json

    SYSTEM_PROMPT_TEMPLATE = """Du bist ein ML-Pipeline-Assistent für den Bike-Sharing-Datensatz.
    Deine Aufgabe ist es, natürlichsprachliche Anfragen des Nutzers in strukturierte Pipeline-Aktionen zu übersetzen.

    ## Verfügbare Steps

    {capabilities_json}

    ## Datensatz-Kontext

    - Datensatz: Bike-Sharing (UCI, 17.379 Einträge)
    - Zielvariable: `cnt` (Anzahl Ausleihungen)
    - Typische Spalten: instant, dteday, season, yr, mnth, hr, holiday, weekday, workingday, weathersit, temp, atemp, hum, windspeed, casual, registered, cnt

    ## Antwortformat

    Du antwortest IMMER mit einem validen JSON-Objekt. Kein Freitext, kein Markdown, nur JSON.

    Das JSON-Objekt hat folgende Struktur:
    ```json
    {{
      "action": "execute" oder "propose",
      "spec": {{
        "steps": [
          {{"type": "<step_type>", "params": {{...}}}}
        ]
      }},
      "explanation": "<Menschenlesbare Erklärung auf Deutsch>"
    }}
    ```

    ## Regeln für action-Wahl

    - **"execute"**: Verwende dies wenn der Nutzer eine klare, eindeutige Aktion beschreibt, bei der alle Parameter ableitbar sind.
      Beispiel: "Entferne Duplikate und imputiere fehlende Werte mit Median" → execute
    - **"propose"**: Verwende dies wenn die Eingabe vage ist, mehrere Interpretationen zulässt, oder wichtige Parameter fehlen.
      Beispiel: "Bereite die Daten vor" → propose (welche Steps? welche Parameter?)

    ## Wichtig

    - Der `split`-Step muss vor allen Preprocessing-Steps (außer `dedup`) und Modeling-Steps stehen.
    - `random_state` ist immer 42, falls nicht anders angegeben.
    - Antworte auf Deutsch in der `explanation`.
    - Erzeuge NUR gültiges JSON. Kein zusätzlicher Text vor oder nach dem JSON.
    """

    def build_system_prompt(capabilities: list[dict]) -> str:
        capabilities_json = json.dumps(capabilities, indent=2, ensure_ascii=False)
        return SYSTEM_PROMPT_TEMPLATE.format(capabilities_json=capabilities_json)

    def build_retry_prompt(error_message: str) -> str:
        return (
            f"Deine letzte Antwort war kein gültiges JSON oder erfüllte das Schema nicht.\n"
            f"Fehler: {error_message}\n\n"
            f"Bitte antworte erneut mit einem gültigen JSON-Objekt im geforderten Format. "
            f"Nur JSON, kein Freitext."
        )
    ```

  - [x] **`src/gysi_ml/llm/response_schema.py`** erstellen:
    ```python
    import json
    import jsonschema
    from gysi_ml.llm.exceptions import LLMResponseValidationError

    LLM_RESPONSE_SCHEMA: dict = {
        "type": "object",
        "required": ["action", "spec", "explanation"],
        "properties": {
            "action": {"type": "string", "enum": ["execute", "propose"]},
            "spec": {
                "type": "object",
                "required": ["steps"],
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {"type": "string"},
                                "params": {"type": "object"},
                            },
                        },
                    }
                },
            },
            "explanation": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def validate_llm_response(response_str: str) -> dict:
        """Parst und validiert die LLM-Antwort gegen das Schema.

        Returns:
            Geparstes dict bei Erfolg.

        Raises:
            LLMResponseValidationError: Bei ungültigem JSON oder Schema-Verletzung.
        """
        # 1. JSON-Parsing
        try:
            data = json.loads(response_str)
        except json.JSONDecodeError as exc:
            raise LLMResponseValidationError(
                f"Ungültiges JSON: {exc}"
            ) from exc

        # 2. Schema-Validierung
        try:
            jsonschema.validate(instance=data, schema=LLM_RESPONSE_SCHEMA)
        except jsonschema.ValidationError as exc:
            raise LLMResponseValidationError(
                f"Schema-Verletzung: {exc.message}"
            ) from exc

        return data
    ```

- [x] **T4 — `services/message_service.py` vollständig implementieren** (AC: 5, 6, 7, 8, 9, 11)
  - [x] `handle_message()` aus Story 3.1 erweitern:
    ```python
    import json
    from gysi_ml.config import get_settings
    from gysi_ml.core.capabilities import get_capabilities
    from gysi_ml.executor.executor import PipelineExecutor
    from gysi_ml.llm.client import call_llm
    from gysi_ml.llm.exceptions import LLMConnectionError, LLMResponseValidationError
    from gysi_ml.llm.prompts import build_system_prompt, build_retry_prompt
    from gysi_ml.llm.response_schema import validate_llm_response
    from gysi_ml.persistence import message_repository

    MAX_RETRIES = 1

    def handle_message(
        session_id: str,
        text: str,
        db_path: str | None = None,
        data_path: str | None = None,
        artifacts_path: str | None = None,
    ) -> dict:
        settings = get_settings()

        # 1. LLM-Konfiguration prüfen
        if not settings.openai_api_key or not settings.llm_model:
            return {
                "type": "error",
                "message": "LLM-Service nicht konfiguriert. "
                "Bitte OPENAI_API_KEY und LLM_MODEL in .env setzen.",
            }

        # 2. Capabilities laden
        capabilities = get_capabilities()

        # 3. System-Prompt bauen
        system_prompt = build_system_prompt(capabilities)

        # 4. Gesprächshistorie laden
        history = message_repository.get_messages_for_session(
            session_id=session_id, db_path=db_path
        )

        # 5. OpenAI messages-Array aufbauen
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        # Aktuelle Nachricht (noch nicht in DB, da Route sie vorher speichert)
        # → ist bereits im history enthalten (Route speichert vor Service-Aufruf)

        # 6. LLM aufrufen + validieren (mit Retry)
        try:
            llm_response_str = call_llm(
                messages=messages,
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or None,
            )
        except LLMConnectionError as exc:
            return {
                "type": "error",
                "message": f"Fehler bei der LLM-Kommunikation: {exc}",
            }

        # 7. Validierung + Retry
        try:
            parsed = validate_llm_response(llm_response_str)
        except LLMResponseValidationError as first_error:
            # Retry mit korrigierendem Prompt
            retry_prompt = build_retry_prompt(str(first_error))
            messages.append({"role": "assistant", "content": llm_response_str})
            messages.append({"role": "user", "content": retry_prompt})
            try:
                llm_retry_str = call_llm(
                    messages=messages,
                    model=settings.llm_model,
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                )
                parsed = validate_llm_response(llm_retry_str)
            except (LLMResponseValidationError, LLMConnectionError):
                return {
                    "type": "error",
                    "message": "Das Sprachmodell konnte keine gültige Aktion erzeugen. "
                    "Bitte formuliere deine Anfrage neu.",
                }

        # 8. Aktion ausführen
        action = parsed["action"]
        spec = parsed["spec"]
        explanation = parsed["explanation"]

        if action == "execute":
            executor = PipelineExecutor(
                data_path=data_path or settings.data_path,
                artifacts_path=artifacts_path or settings.artifacts_path,
            )
            result = executor.execute(
                spec=spec, session_id=session_id, db_path=db_path
            )
            if "error" in result:
                return {
                    "type": "error",
                    "message": result.get("detail", result.get("error")),
                }
            return {
                "type": "result",
                "run_id": result["run_id"],
                "explanation": explanation,
            }

        # action == "propose" → wird in Story 3.3 erweitert
        return {
            "type": "proposal",
            "steps": spec.get("steps", []),
            "explanation": explanation,
            "confirmation_required": True,
        }
    ```
  - [x] **Wichtig**: Die User-Message ist bereits in der DB (Route speichert vor Service-Aufruf), daher ist sie in der `history` enthalten. Kein doppeltes Anhängen an `messages`.

- [x] **T5 — `api/routes/messages.py` aktualisieren** (AC: 9)
  - [x] Die Route aus Story 3.1 bleibt strukturell gleich. Einzige Änderung: der `handle_message()`-Aufruf gibt jetzt richtige Responses zurück statt nur Platzhalter.
  - [x] HTTP-Statuscode-Logik verfeinern:
    - `type: "error"` + "nicht konfiguriert" → 503
    - `type: "error"` + sonstiges → 422
    - `type: "result"` → 200
    - `type: "proposal"` → 200

- [x] **T6 — Unit Tests** (AC: 2, 3, 4, 6, 7, 12)
  - [x] `tests/unit/llm/__init__.py` erstellen (leer)
  - [x] `tests/unit/llm/test_client.py` anlegen:
    - `test_call_llm_returns_string(monkeypatch)`: Mock OpenAI → gibt String zurück
    - `test_call_llm_with_base_url(monkeypatch)`: Prüft dass `base_url` an Client übergeben wird
    - `test_call_llm_connection_error(monkeypatch)`: Mock API-Fehler → `LLMConnectionError`
  - [x] `tests/unit/llm/test_prompts.py` anlegen:
    - `test_build_system_prompt_contains_capabilities()`: Capabilities als JSON im Prompt enthalten
    - `test_build_system_prompt_contains_schema_instruction()`: JSON-Format-Anweisung enthalten
    - `test_build_retry_prompt_contains_error()`: Fehlermeldung im Retry-Prompt enthalten
  - [x] `tests/unit/llm/test_response_schema.py` anlegen:
    - `test_valid_execute_response()`: gültiges execute-JSON → dict zurück
    - `test_valid_propose_response()`: gültiges propose-JSON → dict zurück
    - `test_invalid_json()`: kein JSON → `LLMResponseValidationError`
    - `test_missing_action()`: fehlendes action-Feld → `LLMResponseValidationError`
    - `test_invalid_action_value()`: `action: "something_else"` → Error
    - `test_missing_spec()`: fehlendes spec-Feld → Error
    - `test_missing_explanation()`: fehlendes explanation-Feld → Error
    - `test_invalid_spec_structure()`: spec ohne steps → Error
  - [x] `tests/unit/test_message_service.py` erweitern:
    - `test_handle_message_execute_action(monkeypatch)`: Mock LLM → execute → `type: "result"` mit `run_id`
    - `test_handle_message_propose_action(monkeypatch)`: Mock LLM → propose → `type: "proposal"`
    - `test_handle_message_retry_on_invalid(monkeypatch)`: Erstes LLM-Ergebnis ungültig, zweites gültig → Erfolg
    - `test_handle_message_retry_exhausted(monkeypatch)`: Beide LLM-Ergebnisse ungültig → `type: "error"` mit Retry-Meldung
    - `test_handle_message_llm_connection_error(monkeypatch)`: LLM nicht erreichbar → `type: "error"`
    - `test_handle_message_includes_history(monkeypatch)`: Prüfen dass `messages`-Array Gesprächshistorie enthält

- [x] **T7 — Integration Tests** (AC: 8, 9, 12)
  - [x] `tests/integration/test_llm_integration.py` anlegen:
    - **Hinweis**: Alle LLM-Aufrufe werden gemockt — kein echter API-Call in Tests!
    - `test_message_flow_execute(monkeypatch)`: POST /messages → Mock LLM → execute → `type: "result"`, `run_id` vorhanden
    - `test_message_flow_propose(monkeypatch)`: POST /messages → Mock LLM → propose → `type: "proposal"`
    - `test_message_flow_503_no_llm()`: Kein LLM konfiguriert → HTTP 503
    - `test_message_flow_retry_success(monkeypatch)`: Mock: erst ungültig, dann gültig → Erfolg
    - `test_message_flow_retry_exhausted(monkeypatch)`: Mock: beide ungültig → `type: "error"`
    - `test_conversation_history_sent_to_llm(monkeypatch)`: Mehrere Nachrichten → LLM erhält vollständige Historie

## Dev Notes

### Zielstruktur nach dieser Story

```text
backend/src/gysi_ml/
├── config.py               # ÄNDERN: + openai_base_url
├── llm/
│   ├── __init__.py         # NEU (leer)
│   ├── client.py           # NEU: call_llm()
│   ├── exceptions.py       # NEU: LLMConnectionError, LLMResponseValidationError
│   ├── prompts.py          # NEU: build_system_prompt(), build_retry_prompt()
│   └── response_schema.py  # NEU: LLM_RESPONSE_SCHEMA, validate_llm_response()
├── services/
│   └── message_service.py  # ÄNDERN: handle_message() mit LLM-Aufruf
└── api/
    └── routes/
        └── messages.py     # ÄNDERN: HTTP-Statuscode-Logik verfeinert
```

### Architektur-Constraints (kritisch!)

- **NFR-S1: LLM→JSON→Executor, NIE LLM→Code**: Das LLM erzeugt ausschließlich JSON. Der `validate_llm_response()` stellt sicher, dass nur Schema-konforme Strukturen an den `PipelineExecutor` weitergeleitet werden. Unter keinen Umständen darf `response_str` direkt als Python-Code interpretiert oder an `eval`/`exec` übergeben werden.
- **OpenAI-Kompatibilität**: `openai>=1.0` unterstützt `base_url`-Konfiguration nativ. Das ermöglicht lokale LLM-Server (LM Studio, Ollama mit OpenAI-Adapter, vLLM) und cloud-basierte kompatible APIs (Azure OpenAI, Together AI, etc.). Kein eigener HTTP-Client nötig.
- **temperature=0.2**: Niedrige Temperatur für konsistente, deterministische JSON-Outputs. Nicht 0.0, da manche kompatible APIs das nicht unterstützen.
- **Retry-Prompt als User-Message**: Der Retry-Prompt wird als zusätzliche User-Message an das LLM gesendet (nicht als System-Message), damit das LLM den Kontext der fehlgeschlagenen Antwort hat.
- **Gesprächshistorie begrenzen**: In dieser Story wird die **vollständige** Historie gesendet. Bei sehr langen Sessions kann das das Token-Limit überschreiten. Ein Truncation-Mechanismus ist Nice-to-Have, nicht MVP-Scope. Falls implementiert: letzte N Nachrichten oder Token-Budget.
- **LLM-Kosten**: Jeder POST /messages = 1–2 LLM-Aufrufe (inkl. potentiellem Retry). Kein Bulk-/Batch-Modus.
- **Spec-Kompatibilität**: Das `spec`-Objekt im LLM-Response verwendet ein leicht vereinfachtes Schema (kein `enabled`-Feld, kein `additionalProperties: false`). Der `PipelineExecutor` validiert die Spec nochmal gegen `PIPELINE_SPEC_SCHEMA` — doppelte Sicherheit.

### System-Prompt-Design

Der System-Prompt ist das Herzstück der LLM-Integration. Er muss:
1. **Capabilities dynamisch einbetten**: `get_capabilities()` liefert die Step-Liste inkl. Parameter — diese wird im Prompt aufgelistet, damit das LLM weiß welche Steps verfügbar sind.
2. **JSON-Format erzwingen**: Explizite Anweisung, NUR JSON zu erzeugen. Keine Markdown-Codeblöcke, kein Fließtext.
3. **Vagheits-Klassifikation erklären**: Wann `"execute"`, wann `"propose"` — mit Beispielen.
4. **Datensatz-Kontext liefern**: Spalten, Zielvariable `cnt`, typische Workflows.

**Tipp**: Falls das LLM trotzdem Markdown-Codeblöcke (```json...```) erzeugt, den String vor dem Parsen bereinigen (Codeblock-Wrapper entfernen). Das ist ein häufiges Problem mit OpenAI-kompatiblen APIs.

### Mocking in Tests

- **`call_llm` mocken, nicht die `openai`-Library direkt**: `monkeypatch.setattr("gysi_ml.llm.client.call_llm", mock_fn)` oder auf Service-Ebene `monkeypatch.setattr("gysi_ml.services.message_service.call_llm", mock_fn)`.
- **Kein echter LLM-Aufruf in CI**: Tests dürfen niemals echte API-Calls machen. Alle LLM-Interaktion wird gemockt.
- **Fixtures für valide/invalide LLM-Responses**: Als JSON-Strings in Fixtures oder Inline im Test definieren.

### `get_capabilities()` Funktion

Existiert bereits in `src/gysi_ml/core/capabilities.py` — gibt eine `list[dict]` mit `{"type", "description", "params"}` pro Step zurück. Wird direkt für den System-Prompt genutzt.

### Fehlerbehandlung-Kaskade

```text
POST /messages
│
├── Session nicht gefunden → 404 (Route)
├── Session geschlossen → 409 (Route)
├── LLM nicht konfiguriert → 503 (Service)
├── LLM-Verbindungsfehler → {"type": "error"} + 422 (Service)
├── LLM-Response ungültig → Retry
│   ├── Retry erfolgreich → weiter
│   └── Retry fehlgeschlagen → {"type": "error"} + 422 (Service)
├── Spec-Validierung fehlgeschlagen → {"type": "error"} + 422 (Executor)
└── Ausführung erfolgreich → {"type": "result"} + 200 (Executor)
```

### Regressions-Schutz

- Alle bestehenden Tests (284+) + Story-3.1-Tests müssen weiterhin grün sein
- `PipelineExecutor` wird unverändert genutzt — kein Breaking Change
- `config.py` bekommt ein neues Feld (`openai_base_url`) mit Default `""` — kein Breaking Change (Settings hat `extra="ignore"`)

### Smoke-Check nach Integration

```bash
# Im backend-Verzeichnis
uv run pytest tests/unit/llm/ -v
uv run pytest tests/unit/test_message_service.py -v
uv run pytest tests/integration/test_llm_integration.py -v
uv run pytest tests/ --cov=src/gysi_ml --cov-report=term-missing
```

### Referenzen

- FR39: LLM-Anfrage senden — [epics.md](../../planning-artifacts/backend/epics.md)
- FR40: LLM-Output validieren — [epics.md](../../planning-artifacts/backend/epics.md)
- FR41: Retry bei ungültigem Output — [epics.md](../../planning-artifacts/backend/epics.md)
- FR42: Fehlermeldung bei Retry-Erschöpfung — [epics.md](../../planning-artifacts/backend/epics.md)
- NFR-S1: Kein Code-Ausführung — [prd.md](../../planning-artifacts/backend/prd.md)
- NFR-S2: Keine Secrets im Code — [prd.md](../../planning-artifacts/backend/prd.md)
- Capabilities-Modul: [backend/src/gysi_ml/core/capabilities.py](../../../backend/src/gysi_ml/core/capabilities.py)
- Pipeline-Spec-Schema: [backend/src/gysi_ml/spec/schema.py](../../../backend/src/gysi_ml/spec/schema.py)
- PipelineExecutor: [backend/src/gysi_ml/executor/executor.py](../../../backend/src/gysi_ml/executor/executor.py)
- OpenAI Python SDK v1: `openai.OpenAI(api_key=..., base_url=...)` — `client.chat.completions.create()`

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

- T6 `test_client.py`: Erster Ansatz mit `type()` für Mock-Objekte schlug fehl (`TypeError: mock_create() takes 0 positional arguments but 1 was given`). Fix: `MagicMock` für Fake-OpenAI-Client verwendet.
- Integrationstests: `get_settings()` ist lru_cached → Test-Settings werden nicht übernommen. Fix: `monkeypatch.setattr("gysi_ml.services.message_service.get_settings", ...)` in allen Integrationstests.
- `get_capabilities()` gibt `dict` mit `"steps"`-Key zurück (nicht `list[dict]`). Fix: `get_capabilities()["steps"]` beim Aufruf von `build_system_prompt()` in `message_service.py`.

### Completion Notes List

- **T1**: `openai>=1.0` (installiert: openai-2.28.0) in `requirements.txt` und `pyproject.toml` eingetragen. Smoke-Test erfolgreich.
- **T2**: `openai_base_url: str = ""` in `config.py` hinzugefügt. `.env.example` um `OPENAI_BASE_URL=` ergänzt.
- **T3**: LLM-Package `src/gysi_ml/llm/` vollständig erstellt: `__init__.py`, `client.py` (OpenAI-Aufruf mit Fehlerbehandlung), `exceptions.py` (2 Custom-Exceptions), `prompts.py` (System-Prompt + Retry-Prompt), `response_schema.py` (JSON-Schema-Validierung + Markdown-Codeblock-Stripping).
- **T4**: `message_service.py` vollständig reimplementiert: LLM-Aufruf, Gesprächshistorie, Retry-Logik, execute/propose-Routing.
- **T5**: `messages.py`-Route um 422-Handling für `type: "error"` (non-503) erweitert.
- **T6**: 21 Unit-Tests erstellt (4 client, 6 prompts, 11 response_schema) + 6 neue message_service-Tests. Alle grün.
- **T7**: 6 Integrationstests in `test_llm_integration.py`. Alle grün.
- **Gesamt**: 341 Tests grün, 0 Regressions. Coverage der neuen LLM-Module: client.py 86%, prompts.py 100%, response_schema.py 100%, message_service.py 98%.

### File List

**Neue Dateien:**
- `backend/src/gysi_ml/llm/__init__.py`
- `backend/src/gysi_ml/llm/client.py`
- `backend/src/gysi_ml/llm/exceptions.py`
- `backend/src/gysi_ml/llm/prompts.py`
- `backend/src/gysi_ml/llm/response_schema.py`
- `backend/tests/unit/llm/__init__.py`
- `backend/tests/unit/llm/test_client.py`
- `backend/tests/unit/llm/test_prompts.py`
- `backend/tests/unit/llm/test_response_schema.py`
- `backend/tests/integration/test_llm_integration.py`

**Geänderte Dateien:**
- `backend/requirements.txt`
- `backend/pyproject.toml`
- `backend/src/gysi_ml/config.py`
- `backend/.env.example`
- `backend/src/gysi_ml/services/message_service.py`
- `backend/src/gysi_ml/api/routes/messages.py`
- `backend/tests/unit/test_message_service.py`

## Change Log

- 2026-03-15: Story 3.2 implementiert — LLM-Integration mit openai>=1.0, JSON-Schema-Validierung, Retry-Logik, Gesprächshistorie. 341 Tests grün.
