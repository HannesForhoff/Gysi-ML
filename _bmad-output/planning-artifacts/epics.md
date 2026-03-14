---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-14.md
---

# gysi-ml - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for gysi-ml, decomposing the requirements from the PRD into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Nutzer kann eine neue Konversations-Session erstellen
FR2: Nutzer kann eine laufende Session abrufen (Metadaten, Status)
FR3: Nutzer kann alle Sessions auflisten
FR4: Nutzer kann eine Session beenden/schließen
FR5: Nutzer kann eine natürlichsprachliche Eingabe an eine Session senden
FR6: Das System erkennt, ob eine Eingabe eindeutig oder vage/unvollständig ist
FR7: Bei eindeutiger Eingabe führt das System die Aktion direkt aus
FR8: Bei vager Eingabe gibt das System einen konkreten Ausführungsvorschlag (Proposal) mit Steps und Parametern zurück
FR9: Nutzer kann einen Proposal bestätigen, um die Ausführung zu starten
FR10: Nutzer kann einen Proposal ablehnen oder modifizieren
FR11: Das System gibt eine strukturierte Liste verfügbarer Aktionen und Steps zurück (`/capabilities`)
FR12: Das System erzeugt für jede Ausführung eine versionierte Pipeline-Spec (JSON)
FR13: Nutzer kann eine gespeicherte Pipeline-Spec abrufen
FR14: Nutzer kann eine Pipeline-Spec erneut ausführen (Reproduzierbarkeit)
FR15: Nutzer kann Parameter einer Pipeline-Spec per Spracheingabe anpassen (neue Version)
FR16: Nutzer kann einzelne Steps in einer Pipeline-Spec deaktivieren
FR17: Das System kann Duplikate im Datensatz entfernen (Dedup)
FR18: Das System kann fehlende Werte imputieren (Median, Mean, Most-Frequent — wählbar)
FR19: Das System kann Ausreißer behandeln (IQR- oder Z-Score-Methode — wählbar)
FR20: Das System kann kategorische Features encodieren (Label Encoding, One-Hot Encoding — wählbar)
FR21: Das System kann hochkorrelierte Features filtern (Schwellwert konfigurierbar)
FR22: Das System kann seltene Kategorien in einen Sammelbucket zusammenfassen
FR23: Das System kann Zeit-Features aus `dteday` ableiten (Wochentag, Monat)
FR24: Das System führt den Train/Test-Split als feste Architekturgrenze durch (Ratio konfigurierbar)
FR25: Das System kann ein Decision-Tree-Regressionsmodell trainieren
FR26: Das System kann ein EBM-Regressionsmodell (InterpretML) trainieren
FR27: Das System kann CatBoost Feature Selection auf dem Datensatz ausführen
FR28: Das System berechnet und persistiert Regressionsmetriken (RMSE, MAE, R²) für jeden Trainings-Run
FR29: Das System kann zwei Modell-Runs anhand ihrer Metriken vergleichen
FR30: Das System erzeugt einen globalen Feature-Importance-Plot für trainierte Modelle
FR31: Das System erzeugt einen EBM-Global-Explanation-Plot
FR32: Das System persistiert alle Plots als Dateien (PNG) im Filesystem
FR33: Nutzer kann ein gespeichertes Artefakt (Plot) über die API abrufen
FR34: Das System erzeugt eine Übersicht der Artefakte eines Runs
FR35: Das System persistiert jeden Ausführungs-Run mit Input-Parametern, Ergebnissen und Artefakt-Referenzen
FR36: Nutzer kann alle Runs einer Session auflisten
FR37: Nutzer kann das vollständige Ergebnis eines spezifischen Runs abrufen
FR38: Das System persistiert den vollständigen Gesprächsverlauf einer Session
FR39: Das System sendet Nutzereingaben strukturiert an ein LLM (OpenAI-kompatibler Endpunkt)
FR40: Das System validiert LLM-Outputs gegen ein JSON-Schema vor der Ausführung
FR41: Das System führt bei ungültigem LLM-Output einen Retry-Prompt durch
FR42: Das System gibt dem Nutzer eine verständliche Fehlermeldung, wenn LLM-Output nach Retry weiterhin ungültig ist
FR43: Das System stellt einen Health-Check-Endpunkt bereit (`GET /v1/health`), der den Service-Status zurückgibt

### NonFunctional Requirements

