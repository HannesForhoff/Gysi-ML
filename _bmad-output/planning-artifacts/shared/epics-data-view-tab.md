---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories]
feature: Data View Tab
createdAt: 2026-04-04
inputDocuments:
  - _bmad-output/planning-artifacts/backend/epics.md
  - _bmad-output/planning-artifacts/frontend/epics.md
  - _bmad-output/planning-artifacts/architecture.md
---

# gysi-ml — Data View Tab: Epics & Stories

## Überblick

Dieses Dokument beschreibt die Epics und Stories für das neue **Datenansicht-Feature**: einen separaten Tab neben dem Chat, der den aktuellen Zustand des transformierten Datensatzes als interaktive Tabelle mit Spalten-Statistiken anzeigt. Die Ansicht ist versioniert (via Spec-Verlauf und Rollback), paginiert und bietet einen CSV-Download.

---

## Anforderungen

### Funktionale Anforderungen

FR-DV1: Nach jedem erfolgreichen Run wird ein Snapshot des transformierten Datensatzes persistent gespeichert.

FR-DV2: Zu jedem Snapshot werden Spalten-Statistiken berechnet: Anzahl fehlender Werte (absolut + %), Anzahl Distinct-Werte (absolut + %), Min, Max sowie Histogramm-Bins (10 Bins).

FR-DV3: Ein paginierter API-Endpunkt liefert Zeilen des Snapshots einer Run-ID (`offset`, `limit`), beginnend mit maximal 1000 Zeilen initial.

FR-DV4: Ein API-Endpunkt liefert den Snapshot einer Run-ID als CSV-Download.

FR-DV5: Das Frontend zeigt einen Tab-Switcher (Chat ↔ Datenansicht); der SpecHistoryPanel bleibt in beiden Tabs sichtbar.

FR-DV6: Die Datentabelle zeigt zunächst die ersten 1000 Zeilen; beim Scroll bis zum Ende werden automatisch weitere 100 Zeilen nachgeladen (Infinite Scroll).

FR-DV7: Jede Tabellenspalte hat einen Summary-Header mit: Mini-Balkendiagramm der Werteverteilung, Missing-Werte (Anzahl + %), Distinct-Werte (Anzahl + %), Min/Max-Anzeige.

FR-DV8: Ein Klick auf „Rollback" im SpecHistoryPanel aktualisiert die Datenansicht auf den Snapshot der gewählten Spec-Version (letzter Run dieser Version).

FR-DV9: Ein „CSV herunterladen"-Button löst den CSV-Download des aktuell angezeigten Runs aus.

### Nicht-funktionale Anforderungen

NFR-DV1: Der Snapshot-Speicher darf einen laufenden Run nie zum Scheitern bringen — Fehler beim Speichern werden still geloggt (fire-and-forget).

NFR-DV2: Parquet-Snapshots werden unter `artifacts/{run_id}_snapshot.parquet` abgelegt.

NFR-DV3: Der paginierte Endpunkt antwortet in < 500 ms für `limit=100` bei vollem Bike-Datensatz (17.379 Zeilen).

NFR-DV4: Spalten-Statistiken werden einmalig beim Snapshot berechnet und persistiert — nicht bei jedem API-Aufruf neu berechnet.

NFR-DV5: Die Datentabelle ist horizontal scrollbar; Spalten-Header sind sticky (beim Scrollen sichtbar).

NFR-DV6: Kein neuer Step, kein bestehender Executor-Kern und keine bestehende Datenbankschema-Tabelle werden verändert — ausschließlich additive Änderungen.

### Design-Entscheid: Welche Daten werden angezeigt?

Angezeigt wird immer `df_full` — der vollständige Datensatz im aktuellen Transformationszustand nach dem Run. Wenn ein Split ausgeführt wurde, zeigt `df_full` den Stand vor dem Split (Preprocessing-Ergebnis). Ein Badge „Split durchgeführt" informiert den Nutzer wenn `context.is_split = True`.

---

## Epic-Übersicht

| Epic | Titel | Scope |
|---|---|---|
| Epic DV-1 | Datensatz-Snapshots und Daten-API | Backend |
| Epic DV-2 | Data View Tab — Tabelle, Stats, Rollback, Download | Frontend |

---

## Epic DV-1: Datensatz-Snapshots und Daten-API (Backend)

Nach jedem Run wird der transformierte Datensatz als Parquet-Snapshot persistiert. Zwei neue Endpunkte ermöglichen paginierte Abfrage und CSV-Download.

**FRs covered:** FR-DV1, FR-DV2, FR-DV3, FR-DV4

