# Frontend-Implementationsplan (MVP) — gysi-ml Assistant

> **Datum:** 2026-03-14
> **Autor:** Mary (Business Analyst)
> **Adressat:** John (PM) — PRD-Erstellung
> **Kontext:** Belegarbeit „gysi-ml“ (Codename: Gysi)

## 1. Zielbild (kurz)

Gysi ist ein konversationeller ML‑Assistent. Nutzer steuern eine ML‑Pipeline über natürliche Sprache. Das LLM erzeugt ausschließlich strukturierte Aktionen (JSON) und erklärt Ergebnisse; das Backend führt deterministisch aus, validiert strikt und speichert Versionen/History.

Das Frontend ist ein **leichtgewichtiges Web‑Chat‑Interface**, das:

- Nachrichten (User ↔ Assistant) anzeigt und sendet,
- Status/History der Pipeline in komprimierter Form sichtbar macht,
- Run‑Fortschritt und Artefakt‑Links (Plots/Reports) anzeigt.

## 2. Default‑Annahmen (für dieses Vorgehen verbindlich)

1. **Deployment:** lokal (Belegarbeit), keine Authentifizierung.
2. **Ausführung:** Runs sind **asynchron** (Backend liefert `job_id`/`run_id`), Frontend nutzt **Polling**.
3. **Spec‑Sichtbarkeit:** Spec wird **nicht als Roh‑JSON editiert**. Sichtbar ist **nur eine Kurz‑Zusammenfassung** (Version + Step‑Liste/Count + letzter Run).
4. **UX‑Scope:** **eine Seite** (Single Page), keine zusätzlichen Views/Modals/Filter/Settings.
5. **Spec‑Format (Backend‑Entscheidung):** Pipeline‑Spec ist **JSON**.

## 3. Nutzer & Kern‑Jobs (BA‑Sicht)

**Primärer Nutzer (Belegarbeit):** Entwickler/Analyst (Hannes) bzw. Prüfer*in, die nachvollziehbar sehen wollen:

- was gerade in der Pipeline aktiv ist,
- wie ich per Chat Änderungen auslöse (z.B. Missing‑Value‑Strategie ändern),
- welche Auswirkungen Änderungen haben (Metriken/Reports/Plots),
- wie ich kontrolliert zurückspringen kann (Undo / „2 Schritte zurück“).

## 4. MVP‑Scope

### 4.1 In Scope (MVP)

- Chat‑Eingabe + Chat‑History (aktuelle Session).
- Anzeige des **aktuellen Systemzustands** (Spec‑Version/kurzer Überblick, Run‑Status).
- Asynchroner Run‑Flow (Start → Running → Done/Failed) inkl. Polling.
- Anzeige von **Artefakt‑Referenzen** als klickbare Links (z.B. PNG/JSON/CSV).
- Fehlerbehandlung: Validierungsfehler (Action abgelehnt), Backend‑Fehler, Timeouts.

### 4.2 Out of Scope (später / explizit nicht im MVP)

- Voice (STT/TTS).
- Vollständiger Spec‑Editor im UI.
- Branching‑UI (mehrere Branches parallel).
- Hyperparameter‑Optimierung/HPO‑UI.
- Umfangreiche Dashboards/EDA‑Seiten.

## 5. Kern‑User‑Flows (End‑to‑End)

### Flow A — „Änderung anfordern“

1. User sendet Chat‑Nachricht (z.B. „Impute missing values mit Median“).
2. Backend (ggf. via LLM) übersetzt in Action/Spec‑Änderung.
3. Backend validiert (Schema + Guardrails) und wendet Änderung an.
4. Frontend zeigt Assistant‑Antwort + aktualisierten Status (neue Spec‑Version).

**Erfolg:** User sieht, dass die Änderung angekommen ist (neue Version/Step‑Übersicht) und was genau gemacht wurde (Kurzbeschreibung).

### Flow B — „Ausführung starten und Ergebnisse ansehen“

1. User sendet Chat‑Nachricht (z.B. „Führe die Pipeline aus“).
2. Backend startet Run und gibt `job_id`/`run_id` zurück.
3. Frontend pollt Run‑Status bis `done`/`failed`.
4. Frontend zeigt Run‑Summary (z.B. Kennzahlen) + Artefakt‑Links.

**Erfolg:** User kann Artefakte öffnen (Plot/Report) und sieht kompakte Ergebnisse im Chat.

### Flow C — „Undo / History“

1. User sendet Chat‑Nachricht (z.B. „Geh 2 Schritte zurück“).
2. Backend setzt aktive Spec‑Version zurück.
3. Frontend zeigt neue aktive Version + Hinweis, dass der Zustand zurückgesetzt wurde.