NFR-P1: Standard-Preprocessing-Schritte (Imputation, Encoding, Dedup) schließen in < 5 s ab (bei 17.379 Zeilen)
NFR-P2: Decision-Tree-Training inkl. Metrikberechnung schließt in < 10 s ab
NFR-P3: EBM-Training schließt in < 60 s ab
NFR-P4: API-Endpunkte ohne ML-Berechnung antworten in < 500 ms
NFR-R1: Kein Absturz bei ungültigen Nutzereingaben — jede Exception wird als strukturierte Fehler-Response zurückgegeben
NFR-R2: Klare Fehlermeldung bei Datenbankfehler (kein blanker 500-Error)
NFR-R3: Atomare Ausführung — kein Halb-State in SQLite
NFR-T1: Test-Coverage ≥ 85 % (pytest-cov auf `src/gysi_ml/`)
NFR-T2: Dedizierte Unit-Tests für fit/transform-Grenze, JSON-Schema-Validierung, Proposal-Mode
NFR-T3: Integration-Tests Happy-Path (Session → Message → Confirm → Run → Artifact)
NFR-T4: Alle Steps isoliert testbar (kein globaler State zwischen Tests)
NFR-M1: `@register_step`-Decorator für alle Preprocessing/Modeling-Steps
NFR-M2: Open/Closed-Prinzip — neue Steps ohne Änderung bestehender Steps/Executor hinzufügbar
NFR-M3: Konfiguration ausschließlich in `.env` / `config.py` — keine hartcodierten Werte
NFR-M4: Code-Style: Black-formatiert, type-annotiert, keine ungenutzten Imports
NFR-S1: LLM-Outputs niemals direkt als Code ausgeführt — ausschließlich JSON-Schema-validierte Strukturen
NFR-S2: Keine Secrets im Code — ausschließlich über `.env`
NFR-S3: Parameterized Queries via SQLite-Stdlib (kein SQL-Injection-Risiko)

### Additional Requirements

- **Brownfield-Projekt**: Scaffold vorhanden (`backend/src/gysi_ml/`), kein Produktionscode — kein initiales Setup-Epic erforderlich, aber Grundgerüst muss aufgebaut werden
- **Step-Registry-Pattern**: `@register_step`-Decorator als Kernmuster, alle Steps registrieren sich selbst
- **fit/transform-Grenze**: Architektonisch erzwungen — Splitting vor allen transformierenden Steps; nie `fit()` auf Testdaten
- **SQLite-Schema**: Tabellen `sessions`, `runs`, `artifacts`, `spec_versions` — werden schrittweise angelegt
- **API-Versionierung**: Alle Endpunkte unter `/v1/` — FastAPI mit OpenAPI unter `/docs`
- **Pydantic v2**: Alle Request/Response-Schemas explizit definiert
- **random_state=42**: Für alle nichtdeterministischen Operationen (Reproduzierbarkeit)
- **Artefakt-Speicherung**: PNG im Filesystem (`artifacts/`), nicht als Base64 in Responses
- **LLM-Interface**: OpenAI-kompatible API — konfigurierbar über `.env`
- **Synchrone Ausführung**: Kein Background-Task-Framework; Endpunkte blockieren bis Ergebnis verfügbar

### UX Design Requirements

Nicht zutreffend — gysi-ml ist ein reines API Backend ohne Frontend-Scope im MVP.

### FR Coverage Map

| FR | Epic | Kurzbeschreibung |
|---|---|---|
| FR1 | Epic 1 | Session erstellen |
| FR2 | Epic 1 | Session abrufen |
| FR3 | Epic 1 | Alle Sessions auflisten |
| FR4 | Epic 1 | Session beenden |
| FR5 | Epic 3 | Nutzereingabe an Session senden |
| FR6 | Epic 3 | Vagheits-Erkennung |
| FR7 | Epic 3 | Direkte Ausführung bei eindeutiger Eingabe |
| FR8 | Epic 3 | Proposal-Response bei vager Eingabe |
| FR9 | Epic 3 | Proposal bestätigen |
| FR10 | Epic 3 | Proposal ablehnen/modifizieren |
| FR11 | Epic 1 | `/capabilities`-Endpunkt |
| FR12 | Epic 1 | Versionierte Spec-Erstellung |
| FR13 | Epic 4 | Spec abrufen |
| FR14 | Epic 4 | Spec erneut ausführen |
| FR15 | Epic 4 | Parameter per Sprache anpassen |
| FR16 | Epic 4 | Steps deaktivieren |
| FR17 | Epic 1 | Dedup |
| FR18 | Epic 1 | Missing Value Imputation |
| FR19 | Epic 1 | Outlier Handling |
| FR20 | Epic 1 | Encoding |
| FR21 | Epic 1 | Correlation Filter |
| FR22 | Epic 1 | Rare Category Bucketing |
| FR23 | Epic 1 | Time-Feature-Encoding |
| FR24 | Epic 1 | Train/Test-Split |
| FR25 | Epic 2 | Decision Tree Training |
| FR26 | Epic 2 | EBM Training |
| FR27 | Epic 4 | CatBoost Feature Selection |
| FR28 | Epic 2 | Metriken berechnen und persistieren |
| FR29 | Epic 4 | Modell-Runs vergleichen |
| FR30 | Epic 2 | Feature-Importance-Plot |
| FR31 | Epic 2 | EBM-Global-Explanation-Plot |
| FR32 | Epic 2 | Plots als PNG persistieren |
| FR33 | Epic 2 | Artefakt abrufen |
| FR34 | Epic 2 | Artefakt-Übersicht eines Runs |
| FR35 | Epic 1 | Run persistieren |
| FR36 | Epic 1 | Alle Runs einer Session auflisten |
| FR37 | Epic 1 | Run-Ergebnis abrufen |
| FR38 | Epic 3 | Gesprächsverlauf persistieren |
| FR39 | Epic 3 | LLM-Anfrage senden |
| FR40 | Epic 3 | LLM-Output validieren |
| FR41 | Epic 3 | Retry bei ungültigem LLM-Output |
| FR42 | Epic 3 | Fehlermeldung bei Retry-Erschöpfung |
| FR43 | Epic 1 | Health-Check-Endpunkt |