---

### Story DV-1.1: Run-Snapshot nach Pipeline-Ausführung speichern

Als Entwickler,
möchte ich dass nach jedem erfolgreichen Run der transformierte Datensatz als Parquet-Datei und die Spalten-Statistiken als JSON persistent gespeichert werden,
damit die Datenansicht im Frontend versionssicher den tatsächlichen Zustand nach jedem Run anzeigen kann.

**Technischer Kontext:**

- Eingriff in bestehenden Code: `executor.py` → am Ende von `_run_pipeline()`, nach dem Run-Status-Update auf `"done"`, einen fire-and-forget-Call an `SnapshotService` einfügen.
- Neuer Code: `snapshot_service.py` in `gysi_ml/services/`
- Gespeichert werden: `artifacts/{run_id}_snapshot.parquet` und `artifacts/{run_id}_column_stats.json`
- `df_full` aus `PipelineContext` wird gespeichert; zusätzlich `is_split: bool` als Metadatum.
- Histogramm-Bins: 10 Bins, berechnet mit `numpy.histogram`.

**Acceptance Criteria:**

**Given** ein Run wird erfolgreich ausgeführt (Status `done`)
**When** die Pipeline abgeschlossen ist
**Then** existiert unter `artifacts/{run_id}_snapshot.parquet` eine valide Parquet-Datei
**And** existiert unter `artifacts/{run_id}_column_stats.json` eine JSON-Datei mit Stats pro Spalte

**Given** die Column-Stats-Datei wird gelesen
**When** eine numerische Spalte ausgewertet wird
**Then** enthält sie die Felder: `missing_count`, `missing_pct`, `distinct_count`, `distinct_pct`, `min`, `max`, `histogram` (mit `bins` und `counts`, je 10 Einträge)

**Given** der Snapshot-Schreibvorgang schlägt fehl (z.B. Disk voll)
**When** die Exception auftritt
**Then** wird der Run-Status trotzdem auf `done` gesetzt und der Fehler nur geloggt (kein 500-Fehler)

**Given** ein Run mit Split-Step wird ausgeführt
**When** der Snapshot gespeichert wird
**Then** enthält `column_stats.json` ein Top-Level-Feld `"is_split": true`

---

### Story DV-1.2: Paginierter Daten-Endpunkt

Als Frontend,
möchte ich Zeilen eines Run-Snapshots seitenweise abrufen können (`offset` + `limit`),
damit die Datenansicht zunächst 1000 Zeilen lädt und beim Scrollen weitere 100 Zeilen nachlädt, ohne den gesamten Datensatz auf einmal zu übertragen.

**Technischer Kontext:**

- Neuer Endpunkt: `GET /v1/sessions/{session_id}/runs/{run_id}/data`
- Query-Parameter: `offset: int = 0`, `limit: int = 100` (max 1000)
- Response-Schema:
  ```json
  {
    "columns": ["col1", "col2", ...],
    "rows": [[val, val, ...], ...],
    "total_rows": 17379,
    "offset": 0,
    "limit": 100,
    "is_split": false,
    "column_stats": { "col1": { "missing_count": 0, ... }, ... }
  }
  ```
- `column_stats` wird nur beim ersten Request mitgeliefert (`offset == 0`), danach aus dem Frontend gecacht.
- Parquet wird mit `pandas.read_parquet` geladen; Slice per `iloc[offset:offset+limit]`.
- Session-Zugehörigkeit des Runs muss geprüft werden (404 wenn Run nicht zur Session gehört).

**Acceptance Criteria:**

**Given** ein Run-Snapshot existiert für `run_id`
**When** `GET /v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=100` aufgerufen wird
**Then** antwortet der Endpunkt mit HTTP 200
**And** `rows` enthält genau 100 Einträge (oder weniger wenn Datensatz kleiner)
**And** `column_stats` ist im Response enthalten (da `offset == 0`)
**And** die Response-Zeit liegt unter 500 ms

**Given** `offset=100` und `limit=100`
**When** der Endpunkt aufgerufen wird
**Then** enthält `column_stats` nicht (wird weggelassen um Payload zu reduzieren)
**And** `rows` enthält die Zeilen 100–199

**Given** `limit=2000` wird übergeben
**When** der Endpunkt aufgerufen wird
**Then** wird `limit` serverseitig auf 1000 geclampt

**Given** kein Snapshot für `run_id` existiert (Run lief noch nicht oder ist fehlgeschlagen)
**When** der Endpunkt aufgerufen wird
**Then** antwortet der Endpunkt mit HTTP 404 und einer verständlichen Fehlermeldung