**Erfolg:** kontrolliertes exploratives Arbeiten, nachvollziehbar im UI.

## 6. UI‑Konzept (1 Seite, minimal)

### 6.1 Layout

**Single Page mit 2 Bereichen:**

- **Hauptbereich:** Chat (Message‑Liste + Composer)
- **Nebenbereich (Status‑Panel):**
  - aktive Spec‑Version (ID/Nummer)
  - kurze Step‑Übersicht (z.B. Anzahl Steps + Step‑Namen)
  - letzter Run (Status + Start/Ende + ggf. wichtigste Kennzahlen)
  - letzte Artefakte (Linkliste)

### 6.2 Anzeigeprinzip

- Der Chat bleibt „Quelle der Wahrheit“ für Interaktion.
- Status‑Panel ist **rein informativ** (keine extra Buttons im MVP).

## 7. Contract‑First: vorgeschlagene API‑Oberfläche (Backend ↔ Frontend)

> Hinweis: Backend‑Code ist aktuell Scaffold; dieser Contract ist ein **Vorschlag**, um Frontend parallel (mit Mocks) implementierbar zu machen.

### 7.1 Datenobjekte (minimal)

**ChatMessage**

- `id` (string)
- `role` (`user` | `assistant` | `system`)
- `content` (string)
- `ts` (ISO‑Zeit)
- optional `attachments[]` (Artefakt‑Refs oder strukturierte Summaries)

**SpecSummary**

- `spec_version_id` (string)
- `steps` (array von `{ step_type: string, enabled: boolean }`)
- optional `notes` (string)

**RunSummary**

- `run_id` (string)
- `status` (`queued` | `running` | `done` | `failed`)
- `started_at`, `finished_at` (ISO)
- optional `metrics` (key/value, z.B. `{ rmse: 123.4 }`)
- optional `artifacts[]` (Artefakt‑Refs)
- optional `error` (string)

**ArtifactRef**

- `artifact_id` (string)
- `label` (string)
- `media_type` (z.B. `image/png`, `application/json`)
- `href` (string; Backend‑URL)

**ValidationError**

- `type` = `validation_error`
- `message` (string)
- optional `details` (object)

### 7.2 Endpoints (MVP‑fähig)

1. `POST /api/chat`

Request:

```json
{
  "conversation_id": "optional-string",
  "message": "user text",
  "client_message_id": "uuid"
}
```

Response (synchroner Teil):

```json
{
  "conversation_id": "string",
  "assistant_message": {
    "id": "string",
    "role": "assistant",
    "content": "string",
    "ts": "2026-03-14T12:00:00Z"
  },
  "state": {
    "spec": { "spec_version_id": "v12", "steps": [{"step_type":"missing_values","enabled":true}] },
    "last_run": { "run_id": "r55", "status": "done" }
  },
  "job": {
    "job_id": "optional-string",
    "kind": "optional: run"
  },
  "errors": []
}
```

- Falls Backend eine Ausführung startet: `job.job_id` ist gesetzt.
- Falls Action/Spec ungültig: `errors` enthält `validation_error`, `assistant_message` erklärt kurz.

2. `GET /api/jobs/{job_id}` (Polling)

Response:

```json
{
  "job_id": "string",
  "status": "queued|running|done|failed",
  "run": {
    "run_id": "r56",
    "status": "done",
    "metrics": { "rmse": 123.4 },
    "artifacts": [
      { "artifact_id": "a1", "label": "Boxplot Outliers", "media_type": "image/png", "href": "/api/artifacts/a1" }
    ]
  }
}
```

3. `GET /api/artifacts/{artifact_id}`

- Liefert die Datei (z.B. PNG/JSON/CSV) direkt aus (oder via signierter URL, lokal aber nicht nötig).

4. Optional (nice‑to‑have, aber hilfreich fürs UI): `GET /api/state`

- Liefert `SpecSummary`, `last_run`, `recent_artifacts` ohne Chat.

### 7.3 Polling‑Regeln (Frontend)

- Polling‑Intervall: z.B. 500–1500ms (konfigurierbar), Backoff bei langer Laufzeit.
- Stop bei `done|failed`.
- Timeout‑UX: Wenn Polling > X Minuten, UI bleibt stabil, zeigt Hinweis „Run dauert länger als erwartet“.

## 8. Frontend‑State‑Machine (UX‑Zustände)

MVP muss mindestens sauber unterscheiden:

- `idle` (nichts passiert)
- `sending_message` (Request läuft)
- `validation_error` (Backend hat Action abgelehnt)
- `job_running` (Polling aktiv)
- `job_failed` (Run/Job Fehler)
- `job_done` (Ergebnis + Artefakte verfügbar)
- `backend_unreachable` (Netz/CORS/Server down)

