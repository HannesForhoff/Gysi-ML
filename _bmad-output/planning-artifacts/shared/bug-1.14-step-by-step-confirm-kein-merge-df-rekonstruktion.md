# Bug 1.14 — Propose→Confirm Step-by-Step: Spec-Merge fehlt, df-Rekonstruktion aus Proposal-Steps only

**Gefunden**: 2026-04-25
**Status**: ✅ Gefixt (2026-04-30)
**Priorität**: 🔴 Kritisch (Pipeline-Integrität verletzt)
**Kategorie**: Backend (`proposal_service.py`)
**Session**: Party-Mode-Analyse 25.04.2026 — strukturelles Loch identifiziert

---

## Kontext

Dieser Bug ist die Step-by-Step-Variante von **Bug 1.13A**. Beide Bugs teilen dieselbe Wurzel: Der Propose→Confirm-Pfad merged die Proposal-Spec nie mit der akkumulierten Session-Spec. Bug 1.13A betrifft den `mode="all"`-Zweig; Bug 1.14 betrifft den `mode="step_by_step"`-Zweig und `_execute_single_step()`.

---

## Beobachtetes (potentielles) Fehlverhalten

**Szenario:**
1. Nutzer führt Imputation, Encoding, Split aus → Session-Spec hat 3 Steps
2. LLM schlägt `catboost_feature_selection` vor (action="propose")
3. Nutzer wählt Step-by-Step-Modus
4. `_execute_single_step()` führt `catboost_feature_selection` aus

**Ergebnis:** `catboost_feature_selection` läuft auf dem **rohen Original-Datensatz** — ohne Split, ohne Imputation, ohne Encoding.

**Erwartetes Ergebnis:** Der Step wird auf dem korrekt vorbereiteten Datensatz ausgeführt, der den vollständigen akkumulierten Session-Zustand widerspiegelt.

---

## Technische Ursachenanalyse

### Bug-Kern: `_execute_single_step()` rekonstruiert df ausschließlich aus Proposal-Steps

**Datei:** `backend/src/gysi_ml/services/proposal_service.py`

```python
def _execute_single_step(
    current_step: dict,
    completed_steps: list[dict],  # ← nur bereits gelaufene PROPOSAL-Steps
    data_path: str,
    artifacts_path: str,
) -> dict:
    df = load_bikes_dataset(data_path)   # ← immer frisch von Disk
    context = PipelineContext(df_full=df)

    all_steps = completed_steps + [current_step]
    # ^^^ completed_steps enthält nur die Steps, die im AKTUELLEN PROPOSAL
    # bereits ausgeführt wurden — NICHT die akkumulierten Session-Steps!
    for step_spec in all_steps:
        ...
```

**Fehlender Schritt:** Die akkumulierte Session-Spec (alle bisherigen Runs dieser Session) wird **nie in die df-Rekonstruktion einbezogen**.

### Zweite Lücke: `_run_step_by_step()` ignoriert Session-Kontext beim ersten Aufruf

```python
# _run_step_by_step() — erster Aufruf (kein active_state):
steps = spec.get("steps", [])          # ← spec = raw Proposal-Spec
active_steps = [s for s in steps if s.get("enabled", True)]
remaining = active_steps
completed = []
```

Das `spec`, das hier übergeben wird, ist das raw Proposal-Spec — erschaffen ohne `_merge_specs()`. Es enthält nur die neuen vorgeschlagenen Steps.

### Dritte Lücke: Selber Fehler wie Bug 1.13A — Proposal wird nie gemergt gespeichert

In `message_service.py` (action="propose"):

```python
proposal = proposal_repository.create_proposal(
    spec_json=json.dumps(clean_spec),  # ← raw LLM-Steps, KEIN _merge_specs()!
    ...
)
```

Das Proposal enthält von Anfang an nur die neuen Steps. Der Merge wurde für den Confirm-Pfad nie implementiert.

---

## Auswirkung

| Szenario | Symptom |
|---|---|
| Step-by-Step nach Split+Preprocessing | Modellierungs-Step sieht unsplitteten, unbearbeiteten df |
| Step-by-Step `correlation_filter` nach `impute_missing` | Filter läuft auf Daten mit NaNs → falsches Ergebnis |
| Step-by-Step `train_*` nach Pipeline | Data Leakage: kein Split, kein Test-Set |
| Step 2 in multi-step Proposal | Nur Step 1 aus Proposal wird als "completed" mitgezogen — Session-Steps fehlen |

