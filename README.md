# gysi-ml

Konversationeller ML-Assistent als Belegarbeit. Nutzer beschreiben über natürliche Sprache, was sie mit dem Bike-Datensatz machen wollen. Das LLM erzeugt ausschließlich strukturierte Aktionen (JSON). Alle Berechnungen erfolgen deterministisch im Python-Backend.

## Kernprinzipien

- **Backend kontrolliert den Ablauf** — das LLM wird angefragt, nicht umgekehrt
- **LLM führt keinen Code aus** und verändert kein Framework direkt
- **Versionierte Pipeline-Spec** (JSON) als Quelle der Wahrheit
- **Proposal → Confirm** — Vorschläge müssen vom Nutzer bestätigt werden
- **Hybrid-Persistenz** — SQLite für State/History, Dateisystem für Artefakte
- **Fokus-Datensatz** — Bike Dataset (Scope bewusst begrenzt)

## Was kann Gysi?

### Datenvorverarbeitung

| Step | Beschreibung | Parameter |
| --- | --- | --- |
| `dedup` | Duplikate entfernen | — |
| `impute_missing` | Fehlende Werte füllen | `strategy`: median, mean, most_frequent |
| `outlier_handling` | Ausreißer cappen (Winsorization) | `method`: iqr/zscore, `zscore_threshold` |
| `encode_categorical` | Kategorische Features encodieren | `method`: label/onehot |
| `rare_category_bucketing` | Seltene Kategorien bündeln | `min_frequency` |
| `time_feature_encoding` | Datum → Wochentag + Monat | `column` (default: dteday) |
| `correlation_filter` | Hochkorrelierte Features entfernen | `threshold` (Pearson) |
| `split` | Train/Test-Split | `test_size`, `random_state` |

### Modelltraining

| Step | Beschreibung | Parameter |
| --- | --- | --- |
| `train_decision_tree` | Decision-Tree-Regressor (sklearn) | `max_depth`, `random_state` |
| `train_ebm` | Explainable Boosting Machine (InterpretML) | `random_state` |
| `catboost_feature_selection` | Feature Selection via CatBoost Importance | `top_n`, `random_state` |

### Ergebnisse & Erklärbarkeit

- **Metriken**: RMSE, MAE, R² pro Modell
- **Feature Importance**: Balkendiagramm als PNG (Decision Tree)
- **Globale Erklärung**: EBM-Erklärungsplot als PNG
- **Modellvergleich**: Metriken zweier Runs nebeneinander
- **Artefakte**: Klickbare Links im Chat, öffnen im Browser

### Interaktion

- Chat in natürlicher Sprache (Deutsch)
- LLM schlägt Pipeline-Schritte vor (Proposal-Card)
- Nutzer bestätigt → Backend führt aus → Ergebnis im Chat
- Pipeline-Spec ist versioniert — Undo/Rollback möglich
- Status-Panel zeigt jederzeit: Spec-Version, Steps, letzter Run, Artefakte

## Voraussetzungen

- **Python** 3.10 oder 3.11
- **Node.js** 18+ und npm
- **Git**
- **Datensatz**: `data/raw/bikes.csv` (lokal ablegen, nicht im Repo)
- **LLM-Zugang**: OpenAI-kompatibler Endpunkt (API-Key erforderlich)

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/HannesForhoff/Gysi-ML.git
cd Gysi-ML
```

### 2. Backend einrichten

```bash
cd backend

# Virtuelle Umgebung erstellen und aktivieren
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
# source .venv/bin/activate     # macOS / Linux

# Abhängigkeiten installieren
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Alternativ mit uv:
# uv sync --all-extras
```

### 3. Backend konfigurieren

```bash
# .env aus Vorlage erstellen
cp .env.example .env
```

Folgende Werte in `backend/.env` eintragen:

| Variable | Beschreibung | Pflicht |
| --- | --- | --- |
| `OPENAI_API_KEY` | API-Key für LLM-Endpunkt | Ja |
| `LLM_MODEL` | Modellname (z.B. `gpt-4-turbo`) | Ja |
| `OPENAI_BASE_URL` | Custom Base URL (z.B. für lokales LLM) | Nein |
| `DB_PATH` | SQLite-Pfad (default: `../.local/gysi_ml.db`) | Nein |
| `HOST` | Bind-Adresse (default: `0.0.0.0`) | Nein |
| `PORT` | Port (default: `8000`) | Nein |

### 4. Datensatz ablegen

```bash
# Vom Projektroot aus:
mkdir -p data/raw
# bikes.csv in data/raw/ ablegen
```

### 5. Frontend einrichten

```bash
cd frontend
npm install
```

## Starten

### Backend starten

```bash
cd backend
source .venv/Scripts/activate   # Windows (Git Bash)
python -m gysi_ml.main
```

Das Backend läuft auf `http://localhost:8000`. Die SQLite-Datenbank und alle Tabellen werden beim ersten Start automatisch erstellt.

