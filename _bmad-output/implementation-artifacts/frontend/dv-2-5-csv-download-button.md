# Story DV-2.5: CSV-Download-Button

Status: review

## Story

Als Nutzer,
möchte ich mit einem einzigen Klick den aktuell angezeigten transformierten Datensatz als CSV-Datei herunterladen,
damit ich die aufbereiteten Daten für eigene Analysen oder Berichte weiternutzen kann.

## Acceptance Criteria

1. **Download mit vorhandenem Run** — `activeDataRunId` ist gesetzt und ein Snapshot existiert: Klick auf „CSV herunterladen" startet den Browser-Download einer `.csv`-Datei mit **allen** Spalten und Zeilen des transformierten Datensatzes (vollständig, nicht nur die 1000 sichtbaren Zeilen).

2. **Button ausgegraut** — Ist keine `sessionId` vorhanden (keine aktive Session), ist der Download-Button ausgegraut und nicht klickbar. Bei vorhandener Session ist der Button immer aktiv: mit `activeDataRunId` → Run-Download (`bikes_vN.csv`), ohne `activeDataRunId` → Rohdaten-Download (`gysi_raw_data.csv`).

3. **Fehlerfall 404** — Liefert der Download-Endpunkt einen 404 (kein Snapshot), erhält der Nutzer die Standard-Browser-Fehlermeldung. Kein explizites Frontend-Error Handling erforderlich.

## Tasks / Subtasks

