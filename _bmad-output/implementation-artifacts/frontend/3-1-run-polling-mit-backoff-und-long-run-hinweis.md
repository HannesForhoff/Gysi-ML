# Story 3.1: Run-Polling mit Backoff und Long-Run Hinweis

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Als ein Nutzer,
möchte ich nach Confirm den Run-Status bis terminal (`done|failed`) pollen,
damit ich Fortschritt und Abschluss zuverlässig sehe.

## Acceptance Criteria (BDD)

1. **Given** `run_id` ist bekannt (nach `CONFIRM_SUCCEEDED`)
   **When** der Run nicht terminal ist (`status` ist `queued` oder `running`)
   **Then** pollt die UI `GET /v1/sessions/{session_id}/runs/{run_id}` automatisch

2. **Given** Polling läuft
   **When** mehrere Poll-Zyklen vergehen
   **Then** wächst das Intervall exponentiell (Backoff: 1s → 2s → 4s → 8s, Cap bei 8s)

3. **Given** Polling dauert länger als ~2 Minuten
   **When** der Run immer noch nicht terminal ist
   **Then** erscheint im Chat oder StatusPanel ein Hinweis: „Run dauert länger – wir aktualisieren weiter."

4. **Given** der Run wird `done`
   **When** die nächste Poll-Response `status: "done"` liefert
   **Then** stoppt das Polling, `ui` wechselt zu `run_done`, `lastRun` und `artifacts` werden aktualisiert

5. **Given** der Run wird `failed`
   **When** die nächste Poll-Response `status: "failed"` liefert
   **Then** stoppt das Polling, `ui` wechselt zu `run_failed`, `lastError` enthält `error_message` falls vorhanden

6. **Given** das Backend ist nicht erreichbar während Polling
   **When** ein Netzwerkfehler auftritt
   **Then** wechselt `ui` zu `backend_unreachable`, Polling stoppt

7. **Given** Mock-Modus ist aktiv
   **When** ein Confirm erfolgreich war
   **Then** simuliert das Mock-Polling 2–3 Zyklen (`running` → `done`) mit realistischer Latenz

## Tasks / Subtasks

