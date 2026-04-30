# Bug 1.15 — LLM-Rollback via Chat: System-Prompt hat keine spec_ids, target_spec_id nicht ermittelbar

**Gefunden**: 2026-04-25
**Status**: ✅ Gefixt (2026-04-30)
**Priorität**: 🟠 Hoch (Feature komplett broken wenn via Chat aufgerufen)
**Kategorie**: Backend (`message_service.py`, `prompts.py`) + LLM-Prompt-Design
**Session**: Party-Mode-Analyse 25.04.2026 — strukturelles Loch identifiziert
**Wahrscheinlich Olis Bug**: "Rollback zu v4 führt tatsächlich zu v1 — falsche Versionsreferenz"

---

## Beobachtetes Fehlverhalten (Oli's Session-Notiz)

> "Rollback zu v4 führt tatsächlich zu v1 — falsche Versionsreferenz"

**Rekonstruierter Ablauf:**
1. Nutzer sagt "Führe einen Rollback zu Version 4 durch" (Chat)
2. LLM wird aufgerufen mit `action: "rollback"` und einer `target_spec_id`
3. Die ID ist **halluziniert** (LLM kennt keine echten UUIDs) oder aus einem Muster abgeleitet
4. Backend findet zufällig eine andere Spec-Version oder führt eine falsche aus
5. Ergebnis: "Rollback zu v4" landet bei v1 oder einer anderen falschen Version

---

## Technische Ursachenanalyse

### Kern-Problem: LLM hat im System-Prompt keine spec_ids

`build_system_prompt()` in `prompts.py` übergibt dem LLM:

```python
current_spec_section = (
    "\n\n## Aktuelle Session-Spec (Ausgangs-Spec für Modifikationen)\n\n"
    + json.dumps(current_spec, indent=2, ensure_ascii=False)
)
```

`current_spec` ist die **rohe Spec** (`{"steps": [...]}`). Sie enthält keine `spec_id`, keine Versionsnummer und keine History.

Das LLM generiert folgende JSON-Response:
```json
{
  "action": "rollback",
  "target_spec_id": "...",   ← UUID halluziniert oder leer
  "spec": {"steps": []},
  "explanation": "Rollback zu v4 ausgeführt."
}
```

### Zweites Problem: System-Prompt-Abschnitt für Rollback fehlt vollständig

In `SYSTEM_PROMPT_TEMPLATE` gibt es Abschnitte für:
- Re-Execution einer gespeicherten Spec
- Spec-Modifikation
- Run-Vergleich

Es gibt **keinen Abschnitt** der dem LLM erklärt:
- Wie Rollback funktioniert
- Dass `target_spec_id` eine UUID ist
- Wo die gültigen IDs herkommen

### Dritter Aspekt: LLM-Response-Schema hat `target_spec_id` optional

```python
# response_schema.py
"target_spec_id": {"type": "string"},  # optional, nicht required
```

Das LLM kann Rollback ohne `target_spec_id` zurückgeben — `message_service.py` abfängt das:

```python
target_spec_id = parsed.get("target_spec_id")
if not target_spec_id:
    return {"type": "error", "message": "Rollback: target_spec_id fehlt."}
```

Das schützt vor leerem Feld, aber nicht vor **halluzinierten UUIDs**, die zufällig trotzdem einen Treffer ergeben.

### Vierter Aspekt: Korrekter Rollback-Pfad (via UI-Button) funktioniert

Der UI-Button-Pfad ist korrekt implementiert:

```
VersionTreeGraph.tsx → onRollback(node.spec_id)  ← echte UUID aus specHistory-State
App.tsx → handleRollback(targetSpecId)
healthApi.ts → performRollback(baseUrl, sessionId, targetSpecId)
rollback.py → spec_repository.rollback_to(session_id, target_spec_id)
```

Der UI-Button sendet die echte `spec_id` die `fetchSpecTree()` vom Backend geladen hat. Das funktioniert korrekt.

**Das Problem ist ausschließlich der Chat-Pfad** (LLM → message_service.py → rollback).

---

## Warum dieses Feature prinzipiell fragil ist

Das LLM-basierte Rollback via Chat ist architektonisch problematisch:

1. **UUIDs sind für LLMs nicht handhabbar**: Das LLM kann `spec_id = "3f2a7b..." ` nicht aus dem Gespräch korrekt reproduzieren
2. **Versions-Nummern sind stabil, UUIDs nicht**: Der Nutzer sagt "Rollback zu v4" — das LLM müsste v4 auf die richtige UUID mappen
3. **Das Mapping fehlt**: Der System-Prompt hat weder `version → spec_id`-Mapping noch die vollständige Spec-History

---

## Lösungsoptionen

