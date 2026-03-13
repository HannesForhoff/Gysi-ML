# gysi-ml (Belegarbeit)

Jarvis-ähnlicher Prototyp zur Erstellung, Anpassung und Erklärung von ML-Pipelines über natürliche Sprache.
Das LLM erzeugt ausschließlich strukturierte Aktionen (JSON). Alle Berechnungen erfolgen deterministisch im Python-Backend.

## Kernprinzipien

- Backend kontrolliert den Ablauf (LLM wird angefragt, nicht umgekehrt)
- LLM führt keinen Code aus und verändert kein Framework
- Änderungen erfolgen über eine versionierte Pipeline-Spezifikation (Spec)
- Hybrid-Persistenz: SQLite für State/History, Dateisystem für Artefakte
- Fokus-Datensatz: Bike Dataset (Scope bewusst begrenzt)

## Projektstruktur

- `backend/` – Python Backend (FastAPI + ML-Pipeline)
- `frontend/` – Web-UI Chat-Interface
- `docs/` – Architektur, Systemkonzept, Notizen
- `data/raw/` – Datensatz (lokal)
- `artifacts/` – Generierte Outputs (lokal)
- `.local/` – SQLite DB, Logs (lokal)

## Dokumentation

- Systemkonzept: `docs/systemkonzept.md`
- Architektur: `docs/architecture/`
- Anforderungen: `docs/absprache/`

## Setup

Voraussetzungen: Python 3.10 oder 3.11, Git

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Datensatz: `data/raw/bike.csv` lokal ablegen.
