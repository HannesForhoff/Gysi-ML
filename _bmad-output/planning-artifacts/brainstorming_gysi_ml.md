# Brainstorming — gysi-ml Backend

> **Datum:** 2026-03-14
> **Teilnehmer:** Hannes (Entwickler), Mary (Business Analyst)
> **Scope:** Ausschließlich Backend (Python). Frontend wird später separat geplant.
> **Status:** Initiales Brainstorming — Grundlage für Epic/Story-Planung

---

## 1. Ausgangslage

### 1.1 Projektziel

Gysi-ml ist ein konversationeller ML-Assistent als Belegarbeit. Nutzer beschreiben über natürliche Sprache, was sie mit dem Bike-Datensatz machen wollen. Das LLM erzeugt ausschließlich strukturierte Aktionen (JSON). Alle Berechnungen erfolgen deterministisch im Python-Backend.

### 1.2 Aktueller Stand

- **Dokumentation:** Vollständig — Systemkonzept, Architektur, Repo-Struktur, Preprocessing-Anforderungen
- **Codebasis:** Scaffolding steht (alle Ordner + leere `__init__.py`), aber **null Zeilen Implementation**
- **Dataset:** `data/raw/bikes.csv` vorhanden (17.379 Zeilen, 12 Features)
- **EDA-Notebook:** `backend/notebooks/EDA_bikes.ipynb` vorhanden, noch leer
- **Tests:** Ordnerstruktur steht, keine Tests geschrieben
- **Pipeline-Specs:** Ordner vorhanden, keine Specs erstellt

### 1.3 Dataset-Übersicht (bikes.csv)

| Feature | Typ | Beschreibung |
| --- | --- | --- |
| `dteday` | date | Datum (YYYY-MM-DD) |
| `season` | int/kategorial | Jahreszeit (1–4) |
| `yr` | int/kategorial | Jahr (0=2011, 1=2012) |
| `mnth` | float | Monat (1–12), enthält Missing Values |
| `hr` | int | Stunde (0–23) |
| `holiday` | int/kategorial | Feiertag (0/1) |
| `weathersit` | float/kategorial | Wetterlage (1–4), enthält Missing Values |
| `temp` | float | Normalisierte Temperatur |
| `atemp` | float | Normalisierte gefühlte Temperatur |
| `hum` | float | Normalisierte Luftfeuchtigkeit |
| `windspeed` | float | Normalisierte Windgeschwindigkeit |
| `cnt` | float | Zielvariable — Anzahl Ausleihungen |

**Beobachtungen:** Das Dataset enthält bereits eingebaute Missing Values (mindestens in `mnth` und `weathersit`). Es gibt eine Mischung aus numerischen, kategorialen und zeitbezogenen Features.

---

## 2. Getroffene Entscheidungen

Folgende Punkte wurden im Brainstorming geklärt:

| Frage | Entscheidung |
| --- | --- |
| Spec-Format | **JSON** (nicht YAML) |
| LLM-Integration Timing | **Erst deterministisch bauen**, LLM-Anbindung danach |
| CatBoost Feature Selection | **Direkt einplanen** (neben sklearn-Methoden) |
| Testtiefe | Unit Tests + Integration Smoke Test, **Mindest-Coverage 85%** |
| Report-Artefakte | Kennzahlen als JSON **und** Matplotlib-Plots |
| Frontend | **Ausgeklammert** — wird in separater Phase geplant |

---

## 3. Architektur-Blöcke (Bottom-Up)

Die Implementation folgt einem Bottom-Up-Ansatz: Fundamente zuerst, darauf aufbauend die Fachlogik.

### 3.1 Block 1: Foundation — Pipeline-Infrastruktur

**Ziel:** Das Grundgerüst, auf dem alles aufbaut. Ohne diesen Block läuft kein einziger Step.

#### 3.1.1 Pipeline Spec Schema (JSON)

- JSON-Schema-Definition für die Pipeline-Spezifikation
- Felder: Datensatz-Referenz, Zielvariable, Liste der Steps (Typ + Parameter + Reihenfolge)
- Validierung über `jsonschema`-Bibliothek
- Spec ist **zentrale Quelle der Wahrheit** für den gesamten Systemzustand
- Beispiel-Spec für Bike-Dataset erstellen als Referenz

**Inhalte der Spec (geplant):**

