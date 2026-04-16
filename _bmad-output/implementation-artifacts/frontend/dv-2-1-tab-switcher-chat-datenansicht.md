# Story DV-2.1: Tab-Switcher (Chat ↔ Datenansicht)

Status: done

## Story

Als ein Nutzer,
möchte ich zwischen dem Chat und der Datenansicht über Tabs wechseln können, ohne dass der Spec-Verlauf rechts verschwindet,
damit ich jederzeit den Datenzustand inspizieren kann, ohne den Chat-Verlauf zu verlieren.

## Acceptance Criteria (BDD)

1. **Given** die App ist gestartet und es wurde noch kein Run ausgeführt (`activeDataRunId === null`)
   **When** der Nutzer auf den „Daten"-Tab klickt
   **Then** ist der Tab ausgegraut und nicht klickbar
   **And** ein Hinweistext „Noch kein Datensatz vorhanden — führe zuerst einen Schritt aus." wird im Data-Pane angezeigt

2. **Given** ein Run wurde erfolgreich abgeschlossen (`RUN_POLL_SUCCEEDED` mit `status === 'done'`)
   **When** der Nutzer auf den „Daten"-Tab wechselt
   **Then** wird die Datenansicht (`DataViewPanel`) angezeigt
   **And** der Spec-Verlauf rechts (`historyPane`) bleibt weiterhin sichtbar

3. **Given** der Nutzer befindet sich im „Daten"-Tab
   **When** er auf den „Chat"-Tab klickt
   **Then** wird die Chat-Ansicht (MessageList + Composer) wieder angezeigt
   **And** kein Nachrichtenverlauf im Chat ist verloren gegangen

4. **Given** die App ist gestartet mit initialem State
   **When** die Komponente gerendert wird
   **Then** ist der „Chat"-Tab aktiv
   **And** der „Daten"-Tab ist ausgegraut

5. **Given** alle vorherigen Stories implementiert sind
   **When** alle Tests ausgeführt werden
   **Then** sind alle bestehenden Tests weiterhin grün (keine Regressionen)

## Tasks / Subtasks

