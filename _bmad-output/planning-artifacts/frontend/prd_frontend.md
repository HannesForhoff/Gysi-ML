---
inputDocuments:
  - _bmad-output/planning-artifacts/frontend_implementationsplan_gysi_ml.md
  - _bmad-output/planning-artifacts/prd.md
  - docs/systemkonzept.md
workflowType: prd
projectClassification:
  type: web_frontend
  domain: scientific
  complexity: low_medium
  context: greenfield
  primaryUsers:
    - developer (Hannes)
    - Prof/Wissenschaftlicher Mitarbeiter (Evaluator)
  apiTarget: backend_rest_v1
assumptions:
  - local_only_no_auth
  - single_page
  - async_runs_via_polling
  - spec_summary_only
---

# Product Requirements Document — gysi-ml Frontend

**Author:** John
**Date:** 2026-03-15

## Executive Summary

Das gysi-ml Frontend ist ein **minimalistisches Web‑Chat‑Interface**, das die im Backend definierte konversationelle Pipeline‑Orchestrierung sichtbar und demonstrierbar macht.

**Warum braucht es das?** Das Backend ist als deterministischer Executor + REST‑API konzipiert. Für Demo/Evaluation (Belegarbeit) ist Postman allein zu „technisch“ und vermittelt weder das Bestätigungsprinzip (Proposal‑Mode) noch die Nachvollziehbarkeit (Spec‑Version, Artefakte, Run‑Status) in einer konsistenten Nutzererfahrung.

**Was liefert das Frontend?**

- Chat‑Interaktion (User ↔ Assistant)
- Proposal‑Darstellung + Bestätigung (Confirm)
- Run‑Status (Polling) + Artefakt‑Links
- Kompakter Pipeline‑Status (Spec‑Version + Step‑Übersicht)

Das Frontend führt **keine** ML‑Berechnungen aus, speichert **keine** fachlichen Zustände (nur UI‑State), und respektiert die Kernarchitektur: **LLM/Backend kontrollieren Aktionen**, Frontend rendert und sendet Requests.

## Project Classification

| Dimension | Wert |
|---|---|
| **Projekttyp** | Web Frontend (Single Page App) |
| **Domain** | Scientific / ML & Data Science (UI für Pipeline‑Orchestrierung) |
| **Komplexität** | Low–Medium |
| **Kontext** | Greenfield (Frontend‑Stack noch TBD) |
| **Deployment** | Lokal (Belegarbeit), ohne Auth |
| **Abhängigkeit** | Backend REST API unter `/v1/` |

## Ziele und Nicht‑Ziele

### Ziele (MVP)

1. Eine Person kann eine Session starten, per Chat Anfragen stellen und den Assistant‑Output verstehen.
2. Proposal‑Mode ist klar sichtbar: Vorschlag anzeigen → explizit bestätigen → Run startet.
3. Run‑Ergebnisse + Artefakte (Plots/Reports) sind auffindbar und abrufbar.
4. Pipeline‑Status ist nachvollziehbar (aktive Spec‑Version + Step‑Überblick).
5. Die UX ist robust bei Fehlern (Validation/Run‑Fail/Backend down).

### Nicht‑Ziele (explizit out of scope im MVP)

- Voice (STT/TTS)
- Vollständiger Spec‑Editor (Roh‑JSON) oder komplexe Parameter‑Formulare
- Multi‑Session Management UI (Listen/Archiv/Export) als eigene Seite
- Branching‑UI
- Umfangreiche Dashboards/EDA‑Views

## Default‑Annahmen (bindend)

1. **Lokal, ohne Auth**.
2. **Single Page** (keine Zusatzseiten/Modals als Kern‑UX).
3. **Asynchrone Runs via Polling**: Frontend pollt Run‑Status bis `done|failed`.
4. **Spec nur als Summary sichtbar** (Version + Step‑Liste/Count).

## Personas

1. **Hannes (Developer / Builder):** Will schnell demonstrieren, dass Änderungen per Chat deterministisch zu neuen Spec‑Versionen führen und Artefakte erzeugen.
2. **Evaluator (Prof/WiMi):** Will ohne Tooling‑Hürden prüfen, ob das System methodisch sauber wirkt (Bestätigungsprinzip, Nachvollziehbarkeit, reproduzierbare Runs).

## User Journeys (Frontend‑zentriert)

