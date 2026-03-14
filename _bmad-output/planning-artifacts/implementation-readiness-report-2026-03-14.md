---
stepsCompleted: [step-01-document-discovery, step-02-prd-analysis, step-03-epic-coverage-validation, step-04-ux-alignment, step-05-epic-quality-review, step-06-final-assessment]
documentsInventoried:
  prd: _bmad-output/planning-artifacts/prd.md
  architecture: null
  epics: null
  ux: null
---

# Implementation Readiness Assessment Report

**Date:** 2026-03-14
**Project:** gysi-ml
**Assessor:** John (PM Agent)

---

## Document Inventory

| Dokumenttyp | Datei | Status |
|---|---|---|
| PRD | `_bmad-output/planning-artifacts/prd.md` | ✅ Vollständig (Steps 1–11) |
| Architecture | — | ❌ Nicht vorhanden |
| Epics & Stories | — | ❌ Nicht vorhanden |
| UX Design | — | ❌ Nicht vorhanden (erwartet: API-only) |
| Brainstorming | `_bmad-output/planning-artifacts/brainstorming_gysi_ml.md` | ✅ Referenz |
| Domain Research | `_bmad-output/planning-artifacts/research/domain-technical-research-2026-03-14.md` | ✅ Referenz |

---

## PRD Analysis

### Functional Requirements

**Session Management (FR1–FR4)**

- FR1: Nutzer kann eine neue Konversations-Session erstellen
- FR2: Nutzer kann eine laufende Session abrufen (Metadaten, Status)
- FR3: Nutzer kann alle Sessions auflisten
- FR4: Nutzer kann eine Session beenden/schließen

**Konversations-Orchestrierung (FR5–FR11)**

- FR5: Nutzer kann eine natürlichsprachliche Eingabe an eine Session senden
- FR6: Das System erkennt, ob eine Eingabe eindeutig oder vage/unvollständig ist
- FR7: Bei eindeutiger Eingabe führt das System die Aktion direkt aus
- FR8: Bei vager Eingabe gibt das System einen konkreten Ausführungsvorschlag (Proposal) mit Steps und Parametern zurück
- FR9: Nutzer kann einen Proposal bestätigen, um die Ausführung zu starten
- FR10: Nutzer kann einen Proposal ablehnen oder modifizieren
- FR11: Das System gibt eine strukturierte Liste verfügbarer Aktionen und Steps zurück (`/capabilities`)

**Pipeline-Spec & Versionierung (FR12–FR16)**

- FR12: Das System erzeugt für jede Ausführung eine versionierte Pipeline-Spec (JSON)
- FR13: Nutzer kann eine gespeicherte Pipeline-Spec abrufen
- FR14: Nutzer kann eine Pipeline-Spec erneut ausführen (Reproduzierbarkeit)
- FR15: Nutzer kann Parameter einer Pipeline-Spec per Spracheingabe anpassen (neue Version)
- FR16: Nutzer kann einzelne Steps in einer Pipeline-Spec deaktivieren

**Preprocessing Steps (FR17–FR24)**

- FR17: Das System kann Duplikate im Datensatz entfernen (Dedup)
- FR18: Das System kann fehlende Werte imputieren (Median, Mean, Most-Frequent — wählbar)
- FR19: Das System kann Ausreißer behandeln (IQR- oder Z-Score-Methode — wählbar)
- FR20: Das System kann kategorische Features encodieren (Label Encoding, One-Hot Encoding — wählbar)
- FR21: Das System kann hochkorrelierte Features filtern (Schwellwert konfigurierbar)
- FR22: Das System kann seltene Kategorien in einen Sammelbucket zusammenfassen
- FR23: Das System kann Zeit-Features aus `dteday` ableiten (Wochentag, Monat)
- FR24: Das System führt den Train/Test-Split als feste Architekturgrenze durch (Ratio konfigurierbar)

**Modelltraining & Evaluation (FR25–FR29)**

- FR25: Das System kann ein Decision-Tree-Regressionsmodell trainieren
- FR26: Das System kann ein EBM-Regressionsmodell (InterpretML) trainieren
- FR27: Das System kann CatBoost Feature Selection auf dem Datensatz ausführen
- FR28: Das System berechnet und persistiert Regressionsmetriken (RMSE, MAE, R²) für jeden Trainings-Run
- FR29: Das System kann zwei Modell-Runs anhand ihrer Metriken vergleichen

**Interpretierbarkeit & Artefakte (FR30–FR34)**

- FR30: Das System erzeugt einen globalen Feature-Importance-Plot für trainierte Modelle
- FR31: Das System erzeugt einen EBM-Global-Explanation-Plot
- FR32: Das System persistiert alle Plots als Dateien (PNG) im Filesystem
- FR33: Nutzer kann ein gespeichertes Artefakt (Plot) über die API abrufen
- FR34: Das System erzeugt eine Übersicht der Artefakte eines Runs

**Run-History & Persistenz (FR35–FR38)**

