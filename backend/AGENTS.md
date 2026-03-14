# Backend – Copilot Instructions

## Überblick

Python-Backend für den gysi-ml Assistenten. FastAPI-basiert, deterministisch, modular.

## Architektur-Schichten

| Schicht | Ordner | Verantwortung |
| --- | --- | --- |
| API | `src/gysi_ml/api/` | FastAPI – nimmt Requests an, gibt Responses zurück |
| Orchestrierung | `src/gysi_ml/core/` | Kontext aufbauen, LLM anfragen, Aktionen validieren, Spec verwalten |
| Ausführung | `src/gysi_ml/executor/` | Steps deterministisch nach Spec ausführen |
| Fachlogik | `src/gysi_ml/steps/` | Preprocessing, Modeling, Explainability als modulare Bausteine |
| Persistenz | `src/gysi_ml/persistence/` | SQLite für State/History, FS für Artefakte |

## Pipeline-Scope

### Preprocessing (Phase 1)

- Feature Selection (manuell, Filter-Methoden, Wrapper/Embedded)
- Ausreißerentfernung (Winsorization, Boxplot-Visualisierung)
- Missing Values (Variable Dropping, List-wise Deletion, Mean/Median/Hot-Deck-Imputation, Interpolation)
- One-Hot-Encoding vs. Gruppen-Features für kategoriale Features
- Time Feature Encoding (Datum → Tag/Monat/Jahr als separate Features)
- Duplikat-Erkennung und -Entfernung
- Data Splitting (Train-Test-Validation; kein Data Leakage)

### Modeling (Phase 2)

- Decision Trees, EBM (Explainable Boosting Machine)
- Metriken: Predictive Performance, Training vs. Test (Overfitting)
- Feature Importance (Plot + Liste), globale und lokale Erklärungen

## Konventionen

### Environment

- Python 3.10 oder 3.11
- Virtuelle Umgebung: `.venv/` in `backend/`
- Abhängigkeiten: `requirements.txt` (Runtime), `requirements-dev.txt` (Dev/Test)
- Secrets in `.env` (niemals committed) – Vorlage: `.env.example`

### Shell

- Windows: Git Bash bevorzugt
- Aktivierung: `source .venv/Scripts/activate` (aus `backend/`)

### Tests ausführen

```bash
cd backend
source .venv/Scripts/activate
pytest tests/
```

### Datensatz

- `../data/raw/bike.csv` – relativ vom Backend aus

### Generierte Outputs

- `../artifacts/` – Plots, Reports, Exports
- `../.local/` – SQLite DB, Logs, Run-State
