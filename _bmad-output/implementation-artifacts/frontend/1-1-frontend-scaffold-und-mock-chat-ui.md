# Story 1.1: Frontend-Scaffold und Mock-Chat UI

Status: done

## Story

Als ein Nutzer (Hannes/Evaluator),
möchte ich die Frontend-App lokal starten und einen vollständigen Chat-Flow gegen Mock-Responses nutzen können (inkl. Status-Panel),
damit das UI parallel zum Backend implementierbar ist und die spätere `/v1`-Integration ohne UX-Überraschungen erfolgt.

## Acceptance Criteria

1. **[Scaffold & Dev-Server]** Im Ordner [frontend/](frontend/) existiert ein SPA-Scaffold (Vite + React + TypeScript).
   - `npm install` funktioniert.
   - `npm run dev` startet lokal und rendert die App.
   - `npm run build` läuft ohne Fehler.

2. **[Single-Page Layout]** Die App rendert genau eine Seite mit:
   - Hauptbereich „Chat“ (Message-Liste + Composer)
   - Nebenbereich „Status-Panel“ (Backend-Status, Spec-Summary Placeholder, letzter Run Placeholder, letzte Artefakte Placeholder)
   - Keine zusätzlichen Views/Routes/Modals/Settings im MVP.

3. **[Composer: Enter vs Shift+Enter]**
   - **Given** der Composer hat Fokus
   - **When** Enter gedrückt wird
   - **Then** wird gesendet
   - **And** der Fokus bleibt nach dem Send im Composer
   - **And** Shift+Enter fügt eine neue Zeile ein (kein Send)

4. **[Kein Doppelsenden]** Während ein Send-Request läuft:
   - Send wird eindeutig als „läuft“ angezeigt
   - Send ist deaktiviert (UI-seitige Idempotenz)

5. **[Chat-History Rendering]**
   - User- und Assistant-Messages werden chronologisch in einer Liste gerendert.
   - Message-Content wird als Text gerendert (keine HTML-Interpretation; XSS-Baseline).
   - UI bleibt responsiv bei ≥ 100 Messages (kein O(n²)-Render/State-Update pro Nachricht).

6. **[Mock-First: Typed Responses]** Im Mock-Modus (Env Toggle) können mindestens diese Response-Typen deterministisch simuliert werden:
   - `proposal` (inkl. Steps + Parameter-Summary)
   - `result` (inkl. Status + optional metrics + optional artifacts[])
   - `error` (inkl. kurzer Message + optional Details)

7. **[UI-State Machine]** Must-have UI-States sind im Code explizit modelliert (z.B. via Reducer):
   - `idle`, `sending_message`, `proposal_pending`, `run_polling`, `run_done`, `run_failed`, `validation_error`, `backend_unreachable`
   - Kein Deadend: Nach `validation_error` ist sofort wieder Senden möglich.

8. **[Status-Panel (MVP Placeholder)]**
   - Im Mock-Modus zeigt das Status-Panel zumindest: „Mock aktiv“ + (Fixture) Spec-Summary + last run summary + artifacts.
   - Im Real-Backend-Modus (später) existieren bereits die UI-Felder, aber Story 1.1 muss noch keine echten `/v1`-Calls implementieren.

9. **[Konfiguration]**
   - Backend-Base-URL kommt ausschließlich aus Env/Build-Time Config (kein UI-Setting im MVP).
   - Ein `.env.example` im Frontend dokumentiert die nötigen Variablen.

10. **[Smoke Tests]** Mindestens Smoke-Tests existieren und laufen lokal:
   - Composer Enter/Shift+Enter Verhalten
   - Mock send/receive: User-Message + Assistant-Message erscheinen
   - „kein Doppelsenden“: Send disabled während Request

## Tasks / Subtasks

- [x] **T1 — Scaffold (Vite + React + TS)** (AC: 1, 2)
   - [x] Initialisieren: Vite React TS Projekt unter [frontend/](frontend/)
   - [x] Minimaler Start-Screen durch App-Layout ersetzen (Chat + Status-Panel)
   - [x] `npm run dev` / `npm run build`

- [x] **T2 — Env-Konfiguration & Modus-Switch** (AC: 6, 8, 9)
   - [x] Env-Variablen (Vite): `VITE_GYSI_BACKEND_BASE_URL`, `VITE_GYSI_USE_MOCK`
   - [x] `.env.example` anlegen
   - [x] Einen einzigen „Transport“-Layer vorsehen, der Mock vs Real kapselt (z.B. `src/api/transport.ts`)

- [x] **T3 — Datenmodelle (Frontend) für typed responses** (AC: 6, 7)
   - [x] Types/Interfaces für `ChatMessage`, `Proposal`, `Result`, `Error` (minimal nach PRD/UX)
   - [x] UI-State Machine Types (`UiState` Union)

- [x] **T4 — Mock-Adapter + Fixtures** (AC: 6)
   - [x] Fixtures als JSON unter `src/fixtures/` (mind. proposal/result/error)
   - [x] Deterministische Auswahlregel (Keyword im User-Text)
   - [x] Simulierte Latenz (kurz) um Ladezustand sichtbar zu machen