- FR35: Das System persistiert jeden Ausführungs-Run mit Input-Parametern, Ergebnissen und Artefakt-Referenzen
- FR36: Nutzer kann alle Runs einer Session auflisten
- FR37: Nutzer kann das vollständige Ergebnis eines spezifischen Runs abrufen
- FR38: Das System persistiert den vollständigen Gesprächsverlauf einer Session

**LLM-Integration (FR39–FR42)**

- FR39: Das System sendet Nutzereingaben strukturiert an ein LLM (OpenAI-kompatibler Endpunkt)
- FR40: Das System validiert LLM-Outputs gegen ein JSON-Schema vor der Ausführung
- FR41: Das System führt bei ungültigem LLM-Output einen Retry-Prompt durch
- FR42: Das System gibt dem Nutzer eine verständliche Fehlermeldung, wenn LLM-Output nach Retry weiterhin ungültig ist

**Health & Monitoring (FR43)**

- FR43: Das System stellt einen Health-Check-Endpunkt bereit (`GET /v1/health`), der den Service-Status zurückgibt

**Gesamt FRs: 43**

### Non-Functional Requirements

**Performance (NFR-P)**

- NFR-P1: Standard-Preprocessing-Schritte < 5 s (bei 17.379 Zeilen)
- NFR-P2: Decision-Tree-Training inkl. Metrikberechnung < 10 s
- NFR-P3: EBM-Training < 60 s
- NFR-P4: API-Endpunkte ohne ML-Berechnung < 500 ms

**Zuverlässigkeit (NFR-R)**

- NFR-R1: Kein Absturz bei ungültigen Nutzereingaben — strukturierte Fehler-Response
- NFR-R2: Klare Fehlermeldung bei Datenbankfehler (kein blanker 500-Error)
- NFR-R3: Atomare Ausführung (kein Halb-State in SQLite)

**Testbarkeit (NFR-T)**

- NFR-T1: Test-Coverage ≥ 85 % (pytest-cov auf `src/gysi_ml/`)
- NFR-T2: Dedizierte Unit-Tests für fit/transform-Grenze, JSON-Schema-Validierung, Proposal-Mode
- NFR-T3: Integration-Tests Happy-Path (Session → Message → Confirm → Run → Artifact)
- NFR-T4: Alle Steps isoliert testbar (kein globaler State zwischen Tests)

**Wartbarkeit (NFR-M)**

- NFR-M1: `@register_step`-Decorator für alle Preprocessing/Modeling-Steps
- NFR-M2: Open/Closed-Prinzip — neue Steps ohne Änderung bestehender Steps
- NFR-M3: Konfiguration ausschließlich in `.env` / `config.py`
- NFR-M4: Code-Style: Black-formatiert, type-annotiert, keine ungenutzten Imports

**Sicherheit (NFR-S)**

- NFR-S1: Kein LLM-Code-Exec — ausschließlich JSON-Schema-validierte Strukturen
- NFR-S2: Keine Secrets im Code — ausschließlich über `.env`
- NFR-S3: Parameterized Queries via SQLite-Stdlib

**Gesamt NFRs: 15 (in 5 Kategorien)**

### Zusätzliche Constraints (nicht als FR/NFR gelabelt)

- `random_state=42` für alle nichtdeterministischen Operationen
- `fit()` ausschließlich auf Trainingsdaten, `transform()` auf Train+Test getrennt
- Artefakte als Dateien (PNG) — kein Base64 in Responses
- Synchrone Ausführung — kein Background-Task-Framework
- SQLite als einzige Datenbankabhängigkeit

### PRD-Vollständigkeitsbewertung

Das PRD ist struktur- und inhaltsseitig **sehr solide**. Vision, Phasen, User Journeys und technische Constraints sind klar dokumentiert. Es gibt jedoch **drei konkrete Lücken**, die vor der Epics-Erstellung adressiert werden sollten (siehe Abschnitt "Kritische Lücken").

---

## Epic Coverage Validation

Keine Epics/Stories vorhanden — dieser Check ist **erwartungsgemäß nicht durchführbar**.

Alle 43 FRs sind aktuell nicht durch Epics abgedeckt. Dies ist der Ausgangszustand vor der Epic-Erstellung.

| Statistik | Wert |
|---|---|
| Gesamt PRD FRs | 43 |
| FRs abgedeckt durch Epics | 0 |
| Abdeckungsgrad | 0 % (erwartet) |

---

## UX Alignment Assessment

### UX Document Status

Nicht vorhanden — **korrekt und erwartet**.

gysi-ml ist ein reines API Backend (FastAPI REST). Kein Frontend ist für den MVP geplant. Die User Journeys im PRD beschreiben das Interaktionsmodell ausreichend für den API-Kontrakt.

### Bewertung

✅ Kein UX-Dokument erforderlich für diesen Entwicklungsstand.
✅ Journey 3 (API Consumer) definiert das programmatische Interaktionsmodell klar.
✅ OpenAPI/Swagger unter `/docs` erfüllt die Rolle der "UI-Dokumentation" für API-Konsumenten.

---

## Epic Quality Review

Keine Epics vorhanden — Review nicht durchführbar.

