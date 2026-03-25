---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: complete
completedAt: '2026-03-21'
inputDocuments:
  - _bmad-output/planning-artifacts/backend/prd.md
  - _bmad-output/planning-artifacts/shared/feature-backlog-usability-tests-2026-03-21.md
  - docs/systemkonzept.md
  - docs/architecture/repo_structure.md
  - _bmad-output/planning-artifacts/frontend/ux-design-specification.md
  - _bmad-output/planning-artifacts/backend/research/domain-technical-research-2026-03-14.md
workflowType: architecture
project_name: gysi-ml
user_name: Hannes
date: '2026-03-21'
focus: 'Feature-Backlog 2026-03-21 — 4 neue Backend-Features'
---

# Architecture Decision Document — gysi-ml

_Dieses Dokument entsteht kollaborativ durch schrittweise Entscheidungsfindung zwischen Hannes und Winston (Architect)._
_Scope: Neue Features aus dem Feature-Backlog (Usability-Tests 2026-03-21)_

---

## Projekt-Kontext-Analyse

**Projekttyp:** API Backend (Brownfield-Erweiterung) | **Stack:** FastAPI + Python + SQLite + uv

### Neue Functional Requirements

| Kategorie | FRs | Architektur-Implikation |
|-----------|-----|------------------------|
| F1 Onboarding/Slash-Commands | FR-OB1–OB5 | Command-Router-Layer vor LLM in `MessageService` |
| F2 Datensatz-Profilierung | FR-DO1–DO3 | Neuer `ProfilingService`, isoliert, kein Spec-Eingriff |
| F3 Schrittweise Ausführung | FR-SE1–SE4 | Session-State-Erweiterung, Confirm-Contract-Änderung, neuer Response-Typ |
| F4 Pipeline-Versionsbaum | FR-VB1–VB5 | Schema-Migration `spec_versions`, Spec-Diff-Utility, Rollback-Logik |

### Kritische Beobachtungen

- **F3 bricht Request-Stateless-Muster:** Step-by-Step erfordert Zwischen-State über mehrere HTTP-Requests
- **F4 erfordert Schema-Migration:** `spec_versions` hat kein `parent_spec_id` — ohne Migration kein Baum
- **F1 ist niedriges Risiko:** Reine Erweiterung, LLM-Pfad bleibt unangetastet
- **F2 ist vollständig isolierbar:** Nur CSV-Read, keine Spec-Mutation
- **LLM-Prompts müssen erweitert werden:** Profiling-Kontext (F2) und Version-History (F4) fließen in `prompts.py`

### Offene Architektur-Fragen

1. **F3:** Wo lebt der Step-by-Step Zwischenzustand? In-Memory vs. serialisiert?
2. **F4:** Rollback via LLM-Aktion oder dedizierter Endpunkt?
3. **F4:** Spec-Diff-Granularität: Step-Level oder Parameter-Level?
4. **F1:** Welcome-Message: statisch oder sessionstate-abhängig personalisiert?

### Technologie-Basis (Brownfield — bestätigt)

| Schicht | Technologie | Version |
|---------|-------------|---------|
| API | FastAPI | bestehend |
| Sprache | Python 3.10/3.11 | bestehend |
| Persistenz | SQLite via `database.py` | bestehend |
| Paketverwaltung | uv | bestehend |
| ML-Steps | pandas + scikit-learn + InterpretML | bestehend |
| Tests | pytest + pytest-cov | bestehend |

_Kein neues Starter-Template. Alle neuen Features sind Erweiterungen der bestehenden Architektur._

---

## Kern-Architektur-Entscheidungen

### Entscheidung 1 — F1: Command-Router-Platzierung

**Entschieden: B — Separater `CommandService`**

- Neue Klasse `services/command_service.py`, aufgerufen aus `MessageService`
- Eigenständig testbar ohne LLM-Mock
- Help-Texte als separate Konfigurationsdatei (YAML)
- Klare Trennung für Beleg-Argumentation darstellbar

### Entscheidung 2 — F1: Welcome-Message Delivery

**Entschieden: C — Beides (Response-Body + persistierte Message)**

- `POST /sessions`-Response enthält `welcome_message`-Feld
- Gleichzeitig wird eine `role: assistant`-Message in der Session angelegt
- Frontend bekommt die Message sofort ohne zweiten Request
- History-Konsistenz: Welcome-Message ist dauerhaft abrufbar

### Entscheidung 3 — F2: Profiling-Caching

**Entschieden: C — Modul-Level-Cache (Singleton)**

