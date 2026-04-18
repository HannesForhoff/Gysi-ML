# Story DV-2.4: Rollback-Integration — Datenansicht aktualisiert sich

Status: done

## Story

Als Nutzer,
möchte ich nach einem Rollback auf eine ältere Spec-Version die Datenansicht automatisch auf den Zustand dieser Version aktualisiert sehen,
damit ich visuell überprüfen kann, was dieser Rollback am Datensatz bewirkt hat — und bei einem Rollback auf eine Spec ohne Run die Rohdaten (Basis-CSV) als Fallback sehe.

## Acceptance Criteria

1. **Rollback mit vorhandenem Run** — Nach einem erfolgreichen Rollback auf eine Spec-Version mit mindestens einem Run wechselt `activeDataRunId` auf den letzten Run dieser Spec. Die Datentabelle lädt automatisch neu und zeigt den Datensatz-Zustand dieser Version.

2. **Rollback ohne vorhandenen Run** — Nach einem Rollback auf eine Spec-Version ohne Run wird `activeDataRunId` auf `null` gesetzt. `DataViewPanel` zeigt automatisch die Basis-CSV (Rohdaten) — kein manuelles Refresh, keine Fehlermeldung.

3. **Tab-unabhängige Aktualisierung** — Ist der Nutzer beim Rollback im Chat-Tab, zeigt der Data-Tab beim nächsten Öffnen bereits die korrekte Version (keine veralteten Daten).

4. **Backend: `last_run_id` im Spec-Baum** — `GET /v1/sessions/{session_id}/spec/tree` liefert pro `VersionNode` das Feld `last_run_id: string | null`, das die `run_id` des zuletzt abgeschlossenen Runs für diese Spec enthält (oder `null` wenn noch kein Run existiert).

5. **Kein Regressions-Bruch** — Die Tabelle setzt sich korrekt zurück (kein Mixing alter und neuer Zeilen). Das Infinite-Scroll-Reset-Verhalten bei `activeDataRunId`-Wechsel bleibt unverändert.

## Tasks / Subtasks

