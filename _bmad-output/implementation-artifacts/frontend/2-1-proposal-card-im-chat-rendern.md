# Story 2.1: Proposal-Card im Chat rendern

Status: done

## Story

Als ein Nutzer,
möchte ich eine Backend-Response vom Typ `"proposal"` als strukturierte Proposal-Card im Chat sehen,
damit ich den Vorschlag mit Steps + Parameter-Summary vor der Ausführung nachvollziehen kann
und eine klare Bestätigungsaktion ("Bestätigen & Ausführen") erkenne.

## Acceptance Criteria

1. **[FR4 — Proposal-Card mit Pflichtinhalten]**

   **Given** das Backend (oder der Mock) antwortet mit `type: "proposal"`
   **When** die Message im Chat gerendert wird
   **Then** erscheint eine Proposal-Card mit:
   - Label „Vorschlag (noch nicht ausgeführt)"
   - Step-Liste (step_type + parameters_summary falls vorhanden)
   - CTA-Button „Bestätigen & Ausführen"
   **And** kein plain-Text wird für diese Message gerendert

2. **[FR4 — proposal_id aus Backend extrahieren]**

   **Given** das Backend sendet `proposal_id` im Proposal-Payload
   **When** `realTransport.ts` die Response verarbeitet
   **Then** ist `proposal_id` in `ProposalResponse` als optionales Feld vorhanden
   **And** der Reducer speichert sie als `pendingProposalId` im State

3. **[Mock-Modus: Proposal-Card korrekt dargestellt]**

   **Given** die App läuft im Mock-Modus
   **When** der Nutzer "vorschlag" oder "proposal" sendet
   **Then** rendert der Chat eine Proposal-Card (nicht plain Text)
   **And** Steps aus dem Fixture sind als Liste sichtbar

4. **[UX: Nicht-Proposal-Messages unverändert]**

   **Given** eine Assistant-Message vom Typ `"result"`, `"error"` oder `"spec_updated"`
   **When** die Message gerendert wird
   **Then** wird sie weiterhin als plain-Text-Bubble gerendert (keine Regression)

5. **[UX-DR5 Vorarbeit: Button-Zustand erkennbar]**

   **Given** die UI befindet sich im State `proposal_pending`
   **When** die Proposal-Card sichtbar ist
   **Then** ist der CTA-Button „Bestätigen & Ausführen" aktiv (nicht disabled)
   **And** der Button ruft die `onConfirm`-Callback-Prop mit der `proposal_id` auf
   *(Die eigentliche Confirm-Logik wird in Story 2.2 implementiert — `onConfirm` ist in Story 2.1 ein Stub)*

6. **[XSS-Sicherheit]**

   **Given** ein Proposal enthält Sonderzeichen oder HTML in `message`, `step_type` oder `parameters_summary`
   **When** die Proposal-Card gerendert wird
   **Then** wird Content als Text gerendert (kein `dangerouslySetInnerHTML`)

## Tasks / Subtasks

- [x] **T1 — `types.ts`: `ProposalResponse` um `proposal_id` erweitern** (AC: 2)
  - [x] In `frontend/src/types.ts`, `ProposalResponse` erweitern:
    ```typescript
    export interface ProposalResponse {
      type: 'proposal'
      message: string
      steps: ProposalStep[]
      parameters_summary?: string
      spec_summary?: SpecSummary
      proposal_id?: string   // ← NEU: vom Backend für Confirm-Flow
    }
    ```

- [x] **T2 — `types.ts`: `ChatMessage` um `response` erweitern** (AC: 1, 4)
  - [x] In `frontend/src/types.ts`, `ChatMessage` erweitern:
    ```typescript
    export interface ChatMessage {
      id: string
      role: ChatRole
      content: string
      ts: string
      response?: AssistantResponse   // ← NEU: für typisiertes Rendering (Proposal-Card etc.)
    }
    ```
  - [x] **Begründung:** Damit `MessageList` ProposalCards rendern kann, muss die getypte Response neben dem `content`-String am Message-Objekt hängen. Der `content`-String bleibt für Accessibility/Fallback erhalten.