Akzeptanz: Keine „hängenden“ Buttons/Spinners; jeder Zustand hat klare UI‑Rückmeldung.

## 9. Konkreter Implementations‑Plan (Milestones)

> Ziel: Frontend kann parallel zum Backend entstehen (Mock‑First), bleibt aber strikt Contract‑First.

### M0 — Projekt‑Setup (1 Tag)

**Deliverables**

- Frontend‑Projekt scaffold (Tech TBD; minimal: TypeScript + SPA)
- Dev‑Server + Env‑Config (Backend‑Base‑URL)
- Basis‑CI (optional) oder lokal: lint/build.

**Akzeptanzkriterien**

- `npm run dev` startet UI lokal.
- Ein einfacher Screen rendert.

**Abhängigkeiten**

- keine (Mock‑First).

### M1 — Chat UI + Mock‑Backend (1–2 Tage)

**Deliverables**

- Chat‑Layout (Message‑Liste, Composer, Senden mit Enter)
- Mock‑Responses aus Fixtures (z.B. JSON Dateien)
- Status‑Panel, befüllt aus Mock‑State

**Akzeptanzkriterien**

- User kann 5+ Nachrichten senden; UI bleibt performant.
- Validation‑Error kann simuliert und angezeigt werden.

### M2 — Backend‑Integration: `POST /api/chat` (1–2 Tage)

**Deliverables**

- Echter `POST /api/chat` Call
- Rendering von `assistant_message` + `state` (SpecSummary/last_run)
- Robuste Fehlerbehandlung (Backend down, 4xx/5xx)

**Akzeptanzkriterien**

- UI arbeitet ohne Codeänderung mit Mock oder echtem Backend (Switch über Env).

**Abhängigkeiten**

- Backend stellt Minimal‑Endpoint bereit (oder Stub‑Server).

### M3 — Async Runs: Polling `GET /api/jobs/{job_id}` (1–2 Tage)

**Deliverables**

- Polling‑Loop, Abbruch/Timeout, Backoff
- Anzeige Run‑Status im Status‑Panel
- Anzeige Artefakt‑Links (aus `run.artifacts`)

**Akzeptanzkriterien**

- Run wechselt sichtbar von running → done/failed.
- Artefakt‑Links sind klickbar.

**Abhängigkeiten**

- Backend Job/Run‑Status endpoint.

### M4 — History/Undo sichtbar machen (0.5–1 Tag)

**Deliverables**

- Anzeige aktive `spec_version_id`
- Chat zeigt systemische Rückmeldung bei Undo‑Aktion (als normale Assistant‑Message)

**Akzeptanzkriterien**

- Nach Undo ändert sich `spec_version_id` sichtbar.

### M5 — Hardening & Test (1 Tag)

**Deliverables**

- Edge‑Cases: sehr lange Messages, schnelle Mehrfach‑Sends, Polling bei Reload
- Leichte UI‑Tests (smoke) oder E2E‑smoke (optional)

**Akzeptanzkriterien**

- Keine kritischen UX‑Brüche bei Netzwerk‑Fehlern.

## 10. Risiken & Mitigation

- **Backend noch nicht implementiert:** Mock‑First + klarer Contract minimiert Blocker.
- **Divergenz Contract vs. Implementation:** Contract als Quelle der Wahrheit im Repo (z.B. `docs` oder OpenAPI) und frühe Integration M2.
- **Lange Runs / „UI hängt“:** asynchron + Polling + saubere Zustände.
- **Artefakt‑Handling:** nur Links im MVP; keine komplexe Preview‑UI.

## 11. Offene Punkte (für PRD / Engineering Sync)

- Finaler Frontend‑Stack (React/Vue/Svelte o.ä.) und Build‑Tooling.
- Einheitliche Error‑Semantik (Validation vs. Execution vs. Infra).
- Welche minimalen Kennzahlen (metrics) in Run‑Summary für Phase 1 verpflichtend sind.
- Konversation‑Persistenz: Session‑only vs. speicherbare Conversation‑IDs.

## 12. „Definition of Done“ (MVP Frontend)

MVP gilt als geliefert, wenn:

- User kann Nachrichten senden und Assistant‑Antworten sehen.
- UI zeigt aktive Spec‑Version (Summary) und letzten Run‑Status.
- UI kann asynchrone Runs verfolgen (Polling) und Artefakt‑Links darstellen.
- Validierungsfehler und Backend‑Fehler werden verständlich angezeigt.
- Alles läuft lokal ohne Auth und ohne zusätzliche Seiten.
