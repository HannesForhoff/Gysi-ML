---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish]
inputDocuments:
  - _bmad-output/planning-artifacts/backend/brainstorming_gysi_ml.md
  - _bmad-output/planning-artifacts/backend/research/domain-technical-research-2026-03-14.md
  - docs/systemkonzept.md
  - docs/architecture/repo_structure.md
  - docs/absprache/notizen-erste-konsultation.txt
  - docs/absprache/preprocessing-anforderungen.md
workflowType: prd
documentCounts:
  productBriefs: 0
  researchDocs: 1
  projectDocs: 4
  brainstormingDocs: 1
projectClassification:
  type: api_backend
  domain: scientific
  complexity: medium
  context: brownfield
  primaryUsers: [developer (Hannes), developer (Oliver), Prof/Wissenschaftlicher Mitarbeiter (Evaluator)]
  scope: all_phases
  apiTarget: future_frontend
---

# Product Requirements Document - gysi-ml

**Author:** Hannes
**Date:** 2026-03-14

## Executive Summary

gysi-ml ist ein konversationeller ML-Assistent für den Bike-Sharing-Datensatz (UCI, 17.379 Einträge), der natürliche Sprache in reproduzierbare, versionierte ML-Pipelines übersetzt. Das System richtet sich an Studierende und technisch interessierte Einsteiger, die vollständige ML-Workflows — von Preprocessing über Modelltraining bis Interpretierbarkeit — methodisch korrekt und nachvollziehbar umsetzen wollen, ohne sich in Boilerplate-Code zu verlieren.

**Problem:** Bestehende Jupyter-basierte ML-Workflows sind schwer wiederholbar, methodisch inkonsistent (Data Leakage, unkontrolliertes Splitting) und bieten keine strukturierte Rückmeldung über den Ablauf. Es fehlt ein Werkzeug, das Methodenkompetenz fördert statt ersetzt.

**Lösung:** Nutzer formulieren Absichten in natürlicher Sprache. Das LLM interpretiert, schlägt bei vagen Eingaben konkrete Schritte vor und wartet auf Bestätigung. Das Python-Backend führt deterministisch aus und erzeugt inspizierbare Pipeline-Specs (JSON), versionierte Artefakte (Plots, Reports) und auditierbare Run-History (SQLite).

**Zielnutzer:**

- Primär: Entwickler (Hannes, Kommilitone) — bauen und validieren das System
- Sekundär: Betreuer/Wissenschaftliche Mitarbeiter/Prof — evaluieren den Prototyp als Belegarbeit

**Lieferobjekt:** Funktionierender Prototyp (Backend + REST API), demonstrierbar und im Rahmen einer Belegarbeit eingereicht.

### What Makes This Special

**Trennung von Interpretation und Ausführung als Designprinzip:** LLMs sind gut im Verstehen und Vorschlagen — zuverlässige, reproduzierbare Ausführung ist Sache des deterministischen Python-Backends. Gysi macht diese Trennung explizit und architektonisch erzwungen: das LLM erzeugt ausschließlich strukturierte JSON-Aktionen, kein Code, keine direkten API-Aufrufe.

**Bestätigungsprinzip bei Vagheit:** Bei zu ungenauen Eingaben generiert das System keinen "Best-Guess"-Ablauf still im Hintergrund — es präsentiert konkrete Vorschläge und führt erst nach expliziter Nutzer-Bestätigung aus. Der Nutzer bleibt immer Entscheider.

**Inspizierbare versionierte Pipeline-Specs:** Jede Ausführung basiert auf einer versionierten JSON-Spec. Diese ist losgelöst vom Gesprächsverlauf lesbar, wiederholbar und auf Korrektheit prüfbar — ideal für Lehre und Peer-Review.

**Methodische Korrektheit als first-class Concern:** Splitting ist eine feste Architektur-Grenze (nicht ein optionaler Step). Alle datenverändernden Steps (Imputation, Encoding, Feature Selection) folgen dem fit/transform-Muster, um Data Leakage strukturell zu verhindern.

## Project Classification