- Rohdatensatz-Profiling: `@functools.lru_cache` auf Lade-Funktion — einmal berechnet, gilt für alle Sessions
- Post-Preprocessing-Profiling (FR-DO3): immer frisch berechnet (sessionspezifisch)
- Bike-Datensatz ist statisch → kein Invalidierungsproblem

### Entscheidung 4 — F3: Step-by-Step Zustand

**Entschieden: B — SQLite (neue Tabelle `step_states`)**

- Neue Tabelle `step_states` mit serialisiertem State als JSON
- Persistent über Server-Neustarts hinweg
- Debug-fähig (State ist direkt in DB inspizierbar)
- DataFrame wird **nicht** in DB serialisiert — nur Step-Metadaten; DataFrame wird bei Fortführung neu berechnet (deterministisch aus abgeschlossenen Steps)

### Entscheidung 5 — F3: StepByStepState Struktur

**Entschieden: Bestätigt**

```python
@dataclass
class StepByStepState:
    session_id: str
    proposal_id: str
    remaining_steps: list[StepSpec]
    completed_steps: list[CompletedStep]
    # DataFrame wird NICHT persistiert — bei Fortführung deterministisch neu berechnet
    confirmed_step_indices: list[int]
    created_at: str
    last_updated_at: str
```

### Entscheidung 6 — F4: Rollback-Mechanismus

**Entschieden: C — Beides (LLM-Aktion UND dedizierter Endpunkt)**

- **LLM-Aktion:** `{"action_type": "rollback", "target_spec_id": "..."}` — für Chat-basierte Navigation
- **Endpunkt:** `POST /v1/sessions/{id}/rollback` mit `{"target_spec_id": "..."}` — für Frontend-Klick auf Versionsbaum-Knoten
- Beide Pfade rufen dieselbe Backend-Logik auf (DRY)

### Entscheidung 7 — F4: Spec-Diff-Granularität

**Entschieden: C — Hybrid (Step-Level + geänderte Parameter)**

- Hinzugefügte Steps: `+ outlier_handling (IQR)`
- Entfernte Steps: `− correlation_filter`
- Geänderte Parameter: `imputation: median → mean`
- Aktivierung/Deaktivierung: `encoding: deaktiviert`
- Unveränderte Step-Parameter werden **nicht** aufgelistet (kein Noise)
---

## Implementierungs-Patterns & Konsistenz-Regeln

### Naming-Konventionen

| Bereich | Muster | Beispiel |
|--------|--------|---------|
| SQLite-Tabellen | `snake_case`, Singular | `step_state`, `spec_version` |
| SQLite-Spalten | `snake_case` | `parent_spec_id`, `change_summary` |
| API-Endpunkte | `kebab-case`, REST unter `/v1/sessions/{id}/` | `/v1/sessions/{id}/spec/tree` |
| Python-Klassen | `PascalCase` | `CommandService`, `StepByStepState` |
| Python-Funktionen/Variablen | `snake_case` | `handle_slash_command`, `remaining_steps` |
| Neue Service-Dateien | `services/<name>_service.py` | `command_service.py`, `profiling_service.py` |
| Neue Repository-Dateien | `persistence/<name>_repository.py` | `step_state_repository.py` |

### API Response Patterns

```python
# POST /sessions — erweitertes Response-Schema (F1)
class CreateSessionResponse(BaseModel):
    session_id: str
    name: str
    created_at: str
    welcome_message: str                         # NEU — F1

# POST /sessions/{id}/confirm — erweiterter Request-Body (F3)
class ConfirmProposalRequest(BaseModel):
    proposal_id: str
    confirmed_steps: list[int] | None = None     # NEU — F3 (Indices)
    mode: Literal["all", "step_by_step"] = "all" # NEU — F3

# Neuer Response-Typ für Step-by-Step (F3)
class StepResultResponse(BaseModel):
    type: Literal["step_result"]
    completed_step: CompletedStepSchema
    remaining_steps: list[StepSpecSchema]
    next_action: str

# Error-Format (unverändert)
{"detail": "Fehlerbeschreibung"}
```

### Slash-Command Pattern (F1)

```python
KNOWN_COMMANDS = ["/help", "/overview", "/status"]

def is_slash_command(content: str) -> bool:
    return content.strip().startswith("/")
# Unbekannte Commands → Liste der verfügbaren Commands, kein LLM, kein Exception
```

### Step-by-Step State Pattern (F3)