- [x] **T3 — `realTransport.ts`: `proposal_id` extrahieren** (AC: 2)
  - [x] In `frontend/src/api/realTransport.ts`, in `toAssistantResponse()`, im `proposal`-Branch nach dem `steps`-Mapping ergänzen:
    ```typescript
    const proposalId = toNonEmptyString(payload.proposal_id) ?? undefined
    return {
      type: 'proposal',
      message,
      steps,
      ...(proposalId ? { proposal_id: proposalId } : {}),
    }
    ```
  - [x] Der bestehende `steps`-Mapping-Code (Backend `type` → Frontend `step_type`) bleibt unverändert.

- [x] **T4 — `fixtures/proposal.json`: `proposal_id` hinzufügen** (AC: 3)
  - [x] In `frontend/src/fixtures/proposal.json` auf Top-Level ergänzen:
    ```json
    {
      "type": "proposal",
      "proposal_id": "mock-proposal-001",
      "message": "Vorschlag (Mock): Ich würde die Pipeline wie folgt anpassen.",
      "steps": [ ... ]
    }
    ```
  - [x] Rest des Fixtures bleibt identisch.

- [x] **T5 — `chatReducer.ts`: `pendingProposalId` in State + Reducer** (AC: 2, 5)
  - [x] In `frontend/src/state/chatReducer.ts`, `ChatState` erweitern:
    ```typescript
    export interface ChatState {
      // ...bestehende Felder...
      pendingProposalId: string | null   // ← NEU
    }
    ```
  - [x] In `createInitialChatState()` ergänzen:
    ```typescript
    pendingProposalId: null,
    ```
  - [x] In `SEND_REQUEST_SUCCEEDED`-Handler ergänzen:
    ```typescript
    const pendingProposalId =
      response.type === 'proposal'
        ? (response.proposal_id ?? null)
        : null
    ```
    und in den Return-Spread:
    ```typescript
    pendingProposalId,
    ```
  - [x] **Hinweis:** Story 2.2 liest `state.pendingProposalId` für den Confirm-Call — die Basis wird hier gelegt.

- [x] **T6 — `App.tsx`: `response` an ChatMessage anhängen** (AC: 1, 4)
  - [x] In der `handleSend`-Funktion, beim Erstellen von `assistantMessage`, das `response`-Objekt anhängen:
    ```typescript
    const assistantMessage: ChatMessage = {
      ...createMessage('assistant', formatAssistantResponse(response)),
      response,   // ← NEU: typisierte Response für ProposalCard-Rendering
    }
    ```
  - [x] `createMessage()` und `formatAssistantResponse()` bleiben unverändert.
  - [x] Stub-Handler für Story 2.2 vorbereiten — als leere Funktion die Typsignatur erfüllt:
    ```typescript
    const handleConfirm = useCallback((_proposalId: string) => {
      // Story 2.2: hier kommt der Confirm-Call
    }, [])
    ```
  - [x] `handleConfirm` als `onConfirm`-Prop an `MessageList` weitergeben (Signatur muss matchen).

- [x] **T7 — `components/ProposalCard.tsx` erstellen** (AC: 1, 5, 6)
  - [x] Neue Datei `frontend/src/components/ProposalCard.tsx`:
    ```typescript
    import type { ProposalResponse } from '../types'

    type ProposalCardProps = {
      proposal: ProposalResponse
      onConfirm: (proposalId: string) => void
    }

    export function ProposalCard({ proposal, onConfirm }: ProposalCardProps) {
      return (
        <div className="proposalCard">
          <div className="proposalLabel">Vorschlag (noch nicht ausgeführt)</div>
          {proposal.message && (
            <div className="proposalMessage">{proposal.message}</div>
          )}
          <ul className="proposalSteps">
            {proposal.steps.map((step, idx) => (
              <li key={`${step.step_type}-${idx}`} className="proposalStep">
                <span className="proposalStepType">{step.step_type}</span>
                {step.parameters_summary && (
                  <span className="proposalStepParams">
                    {' '}— {step.parameters_summary}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="proposalConfirmButton"
            onClick={() => onConfirm(proposal.proposal_id ?? '')}
          >
            Bestätigen &amp; Ausführen
          </button>
        </div>
      )
    }
    ```
  - [x] **XSS-Guard:** Alle Inhalte (message, step_type, parameters_summary) als React-Kinder rendern (nie `dangerouslySetInnerHTML`).
  - [x] `key`-Prop nutzt `step_type + index` (Backend liefert keinen garantiert-eindeutigen Step-Key).

