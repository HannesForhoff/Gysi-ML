# Copilot Instructions for gysi-ml

## Agent Initialization Protocol

### Vor jeder Aufgabe diese Schritte befolgen

1. **Scope identifizieren**: Betrifft die Aufgabe `backend/`, `frontend/` oder globale Dateien?
2. **Modul-Kontext laden**:
    - **Backend**: [backend/AGENTS.md](backend/AGENTS.md) lesen
    - **Frontend**: [frontend/AGENTS.md](frontend/AGENTS.md) lesen
3. **Alignment bestätigen**: Im eigenen Denkprozess benennen, welcher Kontext geladen wurde.

---

## Projekt-Überblick

**gysi-ml** (Codename "Gysi") ist ein konversationeller ML-Assistent als Belegarbeit. Nutzer beschreiben über natürliche Sprache was sie mit dem Bike-Datensatz machen wollen. Das LLM erzeugt ausschließlich strukturierte Aktionen (JSON). Alle Berechnungen erfolgen deterministisch im Python-Backend.

### Kernprinzipien

- **Backend kontrolliert den Ablauf** – das LLM wird angefragt, nicht umgekehrt
- **LLM führt keinen Code aus** und verändert kein Framework direkt
- **Änderungen erfolgen über eine versionierte Pipeline-Spec** (JSON/YAML)
- **Hybrid-Persistenz**: SQLite für State/History, Dateisystem für Artefakte
- **Fokus-Datensatz**: Bike Dataset (Scope bewusst begrenzt)

---

## Projektstruktur

```text
gysi-ml/
├── backend/                 # Python Backend (FastAPI + ML-Pipeline)
│   ├── src/gysi_ml/         #   Produktcode als Paket
│   ├── tests/               #   Unit + Integration Tests
│   ├── configs/             #   Pipeline-Specs (YAML)
│   ├── scripts/             #   Lokale Runner
│   ├── notebooks/           #   Explorative Analysen
│   └── AGENTS.md            #   Backend-spezifischer Kontext
├── frontend/                # Web-UI Chat-Interface (TBD)
│   └── AGENTS.md            #   Frontend-spezifischer Kontext
├── docs/                    # Projekt-Dokumentation
│   ├── architecture/        #   Architekturdiagramme, Repo-Struktur
│   ├── absprache/           #   Konsultationsnotizen, Anforderungen
│   └── systemkonzept.md     #   Systemkonzept und Rollenverteilung
├── data/raw/                # bike.csv (lokal, nicht committed)
├── artifacts/               # Generierte Plots/Reports (nicht committed)
├── .local/                  # SQLite DB, Logs (nicht committed)
├── .github/                 # BMAD: Agents, Prompts, Skills
├── _bmad/                   # BMAD Runtime
└── _bmad-output/            # BMAD Arbeitsprodukte (PRD, Stories)
```

## Agent Routing

| Aufgabe | Kontext laden |
| --- | --- |
| Backend (Python, API, Pipeline, ML) | [backend/AGENTS.md](backend/AGENTS.md) |
| Frontend (Web UI, Chat) | [frontend/AGENTS.md](frontend/AGENTS.md) |
| Full-Stack oder Integration | Beide laden |

## Shared Resources

- `data/` – Datensätze (vom Backend gelesen, vom Frontend referenziert)
- `artifacts/` – Generierte Outputs (vom Backend erzeugt, vom Frontend angezeigt)
- `.local/` – Laufzeit-State (SQLite DB, Logs)
- `docs/` – Projektdokumentation für alle Beteiligten

## Konventionen

### Environment

- Python 3.10 oder 3.11
- Backend-venv: `backend/.venv/`
- Secrets in `backend/.env` (niemals committed) – Vorlage: `backend/.env.example`

### Shell

- Windows: Git Bash bevorzugt
- Aktivierung: `source backend/.venv/Scripts/activate`

## BMAD Agents (VS Code Copilot)

BMAD unter `.github/agents/`, `.github/prompts/`, `.github/skills/`.

Slash-Commands: `/bmad-bmm-dev-story`, `/bmad-bmm-create-prd`, `/bmad-bmm-quick-dev` usw.

Agent-Modus: `💻 Developer Agent`, `🏗️ Architect`, `📋 Product Manager` usw.

### Documentation

- Sprint artifacts: `docs/backend/`, `docs/frontend/`
- Project context: `docs/project-context.md`

## Terminal Conventions

> ⚠️ **Follow these rules strictly when running terminal commands.**

### Shell Preference

| OS | Preferred Shell |
| ---- | ----------------- |
| Windows | **Git Bash** (not PowerShell, not cmd) |
| WSL | bash |
| macOS | zsh or bash |

---

### 🎯 CRITICAL: Current Directory Awareness

> **Terminals are reused across tasks!** The current working directory (cwd) may NOT be what you expect.

#### Mandatory Pre-Flight Check

**BEFORE running ANY command**, you MUST:

1. **Read the terminal's `Cwd:` from context** - This is shown in the environment info (e.g., `Cwd: C:/Develop/.../backend`)
2. **Compare with your target directory** - Where does your command need to run?
3. **Navigate if needed** - Use `cd` with absolute path if cwd differs from target