- Datensatz und Zielvariable
- Liste der aktivierten Preprocessing-Schritte mit Parametern und Reihenfolge
- Encoding-Strategien für kategorische Features
- Time Feature Encoding Konfiguration
- Feature Selection Methoden (Filter, Wrapper, Embedded, CatBoost)
- Outlier-Regeln und Grenzwerte
- Splitting-Konfiguration (Train/Test/Validation-Ratio, Stratifikation)

#### 3.1.2 Spec Manager

- Specs laden und validieren (gegen JSON-Schema)
- Neue Versionen anlegen (jede Änderung = neue Version mit ID)
- Aktive Version tracken
- Undo-Fähigkeit vorbereiten (Versionsliste in SQLite)

#### 3.1.3 Step Registry

- Whitelist-basiertes Mapping: `step_type`-String → Python-Klasse
- Registrierung aller verfügbaren Steps
- Unbekannte Step-Types werden strikt abgelehnt
- Erweiterbar: Neue Steps registrieren ohne Executor-Änderung

#### 3.1.4 Pipeline Executor

- Führt Steps sequentiell nach Spec aus
- Input pro Step: DataFrame + Step-Config → Output: DataFrame + Report
- Einheitliches Step-Interface (alle Steps implementieren dasselbe Protokoll)
- Fehlschläge sauber abfangen, keine halben Zustände

#### 3.1.5 Persistence-Grundgerüst

- **SQLite** für: Spec-Versionen, Run-Metadata, History
- **Dateisystem** für: Artefakte (Plots, Reports, CSV-Exports)
- Tabellen-Design: specs, spec_versions, runs, artifacts
- Artifact-Store: Pfade generieren, referenzieren, konsistent ablegen

#### 3.1.6 Dataset Store

- `bikes.csv` aus `data/raw/` laden
- Grundvalidierung (Spalten vorhanden? Typen korrekt?)
- Metadaten bereitstellen (Zeilenanzahl, Spalten, Datentypen, Missing-Value-Statistik)

#### 3.1.7 Result Summarizer

- Backend-Outputs zu kompaktem JSON verdichten
- Kennzahlen, Statistiken, Artefakt-Referenzen
- Später: Input für LLM-Kontext — zunächst: menschenlesbare Zusammenfassung

---

### 3.2 Block 2: Preprocessing Steps — Fachlogik

**Ziel:** Die eigentlichen Pipeline-Bausteine. Kernstück der Belegarbeit (Phase 1).

**Design-Prinzip jedes Steps:**

1. Einheitliches Interface mit **fit/transform-Pattern**: `fit(df, config)` lernt Statistiken auf Trainingsdaten, `transform(df)` wendet sie an → verhindert Data Leakage
2. Ergebnis als `StepResult`: transformierter DataFrame + Report (JSON) + Artefakte (Plots)
3. Unabhängig testbar (Unit Tests pro Step)
4. Über Step Registry registriert (`@register_step` Decorator) und per Spec konfigurierbar
5. Keine Persistenz- oder LLM-Logik im Step selbst
6. Steps müssen per `enabled`-Flag deaktivierbar sein (z.B. Encoding unnötig für EBM)

#### 3.2.1 Missing Values Handling

**Strategien (alle konfigurierbar über Spec):**

- Variable Dropping (gesamte Spalte entfernen wenn zu viele Missing)
- List-wise Deletion (Zeilen mit Missing entfernen)
- Mean Imputation
- Median Imputation
- Hot-Deck Imputation
- Linear Interpolation
- LOCF (Last Observation Carried Forward)
- NOCB (Next Observation Carried Backward)
- NA Imputation (expliziter Marker)

**Zusatz:** Künstliche Missing Values erzeugen (für Experimente/Belegarbeit)

**Report:** Vorher/Nachher-Statistik, Anzahl betroffene Zellen, Verteilungsvergleich

#### 3.2.2 Data Splitting

- Train/Test-Split (konfigurierbare Ratio)
- Train/Test/Validation-Split (optional)
- Stratifikation nach Zielvariable oder Feature
- **Data-Leakage-Schutz:** Splitting erfolgt VOR Preprocessing-Steps, die auf Verteilungen basieren (Mean/Median-Imputation, Scaling etc.)
- Reproducibility: Seed-Parameter

**Report:** Split-Größen, Verteilung der Zielvariable pro Split

#### 3.2.3 Encoding — Kategorische Features

**One-Hot-Encoding:**

- Konfigurierbar welche Features encoded werden
- Drop-First-Option (Multikollinearität vermeiden)

**Gruppierung / Rare Category Bucketing:**