- [x] **T8 — `App.css`: ProposalCard-Styles ergänzen** (AC: 1)
  - [x] Am Ende von `frontend/src/App.css` ergänzen:
    ```css
    .proposalCard {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--bg);
    }

    .proposalLabel {
      font-family: var(--mono);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      opacity: 0.7;
    }

    .proposalMessage {
      white-space: pre-wrap;
      word-break: break-word;
    }

    .proposalSteps {
      margin: 0;
      padding: 0 0 0 16px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .proposalStep {
      font-size: 14px;
    }

    .proposalStepType {
      font-family: var(--mono);
      font-weight: 500;
    }

    .proposalStepParams {
      opacity: 0.8;
    }

    .proposalConfirmButton {
      align-self: flex-start;
      padding: 8px 14px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--accent-bg);
      font: inherit;
      color: inherit;
      cursor: pointer;
    }

    .proposalConfirmButton:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    .proposalConfirmButton:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    ```

- [x] **T9 — `MessageList.tsx`: ProposalCard rendern** (AC: 1, 4)
  - [x] In `frontend/src/components/MessageList.tsx` Imports ergänzen:
    ```typescript
    import { ProposalCard } from './ProposalCard'
    ```
  - [x] `MessageListProps` um `onConfirm` erweitern:
    ```typescript
    type MessageListProps = {
      messages: ChatMessage[]
      onConfirm: (proposalId: string) => void
    }
    ```
  - [x] Im JSX, innerhalb der `li`-Renderfunktion, nach der `bubbleMeta`-Div folgende Logik:
    ```tsx
    {message.response?.type === 'proposal' ? (
      <ProposalCard proposal={message.response} onConfirm={onConfirm} />
    ) : (
      <div className="messageContent">{message.content}</div>
    )}
    ```
  - [x] `bubbleMeta` (Rolle + Timestamp) bleibt für alle Messages erhalten.

- [x] **T10 — `App.tsx`: `onConfirm` an `MessageList` weiterleiten** (AC: 1, 5)
  - [x] In `App.tsx`, `MessageList`-Verwendung um `onConfirm`-Prop ergänzen:
    ```tsx
    <MessageList messages={state.messages} onConfirm={handleConfirm} />
    ```

- [x] **T11 — Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [x] **`ProposalCard.test.tsx`** (neue Datei `frontend/src/components/ProposalCard.test.tsx`):
    - [x] ProposalCard rendert Label „Vorschlag (noch nicht ausgeführt)"
    - [x] ProposalCard rendert alle Steps mit step_type
    - [x] ProposalCard rendert parameters_summary wenn vorhanden
    - [x] ProposalCard rendert Button „Bestätigen & Ausführen"
    - [x] Button-Click ruft `onConfirm` mit `proposal_id` auf
    - [x] Button-Click ruft `onConfirm` mit leerem String wenn `proposal_id` undefined
    - [x] Sonderzeichen in step_type werden als Text gerendert (kein HTML-Escape-Durchbruch)
  - [x] **`App.test.tsx`** — Integration (neue Tests in bestehender `describe`-Gruppe):
    - [x] `'Proposal Mock — Card sichtbar statt plain Text'`
    - [x] `'Proposal Mock — Steps aus Fixture gelistet'`
    - [x] `'Proposal Mock — Confirm-Button vorhanden'`
    - [x] `'Nicht-Proposal bleibt plain Text'`
  - [x] Alle 49 Tests (Stories 1.1–1.4 + 2.1) grün.

## Dev Notes

### Architektur-Entscheidung: `ChatMessage.response` als Sidecar

Die entscheidende Änderung dieser Story: `ChatMessage` erhält ein optionales `response?: AssistantResponse`-Feld. **Begründung:**

- `MessageList` braucht die typisierte Response für bedingtes Rendering (ProposalCard vs. Text-Bubble).
- `content: string` kann nicht als Discriminant genutzt werden (kein `formatAssistantResponse`-Rückwärts-Parsing).
- Das `response`-Feld ist `optional` → Keine Breaking Changes für bestehende Tests, die `ChatMessage` ohne `response` erstellen.
- XSS-Baseline: kein `dangerouslySetInnerHTML` an keiner Stelle.

### Backend-API-Kontrakt (implementiert, getestet)

Quelle: `backend/src/gysi_ml/api/schemas.py` + `backend/src/gysi_ml/api/routes/messages.py`

