# Story 1.4: Fehlerfälle und Undo im UI sichtbar machen

Status: done

## Story

Als ein Nutzer,
möchte ich Validation-Errors verständlich im Chat sehen, sofort danach neue Nachrichten senden können und
nach Undo/Spec-Änderungs-Aktionen die aktualisierte Spec-Version im Status-Panel sehen,
damit ich ohne Deadends iterieren kann und immer weiß, welche Spec-Version aktiv ist.

## Acceptance Criteria

1. **[FR11 — Validation Error sichtbar]**

   **Given** das Backend antwortet mit `type: "error"` oder HTTP 422
   **When** die Message gerendert wird
   **Then** sehe ich eine verständliche Fehlermeldung als Assistant-Message im Chat
   **And** das Status-Panel zeigt den Zustand `validation_error` leserlich an (nicht als roher State-Label)

2. **[FR11 — Kein Deadend nach Fehler]**

   **Given** die UI befindet sich im Zustand `validation_error`
   **When** ich eine neue Nachricht eingebe
   **Then** ist der Composer aktiv (nicht disabled)
   **And** ich kann die Nachricht mit Enter absenden

3. **[FR14 — Spec-Updated Response empfangen]**

   **Given** das Backend antwortet mit `type: "spec_updated"` (z.B. nach Undo/Spec-Revert)
   **When** die Response verarbeitet wird
   **Then** zeigt die UI die `explanation` als Assistant-Message im Chat an
   **And** die UI wechselt in den Zustand `idle`

4. **[FR14 — Status-Panel aktualisiert sich nach Spec-Change]**

   **Given** das Backend antwortet mit `type: "spec_updated"` und enthält `version` + `spec.steps`
   **When** die Response verarbeitet wird
   **Then** zeigt das Status-Panel unter Spec Summary die neue `spec_version_id` und die aktualisierte Step-Liste an

5. **[Mock-Modus: spec_updated testbar]**

   **Given** die App läuft im Mock-Modus
   **When** der Nutzer eine Nachricht sendet, die „undo", „rückgängig" oder „revert" enthält
   **Then** antwortet der Mock-Transport mit dem `spec_updated`-Fixture
   **And** die Spec Summary im Status-Panel aktualisiert sich

## Tasks / Subtasks

- [x] **T1 — `SpecUpdatedResponse` Type hinzufügen** (AC: 3, 4)
  - [x] In `frontend/src/types.ts`: Interface `SpecUpdatedResponse` anlegen:
    ```typescript
    export interface SpecUpdatedResponse {
      type: 'spec_updated'
      message: string
      spec_summary: SpecSummary
    }
    ```
  - [x] `AssistantResponse` Union um `SpecUpdatedResponse` erweitern:
    ```typescript
    export type AssistantResponse = ProposalResponse | ResultResponse | ErrorResponse | SpecUpdatedResponse
    ```

- [x] **T2 — `realTransport.ts`: `spec_updated` mappen** (AC: 3, 4)
  - [x] In `frontend/src/api/realTransport.ts`, in der Funktion `toAssistantResponse()`:
    - [x] Neuen Branch VOR dem Fallback-Block ergänzen (nach dem `error`-Branch):
      ```typescript
      if (type === 'spec_updated') {
        const message =
          toNonEmptyString(payload.explanation) ??
          toNonEmptyString(payload.message) ??
          fallbackMessage
        const version = toNonEmptyString(payload.version) ?? 'unknown'
        const rawSpec = isRecord(payload.spec) ? payload.spec : {}
        const rawSteps = Array.isArray(rawSpec.steps) ? rawSpec.steps : []
        const spec_summary: SpecSummary = {
          spec_version_id: version,
          steps: rawSteps.map((s) => {
            const step = isRecord(s) ? s : {}
            return {
              step_type: toNonEmptyString(step.step_type ?? step.type) ?? 'unknown',
              enabled: typeof step.enabled === 'boolean' ? step.enabled : true,
            }
          }),
        }
        return { type: 'spec_updated', message, spec_summary }
      }
      ```
    - [x] `SpecSummary` aus `'../types'` importieren (prüfen ob bereits importiert)

