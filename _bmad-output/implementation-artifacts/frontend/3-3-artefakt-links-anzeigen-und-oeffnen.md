# Story 3.3: Artefakt-Links anzeigen und öffnen

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Als ein Nutzer,
möchte ich Artefakte als klickbare Linkliste (Label + Media-Type) im Chat-Ergebnis und im Status-Panel öffnen können,
damit ich Plots/Reports direkt im Browser ansehen kann, ohne URLs manuell zusammenbauen zu müssen.

## Acceptance Criteria (BDD)

1. **Given** die Response enthält `artifacts[]` mit gültigen Einträgen
   **When** die `ResultCard` im Chat gerendert wird
   **Then** sehe ich jeden Artefakt-Eintrag als klickbaren Link (Label + Media-Type)
   **And** ein Klick öffnet das Artefakt in einem neuen Browser-Tab

2. **Given** ein Artefakt hat eine ungültige oder leere URL
   **When** die `ResultCard` gerendert wird
   **Then** wird das Artefakt als Text (nicht klickbar) angezeigt mit Hinweis „(ungültige URL)"

3. **Given** das Backend liefert `artifacts[]` OHNE `href`-Feld (nur `artifact_id`)
   **When** `runApi.ts` die Response parst
   **Then** wird die URL automatisch als `/v1/artifacts/{artifact_id}` konstruiert

4. **Given** die Artefakt-URL ein unsicheres Protokoll hat (z.B. `javascript:`, `data:`)
   **When** die URL sanitiert wird
   **Then** wird der Link NICHT gerendert — stattdessen Fallback auf Nur-Text mit Hinweis

5. **Given** Mock-Modus ist aktiv
   **When** eine Result-Message mit Artefakten gerendert wird
   **Then** sind die Mock-Artefakte als klickbare Links sichtbar (z.B. `/favicon.svg`)

6. **Given** die `ResultCard` Artefakt-Links rendert
   **When** ich mit der Maus über einen Link hovere
   **Then** sehe ich visuelles Feedback (Unterstreichung, Cursor-Pointer)

7. **Given** alle vorherigen Stories (3.1, 3.2) und Epics (1, 2) implementiert sind
   **When** alle Tests ausgeführt werden
   **Then** sind alle bestehenden Tests weiterhin grün (keine Regressionen)

## Tasks / Subtasks