- Kategorien mit wenig Samples zusammenfassen
- Schwellenwert konfigurierbar (z.B. Kategorien < 5% → "Other")

**Report:** Originale vs. encodierte Feature-Anzahl, Kategorie-Verteilung

#### 3.2.4 Time Feature Encoding

- Datum-Spalte (`dteday`) → separate Features: Tag, Monat, Jahr
- Optional: Wochentag, Kalenderwoche
- Optional: Zyklische Kodierung (sin/cos für Monat, Stunde)
- Originale Datum-Spalte entfernen oder behalten (konfigurierbar)

**Report:** Erzeugte Features, Beispieldaten

#### 3.2.5 Feature Selection

**Manuelle Auswahl:**

- User definiert Feature-Liste in der Spec

**Filter-Methoden:**

- Korrelation (Pearson, Spearman) — hochkorrelierte Features entfernen
- Varianz-Threshold — Features mit geringer Varianz entfernen
- Mutual Information

**Wrapper/Embedded-Methoden (sklearn):**

- RFE (Recursive Feature Elimination)
- SelectFromModel

**CatBoost Feature Selection:**

- Externe Abhängigkeit — bewusst eingeplant als Ausnahme
- CatBoost-Modell trainieren, Feature Importances extrahieren, darauf selektieren

**Gruppierungen:**

- Zeitbezogene Features (hr, mnth, yr, dteday-Derivate)
- Wetterbezogene Features (weathersit, temp, atemp, hum, windspeed)
- User-definierte Gruppen

**Report:** Selektierte/entfernte Features, Ranking, Korrelationsmatrix-Plot

#### 3.2.6 Outlier Detection / Handling

- **Boxplot-basiert:** IQR-Methode, konfigurierbare Whisker
- **Winsorization:** Extremwerte auf Grenzwerte kappen
- **Z-Score-basiert:** Schwellenwert konfigurierbar
- Visualisierung: Boxplots vor/nach Behandlung (Matplotlib)

**Report:** Anzahl Outlier pro Feature, Grenzwerte, Vorher/Nachher-Boxplots

#### 3.2.7 Duplikat-Erkennung

- Exakte Duplikate erkennen und entfernen
- Feature-basierte Duplikate (Subset-Columns)
- Report: Anzahl gefundene/entfernte Duplikate

#### 3.2.8 Sample-Selektion

- Gezielte Abfragen auf das Dataset (Filterung)
- Beispiel: "Alle Samples wo weathersit == 3" (Regen)
- Konfiguration: Feature, Operator, Wert
- Verwendung: Explorative Analyse, nicht zwingend in Pipeline integriert

**Report:** Anzahl selektierter Samples, Verteilungsstatistik

---

### 3.3 Block 3: Orchestrierung — LLM-Backend-Kopplung

**Hinweis:** Wird erst NACH der deterministischen Pipeline implementiert.

#### 3.3.1 Action Models

- Pydantic-Modelle für alle LLM-Aktionen
- Typen: `ModifySpec`, `ExecutePipeline`, `Undo`, `GetStatus`, `GetReport`
- Strikte Typisierung, Validierung über Pydantic

#### 3.3.2 Action Validator

- JSON-Schema-Validierung der LLM-Ausgabe
- Semantische Guardrails:
  - Referenzierte Steps müssen in Registry existieren
  - Parameter müssen im erlaubten Bereich liegen
  - Keine verbotenen Aktionen (kein Code-Exec, kein Dateisystem-Zugriff)

#### 3.3.3 Conversation Manager

- Kontext aufbauen vor LLM-Call: aktuelle Spec, letzte Ergebnisse, Reports
- Kontext-Komprimierung (Token-Budget beachten)
- Ergebnisse nach Run verarbeiten und als Kontext zurückführen

#### 3.3.4 LLM Client

- API-Wrapper (OpenAI-kompatibel, austauschbar)
- System-Prompt mit Pipeline-Kontext, Action-Katalog, Guardrails
- Retry-Logik, Error-Handling, Timeout

#### 3.3.5 Result Summarizer (Erweiterung)

- Verdichtung der Ergebnisse speziell für LLM-Kontext
- Token-effizient, strukturiert, mit Artefakt-Referenzen

---

### 3.4 Block 4: History & Versionierung

#### 3.4.1 Spec-Versionierung

- Jede Änderung an der Spec erzeugt neue Version (auto-increment ID)
- Versionen in SQLite gespeichert (JSON-Blob + Metadaten)
- Aktive Version als Pointer (`current_version_id`)