- [x] **T5 — UI Komponenten** (AC: 2–5, 7–8)
   - [x] `ChatLayout` (2-Spalten: Chat + Status-Panel)
   - [x] `MessageList` (chronologisch; Text-Rendering)
   - [x] `Composer` (Enter send, Shift+Enter newline, disabled state)
   - [x] `StatusPanel` (Mock Indicator + Spec/Run/Artifacts)

- [x] **T6 — State Management (Reducer)** (AC: 4, 7)
   - [x] Reducer/Actions für send start/success/error
   - [x] Keine Mehrfach-Requests parallel im MVP (ein inflight Request genügt)

- [x] **T7 — Smoke Tests** (AC: 10)
   - [x] Test-Setup (Vitest + React Testing Library)
   - [x] Tests für Composer + Mock send/receive + kein Doppelsenden

## Dev Notes

### Guardrails (MVP bindend)

- Single Page: keine zusätzlichen Seiten/Routes/Modals als Kern-UX.
- Kein Spec-JSON-Editor: nur Status-Panel Summary/Placeholder.
- Kein UI-Setting für Backend-URL: ausschließlich Env/Build-Time.
- Message-Content immer als Text rendern (XSS-Baseline).
- Keine Secrets im Frontend.

### Contract & Drift

- Ziel-Contract ist `/v1/...` (siehe Frontend PRD/UX). Implementationsplan enthält ältere `/api/...` Beispiele — in Story 1.1 nur Mock-First, aber bereits so strukturieren, dass später `/v1` sauber angeschlossen werden kann.

### Empfohlene Ordnerstruktur (minimal)

- `frontend/`
  - `src/api/` (Transport/Client, später echte `/v1` Requests)
  - `src/fixtures/` (Mock JSON)
  - `src/state/` (Reducer/State Machine)
  - `src/components/` (Composer, MessageList, ProposalCard, StatusPanel)

### Testing

- In dieser Story nur Smoke-Tests im Mock-Modus.
- E2E (Playwright) kann später folgen, wenn Real-Backend stabil ist.

### Accessibility Basics

- Tastaturbedienung: Tab-Order logisch (Composer → Send → Proposal CTA → Artefakte).
- Fokus bleibt stabil (nach Send im Composer).

### References

- [_bmad-output/planning-artifacts/frontend/prd_frontend.md](_bmad-output/planning-artifacts/frontend/prd_frontend.md) (Ziele, UX-Konzept, API-Integration, States, Milestones)
- [_bmad-output/planning-artifacts/frontend/ux-spec.md](_bmad-output/planning-artifacts/frontend/ux-spec.md) (Layout, Typed Responses, State Machine, Copy)
- [_bmad-output/planning-artifacts/frontend/ux-design-specification.md](_bmad-output/planning-artifacts/frontend/ux-design-specification.md) (Experience Principles, Fehler-UX, Proposal vs Ergebnis)
- [_bmad-output/planning-artifacts/frontend/frontend_implementationsplan_gysi_ml.md](_bmad-output/planning-artifacts/frontend/frontend_implementationsplan_gysi_ml.md) (Mock-First/Contract-First, Milestones M0/M1)
- [_bmad-output/planning-artifacts/frontend/epics.md](_bmad-output/planning-artifacts/frontend/epics.md) (Epic 1 / Story 1.1)

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Debug Log References

- (falls nötig) Frontend Console Logs + Test Output

### Completion Notes List

- Vite+React+TS Scaffold erzeugt; Startscreen durch Single-Page Chat+Status-Panel ersetzt.
- Mock-First Transport (Fixture-basiert) + deterministische Auswahlregel + kurze Latenz.
- UI-State-Machine explizit als Reducer modelliert.
- Smoke Tests via Vitest/RTL: Enter/Shift+Enter, Mock send/receive, kein Doppelsenden.
- UI optisch „polished“ (Shell-Card, Chat-Bubbles, Status-Cards) bei gleicher Single-Page-IA.

### File List
- frontend/src/index.css

- frontend/package.json
- frontend/package-lock.json
- frontend/tsconfig.app.json
- frontend/vite.config.ts
- frontend/.env.example
- frontend/public/mock/metrics.json
- frontend/src/App.tsx
- frontend/src/App.css
- frontend/src/env.ts
- frontend/src/types.ts
- frontend/src/api/mockTransport.ts
- frontend/src/api/realTransport.ts
- frontend/src/api/transport.ts
- frontend/src/state/chatReducer.ts
- frontend/src/components/ChatLayout.tsx
- frontend/src/components/Composer.tsx
- frontend/src/components/MessageList.tsx
- frontend/src/components/StatusPanel.tsx
- frontend/src/fixtures/proposal.json
- frontend/src/fixtures/result.json
- frontend/src/fixtures/error.json
- frontend/src/setupTests.ts
- frontend/src/vitest.d.ts
- frontend/src/App.test.tsx