- [x] **T1** — API-Funktion `fetchRunStatus()` erstellen (AC: #1)
  - [x] T1.1: Datei `frontend/src/api/runApi.ts` anlegen
  - [x] T1.2: Funktion `fetchRunStatus(baseUrl, sessionId, runId)` implementieren → `RunStatusResponse`
  - [x] T1.3: Neuen Typ `RunStatusResponse` in `types.ts` definieren
  - [x] T1.4: Unit-Tests in `frontend/src/api/runApi.test.ts`

- [x] **T2** — Reducer-Actions für Polling-Ergebnisse (AC: #4, #5, #6)
  - [x] T2.1: Neue Actions `RUN_POLL_SUCCEEDED`, `RUN_POLL_FAILED`, `RUN_POLL_NETWORK_ERROR` in `chatReducer.ts`
  - [x] T2.2: `RUN_POLL_SUCCEEDED` mit `status: 'done'` → `ui: run_done`, `lastRun` + `artifacts` + optional `specSummary` aktualisieren
  - [x] T2.3: `RUN_POLL_SUCCEEDED` mit `status: 'failed'` → `ui: run_failed`, `lastError` setzen
  - [x] T2.4: `RUN_POLL_SUCCEEDED` mit `status: 'running'|'queued'` → `ui` bleibt `run_polling`
  - [x] T2.5: `RUN_POLL_NETWORK_ERROR` → `ui: backend_unreachable`, Polling implizit gestoppt
  - [x] T2.6: Neue Action `RUN_LONG_RUNNING` → setzt Flag `isLongRunning: true` im State
  - [x] T2.7: Unit-Tests in `frontend/src/state/chatReducer.polling.test.ts`

- [x] **T3** — Polling-Hook `useRunPolling` erstellen (AC: #1, #2, #3)
  - [x] T3.1: Datei `frontend/src/hooks/useRunPolling.ts` anlegen
  - [x] T3.2: Hook reagiert auf `ui.type === 'run_polling'` + `runId` + `sessionId`
  - [x] T3.3: Exponentieller Backoff (1s → 2s → 4s → 8s Cap) mit `setTimeout`
  - [x] T3.4: Long-Run-Timer: nach 120s dispatcht `RUN_LONG_RUNNING`
  - [x] T3.5: Cleanup bei Unmount oder State-Wechsel (keine Memory Leaks)
  - [x] T3.6: Mock-Modus: `fetchRunStatus` durch Mock-Implementierung ersetzen
  - [x] T3.7: Unit-Tests in `frontend/src/hooks/useRunPolling.test.ts`

- [x] **T4** — Mock-Polling-Support (AC: #7)
  - [x] T4.1: Mock-Funktion `fetchMockRunStatus(runId, callCount)` → gibt nach 2–3 Calls `done` zurück
  - [x] T4.2: Fixture `frontend/src/fixtures/run_status_done.json` anlegen (optional, kann inline sein)

- [x] **T5** — App.tsx Integration (AC: alle)
  - [x] T5.1: `useRunPolling(dispatch, state)` im App-Root einbinden
  - [x] T5.2: Nach `RUN_POLL_SUCCEEDED` (done): Assistant-Message erstellen und dem Chat hinzufügen (ähnlich wie `handleSend`)

- [x] **T6** — StatusPanel: Long-Run Hinweis (AC: #3)
  - [x] T6.1: `isLongRunning`-Prop an StatusPanel durchreichen
  - [x] T6.2: Hinweisblock rendern: „Run dauert länger – wir aktualisieren weiter."
  - [x] T6.3: CSS-Klasse `statusBlock--info` für den Hinweis

- [x] **T7** — Regressionstests (alle ACs)
  - [x] T7.1: Bestehende Tests ausführen → alle grün
  - [x] T7.2: Manuelle Smoke-Tests im Mock- und Real-Modus

## Dev Notes

### API Contract

**Endpoint:** `GET /v1/sessions/{session_id}/runs/{run_id}`

**Response-Format (aus PRD und UX-Spec):**

```json
{
  "status": "queued | running | done | failed",
  "metrics": { "rmse": 123.45, "r2": 0.89 },
  "artifacts": [
    {
      "artifact_id": "plot-1",
      "label": "Plot (Placeholder)",
      "media_type": "image/svg+xml",
      "href": "/v1/artifacts/plot-1"
    }
  ],
  "error_message": "optional Fehlertext bei failed"
}
```

**Terminal-Status:** `done` oder `failed` — kein weiteres Polling.
**Non-Terminal:** `queued` oder `running` — weiter pollen.

### Neuer Typ: `RunStatusResponse`

```typescript
// In types.ts hinzufügen:
export type RunStatus = 'queued' | 'running' | 'done' | 'failed'

export interface RunStatusResponse {
  status: RunStatus
  metrics?: Record<string, number | string>
  artifacts?: ArtifactRef[]
  error_message?: string
}
```

**ACHTUNG:** Das Backend-Feld `artifact_id` + `href` muss auf das Frontend-`ArtifactRef` gemappt werden (`id` + `url`). Die Mapping-Logik gehört in `runApi.ts`, nicht in den Reducer.

### Reducer-Änderungen

**Neue State-Felder:**

```typescript
// In ChatState hinzufügen:
isLongRunning: boolean  // default: false
```

**Neue Actions:**

```typescript
| { type: 'RUN_POLL_SUCCEEDED'; status: RunStatus; metrics?: Record<string, number | string>; artifacts?: ArtifactRef[]; errorMessage?: string }
| { type: 'RUN_POLL_NETWORK_ERROR'; errorMessage: string }
| { type: 'RUN_LONG_RUNNING' }
```

**Reducer-Logik (Kernpfade):**

- `RUN_POLL_SUCCEEDED` + `status === 'done'`:
  - `ui: { type: 'run_done' }`
  - `lastRun: { type: 'result', message: 'Run abgeschlossen', status: 'done', metrics, artifacts }`
  - `artifacts: response.artifacts ?? state.artifacts`
  - `runId: null` (Cleanup)
  - `isLongRunning: false`

- `RUN_POLL_SUCCEEDED` + `status === 'failed'`:
  - `ui: { type: 'run_failed' }`
  - `lastRun: { type: 'result', message: errorMessage ?? 'Run fehlgeschlagen', status: 'failed' }`
  - `lastError: errorMessage ?? 'Run fehlgeschlagen'`
  - `runId: null`
  - `isLongRunning: false`

- `RUN_POLL_SUCCEEDED` + `status === 'running'|'queued'`:
  - State bleibt unverändert (weiter pollen)

- `RUN_POLL_NETWORK_ERROR`:
  - `ui: { type: 'backend_unreachable' }`
  - `lastError: errorMessage`
  - `runId: null`
  - `isLongRunning: false`

- `RUN_LONG_RUNNING`:
  - Nur setzen wenn `ui.type === 'run_polling'` (Guard)
  - `isLongRunning: true`

### Polling-Hook: `useRunPolling`

```typescript
// Signatur:
export function useRunPolling(
  dispatch: Dispatch<ChatAction>,
  state: Pick<ChatState, 'ui' | 'runId' | 'sessionId' | 'transport'>
): void
```

**Backoff-Logik:**

- Initiales Intervall: 1000ms
- Nach jedem nicht-terminalen Poll: Intervall verdoppeln
- Cap: 8000ms
- Implementierung: `setTimeout` (nicht `setInterval`) — jeder Poll-Zyklus plant den nächsten

**Long-Run Timer:**

- Separater `setTimeout` (120_000ms) bei Start des Pollings
- Dispatcht `RUN_LONG_RUNNING` einmalig
- Wird bei Cleanup gecleant

**Cleanup:**

- `useEffect` Cleanup-Funktion cancelt laufende Timeouts und setzt `cancelled = true` Flag
- Verhindert Dispatches nach Unmount oder State-Wechsel

**Mock-Modus:**

- Wenn `state.transport.useMock` → verwende `fetchMockRunStatus` statt `fetchRunStatus`
- Mock: 1. Call → `{ status: 'running' }`, 2. Call → `{ status: 'running' }`, 3. Call → `{ status: 'done', metrics: {...}, artifacts: [...] }`
- Geht über einen internen Call-Counter

### Integration in App.tsx

- `useRunPolling(dispatch, state)` direkt unter `useHealthPolling` aufrufen
- Der Hook managed alles intern; App.tsx muss nur den Hook einbinden
- **WICHTIG:** Nach `RUN_POLL_SUCCEEDED` mit `done`/`failed` soll eine Result-Message im Chat erscheinen. Zwei Optionen:
  - **Option A (empfohlen):** Der Reducer fügt bei `RUN_POLL_SUCCEEDED` (terminal) eine AssistantMessage zu `messages` hinzu. Dafür muss die Action ein `assistantMessage: ChatMessage` Feld haben, das der Hook erstellt.
  - **Option B:** App.tsx lauscht auf State-Änderungen und fügt die Message ein — **vermeiden**, da Side-Effect-Logik in React-Komponenten fragil ist.
  - → **Entscheidung: Option A** — der Hook erstellt die ChatMessage und inkludiert sie in der Action.

### StatusPanel: Long-Run Hinweis

- Neuer Props-Typ: `isLongRunning: boolean`
- Rendering-Bedingung: `isLongRunning && ui.type === 'run_polling'`
- Text: „Run dauert länger – wir aktualisieren weiter."
- CSS-Klasse: `statusBlock--info` (blauer Akzent, analog zu `--error` und `--warning`)

### Bestehende Patterns die einzuhalten sind

| Pattern | Aus Story | Anwendung hier |
| --- | --- | --- |
| `fetch` mit `encodeURIComponent` für URL-Params | 1.2 / healthApi | `runApi.ts` muss `sessionId` und `runId` encoden |
| Transport-Switch (mock/real) | alle Stories | Hook prüft `state.transport.useMock` |
| Reducer bleibt pure (keine Side-Effects) | alle Stories | Kein `fetch` im Reducer |
| `vi.useFakeTimers` für Timer-Tests | useHealthPolling | Gleicher Ansatz für useRunPolling |
| CSS-Klassen-Konvention (`statusBlock--*`) | 1.4 | `statusBlock--info` für Long-Run |
| `sanitizeArtifactUrl` für Artefakt-URLs | StatusPanel | Wiederverwendbar für Artefakte aus Run-Response |
| `isRecord` / `toNonEmptyString` Helpers | realTransport | Wiederverwendbar in runApi Parsing |

### Vorherige Story Intelligence (2-3)

- **81 Tests grün** vor dieser Story (Baseline)
- **State Machine** ist stabil: `proposal_pending → sending_message → ...` funktioniert korrekt
- **CONFIRM_SUCCEEDED** setzt bereits `ui: run_polling` und `runId` — der Anknüpfpunkt für diese Story
- **Kein neuer Transport-Code** war nötig für 2-3, aber diese Story braucht definitiv neuen Transport (`runApi`)
- **`pendingProposalId`** wird bei CONFIRM_SUCCEEDED auf null gesetzt — keine Konflikte

### Risiken und Mitigationen

| Risiko | Mitigation |
| --- | --- |
| Timer-basierte Tests sind fragil | `vi.useFakeTimers` + explizite `advanceTimersByTimeAsync` Kontrolle |
| Polling stoppt nicht korrekt bei schnellem State-Wechsel | Striktes `cancelled`-Flag in useEffect Cleanup |
| Mock-Polling-Latenz blockiert Tests | `import.meta.env.MODE === 'test'` → 0ms Latenz (siehe mockTransport Pattern) |
| Backend-Response-Format weicht ab | Defensive Parsing in `runApi.ts` (wie `realTransport.ts`) |
| Memory Leak durch nicht-gecleante Timeouts | Alle Timeouts in Refs tracken und in Cleanup clearTimeout |

### Project Structure Notes

- Neue Dateien folgen dem bestehenden Pattern:
  - `src/api/runApi.ts` + `src/api/runApi.test.ts` (neben `healthApi.ts`)
  - `src/hooks/useRunPolling.ts` + `src/hooks/useRunPolling.test.ts` (neben `useHealthPolling.ts`)
  - `src/state/chatReducer.polling.test.ts` (neben anderen Reducer-Test-Dateien)
- Fixtures: optional `src/fixtures/run_status_done.json`
- Keine neuen Verzeichnisse nötig

### References

- [Source: _bmad-output/planning-artifacts/frontend/epics.md → Epic 3 / Story 3.1]
- [Source: _bmad-output/planning-artifacts/frontend/prd_frontend.md → FE7, FE13, Polling-Rules]
- [Source: _bmad-output/planning-artifacts/frontend/ux-spec.md → Section 5.5 Run-Polling, Section 7 State Machine]
- [Source: _bmad-output/planning-artifacts/frontend/ux-design-specification.md → Effortless Interactions, Critical Success Moments]
- [Source: _bmad-output/planning-artifacts/frontend/frontend_implementationsplan_gysi_ml.md → Section 7.3 Polling-Rules, M3]
- [Source: _bmad-output/implementation-artifacts/frontend/sprint-status.yaml → API Contract Decisions]
- [Source: frontend/src/state/chatReducer.ts → CONFIRM_SUCCEEDED, UiState]
- [Source: frontend/src/hooks/useHealthPolling.ts → Polling-Hook-Pattern]
- [Source: frontend/src/api/realTransport.ts → Defensive Parsing Pattern]
- [Source: frontend/src/types.ts → ArtifactRef, ResultResponse]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 via GitHub Copilot

### Debug Log References

- Mock-Modus Timer-Test: `advanceTimersByTimeAsync(1_001)` statt `(1_000)` nötig, da `setTimeout(resolve, 0)` im Mock-Path einen extra Tick braucht unter `vi.useFakeTimers()`.

### Completion Notes List

- T1: `fetchRunStatus` mit defensivem Parsing (Backend `artifact_id`/`href` → Frontend `id`/`url` Mapping in `runApi.ts`).
- T2: 3 neue Actions + `isLongRunning` State-Feld. Option A gewählt: Reducer inkludiert `assistantMessage` in den messages bei terminal status.
- T3: Hook mit exponentieller Backoff (1→2→4→8s Cap), `cancelled`-Flag Pattern, Long-Run Timer bei 120s.
- T4: Mock inline in Hook (kein separates Fixture-File nötig). 2× running → done nach 3. Call.
- T5: `useRunPolling(dispatch, state)` direkt unter `useHealthPolling` in App.tsx.
- T6: `isLongRunning` Prop + `statusBlock--info` CSS (blauer Akzent).
- T7: 122/122 Tests grün (81 Baseline + 41 neu). 0 Compile-Errors.

### File List

- `frontend/src/types.ts` — `RunStatus`, `RunStatusResponse` Typen hinzugefügt
- `frontend/src/api/runApi.ts` — **NEU** — `fetchRunStatus()` mit defensivem Parsing
- `frontend/src/api/runApi.test.ts` — **NEU** — 8 Unit-Tests
- `frontend/src/state/chatReducer.ts` — `isLongRunning`, 3 neue Actions, Reducer-Cases
- `frontend/src/state/chatReducer.polling.test.ts` — **NEU** — 22 Unit-Tests
- `frontend/src/hooks/useRunPolling.ts` — **NEU** — Polling-Hook mit Backoff + Mock
- `frontend/src/hooks/useRunPolling.test.ts` — **NEU** — 11 Unit-Tests
- `frontend/src/components/StatusPanel.tsx` — `isLongRunning` Prop + Long-Run Hinweis
- `frontend/src/App.tsx` — `useRunPolling` Integration + `isLongRunning` Prop
- `frontend/src/App.css` — `statusBlock--info` CSS-Klasse
