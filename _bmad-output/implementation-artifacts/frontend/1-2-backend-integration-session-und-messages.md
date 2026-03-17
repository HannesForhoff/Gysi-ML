# Story 1.2: Backend-Integration (Session + Messages) nach /v1 Contract

Status: done

## Story

Als ein Nutzer,
möchte ich im Frontend automatisch eine Backend-Session erstellen und Chat-Messages an `/v1/sessions/{session_id}/messages` senden,
damit die UI echte typed Responses vom Backend anzeigen kann.

## Acceptance Criteria

1. **[Session Auto-Create + Message Send]**

   **Given** das Backend ist erreichbar
   **When** ich die erste Nachricht sende
   **Then** wird (falls nötig) `POST /v1/sessions` aufgerufen und `session_id` im UI-State gehalten
   **And** anschließend `POST /v1/sessions/{session_id}/messages` aufgerufen

2. **[Backend Unreachable]**

   **Given** das Backend ist nicht erreichbar
   **When** ein Request fehlschlägt
   **Then** wechselt die UI in den Zustand `backend_unreachable` und blockiert nicht dauerhaft

3. **[HTTP-Fehler ≠ Backend down]**

  **Given** das Backend ist erreichbar, aber antwortet mit HTTP 4xx/5xx (z.B. weil `/messages` noch nicht implementiert ist)
  **When** ich eine Nachricht sende
  **Then** wird eine typed `error`-Message angezeigt (UI bleibt bedienbar)
  **And** die UI wechselt **nicht** in `backend_unreachable`

## Tasks / Subtasks

- [x] **T1 — Session-ID im UI-State modellieren** (AC: 1)
  - [x] `ChatState` um `sessionId: string | null` erweitern
  - [x] Reducer-Actions erweitern, sodass nach erfolgreichem Real-Backend-Call die `sessionId` im State gespeichert/aktualisiert wird
  - [x] Mock-Modus darf weiterhin ohne Backend funktionieren (Session-ID kann z.B. konstant `"mock"` sein, muss aber nicht im UI angezeigt werden)

- [x] **T2 — Real Transport: `/v1/sessions` + `/v1/sessions/{id}/messages` implementieren** (AC: 1, 2)
  - [x] In `frontend/src/api/realTransport.ts` echte Requests via `fetch` implementieren (kein neues HTTP-Library)
  - [x] Wenn `sessionId` fehlt: `POST {baseUrl}/v1/sessions` (Body optional, z.B. leer) und `session_id` aus Response lesen
  - [x] Danach: `POST {baseUrl}/v1/sessions/{session_id}/messages` mit Body `{"text": "..."}`
  - [x] Response-Parsing: JSON muss auf das bestehende `AssistantResponse`-Union gemappt werden
    - [x] Wenn Backend bereits `{type: "proposal"|"result"|"error", ...}` liefert: direkt übernehmen
    - [x] Wenn Backend (oder Zwischenstand) `{error, detail, code}` liefert: in `{type:"error", message: detail ?? error, details: code}` mappen
  - [x] Fehlerklassifizierung (wichtig für AC: 2):
    - [x] **Network/CORS/Fetch-throw** → Fehler **werfen**, damit UI `backend_unreachable` setzt
    - [x] **HTTP non-2xx mit JSON** → **nicht werfen**, sondern als `{type:"error", ...}` zurückgeben (UI bleibt benutzbar)

- [x] **T3 — Transport-Signaturen konsistent refactoren (Mock + Real)** (AC: 1)
  - [x] `sendAssistantMessage` so anpassen, dass die Session-ID als Input/Output transportiert wird (z.B. `({ userText, sessionId }) => { sessionId, response }`)
  - [x] `frontend/src/api/transport.ts` entsprechend anpassen (Mock vs Real bleibt über `VITE_GYSI_USE_MOCK` gesteuert)
  - [x] `frontend/src/App.tsx` anpassen, sodass nach jedem erfolgreichen Call die Session-ID aus dem Transport im State landet

- [x] **T4 — Tests (ohne echtes Backend) für Session+Messages Sequenz** (AC: 1, 2)
  - [x] Unit-Tests für `realTransport` (Fetch mocken):
    - [x] Erstes Senden ohne `sessionId` ruft zuerst `/v1/sessions` dann `/messages` auf
    - [x] Zweites Senden mit `sessionId` ruft **nicht** erneut `/v1/sessions` auf
    - [x] Network-Error (fetch rejected/throws) führt zu Throw (UI: `backend_unreachable` via App-Catch)
    - [x] HTTP 4xx/5xx mit JSON führt zu `{type:"error"...}` (kein Throw)
  - [x] Bestehende Smoke-Tests aus Story 1.1 dürfen nicht brechen

## Dev Notes

### Guardrails (MVP bindend)