#### 3.4.2 Undo / Rollback

- "Gehe N Schritte zurück" — aktive Version auf frühere setzen
- Keine Löschung alter Versionen (Audit-Trail)
- Bei Rollback: Neue Version erstellen die den alten Zustand kopiert (nicht einfach Pointer zurücksetzen)

#### 3.4.3 Run-Tracking

- Jeder Pipeline-Run wird mit Spec-Version verknüpft
- Artefakte pro Run gespeichert und referenziert
- Wiederholbarkeit: Gleiche Spec + gleicher Seed = gleiches Ergebnis

#### 3.4.4 Branching (Optional / Stretch-Goal)

- Parallele Pipeline-Varianten (z.B. One-Hot vs. Gruppierung vergleichen)
- Branch-Zuordnung pro Spec-Version
- Head-Pointer pro Branch
- **Bewusst als Stretch-Goal deklariert** — System funktioniert ohne Branching

---

### 3.5 Block 5: API-Schicht

#### 3.5.1 FastAPI Setup

- App-Skeleton, CORS-Config, strukturiertes Error-Handling
- Dependency Injection für Services (Spec Manager, Executor etc.)

#### 3.5.2 Chat Endpoint

- `POST /chat` — Nachricht rein → Aktion → Ergebnis → Response
- Delegiert an Orchestrierungsschicht

#### 3.5.3 Health Endpoint

- `GET /health` — Statuscheck für Monitoring/Testing

#### 3.5.4 Session Management

- Pipeline-Zustand pro Session
- Welche Spec-Version ist aktiv?

---

## 4. Vorgeschlagene Umsetzungsreihenfolge

```text
Phase 1 — Foundation
├── 1a: Spec Schema (JSON) + Validierung
├── 1b: Dataset Store (bikes.csv laden, Metadaten)
├── 1c: Step Interface + Step Registry
├── 1d: Pipeline Executor (minimal, 1 Dummy-Step)
├── 1e: Persistence Grundgerüst (SQLite + Artifact Store)
├── 1f: Result Summarizer (Basis)
└── 1g: Erster End-to-End-Durchstich (Spec → Executor → Report)

Phase 2 — Preprocessing Steps (iterativ, pro Step: Impl + Tests + Report)
├── 2a: Missing Values Handling
├── 2b: Data Splitting (Train/Test/Validation)
├── 2c: Encoding — Kategorial (One-Hot + Gruppierung)
├── 2d: Time Feature Encoding
├── 2e: Feature Selection (Manuell + Filter + CatBoost)
├── 2f: Outlier Detection / Handling
├── 2g: Duplikat-Erkennung
└── 2h: Sample-Selektion

Phase 3 — History & Versionierung
├── 3a: Spec-Versionierung im Spec Manager
├── 3b: Undo / Rollback
├── 3c: Run-Tracking (Runs ↔ Versionen ↔ Artefakte)
└── 3d: (Optional) Branching

Phase 4 — Orchestrierung (LLM-Anbindung)
├── 4a: Action Models (Pydantic)
├── 4b: Action Validator (Schema + Guardrails)
├── 4c: LLM Client (API-Wrapper)
├── 4d: Conversation Manager
└── 4e: Result Summarizer (LLM-optimiert)

Phase 5 — API-Schicht
├── 5a: FastAPI Setup + Health Endpoint
├── 5b: Chat Endpoint
└── 5c: Session Management
```

---

## 5. Querschnittsthemen

### 5.1 Testing-Strategie

- **Unit Tests:** Pro Step, pro Manager, pro Validator — isoliert mit Fixtures
- **Integration Smoke Test:** Spec laden → Pipeline durchlaufen → Artefakte prüfen
- **Mindest-Coverage:** 85%
- **Framework:** pytest
- **Test-Daten:** Fixture-basiert (kleines Subset von bikes.csv oder synthetische Daten)

### 5.2 Abhängigkeiten (Libraries)

| Library | Zweck |
| --- | --- |
| pandas | Datenmanipulation |
| scikit-learn | Preprocessing, Feature Selection, Splitting |
| catboost | Feature Selection (bewusste Ausnahme) |
| matplotlib | Visualisierung / Report-Plots |
| jsonschema | Spec-Validierung |
| pydantic | Action Models, Datenvalidierung |
| fastapi + uvicorn | API-Schicht |
| SQLite (stdlib) | Persistenz |
| pytest | Testing |
| pytest-cov | Coverage-Messung |