- [x] **T3 — `chatReducer.ts`: `spec_updated` im Reducer** (AC: 3, 4)
  - [x] `nextUiStateForResponse()` um `spec_updated` ergänzen:
    ```typescript
    case 'spec_updated':
      return { type: 'idle' }
    ```
  - [x] In `SEND_REQUEST_SUCCEEDED`-Handler den `specSummary`-Extract erweitern:
    ```typescript
    const specSummary =
      response.type === 'proposal' || response.type === 'result'
        ? response.spec_summary ?? state.specSummary
        : response.type === 'spec_updated'
          ? response.spec_summary
          : state.specSummary
    ```
  - [x] TypeScript-Check: `SpecUpdatedResponse` wird automatisch über `AssistantResponse` abgedeckt (kein separater Import nötig, da `chatReducer.ts` `AssistantResponse` aus `types.ts` importiert)

- [x] **T4 — `App.tsx`: `formatAssistantResponse()` für `spec_updated`** (AC: 3)
  - [x] In `formatAssistantResponse()` neuen Case ergänzen:
    ```typescript
    case 'spec_updated':
      return response.message
    ```
  - [x] Sicherstellen, dass TypeScript den exhaustive switch erkennt (kein `default` nötig wenn alle Fälle abgedeckt)

- [x] **T5 — Fixture `spec_updated.json` anlegen** (AC: 5)
  - [x] `frontend/src/fixtures/spec_updated.json` neu anlegen:
    ```json
    {
      "type": "spec_updated",
      "message": "Spec aktualisiert (Mock): Preprocessing auf v1 rückgesetzt.",
      "spec_summary": {
        "spec_version_id": "mock-spec-undo-v1",
        "steps": [
          { "step_type": "load_csv", "enabled": true },
          { "step_type": "train_model", "enabled": false }
        ]
      }
    }
    ```

- [x] **T6 — `mockTransport.ts`: Keyword-Routing für `spec_updated`** (AC: 5)
  - [x] Import ergänzen: `import specUpdatedFixture from '../fixtures/spec_updated.json'`
  - [x] In `pickFixture()` als ERSTEN Branch ergänzen (vor `proposal`-Branch):
    ```typescript
    if (text.includes('undo') || text.includes('rückgängig') || text.includes('revert')) {
      return specUpdatedFixture as AssistantResponse
    }
    ```

- [x] **T7 — `StatusPanel.tsx`: `validation_error`-Block und lesbare Labels** (AC: 1)
  - [x] `uiLabel()`-Funktion auf deutsche, lesbare Texte umstellen:
    ```typescript
    case 'idle': return 'Bereit'
    case 'sending_message': return 'Sendet…'
    case 'proposal_pending': return 'Vorschlag ausstehend'
    case 'run_polling': return 'Run läuft…'
    case 'run_done': return 'Run abgeschlossen'
    case 'run_failed': return 'Run fehlgeschlagen'
    case 'validation_error': return 'Validierungsfehler'
    case 'backend_unreachable': return 'Backend nicht erreichbar'
    ```
  - [x] `validation_error`-Block im JSX ergänzen (direkt nach `backend_unreachable`-Block):
    ```tsx
    {ui.type === 'validation_error' && (
      <div className="statusBlock statusBlock--warning">
        <div className="statusTitle">Hinweis</div>
        <div className="statusMeta">
          Validierungsfehler aufgetreten. Sieh dir die Fehlermeldung im Chat an
          und sende eine neue Nachricht.
        </div>
      </div>
    )}
    ```

- [x] **T8 — `App.css`: fehlende CSS-Klassen ergänzen** (AC: 1)
  - [x] In `frontend/src/App.css` nach `.statusBlock`-Block ergänzen:
    ```css
    .statusBlock--error {
      border-color: #e53e3e;
      background: #fff5f5;
    }

    .statusBlock--warning {
      border-color: #d69e2e;
      background: #fffff0;
    }
    ```
  - [x] Hinweis: `.statusBlock--error` fehlt bisher ebenfalls im CSS (war schon in Story 1.3 referenziert aber nie definiert — diese Story schließt den Rückstand)