- Single Page: keine zusätzlichen Seiten/Routes/Modals/Settings.
- Kein Proposal-Card/Confirm/Polling in dieser Story (kommt in Epic 2/3).
- Backend-Base-URL weiterhin ausschließlich via Env (`VITE_GYSI_BACKEND_BASE_URL`).
- Mock-Mode muss weiterhin Default-fähig sein (`VITE_GYSI_USE_MOCK=1`).
- Keine Secrets im Frontend; Message-Content weiterhin als Text rendern (XSS-Baseline).

### Contract-Quelle / Drift-Hinweis

- Ziel-Contract ist `/v1/...` (Frontend PRD/UX + Backend PRD).
- Der ältere Implementationsplan enthält `/api/chat` und `/api/jobs/...` Beispiele — **nicht** für diese Story verwenden.
- Backend-Code-Stand heute kann hinter dem PRD-Contract liegen (z.B. `/messages` noch nicht implementiert). Frontend soll deshalb **robust** sein: HTTP-Fehler als typed `error` behandeln statt die UI zu "killen".

### Backend-Readiness / Abhängigkeiten

- Aktueller Backend-Code enthält bereits `/v1/sessions` und `/v1/health`, aber (Stand heute) **noch keinen** `/v1/sessions/{session_id}/messages`-Endpunkt.
- Diese Story ist deshalb bewusst **contract-first**: Frontend kann (a) Session-Autocreate, (b) Request-Sequenz, (c) robustes Error-Mapping und (d) Tests via fetch-mocks liefern.
- Ein echter E2E-Happy-Path (typed `proposal|result|error` aus dem Backend) ist erst möglich, wenn Backend Story „Message-Endpunkt“ umgesetzt ist.

### Betroffene Dateien (erwartet)

- `frontend/src/api/realTransport.ts`
- `frontend/src/api/transport.ts`
- `frontend/src/api/mockTransport.ts`
- `frontend/src/state/chatReducer.ts`
- `frontend/src/types.ts` (falls nötig für minimalen Contract-Mapping)
- `frontend/src/App.tsx`
- `frontend/src/App.test.tsx` (nur falls Tests erweitert werden)

### References

- `_bmad-output/implementation-artifacts/frontend/1-1-frontend-scaffold-und-mock-chat-ui.md` (bestehende Patterns: Env Toggle, Transport-Layer, Reducer/States, Smoke-Tests)
- `_bmad-output/planning-artifacts/frontend/epics.md` (Epic 1 / Story 1.2)
- `_bmad-output/implementation-artifacts/frontend/sprint-status.yaml` (Story-Key + Status)
- `_bmad-output/planning-artifacts/frontend/prd_frontend.md` (API-Integration `/v1`, States, Fehler-UX)
- `_bmad-output/planning-artifacts/frontend/ux-spec.md` (Typed responses, State Machine, Copy)
- `_bmad-output/planning-artifacts/frontend/ux-design-specification.md` (Experience Principles, Fehler-UX)
- `_bmad-output/planning-artifacts/backend/prd.md` (Endpoint-Spec inkl. `/v1/sessions/{id}/messages`, ErrorResponse Schema)
- `_bmad-output/planning-artifacts/backend/epics.md` (Request-Body für `/messages`: `{ "text": "..." }`)
- `_bmad-output/planning-artifacts/frontend/frontend_implementationsplan_gysi_ml.md` (Drift-Risiko `/api/*` vs `/v1/*`)

## Dev Agent Record

### Agent Model Used

GPT-5.3-Codex

### Debug Log References

- Frontend Console Logs
- Vitest Output

### Completion Notes List

- Session-ID im Frontend-State eingefuehrt und bei erfolgreichen Requests stabil fortgeschrieben.
- Real-Transport implementiert: Session-Autocreate via `/v1/sessions`, danach Message-POST via `/v1/sessions/{session_id}/messages`.
- Fehlerklassifizierung umgesetzt: Netzwerk/CORS/FETCH-Throw bleibt Throw (UI kann `backend_unreachable` setzen), HTTP-Fehler werden als typed `error` gemappt.
- Transport-Schnittstellen vereinheitlicht auf Input/Output mit `sessionId` und `response` fuer Mock und Real.
- Neue Unit-Tests fuer Request-Sequenz und Fehlerpfade ergänzt; bestehende Story-1.1-Smoke-Tests bleiben gruen.

### File List

- frontend/src/state/chatReducer.ts
- frontend/src/api/transportTypes.ts
- frontend/src/api/transport.ts
- frontend/src/api/mockTransport.ts
- frontend/src/api/realTransport.ts (Backend-Response-Mapping nachgezogen: explanation→message, steps.type→step_type, error_code→details, status-Default für result)
- frontend/src/api/realTransport.test.ts (3 neue Tests für Backend-Response-Shapes: proposal, result, error mit error_code)
- frontend/src/App.tsx
- frontend/src/App.test.tsx