## Epic List

### Epic 1: Nutzer kann Preprocessing-Pipelines via REST API ausführen und Ergebnisse abrufen

Nutzer können den Bike-Datensatz in einer Session bereinigen, transformieren und splitten. Alle Schritte werden als versionierte Spec gespeichert, Runs persistiert und Ergebnisse über die API abrufbar.

**FRs covered:** FR1, FR2, FR3, FR4, FR11, FR12, FR17, FR18, FR19, FR20, FR21, FR22, FR23, FR24, FR35, FR36, FR37, FR43

### Epic 2: Nutzer kann Modelle trainieren und Interpretierbarkeits-Artefakte abrufen

Aufbauend auf vorbereiteten Daten können Nutzer Decision-Tree- und EBM-Modelle trainieren, Regressionsmetriken auswerten und Feature-Importance-Plots herunterladen.

**FRs covered:** FR25, FR26, FR28, FR30, FR31, FR32, FR33, FR34

### Epic 3: Nutzer kann in natürlicher Sprache interagieren — System schlägt Schritte vor und führt nach Bestätigung aus

Das LLM wird als reiner JSON-Übersetzer integriert. Bei Vagheit gibt das System einen Proposal zurück, bei Bestätigung wird ausgeführt. Gesprächsverlauf wird persistiert.

**FRs covered:** FR5, FR6, FR7, FR8, FR9, FR10, FR38, FR39, FR40, FR41, FR42

### Epic 4: Nutzer kann Pipeline-Specs verwalten, History einsehen und erweiterte ML-Features nutzen

Nutzer können Specs abrufen, erneut ausführen, Parameter anpassen, Steps deaktivieren und Modell-Runs vergleichen. Zusätzlich: CatBoost Feature Selection.

**FRs covered:** FR13, FR14, FR15, FR16, FR27, FR29

---

## Epic 1: Nutzer kann Preprocessing-Pipelines via REST API ausführen und Ergebnisse abrufen

Nutzer können den Bike-Datensatz in einer Session bereinigen, transformieren und splitten. Alle Schritte werden als versionierte Spec gespeichert, Runs persistiert und Ergebnisse über die API abrufbar.

### Story 1.1: FastAPI-Grundgerüst, SQLite-Schema und Session-Endpunkte

Als ein API-Konsument (Entwickler oder HTTP-Client),
möchte ich Sessions erstellen, abrufen, auflisten und schließen sowie den Service-Status prüfen können,
damit ich den Lebenszyklus von Konversations-Sessions über die REST API verwalten kann und sicherstellen kann, dass der Service läuft.

**Acceptance Criteria:**

**Given** der Service läuft lokal
**When** `GET /v1/health` aufgerufen wird
**Then** gibt das System `{"status": "ok"}` mit HTTP 200 zurück

**Given** kein Fehler im Service
**When** `POST /v1/sessions` mit optionalem `{"name": "..."}` aufgerufen wird
**Then** wird eine neue Session mit eindeutiger `session_id` (UUID) angelegt, in SQLite persistiert und mit HTTP 201 zurückgegeben
**And** die Response enthält `session_id`, `created_at` und `status: "active"`

**Given** eine existierende Session
**When** `GET /v1/sessions/{id}` aufgerufen wird
**Then** gibt das System Session-Metadaten (`session_id`, `created_at`, `status`) mit HTTP 200 zurück

**Given** mindestens eine existierende Session
**When** `GET /v1/sessions` aufgerufen wird
**Then** gibt das System eine Liste aller Sessions zurück (Array, peut auch leer sein)

**Given** eine existierende Session
**When** `DELETE /v1/sessions/{id}` aufgerufen wird
**Then** wird der Session-Status auf `"closed"` gesetzt und HTTP 200 zurückgegeben
**And** die Session bleibt in SQLite erhalten (kein Hard-Delete)

**Given** eine nicht existierende Session-ID
**When** `GET /v1/sessions/{id}` aufgerufen wird
**Then** gibt das System HTTP 404 mit `{"error": "session_not_found", "detail": "...", "code": "SESSION_NOT_FOUND"}` zurück

**Given** eine ungültige Request-Payload
**When** ein Endpunkt mit fehlerhaften Daten aufgerufen wird
**Then** gibt das System HTTP 422 mit strukturierten Validierungsfehlern (Pydantic) zurück, stürzt nicht ab

---

### Story 1.2: Step-Registry und Pipeline-Executor mit Spec-Validierung

Als ein Entwickler,
möchte ich neue Preprocessing-Steps über einen `@register_step`-Decorator registrieren können und eine JSON-Spec über den Executor ausführen lassen,
damit das System erweiterbar bleibt (Open/Closed-Prinzip) und jede Ausführung auf einer validierten, versionierten Spec basiert.