- DataFrame wird **nicht** in `step_states` persistiert
- Bei Fortführung deterministisch neu berechnet (Bike-CSV + abgeschlossene Steps)
- Nur Metadaten in DB: `remaining_steps` (JSON), `completed_steps` (JSON), `confirmed_step_indices` (JSON)

### Spec-Diff Pattern (F4)

```python
# spec/spec_diff.py — reine Utility-Funktion, kein Service, keine Klasse
def spec_diff(old_spec: PipelineSpec, new_spec: PipelineSpec) -> str:
    """Gibt kompaktes change_summary zurück. Kein Newline."""
    # Format: "+ outlier_handling (IQR), imputation: median → mean"
```

### LLM-Kontext-Injection Pattern

```python
# llm/prompts.py — optionale Blöcke, Bestandsmuster fortführen
if profiling_result:
    context += f"\n\n## Datensatz-Profil\n{profiling_result.to_compact_str()}"
if version_tree:
    context += f"\n\n## Spec-Versionen\n{version_tree.to_compact_str()}"
```

---

## Projektstruktur & Grenzen

### Neue + geänderte Dateien

```
backend/src/gysi_ml/
├── api/
│   ├── schemas.py                     ← ÄNDERN: CreateSessionResponse + welcome_message
│   │                                             ConfirmProposalRequest + confirmed_steps + mode
│   │                                             StepResultResponse, VersionTreeResponse, RollbackRequest (NEU)
│   └── routes/
│       ├── sessions.py                ← ÄNDERN: Welcome-Message in POST /sessions
│       ├── messages.py                ← ÄNDERN: Slash-Command-Routing vor LLM
│       ├── confirm.py                 ← ÄNDERN: confirmed_steps + mode + Step-by-Step Logic
│       ├── specs.py                   ← ÄNDERN: GET /spec/tree Endpunkt hinzufügen
│       └── rollback.py                ← NEU: POST /sessions/{id}/rollback
├── services/
│   ├── message_service.py             ← ÄNDERN: CommandService-Aufruf vorschalten
│   ├── proposal_service.py            ← ÄNDERN: Step-Selektion + Step-by-Step-Modus
│   ├── command_service.py             ← NEU (F1): Slash-Command-Router
│   └── profiling_service.py           ← NEU (F2): Datensatz-Profilierung
├── persistence/
│   ├── schema.py                      ← ÄNDERN: step_states Tabelle + spec_versions Migration
│   ├── spec_repository.py             ← ÄNDERN: parent_spec_id setzen, Rollback-Logik
│   └── step_state_repository.py       ← NEU (F3): CRUD für step_states
├── spec/
│   └── spec_diff.py                   ← NEU (F4): spec_diff() Utility-Funktion
├── llm/
│   └── prompts.py                     ← ÄNDERN: Profiling + Versionsbaum Kontext-Blöcke
└── utils/
    └── data_loader.py                 ← ÄNDERN: @lru_cache auf Bike-CSV-Ladevorgang

backend/configs/
└── help_texts.yaml                    ← NEU (F1): Help-Inhalte für /help (nicht hartcodiert)
```

### Schema-Änderungen (SQLite)

```sql
-- NEU: step_states (F3)
CREATE TABLE step_states (
    state_id                TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL,
    proposal_id             TEXT NOT NULL,
    remaining_steps_json    TEXT NOT NULL,
    completed_steps_json    TEXT NOT NULL,
    confirmed_indices_json  TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    last_updated            TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- MIGRATION: spec_versions erweitern (F4)
ALTER TABLE spec_versions ADD COLUMN parent_spec_id TEXT REFERENCES spec_versions(spec_id);
ALTER TABLE spec_versions ADD COLUMN change_summary TEXT;
```

### API-Endpunkte Delta

| Methode | Pfad | Änderung | Feature |
|---------|------|----------|---------|
| `POST` | `/v1/sessions` | Response + `welcome_message` | F1 |
| `POST` | `/v1/sessions/{id}/messages` | Slash-Command-Routing vorgeschaltet | F1 |
| `POST` | `/v1/sessions/{id}/confirm` | + `confirmed_steps`, `mode` im Body | F3 |
| `GET` | `/v1/sessions/{id}/spec/tree` | NEU — Versionsbaum | F4 |
| `POST` | `/v1/sessions/{id}/rollback` | NEU — Rollback auf Spec-Version | F4 |

### Komponenten-Datenfluss