---

## Root Cause (gemeinsam mit Bug 1.13A)

Der Propose→Confirm-Pfad wurde in **Story 3.3** implementiert, bevor `_merge_specs()` in einem späteren Sprint hinzukam. Der Message→Execute-Pfad wurde nachträglich um den Merge ergänzt; der Confirm-Pfad (beide Modi) wurde nie nachgezogen.

---

## Vorgeschlagener Fix

### Fix A — Merge beim Speichern des Proposals (empfohlen, beseitigt beide Bugs 1.13A+1.14 gleichzeitig)

In `message_service.py`, action="propose":

```python
# VOR
proposal = proposal_repository.create_proposal(
    spec_json=json.dumps(clean_spec),
    ...
)

# NACH
try:
    merged_for_proposal = _merge_specs(current_spec, clean_spec)
except Exception as exc:
    log.exception("Spec-Merge für Proposal fehlgeschlagen")
    return {"type": "error", "message": f"Fehler beim Zusammenführen der Pipeline-Spec: {exc}"}

proposal = proposal_repository.create_proposal(
    spec_json=json.dumps(merged_for_proposal),
    ...
)
```

**Vorteil:** Proposal enthält von Anfang an die vollständige Spec. `confirm_proposal()` und `_execute_single_step()` brauchen keine Änderung — sie arbeiten bereits korrekt mit der gespeicherten Spec.

**Nachteil:** Die UI zeigt dem Nutzer dann alle Steps im Proposal (auch die bereits bekannten). Das muss in `message_service.py` beim Proposal-Response berücksichtigt werden: `"steps": raw_steps` (nur neue Steps zur Anzeige) vs. gespeicherte Merged-Spec.

### Fix B — Merge im Confirm-Pfad (minimaler Eingriff, parallelisierbar zu Bug 1.13A Fix A)

Wenn Bug 1.13A mit Fix B (Merge in `confirm_proposal()`) behoben wird, muss dort auch der Step-by-Step-Zweig angepasst werden:

```python
# proposal_service.py — confirm_proposal(), VOR dem _run_step_by_step()-Aufruf:
from gysi_ml.services.message_service import _merge_specs
from gysi_ml.persistence import spec_repository

current_spec_entry = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
current_spec = current_spec_entry["spec"] if current_spec_entry else None

spec = json.loads(proposal["spec_json"])
merged_spec = _merge_specs(current_spec, spec)

# Dann merged_spec statt spec an _run_step_by_step() übergeben
```

Zusätzlich muss `_execute_single_step()` die Session-Steps für die df-Rekonstruktion als Basis erhalten:

```python
def _execute_single_step(
    current_step: dict,
    completed_steps: list[dict],
    session_steps: list[dict],   # ← NEU: alle bisherigen Session-Steps
    data_path: str,
    artifacts_path: str,
) -> dict:
    df = load_bikes_dataset(data_path)
    context = PipelineContext(df_full=df)

    # Erst Session-Zustand herstellen, dann Proposal-Steps
    all_steps = session_steps + completed_steps + [current_step]
    for step_spec in all_steps:
        ...
```

---

## Empfehlung

**Fix A** bevorzugen:

- Beseitigt Bug 1.13A und 1.14 an derselben Stelle
- `_execute_single_step()` und `confirm_proposal()` bleiben unberührt
- Einziger Aufwand: UI-Step-Liste muss vom gespeicherten (merged) Spec entkoppelt bleiben → `raw_steps` weiterhin für die Anzeige verwenden

**Dateien die Amelia ändern muss:**

- `backend/src/gysi_ml/services/message_service.py` — `_merge_specs()` vor `create_proposal()` aufrufen
- Kein `proposal_service.py`-Eingriff nötig (wenn Fix A)

---

## Verwandte Bugs

- **Bug 1.13** — `confirm_proposal()` mode="all" merged nicht + Response fehlt spec/version/step_results + InfoPanel Index-Matching
- **Bug 1.14** — dieser Bug (step_by_step-Zweig)
- **Bug 1.15** — LLM-Rollback via Chat: System-Prompt hat keine spec_ids