**Acceptance Criteria:**

**Given** eine Python-Klasse mit `@register_step("step_type")`-Decorator
**When** der Service startet
**Then** ist der Step unter dem registrierten Typ in der Registry verfügbar

**Given** eine gültige Pipeline-Spec (JSON) mit einer Liste von Steps
**When** der Executor die Spec erhält
**Then** validiert er die Spec gegen das JSON-Schema (alle Step-Typen bekannt, Pflichtfelder vorhanden)
**And** führt die Steps sequenziell in der definierten Reihenfolge aus

**Given** eine Spec mit einem unbekannten Step-Typ
**When** der Executor die Spec erhält
**Then** gibt er einen strukturierten Fehler zurück (`{"error": "unknown_step_type", ...}`) ohne Absturz

**Given** eine erfolgreich ausgeführte Spec
**When** die Ausführung abgeschlossen ist
**Then** wird ein Run-Eintrag in SQLite `runs`-Tabelle angelegt mit `spec_version`, `status: "completed"`, `started_at`, `finished_at`
**And** die Spec wird in `spec_versions`-Tabelle als `v1` gespeichert

**Given** eine fehlgeschlagene Ausführung (Exception in einem Step)
**When** der Executor den Fehler abfängt
**Then** wird der Run-Eintrag mit `status: "failed"` und `error_message` persistiert
**And** kein Halb-State bleibt in SQLite (atomare Transaktion)

---

### Story 1.3: Preprocessing Steps — Dedup, Imputation und Outlier Handling

Als ein Datenwissenschaftler,
möchte ich Duplikate entfernen, fehlende Werte imputieren und Ausreißer behandeln lassen,
damit der Bike-Datensatz (mit künstlich eingebrachten fehlenden Werten in `mnth` und `weathersit`) für das Modelltraining vorbereitet ist.

**Acceptance Criteria:**

**Given** eine Spec mit Step `{"type": "dedup"}`
**When** der Executor den Step ausführt
**Then** werden exakt duplizierte Zeilen aus dem Datensatz entfernt
**And** die Anzahl entfernter Duplikate wird im Run-Ergebnis gespeichert

**Given** eine Spec mit Step `{"type": "impute_missing", "params": {"strategy": "median"}}`
**When** der Executor den Step ausführt
**Then** werden fehlende Werte numerischer Spalten mit dem Median der Trainingsdaten imputiert (`fit` nur auf Train-Split)
**And** bei `strategy: "mean"` wird der Mittelwert verwendet, bei `"most_frequent"` der häufigste Wert
**And** die Anzahl imputierter Werte pro Spalte wird im Run-Ergebnis gespeichert

**Given** eine Spec mit Step `{"type": "outlier_handling", "params": {"method": "iqr"}}`
**When** der Executor den Step ausführt
**Then** werden Ausreißer (außerhalb 1,5×IQR) anhand der Trainingsdaten identifiziert (`fit`) und im gesamten Datensatz behandelt (`transform`)
**And** bei `method: "zscore"` wird der Z-Score-Grenzwert (Standard: 3) verwendet
**And** die Anzahl behandelter Ausreißer wird im Run-Ergebnis gespeichert

**Given** dass `fit()` für Imputation oder Outlier aufgerufen wird
**When** der Step ausgeführt wird
**Then** werden die gelernten Parameter (Median/IQR-Grenzen) ausschließlich auf den Trainingsdaten berechnet
**And** `transform()` verwendet diese Parameter ohne Neuberechnung auf den Testdaten

---

### Story 1.4: Preprocessing Steps — Encoding, Correlation Filter, Rare Category und Time-Features

Als ein Datenwissenschaftler,
möchte ich kategorische Features encodieren, hochkorrelierte Features filtern, seltene Kategorien bündeln und Datums-Features ableiten lassen,
damit der Datensatz vollständig für baumorientierte Modelle vorbereitet ist.

**Acceptance Criteria:**

**Given** eine Spec mit Step `{"type": "encode_categorical", "params": {"method": "label"}}`
**When** der Executor den Step ausführt
**Then** werden kategorische Spalten mit Label Encoding transformiert (`fit` auf Train, `transform` auf Train+Test)
**And** bei `method: "onehot"` wird One-Hot Encoding angewendet
**And** unbekannte Kategorien im Test-Set werden als `-1` (Label) bzw. Null-Vektor (One-Hot) behandelt

**Given** eine Spec mit Step `{"type": "correlation_filter", "params": {"threshold": 0.9}}`
**When** der Executor den Step ausführt
**Then** werden Features mit Pearson-Korrelation ≥ Schwellwert paarweise identifiziert und eines aus jedem Paar entfernt
**And** der Threshold ist konfigurierbar und wird auf Trainingsdaten berechnet
**And** entfernte Features werden namentlich im Run-Ergebnis gelistet

**Given** eine Spec mit Step `{"type": "rare_category_bucketing", "params": {"min_frequency": 0.01}}`
**When** der Executor den Step ausführt
**Then** werden Kategorien mit relativer Häufigkeit < `min_frequency` (berechnet auf Trainingsdaten) zu `"__rare__"` zusammengefasst