| Dimension | Wert |
|---|---|
| **Projekttyp** | API Backend (FastAPI REST) |
| **Domain** | Scientific / ML & Data Science |
| **Komplexität** | Medium |
| **Kontext** | Brownfield (Scaffold vorhanden, kein Produktionscode) |
| **Phasen-Scope** | Alle Phasen (Preprocessing → Modeling → Interpretierbarkeit → LLM-Orchestrierung → API/History) |
| **API-Ziel** | Intern + zukünftiges Frontend (noch nicht geplant) |

## Success Criteria

### User Success

- Ein Nutzer kann ohne Programmierkenntnisse eine vollständige Preprocessing + Modeling Pipeline per natürlicher Spracheingabe aufbauen, ausführen und das Ergebnis inspizieren
- Bei eindeutiger Eingabe: direkter Ausführungsstart ohne Rückfragen
- Bei vager/unvollständiger Eingabe: das System schlägt konkrete Schritte vor und führt erst nach expliziter Nutzer-Bestätigung aus
- Jede Ausführung erzeugt eine inspizierbare, versionierte Pipeline-Spec (JSON), die unabhängig vom Gesprächsverlauf reproduziert werden kann
- Plots und Reports sind als Artefakte gespeichert und referenzierbar

### Business Success

- Prototyp ist vollständig demonstrierbar gegenüber Prof/Wissenschaftlichen Mitarbeitern
- Das System deckt alle geplanten Phasen (Preprocessing, Modeling, Interpretierbarkeit, LLM-Orchestrierung, API/History) mit echten Features ab — keine Stubs
- Belegarbeit ist einreichbar und enthält einen funktionierenden, feature-reichen Prototyp als zentrales Artefakt
- Codequalität: ≥ 85 % Testabdeckung (pytest-cov), alle kritischen Pfade abgedeckt

### Technical Success

- Keine Data Leakage: alle transformierenden Steps (Imputation, Encoding, Feature Selection) via fit/transform, Training-Set-Fit, Test-Set-Transform
- Splitting ist architektonische Grenze — nicht als regulärer Step implementierbar
- LLM führt keinen Code aus und hat keinen direkten Zugriff auf das Framework — ausschließlich strukturierte JSON-Aktionen
- Pipeline-Specs sind versioniert und in SQLite auditierbar
- Run-History: jede Ausführung mit Parametern, Ergebnissen und Artefakt-Referenzen persistiert
- API ist REST-konform und für zukünftige Frontend-Anbindung vorbereitet (klare Endpunkte, JSON-Responses, CORS-bereit)

### Measurable Outcomes

| Metrik | Zielwert |
|---|---|
| Test-Coverage | ≥ 85 % (pytest-cov) |
| Preprocessing-Steps implementiert | ≥ 6 (Dedup, Missing, Outlier, Encoding, Correlation, Feature Selection) |
| Modelle implementiert | ≥ 2 (Decision Tree + EBM, optional CatBoost) |
| Artefakttypen | Plots (matplotlib), Run-Reports, Pipeline-Spec-Exports |
| Reproduzierbarkeit | Jede Pipeline via gespeicherter Spec exakt wiederholbar |
| Latenz LLM→Ausführung | < 5 s für Standard-Steps (ohne LLM-Wartezeit) |

## Product Scope

### MVP — Minimum Viable Product

Demonstrierbarer Kern-Prototyp:

- Preprocessing-Pipeline: mind. Imputation, Encoding, Correlation Filter, Splitting
- Modelltraining: Decision Tree (sklearn)
- Interpretierbarkeit: EBM (InterpretML) mit globalem Erklärungsplot
- LLM-Orchestrierung: strukturierte JSON-Aktionen → Backend-Ausführung
- Bestätigungsprinzip: Vorschlagsmodus bei vagen Eingaben
- API: FastAPI-Endpunkte für Sessions, Pipeline-Ausführung, Artefakt-Abfrage
- Persistenz: SQLite (Run-History, Spec-Versionen), Filesystem (Artefakte)

### Growth Features (Vollständige Implementierung)

Alle weiteren Features für die finale Belegarbeit:

- CatBoost Feature Selection (`select_features()`)
- Modellvergleich (Decision Tree vs. EBM, Metriken gegenübergestellt)
- Erweitertes Preprocessing: Outlier Handling (IQR/Z-Score), Rare Category Bucketing, Time-Feature-Encoding (`dteday` → `weekday`)
- Step-Deaktivierung in Pipeline-Spec (einzelne Steps an/aus)
- Erweiterter Spec-Editor (Parameteranpassung per Sprache)
- Session-History: vollständige Gesprächs- und Ausführungshistorie über SQLite
- Undo/Rollback: aktive Spec-Version auf frühere zurücksetzen ohne Löschung alter Versionen (Audit-Trail bleibt erhalten)

### Vision (Future / Post-Belegarbeit)

- Web-Frontend (Chat-Interface + Artefakt-Viewer)
- LLM-gestützte Erklärungen der Ergebnisse in natürlicher Sprache
- Multi-Dataset-Support (über Bike-Datensatz hinaus)
- Export-Funktion (Notebook-Export, PDF-Reports)

## User Journeys

### Journey 1 — Hannes (Entwickler, Hauptnutzer): Iterativer Preprocessing-Workflow

**Persona:** Hannes, Student, baut das System aktiv mit. Kennt Python und sklearn, will aber nicht für jeden Experimentierdurchlauf neuen Notebook-Code schreiben. Er möchte schnell verschiedene Preprocessing-Konfigurationen ausprobieren und die Ergebnisse vergleichen.

**Opening Scene:** Hannes öffnet eine neue Chat-Session. Er hat den rohen Bike-Datensatz und weiß, dass fehlende Werte in `mnth` und `weathersit` vorhanden sind — aber noch nicht, welche Strategie er wählen soll.

**Rising Action:**

1. Er tippt: *"Bereite den Bike-Datensatz für ein Regressionsmodell vor"*
2. Das System erkennt die Vagheit — antwortet mit einem Vorschlag: Dedup → Missing Value Imputation (Median) → Outlier Handling (IQR) → Encoding → Correlation Filter → Split (80/20). Hannes bestätigt.
3. Die Pipeline läuft durch. Das System gibt zurück: Spec-Version `v1`, 3 Duplikate entfernt, 47 fehlende Werte imputiert, 2 Features korreliert (temp/atemp) → eines entfernt, Split: 13.903 Train / 3.476 Test.
4. Hannes fragt: *"Zeig mir die Verteilung von cnt nach dem Splitting"* → Plot wird erzeugt, als Artefakt persistiert.
5. Er entscheidet, die Imputationsstrategie zu ändern: *"Setze Missing Value Strategie auf Mean"* → System erzeugt Spec `v2`, führt erneut aus.

**Climax:** Hannes vergleicht `v1` und `v2` über die Run-History. Er sieht, dass Median stabiler ist gegenüber Ausreißern im Kontext dieses Datensatzes. Er hat eine methodisch begründete Entscheidung getroffen — ohne eine einzige Zeile Code zu schreiben.

**Resolution:** Spec `v1` wird als Basis für das Modelltraining festgelegt. Hannes exportiert die Spec als JSON. Der gesamte Ablauf ist auditierbar, reproduzierbar und in SQLite dokumentiert.

**Capabilities revealed:** Session-Management, Bestätigungsprinzip, Pipeline-Spec-Versionierung, Run-History, Artefakt-Erzeugung, Parameteranpassung per Sprache.

---

### Journey 2 — Evaluator (Prof/WiMi): Selbstständige Demo-Session

**Persona:** Prof. Dr. Müller, Betreuer der Belegarbeit. Versteht ML auf konzeptioneller Ebene, programmiert nicht aktiv. Möchte den Prototyp selbst testen — nicht nur zuschauen. Sein Ziel: verstehen, ob das System ML-Konzepte korrekt umsetzt und ob die Entscheidungen des Systems nachvollziehbar sind.

**Opening Scene:** Hannes gibt dem Prof einen Link zum laufenden API-Service. Der Prof öffnet das System (Postman oder ein minimales Test-UI) und beginnt eine neue Session.

**Rising Action:**