```
POST /v1/sessions/{session_id}/messages
Request:  { "text": "..." }
Response: {
  "type": "proposal",
  "proposal_id": "<uuid>",        ← PFLICHTFELD für Confirm-Flow
  "explanation": "...",           ← wird zu message (Fallback: payload.message)
  "steps": [                      ← Backend nutzt "type", nicht "step_type"!
    { "type": "load_csv", "params": {"source": "..."} },
    ...
  ],
  "confirmation_required": true,
  "spec_id": "<uuid>"
}
```

**Kritisch für `realTransport.ts`:** Backend sendet `step.type`, nicht `step.step_type`. Das Mapping `step.step_type ?? step.type` ist bereits in Story 1.2 implementiert und bleibt unverändert. Das `proposal_id`-Feld muss **neu** extrahiert werden (war in Story 1.2 noch nicht nötig).

### Datenfluss: Proposal → ProposalCard

```
Backend/Mock
    → realTransport / mockTransport
    → ProposalResponse (mit proposal_id)
    → handleSend() in App.tsx
        → chatReducer: SEND_REQUEST_SUCCEEDED
            → pendingProposalId = proposal_id im State
        → ChatMessage.response = ProposalResponse
    → MessageList Props (messages, onConfirm)
        → message.response?.type === 'proposal'
            → <ProposalCard proposal={...} onConfirm={onConfirm} />
```

### Story 2.2 Vorbereitung (was hier noch NICHT implementiert wird)

- `handleConfirm` in `App.tsx` ist ein Stub (`_proposalId: string` → kein-op).
- `state.pendingProposalId` wird gesetzt, aber noch nicht für einen API-Call genutzt.
- Der Confirm-Button löst Story 2.2 aus: `POST /v1/sessions/{session_id}/confirm` mit `{ proposal_id }`.
- Story 2.2 ersetzt den `handleConfirm`-Stub durch den echten API-Call und behandelt Idempotenz + Button-Disabled-State.

### Bestehende Patterns (committen, nicht abweichen)

| Pattern | Quelle | Vorgabe |
|---|---|---|
| Neue Komponente = neue Datei in `components/` | Stories 1.1–1.4 | Immer |
| CSS-Klassen in `App.css` (kein CSS-Modules) | Gesamte Codebasis | `.proposalCard` etc. |
| `data-testid` nicht nötig für neue Komponente | MessageList nutzt `data-testid="chat-message"` | `ProposalCard` ist über `role="button"` testbar |
| XSS: nie `dangerouslySetInnerHTML` | NFR5, Story 1.1 | Absolut |
| Key-Prop bei Listen: stabiler Key | `MessageList.tsx` | `${step_type}-${idx}` |
| Vitest + @testing-library/react | `package.json` | Unveränderlich |
| `vi.resetModules()` + `vi.doMock()` nur für Transport-Mocks | `App.test.tsx` | Nur wenn nötig (für ProposalCard-Tests NICHT nötig) |

### Variablenname Mapping Backend → Frontend

| Backend-Feld | Frontend-Feld | Wo gemappt |
|---|---|---|
| `explanation` | `message` | `realTransport.ts: toAssistantResponse()` |
| `step.type` | `step_type` | `realTransport.ts: toAssistantResponse()` (bereits impl.) |
| `step.params` | `parameters_summary` | `realTransport.ts: toAssistantResponse()` (bereits impl.) |
| `proposal_id` | `proposal_id` | NEU in dieser Story |

### CSS Custom Properties (aus `index.css`)

Verfügbar: `--bg`, `--border`, `--text-h`, `--mono`, `--accent`, `--accent-bg`, `--social-bg`, `--heading`, `--shadow`. ProposalCard nutzt `--bg`, `--border`, `--mono`, `--accent-bg`, `--accent`.

### Scope-Grenze

- **IN Scope:** ProposalCard rendern, `proposal_id` extrahieren, `pendingProposalId` im Reducer speichern, `onConfirm`-Stub.
- **OUT of Scope (Story 2.2):** `POST /v1/sessions/{session_id}/confirm` aufrufen, Button während Request disablen, Run-ID als Einstieg für Story 3.1 liefern.
- **OUT of Scope (Story 2.3):** Alter Proposal als „nicht bestätigt" markieren wenn neue Nachricht gesendet wird.

### References