**Given** eine Spec mit Step `{"type": "time_feature_encoding", "params": {"column": "dteday"}}`
**When** der Executor den Step ausführt
**Then** wird aus `dteday` (ISO-Datum) der Wochentag als Integer (0=Montag) und der Monat als Integer (1–12) abgeleitet
**And** die ursprüngliche `dteday`-Spalte wird aus dem Datensatz entfernt

---

### Story 1.5: Train/Test-Split als Architekturgrenze und Run-Persistenz vollständig

Als ein Datenwissenschaftler,
möchte ich den Datensatz reproduzierbar aufteilen und alle Run-Ergebnisse mit Input-Parametern und Artefakt-Referenzen abrufen können,
damit Experimente exakt wiederholbar sind und jede Pipeline-Ausführung vollständig auditierbar ist.

**Acceptance Criteria:**

**Given** eine Spec mit Step `{"type": "split", "params": {"test_size": 0.2, "random_state": 42}}`
**When** der Executor den Split-Step erreicht
**Then** wird der Datensatz in Train (80%) und Test (20%) aufgeteilt mit `random_state=42`
**And** alle nachfolgenden fit/transform-Steps erhalten ausschließlich die Trainings-Partition für `fit()`
**And** der Split-Step kann nicht vor einem Imputation/Encoding-Step positioniert werden (Architektur-Constraint)

**Given** ein abgeschlossener Run
**When** `GET /v1/sessions/{id}/runs` aufgerufen wird
**Then** gibt das System alle Runs der Session zurück (Array) mit `run_id`, `status`, `started_at`, `spec_version`

**Given** ein abgeschlossener Run
**When** `GET /v1/sessions/{id}/runs/{run_id}` aufgerufen wird
**Then** gibt das System vollständige Run-Daten zurück: Input-Spec, Ergebnisse (Step-Outputs, Zeilenzahlen), Metriken (falls vorhanden), Artefakt-Referenzen (falls vorhanden)

**Given** ein fehlgeschlagener Run
**When** `GET /v1/sessions/{id}/runs/{run_id}` aufgerufen wird
**Then** gibt das System `status: "failed"` und `error_message` zurück

**Given** zwei identische Specs mit gleichen Parametern und `random_state=42`
**When** beide Specs ausgeführt werden
**Then** sind die Ergebnisse (Zeilenzahlen, imputierte Werte, entfernte Features) identisch (Reproduzierbarkeit)

---

### Story 1.6: Capabilities-Endpunkt

Als ein API-Konsument (Entwickler oder zukünftiges Frontend),
möchte ich eine strukturierte Übersicht aller verfügbaren Aktionen und Steps abrufen können,
damit ich weiß, welche Pipeline-Steps und API-Operationen das System unterstützt, ohne den Quellcode lesen zu müssen.

**Acceptance Criteria:**

**Given** der Service läuft
**When** `GET /v1/capabilities` aufgerufen wird
**Then** gibt das System HTTP 200 mit einer JSON-Antwort zurück, die alle registrierten Step-Typen enthält
**And** jeder Step enthält `type`, `description` und `params` (Parameterliste mit Typen und Defaults)

**Given** ein neu registrierter Step (via `@register_step`)
**When** `GET /v1/capabilities` aufgerufen wird
**Then** erscheint der neue Step automatisch in der Antwort (keine manuelle Pflege erforderlich)

**Given** die Capabilities-Response
**When** ein Client die Response verarbeitet
**Then** ist die Struktur konsistent JSON (kein freier Text), direkt maschinenlesbar

---

## Epic 2: Nutzer kann Modelle trainieren und Interpretierbarkeits-Artefakte abrufen

Aufbauend auf vorbereiteten Daten können Nutzer Decision-Tree- und EBM-Modelle trainieren, Regressionsmetriken auswerten und Feature-Importance-Plots herunterladen.

### Story 2.1: Decision Tree Training und Metriken

Als ein Datenwissenschaftler,
möchte ich einen Decision-Tree-Regressor auf den vorbereiteten und aufgeteilten Daten trainieren und Regressionsmetriken berechnen lassen,
damit ich die Modellqualität quantitativ bewerten und mit anderen Runs vergleichen kann.

**Acceptance Criteria:**

**Given** ein Run mit abgeschlossenem Split-Step (Train/Test-Daten vorhanden)
**When** eine Spec mit Step `{"type": "train_decision_tree", "params": {"max_depth": 5, "random_state": 42}}` ausgeführt wird
**Then** wird ein `DecisionTreeRegressor` mit den angegebenen Parametern auf den Trainingsdaten trainiert (`fit` ausschließlich auf Train-Partition)
**And** Vorhersagen werden auf den Testdaten berechnet (`predict` auf Test-Partition)

**Given** ein trainiertes Decision-Tree-Modell
**When** die Metrikberechnung abgeschlossen ist
**Then** werden RMSE, MAE und R² auf den Testdaten berechnet und im Run-Ergebnis persistiert
**And** `GET /v1/sessions/{id}/runs/{run_id}` gibt diese Metriken im `metrics`-Feld zurück

