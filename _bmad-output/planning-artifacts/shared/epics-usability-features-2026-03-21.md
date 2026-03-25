---
stepsCompleted: [1, 2, 3, 4]
status: complete
completedAt: '2026-03-21'
inputDocuments:
  - _bmad-output/planning-artifacts/backend/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/shared/feature-backlog-usability-tests-2026-03-21.md
  - _bmad-output/planning-artifacts/frontend/ux-design-specification.md
date: '2026-03-21'
scope: 'Feature-Backlog Usability-Tests 2026-03-21 — 4 neue Backend-Features'
---

# gysi-ml - Epic Breakdown (Usability Features 2026-03-21)

## Overview

Dieses Dokument enthält den vollständigen Epic- und Story-Breakdown für die **4 neuen Backend-Features** aus den Usability-Tests vom 2026-03-21. Die bestehenden Epics (FR1–FR43) sind in `_bmad-output/planning-artifacts/backend/epics.md` dokumentiert.

**Scope:** F1 Onboarding/Slash-Commands · F2 Datensatz-Profilierung · F3 Schrittweise Ausführung · F4 Pipeline-Versionsbaum

---

## Requirements Inventory

### Functional Requirements

FR-OB1: Welcome-Message bei Session-Erstellung — Response-Feld `welcome_message` + als `assistant`-Message persistiert
FR-OB2: Slash-Command-Erkennung in `POST /messages` — ohne LLM-Aufruf, unbekannte Commands → Fehlermeldung + Liste
FR-OB3: `/help`-Command — kategorisierte Funktionsübersicht (Daten, Preprocessing, Modellierung, Pipeline, Grenzen); `/help <thema>` filtert
FR-OB4: `/overview`-Command — triggert Datensatz-Profilierung (FR-DO1) ohne LLM
FR-OB5: `/status`-Command — aktuelle Spec-Version, Anzahl Runs, letzter Run-Status + Metriken, aktive Steps
FR-DO1: Datensatz-Profilierung ausführen — Grundinfos, Spalten-Übersicht, fehlende Werte, Statistiken, Head, Unique-Verteilung
FR-DO2: LLM-Empfehlungen basierend auf echten Profiling-Daten (Auffälligkeiten, nächste Schritte)
FR-DO3: Profilierung nach Preprocessing — Vorher/Nachher-Vergleich auf Sitzungs-State
FR-SE1: Selektive Step-Bestätigung — optionales `confirmed_steps`-Array in `POST /confirm`; fehlend = alle Steps (Rückwärtskompatibilität)
FR-SE2: Step-by-Step-Ausführungsmodus — `mode: "step_by_step"` in `POST /confirm`; nur erster Step, Response-Typ `step_result`
FR-SE3: Step-by-Step Fortführung — nächster Step aufbauend auf Daten des vorherigen; letzter Step → Gesamtzusammenfassung
FR-SE4: Step-by-Step Abbruch/Modifikation — per Chat-Nachricht; Abbruch → Zusammenfassung der bisherigen Steps
FR-VB1: Parent-Child-Tracking in `spec_versions` — `parent_spec_id` + `change_summary` per DB-Migration
FR-VB2: `GET /v1/sessions/{id}/spec/tree` — vollständiger Versionsbaum als JSON mit `active_spec_id`, `has_runs`, `last_run_status`
FR-VB3: Change-Summary-Generierung (Spec-Diff) — hinzugefügte/entfernte Steps, geänderte Parameter, Aktivierung/Deaktivierung
FR-VB4: Rollback auf frühere Version — Kopie als neue Version (kein Überschreiben), `parent_spec_id` = aktuelle, `change_summary = "Rollback auf vX"`
FR-VB5: Branching im Versionsbaum — natürlich aus Parent-Child-Tracking, kein explizites Branch-Konzept

### Non-Functional Requirements

NFR-P4: API-Endpunkte ohne ML-Berechnung antworten in < 500 ms (gilt für Slash-Commands, `/spec/tree`, Rollback)
NFR-R1: Kein Absturz bei ungültigen Nutzereingaben — strukturierte Fehler-Response (gilt für unbekannte Slash-Commands, leeres `confirmed_steps`, ungültige `target_spec_id`)
NFR-T1: Test-Coverage ≥ 85% auf neuen Modulen (`command_service`, `profiling_service`, `step_state_repository`, `spec_diff`)
NFR-S1: LLM-Output NIE direkt ausgeführt — CommandService bypassed LLM vollständig
NFR-M3: Help-Texte in `configs/help_texts.yaml`, nicht hartcodiert im Code