- [x] **T9 — Tests** (AC: 1, 2, 3, 4, 5)
  - [x] **Reducer-Tests** für `spec_updated` (neue Datei `frontend/src/state/chatReducer.spec-updated.test.ts`):
    - [x] `SEND_REQUEST_SUCCEEDED` mit `spec_updated`-Response → `ui.type === 'idle'`
    - [x] `SEND_REQUEST_SUCCEEDED` mit `spec_updated`-Response → `specSummary` aktualisiert
  - [x] **StatusPanel-Tests** (`frontend/src/components/StatusPanel.test.tsx`):
    - [x] `validation_error`-Block sichtbar wenn `ui.type === 'validation_error'`
    - [x] `validation_error`-Block nicht sichtbar wenn `ui.type === 'idle'`
  - [x] **App-Tests** (`frontend/src/App.test.tsx`):
    - [x] Test `'Validation error: nach Fehler sofort wieder senden moeglich'` — `uiLabel`-Check anpassen: `expect(screen.getByText(/Validierungsfehler/)).toBeInTheDocument()` (war: `UI State: validation_error`)
    - [x] Neuer Test: `spec_updated Mock — Spec Summary im Status-Panel aktualisiert sich`
      - Nutzer sendet `undo` im Mock-Modus
      - Warten auf Assistant-Message: `/Spec aktualisiert \(Mock\)/`
      - Prüfen: Spec Summary zeigt `mock-spec-undo-v1`
  - [x] Alle bestehenden Tests müssen weiterhin grün sein (24+ Tests aus Stories 1.1–1.3)

## Dev Notes

### Guardrails (MVP bindend)

- Alle Inhalte weiterhin als Text rendern — kein `dangerouslySetInnerHTML` (XSS-Baseline).
- Kein neues Modal/Seite — Single Page bleibt Single Page.
- `spec_updated` soll den UI-Zustand auf `idle` setzen (nicht `validation_error` o.Ä.) — der Nutzer kann sofort weiterarbeiten.
- Kein Logging sensibler Daten; keine API-Keys im Frontend.

### Implementierter Backend-Kontext (wichtig für Korrektheit)

Das Backend (`backend/src/gysi_ml/api/schemas.py`) dokumentiert offiziell:

```python
class MessageResponse(BaseModel):
    """Typisierte Response fuer POST /messages."""
    type: str  # "proposal" | "result" | "error" | "spec_updated" | "comparison"
    version: Optional[str] = None
    spec: Optional[dict] = None
    explanation: Optional[str] = None
    # ... weitere optionale Felder
```

Der Backend-Service (`message_service.py`) sendet für `action == "modify_spec"`:

```python
return {
    "type": "spec_updated",
    "spec_id": spec_entry["spec_id"],
    "version": spec_entry["version"],       # z.B. "v2"
    "spec": spec_entry["spec"],             # dict mit "steps"-Array
    "explanation": explanation,              # String aus LLM
}
```

Die `spec_entry["spec"].steps` sind Backend-Objekte mit `"type"` (nicht `"step_type"`!) und `"params"` als dict:

```json
{
  "steps": [
    { "type": "load_csv", "enabled": true, "params": {} },
    { "type": "train_model", "enabled": false, "params": { "n_estimators": 100 } }
  ]
}
```

→ `realTransport.ts::toAssistantResponse()` muss wie bei `proposal` sowohl `step.type` als auch `step.step_type` berücksichtigen (beide bereits durch `toNonEmptyString(step.step_type ?? step.type)` abgedeckt).

### Bestehende Patterns (zwingend beibehalten)

- **`chatReducer.ts`**: `nextUiStateForResponse()` muss exhaustive bleiben (TypeScript exhaustiveness prüfen)
- **`realTransport.ts`**: `toAssistantResponse()` — `isRecord()` und `toNonEmptyString()` bereits vorhanden, wiederverwenden
- **`mockTransport.ts`**: `pickFixture()` — neuer Branch muss VOR `proposal` stehen (längerer keyword-match hat Vorrang)
- **`types.ts`**: `SpecSummary`-Interface ist bereits definiert — wiederverwenden, NICHT neu anlegen

### Bestehende Dateistruktur (unverändert lassen)