1. Er tippt: *"Was kann dieses System?"* → Das System antwortet mit einer strukturierten Übersicht der verfügbaren Aktionen.
2. Er startet: *"Trainiere ein Modell auf dem Bike-Datensatz"* → Das System schlägt einen vollständigen Ablauf vor (Preprocessing + Decision Tree). Der Prof bestätigt.
3. Die Pipeline läuft. Das System gibt zurück: RMSE, MAE, R², Feature Importances als Plot.
4. Er fragt: *"Erkläre mir, warum Stunde das wichtigste Feature ist"* → Das System liefert den EBM-Global-Plot mit einem strukturierten Text-Summary.
5. Er testet das Bestätigungsprinzip: *"Mach was mit den Daten"* → Das System antwortet mit Vorschlägen statt blind auszuführen.

**Climax:** Der Prof sieht, dass das System nicht rät und nicht halluziniert — es macht transparent, was es tun will, wartet auf Bestätigung, und liefert inspizierbare Ergebnisse. Er versteht, dass das LLM Übersetzer ist, nicht Entscheider.

**Resolution:** Der Prof ist überzeugt, dass das System methodisch korrekt arbeitet und didaktisch sinnvoll ist.

**Capabilities revealed:** Onboarding/Help-Endpunkt, vollständiger Happy-Path (Preprocessing + Training + Erklärung), EBM-Visualisierung, Bestätigungsprinzip bei Vagheit, lesbare Ergebnis-Outputs.

---

### Journey 3 — API-Konsument (zukünftiges Frontend / Postman): Programmatische Integration

**Persona:** Kein menschlicher Nutzer — repräsentiert einen HTTP-Client (Postman heute, Browser-Frontend morgen). Diese Journey definiert, wie die API von außen konsumiert wird.

**Opening Scene:** Ein Frontend-Client öffnet eine neue Session, sendet eine Nutzereingabe als JSON-Payload, empfängt strukturierte Antworten und rendert Artefakte.

**Rising Action:**

1. `POST /sessions` → Session-ID zurück
2. `POST /sessions/{id}/messages` mit `{"text": "Bereite Daten vor"}` → Antwort: `{"type": "proposal", "steps": [...], "confirmation_required": true}`
3. `POST /sessions/{id}/confirm` → Ausführung startet, Status-Response
4. `GET /sessions/{id}/runs/{run_id}` → Ergebnisse, Metriken, Artefakt-Referenzen
5. `GET /artifacts/{artifact_id}` → Plot als Byte-Stream (PNG)

**Climax:** Alle Responses sind konsistent strukturiert (JSON), zustandslos und idempotent.

**Resolution:** Das Frontend kann auf Basis dieser API gebaut werden, ohne das Backend zu kennen.

**Capabilities revealed:** Session-Endpunkte, Message-Endpunkt mit Proposal-Response, Confirm-Endpunkt, Run-Status-Endpunkt, Artefakt-Download-Endpunkt, konsistentes JSON-Response-Schema.

### Journey Requirements Summary

| Capability | Aus Journey |
|---|---|
| Session-Management (Create, List, Get) | J1, J2, J3 |
| Bestätigungsprinzip / Proposal-Mode | J1, J2, J3 |
| Pipeline-Spec-Versionierung | J1 |
| Run-History mit Parametern & Metriken | J1, J2 |
| Artefakt-Erzeugung & -Abruf (Plots) | J1, J2, J3 |
| EBM-Erklärungsplot (global) | J2 |
| Help / Capabilities-Endpunkt | J2 |
| Parameteranpassung per Sprache | J1 |
| Konsistentes JSON-Response-Schema | J3 |
| CORS-Vorbereitung für Frontend | J3 |

## Domain-Specific Requirements

### Reproduzierbarkeit

- Identischer Input muss immer identischen Output erzeugen
- Alle Random Seeds werden fixiert (`random_state=42`)
- Keine nichtdeterministischen Operationen ohne explizite Kennzeichnung und Dokumentation

### Wissenschaftliche Validierungsmethodik

- Train/Test-Split ist architektonisch erzwungen — nicht als optionaler Step konfigurierbar
- Standardmetriken für Regression: RMSE, MAE, R² — konsistent berechnet und persistiert
- `fit()` ausschließlich auf Trainingsdaten; `transform()` auf Test- und Trainingsdaten getrennt
- Keine Parameter-Übernahme über Split-Grenzen (kein Look-ahead-Bias)

