# Story 2.3: Proposal modifizieren durch neue Nachricht

Status: done

## Story

Als ein Nutzer,
möchte ich einen Proposal vor Bestätigung durch einfaches Senden einer neuen Nachricht modifizieren können,
damit ich den Vorschlag iterativ durch Spracheingabe präzisieren kann — ohne ein extra Formular oder modale UI.

## Acceptance Criteria

1. **[FR6 — Neue Nachricht überschreibt offenen Proposal]**

   **Given** ein Proposal ist pending (`ui.type === 'proposal_pending'`)
   **When** der Nutzer eine neue User-Message sendet
   **Then** wechselt die UI sofort in den Zustand `sending_message`
   **And** `pendingProposalId` wird auf `null` zurückgesetzt (sofortiges visuelles Feedback)
   **And** die neue Nachricht wird an `POST /v1/sessions/{session_id}/messages` gesendet
   **And** das Backend verwirft den alten Proposal automatisch (`reject_pending_proposals()`)

2. **[FR6 — Alter Proposal bleibt im Verlauf sichtbar als „Nicht bestätigt"]**

   **Given** eine neue Nachricht wurde gesendet während ein Proposal pending war
   **When** die UI den Zustand `sending_message` erreicht
   **Then** zeigt die alte Proposal-Card im Chat-Verlauf das Label „Vorschlag (nicht bestätigt)" (statt „Vorschlag (noch nicht ausgeführt)")
   **And** der CTA-Button „Bestätigen & Ausführen" ist nicht mehr sichtbar
   **And** die Step-Liste des alten Proposals bleibt zur Nachvollziehbarkeit erhalten
   **And** der Chat-Verlauf wird nicht verkürzt (keine Message entfernt)

3. **[FR6 — Neue Response wird normal verarbeitet]**

   **Given** das Backend antwortet auf die Modifizierungs-Nachricht
   **When** die Response eintrifft (`SEND_REQUEST_SUCCEEDED`)
   **Then** wird sie nach dem normalen Response-Pfad verarbeitet:
   - `type: "proposal"` → neue Proposal-Card erscheint, `pendingProposalId` = neue ID, UI-State `proposal_pending`
   - `type: "result"` → UI-State `run_done`
   - `type: "error"` → UI-State `validation_error`

4. **[Accessibility — Kein Deadend nach Modifizierung]**

   **Given** ein Proposal wurde durch neue Nachricht überschrieben
   **When** die Response verarbeitet wurde
   **Then** ist der Composer wieder aktiv (nicht disabled)
   **And** kein Bestätigen des alten Proposals ist mehr möglich (Button nicht vorhanden)
   **And** falls eine neue Proposal-Card erscheint, ist deren CTA-Button aktiv

5. **[Mock-Modus — Modifizierungs-Flow simulierbar]**

   **Given** die App läuft im Mock-Modus und eine Proposal-Card ist sichtbar
   **When** der Nutzer „ändern" oder „modifizieren" als Nachricht sendet
   **Then** antwortet der Mock mit einem neuen Proposal (vorhandenes `proposalFixture`)
   **And** die alte Proposal-Card wechselt auf „Vorschlag (nicht bestätigt)"
   **And** eine neue Proposal-Card erscheint als aktiver Vorschlag