**Given** ein Decision-Tree-Training
**When** kein `random_state` in der Spec angegeben ist
**Then** wird `random_state=42` als Default verwendet (Reproduzierbarkeit)

**Given** dass kein Split-Step vor dem Training in der Spec vorhanden ist
**When** der Executor den Training-Step erreicht
**Then** gibt das System einen strukturierten Fehler zurück (`{"error": "split_required_before_training", ...}`)

---

### Story 2.2: Feature-Importance-Plot und Artefakt-Abruf

Als ein Datenwissenschaftler,
möchte ich nach dem Modelltraining einen Feature-Importance-Plot als PNG-Datei abrufen können,
damit ich visuell nachvollziehen kann, welche Features den größten Einfluss auf die Vorhersage haben.

**Acceptance Criteria:**

**Given** ein abgeschlossenes Decision-Tree-Training
**When** die Ausführung abgeschlossen ist
**Then** wird automatisch ein Feature-Importance-Balkendiagramm (matplotlib) als PNG erstellt
**And** die PNG-Datei wird im Filesystem unter `artifacts/` gespeichert (nicht als Base64 in der Response)
**And** ein Artefakt-Eintrag wird in SQLite mit `artifact_id`, `run_id`, `type: "feature_importance"`, `file_path` angelegt

**Given** ein persistierter Artefakt-Eintrag
**When** `GET /v1/artifacts/{artifact_id}` aufgerufen wird
**Then** gibt das System die PNG-Datei als Byte-Stream mit `Content-Type: image/png` zurück (HTTP 200)

**Given** eine nicht existierende `artifact_id`
**When** `GET /v1/artifacts/{artifact_id}` aufgerufen wird
**Then** gibt das System HTTP 404 mit `{"error": "artifact_not_found", ...}` zurück

**Given** ein abgeschlossener Run mit Artefakten
**When** `GET /v1/sessions/{id}/runs/{run_id}` aufgerufen wird
**Then** enthält die Response ein `artifacts`-Array mit `artifact_id`, `type` und `created_at` für alle erzeugten Artefakte

---

### Story 2.3: EBM Training und globaler Erklärungsplot

Als ein Datenwissenschaftler,
möchte ich ein Explainable Boosting Machine (EBM) Regressionsmodell trainieren und einen globalen Erklärungsplot abrufen können,
damit ich die Modellentscheidungen auf Feature-Ebene interpretieren und dem Evaluator transparent erklären kann.

**Acceptance Criteria:**

**Given** ein Run mit abgeschlossenem Split-Step
**When** eine Spec mit Step `{"type": "train_ebm", "params": {"random_state": 42}}` ausgeführt wird
**Then** wird ein `ExplainableBoostingRegressor` (InterpretML v0.7.7) auf den Trainingsdaten trainiert
**And** Vorhersagen werden auf den Testdaten berechnet

**Given** ein trainiertes EBM-Modell
**When** die Metrikberechnung abgeschlossen ist
**Then** werden RMSE, MAE und R² berechnet und im Run persistiert (identisches Schema wie Decision Tree)

**Given** ein abgeschlossenes EBM-Training
**When** die Ausführung abgeschlossen ist
**Then** wird automatisch ein EBM-Global-Explanation-Plot (Feature-Shapes über alle Features) als PNG erstellt
**And** die PNG-Datei wird unter `artifacts/` gespeichert
**And** ein Artefakt-Eintrag mit `type: "ebm_global_explanation"` wird in SQLite angelegt

**Given** ein EBM-Training
**When** kein `random_state` in der Spec angegeben ist
**Then** wird `random_state=42` als Default verwendet

**Given** ein EBM-Training auf dem vollständigen Bike-Datensatz (17.379 Zeilen)
**When** das Training abgeschlossen ist
**Then** dauert die Gesamtdauer (Training + Plot-Erstellung) weniger als 60 Sekunden (NFR-P3)

---

## Epic 3: Nutzer kann in natürlicher Sprache interagieren — System schlägt Schritte vor und führt nach Bestätigung aus

Das LLM wird als reiner JSON-Übersetzer integriert. Bei Vagheit gibt das System einen Proposal zurück, bei Bestätigung wird ausgeführt. Gesprächsverlauf wird persistiert.

### Story 3.1: Message-Endpunkt und Gesprächsverlauf-Persistenz

Als ein API-Konsument,
möchte ich Texteingaben an eine Session senden und den Gesprächsverlauf persistiert abrufen können,
damit alle Interaktionen auditierbar sind und das System auf frühere Nachrichten in der Session referenzieren kann.

**Acceptance Criteria:**

**Given** eine existierende aktive Session
**When** `POST /v1/sessions/{id}/messages` mit `{"text": "Bereite die Daten vor"}` aufgerufen wird
**Then** wird die Nachricht mit `role: "user"`, `content`, `created_at` in SQLite persistiert
**And** das System gibt eine typisierte Response zurück: entweder `{"type": "proposal", "steps": [...], "confirmation_required": true}` oder `{"type": "result", "run_id": "..."}`
**And** es wird niemals unstrukturierter Freitext als primäre Response zurückgegeben