**Given** `run_id` gehört zu einer anderen Session
**When** der Endpunkt aufgerufen wird
**Then** antwortet der Endpunkt mit HTTP 404

---

### Story DV-1.3: CSV-Download-Endpunkt

Als Nutzer,
möchte ich den aktuell angezeigten transformierten Datensatz als CSV-Datei herunterladen können,
damit ich die Ergebnisse meines Preprocessing-Workflows weiterverarbeiten kann.

**Technischer Kontext:**

- Neuer Endpunkt: `GET /v1/sessions/{session_id}/runs/{run_id}/data/download`
- Liest `artifacts/{run_id}_snapshot.parquet` und streamt es als CSV (`StreamingResponse` mit `media_type="text/csv"`).
- Response-Header: `Content-Disposition: attachment; filename="gysi_data_{run_id[:8]}.csv"`
- Session-Zugehörigkeit des Runs wird geprüft.

**Acceptance Criteria:**

**Given** ein Run-Snapshot existiert für `run_id`
**When** `GET /v1/sessions/{session_id}/runs/{run_id}/data/download` aufgerufen wird
**Then** antwortet der Endpunkt mit HTTP 200
**And** `Content-Type` ist `text/csv`
**And** `Content-Disposition` enthält `attachment; filename="gysi_data_...csv"`
**And** der Response-Body ist ein valides CSV mit Header-Zeile und allen Datensatzspalten

**Given** kein Snapshot für `run_id` existiert
**When** der Endpunkt aufgerufen wird
**Then** antwortet der Endpunkt mit HTTP 404

**Given** `run_id` gehört zu einer anderen Session
**When** der Endpunkt aufgerufen wird
**Then** antwortet der Endpunkt mit HTTP 404

---

## Epic DV-2: Data View Tab — Tabelle, Stats, Rollback, Download (Frontend)

Die Web-UI erhält einen Tab-Switcher (Chat ↔ Datenansicht). Die Datenansicht zeigt eine paginierte Tabelle mit Spalten-Summary-Headern, aktualisiert sich bei Rollback und bietet einen CSV-Download-Button.

**FRs covered:** FR-DV5, FR-DV6, FR-DV7, FR-DV8, FR-DV9

---

### Story DV-2.1: Tab-Switcher (Chat ↔ Datenansicht)

Als Nutzer,
möchte ich zwischen dem Chat und der Datenansicht über Tabs wechseln können, ohne dass der Spec-Verlauf rechts verschwindet,
damit ich jederzeit den Datenzustand inspizieren kann, ohne den Chat-Verlauf zu verlieren.

**Technischer Kontext:**

- Eingriff in bestehenden Code: `ChatLayout.tsx` erhält eine Tab-Leiste; `<main>` rendert je nach aktivem Tab entweder `ChatPane` oder `DataViewPanel`.
- Neues State-Feld im `ChatState` (`chatReducer.ts`): `activeTab: 'chat' | 'data'`.
- `SpecHistoryPanel` (rechts, `historyPane`) bleibt in beiden Tabs unverändert sichtbar.
- Der Data-Tab ist deaktiviert (ausgegraut), solange kein Run mit Snapshot vorliegt (`activeDataRunId === null`).
- Neues State-Feld: `activeDataRunId: string | null` — wird nach jedem erfolgreichen Run auf die aktuelle `run_id` gesetzt.

**Acceptance Criteria:**

**Given** die App ist gestartet und es wurde noch kein Run ausgeführt
**When** der Nutzer auf den „Daten"-Tab klickt
**Then** ist der Tab ausgegraut und nicht klickbar
**And** ein Hinweistext „Noch kein Datensatz vorhanden — führe zuerst einen Schritt aus." wird angezeigt (oder der Klick ist inaktiv)

**Given** ein Run wurde erfolgreich abgeschlossen
**When** der Nutzer auf den „Daten"-Tab wechselt
**Then** wird die Datenansicht angezeigt
**And** der Spec-Verlauf rechts bleibt sichtbar

**Given** der Nutzer wechselt zurück zum „Chat"-Tab
**When** der Tab-Click erfolgt
**Then** wird die Chat-Ansicht (MessageList + Composer) wieder angezeigt
**And** keine Nachricht im Chat-Verlauf ist verloren gegangen

---

### Story DV-2.2: Paginierte Datentabelle mit Infinite Scroll

Als Nutzer,
möchte ich in der Datenansicht die ersten 1000 Zeilen des transformierten Datensatzes sehen und beim Scrollen ans Ende automatisch weitere 100 Zeilen nachladen,
damit ich auch große Datensätze inspizieren kann ohne die gesamte Seite zu blockieren.

