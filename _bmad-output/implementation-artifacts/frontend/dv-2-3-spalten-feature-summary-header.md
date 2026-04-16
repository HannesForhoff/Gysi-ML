# Story DV-2.3: Spalten-Feature-Summary-Header

Status: review

## Story

Als ein Nutzer,
möchte ich über jeder Tabellenspalte eine kompakte Zusammenfassung mit Werteverteilung, fehlenden Werten, Distinct-Werten und Min/Max sehen,
damit ich auf einen Blick die Datenqualität und Verteilung jeder Spalte einschätzen kann — ähnlich wie im VS Code Data Wrangler.

## Acceptance Criteria (BDD)

1. **Given** die Daten sind geladen und `column_stats` ist vorhanden
   **When** die Datentabelle gerendert wird
   **Then** zeigt jede Spalte einen Summary-Header mit Spaltenname, Missing und Distinct

2. **Given** eine numerische Spalte hat Histogram-Daten (`histogram` vorhanden)
   **When** der Spalten-Header gerendert wird
   **Then** ist ein SVG-Balkendiagramm mit 10 Balken sichtbar
   **And** unter dem Diagramm stehen Min und Max in kleiner Schrift

3. **Given** eine nicht-numerische Spalte (z.B. `dteday`, dtype `object` — erkennbar daran, dass `histogram`, `min` und `max` undefined sind)
   **When** der Spalten-Header gerendert wird
   **Then** wird kein Histogramm angezeigt, nur Missing und Distinct

4. **Given** Missing-Count ist 0
   **When** der Summary-Header angezeigt wird
   **Then** wird `Missing: 0 (0%)` angezeigt (kein leeres Feld)

5. **Given** der Nutzer scrollt vertikal durch viele Zeilen
   **When** der Scroll-Offset > Viewport-Höhe ist
   **Then** bleiben alle Spalten-Header sticky sichtbar (bestehende CSS-Regel — unverändert)

6. **Given** `column_stats` ist `null` (noch kein Fetch abgeschlossen oder Fehler)
   **When** die Tabelle gerendert wird
   **Then** zeigen alle `<th>`-Zellen nur den nackten Spaltennamen (Fallback — kein Absturz)

7. **Given** alle vorherigen Stories implementiert sind
   **When** alle Tests ausgeführt werden
   **Then** sind alle bestehenden Tests weiterhin grün (keine Regressionen)

## Tasks / Subtasks