### 5.3 Artefakt-Strategie

- **JSON-Reports:** Kennzahlen, Statistiken, Zusammenfassungen — pro Step + pro Run
- **Matplotlib-Plots:** Boxplots, Verteilungen, Korrelationsmatrizen, Feature Importances
- **Speicherort:** `artifacts/<run_id>/` mit Unterordnern pro Step
- **Referenzierung:** Pfade in SQLite-Tabelle `artifacts`

### 5.4 Risiken und Mitigierung

| Risiko | Impact | Mitigierung |
| --- | --- | --- |
| Spec-Schema schlecht designt | Hoch — Refactoring aller Steps | Frühes Review, Beispiel-Spec vor Implementierung |
| Data Leakage bei Preprocessing | Hoch — ungültige Ergebnisse | Splitting als erster Step, klare Trennung Train/Test |
| CatBoost-Integration komplex | Mittel | Frühzeitig Spike, Fallback auf sklearn-Methoden |
| 85% Coverage schwer erreichbar | Mittel | Tests parallel zur Implementation schreiben (TDD-nah) |
| Scope Creep bei Preprocessing Steps | Mittel | Klare Priorisierung, Optional-Steps bewusst abgrenzen |

---

## 6. Erkenntnisse aus Domain/Technical Research

> Vollständiger Report: `_bmad-output/planning-artifacts/research/domain-technical-research-2026-03-14.md`

### 6.1 Architektur-relevante Erkenntnisse

| Erkenntnis | Impact auf Planung |
| --- | --- |
| **Step-Interface braucht fit/transform** — nicht nur execute() | Alle Steps müssen Statistiken auf Trainingsdaten lernen und auf Test anwenden |
| **Splitting ist architektonischer Trennpunkt** | Splitting als separater Spec-Abschnitt (nicht als Step), teilt Pipeline in Pre-Split und Post-Split |
| **EBM behandelt Missing Values + kategoriale Features nativ** | Steps müssen per `enabled`-Flag deaktivierbar sein |
| **Decorator-basierte Step Registry** | `@register_step("type")` Pattern für saubere Erweiterbarkeit |
| **temp/atemp hochkorreliert (~0.99)** | Perfektes Demo-Beispiel für Korrelationsfilter |
| **weathersit=4 extrem selten** | Demo-Case für Rare Category Bucketing |
| **Modifiziertes Dataset ohne weekday/workingday** | Time Feature Encoding muss Wochentag aus dteday ableiten |

### 6.2 Data Leakage Reihenfolge (Best Practice)

```text
VOR dem Split (verteilungsunabhängig):
  1. Duplikat-Erkennung/-Entfernung
  2. Time Feature Encoding (Datum → Tag/Monat/Jahr)
  3. Data Splitting ← TRENNPUNKT

NACH dem Split (fit auf Train, transform auf Train+Test):
  4. Missing Value Handling
  5. Outlier Detection/Handling
  6. Encoding (One-Hot, Gruppierung)
  7. Feature Selection
```

### 6.3 CatBoost Integration

- `model.select_features()` API mit `RecursiveByShapValues` Algorithmus
- Benötigt `Pool`-Objekt (Konversion im Step)
- Returns: `selected_features`, `eliminated_features` (mit Names)
- Fallback auf sklearn-Methoden wenn CatBoost nicht verfügbar

### 6.4 EBM (InterpretML) Outputs

- `explain_global()` → Feature Importance, Shape Functions, Interactions
- `explain_local()` → Einzelne Samples erklären
- Package: `interpret` (v0.7.7, MIT, aktiv gepflegt)
- Auf Bike-Dataset typischerweise R² ~0.93–0.95

---

## 7. Offene Punkte für Feinjustierung

- [ ] Detaillierte Reihenfolge innerhalb Phase 2 festlegen
- [ ] Spec-Schema konkret entwerfen (JSON, Felder, Typen, Beispiel-Spec)
- [ ] Step-Interface formalisieren (fit/transform Pattern, StepResult Dataclass)
- [ ] SQLite-Tabellendesign finalisieren
- [x] ~~Data-Leakage-Strategie~~ → Geklärt: Split als Trennpunkt
- [ ] EDA durchführen (Notebook füllen) als Grundlage für Step-Design
- [ ] Epic/Story-Schnitt aus diesem Brainstorming ableiten
- [ ] Klären: Artefakt-Format für Plots (PNG, SVG oder beides?)
- [ ] Klären: EDA als eigenständiger Step oder als separates Notebook?