- [x] **T1** — URL-Sanitierung als shared Utility extrahieren (AC: #4)
  - [x] T1.1: Datei `frontend/src/utils/sanitizeArtifactUrl.ts` erstellen — Funktion aus `StatusPanel.tsx` extrahieren
  - [x] T1.2: Unit-Tests in `frontend/src/utils/sanitizeArtifactUrl.test.ts` — Testfälle: leere URL, relative URL (`/path`), absolute HTTP(S), `javascript:`-Protokoll, `data:`-Protokoll, Leerzeichen-Trimming
  - [x] T1.3: `StatusPanel.tsx` auf Import von `sanitizeArtifactUrl` umstellen (lokale Funktion entfernen)

- [x] **T2** — `parseArtifacts` in `runApi.ts` erweitern: URL-Fallback (AC: #3)
  - [x] T2.1: Wenn weder `href` noch `url` vorhanden, aber `artifact_id` gesetzt → URL als `/v1/artifacts/${artifact_id}` konstruieren
  - [x] T2.2: Bestehende Tests in `runApi.test.ts` erweitern: Testfall für fehlende `href`/`url` mit vorhandener `artifact_id`
  - [x] T2.3: Bestehende Tests prüfen — keine Regression

- [x] **T3** — `ResultCard.tsx` aktualisieren: Artefakte als klickbare Links (AC: #1, #2, #6)
  - [x] T3.1: `sanitizeArtifactUrl` importieren
  - [x] T3.2: Artefakt-`<li>` zu `<a href={safeUrl} target="_blank" rel="noreferrer">` umbauen
  - [x] T3.3: Fallback bei ungültiger URL: `<span>` mit Label + „(ungültige URL)" statt Link
  - [x] T3.4: Media-Type Badge weiterhin als `<span className="resultArtifactType">` anzeigen

- [x] **T4** — CSS für Artefakt-Links in `App.css` ergänzen (AC: #6)
  - [x] T4.1: `.resultArtifactLink` — `color`, `text-decoration`, `cursor: pointer`
  - [x] T4.2: `.resultArtifactLink:hover` — `text-decoration: underline`
  - [x] T4.3: `.resultArtifactInvalid` — visueller Hinweis (opacity, kein Cursor)

- [x] **T5** — Unit-Tests für `ResultCard` aktualisieren (AC: #1, #2, #5)
  - [x] T5.1: Test: Artefakte werden als `<a>`-Tags mit `target="_blank"` gerendert
  - [x] T5.2: Test: Artefakt-Links haben korrekte `href`-Attribute
  - [x] T5.3: Test: Ungültige URLs werden als Nur-Text mit Hinweis gerendert
  - [x] T5.4: Test: Bestehende Tests (Status-Label, Metriken, Message) bleiben grün

- [x] **T6** — Regressionstests (AC: #7)
  - [x] T6.1: Alle bestehenden Tests ausführen → alle grün
  - [x] T6.2: `StatusPanel.test.tsx` prüfen — Artefakt-Links funktionieren weiterhin nach Utility-Extraktion
  - [ ] T6.3: Manueller Smoke-Test (durch Hannes): Mock-Modus → Nachricht → Confirm → Polling → ResultCard mit klickbaren Artefakt-Links

## Dev Notes

### Backend-API-Contract (kritisch!)

**Artefakt-Endpoint:** `GET /v1/artifacts/{artifact_id}`

- Response: Binary File (`FileResponse`) mit `Content-Type: image/png`
- `200 OK` — Datei zurückgegeben
- `404 Not Found` — Artefakt-ID nicht gefunden oder Datei fehlt
- `403 Forbidden` — Path-Traversal-Schutz (Datei außerhalb `artifacts_path`)

**RunDetailResponse enthält KEIN `href`-Feld:**

```json
{
  "artifacts": [
    {
      "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "plot",
      "created_at": "2026-03-20T10:30:00Z"
    }
  ]
}
```

⚠️ **Frontend muss URL selbst konstruieren:** `/v1/artifacts/${artifact_id}`

[Source: backend/src/gysi_ml/api/routes/artifacts.py]
[Source: backend/src/gysi_ml/api/schemas.py — ArtifactSummary]

### Aktuelles Problem in `parseArtifacts`

`runApi.ts > parseArtifacts()` prüft `item.href` → `item.url` → `''`. Da das Backend weder `href` noch `url` liefert, wird `url = ''` gesetzt und das Artefakt **übersprungen** (`if (id && url)`). Im Mock-Modus funktioniert es, weil `result.json` explizit `url` setzt.

**Fix:** Wenn kein `href`/`url` vorhanden, aber `artifact_id` gesetzt → URL als `/v1/artifacts/${artifact_id}` konstruieren.

[Source: frontend/src/api/runApi.ts L53-66]

### URL-Sanitierung (Security)

`StatusPanel.tsx` enthält bereits `sanitizeArtifactUrl()` — diese Funktion muss nach `utils/` extrahiert werden, damit `ResultCard` sie ebenfalls nutzen kann. Die Funktion:

- Leere URLs → `null`
- Relative Pfade (`/...`) → gültig
- HTTP(S) absolute URLs → gültig
- Andere Protokolle (`javascript:`, `data:`, `file:`) → `null` (rejected)

[Source: frontend/src/components/StatusPanel.tsx L42-62]

### Vorhandene Typen (kein Änderungsbedarf)

```typescript
// frontend/src/types.ts
export interface ArtifactRef {
  id: string
  label: string
  url: string
  media_type: string
}
```

### Datenfluss (was bereits existiert)

```
GET /v1/sessions/{sid}/runs/{rid}
  → fetchRunStatus() → parseArtifacts() → ArtifactRef[]
  → useRunPolling → RUN_POLL_SUCCEEDED
  → state.artifacts + state.lastRun.artifacts
  → ResultCard (Chat) ← STORY 3.3: Links klickbar machen
  → StatusPanel (Sidebar) ← bereits klickbar (Story 3.1)
```

### Mock-Fixture (vorhanden, nicht ändern)

```json
// frontend/src/fixtures/result.json — Artefakte mit expliziter URL
{
  "artifacts": [
    { "id": "plot-1", "label": "Plot (Placeholder)", "url": "/favicon.svg", "media_type": "image/svg+xml" },
    { "id": "metrics-1", "label": "Metrics (JSON)", "url": "/mock/metrics.json", "media_type": "application/json" }
  ]
}
```

### Komponenten-Pattern

- `ResultCard` bleibt reiner Presentational-Component (keine Side-Effects außer Link-Navigation)
- URL-Sanitierung als pure Function in `utils/` — testbar ohne DOM
- CSS folgt bestehendem BEM-light-Pattern: `.resultArtifactLink`, `.resultArtifactInvalid`

### Scope-Abgrenzung (was NICHT Teil dieser Story ist)

- **Inline-Preview von Bildern/Plots** → ggf. Future Epic
- **Download-Button mit Fortschrittsanzeige** → kein Scope (Browser-nativer Download reicht)
- **Backend-Änderungen** → kein Scope (Endpoint existiert bereits)
- **Polling-Hook oder Reducer ändern** → nicht nötig (Daten kommen bereits korrekt an)

### References

- [Source: _bmad-output/planning-artifacts/frontend/epics.md — Story 3.3 Definition]
- [Source: _bmad-output/implementation-artifacts/frontend/3-1-run-polling-mit-backoff-und-long-run-hinweis.md — Vorgänger]
- [Source: _bmad-output/implementation-artifacts/frontend/3-2-result-message-status-und-metriken-rendern.md — Vorgänger]
- [Source: backend/src/gysi_ml/api/routes/artifacts.py — Artefakt-Endpoint]
- [Source: backend/src/gysi_ml/api/schemas.py — ArtifactSummary Schema]
- [Source: frontend/src/api/runApi.ts — parseArtifacts (URL-Konstruktion)]
- [Source: frontend/src/components/ResultCard.tsx — Hauptkomponente]
- [Source: frontend/src/components/ResultCard.test.tsx — Bestehende Tests]
- [Source: frontend/src/components/StatusPanel.tsx — sanitizeArtifactUrl Vorlage]
- [Source: frontend/src/types.ts — ArtifactRef, ResultResponse]
- [Source: frontend/src/fixtures/result.json — Mock-Daten]
- [Source: frontend/src/App.css — Bestehende ResultCard-Styles]

## Dev Agent Record

### Implementiert

- **T1**: `sanitizeArtifactUrl` als shared Utility nach `frontend/src/utils/sanitizeArtifactUrl.ts` extrahiert. 10 Unit-Tests in `sanitizeArtifactUrl.test.ts`. `StatusPanel.tsx` importiert jetzt aus `utils/`.
- **T2**: `parseArtifacts` in `runApi.ts` — URL-Fallback: wenn weder `href` noch `url` vorhanden, aber `artifact_id` gesetzt → URL wird als `/v1/artifacts/${artifact_id}` konstruiert. Neuer Testfall in `runApi.test.ts`.
- **T3**: `ResultCard.tsx` — Artefakte als klickbare `<a>`-Tags mit `target="_blank" rel="noreferrer"`. Ungültige URLs werden als `<span>` mit Hinweis „(ungültige URL)" gerendert. Media-Type Badge bleibt erhalten.
- **T4**: CSS-Klassen `.resultArtifactLink`, `.resultArtifactLink:hover`, `.resultArtifactInvalid` in `App.css` ergänzt.
- **T5**: 3 neue Tests in `ResultCard.test.tsx` (klickbare Links, korrekte href, ungültige URL als Nur-Text).
- **T6**: Alle 150 Tests grün — keine Regressionen. T6.3 (manueller Smoke-Test) offen für Hannes.

### Entscheidungen

- URL-Sanitierung als pure Function ohne externen State — wiederverwendbar für StatusPanel und ResultCard
- `rel="noreferrer"` statt `rel="noopener noreferrer"` — reicht für security, `noreferrer` impliziert `noopener`
- Kein Typ-Änderungsbedarf: `ArtifactRef` Interface bleibt unverändert

### File List

| Datei | Aktion |
| --- | --- |
| `frontend/src/utils/sanitizeArtifactUrl.ts` | NEU |
| `frontend/src/utils/sanitizeArtifactUrl.test.ts` | NEU |
| `frontend/src/api/runApi.ts` | GEÄNDERT |
| `frontend/src/api/runApi.test.ts` | GEÄNDERT |
| `frontend/src/components/ResultCard.tsx` | GEÄNDERT |
| `frontend/src/components/ResultCard.test.tsx` | GEÄNDERT |
| `frontend/src/components/StatusPanel.tsx` | GEÄNDERT |
| `frontend/src/App.css` | GEÄNDERT |