Die 5 Implementierungs-Phasen im PRD liefern eine solide Grundstruktur für die spätere Epic-Erstellung:

| Phase | Potenzielle Epic-Themen |
|---|---|
| Phase 1 — Foundation | Session-Management, SQLite-Schema, Step-Registry |
| Phase 2 — Preprocessing | Alle FR17–FR24 + Pipeline-Executor |
| Phase 3 — Modeling | FR25–FR34 (Training + Interpretierbarkeit + Artefakte) |
| Phase 4 — LLM | FR39–FR43 + FR5–FR11 (Orchestrierung) |
| Phase 5 — History & Polish | FR12–FR16, FR35–FR38, FR29 (Run-History, Versionierung, Vergleich) |

---

## Summary and Recommendations

### Overall Readiness Status

**✅ READY — PRD vollständig und konsistent, bereit für Epic-Erstellung**

Die 3 identifizierten Endpunkt-Lücken wurden direkt behoben. Das PRD ist jetzt intern konsistent und alle 43 FRs haben tracebare Endpunkte.

---

### Kritische Lücken (vor Epic-Erstellung schließen)

#### 🔴 Lücke 1: Fehlender `GET /v1/sessions` Endpunkt (FR3)

**Problem:** FR3 fordert "Nutzer kann alle Sessions auflisten", aber die Endpoint-Spezifikation enthält **keinen** `GET /v1/sessions` Endpunkt.

**Aktuell in der Tabelle:** `POST /v1/sessions` (erstellen) und `GET /v1/sessions/{id}` (einzeln abrufen) — aber kein Listen-Endpunkt.

**Empfehlung:** `GET /v1/sessions` zur Endpoint-Tabelle hinzufügen.

---

#### 🔴 Lücke 2: Fehlender Endpunkt zum Beenden einer Session (FR4)

**Problem:** FR4 fordert "Nutzer kann eine Session beenden/schließen", aber in der Endpoint-Tabelle gibt es **keinen** entsprechenden Endpunkt (weder `DELETE /v1/sessions/{id}` noch `POST /v1/sessions/{id}/close`).

**Empfehlung:** Endpunkt und HTTP-Methode für FR4 explizit definieren und zur Tabelle hinzufügen.

---

#### 🔴 Lücke 3: Fehlender Endpunkt für Pipeline-Spec-Abruf (FR13)

**Problem:** FR13 fordert "Nutzer kann eine gespeicherte Pipeline-Spec abrufen", aber die Endpoint-Tabelle hat **keinen** Spec-Abruf-Endpunkt (z. B. `GET /v1/sessions/{id}/spec` oder `GET /v1/sessions/{id}/spec/{version}`).

**Empfehlung:** Spec-Abruf-Endpunkt definieren — auch in Verbindung mit FR14 (Re-execute) und FR15 (Parameter anpassen).

---

### Kleinere Anmerkungen (kein Blocker)

#### 🟡 FR10 — Proposal-Ablehnung nicht spezifiziert

FR10 ("Nutzer kann einen Proposal ablehnen oder modifizieren") ist funktional definiert, aber der Mechanismus fehlt: Geht eine Ablehnung über `POST /messages` mit einem neuen Text? Oder gibt es einen eigenen `DELETE /sessions/{id}/proposal` Endpunkt? Dies sollte vor der Story-Erstellung für Phase 4 spezifiziert sein — **kein MVP-Blocker**, da Phase 4 später kommt.

#### 🟡 JSON Pipeline-Spec Schema nicht definiert

Das Format der Pipeline-Spec (JSON-Struktur, Felder, Typen) ist im PRD nicht spezifiziert. Dies ist eine Architektur-Entscheidung und gehört in das Architecture-Dokument, das noch fehlt. **Kein PRD-Blocker**, aber ein kritischer Input für Phase 2.

#### 🟡 Session-Zustände nicht als State-Machine formalisiert

Welche Zustände hat eine Session? (z.B. `pending`, `running`, `completed`, `failed`?) Relevant für FR2 (Session-Metadaten) und das SQLite-Schema. Sollte beim Architecture-Dokument oder spätestens in der Foundation-Phase-Story definiert werden.

---

### Empfohlene Nächste Schritte

1. **Sofort:** Die 3 fehlenden Endpunkte in der PRD-Endpoint-Tabelle ergänzen (FR3 + FR4 + FR13)
2. **Vor Epics:** Architecture-Dokument erstellen — insb. Pipeline-Spec JSON-Schema und Session-State-Machine
3. **Dann:** Epics & Stories auf Basis PRD + Architecture ableiten (Option B)
4. **Parallel:** Git commit & push des finalen PRD (Option C — steht noch aus)

---

### Final Note

Dieses Assessment identifizierte **3 kritische Lücken** und **3 kleinere Anmerkungen**. Die kritischen Lücken betreffen alle fehlende Endpunkte, die direkt aus bestehenden FRs folgen — das PRD ist intern inkonsistent. Diese lassen sich in **5 Minuten** durch Ergänzung der Endpoint-Tabelle beheben. Danach ist das PRD bereit für die Epic-Erstellung.
