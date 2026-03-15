---
stepsCompleted: [step-01-validate-prerequisites]
inputDocuments:
  - _bmad-output/planning-artifacts/prd_frontend.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/ux-spec.md
  - _bmad-output/planning-artifacts/frontend_implementationsplan_gysi_ml.md
  - _bmad-output/planning-artifacts/backend/prd.md
  - _bmad-output/planning-artifacts/backend/implementation-readiness-report-2026-03-14.md
  - docs/systemkonzept.md
  - docs/architecture/repo_structure.md
---

# gysi-ml Frontend - Epic Breakdown

## Overview

Dieses Dokument beschreibt die Epics und Stories für das **gysi-ml Frontend (MVP)** als Single-Page Web-Chat-Interface inkl. Backend-Integration.

## Requirements Inventory

### Functional Requirements

FR1 (FE1): UI kann eine neue Session starten (automatisch oder beim ersten Senden) und `session_id` im UI-State halten.
FR2 (FE2): Nutzer kann Chat-Nachrichten senden; UI zeigt User- und Assistant-Messages in chronologischer Reihenfolge.
FR3 (FE3): Während Requests zeigt die UI einen klaren Ladezustand und verhindert doppeltes Senden.
FR4 (FE4): Bei Backend-Response `type: "proposal"` zeigt die UI den Vorschlag als strukturierte Darstellung (Steps + Parameter-Summary).
FR5 (FE5): UI bietet einen eindeutigen Bestätigungs-Mechanismus („Bestätigen & Ausführen“) und ruft `POST /v1/sessions/{session_id}/confirm` auf.
FR6 (FE6): Nutzer kann einen Proposal vor Bestätigung „modifizieren“, indem er eine neue Nachricht sendet (kein extra Formular).
FR7 (FE7): UI kann Run-Status über `GET /v1/sessions/{session_id}/runs/{run_id}` pollen und visuell darstellen.
FR8 (FE8): Nach Run-Abschluss zeigt UI eine Ergebniszusammenfassung (mindestens Status + Metriken, falls vorhanden).
FR9 (FE9): UI zeigt Artefakt-Links (PNG/JSON/CSV) aus der Run-Response und ermöglicht Öffnen (neuer Tab reicht).
FR10 (FE10): UI zeigt Spec-Summary im Status-Panel (aktive Spec-Version + Step-Übersicht mit enabled), bevorzugt aus Backend-Responses, alternativ via `GET /v1/sessions/{session_id}/spec`.
FR11 (FE11): Validation-Errors (422 oder `type: "error"`) werden verständlich angezeigt, ohne die UI zu blockieren.
FR12 (FE12): Backend-Unreachability wird erkannt (z.B. via `GET /v1/health`/Network-Fail) und als Zustand `backend_unreachable` angezeigt.
FR13 (FE13): Run-Fehler (`failed`) werden angezeigt inkl. kurzer Ursache (falls Backend `error_message`/`detail` liefert).
FR14 (ImplPlan M4): Undo/History-Effekte werden sichtbar: nach Undo-Aktion (als normale Assistant-Message) aktualisiert sich die aktive Spec-Version im Status-Panel.

### NonFunctional Requirements

NFR1 (Performance): UI bleibt responsiv bei ≥ 100 Messages in einer Session.
NFR2 (Performance): Polling belastet den Browser nicht spürbar (Backoff, keine unnötigen Re-Renders).
NFR3 (Reliability): Kein doppeltes Confirm (Button disabled während Request; UI-seitige Idempotenz).
NFR4 (Reliability): Bei Reload darf MVP die Session verlieren; optionaler Enhancer ist Persistenz der `session_id` in `localStorage`.
NFR5 (Security): UI rendert Message-Content als Text (keine HTML-Interpretation) zur Reduktion von XSS-Risiko.
NFR6 (Security): Keine Secrets im Frontend (keine API-Keys).
NFR7 (Testbarkeit): Mindestens Smoke-Tests für Chat send/receive, Proposal confirm, Run polling, Artifact link.

### Additional Requirements

- **Scope-Constraints (MVP bindend):** lokal, ohne Auth; Single Page; keine zusätzlichen Views/Modals/Filter/Settings als Kern-UX; Spec nur als Summary sichtbar (kein Roh-JSON-Editor).
- **Backend als Quelle der Wahrheit:** Frontend führt keine ML-Berechnungen aus und speichert keinen fachlichen Zustand (nur UI-State).
- **API-Contract (Frontend-relevant):** `/messages` ist typisiert (`proposal|result|error`) und `proposal` erfordert explizite Bestätigung; `confirm` liefert `run_id`; Run-Status liefert `status` + optional `metrics` + optional `artifacts[]`.
- **Sync/Async-Toleranz:** UI muss sowohl sofort terminale Responses (z.B. `result`) als auch `run_id` + Polling bis `done|failed` unterstützen.
- **Artefakte:** Artefakte werden als Links geöffnet (neuer Tab genügt); `media_type` muss berücksichtigt werden (z.B. `image/png`, `application/json`).
- **Contract Drift Risiko:** Implementationsplan nutzt `/api/chat` + `/api/jobs/...`, PRDs definieren `/v1/...` — Contract muss finalisiert werden (präferiert: `/v1` als Backend-Standard + OpenAPI `/openapi.json`).
- **CORS & Lokalbetrieb:** Backend ist für `localhost`-Origins CORS-bereit; Frontend benötigt konfigurierbare Backend-Base-URL (env/build-time, kein UI-Setting im MVP).
- **Mock-First/Contract-First:** Frontend soll mit Fixtures/MOCK-Responses startbar sein und per Env zwischen Mock und echtem Backend umschalten können.