```text
frontend/src/
  api/
    realTransport.ts     ← T2: spec_updated Branch
    mockTransport.ts     ← T6: undo/rückgängig/revert Routing
    transport.ts         ← nicht anfassen
    transportTypes.ts    ← nicht anfassen
    healthApi.ts         ← nicht anfassen
  state/
    chatReducer.ts       ← T3: spec_updated Case + specSummary-Extrakt
  components/
    StatusPanel.tsx      ← T7: validation_error Block + uiLabel verbessern
    StatusPanel.test.tsx ← T9: neue Tests
  fixtures/
    spec_updated.json    ← T5: NEU anlegen
    error.json           ← nicht anfassen
    proposal.json        ← nicht anfassen
    result.json          ← nicht anfassen
  types.ts               ← T1: SpecUpdatedResponse
  App.tsx                ← T4: spec_updated Case
  App.test.tsx           ← T9: bestehenden Test anpassen + neuer Test
  App.css                ← T8: statusBlock--error / statusBlock--warning
```

### Wichtig: App.test.tsx — bestehender Test muss angepasst werden

In Story 1.3 gibt es einen Test, der explizit prüft:

```typescript
expect(screen.getByText(/UI State: validation_error/)).toBeInTheDocument()
```

Nach T7 (deutsche Labels in `uiLabel()`) muss dieser Test geändert werden:

```typescript
// NEU: German label nach T7
expect(screen.getByText(/Validierungsfehler/)).toBeInTheDocument()
```

Der Test selbst (`'Validation error: nach Fehler sofort wieder senden moeglich'`) bleibt inhaltlich valide — nur die Text-Prüfung ändert sich.

### Testing-Hinweise

- Mock-Modus aktiv in Tests (kein Health-Polling, kein Real-Backend nötig).
- Für neuen `spec_updated`-Integration-Test: `await screen.findByText(/Spec aktualisiert \(Mock\)/)` verwenden.
- Reducer-Tests: synchron, keine async-Operationen nötig.
- StatusPanel-Tests: `render(<StatusPanel ... ui={{ type: 'validation_error' }} />)` und `screen.getByText(...)`.
- Alle Tests mit `uv run` → nein, Frontend nutzt `npm run test` via Vitest! Korrekt: `npm run test` oder `npx vitest run` im `frontend/`-Verzeichnis.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot Developer Agent)

### Debug Log References

- Vitest Output: 37/37 Tests grün

### Completion Notes List

- `SpecUpdatedResponse`-Interface in `types.ts` angelegt; `AssistantResponse` Union erweitert.
- `toAssistantResponse()` in `realTransport.ts` um `spec_updated`-Branch ergänzt (Backend-Felder `explanation`/`message`, `version`, `spec.steps[].type` korrekt gemappt).
- `nextUiStateForResponse()` und `SEND_REQUEST_SUCCEEDED`-Handler im Reducer um `spec_updated` erweitert (exhaustive switch beibehalten).
- `formatAssistantResponse()` in `App.tsx` um `case 'spec_updated'` ergänzt.
- Fixture `spec_updated.json` angelegt; `mockTransport.ts` um Keyword-Routing (undo/rückgängig/revert) als ersten Branch ergänzt.
- `StatusPanel.tsx`: `uiLabel()` auf deutsche Texte umgestellt; `validation_error`-Block ergänzt (kein `dangerouslySetInnerHTML`).
- `App.css`: `.statusBlock--error` und `.statusBlock--warning` ergänzt.
- Neue Testdateien: `chatReducer.spec-updated.test.ts` (4 Tests), erweiterte `StatusPanel.test.tsx` (+2 Tests), `App.test.tsx` (+1 Test, 1 Test angepasst).
- Bestehende 24 Tests aus Stories 1.1–1.3 bleiben grün; Gesamtergebnis: 37/37.

### File List

- frontend/src/types.ts
- frontend/src/api/realTransport.ts
- frontend/src/api/mockTransport.ts
- frontend/src/state/chatReducer.ts
- frontend/src/state/chatReducer.spec-updated.test.ts
- frontend/src/components/StatusPanel.tsx
- frontend/src/components/StatusPanel.test.tsx
- frontend/src/fixtures/spec_updated.json
- frontend/src/App.tsx
- frontend/src/App.test.tsx
- frontend/src/App.css