### Additional Requirements (Architecture)

- **DB-Migration zuerst (Story 0):** `step_states`-Tabelle (NEU) + `ALTER TABLE spec_versions ADD COLUMN parent_spec_id` + `change_summary` — Pflicht-Voraussetzung für alle anderen Features
- **Neues Modul:** `services/command_service.py` — Eigenständige Klasse, aufrufbar aus `MessageService`, isoliert testbar
- **Neues Modul:** `services/profiling_service.py` — `@functools.lru_cache` auf Rohdatensatz-Laden; Post-Preprocessing-Profiling immer frisch
- **Neues Modul:** `persistence/step_state_repository.py` — CRUD für `step_states`-Tabelle
- **Neue Utility:** `spec/spec_diff.py` — reine Funktion `spec_diff(old, new) -> str`, kein Service, keine Klasse
- **Neue Konfig:** `configs/help_texts.yaml` — Help-Inhalte für `/help`-Command
- **Neuer Endpunkt:** `api/routes/rollback.py` — `POST /v1/sessions/{id}/rollback`
- **Rückwärtskompatibilität:** `POST /confirm` ohne `confirmed_steps`/`mode` → verhält sich wie bisher

### UX Design Requirements

UX-DR1: Proposal-Card erweitern um optionale Step-Checkboxen — Nutzer kann einzelne Steps vor dem Confirm an-/abwählen (Selektive Bestätigung, F3/FR-SE1)
UX-DR2: Step-by-Step-Fortschrittsanzeige — nach jedem Step: `step_result`-Nachricht mit Zusammenfassung des ausgeführten Steps + verbleibende Steps als neue Mini-Proposal-Card
UX-DR3: Versionsbaum-Panel (rechtes Seitenpanel) — Baumstruktur aller Spec-Versionen; aktive Version hervorgehoben; Knoten zeigt `change_summary` + `last_run_status`
UX-DR4: Rollback-Interaktion — Klick auf Versionsbaum-Knoten → Rollback-Bestätigung + `POST /rollback` (kein stiller Rollback)
UX-DR5: Welcome-Message als erste Chat-Nachricht — wird beim Session-Start direkt als `assistant`-Bubble angezeigt (aus `welcome_message`-Feld in Session-Response)

### FR Coverage Map

| FR | Epic | Story |
|----|------|-------|
| FR-OB1 | Epic 6 | Story 6.1 |
| FR-OB2 | Epic 6 | Story 6.2 |
| FR-OB3 | Epic 6 | Story 6.2 |
| FR-OB4 | Epic 6 | Story 6.2 |
| FR-OB5 | Epic 6 | Story 6.2 |
| FR-DO1 | Epic 7 | Story 7.1 |
| FR-DO2 | Epic 7 | Story 7.2 |
| FR-DO3 | Epic 7 | Story 7.3 |
| FR-SE1 | Epic 9 | Story 9.2 |
| FR-SE2 | Epic 9 | Story 9.3 |
| FR-SE3 | Epic 9 | Story 9.3 |
| FR-SE4 | Epic 9 | Story 9.3 |
| FR-VB1 | Epic 5 | Story 5.1 |
| FR-VB2 | Epic 8 | Story 8.2 |
| FR-VB3 | Epic 8 | Story 8.1 |
| FR-VB4 | Epic 8 | Story 8.3 |
| FR-VB5 | Epic 8 | Story 8.3 |
| UX-DR1 | Epic 9 | Story 9.2 |
| UX-DR2 | Epic 9 | Story 9.3 |
| UX-DR3 | Epic 8 | Story 8.2 |
| UX-DR4 | Epic 8 | Story 8.3 |
| UX-DR5 | Epic 6 | Story 6.1 |

## Epic List

- Epic 5: Fundament — DB-Migration & Infrastruktur
- Epic 6: Onboarding-System (Welcome-Message + Slash-Commands)
- Epic 7: Datensatz-Profilierung
- Epic 8: Pipeline-Versionsbaum & Rollback
- Epic 9: Schrittweise Ausführung (Selektiv + Step-by-Step)

---

## Epic 5: Fundament — DB-Migration & Infrastruktur

**Epic Goal:** Alle Datenbank-Schema-Änderungen, die als Voraussetzung für die 4 neuen Features benötigt werden, stabil und rückwärtskompatibel umsetzen. Kein neues Feature ist implementierbar ohne diesen Schritt.