### UX Design Requirements

UX-DR1: Single-Page Layout mit Hauptbereich „Chat“ (Message-Liste + Composer) und Nebenbereich „Status-Panel“ (Backend-Status, Spec-Summary, letzter Run, letzte Artefakte).
UX-DR2: Composer-Verhalten: Enter sendet; Shift+Enter erzeugt neue Zeile; während Request ist Senden klar als „läuft“ erkennbar und verhindert Doppelsends.
UX-DR3: Typisierte Response-Rendering-Regeln: `proposal` → Proposal-Card; `result` → Result-Message (Status/Metriken/Artefakte); `error`/422 → Error-Message (kurz + optional Details).
UX-DR4: Proposal-Card Pflichtinhalte: Label „Vorschlag (noch nicht ausgeführt)“, Step-Liste (Name + Parameter-Summary), CTA „Bestätigen & Ausführen“.
UX-DR5: Confirm-UX: Confirm ist eine bewusste Aktion; Button ist während Request disabled; nach Confirm wird ein Run-Statuswechsel sichtbar.
UX-DR6: Polling-UX: Polling nur bis terminal (`done|failed`) mit Backoff; bei Long Run (~2 Minuten) Hinweis „Run dauert länger – wir aktualisieren weiter.“
UX-DR7: Ruhiges Autoscroll-Verhalten: neue Nachrichten sichtbar, Polling-Updates verursachen keine aggressiven Scroll-Sprünge.
UX-DR8: Backend-Reachability: sichtbarer Zustand `backend_unreachable` (z.B. Health-Fail/Network) mit handlungsfähiger Copy („Backend nicht erreichbar…“).
UX-DR9: Run-Status-Visualisierung: Status-Chip/Label für `queued|running|done|failed` (nicht nur über Farbe kommuniziert).
UX-DR10: Artefakt-Linkliste: jedes Artefakt mit Label + Media-Type; Klick öffnet in neuem Tab; Fehlerfall wird verständlich angezeigt.
UX-DR11: Accessibility (Desktop): vollständig per Tastatur bedienbar (logische Tab-Order); sichtbarer Fokus; Fokus bleibt nach Send im Composer; nach Confirm keine Fokus-Sprünge.
UX-DR12: Copy & Tonalität (Deutsch): konsistente Begriffe (Vorschlag/Bestätigen/Run) und klare Microcopy für Fehler/Long Runs.
UX-DR13: State Machine: Must-Have States (`idle`, `sending_message`, `proposal_pending`, `run_polling`, `run_done`, `run_failed`, `validation_error`, `backend_unreachable`) sind im UI sauber modelliert und führen zu keinen Deadends.

### FR Coverage Map

| FR | Epic | Kurzbeschreibung |
|---|---|---|
| FR1 | Epic 1 | Session starten & `session_id` halten |
| FR2 | Epic 1 | Chat-Nachrichten senden & anzeigen |
| FR3 | Epic 1 | Ladezustände & Doppelsenden verhindern |
| FR4 | Epic 2 | Proposal als Card strukturiert rendern |
| FR5 | Epic 2 | Confirm auslösen („Bestätigen & Ausführen“) |
| FR6 | Epic 2 | Proposal via neue Nachricht modifizieren |
| FR7 | Epic 3 | Run-Status pollen bis terminal |
| FR8 | Epic 3 | Ergebnis-Summary (Status/Metriken) anzeigen |
| FR9 | Epic 3 | Artefakt-Links anzeigen & öffnen |
| FR10 | Epic 1 | Spec-Summary (Version + Steps) im Status-Panel |
| FR11 | Epic 1 | Validation-Errors verständlich anzeigen |
| FR12 | Epic 1 | Backend-Unreachability erkennen/anzeigen |
| FR13 | Epic 3 | Run-Fail (`failed`) inkl. Ursache anzeigen |
| FR14 | Epic 1 | Undo/History-Effekt sichtbar machen |

## Epic List

### Epic 1: Chat starten & Systemzustand nachvollziehen

Nutzer kann die Web-UI öffnen, automatisch eine Session nutzen, Nachrichten senden/sehen und jederzeit den Systemzustand verstehen (Spec-Summary, Backend-Status, verständliche Fehler, Undo-Feedback).

**FRs covered:** FR1, FR2, FR3, FR10, FR11, FR12, FR14

### Epic 2: Vorschläge prüfen und kontrolliert ausführen (Proposal → Confirm)

Nutzer sieht Vorschläge als strukturierte Proposal-Card und entscheidet bewusst: bestätigen & ausführen oder durch neue Nachricht modifizieren.

**FRs covered:** FR4, FR5, FR6

### Epic 3: Runs verfolgen und Ergebnisse/Artefakte abrufen

Nutzer kann nach Confirm Runs pollen, Ergebnis-Summary (Status/Metriken) sehen, Artefakte öffnen und Fehlerfälle (`failed`) verstehen.

**FRs covered:** FR7, FR8, FR9, FR13

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic {{N}}: {{epic_title_N}}

{{epic_goal_N}}

<!-- Repeat for each story (M = 1, 2, 3...) within epic N -->

### Story {{N}}.{{M}}: {{story_title_N_M}}

As a {{user_type}},
I want {{capability}},
So that {{value_benefit}}.

**Acceptance Criteria:**

**Given** {{precondition}}
**When** {{action}}
**Then** {{expected_outcome}}
**And** {{additional_criteria}}