```
POST /messages
  └─ MessageService
       ├─ [Slash?] → CommandService.handle() → Response (KEIN LLM)
       └─ [Normal] → LLM + Profiling-Kontext → bisheriger Pfad

POST /confirm
  └─ ProposalService.confirm_proposal()
       ├─ mode="all"          → alle Steps ausführen (bestehend)
       ├─ confirmed_steps=[…] → nur selektierte Steps (neu)
       └─ mode="step_by_step" → Step 1 → StepByStepState zu DB schreiben

POST /rollback
  └─ SpecRepository.rollback_to(target_spec_id)
       → alte Spec kopieren → neue Version (parent=aktuelle) → change_summary="Rollback auf vX"
```

### Test-Struktur (neue Unit-Tests)

```
backend/tests/unit/
├── test_command_service.py        ← F1: alle Slash-Commands + unbekannter Command
├── test_profiling_service.py      ← F2: Profiling-Output-Struktur, Caching
├── test_proposal_service_step.py  ← F3: Selektive Steps + Step-by-Step
└── test_spec_diff.py              ← F4: Diff-Szenarien (add, remove, param-change)

backend/tests/integration/
└── test_rollback_endpoint.py      ← F4: Rollback-Endpunkt + Baum-Endpunkt
```

---

## Architektur-Validierung

### Kohärenz-Check ✅ 6/6

| # | Prüfpunkt | Ergebnis |
|---|-----------|----------|
| 1 | `CommandService` greift nicht auf LLM zu — keine versteckte LLM-Abhängigkeit | ✅ |
| 2 | Rollback-Logik nur in `SpecRepository` (DRY) — LLM-Aktion + Endpunkt rufen dieselbe Methode | ✅ |
| 3 | `@lru_cache` auf statischen Bike-CSV-Load: kein Invalidierungsproblem (read-only) | ✅ |
| 4 | `step_states`-Tabelle mit Foreign Key auf `sessions` — referenzielle Integrität gewahrt | ✅ |
| 5 | DataFrame-Ausschluss aus Persistenz: deterministisch rekonstruierbar aus `completed_steps` + Bike-CSV | ✅ |
| 6 | Help-Texte in YAML-Config — keine Hartcodierung, wartbar ohne Code-Änderung | ✅ |

### Anforderungsabdeckung ✅ 17/17 FRs

| Feature | FRs | Architektur-Element |
|---------|-----|---------------------|
| F1 Onboarding/Slash-Commands | FR-OB1–OB5 | `CommandService`, `help_texts.yaml`, `POST /sessions` + `welcome_message` |
| F2 Datensatz-Profilierung | FR-DO1–DO3 | `ProfilingService`, `@lru_cache`, LLM-Kontext-Injection in `prompts.py` |
| F3 Schrittweise Ausführung | FR-SE1–SE4 | `step_states`-Tabelle, `StepByStepState`, `ConfirmProposalRequest.mode` + `confirmed_steps` |
| F4 Pipeline-Versionsbaum | FR-VB1–VB5 | `spec_diff()`, `parent_spec_id`-Migration, `GET /spec/tree`, `POST /rollback` |

### Implementierungs-Bereitschaft ✅ 6/6

| Dimension | Status |
|-----------|--------|
| Alle Dateipfade benannt (neu + geändert) | ✅ |
| SQL-Schema-Migration vollständig definiert | ✅ |
| API-Contracts (Request/Response-Schemas) vollständig | ✅ |
| Naming-Konventionen dokumentiert | ✅ |
| Test-Struktur und Abdeckungs-Scope definiert | ✅ |
| Datenfluss-Diagramme für alle geänderten Pfade | ✅ |

### ⚠️ Kritische Implementierungs-Reihenfolge

**DB-Migration muss zuerst implementiert werden.** Alle anderen Features setzen `step_states`-Tabelle (F3) bzw. `parent_spec_id`-Spalte (F4) voraus.

### Empfohlene Story-Reihenfolge

| Story | Feature | Inhalt | Abhängigkeit |
|-------|---------|--------|--------------|
| Story 0 | — | DB-Migration: `step_states`-Tabelle + `spec_versions`-Erweiterung | Keine |
| Story 1 | F1 | `CommandService` + Welcome-Message + `help_texts.yaml` | Story 0 |
| Story 2 | F2 | `ProfilingService` + `@lru_cache` + LLM-Kontext | Story 0 |
| Story 3 | F4 | `spec_diff()` + Versionsbaum-API + Rollback-Endpunkt | Story 0 |
| Story 4 | F3 | Selektive Step-Bestätigung (`confirmed_steps`) | Story 0, Story 3 |
| Story 5 | F3 | Step-by-Step-Modus (`mode="step_by_step"`, `StepByStepState`) | Story 4 |