- [x] **T1** — `frontend/src/components/ColumnSummaryHeader.tsx`: Neue Komponente erstellen (AC: #1–#5)
  - [x] T1.1: Props-Typ: `{ colName: string; stats: ColumnStats | undefined }` — `ColumnStats` aus `../api/dataApi` importieren
  - [x] T1.2: Fallback: Wenn `stats === undefined` → nur `<span className="columnSummaryName">{colName}</span>` rendern (keine weiteren Elemente)
  - [x] T1.3: Normalfall-Layout (flex-column, von oben nach unten):
    1. `<span className="columnSummaryName">{colName}</span>`
    2. SVG-Histogram (nur wenn `stats.histogram` vorhanden — numerisch)
    3. `<span className="columnSummaryStat">Missing: {stats.missing_count} ({stats.missing_pct.toFixed(1)}%)</span>`
    4. `<span className="columnSummaryStat">Distinct: {stats.distinct_count} ({stats.distinct_pct.toFixed(1)}%)</span>`
    5. Min/Max-Zeile (nur wenn `stats.min !== undefined && stats.max !== undefined`):
       `<div className="columnSummaryMinMax"><span>Min {stats.min}</span><span>Max {stats.max}</span></div>`
  - [x] T1.4: SVG-Histogram: `width="100%"`, `height="40"`, `viewBox="0 0 100 40"`, `preserveAspectRatio="none"`
    - Alle `counts` auf max normieren: `maxCount = Math.max(...stats.histogram.counts, 1)`
    - 10 Balken gleichmäßig verteilt: `barWidth = 100 / 10 = 10`; x-Position: `i * 10`
    - Balkenhöhe: `barHeight = (count / maxCount) * 40`; y-Position (SVG wächst nach unten): `y = 40 - barHeight`
    - Balkenfarbe: `fill="#4299e1"` (Akzentfarbe)
    - Lücke zwischen Balken: 1px — Breite eines Balkens innerhalb viewBox = `9` (mit 1px Abstand), x-Offset = `i * 10 + 0.5`
  - [x] T1.5: Wrapper-Element: `<div className="columnSummaryHeader">...</div>` als äußerstes Element

- [x] **T2** — `frontend/src/components/DataViewPanel.tsx`: `columnStats` State lesbar machen und an Header übergeben (AC: #1, #6)
  - [x] T2.1: Zeile `const [, setColumnStats] = ...` → `const [columnStats, setColumnStats] = ...`
    - **⚠️ KRITISCH**: Nur diese eine Zeile ändern — der Rest des Datei-Codes bleibt exakt identisch
  - [x] T2.2: Import: `ColumnSummaryHeader` aus `./ColumnSummaryHeader` importieren
  - [x] T2.3: In `<thead><tr>` das `{columns.map((col) => (<th key={col}>{col}</th>))}` ersetzen durch:
    ```tsx
    {columns.map((col) => (
      <th key={col}>
        <ColumnSummaryHeader
          colName={col}
          stats={columnStats?.[col]}
        />
      </th>
    ))}
    ```
  - [x] T2.4: CSS-Anpassung: Die bestehende Regel `.dataTable thead th { white-space: nowrap }` in `App.css` muss **entfernt oder auf `white-space: normal` geändert** werden — damit der Summary-Header korrekt umbrechen kann

- [x] **T3** — `frontend/src/App.css`: Styles für den Summary-Header hinzufügen (AC: #1–#5)
  - [x] T3.1: `white-space: nowrap` aus `.dataTable thead th` entfernen (Zeile 255 ca.) — ermöglicht mehrzeiligen Header-Inhalt
  - [x] T3.2: Neue CSS-Klassen am Ende des dataTable-Blocks einfügen:
    ```css
    .columnSummaryHeader {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 80px;
      padding: 2px 0;
    }

    .columnSummaryName {
      font-weight: 600;
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .columnSummaryStat {
      font-size: 10px;
      color: var(--text-muted, #888);
      white-space: nowrap;
    }

    .columnSummaryMinMax {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: var(--text-muted, #888);
      white-space: nowrap;
    }
    ```

- [x] **T4** — `frontend/src/components/ColumnSummaryHeader.test.tsx`: Unit-Tests (AC: #1–#4, #6)
  - [x] T4.1: Test-Pattern analog zu `ResultCard.test.tsx` — `render` + `screen` aus `@testing-library/react`, `describe`/`it`/`expect` aus vitest
  - [x] T4.2: `numericStats`-Fixture: vollständige `ColumnStats` mit `histogram`, `min`, `max`, `missing_count`, `missing_pct`, `distinct_count`, `distinct_pct`
  - [x] T4.3: `categoricalStats`-Fixture: `ColumnStats` ohne `histogram`, ohne `min`/`max`
  - [x] T4.4: Test: Spaltenname wird gerendert (numerisch + kategorisch)
  - [x] T4.5: Test: SVG mit 10 `<rect>`-Elementen bei numerischer Spalte sichtbar
  - [x] T4.6: Test: Kein SVG-Element bei kategorischer Spalte
  - [x] T4.7: Test: `Missing: 0 (0.0%)` korrekt angezeigt (AC: #4)
  - [x] T4.8: Test: Min/Max bei numerischer Spalte sichtbar
  - [x] T4.9: Test: Kein Min/Max bei kategorischer Spalte
  - [x] T4.10: Test: `stats === undefined` → nur Spaltenname gerendert, kein Absturz (AC: #6)

- [ ] **T5** — Manuelle Smoke-Tests (AC: #1–#5) — Hannes
  - [ ] T5.1: Run ausführen → Data-Tab öffnen → jede Spalte zeigt Summary-Header
  - [ ] T5.2: Numerische Spalte (z.B. `cnt`, `temp`): SVG-Histogramm sichtbar, Min/Max vorhanden
  - [ ] T5.3: Nicht-numerische Spalte (z.B. `dteday`, `season`): kein Histogramm
  - [ ] T5.4: Missing: 0 (0.0%) korrekt angezeigt (Bike-Datensatz hat keine Missing Values)
  - [ ] T5.5: Spalten-Header bleiben sticky beim vertikalen Scrollen

## Dev Notes

### Kritische Vorab-Analyse: Was ist bereits implementiert

**DV-2.2 hat `columnStats` bereits gecacht** — aber noch nicht gerendert!

In `DataViewPanel.tsx` (Zeile 23) steht:
```tsx
// Cached for DV-2.3 — stored but not rendered in this story
const [, setColumnStats] = useState<Record<string, ColumnStats> | null>(null)
```

→ Der `setColumnStats`-Aufruf in Zeile 101 ist aktiv — Stats werden bereits gespeichert.
→ Diese Story muss nur den ersten Teil (`setColumnStats`) zu `columnStats` umbenennen und den Render-Code hinzufügen.

### SVG-Histogram-Implementierung (konkret)

```tsx
function HistogramSvg({ histogram }: { histogram: NonNullable<ColumnStats['histogram']> }) {
  const maxCount = Math.max(...histogram.counts, 1)
  return (
    <svg width="100%" height="40" viewBox="0 0 100 40" preserveAspectRatio="none">
      {histogram.counts.map((count, i) => {
        const barHeight = (count / maxCount) * 40
        return (
          <rect
            key={i}
            x={i * 10 + 0.5}
            y={40 - barHeight}
            width={9}
            height={barHeight}
            fill="#4299e1"
          />
        )
      })}
    </svg>
  )
}
```

### Wichtig: Numerisch vs. Kategorisch erkennen

Es gibt kein explizites `dtype`-Feld in `ColumnStats`. Die Erkennung erfolgt implizit:
- **Numerisch** = `stats.histogram !== undefined` (und `stats.min !== undefined`)
- **Kategorisch** = `stats.histogram === undefined`

> Der Backend-`SnapshotService` berechnet Histogramm, Min und Max nur für numerische Spalten.
> Quelle: `epics-data-view-tab.md`, Story DV-1.1, Abschnitt "Technischer Kontext"

### Bestehende Patterns (NICHT neu erfinden!)

| Pattern | Datei | Muster |
|---|---|---|
| Component-Tests | `frontend/src/components/ResultCard.test.tsx` | `render` + `screen` aus `@testing-library/react` |
| Component-Tests | `frontend/src/components/ProposalCard.test.tsx` | Gleiche Struktur |
| ColumnStats-Typ | `frontend/src/api/dataApi.ts` | Bereits vollständig definiert — nicht neu erstellen |
| CSS-Variablen | `frontend/src/App.css` | `var(--text-muted, #888)`, `var(--border, #e0e0e0)`, `var(--accent, #5b6af6)` |

### Datei-Übersicht der zu ändernden Dateien

| Aktion | Datei | Änderungsumfang |
|---|---|---|
| NEU | `frontend/src/components/ColumnSummaryHeader.tsx` | Neue Komponente |
| NEU | `frontend/src/components/ColumnSummaryHeader.test.tsx` | Unit-Tests |
| MINIMAL | `frontend/src/components/DataViewPanel.tsx` | 2 Änderungen: 1× State-Rename, 1× `<th>`-Content |
| MINIMAL | `frontend/src/App.css` | `white-space: nowrap` entfernen + 4 neue CSS-Klassen |

### Keine neuen API-Endpunkte, keine Backend-Änderungen

Diese Story ist **rein frontend-seitig**. Der Backend-Endpunkt `GET .../data?offset=0` liefert `column_stats` bereits seit DV-1.2. Der Fetch-Code in `DataViewPanel` speichert die Stats bereits seit DV-2.2 (T2.15). Kein neuer API-Call nötig.

### Project Structure Notes

- Neue Komponente unter `frontend/src/components/` (analog zu `ResultCard.tsx`, `ProposalCard.tsx`)
- Test-Datei: `ColumnSummaryHeader.test.tsx` im gleichen Ordner (analog zu `ResultCard.test.tsx`)
- Kein neues CSS-Modul — weiterhin `App.css` verwenden (bestehender Projektstandard)
- TypeScript strict mode aktiv — alle Props müssen typisiert sein

### References

- Story-Anforderungen: [_bmad-output/planning-artifacts/shared/epics-data-view-tab.md](../../../../_bmad-output/planning-artifacts/shared/epics-data-view-tab.md) — Story DV-2.3
- Vorherige Story: [_bmad-output/implementation-artifacts/frontend/dv-2-2-paginierte-datentabelle-mit-infinite-scroll.md](dv-2-2-paginierte-datentabelle-mit-infinite-scroll.md) — T2.15: `columnStats` gecacht
- `ColumnStats`-Typ: [frontend/src/api/dataApi.ts](../../../../frontend/src/api/dataApi.ts)
- Existierender State: [frontend/src/components/DataViewPanel.tsx](../../../../frontend/src/components/DataViewPanel.tsx) — Zeile 23
- CSS-Basis: [frontend/src/App.css](../../../../frontend/src/App.css) — Zeile 249: `.dataTable thead th`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (GitHub Copilot)

### Debug Log References

- App.test.tsx hat 9 pre-existing Failures (Proposal-Flow-Tests) — vor und nach diesem Story identisch fehlgeschlagen, keine Regression.

### Completion Notes List

- ✅ T1: `ColumnSummaryHeader.tsx` erstellt — neue Komponente mit `HistogramSvg`-Subkomponente, korrektem Fallback und allen Props.
- ✅ T2: `DataViewPanel.tsx` — State-Rename von `[, setColumnStats]` zu `[columnStats, setColumnStats]`, Import und `<th>`-Content ersetzt.
- ✅ T3: `App.css` — `white-space: nowrap` durch `normal` ersetzt, 4 neue CSS-Klassen hinzugefügt.
- ✅ T4: `ColumnSummaryHeader.test.tsx` — 10 Tests, alle grün. Deckt AC #1–#4, #6 ab.
- T5 (Manuelle Smoke-Tests) — liegt bei Hannes.
- Alle 54 Komponenten-Tests grün, 0 neue Regressionen.

### File List

- `frontend/src/components/ColumnSummaryHeader.tsx` (NEU)
- `frontend/src/components/ColumnSummaryHeader.test.tsx` (NEU)
- `frontend/src/components/DataViewPanel.tsx` (GEÄNDERT)
- `frontend/src/App.css` (GEÄNDERT)

## Change Log

- 2026-04-14: DV-2.3 implementiert — ColumnSummaryHeader-Komponente, SVG-Histogramme, CSS-Styles, Unit-Tests (10/10 grün)