### Journey 1 — Hannes: Pipeline ändern → ausführen → Artefakte ansehen

- Hannes öffnet die Web‑UI.
- Er sendet eine Anfrage („Bereite Daten vor …“).
- UI zeigt einen Proposal (Steps + Parameter) und einen klaren Bestätigungs‑Call‑to‑Action.
- Nach Bestätigung startet ein Run; UI zeigt `running` und pollt.
- Nach Abschluss sieht Hannes Metriken + Artefakt‑Links (PNG/JSON), öffnet einen Plot.

**Success signal:** Das UI macht sichtbar, dass der Nutzer entscheidet (Confirm) und dass Ergebnisse aus echten Runs stammen.

### Journey 2 — Evaluator: „Was kann das System?“ → Vorschlag verstehen → bestätigen

- Evaluator stellt eine vage Frage („Mach was mit den Daten“).
- UI zeigt Proposal statt still auszuführen.
- Evaluator bestätigt, sieht Run‑Status und Artefakte.

**Success signal:** Die UI vermittelt Didaktik: Vorschlag → Bestätigung → Ergebnis.

### Journey 3 — Fehlerfall: Validierung schlägt fehl

- Nutzer fordert etwas Unmögliches („Nutze Step XYZ“, der nicht existiert).
- Backend antwortet strukturiert mit Validation‑Error.
- UI zeigt verständliche Fehlermeldung und lässt sofort neue Eingabe zu.

**Success signal:** Kein „UI hängt“, keine kryptischen Fehler.

## UX‑Konzept (MVP)

### Informationsarchitektur

- **Hauptbereich:** Chat (Message‑Liste + Eingabefeld)
- **Nebenbereich (Status‑Panel):**
  - aktive Spec‑Version
  - Step‑Übersicht (Name + enabled)
  - letzter Run (Status + wichtigste Metriken)
  - letzte Artefakte (Linkliste)

### Interaktionsregeln

- Senden via Enter, neue Zeile via Shift+Enter.
- Autoscroll: neue Nachrichten sichtbar, aber keine aggressiven Sprünge beim Artefakt‑Polling.
- Proposal‑Darstellung im Chat als „Card“ (rein visuell; keine neue Seite):
  - Liste der vorgeschlagenen Steps
  - Button **„Bestätigen & Ausführen“**
  - „Ändern“ erfolgt über neue Chat‑Nachricht (kein extra Formular).

### Zustände (must‑have)

- `idle`
- `sending_message`
- `proposal_pending`
- `run_polling`
- `run_done`
- `run_failed`
- `validation_error`
- `backend_unreachable`

## API‑Integration (Contract Requirements)

Das Frontend orientiert sich am Backend‑PRD (REST unter `/v1/`). Für MVP braucht das Frontend mindestens folgende Endpoints.

### Required Endpoints

- `POST /v1/sessions`
- `POST /v1/sessions/{session_id}/messages`
- `POST /v1/sessions/{session_id}/confirm`
- `GET /v1/sessions/{session_id}/runs/{run_id}` (Polling)
- `GET /v1/artifacts/{artifact_id}`
- `GET /v1/health` (für „Backend erreichbar?“ Indikator)

### Response‑Typen (MVP‑Minimalstandard)

Für `POST /v1/sessions/{session_id}/messages` muss die Response **typisiert** sein:

- `type: "proposal"` mit `confirmation_required: true` und menschenlesbarer Step‑Liste
- **oder** `type: "result"` (direktes Ergebnis / Run bereits abgeschlossen)
- **oder** `type: "error"` mit validierbaren Feldern (Code, Detail)

Für `POST /confirm` muss die Response ein `run_id` enthalten (Run startet oder ist sofort fertig).

Für `GET /runs/{run_id}` muss die Response enthalten:

- `status: queued|running|done|failed`
- optional `metrics` (key/value)
- optional `artifacts[]` mit `artifact_id`, `label`, `media_type`, `href`

### Polling‑Regeln (Frontend)

- Polling nur, wenn `status` nicht terminal ist.
- Terminal: `done|failed`.
- Backoff bei langer Laufzeit.
- UX‑Timeout: nach z.B. 2 Minuten Hinweis „Run dauert länger“, Polling läuft weiter.

## Functional Requirements (Frontend)

### Session & Chat