**API-Dokumentation**: `http://localhost:8000/docs` (Swagger UI)

### Frontend starten

```bash
cd frontend
npm run dev
```

Das Frontend läuft auf `http://localhost:5173`.

**Standardmäßig startet das Frontend im Mock-Modus** (ohne Backend-Verbindung). Um das echte Backend zu nutzen:

```bash
# Frontend mit Backend-Verbindung starten:
VITE_GYSI_USE_MOCK=false npm run dev
```

Oder eine `.env`-Datei in `frontend/` erstellen:

```text
VITE_GYSI_USE_MOCK=false
VITE_GYSI_BACKEND_BASE_URL=http://localhost:8000
```

### Beide zusammen (Kurzfassung)

Terminal 1 (Backend):

```bash
cd backend && source .venv/Scripts/activate && python -m gysi_ml.main
```

Terminal 2 (Frontend):

```bash
cd frontend && VITE_GYSI_USE_MOCK=false npm run dev
```

Browser öffnen: `http://localhost:5173`

## Tests

### Backend-Tests

```bash
cd backend
source .venv/Scripts/activate
pytest                          # Unit-Tests (schnell)
pytest -m slow                  # + Tests mit echtem Datensatz
pytest --cov=gysi_ml            # mit Coverage
```

### Frontend-Tests

```bash
cd frontend
npm test                        # vitest run
npx vitest --watch              # Watch-Modus
```

## Projektstruktur

```text
gysi-ml/
├── backend/                     # Python Backend (FastAPI + ML-Pipeline)
│   ├── src/gysi_ml/
│   │   ├── api/                 #   FastAPI Routes & Schemas
│   │   ├── core/                #   LLM-Orchestrierung, Kontext, Aktionen
│   │   ├── executor/            #   Deterministischer Pipeline-Executor
│   │   ├── steps/               #   Preprocessing + Modeling Steps
│   │   │   ├── preprocessing/   #     dedup, impute, encode, split, ...
│   │   │   └── modeling/        #     decision_tree, ebm, catboost
│   │   ├── persistence/         #   SQLite + Dateisystem
│   │   ├── config.py            #   Settings (aus .env)
│   │   └── main.py              #   Einstiegspunkt (uvicorn)
│   ├── tests/                   #   Unit + Integration Tests
│   ├── configs/                 #   Pipeline-Specs (YAML)
│   └── .env.example             #   Vorlage für Secrets
├── frontend/                    # React + TypeScript (Vite)
│   └── src/
│       ├── api/                 #   API-Client (runApi, chatApi)
│       ├── components/          #   Chat, StatusPanel, ProposalCard, ResultCard
│       ├── state/               #   Reducer (State Machine)
│       ├── hooks/               #   useRunPolling, useHealthCheck
│       ├── utils/               #   URL-Sanitierung, Helpers
│       └── fixtures/            #   Mock-Daten für Entwicklung
├── data/raw/                    # bikes.csv (lokal, nicht committed)
├── artifacts/                   # Generierte Plots/Reports (nicht committed)
├── .local/                      # SQLite DB, Logs (nicht committed)
└── docs/                        # Systemkonzept, Architektur, Notizen
```

## API-Endpunkte (Übersicht)

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| GET | `/v1/health` | Health-Check |
| GET | `/v1/capabilities` | Verfügbare Pipeline-Steps |
| POST | `/v1/sessions` | Neue Session erstellen |
| GET | `/v1/sessions/{id}` | Session abrufen |
| POST | `/v1/sessions/{id}/messages` | Nachricht senden → Proposal/Result/Error |
| POST | `/v1/sessions/{id}/confirm` | Proposal bestätigen → Run starten |
| GET | `/v1/sessions/{id}/runs/{rid}` | Run-Status abfragen (Polling) |
| GET | `/v1/sessions/{id}/spec` | Aktuelle Pipeline-Spec |
| GET | `/v1/sessions/{id}/spec/{version}` | Spec einer bestimmten Version |
| GET | `/v1/artifacts/{aid}` | Artefakt herunterladen (PNG/JSON) |

## Technologie-Stack

**Backend**: Python 3.10+, FastAPI, SQLite, pandas, scikit-learn, InterpretML, CatBoost, matplotlib

**Frontend**: React 19, TypeScript, Vite

**LLM**: OpenAI-kompatible API (konfigurierbar)

## Dokumentation

- Systemkonzept: `docs/systemkonzept.md`
- Architektur: `docs/architecture/`
- Anforderungen: `docs/absprache/`
