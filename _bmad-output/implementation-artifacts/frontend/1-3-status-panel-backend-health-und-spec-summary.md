# Story 1.3: Status-Panel — Backend-Health und Spec-Summary

Status: done

## Story

Als ein Nutzer,
möchte ich im Status-Panel den Backend-Erreichbarkeitsstatus aktiv überwacht und eine kompakte Spec-Zusammenfassung aus dem Backend sehen,
damit ich jederzeit weiß, ob das System erreichbar ist und welche Spec-Version aktiv ist – ohne dafür eine Nachricht senden zu müssen.

## Acceptance Criteria

1. **[Health-Polling: Backend nicht erreichbar]**

   **Given** die App läuft im Real-Backend-Modus (`VITE_GYSI_USE_MOCK` nicht gesetzt oder `false`)
   **When** `GET /v1/health` fehlschlägt (Network-Error oder HTTP non-2xx)
   **Then** wechselt die UI in den Zustand `backend_unreachable`
   **And** das Status-Panel zeigt die handlungsfähige Copy: „Backend nicht erreichbar. Bitte Backend starten oder URL prüfen."

2. **[Health-Polling: Recovery]**

   **Given** die UI befindet sich im Zustand `backend_unreachable`
   **When** `GET /v1/health` wieder erfolgreich antwortet
   **Then** wechselt die UI zurück in den Zustand `idle`
   **And** das Status-Panel zeigt keinen Fehler mehr

3. **[Health-Polling nur im Real-Modus]**

   **Given** die App läuft im Mock-Modus (`VITE_GYSI_USE_MOCK=1`)
   **When** die App startet
   **Then** wird kein Health-Check-Poll gestartet
   **And** das Status-Panel zeigt „Mock aktiv" ohne Backend-Erreichbarkeitsindikator

4. **[Spec-Summary via Response (primäre Quelle)]**

   **Given** eine Message-Response enthält `spec_summary`
   **When** die Response verarbeitet wird
   **Then** wird die Spec-Summary im Status-Panel aktualisiert (bereits durch `chatReducer` in Story 1.2 implementiert; diese Story stellt sicher, dass das Panel sie korrekt rendert)

5. **[Spec-Summary via direkten Fetch (Fallback)]**

   **Given** eine `session_id` ist bekannt (im UI-State vorhanden)
   **And** `specSummary` ist noch `null`
   **When** die `session_id` erstmals gesetzt wird
   **Then** wird einmalig `GET /v1/sessions/{session_id}/spec` aufgerufen
   **And** bei Erfolg wird die Spec-Summary im Status-Panel angezeigt