- **FE1:** UI kann eine neue Session starten (automatisch oder beim ersten Senden) und `session_id` halten.
- **FE2:** Nutzer kann Chat‑Nachrichten senden; UI zeigt User‑ und Assistant‑Messages in Reihenfolge.
- **FE3:** Während Requests zeigt UI einen klaren Ladezustand (kein doppeltes Senden).

### Proposal / Bestätigungsprinzip

- **FE4:** Wenn Backend `type: proposal` zurückgibt, zeigt UI den Vorschlag als strukturierte Darstellung (Steps + Parameter‑Summary).
- **FE5:** UI bietet einen eindeutigen Bestätigungs‑Mechanismus („Bestätigen & Ausführen“) und ruft `POST /confirm` auf.
- **FE6:** Nutzer kann einen Proposal „modifizieren“, indem er vor Bestätigung eine neue Nachricht sendet (kein Zwang zur Bestätigung).

### Run‑Status & Ergebnisse

- **FE7:** UI kann Run‑Status über `GET /runs/{run_id}` pollen und visuell darstellen.
- **FE8:** Nach Run‑Abschluss zeigt UI eine Ergebniszusammenfassung (mindestens Status + Metriken, wenn vorhanden).
- **FE9:** UI zeigt Artefakt‑Links (PNG/JSON/CSV) aus der Run‑Response und ermöglicht Öffnen (neuer Tab reicht).

### Pipeline‑Status (Spec Summary)

- **FE10:** UI zeigt die aktive Spec‑Version und eine Step‑Übersicht (min. Step‑Namen + enabled) im Status‑Panel.
  - Quelle: bevorzugt aus Backend‑Responses; alternativ über `GET /spec` (wenn Backend das anbietet und UI es nutzen soll).

### Fehlerbehandlung

- **FE11:** Validation‑Errors (422 oder `type:error`) werden verständlich angezeigt (kein „Silent Fail“).
- **FE12:** Backend‑Unreachability wird erkannt (z.B. `GET /health` fail) und angezeigt, ohne dass die UI „einfriert“.
- **FE13:** Run‑Fehler (`failed`) werden angezeigt inkl. kurzer Ursache (falls Backend `error_message` liefert).

## Non‑Functional Requirements

### Performance

- UI bleibt responsiv bei ≥ 100 Messages in der Session.
- Polling darf den Browser nicht spürbar belasten (Backoff, keine unnötigen Re‑Renders).

### Reliability & UX Robustness

- Kein doppeltes Confirm (idempotent auf UI‑Seite: Button disabled während Request).
- Bei Reload: MVP darf Session verlieren; optionaler Enhancer ist Persistenz der `session_id` in `localStorage`.

### Security (Baseline)

- UI rendert Message‑Content als Text (keine HTML‑Interpretation) → reduziert XSS‑Risiko.
- Keine Secrets im Frontend (keine API‑Keys).

### Testbarkeit

- Mindestens Smoke‑Tests: Chat send/receive, Proposal confirm, Run polling, Artifact link.

## Milestones (Delivery Plan)

- **M0 Setup:** Projekt scaffold + Dev‑Server + env Backend‑URL.
- **M1 UI Mock‑First:** Chat + Status‑Panel + Fixture‑Responses.
- **M2 Backend‑Integration:** Sessions + Messages (typed responses).
- **M3 Proposal/Confirm + Polling:** Confirm‑Flow + Run‑Status + Artefakte.
- **M4 Hardening:** Fehlerfälle, Long runs, reload‑Verhalten.

## Risiken & Dependencies

- **Contract Drift:** Backend‑Responses sind noch nicht implementiert → Gegenmaßnahme: früh ein minimaler OpenAPI‑Contract und Mock‑Server/Fixtures.
- **Async vs. Sync:** Backend‑Implementierung kann Runs synchron blockieren → UI muss beide Fälle verkraften (sofort `done` oder `running` + Polling).
- **Artefakt‑Serving:** CORS/Content‑Type muss stimmen, sonst „Downloads funktionieren nicht“.

## Definition of Done (MVP)

- Chat funktioniert end‑to‑end gegen ein laufendes Backend (Session → Message → Proposal → Confirm → Run → Artefakt).
- Status‑Panel zeigt Spec‑Summary + letzten Run.
- Polling ist stabil (keine Endlosschleifen, klare Zustände).
- Fehlerfälle (Validation/Backend down/Run failed) sind verständlich und nicht-blockierend.