### Nachvollziehbarkeit & Auditierbarkeit

- Jede Entscheidung (Schritt, Parameter, Ergebnis, Artefakt) ist persistiert und referenzierbar
- Pipeline-Specs sind menschenlesbar (JSON) und unabhängig vom Gesprächsverlauf reproduzierbar
- Kein intransparentes "Magic Black Box"-Verhalten — das System erklärt was es tut, bevor es es tut

### Technische Constraints

- Alle schweren Berechnungen (Training, Transformation) laufen synchron im Backend — kein Async ohne expliziten Status-Endpunkt
- Artefakte (Plots) werden als Dateien persistiert, nicht als Base64 in Responses eingebettet
- SQLite als einzige Datenbankabhängigkeit — keine externen Dienste erforderlich

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Hybrid-Orchestrierung: LLM als reiner Übersetzer**

Gestehende "AI-gestützte Data Science Tools" (Julius AI, ChatGPT Code Interpreter) lassen das LLM Code generieren und direkt ausführen. Gysi trennt diese Verantwortlichkeiten explizit:

- Das LLM erzeugt ausschließlich strukturierte JSON-Aktionsbeschreibungen — kein Code, keine direkten Framework-Aufrufe
- Das Python-Backend ist der alleinige Ausführungs-Aktor — deterministisch, testbar, auditierbar
- Diese Trennung macht das System sicher, reproduzierbar und unabhängig von LLM-Versionen

**2. Bestätigungsprinzip als didaktisches Designprinzip**

Bei vagen Nutzereingaben führt das System nicht einfach einen "Best-Guess"-Ablauf aus. Es:

1. Erkennt die Vagheit
2. Generiert einen konkreten Vorschlag (was würde ich tun und mit welchen Parametern?)
3. Wartet auf explizite Nutzer-Bestätigung

Das ist nicht nur eine UX-Entscheidung — es ist didaktisch motiviert: Der Nutzer muss verstehen und aktiv zustimmen, bevor das System handelt. Methodenkompetenz wird gefördert, nicht umgangen.

### Marktkontext & Abgrenzung

| System | LLM-Rolle | Ausführung | Reproduzierbar | Bestätigungsprinzip |
|---|---|---|---|---|
| ChatGPT Code Interpreter | Codegenerator + Ausführer | LLM direkt | Nein | Nein |
| Julius AI | Codegenerator | LLM direkt | Bedingt | Nein |
| **Gysi** | **Reiner Übersetzer (JSON)** | **Python-Backend** | **Ja** | **Ja** |

### Validierungsansatz

- Hybrid-Orchestrierung: Unit-Tests auf JSON-Schema-Validierung + Integration-Tests auf deterministisches Ausführungsverhalten
- Bestätigungsprinzip: Testfälle mit absichtlich vagen Inputs — System muss immer Proposal-Response liefern, nie direkt ausführen

### Risiken & Mitigierungen

| Risiko | Mitigierung |
|---|---|
| LLM generiert ungültiges JSON | JSON-Schema-Validierung vor jeder Ausführung; Fehler-Response mit Erklärung |
| LLM interpretiert Vagheit als klar | Konfidenz-Score oder explizite "unclear"-Klassifizierung im LLM-Prompt |
| Nutzer bestätigt blind ohne zu lesen | Proposal-Response muss menschenlesbar und präzise formuliert sein |

## API Backend Specific Requirements

### Project-Type Overview

gysi-ml exponiert eine versionierte REST API (`/v1/`) als einzige Schnittstelle zwischen Nutzern/Clients und der ML-Pipeline. Alle Interaktionen laufen über HTTP JSON — kein direkter Python-Zugriff, keine Seitenpfade.

### Endpoint Specification