**Given** eine verarbeitete Nutzereingabe
**When** das System eine Antwort generiert
**Then** wird auch die System-Antwort mit `role: "assistant"` in SQLite persistiert

**Given** eine Session mit mehreren Nachrichten
**When** `GET /v1/sessions/{id}` aufgerufen wird
**Then** enthält die Response ein `messages`-Array mit dem vollständigen Gesprächsverlauf (Reihenfolge: chronologisch)

**Given** eine geschlossene Session
**When** `POST /v1/sessions/{id}/messages` aufgerufen wird
**Then** gibt das System HTTP 409 mit `{"error": "session_closed", ...}` zurück

---

### Story 3.2: LLM-Integration und JSON-Schema-Validierung mit Retry

Als ein Entwickler,
möchte ich dass Nutzereingaben an ein LLM (OpenAI-kompatibel) gesendet werden, die Antwort gegen ein JSON-Schema validiert wird und bei Fehler ein Retry-Prompt ausgelöst wird,
damit das System robust gegen fehlerhafte LLM-Outputs ist und kein ungültiges JSON die Ausführungskette erreicht.

**Acceptance Criteria:**

**Given** eine Nutzereingabe via `/messages`
**When** das System die Anfrage verarbeitet
**Then** wird die Eingabe strukturiert (mit System-Prompt und Gesprächshistorie) an den konfigurierten LLM-Endpunkt gesendet (Endpunkt aus `.env`)

**Given** eine LLM-Antwort
**When** die Antwort empfangen wird
**Then** wird sie gegen das Pipeline-Spec JSON-Schema validiert, bevor sie verarbeitet wird

**Given** eine LLM-Antwort die das Schema nicht erfüllt
**When** die Validierung fehlschlägt
**Then** wird ein korrigierender Retry-Prompt an das LLM gesendet (max. 1 Retry)
**And** das System protokolliert den Fehler intern

**Given** dass der Retry-Output erneut ungültig ist
**When** die zweite Validierung fehlschlägt
**Then** gibt das System eine verständliche Fehlermeldung an den Nutzer zurück: `{"type": "error", "message": "Das Sprachmodell konnte keine gültige Aktion erzeugen. Bitte formuliere deine Anfrage neu.", ...}`
**And** kein Absturz, kein 500-Error

**Given** kein LLM-Endpunkt in `.env` konfiguriert
**When** der Service startet
**Then** gibt der Service eine klare Warnung aus (kein Absturz), LLM-Endpunkte geben HTTP 503 zurück

**Given** das LLM liefert eine valide JSON-Aktion
**When** die Validierung erfolgreich ist
**Then** wird die Aktion an den Executor weitergeleitet und ausgeführt (bei eindeutiger Eingabe) oder als Proposal zurückgegeben (bei Vagheit)

---

### Story 3.3: Vagheits-Erkennung, Proposal-Mode und Bestätigungs-Endpunkt

Als ein Nutzer,
möchte ich bei vagen Eingaben einen konkreten Vorschlag mit Steps und Parametern erhalten und diesen bestätigen oder ablehnen können, bevor das System ausführt,
damit ich immer Entscheider bleibe und das System keine stillen "Best-Guess"-Aktionen durchführt.

**Acceptance Criteria:**

**Given** eine vage Eingabe wie `"Bereite die Daten vor"` oder `"Mach was mit den Daten"`
**When** das LLM die Vagheit erkennt (via System-Prompt-Instruktion)
**Then** gibt das System `{"type": "proposal", "steps": [...], "confirmation_required": true}` zurück
**And** `steps` enthält eine menschenlesbare Liste der vorgeschlagenen Schritte mit Parametern
**And** es wird keine Ausführung gestartet

**Given** eine eindeutige Eingabe wie `"Entferne Duplikate und imputiere fehlende Werte mit Median"`
**When** das LLM eine klare Aktion extrahiert
**Then** wird die Ausführung direkt gestartet (kein Proposal)
**And** das System gibt `{"type": "result", "run_id": "..."}` zurück

**Given** ein offener Proposal (noch nicht bestätigt)
**When** `POST /v1/sessions/{id}/confirm` mit `{"proposal_id": "..."}` aufgerufen wird
**Then** wird die im Proposal beschriebene Pipeline-Spec ausgeführt
**And** das System gibt `{"type": "result", "run_id": "..."}` zurück

**Given** ein Proposal
**When** der Nutzer eine neue Nachricht sendet (statt zu bestätigen)
**Then** wird der offene Proposal verworfen und die neue Eingabe verarbeitet (implizite Ablehnung)

**Given** kein offener Proposal in der Session
**When** `POST /v1/sessions/{id}/confirm` aufgerufen wird
**Then** gibt das System HTTP 409 mit `{"error": "no_pending_proposal", ...}` zurück

---

## Epic 4: Nutzer kann Pipeline-Specs verwalten, History einsehen und erweiterte ML-Features nutzen