### References

- Backend-Schema: [backend/src/gysi_ml/api/schemas.py](backend/src/gysi_ml/api/schemas.py#L112-L140)
  → `MessageResponse.type: str # "proposal" | "result" | "error" | "spec_updated" | "comparison"`
- Backend-Service: [backend/src/gysi_ml/services/message_service.py](backend/src/gysi_ml/services/message_service.py#L148-L165)
  → `modify_spec`-Action → `spec_updated`-Response
- Frontend Types: [frontend/src/types.ts](frontend/src/types.ts)
- Reducer: [frontend/src/state/chatReducer.ts](frontend/src/state/chatReducer.ts)
- realTransport: [frontend/src/api/realTransport.ts](frontend/src/api/realTransport.ts)
- mockTransport: [frontend/src/api/mockTransport.ts](frontend/src/api/mockTransport.ts)
- StatusPanel: [frontend/src/components/StatusPanel.tsx](frontend/src/components/StatusPanel.tsx)
- App.tsx: [frontend/src/App.tsx](frontend/src/App.tsx)
- App.css: [frontend/src/App.css](frontend/src/App.css)
- Bestehende Health-Tests: [frontend/src/state/chatReducer.health.test.ts](frontend/src/state/chatReducer.health.test.ts)
- Epics FR11 + FR14: [_bmad-output/planning-artifacts/frontend/epics.md](_bmad-output/planning-artifacts/frontend/epics.md)
- UX-Spec Section 5.3 + 7.1: [_bmad-output/planning-artifacts/frontend/ux-spec.md](_bmad-output/planning-artifacts/frontend/ux-spec.md)
- Story 1.3 (Vorgänger): [_bmad-output/implementation-artifacts/frontend/1-3-status-panel-backend-health-und-spec-summary.md](_bmad-output/implementation-artifacts/frontend/1-3-status-panel-backend-health-und-spec-summary.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot Dev Agent — Implementierung)

### Debug Log References

- `vi.doMock('./api/transport')` aus Test 4 persistiert nach `vi.resetModules()` → Fix: `vi.doUnmock()` in Test 5 explizit aufrufen

### Completion Notes List

- Backend vollständig — `spec_updated` in `message_service.py` bereits implementiert. Kein Backend-Nacharbeit.
- Backend-Steps nutzen `"type"` (nicht `"step_type"`) — bereits durch `toNonEmptyString(step.step_type ?? step.type)` abgedeckt.
- `uiLabel()` von rohen State-Labels auf deutsche Texte umgestellt (validierbar über StatusPanel.test.tsx).
- Bestehender Test `'Validation error: ...'` musste auf `/Validierungsfehler aufgetreten/` präzisiert werden, da jetzt 3 Elemente `/Validierungsfehler/` matchen.

### File List

- `frontend/src/types.ts` — `SpecUpdatedResponse` Interface + `AssistantResponse` Union
- `frontend/src/api/realTransport.ts` — `spec_updated` Branch in `toAssistantResponse()`, `SpecSummary` Import
- `frontend/src/api/mockTransport.ts` — `specUpdatedFixture` Import + undo/rückgängig/revert Routing
- `frontend/src/state/chatReducer.ts` — `spec_updated` in `nextUiStateForResponse()` + `specSummary`-Extraktion
- `frontend/src/App.tsx` — `spec_updated` Case in `formatAssistantResponse()`
- `frontend/src/App.css` — `.statusBlock--error` + `.statusBlock--warning`
- `frontend/src/components/StatusPanel.tsx` — deutsche `uiLabel()`-Texte + `validation_error`-Block
- `frontend/src/fixtures/spec_updated.json` — NEU
- `frontend/src/state/chatReducer.spec-updated.test.ts` — NEU (4 Tests)
- `frontend/src/components/StatusPanel.test.tsx` — 2 neue Tests für `validation_error`
- `frontend/src/App.test.tsx` — 1 Test angepasst (uiLabel-Assertion), 1 neuer Test (`spec_updated Mock`)