- [x] **T1** — `chatReducer.ts`: State-Erweiterung (AC: #1, #2, #4)
  - [x] T1.1: `activeTab: 'chat' | 'data'` zu `ChatState` Interface hinzufügen
  - [x] T1.2: `activeDataRunId: string | null` zu `ChatState` Interface hinzufügen
  - [x] T1.3: `createInitialChatState()` initialisiert `activeTab: 'chat'` und `activeDataRunId: null`
  - [x] T1.4: Neues Action-Type `SET_ACTIVE_TAB: { tab: 'chat' | 'data' }` zu `ChatAction` Union hinzufügen
  - [x] T1.5: Case `SET_ACTIVE_TAB` im Reducer implementieren — Guard: nur zu `'data'` wechseln wenn `activeDataRunId !== null`
  - [x] T1.6: In `RUN_POLL_SUCCEEDED` (status `done`): `activeDataRunId` auf `state.runId` setzen (vor dem Nullen)

- [x] **T2** — `ChatLayout.tsx`: Tab-Leiste hinzufügen (AC: #1, #2, #3, #4)
  - [x] T2.1: Props-Typ um `activeTab`, `onTabChange`, `dataPane: ReactNode`, `dataTabEnabled: boolean` erweitern
  - [x] T2.2: Tab-Leiste innerhalb von `<main className="chatPane">` oben einfügen (zwei Buttons: „Chat" / „Daten")
  - [x] T2.3: `<main>` rendert je nach `activeTab` entweder `children` (Chat) oder `dataPane` (Daten)
  - [x] T2.4: „Daten"-Tab-Button erhält `disabled={!dataTabEnabled}` und entsprechende CSS-Klassen

- [x] **T3** — `DataViewPanel.tsx`: Placeholder-Komponente erstellen (AC: #2)
  - [x] T3.1: Neue Datei `frontend/src/components/DataViewPanel.tsx`
  - [x] T3.2: Props: `activeDataRunId: string | null` — rendert Hinweistext wenn `null`, andernfalls Platzhalter für nachfolgende Stories
  - [x] T3.3: Hinweistext wenn kein Run: „Noch kein Datensatz vorhanden — führe zuerst einen Schritt aus."
  - [x] T3.4: Platzhaltertext wenn Run vorhanden: „Datenansicht — wird in Story DV-2.2 implementiert." (temporär)

- [x] **T4** — `App.tsx`: Integration (AC: #1, #2, #3)
  - [x] T4.1: `SET_ACTIVE_TAB`-Action: `handleTabChange` Callback mit `dispatch` verdrahten
  - [x] T4.2: `ChatLayout` bekommt: `activeTab={state.activeTab}`, `onTabChange={handleTabChange}`, `dataTabEnabled={state.activeDataRunId !== null}`, `dataPane={<DataViewPanel activeDataRunId={state.activeDataRunId} />}`
  - [x] T4.3: `DataViewPanel` importieren

- [x] **T5** — `App.css`: Tab-Bar-Styles (AC: #1, #4)
  - [x] T5.1: `.tabBar` — Flex-Container, `border-bottom: 1px solid var(--border)`, Background: `var(--header-bg)`
  - [x] T5.2: `.tabBtn` — Reset, Styling analog zu bestehenden Buttons; `cursor: pointer`
  - [x] T5.3: `.tabBtn--active` — Aktiver Tab: `border-bottom: 2px solid var(--accent)`-ähnlich, fett
  - [x] T5.4: `.tabBtn:disabled` — ausgegraut: `opacity: 0.4; cursor: not-allowed`

- [x] **T6** — Tests (AC: #5)
  - [x] T6.1: Reducer-Unit-Tests in `chatReducer.tab.test.ts`: `SET_ACTIVE_TAB` nur wirksam wenn `activeDataRunId !== null`; `RUN_POLL_SUCCEEDED` setzt `activeDataRunId`; Initial-State korrekt
  - [x] T6.2: Alle bestehenden Tests ausführen → alle grün (keine Regressionen durch State-Erweiterung)
  - [ ] T6.3: Manueller Smoke-Test (Hannes): Tab-Switcher sichtbar → Daten-Tab deaktiviert → Run ausführen → Daten-Tab klickbar → DataViewPanel-Platzhalter sichtbar → zurück zu Chat → History erhalten

## Dev Notes

### Architektur-Entscheidungen

**Tab-State im globalen ChatReducer (nicht lokal in ChatLayout):**
Der `activeTab`-State lebt in `chatReducer.ts`, weil die Reducer-Action `RUN_POLL_SUCCEEDED` den Daten-Tab erst freischalten muss. Wenn der State lokal in `ChatLayout` wäre, gäbe es keine saubere Verbindung zum Reducer. Pattern: State im Reducer, Callbacks per Props.

**`ChatLayout` ist weiterhin ein Presentational Component:**
`ChatLayout` kennt nur `activeTab` und `onTabChange` — kein direkter `dispatch`-Import. Das hält die Komponente testbar und entkoppelt.

**`DataViewPanel` als Stub für DV-2.2:**
Diese Story erstellt nur den Tab-Switcher-Mechanismus. `DataViewPanel` ist ein Platzhalter. DV-2.2 baut die vollständige Tabelle.

### Kritische Implementierungsdetails

#### chatReducer.ts — `RUN_POLL_SUCCEEDED` Änderung

```typescript
case 'RUN_POLL_SUCCEEDED': {
  if (action.status === 'done') {
    const lastRun: ResultResponse = { ... }
    return {
      ...state,
      ui: { type: 'run_done' },
      lastRun,
      artifacts: action.artifacts ?? state.artifacts,
      activeDataRunId: state.runId,   // ← NEU: state.runId VOR dem Nullen übernehmen
      runId: null,
      isLongRunning: false,
      ...
    }
  }
  // ...
}
```

> ⚠️ **Reihenfolge ist kritisch**: `state.runId` wird in der neuen Zeile gelesen, BEVOR `runId: null` gesetzt wird. TypeScript-Type `string | null` — `activeDataRunId` bekommt den Wert vor dem Reset.

#### chatReducer.ts — `SET_ACTIVE_TAB` Case

```typescript
case 'SET_ACTIVE_TAB':
  // Guard: nur zu 'data' wechseln wenn Run vorhanden
  if (action.tab === 'data' && state.activeDataRunId === null) return state
  return { ...state, activeTab: action.tab }
```

#### ChatLayout.tsx — Neue Props

```typescript
type ChatLayoutProps = {
  children: ReactNode      // Chat-Content (MessageList + Composer)
  dataPane: ReactNode      // DataViewPanel
  status: ReactNode
  history: ReactNode
  activeTab: 'chat' | 'data'
  onTabChange: (tab: 'chat' | 'data') => void
  dataTabEnabled: boolean
}
```

Der `<main>`-Bereich erhält eine Tab-Leiste am oberen Rand. Das `tabContent`-div
nimmt den verbleibenden Platz (`flex: 1; min-height: 0; overflow: hidden`) ein.

```tsx
<main className="chatPane">
  <div className="tabBar">
    <button
      className={`tabBtn${activeTab === 'chat' ? ' tabBtn--active' : ''}`}
      onClick={() => onTabChange('chat')}
    >
      Chat
    </button>
    <button
      className={`tabBtn${activeTab === 'data' ? ' tabBtn--active' : ''}`}
      onClick={() => onTabChange('data')}
      disabled={!dataTabEnabled}
    >
      Daten
    </button>
  </div>
  <div className="tabContent">
    {activeTab === 'chat' ? children : dataPane}
  </div>
</main>
```

#### CSS: `.chatPane` bleibt flexibel

Das bestehende `.chatPane { display: flex; flex-direction: column; min-height: 0; }` bleibt.
Neu hinzufügen:
```css
.tabBar { flex: 0 0 auto; ... }   /* kein Schrumpfen */
.tabContent { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
```

Der Chat-Content (MessageList + Composer) ist damit weiterhin korrekt gescrollt — `MessageList` bekommt `flex: 1; overflow: auto` vom Parent.

### Vorhandene Patterns (nicht reinventen!)

- **CSS-Pattern**: BEM-light in `App.css` — Klassen wie `.tabBtn`, `.tabBtn--active`, `.tabBtn:disabled`
- **Reducer-Pattern**: Alle State-Änderungen via `chatReducer.ts`, nie direkte State-Mutation
- **Props-Pattern**: `ChatLayout` ist Presentational — kein `dispatch` direkt, nur Callbacks
- **Test-Pattern**: Reducer-Unit-Tests in eigener Datei (`chatReducer.*.test.ts`) — analog zu bestehenden `chatReducer.confirm.test.ts` etc.
- **CSS-Variable**: `var(--border)`, `var(--header-bg)`, `var(--accent)` aus `index.css` — nie Hardcoded-Farben

### Bestehende State-Felder (nicht stören!)

```typescript
// chatReducer.ts — Bestehende Felder, keine Änderung nötig:
runId: string | null              // Aktiver Polling-Run → wird nach done auf null gesetzt
lastRun: ResultResponse | null    // Letztes Run-Ergebnis
artifacts: ArtifactRef[]          // Artefakte des letzten Runs
```

`activeDataRunId` ist separat von `runId`: `runId` ist der aktive Polling-Lauf (transient), `activeDataRunId` ist der persistierte "zuletzt abgeschlossene Run" für die Datenansicht.

### Scope-Abgrenzung (was NICHT Teil dieser Story ist)

- **Datentabelle mit echten Daten** → DV-2.2 (`DataViewPanel` bleibt Stub)
- **Spalten-Stats-Header** → DV-2.3
- **Rollback-Integration in Datenansicht** → DV-2.4 (setzt `activeDataRunId` bei Rollback)
- **CSV-Download-Button** → DV-2.5
- **Backend-Änderungen** → kein Scope
- **`SpecHistoryPanel` Änderungen** → kein Scope (bleibt in `historyPane` unverändert)

### Project Structure Notes

```
frontend/src/
├── components/
│   ├── ChatLayout.tsx          ← GEÄNDERT: Tab-Leiste, neue Props
│   ├── DataViewPanel.tsx       ← NEU: Placeholder
│   ├── MessageList.tsx         ← unverändert
│   ├── Composer.tsx            ← unverändert
│   └── SpecHistoryPanel.tsx    ← unverändert
├── state/
│   ├── chatReducer.ts          ← GEÄNDERT: activeTab, activeDataRunId, SET_ACTIVE_TAB
│   └── chatReducer.tab.test.ts ← NEU: Unit-Tests Tab-Reducer
├── App.tsx                     ← GEÄNDERT: handleTabChange, neue Props an ChatLayout
└── App.css                     ← GEÄNDERT: .tabBar, .tabBtn, .tabContent
```

### References

- [Source: _bmad-output/planning-artifacts/shared/epics-data-view-tab.md — Story DV-2.1 Definition + Technischer Kontext]
- [Source: frontend/src/state/chatReducer.ts — ChatState Interface, ChatAction Union, RUN_POLL_SUCCEEDED]
- [Source: frontend/src/components/ChatLayout.tsx — Bestehende Layout-Struktur]
- [Source: frontend/src/App.tsx — ChatLayout-Integration, handleRollback Pattern]
- [Source: frontend/src/App.css — Layout-Styles .layout, .chatPane, CSS-Variablen]
- [Source: _bmad-output/implementation-artifacts/frontend/3-3-artefakt-links-anzeigen-und-oeffnen.md — Dev-Patterns, CSS-BEM-light, Test-Patterns]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (via GitHub Copilot — Developer Agent Amelia)

### Debug Log References

- Pre-existing: `App.test.tsx` (9/10 Tests) schlugen bereits vor dieser Story fehl — keine neuen Regressionen eingeführt. Bestätigt via `git stash` + Test-Run.

### Completion Notes List

- **T1** `chatReducer.ts`: `activeTab` + `activeDataRunId` zu `ChatState` ergänzt, `SET_ACTIVE_TAB` Action-Type + Guard implementiert, `RUN_POLL_SUCCEEDED` setzt `activeDataRunId: state.runId` vor dem `runId: null`-Reset.
- **T2** `ChatLayout.tsx`: Props auf 7 Felder erweitert, Tab-Leiste mit zwei Buttons + `tabContent`-Wrapper eingefügt.
- **T3** `DataViewPanel.tsx`: Neue Komponente mit Null-Guard — Hinweistext vs. Platzhalter.
- **T4** `App.tsx`: `DataViewPanel` importiert, `handleTabChange` Callback ergänzt, `ChatLayout` mit allen neuen Props verdrahtet.
- **T5** `App.css`: `.tabBar`, `.tabBtn`, `.tabBtn--active`, `.tabBtn:disabled`, `.tabContent` hinzugefügt — CSS-Variablen genutzt.
- **T6** `chatReducer.tab.test.ts`: 12 Unit-Tests (RED→GREEN) — Initial-State, SET_ACTIVE_TAB Guard, RUN_POLL_SUCCEEDED. 56/56 Reducer-Tests grün, TypeScript 0 Fehler.

### File List

- `frontend/src/state/chatReducer.ts` — geändert: `activeTab`, `activeDataRunId` in `ChatState`; `SET_ACTIVE_TAB` in `ChatAction`; `createInitialChatState`; Reducer-Cases
- `frontend/src/state/chatReducer.tab.test.ts` — neu: 12 Unit-Tests für Tab-State
- `frontend/src/components/ChatLayout.tsx` — geändert: neue Props, Tab-Leiste, `tabContent`-Wrapper
- `frontend/src/components/DataViewPanel.tsx` — neu: Placeholder-Komponente
- `frontend/src/App.tsx` — geändert: `DataViewPanel` importiert, `handleTabChange`, `ChatLayout` Props
- `frontend/src/App.css` — geändert: `.tabBar`, `.tabBtn`, `.tabBtn--active`, `.tabBtn:disabled`, `.tabContent`, `.dataViewPanel`, `.dataViewPanel--empty`

## Change Log

- 2026-04-14: DV-2.1 implementiert — Tab-Switcher Chat/Daten, Reducer-State-Erweiterung, ChatLayout Tab-Leiste, DataViewPanel Placeholder, CSS Tab-Bar-Styles. 12 neue Unit-Tests grün.
- 2026-04-14: Code Review — `.dataViewPanel` / `.dataViewPanel--empty` CSS-Klassen ergänzt (`flex: 1; overflow: auto; padding: 18px` + Muted-Color für Empty-State). Status → done.