Nutzer können Specs abrufen, erneut ausführen, Parameter anpassen, Steps deaktivieren und Modell-Runs vergleichen. Zusätzlich: CatBoost Feature Selection.

### Story 4.1: Spec-Abruf und Re-Execution

Als ein Datenwissenschaftler,
möchte ich eine gespeicherte Pipeline-Spec-Version abrufen und identisch erneut ausführen können,
damit ich frühere Experimente exakt reproduzieren und mit neuen Runs vergleichen kann.

**Acceptance Criteria:**

**Given** eine Session mit mindestens einem abgeschlossenen Run
**When** `GET /v1/sessions/{id}/spec` aufgerufen wird
**Then** gibt das System die aktuelle (neueste) Pipeline-Spec als JSON zurück mit `version`, `created_at` und dem vollständigen Step-Array

**Given** eine Session mit mehreren Spec-Versionen
**When** `GET /v1/sessions/{id}/spec/{version}` mit einer gültigen Versionsnummer aufgerufen wird
**Then** gibt das System exakt die Spec dieser Version zurück

**Given** eine abgerufene Spec-Version
**When** die Spec erneut via Executor ausgeführt wird (z.B. per `/messages` mit "Führe Spec v1 erneut aus")
**Then** erzeugt die Ausführung einen neuen Run mit identischen Ergebnissen wie der originale Run (Reproduzierbarkeit)
**And** der neue Run referenziert die ursprüngliche Spec-Version (`spec_version: "v1"`)

**Given** eine nicht existierende Spec-Version
**When** `GET /v1/sessions/{id}/spec/{version}` aufgerufen wird
**Then** gibt das System HTTP 404 mit `{"error": "spec_version_not_found", ...}` zurück

---

### Story 4.2: Parameter-Anpassung per Sprache und Step-Deaktivierung

Als ein Datenwissenschaftler,
möchte ich Parameter einer bestehenden Pipeline-Spec per natürlicher Sprache anpassen und einzelne Steps deaktivieren können,
damit ich schnell Variationen ausprobieren kann ohne eine komplett neue Pipeline zu definieren.

**Acceptance Criteria:**

**Given** eine existierende Spec `v1` mit Imputation-Step (`strategy: "median"`)
**When** der Nutzer sendet `"Setze die Imputationsstrategie auf mean"`
**Then** erzeugt das System eine neue Spec-Version `v2` mit dem geänderten Parameter
**And** die alte Version `v1` bleibt unverändert in SQLite erhalten (Audit-Trail)
**And** das System gibt die neue Spec-Version in der Response zurück

**Given** eine Spec mit mehreren Steps
**When** der Nutzer einen Step per Sprache deaktiviert (z.B. `"Deaktiviere den Outlier-Handling-Step"`)
**Then** erzeugt das System eine neue Spec-Version mit `"enabled": false` für den betreffenden Step
**And** der Executor überspringt deaktivierte Steps bei der Ausführung

**Given** eine Spec mit einem deaktivierten Step
**When** `GET /v1/sessions/{id}/spec` aufgerufen wird
**Then** sind deaktivierte Steps in der Response erkennbar (`"enabled": false`) und explizit aufgeführt

**Given** eine Parameteranpassung die zu einem ungültigen Spec-Zustand führt (z.B. unbekannter Step-Typ)
**When** das System die neue Spec-Version anlegen soll
**Then** gibt das System einen strukturierten Fehler zurück und legt keine neue Version an

---

### Story 4.3: Modellvergleich und CatBoost Feature Selection

Als ein Datenwissenschaftler,
möchte ich zwei Trainings-Runs anhand ihrer Metriken gegenüberstellen und CatBoost-basierte Feature-Selektion ausführen können,
damit ich fundiert entscheiden kann welches Modell oder welche Feature-Auswahl besser für den Bike-Datensatz geeignet ist.

**Acceptance Criteria:**

**Given** zwei abgeschlossene Runs mit Modelltraining in derselben Session
**When** der Nutzer einen Vergleich anfordert (z.B. `"Vergleiche Run abc mit Run xyz"`)
**Then** gibt das System eine strukturierte Gegenüberstellung zurück: RMSE, MAE, R² beider Runs nebeneinander
**And** das System kennzeichnet den Run mit besserem R²-Wert als "besser"

**Given** eine Spec mit Step `{"type": "catboost_feature_selection", "params": {"top_n": 8}}`
**When** der Executor den Step ausführt
**Then** wird CatBoost auf den Trainingsdaten trainiert und die `top_n` wichtigsten Features anhand der Feature-Importances selektiert
**And** alle nicht selektierten Features werden aus Train- und Test-Datensatz entfernt
**And** die selektierten Feature-Namen werden im Run-Ergebnis gespeichert

**Given** ein CatBoost-Feature-Selection-Step
**When** kein `random_state` in der Spec angegeben ist
**Then** wird `random_state=42` als Default verwendet (Reproduzierbarkeit)

**Given** ein CatBoost-Feature-Selection-Step
**When** der Step über `@register_step("catboost_feature_selection")` registriert ist
**Then** erscheint er automatisch in `GET /v1/capabilities` ohne manuelle Pflege
