# Story 2.2: Confirm-Flow (Bestätigen & Ausführen) mit UI-Idempotenz

Status: done

## Story

Als ein Nutzer,
möchte ich einen Proposal per „Bestätigen & Ausführen" kontrolliert auslösen, ohne versehentlich doppelt zu confirmen,
damit Runs zuverlässig und einmalig starten und ich den Run-Fortschritt anschließend verfolgen kann (Epic 3).

## Acceptance Criteria

1. **[FR5 — Confirm-Call ausgelöst]**

   **Given** ein Proposal ist pending (UI-Status `proposal_pending`)
   **When** der Nutzer auf „Bestätigen & Ausführen" klickt
   **Then** ruft die UI `POST /v1/sessions/{session_id}/confirm` mit `{ proposal_id: "..." }` auf
   **And** die erhaltene `run_id` wird im UI-State gespeichert

2. **[NFR3 — UI-Idempotenz: Button disabled während Request]**

   **Given** der Confirm-Request läuft (zwischen Click und Response)
   **When** die UI auf die Backend-Antwort wartet
   **Then** ist der „Bestätigen & Ausführen"-Button disabled und nicht erneut klickbar
   **And** ein zweiter Klick hat keine Auswirkung (kein zweiter Request)

3. **[State-Transition nach Confirm-Erfolg]**

   **Given** das Backend antwortet auf `/confirm` mit `run_id`
   **When** die Response verarbeitet wird
   **Then** wechselt die UI in den Zustand `run_polling`
   **And** `pendingProposalId` wird zurückgesetzt auf `null`
   **And** `runId` ist im State gesetzt (Vorbereitung für Epic 3)

4. **[Fehlerbehandlung: Confirm schlägt fehl]**

   **Given** das Backend antwortet auf `/confirm` mit HTTP 4xx oder liefert keine `run_id`
   **When** die Antwort verarbeitet wird
   **Then** wechselt die UI in den Zustand `validation_error`
   **And** `isConfirming` wird zurückgesetzt (Button wird wieder klickbar, falls State erneut `proposal_pending` wird)
   **And** kein Run-Polling wird gestartet

5. **[Mock-Modus: Confirm simuliert run_id]**

   **Given** die App läuft im Mock-Modus
   **When** der Nutzer „Bestätigen & Ausführen" klickt
   **Then** wird nach simulierter Latenz der State auf `run_polling` mit `runId: "mock-run-001"` gesetzt
   **And** der Button ist während der Latenz disabled

6. **[XSS-Sicherheit: kein HTML in Fehlermeldungen]**

   **Given** das Backend liefert im Fehlerfall HTML oder Sonderzeichen im `detail`-Feld
   **When** die Fehlermeldung angezeigt wird
   **Then** wird sie als Text gerendert (kein `dangerouslySetInnerHTML`)

## Tasks / Subtasks

- [x] **T1 — `transportTypes.ts`: `ConfirmInput` und `ConfirmResult` hinzufügen** (AC: 1, 4)
  - [ ] In `frontend/src/api/transportTypes.ts` ergänzen:
    ```typescript
    export interface ConfirmInput {
      proposalId: string
      sessionId: string
    }

    export interface ConfirmResult {
      runId: string | null
      error?: string
    }
    ```