| Method | Path | Zweck |
|---|---|---|
| `POST` | `/v1/sessions` | Neue Session starten |
| `GET` | `/v1/sessions` | Alle Sessions auflisten (FR3) |
| `GET` | `/v1/sessions/{id}` | Session-Metadaten abrufen |
| `DELETE` | `/v1/sessions/{id}` | Session beenden/schließen (FR4) |
| `POST` | `/v1/sessions/{id}/messages` | Nutzereingabe senden → Proposal- oder Execute-Response |
| `POST` | `/v1/sessions/{id}/confirm` | Proposal bestätigen → Ausführung starten |
| `GET` | `/v1/sessions/{id}/runs` | Alle Runs einer Session auflisten |
| `GET` | `/v1/sessions/{id}/runs/{run_id}` | Run-Ergebnis, Metriken, Artefakt-Referenzen |
| `GET` | `/v1/sessions/{id}/spec` | Aktuelle Pipeline-Spec abrufen (FR13) |
| `GET` | `/v1/sessions/{id}/spec/{version}` | Bestimmte Spec-Version abrufen (FR13/FR14) |
| `GET` | `/v1/artifacts/{artifact_id}` | Artefakt (Plot als PNG/Bytes) abrufen |
| `GET` | `/v1/capabilities` | Verfügbare Aktionen und Steps auflisten |
| `GET` | `/v1/health` | Service-Status-Check (Monitoring/Testing) |

### Authentication Model

- Prototyp: kein Auth — API läuft lokal/intern
- Architektur ist für späteren API-Key-Mechanismus offen (Header `X-API-Key`) — kein Refactoring erforderlich

### Data Formats

- Alle Requests und Responses: `application/json`
- Artefakt-Download (`/artifacts/{id}`): `image/png` oder `application/octet-stream`
- Response-Struktur für `/messages`: immer typisiert — entweder `{"type": "proposal", "steps": [...], "confirmation_required": true}` oder `{"type": "result", "run_id": "..."}` — kein freier Text als primäre Response

### API Versioning

- Alle Endpunkte unter `/v1/` — ermöglicht Breaking Changes in `/v2/` ohne bestehende Clients zu brechen
- Keine automatische Weiterleitung von `/` nach `/v1/`

### Technical Architecture Considerations

- FastAPI mit automatischer OpenAPI-Dokumentation unter `/docs`
- Pydantic v2 für Request/Response-Validierung — alle Schemas explizit definiert
- CORS aktiviert für `localhost`-Origins (Frontend-Entwicklung)
- Synchrone Ausführung — kein Background-Task-Framework; bei langen Operationen gibt der Endpunkt direkt zurück wenn fertig
- Fehler-Responses folgen einheitlichem Schema: `{"error": "...", "detail": "...", "code": "..."}`

### Implementation Considerations

- OpenAPI-Spec (`/openapi.json`) ist das Vertragsdokument für das spätere Frontend
- Kein SDK erforderlich — die API ist selbstbeschreibend genug für Postman/Frontend-Direktnutzung

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — minimale Funktionsmenge, die den vollständigen Kern-Workflow (Spracheingabe → Pipeline-Ausführung → Ergebnis) demonstrierbar macht.

**Ressourcen:** 2 Entwickler (Hannes + Kommilitone), Belegarbeit-Kontext.

### Implementierungs-Phasen

**Phase 1 — Foundation**

FastAPI-Grundgerüst, Session-Model, SQLite-Schema (sessions, runs, artifacts, spec_versions), Step-Registry (`@register_step`-Decorator), Basis-Persistenzschicht.

*Alle weiteren Phasen bauen hierauf auf.*

**Phase 2 — Preprocessing Pipeline**

Alle Preprocessing-Steps mit fit/transform-Interface: Dedup, Missing Value Imputation, Outlier Handling (IQR/Z-Score), Encoding (Label/One-Hot), Correlation Filter, Rare Category Bucketing, Time-Feature-Encoding (`dteday` → `weekday`). Pipeline-Executor + JSON-Spec-Validierung. Train/Test-Split als architektonische Grenze.

**Phase 3 — Modeling & Interpretierbarkeit**

Decision Tree (sklearn), EBM (InterpretML), Metriken (RMSE, MAE, R²), Feature-Importance-Plots (matplotlib), Artefakt-Persistenz im Filesystem.

**Phase 4 — LLM-Orchestrierung**

LLM-Integration (OpenAI-kompatible API), JSON-Schema-Validierung der LLM-Outputs, Proposal-Mode (Vagheits-Erkennung + Vorschlag + Bestätigung), System-Prompt-Design.

**Phase 5 — History, CatBoost & Polish**