### Option A — Rollback-History im System-Prompt (minimaler Eingriff)

`build_system_prompt()` bekommt die Version-History der Session:

```python
def build_system_prompt(
    capabilities: list[dict],
    current_spec: dict | None = None,
    df_stats: dict | None = None,
    spec_history: list[dict] | None = None,   # ← NEU
) -> str:
```

Der System-Prompt erhält einen neuen Abschnitt:

```
## Verfügbare Spec-Versionen (für Rollback)

| Version | spec_id                              | Erstellt          | Zusammenfassung         |
|---------|--------------------------------------|-------------------|-------------------------|
| v1      | 3f2a7b12-...                         | 2026-04-25 10:42  | Initialversion           |
| v2      | 8d1e4c99-...                         | 2026-04-25 10:48  | impute_missing hinzugefügt |
| v3      | a4f20d11-...                         | 2026-04-25 11:02  | correlation_filter hinzugefügt |

Für Rollback: Setze `action: "rollback"` und `target_spec_id` auf die korrekte spec_id.
```

**Vorteil:** LLM hat echte UUIDs im Context → kann sie korrekt zurückgeben  
**Nachteil:** System-Prompt wird länger, kostet mehr Tokens

**Änderungen:**
- `backend/src/gysi_ml/llm/prompts.py` — `build_system_prompt()` + Template erweitern
- `backend/src/gysi_ml/services/message_service.py` — `spec_history` an `build_system_prompt()` übergeben
- `backend/src/gysi_ml/persistence/spec_repository.py` — `get_all_specs_for_session()` schon vorhanden ✓

### Option B — LLM nutzt Versionsnummer, Backend löst spec_id auf (robuster)

Das LLM-Response-Schema wird erweitert um `target_version`:

```python
# response_schema.py
"target_version": {"type": "string"},  # z.B. "v4" — NEU
```

`message_service.py` löst die Version auf die spec_id auf:

```python
if action == "rollback":
    target_version = parsed.get("target_version")
    target_spec_id = parsed.get("target_spec_id")

    if target_version and not target_spec_id:
        # Versionsnummer → spec_id auflösen
        target_spec_id = spec_repository.get_spec_id_by_version(
            session_id=session_id, version=target_version, db_path=db_path
        )
        if not target_spec_id:
            return {"type": "error", "message": f"Version '{target_version}' nicht gefunden."}
```

System-Prompt-Ergänzung (nur Versionnummern, keine UUIDs):
```
## Rollback

Für Rollback zu einer früheren Version:
- Setze `action: "rollback"`
- Setze `target_version: "<version>"` (z.B. "v3") — aus der Spec-History
- Die aktuelle Session-Spec ist Version {current_version}.
  Frühere Versionen: {alle vorhandenen Versionen, z.B. "v1, v2, v3"}
```

**Vorteil:** LLM muss keine UUIDs kennen — nur stabile Versionsnummern  
**Vorteil:** `get_spec_id_by_version()` in `spec_repository.py` existiert bereits ✓  
**Empfehlung:** Diese Option ist robuster und LLM-freundlicher

---

## Empfehlung

**Option B** implementieren:

1. Minimale Schema-Änderung: `target_version` zum Response-Schema hinzufügen
2. System-Prompt: Rollback-Abschnitt mit verfügbaren Versionen ergänzen
3. `message_service.py`: `target_version → spec_id`-Auflösung vor dem `rollback_to()`-Aufruf

**Dateien die Amelia ändern muss:**

- `backend/src/gysi_ml/llm/response_schema.py` — `target_version` als optionales Feld
- `backend/src/gysi_ml/llm/prompts.py` — `build_system_prompt()` + Template um Rollback-Abschnitt ergänzen, verfügbare Versionen injizieren
- `backend/src/gysi_ml/services/message_service.py` — `spec_history` laden, an Prompt übergeben; `target_version → spec_id`-Auflösung im `rollback`-Handler

---

## Abgrenzung: Was nicht geändert werden muss

- `spec_repository.rollback_to()` — korrekt implementiert ✓
- `spec_repository.get_spec_id_by_version()` — existiert und funktioniert ✓
- `api/routes/rollback.py` — UI-Button-Pfad ist korrekt ✓
- `frontend/` — kein Änderungsbedarf für diesen Bug ✓

---

## Verwandte Bugs

- **Bug 1.12** — Spec-Versionierung Idempotenz + cast_dtype-Reihenfolge
- **Bug 1.13** — Confirm-Pfad kein Merge (mode="all") + Response-Felder + InfoPanel
- **Bug 1.14** — Confirm-Pfad kein Merge (mode="step_by_step")
- **Bug 1.15** — dieser Bug (LLM-Rollback via Chat: keine spec_ids im Prompt)