**Abhängigkeit:** Keine — muss zuerst implementiert werden.

### Story 5.1: DB-Migration — `step_states`-Tabelle und `spec_versions`-Erweiterung

Als **Entwickler**,
möchte ich eine neue `step_states`-Tabelle und erweiterte `spec_versions`-Spalten in SQLite anlegen,
damit die Step-by-Step-Ausführung (F3) und der Versionsbaum (F4) persistiert werden können.

**Acceptance Criteria:**

**Given** die Anwendung startet zum ersten Mal nach der Migration
**When** `persistence/schema.py` ausgeführt wird
**Then** existiert die Tabelle `step_states` mit den Spalten: `state_id TEXT PK`, `session_id TEXT FK`, `proposal_id TEXT`, `remaining_steps_json TEXT`, `completed_steps_json TEXT`, `confirmed_indices_json TEXT`, `created_at TEXT`, `last_updated TEXT`

**Given** eine bestehende DB mit `spec_versions`-Tabelle
**When** die Migration läuft
**Then** hat `spec_versions` zwei neue Spalten: `parent_spec_id TEXT REFERENCES spec_versions(spec_id)` und `change_summary TEXT`
**And** bestehende Zeilen haben `parent_spec_id = NULL` und `change_summary = NULL` (keine Datenverluste)

**Given** die Migration läuft auf einer frischen DB (kein vorheriger State)
**When** Schema angelegt wird
**Then** werden beide neuen Strukturen korrekt erstellt

**Given** die Migration läuft ein zweites Mal (Idempotenz)
**When** Schema-Initialisierung erneut ausgeführt wird
**Then** schlägt kein Fehler auf (IF NOT EXISTS / try-except für ALTER TABLE)

**Technische Hinweise:**
- `ALTER TABLE spec_versions ADD COLUMN` in `persistence/schema.py` mit try/except für Idempotenz
- `CREATE TABLE IF NOT EXISTS step_states` in `persistence/schema.py`
- Kein DataFrame in `step_states` — nur Metadaten als JSON-Strings

---

## Epic 6: Onboarding-System (Welcome-Message + Slash-Commands)

**Epic Goal:** Neue und wiederkehrende Nutzer bekommen beim Session-Start eine strukturierte Begrüßung und können per Slash-Commands ohne LLM-Aufruf Hilfe, Datensatz-Überblick und Session-Status abfragen.

**Abhängigkeit:** Epic 5 (DB-Migration, für `step_states` falls Slash-Commands den State benötigen — primär für `/status`).

### Story 6.1: Welcome-Message bei Session-Erstellung

Als **Nutzer**,
möchte ich beim Erstellen einer neuen Session automatisch eine strukturierte Willkommensnachricht erhalten,
damit ich sofort weiß, was das System kann, wie ich interagieren soll und wie ich Hilfe bekomme.

**Acceptance Criteria:**

**Given** ein Nutzer ruft `POST /v1/sessions` auf
**When** die Session erfolgreich erstellt wird
**Then** enthält die Response ein Feld `welcome_message: str` mit einer nicht-leeren Begrüßung
**And** die Begrüßung enthält: mindestens eine Kurzanleitung, Beispiel-Prompts, Hinweis auf `/help` und `/overview`
**And** die Welcome-Message ist im Backend generiert (aus `configs/help_texts.yaml` oder äquivalent) — nicht im Frontend hartcodiert

**Given** die Session wurde erstellt
**When** der Message-History der Session abgerufen wird
**Then** existiert die Welcome-Message als erste Message mit `role: "assistant"`
**And** der Inhalt entspricht dem `welcome_message`-Feld aus der Session-Response (gleicher Text)

**Given** das Frontend empfängt die Session-Response
**When** die neue Session angezeigt wird
**Then** wird `welcome_message` als erste Chat-Nachricht (assistant-Bubble) angezeigt (UX-DR5)
**And** kein zweiter API-Call zum Laden der Welcome-Message ist nötig

**Technische Hinweise:**
- `CreateSessionResponse` in `api/schemas.py` um `welcome_message: str` erweitern
- Welcome-Text aus `configs/help_texts.yaml` laden (Schlüssel `welcome_message`)
- Welcome-Message als `role: assistant` in `messages`-Tabelle beim Session-Create-Schritt persistieren

### Story 6.2: Slash-Command-Router mit `/help`, `/overview`, `/status`