#### Decision Flow

```text
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Check terminal context for current Cwd              │
│         (Look at "Cwd:" in terminal info above)             │
├─────────────────────────────────────────────────────────────┤
│ Step 2: Does Cwd match where command needs to run?          │
│         ├─ YES → Run command directly                       │
│         └─ NO  → cd to correct directory first              │
└─────────────────────────────────────────────────────────────┘
```

#### Workspace Path References

The agent has access to the workspace root path from context. Use it to construct absolute paths:

```bash

# Reference: $WORKSPACE = workspace root path from context (e.g., shown in terminal Cwd)

#

# Key directories

#   $WORKSPACE/backend    - Python backend

#   $WORKSPACE/frontend   - Web frontend  

#   $WORKSPACE/data       - Shared data directory

```

---

### Before Running Commands

1. **ALWAYS check `Cwd:` in terminal context first** - Never assume the terminal is in any specific directory
2. **Derive the workspace root from `Cwd:`** - Extract the base path (everything before `/backend`, `/frontend`, etc.)
3. **Use absolute paths for `cd`** - Never use relative `cd ..` navigation; it's error-prone
4. **Combine `cd` with command when directory differs** - `cd <absolute-path> && command`
5. **Run directly if already in correct directory** - Don't cd unnecessarily

### Command Patterns

```bash

# ✅ PATTERN 1: Already in backend/ (Cwd shows .../backend)

uv run pytest

# ✅ PATTERN 2: NOT in backend/ - navigate first with absolute path

# (construct path from workspace root shown in terminal context)

cd <workspace-root>/backend && uv run pytest

# ✅ PATTERN 3: Reference files with absolute paths (no cd needed)

cat <workspace-root>/data/sessions/file.json

# ❌ BAD: Assuming current directory without checking

uv run pytest  # (when terminal might be in frontend/)

# ❌ BAD: Relative navigation (fragile, error-prone)

cd ../backend && uv run pytest

# ❌ BAD: Multiple relative hops

cd ../../data/sessions && cat file.json && cd -
```

### Terminal Reuse Examples

#### Scenario: Terminal shows `Cwd: /c/Users/dev/projects/ai4solutions/frontend` but you need to run backend tests

```bash

# ✅ CORRECT: Derive workspace root, navigate with absolute path

# Workspace root = /c/Users/dev/projects/ai4solutions (from Cwd minus /frontend)

cd /c/Users/dev/projects/ai4solutions/backend && uv run pytest

# ❌ WRONG: Running without checking/changing directory

uv run pytest  # Will fail - wrong directory!
```

### Scenario: Terminal shows `Cwd: .../backend` and you need to run backend tests

```bash

# ✅ CORRECT: Already there, run directly

uv run pytest

# ❌ WRONG: Unnecessary navigation

cd .../backend && uv run pytest  # Works but wasteful
```

---

### Common Pitfalls to Avoid

- **Don't assume terminal location** - ALWAYS check `Cwd:` in terminal context first
- **Don't use relative `cd`** - Use absolute paths: `cd /c/full/path`, not `cd ../sibling`
- **Don't use PowerShell syntax** (`$env:VAR`) - Use bash syntax (`export VAR=value`)
- **Don't create subshells** (`bash -c "..."`) unless explicitly needed
- **Don't run multiple terminal commands in parallel** - Wait for output before next command
- **Quote paths with spaces**: `"path/with spaces/file.txt"`

### Virtual Environment

- The backend venv should already be activated in bash terminals
- If not: `source .venv/Scripts/activate` (Windows Git Bash) or `source .venv/bin/activate` (Unix)
- Use `uv run` prefix to auto-use the correct environment: `uv run pytest`, `uv run python main.py`

## Markdown-Qualitätsstandards

Beim Erstellen oder Bearbeiten von Markdown-Dokumenten folgende Regeln beachten:

### Struktur

- Nur eine H1-Überschrift pro Dokument (erste Zeile)
- Überschriftenebenen nicht überspringen (H1→H2→H3, nicht H1→H3)

#### Leerzeilen (wichtigste Fehlerquelle!)

- Vor und nach Überschriften
- Vor und nach Listen
- Vor und nach Code-Blöcken

#### Code-Blöcke

- Immer mit Sprache kennzeichnen: `\`\`\`python`, `\`\`\`bash`, `\`\`\`json`
- Bei unformatiertem Text: `\`\`\`text`

#### Tabellen

- Einheitliches Spalten-Format mit Leerzeichen: `| Spalte | Spalte |`
- Nicht: `|Spalte|Spalte|` (fehlende Leerzeichen)

#### Links & URLs

- Nackte URLs in Winkelklammern: `<https://example.com>`
- Oder als beschreibenden Link: `[Beschreibung](https://example.com)`

#### Konsistenz

- Einheitliche Listen-Marker (`*`, `-`, oder `+` - nicht gemischt)
- Datei endet mit einzelnem Newline

#### Validierung

```bash
npx markdownlint-cli2 "**/*.md"
```