- [Source: frontend/src/types.ts] — bestehende Typen `ProposalResponse`, `ChatMessage`, `AssistantResponse`
- [Source: frontend/src/state/chatReducer.ts] — `ChatState`, `SEND_REQUEST_SUCCEEDED`-Handler
- [Source: frontend/src/api/realTransport.ts] — `toAssistantResponse()`, Step-Mapping (Backend `type` → `step_type`)
- [Source: frontend/src/api/mockTransport.ts] — `pickFixture()`, Keyword-Routing
- [Source: frontend/src/fixtures/proposal.json] — Mock-Fixture (muss `proposal_id` erhalten)
- [Source: frontend/src/components/MessageList.tsx] — bestehende Render-Logik, `data-testid="chat-message"`
- [Source: frontend/src/App.tsx] — `handleSend()`, `formatAssistantResponse()`, `ChatLayout`-Verwendung
- [Source: frontend/src/App.css] — CSS Custom Properties, bestehende `.statusBlock`-Patterns
- [Source: frontend/src/App.test.tsx] — bestehende Tests (24+), `deferred()`-Helper, `vi.doMock()`-Pattern
- [Source: backend/src/gysi_ml/api/schemas.py] — `MessageResponse`, `ConfirmRequest` (zeigt `proposal_id`-Pflicht)
- [Source: backend/src/gysi_ml/api/routes/confirm.py] — `POST /confirm` erwartet `{ proposal_id }` im Body
- [Source: backend/src/gysi_ml/services/proposal_service.py] — Confirm gibt immer `run_id` zurück (API Contract Decision)
- [Source: _bmad-output/implementation-artifacts/frontend/sprint-status.yaml] — API Contract Decision: confirm → immer run_id

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot — Amelia, Developer Agent)

### Debug Log References

Keine Fehler aufgetreten. Alle 49 Tests auf Anhieb grün.

### Completion Notes List

- `ChatMessage.response` als optionaler Sidecar eingeführt (âkein Breaking Change für bestehende Tests)
- `pendingProposalId` im Reducer gelegt als Basis für Story 2.2 (Confirm-Call)
- `handleConfirm` in `App.tsx` ist bewusst ein Stub (`_proposalId` no-op) — Story 2.2 setzt die echte Logik
- XSS-Guard durchgängig: Kein `dangerouslySetInnerHTML` an keiner Stelle
- `proposal_id`-Extraktion in `realTransport.ts` mit `toNonEmptyString()` gesichert (kein Truthy-Check auf leeren String)
- 8 Unit-Tests für ProposalCard, 4 neue Integration-Tests in App.test.tsx hinzugefügt

### File List

- `frontend/src/types.ts` — `ProposalResponse` + `proposal_id`, `ChatMessage` + `response`
- `frontend/src/api/realTransport.ts` — `proposal_id` extrahiert in `toAssistantResponse()`
- `frontend/src/fixtures/proposal.json` — `proposal_id: "mock-proposal-001"` hinzugefügt
- `frontend/src/state/chatReducer.ts` — `pendingProposalId` in State, Initial State, Reducer
- `frontend/src/App.tsx` — `response`-Sidecar, `handleConfirm`-Stub, `onConfirm`-Prop
- `frontend/src/components/ProposalCard.tsx` — neu erstellt
- `frontend/src/components/MessageList.tsx` — `onConfirm`-Prop, ProposalCard-Rendering
- `frontend/src/App.css` — ProposalCard-Styles ergänzt
- `frontend/src/components/ProposalCard.test.tsx` — neu erstellt (8 Tests)
- `frontend/src/App.test.tsx` — 4 neue Integration-Tests ergänzt
- `frontend/src/api/mockTransport.ts` — `spec_updated`-Fixture-Routing + Import (Scope-Erweiterung aus 1.4-Backlog)
- `frontend/src/components/StatusPanel.tsx` — `uiLabel()`-Strings lokalisiert + `validation_error`-Block (Scope-Erweiterung aus 1.4-Backlog)
- `frontend/src/components/StatusPanel.test.tsx` — 4 neue Tests für StatusPanel (Scope-Erweiterung aus 1.4-Backlog)
- `frontend/src/state/chatReducer.spec-updated.test.ts` — neue Testdatei für spec_updated-Reducer (Scope-Erweiterung aus 1.4-Backlog)
- `frontend/src/fixtures/spec_updated.json` — neues Fixture (Scope-Erweiterung aus 1.4-Backlog)