Als **Nutzer**,
möchte ich Slash-Commands (`/help`, `/overview`, `/status`) über den normalen Chat-Endpunkt senden können,
damit ich ohne Umwege strukturierte Systeminformationen bekomme — ohne LLM-Aufruf und ohne extra Endpunkte.

**Acceptance Criteria:**

**Given** ein Nutzer sendet eine Nachricht, die mit `/` beginnt, an `POST /v1/sessions/{id}/messages`
**When** das Backend die Nachricht verarbeitet
**Then** erkennt `CommandService` den Slash-Command und verarbeitet ihn **ohne LLM-Aufruf**
**And** die Response enthält eine strukturierte Antwort als `type: "assistant"`

**Given** der Nutzer sendet `/help`
**When** `CommandService.handle_slash_command("/help")` aufgerufen wird
**Then** gibt das System eine kategorisierte Übersicht zurück mit Abschnitten: Daten erkunden, Preprocessing, Modellierung, Pipeline-Verwaltung, Grenzen
**And** der Inhalt kommt aus `configs/help_texts.yaml` — keine Hartcodierung im Python-Code

**Given** der Nutzer sendet `/help preprocessing`
**When** der Command verarbeitet wird
**Then** gibt das System nur die Preprocessing-Kategorie zurück

**Given** der Nutzer sendet `/overview`
**When** der Command verarbeitet wird
**Then** delegiert `CommandService` an `ProfilingService` (FR-DO1) und gibt das Profiling-Ergebnis zurück
**And** kein LLM-Aufruf findet statt