Run-History-Endpunkte, Spec-Versionierung, CatBoost Feature Selection, Modellvergleich, Step-Deaktivierung, vollständige Test-Coverage (≥ 85 %), API-Dokumentation.

### Risiko-Mitigierungsstrategie

**Technisches Hauptrisiko: LLM-Prompt-Engineering**
Risiko: LLM liefert inkonsistent strukturierte JSON-Outputs — bricht die gesamte Ausführungskette.
Mitigierung: JSON-Schema-Validierung vor jeder Ausführung; automatischer Retry-Prompt bei Validierungsfehler; Fallback auf strukturierte Fehlermeldung an Nutzer.

**Ressourcenrisiko: Zeitbudget Belegarbeit**
Risiko: Phase 4+5 werden nicht vollständig fertig.
Mitigierung: Phase 1-3 sind unabhängig von LLM demonstrierbar (Script-Mode als Fallback); jede Phase ist einzeln deploybar und testbar.

**Wissenschaftliches Risiko: Data Leakage**
Risiko: fit/transform-Grenze wird durch Refactoring versehentlich verletzt.
Mitigierung: Architektonische Erzwingung (Splitting vor Steps, die fit() aufrufen); Unit-Tests prüfen explizit auf korrekte fit/transform-Trennung.

## Functional Requirements

### Session Management

- FR1: Nutzer kann eine neue Konversations-Session erstellen
- FR2: Nutzer kann eine laufende Session abrufen (Metadaten, Status)
- FR3: Nutzer kann alle Sessions auflisten
- FR4: Nutzer kann eine Session beenden/schließen

### Konversations-Orchestrierung

- FR5: Nutzer kann eine natürlichsprachliche Eingabe an eine Session senden
- FR6: Das System erkennt, ob eine Eingabe eindeutig oder vage/unvollständig ist
- FR7: Bei eindeutiger Eingabe führt das System die Aktion direkt aus
- FR8: Bei vager Eingabe gibt das System einen konkreten Ausführungsvorschlag (Proposal) mit Steps und Parametern zurück
- FR9: Nutzer kann einen Proposal bestätigen, um die Ausführung zu starten
- FR10: Nutzer kann einen Proposal ablehnen oder modifizieren
- FR11: Das System gibt eine strukturierte Liste verfügbarer Aktionen und Steps zurück (`/capabilities`)

### Pipeline-Spec & Versionierung

- FR12: Das System erzeugt für jede Ausführung eine versionierte Pipeline-Spec (JSON)
- FR13: Nutzer kann eine gespeicherte Pipeline-Spec abrufen
- FR14: Nutzer kann eine Pipeline-Spec erneut ausführen (Reproduzierbarkeit)
- FR15: Nutzer kann Parameter einer Pipeline-Spec per Spracheingabe anpassen (neue Version)
- FR16: Nutzer kann einzelne Steps in einer Pipeline-Spec deaktivieren

### Preprocessing Steps

- FR17: Das System kann Duplikate im Datensatz entfernen (Dedup)
- FR18: Das System kann fehlende Werte imputieren (Median, Mean, Most-Frequent — wählbar)
- FR19: Das System kann Ausreißer behandeln (IQR- oder Z-Score-Methode — wählbar)
- FR20: Das System kann kategorische Features encodieren (Label Encoding, One-Hot Encoding — wählbar)
- FR21: Das System kann hochkorrelierte Features filtern (Schwellwert konfigurierbar)
- FR22: Das System kann seltene Kategorien in einen Sammelbucket zusammenfassen
- FR23: Das System kann Zeit-Features aus `dteday` ableiten (Wochentag, Monat)
- FR24: Das System führt den Train/Test-Split als feste Architekturgrenze durch (Ratio konfigurierbar)

### Modelltraining & Evaluation

- FR25: Das System kann ein Decision-Tree-Regressionsmodell trainieren
- FR26: Das System kann ein EBM-Regressionsmodell (InterpretML) trainieren
- FR27: Das System kann CatBoost Feature Selection auf dem Datensatz ausführen
- FR28: Das System berechnet und persistiert Regressionsmetriken (RMSE, MAE, R²) für jeden Trainings-Run
- FR29: Das System kann zwei Modell-Runs anhand ihrer Metriken vergleichen