6. **[StatusPanel: backend_unreachable klar kommuniziert]**

   **Given** der UI-Zustand ist `backend_unreachable`
   **When** das Status-Panel gerendert wird
   **Then** ist die Fehlerbotschaft als Text sichtbar (nicht nur als roher State-Label)
   **And** die Copy ist handlungsfähig (z.B. „Backend nicht erreichbar. Bitte Backend starten oder URL prüfen.")
   **And** der Inhalt enthält keine rohe HTML-Interpretation (XSS-Baseline)

## Tasks / Subtasks

- [x] **T1 — Neue Reducer-Actions für Health und Spec** (AC: 1, 2, 5)
  - [x] `HEALTH_CHECK_FAILED` in `ChatAction` Union hinzufügen
  - [x] `HEALTH_CHECK_RECOVERED` in `ChatAction` Union hinzufügen
  - [x] `SPEC_SUMMARY_LOADED` in `ChatAction` Union hinzufügen (payload: `SpecSummary`)
  - [x] Reducer-Handlers implementieren:
    - [x] `HEALTH_CHECK_FAILED`: setzt `ui` auf `backend_unreachable` **nur wenn** aktueller Zustand nicht bereits `backend_unreachable` und nicht `sending_message` (d.h. kein Override aktiver Requests)
    - [x] `HEALTH_CHECK_RECOVERED`: setzt `ui` auf `idle` **nur wenn** aktueller Zustand `backend_unreachable` ist
    - [x] `SPEC_SUMMARY_LOADED`: überschreibt `specSummary` im State

- [x] **T2 — Health-Check API-Funktion** (AC: 1, 2)
  - [x] `src/api/healthApi.ts` anlegen
  - [x] `fetchHealth(baseUrl: string): Promise<boolean>` implementieren: `GET {baseUrl}/v1/health`
  - [x] Gibt `true` zurück wenn HTTP 2xx; wirft oder gibt `false` für Network-Error oder non-2xx
  - [x] Keine Secrets im Frontend; kein Logging sensibler Daten

- [x] **T3 — Spec-Summary API-Funktion** (AC: 5)
  - [x] `fetchSpecSummary(baseUrl: string, sessionId: string): Promise<SpecSummary | null>` implementiert in `healthApi.ts`
  - [x] `GET {baseUrl}/v1/sessions/{encodeURIComponent(sessionId)}/spec`
  - [x] Bei HTTP 2xx: JSON parsen und als `SpecSummary` zurückgeben
  - [x] Bei Fehler: `null` zurückgeben (kein Throw, kein UI-Block)

- [x] **T4 — `useHealthPolling`-Hook** (AC: 1, 2, 3)
  - [x] `src/hooks/useHealthPolling.ts` anlegen
  - [x] Pollt `GET /v1/health` periodisch (alle 10 Sekunden) via `setInterval`
  - [x] **Nur aktiv wenn `transport.useMock === false`** (AC: 3)
  - [x] Bei Failure: `dispatch({ type: 'HEALTH_CHECK_FAILED' })`
  - [x] Bei Recovery (nach vorherigem Fail): `dispatch({ type: 'HEALTH_CHECK_RECOVERED' })`
  - [x] Cleanup: `clearInterval` bei Unmount (kein Memory Leak)
  - [x] Kein Polling-Update wenn Tab/Window nicht aktiv ist (`document.visibilityState`)

- [x] **T5 — `useSpecSummaryFetch`-Effect** (AC: 5)
  - [x] In `App.tsx` als `useEffect` wenn `sessionId !== null` und `specSummary === null` und `!useMock`
  - [x] Bei Erfolg: `dispatch({ type: 'SPEC_SUMMARY_LOADED', specSummary: result })`
  - [x] Bei Fehler: still ignorieren (kein UI-Block)

- [x] **T6 — StatusPanel: backend_unreachable UX verbessern** (AC: 6)
  - [x] In `src/components/StatusPanel.tsx`: explizites Rendering für `backend_unreachable`
  - [x] Copy: „Backend nicht erreichbar. Bitte Backend starten oder URL prüfen."
  - [x] Copy als Text rendern (keine `dangerouslySetInnerHTML`)

- [x] **T7 — `useHealthPolling`-Hook in `App.tsx` einbinden** (AC: 1, 2, 3)
  - [x] `useHealthPolling(dispatch, state.transport)` in `App.tsx` aufgerufen

- [x] **T8 — Tests** (AC: 1, 2, 3, 5, 6)
  - [x] Unit-Tests für `useHealthPolling` (`src/hooks/useHealthPolling.test.ts`)
  - [x] Unit-Tests für Reducer (`src/state/chatReducer.health.test.ts`)
  - [x] Smoke-Test für StatusPanel (`src/components/StatusPanel.test.tsx`)
  - [x] Alle bestehenden 18 Tests aus Story 1.1+1.2 weiterhin grün
  - [ ] Bestehende Tests aus Story 1.1 und 1.2 dürfen nicht brechen

## Dev Notes

### Guardrails (MVP bindend)

- Single Page: keine zusätzlichen Seiten/Routes/Modals.
- Health-Polling **nicht** im Mock-Modus — `transport.useMock === true` → kein Interval starten.
- Backend-Base-URL kommt ausschließlich aus Env (`VITE_GYSI_BACKEND_BASE_URL`) — keine UI-Einstellung.
- Spec-Summary nur als Summary sichtbar (kein Roh-JSON-Editor).
- Alle Inhalte als Text rendern (XSS-Baseline, kein `dangerouslySetInnerHTML`).
- Keine Secrets im Frontend.

### Bestehende Code-Struktur (was bereits existiert)

- **`src/state/chatReducer.ts`**: Enthält `ChatState`, `ChatAction` Union, `chatReducer`. Hier müssen die neuen Actions ergänzt werden.
- **`src/components/StatusPanel.tsx`**: Status-Panel-Komponente existiert bereits mit allen 4 Sektionen (Backend, SpecSummary, LastRun, Artefakte). In T6 wird nur der `backend_unreachable`-Block verbessert — kein Umbau der Gesamt-Komponente.
- **`src/App.tsx`**: Enthält den `useReducer`-Aufruf und den `handleSend`-Handler. `useHealthPolling` und `useSpecSummaryFetch`-Effect werden hier eingebunden.
- **`src/api/realTransport.ts`**: Enthält Real-Backend-Requests. Neue Health/Spec-API-Funktionen werden in separaten Files angelegt (`src/api/healthApi.ts`), um realTransport fokussiert zu halten.
- **`src/env.ts`**: `getFrontendEnv()` liefert `{ backendBaseUrl, useMock }` — bereits genutzt in `chatReducer` als `TransportInfo`.

### Empfohlene neue Dateistruktur

```text
frontend/src/
  api/
    healthApi.ts        ← NEU: fetchHealth(), fetchSpecSummary()
  hooks/
    useHealthPolling.ts ← NEU: Background Health-Check Hook
```

### API-Contract (Health + Spec Endpoints)

Health-Endpoint:

- `GET /v1/health`
- Erfolg: HTTP 2xx (Body-Inhalt irrelevant für MVP — nur Status-Code prüfen)
- Fehler: Network-Error (fetch throws) oder HTTP non-2xx

Spec-Endpoint:

- `GET /v1/sessions/{session_id}/spec`
- Erfolg: HTTP 2xx + JSON Body als `SpecSummary`:

  ```json
  {
    "spec_version_id": "v3",
    "steps": [
      { "step_type": "preprocessing", "enabled": true },
      { "step_type": "model_training", "enabled": false }
    ]
  }
  ```

- Fehler: HTTP non-2xx oder Network-Error → `null` zurückgeben, kein UI-Block

### Reducer: HEALTH_CHECK_FAILED Override-Logik

Der `HEALTH_CHECK_FAILED`-Handler muss laufende User-Requests nicht unterbrechen:

```typescript
case 'HEALTH_CHECK_FAILED':
  // Kein Override aktiver Requests (送 sending_message)
  if (state.ui.type === 'sending_message') return state
  return { ...state, ui: { type: 'backend_unreachable' } }
```

### Testing-Hinweise

- `useHealthPolling` mit `vi.useFakeTimers()` testen (Vitest): `vi.advanceTimersByTime(10_000)` um ein Interval-Tick zu simulieren.
- Fetch in Tests global mocken: `vi.stubGlobal('fetch', vi.fn())`.
- Bestehende Tests in `App.test.tsx` und `realTransport.test.ts` laufen im Mock-Modus — kein Health-Polling aktiv, kein Bruch erwartet.

### References

- Epics + FRs: [epics.md — Story 1.3, FR10, FR12](_bmad-output/planning-artifacts/frontend/epics.md#story-13-status-panel-backend-health-und-spec-summary)
- UX-Spec Status-Panel: [ux-spec.md — Section 6.3](_bmad-output/planning-artifacts/frontend/ux-spec.md)
- UX-Spec Microcopy: [ux-spec.md — Section 8](_bmad-output/planning-artifacts/frontend/ux-spec.md)
- Frontend PRD FR12: [prd_frontend.md](_bmad-output/planning-artifacts/frontend/prd_frontend.md)
- Bestehender StatusPanel: [frontend/src/components/StatusPanel.tsx](frontend/src/components/StatusPanel.tsx)
- Bestehender Reducer: [frontend/src/state/chatReducer.ts](frontend/src/state/chatReducer.ts)
- Story 1.1 (Scaffold + Mock): [1-1-frontend-scaffold-und-mock-chat-ui.md](_bmad-output/implementation-artifacts/frontend/1-1-frontend-scaffold-und-mock-chat-ui.md)
- Story 1.2 (Session + Messages): [1-2-backend-integration-session-und-messages.md](_bmad-output/implementation-artifacts/frontend/1-2-backend-integration-session-und-messages.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot Developer Agent)

### Debug Log References

- Vitest Output: 24/24 Tests grün

### Completion Notes List

- `GET /v1/sessions/{session_id}/spec` fehlt im Backend (siehe unten). `fetchSpecSummary` gibt bei 404 gracefully `null` zurück — kein UI-Block.
- `HEALTH_CHECK_FAILED` überschreibt den `sending_message`-Zustand bewusst nicht (kein Race-Condition-Override).
- Health-Polling wird bei `document.visibilityState === 'hidden'` übersprungen (kein unnötiger Netzwerk-Traffic im Hintergrund-Tab).

### File List

- `frontend/src/state/chatReducer.ts` (T1: neue Actions + Reducer-Handler)
- `frontend/src/api/healthApi.ts` (T2 + T3: fetchHealth + fetchSpecSummary)
- `frontend/src/hooks/useHealthPolling.ts` (T4: Hook)
- `frontend/src/App.tsx` (T5 + T7: useSpecSummaryFetch-Effect + useHealthPolling eingebunden)
- `frontend/src/components/StatusPanel.tsx` (T6: backend_unreachable UX)
- `frontend/src/state/chatReducer.health.test.ts` (T8: Reducer-Tests)
- `frontend/src/hooks/useHealthPolling.test.ts` (T8: Hook-Tests)
- `frontend/src/components/StatusPanel.test.tsx` (T8: Smoke-Test)