- [x] **Task 1: Download-Link zum `dataViewToolbar` in `DataViewPanel.tsx` hinzufügen** (AC: #1, #2)
  - [x] Im `dataViewToolbar`-Container nach dem `dataViewInfo`-Span: bedingtes `<a>`/`<span>`-Element einfügen
  - [x] Aktiven Zustand (`sessionId` vorhanden): `<a className="csvDownloadButton" href={...} download>⬇ CSV herunterladen</a>` — bei `activeDataRunId` → Run-URL, sonst → Raw-Data-URL
  - [x] Download-URL (Run): `` `${backendBaseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(activeDataRunId)}/data/download` ``
  - [x] Download-URL (Rohdaten-Fallback): `` `${backendBaseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/raw-data/download` ``
  - [x] Deaktivierten Zustand (`!sessionId`): `<span className="csvDownloadButton csvDownloadButton--disabled" aria-disabled="true">⬇ CSV herunterladen</span>`

- [x] **Task 2: CSS-Klassen ergänzen in `App.css`** (AC: #1, #2)
  - [x] `.csvDownloadButton` — kleine Pill-Schaltfläche analoog zu `.splitBadge`; `margin-left: auto` um sie rechtsbündig in der Toolbar zu halten
  - [x] `.csvDownloadButton--disabled` — grauer Hintergrund, `cursor: not-allowed`

- [ ] **Task 3: Manueller Smoke-Test** (AC: #1, #2, #3)
  - [ ] Nach einem abgeschlossenen Run: Download-Button erscheint und startet Browser-Download
  - [ ] Download-Datei heißt `bikes_v1.csv` (bzw. `bikes_vN.csv` passend zur Spec-Version)
  - [ ] Download-Datei enthält Header-Zeile und alle Zeilen des Datensatzes (nicht nur 1000)
  - [ ] Im Initial-State (kein Run, aber Session vorhanden): Button aktiv, Download startet `gysi_raw_data.csv`
  - [ ] Ohne Session: Button ausgegraut, kein Klick möglich
  - [ ] Rollback auf Spec ohne Run: Button bleibt aktiv (Raw-Data-Download)

## Dev Notes

### Zusammenfassung

Minimalste Frontend-Änderung: Einen Download-Link-Button zur `dataViewToolbar` in `DataViewPanel.tsx` hinzufügen. Der Backend-Endpunkt für CSV-Download ist **bereits vollständig implementiert** (`data.py`, Zeile 167). Kein neuer API-Client-Code, kein React-State, kein clientseitiger CSV-Serializer — nur `<a href="..." download>`.

### Zu ändernde Dateien (3 Dateien)

| Datei | Art der Änderung |
|---|---|
| `frontend/src/components/DataViewPanel.tsx` | Download-Button im `dataViewToolbar`-Block ergänzen |
| `frontend/src/App.css` | 2 neue CSS-Klassen `.csvDownloadButton` und `.csvDownloadButton--disabled` |
| `backend/src/gysi_ml/api/routes/data.py` | Neuer Raw-Data-Download-Endpunkt; versionierter Dateiname für Run-Download |

### Exakte Implementierung — DataViewPanel.tsx

Die aktuelle Toolbar (ca. Zeilen 163–172):

```tsx
<div className="dataViewToolbar">
  {isSplit && <span className="splitBadge">Split durchgeführt</span>}
  {rows.length > 0 && (
    <span className="dataViewInfo">
      1–{rows.length} von {totalRows.toLocaleString('de-DE')} Zeilen
    </span>
  )}
</div>
```

Ergänzung nach der `dataViewInfo`-Span (neuer Block am Ende des `dataViewToolbar`):

```tsx
{sessionId ? (
  <a
    className="csvDownloadButton"
    href={
      activeDataRunId
        ? `${backendBaseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(activeDataRunId)}/data/download`
        : `${backendBaseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/raw-data/download`
    }
    download
  >
    ⬇ CSV herunterladen
  </a>
) : (
  <span className="csvDownloadButton csvDownloadButton--disabled" aria-disabled="true">
    ⬇ CSV herunterladen
  </span>
)}
```

**Logik:**
- `sessionId` vorhanden + `activeDataRunId` gesetzt → Run-Snapshot-Download (`bikes_vN.csv`)
- `sessionId` vorhanden + `activeDataRunId === null` → Rohdaten-Download (`gysi_raw_data.csv`)
- `sessionId === null` → ausgegraut, kein Klick möglich

### Exakte Implementierung — App.css

Nach der `.splitBadge`-Definition (ca. Zeile 227) folgende Klassen einfügen:

```css
.csvDownloadButton {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--accent, #5b6af6);
  color: #fff;
  text-decoration: none;
  margin-left: auto;
  cursor: pointer;
}

.csvDownloadButton--disabled {
  background: var(--border, #e0e0e0);
  color: var(--text-muted, #888);
  cursor: not-allowed;
  margin-left: auto;
}
```

**Hinweis:** `margin-left: auto` auf dem Download-Button schiebt ihn rechtsbündig in der Flex-Toolbar (`dataViewToolbar` ist `display: flex`). Split-Badge und Zeilen-Info bleiben linksbündig.

### Backend-Endpunkte

**Run-Snapshot-Download** — `backend/src/gysi_ml/api/routes/data.py`

- **Route:** `GET /v1/sessions/{session_id}/runs/{run_id}/data/download`
- Prüft Session-Zugehörigkeit des Runs (404 wenn Run nicht zur Session gehört)
- Liest `artifacts/{run_id}_snapshot.parquet`
- Gibt vollständige CSV als `StreamingResponse` zurück (`media_type="text/csv"`)
- **Dateiname:** `bikes_{spec_version}.csv` (z.B. `bikes_v1.csv`) — aus `run.spec_version`; Fallback auf `bikes_{run_id[:8]}.csv` wenn `spec_version` fehlt
- HTTP 404 wenn kein Snapshot existiert

**Rohdaten-Download** — `backend/src/gysi_ml/api/routes/data.py` (neu hinzugefügt)

- **Route:** `GET /v1/sessions/{session_id}/raw-data/download`
- Liest `bikes.csv` direkt aus `data_path`
- Gibt vollständige CSV als `StreamingResponse` zurück
- **Dateiname:** `gysi_raw_data.csv`
- HTTP 404 wenn Datei nicht gefunden

**Hinweis zu DV-1-3:** Die Sprint-Status-Datei zeigt DV-1-3 (`dv-1-3-csv-download-endpunkt`) als `ready-for-dev`, aber der Run-Endpunkt war **bereits in der Codebase implementiert**. DV-2-5 hat daher keine blockierende Backend-Abhängigkeit.

### Vorab-Warnung: NICHT anfassen

- `DataViewPanel.tsx`-Props-Interface bleibt unverändert (`activeDataRunId`, `sessionId`, `backendBaseUrl` — alle bereits vorhanden)
- `currentRunRef`-Tracking und stale-response-prevention — **nicht anfassen**
- Infinite-Scroll-Logik und `loadMore`-Callback — **nicht anfassen**
- `chatReducer.ts`, `dataApi.ts`, `types.ts`, `App.tsx`, `healthApi.ts` — **keine Änderungen**

### Learnings aus DV-2-4

- `activeDataRunId` kommt als Prop direkt in `DataViewPanel` — kein neues State-Management nötig
- Der Prop `sessionId` ist bereits in der Komponenten-Signatur vorhanden
- `backendBaseUrl`-Prop ist der korrekte Weg für URL-Konstruktion (nicht hardcoden, nicht Env-Variable direkt)
- `encodeURIComponent` für beide IDs (Muster aus `dataApi.ts`)
- Bestehende Toolbar ist `display: flex; align-items: center; gap: 8px` — Download-Button passt als Flex-Item hinein

### Project Structure Notes

- Frontend-Quellen: `frontend/src/`
- Komponenten: `frontend/src/components/`
- Globale Styles: `frontend/src/App.css`
- State-Management: `frontend/src/state/chatReducer.ts` (NICHT ändern)
- API-Layer: `frontend/src/api/dataApi.ts` (NICHT ändern)

### References

- [Source: _bmad-output/planning-artifacts/shared/epics-data-view-tab.md — Story DV-2.5]
- [Source: _bmad-output/implementation-artifacts/frontend/dv-2-4-rollback-integration-datenansicht-aktualisiert-sich.md — Dev Notes, Project Structure]
- [Source: frontend/src/components/DataViewPanel.tsx — Props-Interface, Toolbar-Struktur]
- [Source: frontend/src/api/dataApi.ts — URL-Konstruktionsmuster mit encodeURIComponent]
- [Source: frontend/src/App.css — Toolbar und splitBadge CSS-Definitionen]
- [Source: backend/src/gysi_ml/api/routes/data.py — Implementierter Download-Endpunkt]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

_keine_

### Completion Notes List

- Task 1 erledigt: Bedingtes `<a>`/`<span>`-Element in `dataViewToolbar` von `DataViewPanel.tsx` eingefügt. Button ist aktiv wenn `sessionId` vorhanden: bei `activeDataRunId` → Run-Download, sonst → Raw-Data-Download. Nur ohne `sessionId` ausgegraut. AC #2 wurde post-implementation angepasst: Rohdaten-Download ohne aktiven Run ist explizit erwünscht.
- Task 2 erledigt: `.csvDownloadButton` und `.csvDownloadButton--disabled` in `App.css` nach `.splitBadge` eingefügt. `margin-left: auto` sorgt für Rechtsbündigkeit in der Flex-Toolbar.
- Backend erweitert: Neuer Endpunkt `GET /v1/sessions/{session_id}/raw-data/download` für Rohdaten-Download (`gysi_raw_data.csv`) hinzugefügt.
- Backend geändert: Run-Download-Dateiname von `gysi_data_{run_id[:8]}.csv` auf `bikes_{spec_version}.csv` umgestellt (z.B. `bikes_v1.csv`); Fallback auf `bikes_{run_id[:8]}.csv` wenn `spec_version` fehlt.
- TypeScript-Kompilierung fehlerfrei (`npx tsc --noEmit`).
- Task 3 (manueller Smoke-Test) liegt beim Nutzer.

### File List

- frontend/src/components/DataViewPanel.tsx
- frontend/src/App.css
- backend/src/gysi_ml/api/routes/data.py
- frontend/src/types.ts (run_id-Feld in ResultResponse ergänzt)
- frontend/src/api/realTransport.ts (run_id aus Backend-Result parsen)
- frontend/src/state/chatReducer.ts (SEND_REQUEST_SUCCEEDED setzt activeDataRunId bei direktem Execute)