### Interpretierbarkeit & Artefakte

- FR30: Das System erzeugt einen globalen Feature-Importance-Plot für trainierte Modelle
- FR31: Das System erzeugt einen EBM-Global-Explanation-Plot
- FR32: Das System persistiert alle Plots als Dateien (PNG) im Filesystem
- FR33: Nutzer kann ein gespeichertes Artefakt (Plot) über die API abrufen
- FR34: Das System erzeugt eine Übersicht der Artefakte eines Runs

### Run-History & Persistenz

- FR35: Das System persistiert jeden Ausführungs-Run mit Input-Parametern, Ergebnissen und Artefakt-Referenzen
- FR36: Nutzer kann alle Runs einer Session auflisten
- FR37: Nutzer kann das vollständige Ergebnis eines spezifischen Runs abrufen
- FR38: Das System persistiert den vollständigen Gesprächsverlauf einer Session

### LLM-Integration

- FR39: Das System sendet Nutzereingaben strukturiert an ein LLM (OpenAI-kompatibler Endpunkt)
- FR40: Das System validiert LLM-Outputs gegen ein JSON-Schema vor der Ausführung
- FR41: Das System führt bei ungültigem LLM-Output einen Retry-Prompt durch
- FR42: Das System gibt dem Nutzer eine verständliche Fehlermeldung, wenn LLM-Output nach Retry weiterhin ungültig ist

### Health & Monitoring

- FR43: Das System stellt einen Health-Check-Endpunkt bereit (`GET /v1/health`), der den Service-Status zurückgibt

## Non-Functional Requirements

### Performance

- Standard-Preprocessing-Schritte (Imputation, Encoding, Dedup) schließen in < 5 s ab (bei 17.379 Zeilen)
- Decision-Tree-Training inkl. Metrikberechnung schließt in < 10 s ab
- EBM-Training schließt in < 60 s ab
- API-Endpunkte ohne ML-Berechnung antworten in < 500 ms
- LLM-Wartezeit ist explizit ausgenommen (externe Abhängigkeit, nicht kontrollierbar)

### Zuverlässigkeit

- Das System stürzt bei ungültigen Nutzereingaben nicht ab — jede Exception wird abgefangen und als strukturierte Fehler-Response zurückgegeben
- Bei fehlgeschlagenem Datenbankzugriff gibt das System eine klare Fehlermeldung zurück, nicht einen 500-Error ohne Kontext
- Jede Ausführung ist atomar: entweder vollständig persistiert oder vollständig rükgängig gemacht (kein Halb-State in SQLite)

### Testbarkeit

- Test-Coverage ≥ 85 % (pytest-cov, gemessen auf `src/gysi_ml/`)
- Alle kritischen Pfade (fit/transform-Grenze, JSON-Schema-Validierung, Proposal-Mode) haben dedizierte Unit-Tests
- Integration-Tests decken den vollständigen Happy-Path (Session → Message → Confirm → Run → Artifact) ab
- Alle Steps sind isoliert testbar (kein globaler State zwischen Tests)

### Wartbarkeit

- Jeder Preprocessing- und Modeling-Step ist als eigenständige Klasse implementiert (`@register_step`-Decorator) — keine Monolith-Funktionen
- Neue Steps können hinzugefügt werden, ohne bestehende Steps oder den Executor zu modifizieren (Open/Closed-Prinzip)
- Konfiguration (Datenpfade, LLM-Endpoint, Artefakt-Verzeichnis) liegt ausschließlich in `.env` / `config.py` — keine hartcodierten Werte im Produktionscode
- Code-Style: Black-formatiert, type-annotiert, keine ungenutzten Imports

### Sicherheit (Basisanforderungen)

- LLM-Outputs werden niemals direkt als Code ausgeführt — ausschließlich JSON-Schema-validierte Strukturen werden verarbeitet
- Keine Secrets (API-Keys, DB-Pfade) im Quellcode oder in committed Dateien — ausschließlich über `.env`
- Eingaben von Nutzern werden nicht direkt in SQL-Queries interpoliert (Parameterized Queries via SQLite-Stdlib)