6. **[XSS-Sicherheit — „Nicht bestätigt"-Label]**

   **Given** das „Vorschlag (nicht bestätigt)"-Label wird gerendert
   **When** es im UI erscheint
   **Then** ist es als statischer Text-Node implementiert
   **And** kein dynamischer Nutzer-Content fließt in diesen Bereich (kein `dangerouslySetInnerHTML`)

## Tasks / Subtasks

### T1 — `chatReducer.ts`: `SEND_REQUEST_STARTED` löscht `pendingProposalId` bei aktivem Proposal (AC: 1, 2)

In `frontend/src/state/chatReducer.ts`, den bestehenden `SEND_REQUEST_STARTED`-Case erweitern:

**Aktuell:**
```typescript
case 'SEND_REQUEST_STARTED':
  return {
    ...state,
    ui: { type: 'sending_message' },
    messages: [...state.messages, action.userMessage],
    lastError: null,
  }
```

**Neu:**
```typescript
case 'SEND_REQUEST_STARTED':
  return {
    ...state,
    ui: { type: 'sending_message' },
    messages: [...state.messages, action.userMessage],
    lastError: null,
    // Sofortiges visuelles Feedback: alter Proposal wird als "nicht bestätigt" markiert,
    // sobald der Nutzer eine neue Nachricht sendet.
    pendingProposalId: state.ui.type === 'proposal_pending' ? null : state.pendingProposalId,
  }
```

**Begründung:** `SEND_REQUEST_SUCCEEDED` würde `pendingProposalId` ohnehin auf null setzen (wenn Response kein Proposal ist), aber erst nach Netzwerkverzögerung. Der Guard auf `state.ui.type === 'proposal_pending'` stellt sicher, dass `pendingProposalId` nur in genau diesem Übergang gecleart wird — nicht bei normalen Sends aus `idle`.

**Keine weiteren Reducer-Änderungen nötig:** `SEND_REQUEST_SUCCEEDED` setzt `pendingProposalId` bereits korrekt auf die neue `proposal_id` (oder `null` falls kein Proposal). Diese Logik bleibt unverändert.

---

### T2 — `ProposalCard.tsx`: `isActive` Prop hinzufügen (AC: 2, 4, 6)

In `frontend/src/components/ProposalCard.tsx`:

**Props-Typ erweitern:**
```typescript
type ProposalCardProps = {
  proposal: ProposalResponse
  onConfirm: (proposalId: string) => void
  disabled?: boolean   // aus Story 2.2: Button loading/idempotenz
  isActive?: boolean   // NEU: false = Proposal wurde durch neue Nachricht überschrieben
}
```

**Komponente anpassen (vollständig):**
```tsx
export function ProposalCard({ proposal, onConfirm, disabled, isActive = true }: ProposalCardProps) {
  return (
    <div className={`proposalCard${!isActive ? ' proposalCard--superseded' : ''}`}>
      <div className="proposalLabel">
        {isActive ? 'Vorschlag (noch nicht ausgeführt)' : 'Vorschlag (nicht bestätigt)'}
      </div>
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
      {isActive && (
        <button
          type="button"
          className="proposalConfirmButton"
          onClick={() => onConfirm(proposal.proposal_id ?? '')}
          disabled={disabled}
          aria-disabled={disabled}
        >
          Bestätigen &amp; Ausführen
        </button>
      )}
    </div>
  )
}
```

**Wichtig:**
- `isActive` ist optional mit Default `true` → bestehende Tests und Rendering-Stellen bleiben ohne Änderung lauffähig (kein Breaking Change).
- Der CTA-Button wird bei `!isActive` vollständig aus dem DOM entfernt (`{isActive && <button ...>}`), nicht nur mit `disabled`. Das verhindert irrtümliche Screen-Reader-Fokussierung.
- Das Label ändert sich statisch von „noch nicht ausgeführt" auf „nicht bestätigt" — kein dynamischer Nutzer-Content fließt ein (XSS-sicher).
- Die CSS-Klasse `proposalCard--superseded` ermöglicht optionales visuelles Dimming (z.B. `opacity: 0.6`). Minimales CSS-Update optional — kein Pflichtbestandteil dieser Story.

---

### T3 — `MessageList.tsx`: `activePendingProposalId` Prop + `isActive`-Ableitung (AC: 2, 4)

In `frontend/src/components/MessageList.tsx`:

**Props-Typ erweitern:**
```typescript
type MessageListProps = {
  messages: ChatMessage[]
  onConfirm: (proposalId: string) => void
  confirmDisabled: boolean
  activePendingProposalId: string | null   // NEU: aus state.pendingProposalId
}
```

**Destrukturierung und ProposalCard-Render anpassen:**
```tsx
export function MessageList({ messages, onConfirm, confirmDisabled, activePendingProposalId }: MessageListProps) {
  return (
    <ol className="messageList" aria-label="Chat messages">
      {messages.map((message) => (
        <li
          key={message.id}
          className="message"
          data-role={message.role}
          data-testid="chat-message"
        >
          <div className="messageRow">
            <div className="avatar" aria-hidden="true">
              {message.role === 'assistant'
                ? 'G'
                : message.role === 'user'
                  ? 'U'
                  : 'S'}
            </div>
            <div className="bubble">
              <div className="bubbleMeta">
                <span className="messageRole">{message.role}</span>
                <span className="messageTs">{message.ts}</span>
              </div>
              {message.response?.type === 'proposal' ? (
                <ProposalCard
                  proposal={message.response}
                  onConfirm={onConfirm}
                  disabled={confirmDisabled}
                  isActive={
                    activePendingProposalId !== null &&
                    message.response.proposal_id === activePendingProposalId
                  }
                />
              ) : (
                <div className="messageContent">{message.content}</div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
```

**Logik für `isActive`:**
- `activePendingProposalId === null` → kein aktiver Proposal → alle Cards sind `isActive=false`
- `activePendingProposalId !== null` → nur die Card mit übereinstimmender `proposal_id` ist `isActive=true`
- `proposal_id` fehlt in der Message (`undefined`) und `activePendingProposalId` ist gesetzt → `undefined === "xxx"` ergibt `false` → Card zeigt „nicht bestätigt" (sicher, da wir die Karte nicht identifizieren können)

`confirmDisabled` kontrolliert weiterhin den Button-disabled-State der **aktiven** Card (während `isConfirming` oder außerhalb `proposal_pending`). Das Zusammenspiel ist konsistent:
- `isActive=true, disabled=false` → Button aktiv und klickbar
- `isActive=true, disabled=true` → Button sichtbar aber deaktiviert (z.B. während Confirm-Request)
- `isActive=false` → kein Button (Card ist überschrieben)

---

### T4 — `App.tsx`: `activePendingProposalId` an `MessageList` durchreichen (AC: 1, 2, 4)

In `frontend/src/App.tsx`, die `MessageList`-Verwendung anpassen:

**Aktuell:**
```tsx
<MessageList
  messages={state.messages}
  onConfirm={handleConfirm}
  confirmDisabled={state.isConfirming || state.ui.type !== 'proposal_pending'}
/>
```

**Neu:**
```tsx
<MessageList
  messages={state.messages}
  onConfirm={handleConfirm}
  confirmDisabled={state.isConfirming || state.ui.type !== 'proposal_pending'}
  activePendingProposalId={state.pendingProposalId}
/>
```

**Kein weiterer Änderungsbedarf in `App.tsx`.** `handleSend` lässt bereits das Senden aus `proposal_pending` zu (Guard nur gegen `sending_message`). Das Backend übernimmt das Verwerfen des alten Proposals automatisch.

---

### T5 — `mockTransport.ts`: „ändern"/„modifizieren"-Trigger hinzufügen (AC: 5)

In `frontend/src/api/mockTransport.ts`, in der `pickFixture`-Funktion **vor** dem bestehenden `proposal`-Check ergänzen:

```typescript
function pickFixture(userText: string): AssistantResponse {
  const text = userText.trim().toLowerCase()

  if (text.includes('undo') || text.includes('rückgängig') || text.includes('revert')) {
    return specUpdatedFixture as AssistantResponse
  }

  // NEU: Modifizierungs-Keywords → neuer Proposal (simuliert Modify-Flow)
  if (text.includes('ändern') || text.includes('modifizieren') || text.includes('modify')) {
    return proposalFixture as AssistantResponse
  }

  if (text.includes('proposal') || text.includes('vorschlag')) {
    return proposalFixture as AssistantResponse
  }

  if (text.includes('error') || text.includes('fehler') || text.includes('fail')) {
    return errorFixture as AssistantResponse
  }

  return resultFixture as AssistantResponse
}
```

**Anmerkung:** Derselbe `proposalFixture` (mit `proposal_id: "mock-proposal-001"`) wird zurückgegeben. Im Mock-Modus ist das ausreichend: der neue Proposal überschreibt die `pendingProposalId` im State (`proposal_id` aus dem Fixture bleibt gleich, aber der State-Wechsel über `SEND_REQUEST_STARTED → SEND_REQUEST_SUCCEEDED` sorgt für das korrekte UI-Verhalten). Kein neues Fixture nötig.

---

### T6 — Tests: `chatReducer.modify.test.ts` (AC: 1, 3)

Neue Testdatei: `frontend/src/state/chatReducer.modify.test.ts`

```typescript
import { describe, expect, it } from 'vitest'
import { chatReducer, createInitialChatState } from './chatReducer'
import type { ChatState, ChatMessage } from '../types'

function makeProposalPendingState(): ChatState {
  return {
    ...createInitialChatState(),
    ui: { type: 'proposal_pending' },
    pendingProposalId: 'mock-proposal-001',
    sessionId: 'session-abc',
  }
}

const dummyUserMessage: ChatMessage = {
  id: 'u1',
  role: 'user',
  content: 'modifizieren',
  ts: new Date().toISOString(),
}

describe('SEND_REQUEST_STARTED — Modify-Flow', () => {
  it('löscht pendingProposalId wenn ui.type === proposal_pending', () => {
    const state = makeProposalPendingState()
    const next = chatReducer(state, {
      type: 'SEND_REQUEST_STARTED',
      userMessage: dummyUserMessage,
    })
    expect(next.pendingProposalId).toBeNull()
    expect(next.ui.type).toBe('sending_message')
  })

  it('behält pendingProposalId wenn ui.type !== proposal_pending', () => {
    const state = {
      ...createInitialChatState(),
      ui: { type: 'idle' } as const,
      pendingProposalId: 'some-id',
    }
    const next = chatReducer(state, {
      type: 'SEND_REQUEST_STARTED',
      userMessage: dummyUserMessage,
    })
    expect(next.pendingProposalId).toBe('some-id')
  })

  it('fügt userMessage zu messages hinzu', () => {
    const state = makeProposalPendingState()
    const next = chatReducer(state, {
      type: 'SEND_REQUEST_STARTED',
      userMessage: dummyUserMessage,
    })
    expect(next.messages).toContain(dummyUserMessage)
  })
})
```

---

### T7 — Tests: `ProposalCard.test.tsx` erweitern (AC: 2, 4, 6)

In `frontend/src/components/ProposalCard.test.tsx` neue `describe`-Gruppe ergänzen:

```typescript
describe('ProposalCard — isActive=false (superseded)', () => {
  const baseProps = {
    proposal: {
      type: 'proposal' as const,
      proposal_id: 'mock-proposal-001',
      message: 'Vorschlag-Text',
      steps: [{ step_type: 'load_csv', parameters_summary: 'source=bike.csv' }],
    },
    onConfirm: vi.fn(),
    disabled: false,
    isActive: false,
  }

  it('zeigt "Vorschlag (nicht bestätigt)" als Label', () => {
    render(<ProposalCard {...baseProps} />)
    expect(screen.getByText('Vorschlag (nicht bestätigt)')).toBeInTheDocument()
  })

  it('rendert keinen Confirm-Button', () => {
    render(<ProposalCard {...baseProps} />)
    expect(screen.queryByRole('button', { name: /bestätigen/i })).not.toBeInTheDocument()
  })

  it('zeigt weiterhin die Step-Liste', () => {
    render(<ProposalCard {...baseProps} />)
    expect(screen.getByText('load_csv')).toBeInTheDocument()
  })
})

describe('ProposalCard — isActive=true (Standard / Regression)', () => {
  const baseProps = {
    proposal: {
      type: 'proposal' as const,
      proposal_id: 'mock-proposal-001',
      message: 'Vorschlag-Text',
      steps: [{ step_type: 'load_csv', parameters_summary: 'source=bike.csv' }],
    },
    onConfirm: vi.fn(),
    disabled: false,
  }

  it('zeigt "Vorschlag (noch nicht ausgeführt)" als Label (Default)', () => {
    render(<ProposalCard {...baseProps} />)
    expect(screen.getByText('Vorschlag (noch nicht ausgeführt)')).toBeInTheDocument()
  })

  it('zeigt den Confirm-Button', () => {
    render(<ProposalCard {...baseProps} />)
    expect(screen.getByRole('button', { name: /bestätigen/i })).toBeInTheDocument()
  })
})
```

**Hinweis:** Bestehende Tests mit `disabled`-Verhalten (aus Story 2.2) müssen NICHT verändert werden — `isActive` hat Default `true`.

---

### T8 — Tests: `MessageList.test.tsx` — `activePendingProposalId` (AC: 2, 4)

In der bestehenden Testdatei `frontend/src/components/MessageList.test.tsx` (oder neu anlegen falls nicht vorhanden):

```typescript
describe('MessageList — Proposal isActive-Ableitung', () => {
  const proposalMessage: ChatMessage = {
    id: 'msg-1',
    role: 'assistant',
    content: 'Vorschlag-Fallback-Text',
    ts: new Date().toISOString(),
    response: {
      type: 'proposal',
      proposal_id: 'prop-001',
      message: 'Vorschlag',
      steps: [{ step_type: 'load_csv', parameters_summary: '' }],
    },
  }

  it('zeigt Proposal als aktiv wenn proposal_id mit activePendingProposalId übereinstimmt', () => {
    render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId="prop-001"
      />
    )
    expect(screen.getByRole('button', { name: /bestätigen/i })).toBeInTheDocument()
    expect(screen.getByText('Vorschlag (noch nicht ausgeführt)')).toBeInTheDocument()
  })

  it('zeigt Proposal als überschrieben wenn activePendingProposalId null ist', () => {
    render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId={null}
      />
    )
    expect(screen.queryByRole('button', { name: /bestätigen/i })).not.toBeInTheDocument()
    expect(screen.getByText('Vorschlag (nicht bestätigt)')).toBeInTheDocument()
  })

  it('zeigt Proposal als überschrieben wenn activePendingProposalId eine andere ID ist', () => {
    render(
      <MessageList
        messages={[proposalMessage]}
        onConfirm={vi.fn()}
        confirmDisabled={false}
        activePendingProposalId="prop-002"
      />
    )
    expect(screen.queryByRole('button', { name: /bestätigen/i })).not.toBeInTheDocument()
  })
})
```

## Dev Notes

### Architektur-Prinzipien

- **Backend als Source of Truth für Proposal-Verwerfung:** Das Frontend setzt `pendingProposalId = null` in `SEND_REQUEST_STARTED` nur für sofortiges visuelles Feedback. Die eigentliche Verwerfung des Proposals (`reject_pending_proposals()` in `message_service.py`) erfolgt im Backend — das Frontend hat keine eigene Proposal-Cancel-API.
- **Kein neuer Transport-Code:** `sendAssistantMessage()` ist vollständig wiederverwendbar. Keine neuen API-Calls, keine neuen Transport-Types.
- **State Machine bleibt konsistent:** `proposal_pending → sending_message → (proposal_pending | run_done | run_failed | validation_error)` ist der Flow. Der Reducer ist bereits korrekt aufgebaut; T1 ist die einzige Reducer-Änderung.

### Dateien, die angefasst werden

| Datei | Änderungstyp |
| --- | --- |
| `frontend/src/state/chatReducer.ts` | Minimal: 1 Zeile in `SEND_REQUEST_STARTED` |
| `frontend/src/components/ProposalCard.tsx` | Props + konditionelles Rendering |
| `frontend/src/components/MessageList.tsx` | Props + `isActive`-Ableitung |
| `frontend/src/App.tsx` | 1 neue Prop in `<MessageList>` |
| `frontend/src/api/mockTransport.ts` | 1 neuer Keyword-Block in `pickFixture()` |

### Keine Änderungen an folgenden Dateien

- `frontend/src/api/transport.ts` — keine neuen API-Calls
- `frontend/src/api/realTransport.ts` — Backend-Kommunikation unverändert
- `frontend/src/api/mockTransport.ts` (Struktur) — nur `pickFixture` erweitert
- `frontend/src/api/transportTypes.ts` — keine neuen Types
- `frontend/src/types.ts` — keine neuen Types
- `frontend/src/fixtures/` — kein neues Fixture nötig

### Backend-API-Contract (relevant für Story 2.3)

`POST /v1/sessions/{session_id}/messages` — unverändertes Verhalten:

```python
# In message_service.py, vor LLM-Aufruf:
proposal_repository.reject_pending_proposals(session_id=session_id, db_path=db_path)
```

Das Backend verwirft **implizit** alle pending Proposals der Session, bevor es die neue Nachricht verarbeitet. Der Response-Typ kann daher alles sein: `proposal | result | error | spec_updated`.

**Kein Frontend-seitiger Cancel-Call notwendig.**

### Testing-Standards

- Neue Tests in `frontend/src/state/chatReducer.modify.test.ts` (T6) — eigenständige Datei wie `chatReducer.confirm.test.ts` aus Story 2.2.
- `ProposalCard.test.tsx` (T7) — bestehende Datei um neue `describe`-Gruppe ergänzen, keine bestehenden Tests ändern.
- `MessageList.test.tsx` (T8) — neue `describe`-Gruppe; Datei ggf. anlegen falls nicht vorhanden.
- Alle Tests mit `vitest` + `@testing-library/react` (bereits konfiguriert).
- Mock-Modus: `MOCK_LATENCY_MS` im Testmodus ist `0` (bereits in `mockTransport.ts` definiert).

### Regression-Schutz

- `isActive` hat Default `true` in `ProposalCard` → kein Breaking Change an bestehenden Render-Stellen.
- `activePendingProposalId` ist neues **required** Prop in `MessageList` → TypeScript-Fehler wenn `App.tsx` nicht angepasst wird. Das ist gewollt: T3 und T4 müssen gemeinsam umgesetzt werden.
- `confirmDisabled`-Logik in `App.tsx` bleibt unverändert.
- `SEND_REQUEST_SUCCEEDED` Reducer-Logik für `pendingProposalId` bleibt unverändert.

### UX-Verhalten bei Grenzfällen

- **Backend liefert kein `proposal_id`:** `pendingProposalId` bleibt `null` (aus `toNonEmptyString` in `realTransport.ts`), alle Proposal-Cards zeigen `isActive=false`. Safe.
- **Zwei Proposals hintereinander:** Alter Proposal (ID A) → `isActive=false`. Neuer Proposal (ID B) → `isActive=true`. Korrekt.
- **Proposal ohne `proposal_id` in History:** `message.response.proposal_id === undefined`, `activePendingProposalId !== null` → `isActive=false`. Safe.

### Project Structure Notes

- Tests folgen der Konvention aus Story 2.2: Feature-spezifische Test-Datei unter `src/state/` für Reducer-Tests.
- Keine neuen Ordner oder Module nötig.
- CSS für `.proposalCard--superseded` ist optional enhancement; kein funktionales Muss.

### References

- [Source: _bmad-output/planning-artifacts/frontend/epics.md#Epic-2-Story-2.3]
- [Source: _bmad-output/planning-artifacts/frontend/epics.md#FR6-FE6]
- [Source: _bmad-output/planning-artifacts/frontend/ux-spec.md#5.7-Proposal-ändern]
- [Source: backend/src/gysi_ml/services/message_service.py — reject_pending_proposals()]
- [Source: backend/src/gysi_ml/persistence/proposal_repository.py — reject_pending_proposals()]
- [Source: frontend/src/state/chatReducer.ts — SEND_REQUEST_STARTED, SEND_REQUEST_SUCCEEDED]
- [Source: frontend/src/components/ProposalCard.tsx — disabled prop aus Story 2.2]
- [Source: frontend/src/components/MessageList.tsx — confirmDisabled aus Story 2.2]
- [Source: _bmad-output/implementation-artifacts/frontend/2-2-confirm-flow-bestaetigen-und-ausfuehren.md — T6, T7, T8]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot — Developer Agent)

### Debug Log References

Keine Abweichungen vom Story-Plan. Alle Tasks exakt nach Spec umgesetzt.

### Completion Notes List

- T1: `SEND_REQUEST_STARTED` guard `state.ui.type === 'proposal_pending'` setzt `pendingProposalId` sofort auf null — kein Netzwerk-Delay.
- T2: `isActive` default `true` → kein Breaking Change in bestehenden Tests/Render-Stellen.
- T3: `activePendingProposalId` als required Prop — TypeScript erzwingt T4-Änderung in App.tsx.
- T5: `proposalFixture` (mock-proposal-001) wird bei ändern/modifizieren/modify zurückgegeben — ausreichend für Mock-Flow-Simulation.
- T8: `MessageList.test.tsx` neu angelegt (Datei existierte noch nicht).
- Testsuite: 81/81 Tests grün (11 Dateien).

### File List

- `frontend/src/state/chatReducer.ts`
- `frontend/src/components/ProposalCard.tsx`
- `frontend/src/components/MessageList.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/mockTransport.ts`
- `frontend/src/state/chatReducer.modify.test.ts` _(neu)_
- `frontend/src/components/ProposalCard.test.tsx`
- `frontend/src/components/MessageList.test.tsx` _(neu)_
- `_bmad-output/implementation-artifacts/frontend/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/frontend/2-3-proposal-modifizieren-durch-neue-nachricht.md`