- [x] **T2 — `realTransport.ts`: `sendRealConfirm()` implementieren** (AC: 1, 4)
  - [ ] In `frontend/src/api/realTransport.ts` hinzufügen (direkt nach `sendRealMessage`):
    ```typescript
    export async function sendRealConfirm(
      backendBaseUrl: string,
      sessionId: string,
      proposalId: string,
    ): Promise<ConfirmResult> {
      const baseUrl = backendBaseUrl.replace(/\/+$/, '')
      const response = await fetch(
        `${baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/confirm`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ proposal_id: proposalId }),
        },
      )
      const body = await parseJsonBody(response)

      if (!response.ok) {
        const errBody = isRecord(body) ? body : {}
        const detail =
          toNonEmptyString(errBody.detail) ??
          `Confirm fehlgeschlagen (HTTP ${response.status}).`
        return { runId: null, error: detail }
      }

      if (!isRecord(body)) {
        return { runId: null, error: 'Confirm-Response konnte nicht gelesen werden.' }
      }

      const runId = toNonEmptyString(body.run_id)
      if (!runId) {
        return { runId: null, error: 'Confirm-Response enthält keine run_id.' }
      }

      return { runId }
    }
    ```
  - [ ] Import für `ConfirmResult` aus `./transportTypes` ergänzen.
  - [ ] `parseJsonBody`, `isRecord`, `toNonEmptyString` sind bereits in `realTransport.ts` verfügbar (keine Doppelung).

- [x] **T3 — `mockTransport.ts`: `sendMockConfirm()` implementieren** (AC: 5)
  - [ ] In `frontend/src/api/mockTransport.ts` ergänzen:
    ```typescript
    import type { ConfirmResult } from './transportTypes'

    export async function sendMockConfirm(_proposalId: string): Promise<ConfirmResult> {
      await sleep(MOCK_LATENCY_MS)
      return { runId: 'mock-run-001' }
    }
    ```
  - [ ] `sleep` und `MOCK_LATENCY_MS` sind bereits im File — keine Duplikation.

- [x] **T4 — `transport.ts`: `confirmProposal()` hinzufügen** (AC: 1, 5)
  - [ ] In `frontend/src/api/transport.ts` ergänzen:
    ```typescript
    import { sendMockConfirm } from './mockTransport'
    import { sendRealConfirm } from './realTransport'
    import type { ConfirmInput, ConfirmResult } from './transportTypes'

    export async function confirmProposal(input: ConfirmInput): Promise<ConfirmResult> {
      const env = getFrontendEnv()
      return env.useMock
        ? await sendMockConfirm(input.proposalId)
        : await sendRealConfirm(env.backendBaseUrl, input.sessionId, input.proposalId)
    }
    ```

- [x] **T5 — `chatReducer.ts`: Neue Actions + State-Felder** (AC: 2, 3, 4)
  - [ ] `ChatState` um `runId` und `isConfirming` erweitern:
    ```typescript
    export interface ChatState {
      // ...bestehende Felder...
      runId: string | null       // ← NEU: run_id nach Confirm (für Epic 3)
      isConfirming: boolean      // ← NEU: Button-Idempotenz während Confirm-Request
    }
    ```
  - [ ] In `createInitialChatState()` ergänzen:
    ```typescript
    runId: null,
    isConfirming: false,
    ```
  - [ ] `ChatAction` um drei neue Actions erweitern:
    ```typescript
    | { type: 'CONFIRM_STARTED' }
    | { type: 'CONFIRM_SUCCEEDED'; runId: string }
    | { type: 'CONFIRM_FAILED'; errorMessage: string }
    ```
  - [ ] Im `chatReducer` Switch-Statement ergänzen:
    ```typescript
    case 'CONFIRM_STARTED':
      return { ...state, isConfirming: true }

    case 'CONFIRM_SUCCEEDED':
      return {
        ...state,
        isConfirming: false,
        runId: action.runId,
        pendingProposalId: null,
        ui: { type: 'run_polling' },
      }

    case 'CONFIRM_FAILED':
      return {
        ...state,
        isConfirming: false,
        lastError: action.errorMessage,
        ui: { type: 'validation_error' },
      }
    ```

- [x] **T6 — `ProposalCard.tsx`: `disabled` Prop + ARIA hinzufügen** (AC: 2)
  - [ ] Props-Typ erweitern:
    ```typescript
    type ProposalCardProps = {
      proposal: ProposalResponse
      onConfirm: (proposalId: string) => void
      disabled?: boolean         // ← NEU
    }
    ```
  - [ ] Destrukturierung und Button anpassen:
    ```tsx
    export function ProposalCard({ proposal, onConfirm, disabled }: ProposalCardProps) {
      // ...
      <button
        type="button"
        className="proposalConfirmButton"
        onClick={() => onConfirm(proposal.proposal_id ?? '')}
        disabled={disabled}
        aria-disabled={disabled}
      >
        Bestätigen &amp; Ausführen
      </button>
    ```
  - [ ] **Keine Logik im Handler trotz `disabled`** — der Browser unterdrückt `onClick` bei `disabled`; kein Guard im Handler nötig.

- [x] **T7 — `MessageList.tsx`: `confirmDisabled` Prop weiterleiten** (AC: 2)
  - [ ] Props-Typ erweitern:
    ```typescript
    type MessageListProps = {
      messages: ChatMessage[]
      onConfirm: (proposalId: string) => void
      confirmDisabled: boolean   // ← NEU
    }
    ```
  - [ ] `ProposalCard`-Render anpassen:
    ```tsx
    export function MessageList({ messages, onConfirm, confirmDisabled }: MessageListProps) {
      // ...
      <ProposalCard proposal={message.response} onConfirm={onConfirm} disabled={confirmDisabled} />
    ```

- [x] **T8 — `App.tsx`: `handleConfirm` implementieren** (AC: 1, 2, 3, 4)
  - [ ] Import ergänzen:
    ```typescript
    import { confirmProposal } from './api/transport'
    ```
  - [ ] `handleConfirm` ersetzen (aktuell leerer Stub):
    ```typescript
    const handleConfirm = useCallback(
      async (proposalId: string) => {
        if (state.isConfirming || state.ui.type !== 'proposal_pending') return

        dispatch({ type: 'CONFIRM_STARTED' })

        try {
          const result = await confirmProposal({
            proposalId,
            sessionId: state.sessionId ?? '',
          })

          if (result.error || !result.runId) {
            dispatch({
              type: 'CONFIRM_FAILED',
              errorMessage: result.error ?? 'Confirm fehlgeschlagen.',
            })
            return
          }

          dispatch({ type: 'CONFIRM_SUCCEEDED', runId: result.runId })
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unbekannter Fehler'
          dispatch({ type: 'CONFIRM_FAILED', errorMessage })
        }
      },
      [state.isConfirming, state.ui.type, state.sessionId],
    )
    ```
  - [ ] `MessageList`-Verwendung anpassen:
    ```tsx
    <MessageList
      messages={state.messages}
      onConfirm={handleConfirm}
      confirmDisabled={state.isConfirming || state.ui.type !== 'proposal_pending'}
    />
    ```
  - [ ] **Beachte:** `handleConfirm` ist jetzt `async` — der `useCallback`-Typ passt, da React keine Rückgabe von Callbacks erwartet.

- [x] **T9 — Tests: `chatReducer` Confirm-Actions** (AC: 2, 3, 4)
  - [ ] Neue Testdatei: `frontend/src/state/chatReducer.confirm.test.ts`
  - [ ] Tests für `CONFIRM_STARTED`:
    - `isConfirming` wird `true`
    - `ui.type` bleibt `proposal_pending` (kein State-Wechsel vor Response)

    **Hinweis:** `CONFIRM_STARTED` wechselt nicht den `ui.type`. Der Button-Disable läuft über `isConfirming`.

  - [ ] Tests für `CONFIRM_SUCCEEDED`:
    - `ui.type` wechselt auf `run_polling`
    - `runId` ist gesetzt
    - `isConfirming` ist `false`
    - `pendingProposalId` ist `null`
  - [ ] Tests für `CONFIRM_FAILED`:
    - `ui.type` wechselt auf `validation_error`
    - `isConfirming` ist `false`
    - `lastError` enthält die Fehlermeldung

- [x] **T10 — Tests: `realTransport` Confirm** (AC: 1, 4)
  - [ ] In `frontend/src/api/realTransport.test.ts` neue describe-Gruppe: `sendRealConfirm`
  - [ ] Test: Erfolgsfall → `runId` wird aus `run_id` extrahiert
  - [ ] Test: HTTP-4xx → `runId: null` + `error` enthält `detail`-Text vom Backend
  - [ ] Test: Response ohne `run_id` → `runId: null` + `error` gesetzt

- [x] **T11 — Tests: `ProposalCard` disabled-Verhalten** (AC: 2)
  - [ ] In `frontend/src/components/ProposalCard.test.tsx` ergänzen:
    - Test: Button ist klickbar wenn `disabled` falsy
    - Test: Button ist nicht klickbar wenn `disabled={true}` (rendered mit `disabled`-Attribut)
    - Test: `onConfirm` wird bei `disabled={true}` nicht aufgerufen (via userEvent)

## Dev Notes

### Backend-Contract (bindend)

- **Endpoint:** `POST /v1/sessions/{session_id}/confirm`
- **Request-Body:** `{ "proposal_id": "string" }` — Schema: `ConfirmRequest` in `backend/src/gysi_ml/api/schemas.py`
- **Erfolgs-Response:** `{ "type": "result", "run_id": "...", "explanation": "..." }` — Schema: `MessageResponse`
  - `run_id` ist **immer vorhanden** (Sprint-Kontrakt 2026-03-20)
  - `explanation` entspricht dem Frontend-Feld `message`
  - `status` ist in der Confirm-Response **nicht gesetzt** → Frontend darf keinen Status aus dieser Response lesen
- **Fehler-Responses:**
  - HTTP 404 → `{ "error": "proposal_not_found" | "session_not_found", "detail": "...", "code": "..." }`
  - HTTP 409 → `{ "error": "no_pending_proposal" | "session_closed", "detail": "...", "code": "..." }`
- **Backend-Verhalten:** `confirm_proposal()` führt die Pipeline synchron aus und gibt danach die `run_id` zurück. Das Frontend geht davon aus, dass die Response erst nach Abschluss oder Registrierung des Runs kommt.

### Frontend State Machine — Story-2.2-relevante Übergänge

```
idle → (Proposal empfangen) → proposal_pending
proposal_pending → (CONFIRM_STARTED) → proposal_pending [isConfirming=true]
proposal_pending [isConfirming=true] → (CONFIRM_SUCCEEDED) → run_polling [runId gesetzt]
proposal_pending [isConfirming=true] → (CONFIRM_FAILED) → validation_error [isConfirming=false]
```

`run_polling` ist der Einstiegszustand für Epic 3 (Story 3.1). Epic 3 vervollständigt den Polling-Loop.

### Warum `isConfirming` als separates Flag (nicht neuer `ui.type`)?

Der `ui.type` soll den **sichtbaren App-Zustand** abbilden (State Machine). Während der Confirm-Request läuft, ist der Nutzer noch im `proposal_pending`-Screen — nur der Button ist disabled. Ein eigener `confirming_proposal` State wäre semantisch korrekt, aber würde zusätzliche Komplexität erzeugen (z.B. Abfragen in Composer, HealthPolling, etc.). `isConfirming: boolean` ist das minimale Mittel für NFR3.

### Wichtige Regression-Checks

- `SEND_REQUEST_SUCCEEDED` mit `type: 'proposal'` setzt weiterhin `pendingProposalId` — kein Eingriff nötig
- `chatReducer`-Reducer für `SEND_REQUEST_SUCCEEDED` muss `runId` **nicht** anfassen — `runId` kommt ausschließlich über `CONFIRM_SUCCEEDED`
- `ProposalCard.test.tsx` hat bestehende Tests für `onConfirm`-Aufruf ohne `disabled` — diese Tests bleiben grün (Default: `disabled` ist `undefined` → falsy)
- `MessageList`-Prop `confirmDisabled` ist ein neues Pflichtfeld — alle Tests in der Codebasis, die `MessageList` verwenden, müssen `confirmDisabled` ergänzen (z.B. `App.test.tsx` falls vorhanden)

### Project Structure Notes

| Datei | Aktion |
| --- | --- |
| `frontend/src/api/transportTypes.ts` | Ergänzen: `ConfirmInput`, `ConfirmResult` |
| `frontend/src/api/realTransport.ts` | Ergänzen: `sendRealConfirm()` am Ende des Files |
| `frontend/src/api/mockTransport.ts` | Ergänzen: `sendMockConfirm()` + Import `ConfirmResult` |
| `frontend/src/api/transport.ts` | Ergänzen: `confirmProposal()` + Imports |
| `frontend/src/state/chatReducer.ts` | Erweitern: State-Felder, Actions, Reducer-Cases |
| `frontend/src/components/ProposalCard.tsx` | Erweitern: `disabled` Prop + ARIA |
| `frontend/src/components/MessageList.tsx` | Erweitern: `confirmDisabled` Prop |
| `frontend/src/App.tsx` | Implementieren: `handleConfirm` + `confirmDisabled` an `MessageList` |
| `frontend/src/state/chatReducer.confirm.test.ts` | NEU: Tests für Confirm-Actions |

### Mock-Fixture für Confirm

Kein separates JSON-Fixture nötig — `sendMockConfirm()` gibt direkt `{ runId: 'mock-run-001' }` zurück. Das ist konsistent mit dem Mock-Run-ID-Pattern im `result.json`-Fixture.

### References

- Backend-Endpoint: [backend/src/gysi_ml/api/routes/confirm.py](../../../../../backend/src/gysi_ml/api/routes/confirm.py)
- Backend-Service: [backend/src/gysi_ml/services/proposal_service.py](../../../../../backend/src/gysi_ml/services/proposal_service.py) — `confirm_proposal()` gibt `{ "type": "result", "run_id": "...", "explanation": "..." }` zurück
- Backend-Schema: [backend/src/gysi_ml/api/schemas.py](../../../../../backend/src/gysi_ml/api/schemas.py) — `ConfirmRequest`, `MessageResponse`
- Frontend-Types: [frontend/src/types.ts](../../../../../frontend/src/types.ts)
- Transport-Types: [frontend/src/api/transportTypes.ts](../../../../../frontend/src/api/transportTypes.ts)
- Real-Transport: [frontend/src/api/realTransport.ts](../../../../../frontend/src/api/realTransport.ts)
- Mock-Transport: [frontend/src/api/mockTransport.ts](../../../../../frontend/src/api/mockTransport.ts)
- Transport-Dispatcher: [frontend/src/api/transport.ts](../../../../../frontend/src/api/transport.ts)
- Reducer: [frontend/src/state/chatReducer.ts](../../../../../frontend/src/state/chatReducer.ts)
- ProposalCard: [frontend/src/components/ProposalCard.tsx](../../../../../frontend/src/components/ProposalCard.tsx) — `onConfirm`-Stub aktiv, Button verbindet prop
- MessageList: [frontend/src/components/MessageList.tsx](../../../../../frontend/src/components/MessageList.tsx) — leitet `onConfirm` weiter
- App: [frontend/src/App.tsx](../../../../../frontend/src/App.tsx) — `handleConfirm` ist aktuell leerer Stub (Zeile mit `// Story 2.2: hier kommt der Confirm-Call`)
- Vorhergehende Story: [2-1-proposal-card-im-chat-rendern.md](./2-1-proposal-card-im-chat-rendern.md) — liefert `pendingProposalId` im State + ProposalCard-Komponente
- Sprint-Status mit API-Kontrakt: [sprint-status.yaml](./sprint-status.yaml)
- Epics: [planning-artifacts/frontend/epics.md](../../planning-artifacts/frontend/epics.md) — FR5, NFR3, UX-DR5

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

Keine relevanten Debug-Einträge.

### Completion Notes List

- `handleConfirm` ist jetzt `async` in App.tsx — React-Callback-Rückgabe ignoriert, kein Problem
- `realTransport.ts`: Hilfsfunktionen `parseJsonBody`, `isRecord`, `toNonEmptyString` sind file-lokal und in `sendRealConfirm` direkt verwendbar
- `confirmDisabled` als neues Pflichtfeld in `MessageList` — alle bestehenden Tests für `MessageList` werden indirekt über `App.test.tsx` abgedeckt; `App.tsx` übergibt den Wert korrekt
- `SEND_REQUEST_SUCCEEDED`-Handler in chatReducer unberührt — `runId`-Feld wird ausschließlich über `CONFIRM_SUCCEEDED` gesetzt (kein Regression-Risiko)
- **Code-Review-Fixes (2026-03-20):** `sessionId`-Null-Guard vor `CONFIRM_STARTED` hinzugefügt [L1]; Confirm-Flow-Integration-Smoke-Test in `App.test.tsx` ergänzt [L2]; `App.test.tsx` in File List ergänzt [M1]
- 65/65 Tests grün nach vollständiger Implementierung inkl. Review-Fixes

### File List

- `frontend/src/api/transportTypes.ts` — `ConfirmInput`, `ConfirmResult` ergänzt
- `frontend/src/api/realTransport.ts` — `sendRealConfirm()` + Import `ConfirmResult`
- `frontend/src/api/mockTransport.ts` — `sendMockConfirm()` + Import `ConfirmResult`
- `frontend/src/api/transport.ts` — `confirmProposal()` + Imports
- `frontend/src/state/chatReducer.ts` — `runId`, `isConfirming` im State; 3 neue Actions; 3 neue Reducer-Cases
- `frontend/src/components/ProposalCard.tsx` — `disabled` Prop + `aria-disabled`
- `frontend/src/components/MessageList.tsx` — `confirmDisabled` Prop + Weitergabe
- `frontend/src/App.tsx` — `handleConfirm` implementiert; `sessionId`-Null-Guard; `confirmDisabled` an `MessageList`
- `frontend/src/App.test.tsx` — `confirmDisabled` Prop in MessageList-Usages; Confirm-Flow-Smoke-Test
- `frontend/src/state/chatReducer.confirm.test.ts` — NEU: 9 Tests für Confirm-Actions
- `frontend/src/api/realTransport.test.ts` — 3 Tests für `sendRealConfirm` ergänzt
- `frontend/src/components/ProposalCard.test.tsx` — 3 Tests für `disabled`-Verhalten ergänzt
