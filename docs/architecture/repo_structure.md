```markdown
# Repo Structure Knowledge Base

Dieses Dokument beschreibt die Verantwortlichkeiten der Ordner im Repository.
Ziel ist, dass sich das Team nicht in der Struktur verliert und jede Komponente eindeutig zugeordnet ist.

## Leitprinzip
Trennung nach Verantwortung, passend zur Architektur:

- API-Schicht: nimmt Requests an und gibt Responses zurück
- Orchestrierungsschicht: entscheidet, validiert, verwaltet Kontext und Spec-Versionen
- Ausführungsschicht: führt deterministisch Steps anhand der Spec aus
- Fachlogik: Preprocessing, später Modeling und Explainability als modulare Steps
- Persistenz: SQLite für State/History, Dateisystem für Artefakte

Dadurch bleibt die Kontrolle im Backend, das LLM ist nur Generator für strukturierte Aktionen und Erklärungstexte.

## Top-Level

### README.md
Einstiegspunkt, Setup, lokale Runs, Tests, Sicherheitsregeln.

### requirements.txt, requirements-dev.txt
Abhängigkeiten für Runtime und Development (Tests, Linting optional).

### .env.example
Platzhalter für lokale Umgebungsvariablen. Keine echten Secrets.

### .local/
Lokaler Laufzeitzustand (SQLite DB, Logs, Runs). Nicht committed.

### artifacts/
Generierte Artefakte (Plots, Reports, Exports). Nicht committed.

## docs/architecture
- `diagram.drawio` Architekturdiagramm (draw.io)
- `architecture.md` Textliche Architektur, Rollen und Datenflüsse
- `spec.md` Beschreibung des Spec-Formats (Pipeline Spec + Action JSON)
- `repo_structure.md` Dieses Dokument

## configs/pipeline_specs
Pipeline-Rezepte als YAML/JSON.
Das LLM darf später Specs ändern, aber nicht den Code.

Beispiel:
- `preprocessing_only_bike.yaml` reproduzierbare Preprocessing-Pipeline

## src/jarvis_ml (Produktcode als Paket)

### api/
FastAPI Oberfläche, keine Businesslogik.
- `main.py` App Setup
- `routes/chat.py` Chat Endpoint (Message rein, Response raus)
- `routes/health.py` Healthcheck

### core/
Orchestrierung und Kontrolllogik.
- `conversation_manager.py` baut Kontext vor LLM Call und verarbeitet Resultate nach Runs
- `llm_client.py` kapselt LLM API Calls (später austauschbar)
- `action_models.py` strukturierte Datenmodelle (Actions/Responses)
- `action_validator.py` JSON Schema Validation + semantische Guardrails

### spec/
Pipeline Spec + Versionierung.
- `schema/` JSON Schemas für Spec und Actions
- `spec_manager.py` speichert Spec Versionen, Undo, optional Branching

### executor/
Deterministische Ausführung nach Spec.
- `pipeline_executor.py` führt Steps sequentiell aus
- `step_registry.py` mappt step_type Strings auf Implementierungen (Whitelist)
- `result_summarizer.py` verdichtet Outputs für LLM und UI

### steps/
Modulare Pipeline-Bausteine, referenziert durch Spec.
- `preprocessing/` pandas/sklearn Vorverarbeitung (Missing Values, Encoding, Splitting, Feature Selection usw.)
- `modeling/` Training (Trees, EBM), Default/User Parameter, optional HPO, Metriken
- `explainability/` Feature Importance, Global/Local Explanations, Shape Functions, Rules

Wichtig:
Steps enthalten keine Persistenz- oder LLM-Logik.

### persistence/
Hybrid Persistenz.
- `sqlite_store.py` State/History/Run Metadata
- `dataset_store.py` Laden/Verwalten des Bike-Datasets
- `artifact_store.py` Speichern/Referenzieren von Plots/Reports/Exports

### utils/
Hilfsfunktionen ohne Businesslogik.
- Pfade, Logging, Serialisierung, Validierungshilfen

## scripts/
Lokale Runner und Utilities.
- `init_local_state.py` initialisiert `.local` und SQLite
- `run_preprocessing_local.py` führt Spec ohne LLM aus
- `run_api_local.ps1` startet API lokal

## tests/
Unit Tests für Robustheit.
- Validator, Spec Manager, Registry, Smoke-Run der Preprocessing Spec

## notebooks/
Exploration und EDA, getrennt vom Produktcode.
Notebooks dürfen nicht die einzige Quelle von Logik werden.