**Given** der Nutzer sendet `/status`
**When** der Command verarbeitet wird
**Then** gibt das System zurück: aktuelle Spec-Version (oder „Keine Pipeline konfiguriert"), Anzahl Runs, letzter Run-Status + Metriken (falls vorhanden), aktive Steps

**Given** der Nutzer sendet einen unbekannten Command (z.B. `/foo`)
**When** der Command verarbeitet wird
**Then** gibt das Backend eine Fehlermeldung zurück mit der Liste verfügbarer Commands
**And** kein Absturz, keine 500-Exception

**Given** Slash-Command-Responses
**When** die Session-History abgerufen wird
**Then** sind alle Slash-Command-Antworten als `role: "assistant"`-Messages persistiert (vollständiger Gesprächsverlauf)

**Technische Hinweise:**
- Neue Klasse `services/command_service.py`: `is_slash_command(content) -> bool` + `handle(content, session_id) -> str`
- `MessageService` prüft `is_slash_command()` vor LLM-Aufruf
- `KNOWN_COMMANDS = ["/help", "/overview", "/status"]`
- Help-Texte in `configs/help_texts.yaml` als YAML-Mapping

---

## Epic 7: Datensatz-Profilierung

**Epic Goal:** Nutzer können jederzeit einen realen, strukturierten Überblick über den Bike-Datensatz abrufen — sowohl über den Rohdatensatz als auch über den Zustand nach Preprocessing-Schritten. Das LLM erhält Profiling-Daten als Kontext für kontextualisierte Empfehlungen.

**Abhängigkeit:** Epic 5 (DB-Migration), Epic 6 (CommandService für `/overview`-Routing).

### Story 7.1: Rohdatensatz-Profilierung (ProfilingService)

Als **Nutzer**,
möchte ich über `/overview` oder natürliche Sprache einen vollständigen statistischen Überblick über den Bike-Datensatz erhalten,
damit ich informierte Entscheidungen über Preprocessing-Schritte treffen kann.

**Acceptance Criteria:**

**Given** der Nutzer sendet `/overview` oder ein natürlichsprachlicher Prompt löst `action_type: "dataset_overview"` aus
**When** das Backend `ProfilingService.profile_raw()` aufruft
**Then** enthält die Response alle folgenden Abschnitte:
  - Grundinfos: Zeilen-/Spaltenanzahl, Datensatzname
  - Spalten-Übersicht: Name, dtype, Non-Null-Count pro Spalte
  - Fehlende Werte: Spalte, Anzahl fehlend, % fehlend (sortiert nach Häufigkeit)
  - Statistische Zusammenfassung: Min, Max, Mean, Median, Std für numerische Spalten
  - Erste 5 Zeilen als tabellarische Darstellung
  - Unique-Wert-Verteilung (Kardinalität) pro Spalte

**Given** das Profiling des Rohdatensatzes wurde bereits einmal berechnet
**When** ein zweiter `/overview`-Aufruf kommt
**Then** wird das Ergebnis aus dem `@lru_cache` zurückgegeben (kein erneutes CSV-Laden/Berechnen)

**Given** die Anwendung startet neu
**When** `/overview` zum ersten Mal aufgerufen wird
**Then** wird der Cache neu befüllt (cold start ist toleriert)

**Technische Hinweise:**
- `services/profiling_service.py` mit `@functools.lru_cache` auf `_load_and_profile_raw()`
- Rohdatensatz-Profiling: pandas `df.info()`, `df.describe()`, `df.isnull().sum()`, `df.nunique()`, `df.head(5)`
- Kein Spec-Eingriff — Profiling ändert keine Pipeline-Spec

### Story 7.2: LLM-Kontext-Injection für Profiling-Empfehlungen

Als **Nutzer**,
möchte ich nach einem Datensatz-Überblick kontextualisierte Empfehlungen vom LLM erhalten,
damit das LLM auf echten Daten basierte Hinweise zu Auffälligkeiten und nächsten Schritten geben kann.

**Acceptance Criteria:**

**Given** der Nutzer fragt nach einem Datensatz-Überblick (per natürlicher Sprache, kein Slash-Command)
**When** das LLM angefragt wird
**Then** enthält der LLM-Prompt einen kompakten `## Datensatz-Profil`-Block mit den Profiling-Ergebnissen
**And** das LLM generiert Empfehlungen zu: Auffälligkeiten (z.B. hohe Korrelation), vorgeschlagene nächste Schritte, Besonderheiten

**Given** kein Profiling-Ergebnis vorhanden (erste Session, kein Profiling ausgelöst)
**When** LLM-Prompt zusammengestellt wird
**Then** fehlt der Profiling-Block im Prompt (kein leerer Block, kein Fehler)

**Technische Hinweise:**
- `llm/prompts.py`: optionaler `if profiling_result: context += f"\n\n## Datensatz-Profil\n{...}"` Block
- `ProfilingResult.to_compact_str()` — kompakte Darstellung für Prompt-Injection (kein voller DataFrame-Output)

### Story 7.3: Post-Preprocessing-Profilierung (Vorher/Nachher)

Als **Nutzer**,
möchte ich nach ausgeführten Preprocessing-Schritten einen aktuellen Datensatz-Überblick abrufen können,
damit ich den Effekt der Transformationen sehe (z.B. „3 Duplikate entfernt, 17.376 Zeilen verbleiben").

**Acceptance Criteria:**

**Given** der Nutzer hat mindestens einen Preprocessing-Step ausgeführt (Run vorhanden)
**When** der Nutzer `/overview` oder einen Profiling-Prompt sendet
**Then** zeigt das System den Zustand des Datensatzes **nach** den ausgeführten Transformationen
**And** enthält die Antwort einen Vorher/Nachher-Vergleich: z.B. „Vorher: 17.379 Zeilen → Nachher: 17.376 Zeilen"

**Given** kein Run in der Session vorhanden
**When** Profiling angefragt wird
**Then** wird das Rohdatensatz-Profiling zurückgegeben (kein Fehler, kein leerer Response)

**Technische Hinweise:**
- `ProfilingService.profile_after_steps(session_id)` — liest abgeschlossene Steps aus DB, wendet sie auf Bike-CSV an, erstellt frisches Profiling (kein Cache hier — sessionspezifisch)
- CommandService erkennt, ob eine Session bereits Runs hat, und wählt entsprechende Profiling-Methode

---

## Epic 9: Schrittweise Ausführung (Selektiv + Step-by-Step)

**Epic Goal:** Nutzer können vor der Ausführung einzelne Steps aus einem Proposal abwählen (selektive Bestätigung) und optional im Step-by-Step-Modus Schritt für Schritt vorgehen — mit Ergebnissichtung und Entscheidung nach jedem Step. Dies ist der didaktische Kern der Belegarbeit.

**Abhängigkeit:** Epic 5 (DB-Migration für `step_states`-Tabelle), Epic 8 (Spec-Diff für `change_summary`).

### Story 9.1: `StepStateRepository` — Persistenz für Step-by-Step-State

Als **Entwickler**,
möchte ich CRUD-Operationen für den Step-by-Step-State in der `step_states`-Tabelle,
damit der Fortschritt einer Step-by-Step-Session über HTTP-Requests hinweg erhalten bleibt.

**Acceptance Criteria:**

**Given** ein Step-by-Step-Vorgang startet
**When** `StepStateRepository.create(state)` aufgerufen wird
**Then** ist der State in `step_states` mit allen Feldern persistiert: `state_id`, `session_id`, `proposal_id`, `remaining_steps_json`, `completed_steps_json`, `confirmed_indices_json`, `created_at`, `last_updated`

**Given** ein State existiert
**When** `StepStateRepository.get_by_session(session_id)` aufgerufen wird
**Then** wird der State deserialisiert zurückgegeben (JSON-Felder als Python-Objekte)

**Given** ein Step abgeschlossen wurde
**When** `StepStateRepository.update(state)` aufgerufen wird
**Then** sind `remaining_steps_json`, `completed_steps_json` und `last_updated` aktualisiert

**Given** ein Step-by-Step-Vorgang abgeschlossen oder abgebrochen wird
**When** `StepStateRepository.delete(state_id)` aufgerufen wird
**Then** ist der State aus `step_states` entfernt

**Technische Hinweise:**
- `persistence/step_state_repository.py` — analog zu bestehenden Repositories
- DataFrame wird **nicht** persistiert — bei Fortführung deterministisch aus Bike-CSV + `completed_steps` neu berechnet

### Story 9.2: Selektive Step-Bestätigung (`confirmed_steps`)

Als **Nutzer**,
möchte ich vor der Ausführung eines Proposals einzelne Steps an- oder abwählen können,
damit nur die von mir ausgewählten Schritte ausgeführt werden — ohne den restlichen Flow zu ändern.

**Acceptance Criteria:**

**Given** ein Proposal mit mehreren Steps existiert
**When** der Nutzer `POST /v1/sessions/{id}/confirm` mit `{"proposal_id": "...", "confirmed_steps": [0, 2]}` aufruft
**Then** führt das Backend nur die Steps mit Index 0 und 2 aus
**And** nicht ausgewählte Steps werden in der Pipeline-Spec als `enabled: false` markiert
**And** die Response enthält nur die Ergebnisse der ausgeführten Steps

**Given** `POST /confirm` wird **ohne** `confirmed_steps` aufgerufen
**When** das Backend verarbeitet den Request
**Then** werden alle Steps ausgeführt (unveränderte Rückwärtskompatibilität)

**Given** das Frontend zeigt eine Proposal-Card
**When** der Nutzer die Checkboxen für einzelne Steps sieht (UX-DR1)
**Then** sendet ein Klick auf „Bestätigen" nur die angehakten Step-Indices als `confirmed_steps`

**Given** `confirmed_steps` ist ein leeres Array `[]`
**When** der Request verarbeitet wird
**Then** gibt das Backend einen validen Fehler zurück (nicht 500): „Mindestens ein Step muss ausgewählt sein"

**Technische Hinweise:**
- `ConfirmProposalRequest` in `api/schemas.py` um `confirmed_steps: list[int] | None = None` erweitern
- `ProposalService.confirm_proposal()` — Step-Filterung anhand Indices, nicht ausgewählte Steps → `enabled: false` in Spec

### Story 9.3: Step-by-Step-Ausführungsmodus

Als **Nutzer**,
möchte ich ein Proposal im Step-by-Step-Modus ausführen können, bei dem nach jedem Step das Ergebnis gezeigt wird und ich aktiv entscheide wie es weitergeht,
damit ich jeden Preprocessing-Schritt nachvollziehe und das System als interaktives Lernwerkzeug nutzen kann.

**Acceptance Criteria:**

**Given** ein Proposal mit mehreren Steps existiert
**When** der Nutzer `POST /confirm` mit `{"proposal_id": "...", "mode": "step_by_step"}` aufruft
**Then** führt das Backend **nur den ersten aktiven Step** aus
**And** die Response hat `type: "step_result"` mit:
  - `completed_step.type` und `completed_step.summary` (z.B. „3 Duplikate entfernt. 17.376 Zeilen verbleiben.")
  - `remaining_steps` als Liste der noch ausstehenden Steps
  - `next_action` als Handlungsaufforderung (z.B. „Nächster Schritt: Imputation (Median). Bestätigen, überspringen oder anpassen?")
**And** der Step-by-Step-State wird in `step_states` persistiert

**Given** ein Step-by-Step-Vorgang läuft (State in `step_states`)
**When** der Nutzer den nächsten Step bestätigt (gleicher `POST /confirm`-Endpunkt oder per Chat)
**Then** führt das Backend den nächsten Step aus, aufbauend auf dem Datenzustand nach dem vorherigen Step
**And** die Response enthält den aktualisierten State (`step_result` mit neuem `completed_step`)

**Given** der letzte Step in einem Step-by-Step-Vorgang wird ausgeführt
**When** kein weiterer Step verbleibt
**Then** gibt das Backend eine Gesamtzusammenfassung zurück (alle `completed_steps`, Gesamt-Metriken falls anwendbar)
**And** der State wird aus `step_states` gelöscht

**Given** ein Step-by-Step-Vorgang läuft
**When** der Nutzer per Chat „Stopp" oder „Das reicht erstmal" sendet
**Then** erkennt das LLM die Abbruch-Intention und beendet den Step-by-Step-Modus
**And** das Backend gibt eine Zusammenfassung der bisher ausgeführten Steps zurück
**And** der State wird aus `step_states` gelöscht

**Given** ein Step-by-Step-Vorgang läuft
**When** der Nutzer per Chat einen Step modifizieren möchte (z.B. „Nutze Mean statt Median")
**Then** aktualisiert das LLM den aktuellen Step in `remaining_steps` und wartet erneut auf Bestätigung

**Given** das Frontend zeigt ein `step_result`
**When** der Nutzer die Step-Zusammenfassung und die verbleibenden Steps sieht (UX-DR2)
**Then** wird ein Mini-Proposal für den nächsten Step mit Confirm-Option angezeigt

**Technische Hinweise:**
- `ConfirmProposalRequest` um `mode: Literal["all", "step_by_step"] = "all"` erweitern
- `StepResultResponse` Schema in `api/schemas.py`
- `ProposalService` nutzt `StepStateRepository` für Persistenz des Fortschritts
- DataFrame wird NICHT persistiert — bei Fortführung deterministisch aus Bike-CSV + `completed_steps` rekonstruiert

---

## Epic 8: Pipeline-Versionsbaum & Rollback

**Epic Goal:** Jede Spec-Version kennt ihre Vorgänger-Version. Nutzer können den vollständigen Versionsbaum abrufen, sehen welche Änderungen jede Version eingeführt hat, und zu jeder früheren Version zurückrollen (als neue Version, kein Überschreiben).

**Abhängigkeit:** Epic 5 (DB-Migration für `parent_spec_id` + `change_summary`).

### Story 8.1: Spec-Diff-Utility (`spec_diff`)

Als **Entwickler**,
möchte ich eine reine Utility-Funktion `spec_diff(old_spec, new_spec) -> str`, die eine kompakte, menschenlesbare Zusammenfassung der Änderungen zwischen zwei Specs generiert,
damit `change_summary` automatisch beim Erstellen jeder neuen Spec-Version befüllt wird.

**Acceptance Criteria:**

**Given** eine alte Spec und eine neue Spec mit einem hinzugefügten Step (`outlier_handling`)
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** enthält das Ergebnis `"+ outlier_handling (IQR)"`

**Given** eine alte Spec mit einem Step, der in der neuen fehlt (`correlation_filter`)
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** enthält das Ergebnis `"− correlation_filter"`

**Given** eine Spec wo `imputation.params.method` von `median` zu `mean` geändert wurde
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** enthält das Ergebnis `"imputation: median → mean"`

**Given** ein Step wurde deaktiviert (`enabled: false`)
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** enthält das Ergebnis `"encoding: deaktiviert"`

**Given** mehrere Änderungen gleichzeitig
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** werden alle Änderungen kommasepariert zurückgegeben: z.B. `"+ outlier_handling (IQR), imputation: median → mean"`

**Given** keine Änderungen zwischen alter und neuer Spec
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** gibt die Funktion einen leeren String zurück (kein Fehler)

**Given** unveränderte Step-Parameter
**When** `spec_diff(old_spec, new_spec)` aufgerufen wird
**Then** werden unveränderte Parameter **nicht** aufgelistet (kein Noise)

**Technische Hinweise:**
- `spec/spec_diff.py` — reine Funktion, kein Service, keine Klasse
- Wird von `SpecRepository` aufgerufen wenn neue Version erstellt wird
- Format: `"+ step (param), − step, step: old → new, step: deaktiviert"`

### Story 8.2: Versionsbaum-API-Endpunkt

Als **Nutzer**,
möchte ich den vollständigen Versionsbaum meiner Pipeline-Specs über einen API-Endpunkt abrufen,
damit ich sehe welche Versionen existieren, wie sie zusammenhängen und welche gerade aktiv ist.

**Acceptance Criteria:**

**Given** eine Session mit drei Spec-Versionen (v1 → v2 → v3)
**When** `GET /v1/sessions/{id}/spec/tree` aufgerufen wird
**Then** gibt das Backend ein JSON zurück mit:
  - `session_id`
  - `active_spec_id` (aktuell aktive Version)
  - `versions`: Liste aller Versionen, je mit: `spec_id`, `version`, `parent_spec_id` (null für v1), `change_summary`, `created_at`, `has_runs`, `last_run_status`

**Given** eine Session, bei der der Nutzer nach Rollback auf v1 eine neue v4 erstellt hat
**When** `GET /spec/tree` aufgerufen wird
**Then** zeigt die Baumstruktur korrekte Abzweigungen: v1→v2→v3 und v1→v4 (durch `parent_spec_id`)

**Given** eine Session mit nur einer Spec-Version
**When** `GET /spec/tree` aufgerufen wird
**Then** gibt das Backend eine Version mit `parent_spec_id: null` zurück (kein Fehler)

**Given** eine Session ohne jede Spec-Version
**When** `GET /spec/tree` aufgerufen wird
**Then** gibt das Backend `{"session_id": "...", "active_spec_id": null, "versions": []}` zurück

**Given** das Frontend zeigt das Versionsbaum-Panel (UX-DR3)
**When** der Nutzer das Panel öffnet
**Then** werden alle Versionen als Baum dargestellt; die aktive Version ist hervorgehoben; jeder Knoten zeigt `change_summary` und `last_run_status`

**Technische Hinweise:**
- Neuer Endpunkt in `api/routes/specs.py` (oder neues `api/routes/version_tree.py`)
- `VersionTreeResponse` Schema in `api/schemas.py`
- `SpecRepository` liefert alle Versionen einer Session mit `parent_spec_id`

### Story 8.3: Rollback auf frühere Spec-Version

Als **Nutzer**,
möchte ich zu einer früheren Spec-Version zurückrollen können (per Chat oder Versionsbaum-Klick),
damit ich von einem früheren Stand aus neue Richtungen ausprobieren kann — ohne bisherige Versionen und Runs zu verlieren.

**Acceptance Criteria:**

**Given** eine Session mit Spec-Versionen v1, v2, v3 (v3 ist aktiv)
**When** der Nutzer über Chat „Gehe zurück zu v1" oder per `POST /v1/sessions/{id}/rollback` mit `{"target_spec_id": "spec-v1"}` einen Rollback auslöst
**Then** wird eine **neue** Spec-Version v4 erstellt, die eine Kopie von v1 ist
**And** v4 hat `parent_spec_id = "spec-v3"` (aktuelle Version vor dem Rollback)
**And** v4 hat `change_summary = "Rollback auf v1"`
**And** v4 ist die neue aktive Version

**Given** ein Rollback wurde ausgeführt
**When** `GET /spec/tree` aufgerufen wird
**Then** sind v1, v2, v3, v4 alle noch vorhanden (kein Löschen/Überschreiben)
**And** der Baum zeigt: v3 → v4 (Rollback-Abzweigung)

**Given** der Nutzer klickt im Versionsbaum-Panel auf einen älteren Knoten (UX-DR4)
**When** der Klick eine Rollback-Bestätigung auslöst
**Then** wird `POST /rollback` mit `target_spec_id` des gewählten Knotens gesendet (kein stiller Rollback)

**Given** ein LLM-Rollback (`action_type: "rollback", target_spec_id: "..."`)
**When** das Backend die LLM-Aktion verarbeitet
**Then** ruft das Backend dieselbe Rollback-Logik wie der `POST /rollback`-Endpunkt auf (DRY)

**Given** `target_spec_id` existiert nicht oder gehört nicht zu dieser Session
**When** `POST /rollback` aufgerufen wird
**Then** gibt das Backend HTTP 404 mit verständlicher Fehlermeldung zurück

**Technische Hinweise:**
- Neuer Endpunkt `api/routes/rollback.py`: `POST /v1/sessions/{id}/rollback` mit `RollbackRequest(target_spec_id: str)`
- `SpecRepository.rollback_to(session_id, target_spec_id)` — Kopier-Logik, neue Version mit `parent_spec_id` = aktuelle aktive
- LLM-Aktion `action_type: "rollback"` und Endpunkt nutzen dieselbe Repository-Methode
- `parent_spec_id` und `change_summary` werden durch `spec_diff()` (Story 4.1) befüllt
