# Story 3.2: Result-Message (Status/Metriken) rendern

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Als ein Nutzer,
möchte ich bei Run-Abschluss (`done` oder `failed`) eine strukturierte Ergebniszusammenfassung im Chat sehen,
damit ich Status und Metriken auf einen Blick erfassen kann, ohne den reinen Text parsen zu müssen.

## Acceptance Criteria (BDD)

1. **Given** der Run ist `done` und die Response enthält `metrics`
   **When** die Result-Message im Chat gerendert wird
   **Then** sehe ich eine `ResultCard` mit Status-Label „Ergebnis" und Metriken als Key/Value-Liste

2. **Given** der Run ist `done` aber `metrics` fehlt (leer oder `null`)
   **When** die Result-Message gerendert wird
   **Then** zeigt die `ResultCard` nur den Status „Ergebnis" und die Text-Message, kein leerer Metriken-Block

3. **Given** der Run ist `failed`
   **When** die Result-Message gerendert wird
   **Then** sehe ich eine `ResultCard` mit Status-Label „Fehlgeschlagen" und `error_message` (falls vorhanden)

4. **Given** die Response enthält `artifacts[]`
   **When** die Result-Message gerendert wird
   **Then** werden die Artefakte als kompakte Liste (Label + Media-Type) in der `ResultCard` angezeigt
   **Note:** Artefakt-Links (Klick → neuer Tab) sind Scope von Story 3.3 — hier nur Textanzeige

5. **Given** ein `type: "result"` existiert als `response` auf einer `ChatMessage`
   **When** `MessageList` die Message rendert
   **Then** wird `ResultCard` statt der generischen `messageContent`-Div gerendered

6. **Given** der bestehende Mock-Modus liefert eine Result-Message
   **When** Polling `done` erreicht
   **Then** wird die `ResultCard` korrekt mit Mock-Daten aus `useRunPolling.ts` gerendert

7. **Given** das Backend sendet `status: "completed"` (statt `"done"`)
   **When** `runApi.ts` die Response parst
   **Then** wird `"completed"` korrekt auf `"done"` gemappt (Backward-Kompatibilität)

## Tasks / Subtasks