- [x] **Task 1: Backend — `last_run_id` in `VersionNodeResponse` ergänzen** (AC: #4)
  - [x] In `backend/src/gysi_ml/api/schemas.py`: `VersionNodeResponse` um `last_run_id: Optional[str] = None` erweitern
  - [x] In `backend/src/gysi_ml/api/routes/specs.py`: `get_spec_tree()` — `last_run` bereits geladen → `last_run["run_id"]` als `last_run_id` übergeben

- [x] **Task 2: Frontend — `VersionNode` Typ ergänzen** (AC: #4)
  - [x] In `frontend/src/types.ts`: `VersionNode` um `last_run_id: string | null` erweitern
  - [x] In `frontend/src/api/healthApi.ts`: `parseVersionNode()` — `last_run_id` aus Backend-Response parsen

- [x] **Task 3: Frontend — `ROLLBACK_SUCCEEDED` Action erweitern** (AC: #1, #2, #3)
  - [x] In `frontend/src/state/chatReducer.ts`: Action-Typ `ROLLBACK_SUCCEEDED` um `activeDataRunId: string | null` erweitern
  - [x] In `frontend/src/state/chatReducer.ts`: Reducer-Handler für `ROLLBACK_SUCCEEDED` — `activeDataRunId: action.activeDataRunId` setzen

- [x] **Task 4: Frontend — `handleRollback` in App.tsx ergänzen** (AC: #1, #2, #3)
  - [x] Nach Erhalt von `newTree`: die Ziel-Spec (`targetSpecId`) in `newTree.versions` suchen und deren `last_run_id` extrahieren
  - [x] `activeDataRunId` = `last_run_id` der Ziel-Spec (oder `null` wenn kein Run)
  - [x] `dispatch({ type: 'ROLLBACK_SUCCEEDED', ..., activeDataRunId })` — neues Pflichtfeld befüllt

- [x] **Task 5: Tests** (AC: #1, #2, #3, #5)
  - [x] Backend-Test: `GET /spec/tree` liefert `last_run_id` für Specs mit Run; `null` für Specs ohne Run
  - [x] Frontend-Unit-Test (chatReducer): `ROLLBACK_SUCCEEDED` setzt `activeDataRunId` korrekt

## Dev Notes

### Zusammenfassung der Änderung

Dieses Feature schließt die Lücke zwischen Rollback und Datenansicht. Aktuell aktualisiert `ROLLBACK_SUCCEEDED` den `activeDataRunId` nicht — das ist der einzige fehlende Link. Die gesamte Rendering-Logik (Datennachladen, Reset, Basis-CSV-Fallback) ist bereits vollständig in `DataViewPanel` implementiert.

### Wichtige Vorab-Information: Basis-CSV ohne Run (bereits implementiert)

Seit der Implementierung von DV-2-2 zeigt `DataViewPanel` die Basis-CSV (Rohdaten des Bike-Datensatzes) wenn `activeDataRunId === null`. Das ist kein Error-State, sondern ein vollwertiger View.

- `fetchRawData()` wird aufgerufen wenn `capturedRunId === null`
- Endpunkt: `GET /v1/sessions/{session_id}/raw-data`
- **Konsequenz für DV-2-4**: Rollback auf eine Spec ohne Run → `activeDataRunId = null` → Basis-CSV wird angezeigt. Der im ursprünglichen Epic beschriebene Hinweis „Keine Daten für diese Version — führe die Spec erneut aus" ist damit **obsolet und soll nicht implementiert werden**.

### Zu ändernde Dateien (alle Änderungen sind additiv/minimal)

#### Backend

**`backend/src/gysi_ml/api/schemas.py`**
- Klasse `VersionNodeResponse` — neues optionales Feld `last_run_id: Optional[str] = None`
- Import: `Optional` ist bereits importiert (`from typing import Optional`)

**`backend/src/gysi_ml/api/routes/specs.py`** (Zeile ~88)
- In `get_spec_tree()`, beim Aufbau der `nodes`-Liste:
  - `last_run["run_id"]` ist bereits verfügbar (Variable `last_run`)
  - `last_run_id=last_run["run_id"] if last_run else None` dem `VersionNodeResponse(...)`-Aufruf hinzufügen

#### Frontend

**`frontend/src/types.ts`**
- Interface `VersionNode` — neues Feld `last_run_id: string | null`

**`frontend/src/api/healthApi.ts`** (Funktion `parseVersionNode`)
- Return-Objekt um `last_run_id: typeof item.last_run_id === 'string' ? item.last_run_id : null` ergänzen

**`frontend/src/state/chatReducer.ts`**
- Action-Typ `ROLLBACK_SUCCEEDED` — neues Feld `activeDataRunId: string | null`
- Reducer-Case `ROLLBACK_SUCCEEDED` — `activeDataRunId: action.activeDataRunId` hinzufügen

**`frontend/src/App.tsx`** (Funktion `handleRollback`)
- Nach `const [newSummary, newTree] = await Promise.all([...])`:
  ```typescript
  const targetNode = newTree?.versions.find(v => v.spec_id === targetSpecId) ?? null
  const newActiveDataRunId = targetNode?.last_run_id ?? null
  ```
- `dispatch({ type: 'ROLLBACK_SUCCEEDED', ..., activeDataRunId: newActiveDataRunId })`

### Bestehende Funktionalität die NICHT angerührt werden darf

- `DataViewPanel.tsx` — keinerlei Änderungen. Der Reset-Mechanismus bei `activeDataRunId`-Wechsel (via `useEffect`) funktioniert bereits korrekt.
- `currentRunRef`-Tracking (stale-response prevention) — funktioniert bereits für `null` via `refKey = capturedRunId ?? '__raw__'`
- `SpecHistoryPanel.tsx`, `ChatLayout.tsx` — keine Änderungen
- Bestehende Rollback-API-Aufrufe (`performRollback`, `fetchSpecSummary`, `fetchSpecTree`) — unverändert

### Datenfluss nach Rollback (vollständig)

```
User klickt Rollback
  → App.tsx: handleRollback(targetSpecId)
  → performRollback() → POST /rollback → { ok: true, newVersion }
  → fetchSpecSummary() + fetchSpecTree() parallel
  → newTree.versions.find(v => v.spec_id === targetSpecId)
  → targetNode.last_run_id (string | null)
  → dispatch ROLLBACK_SUCCEEDED { ..., activeDataRunId: targetNode.last_run_id ?? null }
  → chatReducer: state.activeDataRunId = action.activeDataRunId
  → DataViewPanel useEffect reagiert auf activeDataRunId-Änderung
  → activeDataRunId !== null: fetchRunData(runId)  → historischer Snapshot
  → activeDataRunId === null: fetchRawData()        → Basis-CSV
```

### Typ-Konsistenz: `VersionNode.last_run_id` vs. `run_id`

- `VersionNode.last_run_id` ist der zuletzt gespeicherte `run_id` zu dieser Spec (letzter Eintrag in `runs_by_spec[spec_id]`)
- Das entspricht exakt dem, was `activeDataRunId` erwartet — kein Mapping nötig
- Das Backend liefert `runs_by_spec.get(spec["spec_id"], [])[-1]["run_id"]`; diese Liste ist bereits nach Erstellungszeit sortiert (Einfügereihenfolge in der DB)

### Testdaten / Testszenarien

**Backend-Test:** `tests/api/test_specs.py` (oder vorhandene Test-Suite für `/spec/tree`)
- Session mit 1 Spec + 1 Run → `last_run_id` in Node vorhanden
- Session mit 1 Spec + 0 Runs → `last_run_id: null`
- Session mit 2 Specs, Spec-1 hat 2 Runs → `last_run_id` = Run2-ID von Spec-1

**Frontend-Test:** `tests/` oder `src/**/__tests__/`
- Dispatch `ROLLBACK_SUCCEEDED` mit `activeDataRunId: "run-123"` → State enthält `activeDataRunId: "run-123"`
- Dispatch `ROLLBACK_SUCCEEDED` mit `activeDataRunId: null` → State enthält `activeDataRunId: null`

### Scope-Abgrenzung (nicht in dieser Story)

- DV-2-4 betrifft ausschließlich den Rollback-Flow
- Die Basis-CSV-Anzeige (`activeDataRunId === null`) ist bereits vollständig funktionsfähig seit DV-2-2 (nicht nochmal implementieren)
- DV-2-5 (CSV Download) und DV-1-3 (CSV-Endpunkt) sind separate Stories
- Toast/Notification nach Rollback ist nicht Teil dieser Story

### Project Structure Notes

- Backend-Paket: `backend/src/gysi_ml/`
- API-Schemas: `backend/src/gysi_ml/api/schemas.py`
- API-Routes: `backend/src/gysi_ml/api/routes/specs.py`
- Frontend-Quellen: `frontend/src/`
- State-Management: `frontend/src/state/chatReducer.ts`
- API-Layer: `frontend/src/api/healthApi.ts`, `frontend/src/api/dataApi.ts`
- Hauptkomponente: `frontend/src/App.tsx`

### References

- Epic-Definition: [_bmad-output/planning-artifacts/shared/epics-data-view-tab.md](_bmad-output/planning-artifacts/shared/epics-data-view-tab.md) — Story DV-2.4
- Backend Schema: [backend/src/gysi_ml/api/schemas.py](backend/src/gysi_ml/api/schemas.py) — `VersionNodeResponse`, `VersionTreeResponse`
- Backend Route: [backend/src/gysi_ml/api/routes/specs.py](backend/src/gysi_ml/api/routes/specs.py) — `get_spec_tree()`
- Frontend State: [frontend/src/state/chatReducer.ts](frontend/src/state/chatReducer.ts) — `ROLLBACK_SUCCEEDED`, `ChatState.activeDataRunId`
- Frontend App: [frontend/src/App.tsx](frontend/src/App.tsx) — `handleRollback()`
- Frontend Typen: [frontend/src/types.ts](frontend/src/types.ts) — `VersionNode`
- Frontend API: [frontend/src/api/healthApi.ts](frontend/src/api/healthApi.ts) — `parseVersionNode()`, `performRollback()`
- Data View: [frontend/src/components/DataViewPanel.tsx](frontend/src/components/DataViewPanel.tsx) — Reset-Logik, Basis-CSV-Fallback

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

(keine Blocker)

### Completion Notes List

- Alle 5 Tasks implementiert. Änderungen sind additiv/minimal wie in Dev Notes beschrieben.
- Zweite (toter Code) `VersionNodeResponse`-Stelle in `specs.py` ebenfalls mit `last_run_id` versorgt.
- 4 pre-existing Backend-Testfehler (EBM, Messages API, SnapshotService) — nicht durch diese Story verursacht.
- 11 pre-existing Frontend-Testfehler (App.test.tsx, chatReducer.tab.test.ts) — identisch vor und nach den Änderungen.
- **Code Review Fixes (2026-04-18):**
  - H1 behoben: Dead-Code-Block nach `return SpecVersionResponse(**row)` in `specs.py` entfernt (exakte Duplik der `get_spec_tree`-Logik, nie ausgeführt).
  - M1 behoben: `handleRollback` in `App.tsx` verwendet jetzt `treeForLookup = newTree ?? state.specHistory` — kein stiller `null`-Fallback bei `fetchSpecTree`-Fehler.
  - M2 behoben: `chatReducer.rollback.test.ts` um 5 Unit-Tests für `resolveActiveDataRunId`-Algorithmus (handleRollback-Logik) erweitert.

### File List

- `backend/src/gysi_ml/api/schemas.py` — `VersionNodeResponse.last_run_id` ergänzt
- `backend/src/gysi_ml/api/routes/specs.py` — `last_run_id` in ersten `VersionNodeResponse`-Aufruf eingebaut; Dead-Code-Block entfernt (CR-Fix H1)
- `backend/tests/integration/test_spec_tree.py` — 3 neue Tests für `last_run_id`
- `frontend/src/types.ts` — `VersionNode.last_run_id: string | null`
- `frontend/src/api/healthApi.ts` — `parseVersionNode` parst `last_run_id`
- `frontend/src/state/chatReducer.ts` — `ROLLBACK_SUCCEEDED` Action + Reducer um `activeDataRunId` erweitert
- `frontend/src/App.tsx` — `handleRollback` extrahiert `last_run_id` via `treeForLookup = newTree ?? state.specHistory` (CR-Fix M1)
- `frontend/src/state/chatReducer.rollback.test.ts` — 4 Reducer-Tests + 5 neue `resolveActiveDataRunId`-Tests (CR-Fix M2)