**Technischer Kontext:**

- Neue Komponente: `DataViewPanel.tsx`
- Initialer Load: `GET .../data?offset=0&limit=1000` beim Öffnen des Data-Tabs (oder nach Run-Abschluss).
- Infinite Scroll: `IntersectionObserver` auf ein Sentinel-Element am Tabellenende; bei Sichtbarkeit wird `GET .../data?offset=currentRows&limit=100` gefeuert.
- Während Nachladen: Spinner-Zeile am Tabellenende; kein Layout-Shift.
- Tabelle: horizontales Scrollen bei vielen Spalten; Zebra-Striping für Lesbarkeit; sticky Column-Header.
- `null`/`NaN`-Werte werden als kursiver grauer Text „Missing value" dargestellt (analog zum Screenshot).
- Keine externe Tabellen-Library erforderlich — natives `<table>` mit CSS reicht.

**Acceptance Criteria:**

**Given** der Data-Tab wird geöffnet und `activeDataRunId` ist gesetzt
**When** der initiale Fetch abgeschlossen ist
**Then** werden bis zu 1000 Zeilen der Tabelle angezeigt
**And** die `total_rows`-Anzahl wird als Info angezeigt (z.B. „1–1000 von 17.379 Zeilen")

**Given** der Nutzer scrollt bis zum Ende der Tabelle
**When** das Sentinel-Element sichtbar wird
**Then** werden 100 weitere Zeilen nachgeladen und direkt an die Tabelle angehängt
**And** kein Layout-Shift tritt auf

**Given** alle Zeilen wurden geladen (`currentRows >= total_rows`)
**When** der Nutzer ans Ende scrollt
**Then** wird kein weiterer Request ausgelöst
**And** ein Text „Alle Zeilen geladen" wird angezeigt

**Given** eine Zelle enthält `null` oder `NaN`
**When** die Zelle gerendert wird
**Then** wird „Missing value" in grauer kursiver Schrift angezeigt

**Given** ein Fetch-Fehler tritt beim Nachladen auf
**When** der Request fehlschlägt
**Then** wird eine Fehlermeldung am Tabellenende angezeigt (kein Absturz)

---

### Story DV-2.3: Spalten-Feature-Summary-Header

Als Nutzer,
möchte ich über jeder Tabellenspalte eine kompakte Zusammenfassung mit Werteverteilung, fehlenden Werten, Distinct-Werten und Min/Max sehen,
damit ich auf einen Blick die Datenqualität und Verteilung jeder Spalte einschätzen kann — ähnlich wie im VS Code Data Wrangler.

**Technischer Kontext:**

- Neue Komponente: `ColumnSummaryHeader.tsx` — wird in den `<th>` jeder Spalte gerendert.
- Die `column_stats` kommen aus dem ersten Data-Fetch (`offset=0`) und werden in `DataViewPanel` lokal gecacht (kein extra API-Call).
- Mini-Balkendiagramm: SVG, 10 Bins, Höhe 40px, volle Spaltenbreite; Balken in Akzentfarbe (`#4299e1` oder Theme-Variante).
- Layout pro Spalten-Header (von oben nach unten):
  1. Spaltenname (fett)
  2. Mini-SVG-Histogram (40px hoch)
  3. `Missing: {n} ({pct}%)` — grau
  4. `Distinct: {n} ({pct}%)` — grau
  5. Min/Max-Zeile: `Min {min}` links, `Max {max}` rechts (klein, grau)
- Bei nicht-numerischen Spalten (dtype `object`): kein Histogram, nur Missing + Distinct.
- Spalten-Header sticky beim vertikalen Scrollen.

**Acceptance Criteria:**

**Given** die Daten sind geladen und `column_stats` ist vorhanden
**When** die Datentabelle gerendert wird
**Then** zeigt jede Spalte einen Summary-Header mit Spaltenname, Missing, Distinct

**Given** eine numerische Spalte hat Histogram-Daten
**When** der Spalten-Header gerendert wird
**Then** ist ein SVG-Balkendiagramm mit 10 Balken sichtbar
**And** unter dem Diagramm stehen Min und Max in kleiner Schrift

**Given** eine nicht-numerische Spalte (z.B. `dteday`)
**When** der Spalten-Header gerendert wird
**Then** wird kein Histogramm angezeigt, nur Missing und Distinct

**Given** Missing-Count ist 0
**When** der Summary-Header angezeigt wird
**Then** wird `Missing: 0 (0%)` angezeigt (kein leeres Feld)

**Given** der Nutzer scrollt vertikal durch viele Zeilen
**When** der Scroll-Offset > Viewport-Höhe ist
**Then** bleiben alle Spalten-Header sticky sichtbar

---

### Story DV-2.4: Rollback-Integration — Datenansicht aktualisiert sich

Als Nutzer,
möchte ich nach einem Rollback auf eine ältere Spec-Version im rechten Verlaufspanel die Daten in der Datenansicht automatisch auf den Zustand dieser Version aktualisiert sehen,
damit ich visuell vergleichen kann was dieser Rollback am Datensatz verändert hat.

**Technischer Kontext:**

- Rollback-Response enthält bereits `new_spec_id` und `new_version` im `chatReducer`.
- Nach einem Rollback: suche im `specHistory` nach dem neuesten Run der `new_spec_id`. Wenn ein Run existiert: setze `activeDataRunId` auf dessen `run_id` und lade Daten neu.
- Wenn kein Run für die Rollback-Spec existiert: zeige in der Datenansicht einen Hinweis „Keine Daten für diese Version — führe die Spec erneut aus".
- Kein neuer Backend-Endpunkt erforderlich; `GET .../data` mit der alten `run_id` reicht.
- `chatReducer.ts`: `ROLLBACK_SUCCEEDED`-Action setzt `activeDataRunId` auf den letzten Run der Ziel-Spec (oder `null` wenn keiner existiert).

**Acceptance Criteria:**

**Given** der Nutzer hat mehrere Runs ausgeführt (Spec v1 und v2)
**When** der Nutzer im Spec-Verlauf auf „Rollback" zu v1 klickt
**Then** wechselt `activeDataRunId` auf den letzten Run von Spec v1
**And** die Datentabelle lädt neu und zeigt den Datensatz-Zustand von v1

**Given** der Rollback-Ziel-Spec hat noch keinen Run (z.B. nach `modify_spec` ohne anschließenden Execute)
**When** der Nutzer den Data-Tab öffnet
**Then** wird der Hinweis „Keine Daten für diese Version — führe die Spec erneut aus" angezeigt

**Given** der Rollback ist abgeschlossen und der Nutzer ist im Chat-Tab
**When** der Nutzer zum Data-Tab wechselt
**Then** zeigt die Datentabelle bereits die Daten der Rollback-Version (kein manuelles Refresh nötig)

---

### Story DV-2.5: CSV-Download-Button

Als Nutzer,
möchte ich mit einem einzigen Klick den aktuell angezeigten transformierten Datensatz als CSV-Datei herunterladen,
damit ich die aufbereiteten Daten für eigene Analysen oder Berichte weiternutzen kann.

**Technischer Kontext:**

- Button in der Toolbar des `DataViewPanel` (oben rechts, neben der Zeilen-Info).
- Implementierung: ein `<a href=".../data/download" download>` mit der Backend-URL für `activeDataRunId` — kein clientseitiger CSV-Serializer nötig.
- Button ist ausgegraut wenn `activeDataRunId === null`.
- Label: „CSV herunterladen" mit Download-Icon.

**Acceptance Criteria:**

**Given** `activeDataRunId` ist gesetzt und ein Snapshot existiert
**When** der Nutzer auf „CSV herunterladen" klickt
**Then** startet der Browser-Download einer `.csv`-Datei
**And** die CSV-Datei enthält alle Spalten und Zeilen des transformierten Datensatzes (vollständig, nicht nur die 1000 sichtbaren Zeilen)

**Given** `activeDataRunId` ist `null` (kein Run vorhanden)
**When** die Toolbar gerendert wird
**Then** ist der Download-Button ausgegraut und nicht klickbar

**Given** der Download-Endpunkt liefert einen 404
**When** der Browser den Download versucht
**Then** erhält der Nutzer eine Browser-seitige Fehlermeldung (Standard-Browser-Verhalten genügt)

---

## Implementierungsreihenfolge (empfohlen)

```
DV-1.1 (Snapshot speichern)
  └─► DV-1.2 (Paginierter Endpunkt)
        └─► DV-2.1 (Tab-Switcher)
              └─► DV-2.2 (Datentabelle + Infinite Scroll)
                    ├─► DV-2.3 (Spalten-Stats-Header)
                    ├─► DV-2.4 (Rollback-Integration)
                    └─► DV-2.5 (CSV-Download-Button)
  └─► DV-1.3 (CSV-Download-Endpunkt)  ──────────────────►  DV-2.5
```

**DV-1.1 ist harter Blocker** für alle anderen Stories — ohne Snapshot gibt es nichts anzuzeigen.