- [x] **T1** — Backend-Status-Mapping in `runApi.ts` fixen (AC: #7)
  - [x] T1.1: In `parseRunStatus()` den Wert `"completed"` auf `"done"` mappen — das Backend persistiert `"completed"`, die Frontend-Types erwarten `"done"`
  - [x] T1.2: Test in `runApi.test.ts` hinzufügen: `"completed"` → `"done"` Mapping verifizieren
  - [x] T1.3: Bestehende Tests prüfen — keine Regression

- [x] **T2** — `ResultCard`-Komponente erstellen (AC: #1, #2, #3, #4)
  - [x] T2.1: Datei `frontend/src/components/ResultCard.tsx` anlegen
  - [x] T2.2: Props-Interface: `{ result: ResultResponse }` — keine eigenen Actions/Callbacks (read-only)
  - [x] T2.3: Status-Label rendern: `done` → „Ergebnis", `failed` → „Fehlgeschlagen"
  - [x] T2.4: `result.message` als Textblock rendern (falls vorhanden)
  - [x] T2.5: `result.metrics` als Key/Value-Liste rendern (falls vorhanden, nicht leer)
  - [x] T2.6: `result.artifacts` als kompakte Textliste rendern (Label + Media-Type) — nur Anzeige, kein Link (Scope Story 3.3)
  - [x] T2.7: Status-Visualisierung über CSS-Klasse: `.resultCard--done` (Erfolg) vs `.resultCard--failed` (Fehler)

- [x] **T3** — CSS für `ResultCard` in `App.css` hinzufügen (AC: #1, #3)
  - [x] T3.1: Klassen `.resultCard`, `.resultCard--done`, `.resultCard--failed`, `.resultLabel`, `.resultMessage`, `.resultMetrics`, `.resultMetricsRow`, `.resultArtifacts` definieren
  - [x] T3.2: Pattern von `.proposalCard` folgen (Flexbox, Gap, Border-Radius, Mono-Font für Labels)
  - [x] T3.3: `.resultCard--done` → Erfolg-Akzent (z.B. grünlicher Border), `.resultCard--failed` → Fehler-Akzent (z.B. rötlicher Border)

- [x] **T4** — `MessageList.tsx` erweitern (AC: #5)
  - [x] T4.1: Import `ResultCard` hinzufügen
  - [x] T4.2: Im Render-Switch `message.response?.type === 'result'` → `<ResultCard result={message.response} />` rendern
  - [x] T4.3: Reihenfolge: `proposal` → `result` → Default (`messageContent`)

- [x] **T5** — Unit-Tests für `ResultCard` (AC: #1, #2, #3, #4)
  - [x] T5.1: Datei `frontend/src/components/ResultCard.test.tsx` anlegen
  - [x] T5.2: Test: Rendert Status-Label „Ergebnis" bei `status: 'done'`
  - [x] T5.3: Test: Rendert Status-Label „Fehlgeschlagen" bei `status: 'failed'`
  - [x] T5.4: Test: Rendert Metriken als Key/Value (z.B. `rmse: 123.45`, `r2: 0.89`)
  - [x] T5.5: Test: Rendert keinen Metriken-Block wenn `metrics` fehlt
  - [x] T5.6: Test: Rendert Artefakte-Liste (Label + Media-Type)
  - [x] T5.7: Test: Rendert keine Artefakte-Liste wenn `artifacts` fehlt
  - [x] T5.8: Test: Rendert Message-Text wenn vorhanden

- [x] **T6** — Integration in `MessageList` testen (AC: #5, #6)
  - [x] T6.1: In `MessageList.test.tsx` (oder neu) Test: Result-Message wird als `ResultCard` gerendert, nicht als Plain-Text
  - [x] T6.2: Test: Proposal-Messages werden weiterhin als `ProposalCard` gerendert (Regression)

- [x] **T7** — Regressionstests (alle ACs)
  - [x] T7.1: Alle bestehenden Tests ausführen → alle grün
  - [ ] T7.2: Manueller Smoke-Test: Mock-Modus → Nachricht senden → Confirm → Polling → ResultCard wird gerendert

## Dev Notes

### Backend-API-Contract (kritisch!)

**Endpoint:** `GET /v1/sessions/{session_id}/runs/{run_id}`

**Response (Backend, Pydantic `RunDetailResponse`):**

```json
{
  "run_id": "uuid",
  "status": "completed",
  "started_at": "ISO8601",
  "finished_at": "ISO8601",
  "spec_version": "v1",
  "spec": { "steps": [...] },
  "step_results": [{ "step_type": "split", "metadata": {...} }],
  "metrics": { "rmse": 12.345, "mae": 8.901, "r2": 0.8723 },
  "artifacts": [{ "artifact_id": "uuid", "type": "feature_importance", "created_at": "ISO8601" }],
  "error_message": null
}
```

**⚠️ STATUS-MAPPING:** Das Backend persistiert `"completed"` (nicht `"done"`). Der Frontend-Typ `RunStatus` kennt nur `'queued' | 'running' | 'done' | 'failed'`. Die Mapping-Logik `"completed"` → `"done"` **muss** in `runApi.ts > parseRunStatus()` hinzugefügt werden.

[Source: backend/src/gysi_ml/executor/executor.py L254]
[Source: backend/src/gysi_ml/api/schemas.py L74-84]

### Artifact-Mapping (bereits implementiert)

`runApi.ts > parseArtifacts()` mappt bereits korrekt:

- Backend `artifact_id` → Frontend `id`
- Backend `type` → Frontend `label` (Fallback)
- Backend `href` → Frontend `url` (Fallback auf `url`)

**Info für Story 3.3:** Artifact-Links brauchen eine vollqualifizierte URL. Aktuell gibt das Backend relative Pfade oder nur IDs. Die URL-Konstruktion (z.B. `${baseUrl}/v1/artifacts/${artifact_id}`) wird in Story 3.3 gelöst.

[Source: frontend/src/api/runApi.ts L53-66]

### Vorhandene Types (kein Änderungsbedarf)

```typescript
// frontend/src/types.ts — bereits definiert:
export interface ResultResponse {
  type: 'result'
  message: string
  status: 'done' | 'failed'
  metrics?: Record<string, number | string>
  artifacts?: ArtifactRef[]
  spec_summary?: SpecSummary
}
```

### Polling → ResultCard Datenpfad

1. `useRunPolling.ts` pollt bis terminal
2. Bei `done`/`failed`: `createResultMessage(result)` erstellt `ChatMessage` mit `response: ResultResponse`
3. `RUN_POLL_SUCCEEDED`-Action fügt Message zu `state.messages` hinzu
4. `MessageList.tsx` rendert — **hier muss der Switch für `type: 'result'` → `<ResultCard>` ergänzt werden** (aktuell fällt Result auf Plain-Text-`messageContent` zurück)

[Source: frontend/src/hooks/useRunPolling.ts L108-137]
[Source: frontend/src/state/chatReducer.ts L197-243]
[Source: frontend/src/components/MessageList.tsx L37-47]

### Komponenten-Pattern (ProposalCard als Vorlage)

`ResultCard` soll dem gleichen Pattern wie `ProposalCard` folgen:

- Reiner Presentational-Component (keine Side-Effects)
- Props: `{ result: ResultResponse }` (read-only, keine Callbacks)
- CSS-Klassen nach BEM-light: `.resultCard`, `.resultCard--done`, `.resultCard--failed`
- CSS-Variablen `var(--border)`, `var(--bg)`, `var(--mono)` aus bestehender App.css nutzen

[Source: frontend/src/components/ProposalCard.tsx]
[Source: frontend/src/App.css L266-330]

### Test-Pattern (ProposalCard.test.tsx als Vorlage)

- `@testing-library/react` + `vitest`
- `render()` + `screen.getByText()` / `screen.queryByText()` Pattern
- Fixture-Daten als const definieren, nicht importieren

[Source: frontend/src/components/ProposalCard.test.tsx]

### Mock-Fixture (vorhanden, nicht ändern)

```json
// frontend/src/fixtures/result.json
{
  "type": "result",
  "message": "Ergebnis (Mock): Run abgeschlossen.",
  "status": "done",
  "metrics": { "rmse": 123.45, "r2": 0.89 },
  "artifacts": [
    { "id": "plot-1", "label": "Plot (Placeholder)", "url": "/favicon.svg", "media_type": "image/svg+xml" },
    { "id": "metrics-1", "label": "Metrics (JSON)", "url": "/mock/metrics.json", "media_type": "application/json" }
  ]
}
```

### Scope-Abgrenzung (was NICHT Teil dieser Story ist)

- **Artefakt-Links klickbar machen** → Story 3.3
- **Artefakt-Download/Preview** → Story 3.3
- **Neue Types definieren** → nicht nötig, `ResultResponse` existiert bereits
- **Reducer oder Polling-Hook ändern** → nicht nötig, Daten kommen bereits korrekt an
- **StatusPanel-Änderungen** → nicht nötig, `lastRun` wird schon von Story 3.1 im Panel dargestellt

### Project Structure Notes

- Alignment mit bestehender Projektstruktur bestätigt
- Neue Dateien: `ResultCard.tsx`, `ResultCard.test.tsx` — unter `frontend/src/components/`
- CSS ergänzt in bestehendem `App.css` (kein separates CSS-Modul)
- Keine neuen Dependencies nötig

### References

- [Source: _bmad-output/planning-artifacts/frontend/epics.md — Story 3.2 Definition]
- [Source: backend/src/gysi_ml/api/schemas.py — RunDetailResponse, ArtifactSummary]
- [Source: backend/src/gysi_ml/api/routes/runs.py — GET /runs/{run_id} Endpoint]
- [Source: backend/src/gysi_ml/executor/executor.py L254 — status="completed"]
- [Source: frontend/src/types.ts — ResultResponse, RunStatusResponse, ArtifactRef]
- [Source: frontend/src/api/runApi.ts — parseRunStatus, parseArtifacts]
- [Source: frontend/src/hooks/useRunPolling.ts — createResultMessage]
- [Source: frontend/src/state/chatReducer.ts — RUN_POLL_SUCCEEDED Handling]
- [Source: frontend/src/components/MessageList.tsx — Render-Switch (aktuell nur Proposal)]
- [Source: frontend/src/components/ProposalCard.tsx — Pattern-Vorlage]
- [Source: frontend/src/App.css L266-330 — ProposalCard CSS-Pattern]
- [Source: frontend/src/fixtures/result.json — Mock-Daten]
- [Source: _bmad-output/implementation-artifacts/frontend/3-1-run-polling-mit-backoff-und-long-run-hinweis.md — Vorgänger-Story]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (GitHub Copilot)

### Debug Log References

Keine Debug-Probleme aufgetreten.

### Completion Notes List

- T1: `STATUS_ALIASES`-Map in `parseRunStatus()` — erweiterbar für zukünftige Backend-Status-Aliase
- T2: `ResultCard` als reiner Presentational-Component (kein State, keine Side-Effects)
- T3: CSS folgt ProposalCard-Pattern, `--done` grün (#38a169), `--failed` rot (#e53e3e)
- T4: Render-Switch-Reihenfolge: `proposal` → `result` → Default
- T5: 12 Unit-Tests decken alle ACs ab (Status-Labels, Metriken, Artefakte, CSS-Klassen)
- T6: 2 Integration-Tests (ResultCard-Rendering + ProposalCard-Regression)
- T7.1: Volle Suite 137/137 Tests grün
- T7.2: Manueller Smoke-Test ausstehend (durch Hannes)

### File List

- `frontend/src/api/runApi.ts` — STATUS_ALIASES + parseRunStatus erweitert
- `frontend/src/api/runApi.test.ts` — +1 Test (completed→done)
- `frontend/src/components/ResultCard.tsx` — NEU
- `frontend/src/components/ResultCard.test.tsx` — NEU (12 Tests)
- `frontend/src/components/MessageList.tsx` — ResultCard-Import + Render-Switch
- `frontend/src/components/MessageList.test.tsx` — +2 Integration-Tests
- `frontend/src/App.css` — ResultCard CSS-Klassen
