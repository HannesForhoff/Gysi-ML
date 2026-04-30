# Bug 1.13 — Korrelations-Filter: Drei gekoppelte Fehler (Spec-Merge, Confirm-Response, InfoPanel-Rendering)

**Gefunden**: 2026-04-25
**Status**: ✅ Gefixt (2026-04-30)
**Priorität**: 🔴 Kritisch (Pipeline-Integrität verletzt, irreführende Anzeige)
**Kategorie**: Backend (`proposal_service.py`) + Frontend (`InfoPanel.tsx`)
**Session**: Usability-Test 25.04.2026 (Hannes + Party-Mode-Analyse)

---

## Beobachtetes Fehlverhalten

**Test-Session Ablauf:**
1. "Import Missing Values von Weathersit mit dem Modus" → ✓ Imputation (4170 Werte ersetzt)
2. "Führe ein Time Feature Encoding für dteday durch" → ✓ weekday + month extrahiert
3. "Führe einen Korrelationsfilter auf alle Features durch" → Propose (nicht bestätigt)
4. "Ja mit 0.9 auf alle Spalten" → zweite Propose → Bestätigen → **Run abgeschlossen**

**Beobachtetes Ergebnis in der Seitenleiste:**

```
Aktive Pipeline  v2
──────────────────────────────────────
1  Fehlende Werte auffüllen   [aktiv]
   Schwellwert: |r| ≥ 0.9              ← FALSCH: zeigt Korrelationsfilter-Daten!
   Paare: temp ↔ atemp r=0.99 → temp entfernt
   Entfernt: temp
   Behalten: cnt, holiday, hr, hum, ...

2  Zeitmerkmale ableiten      [aktiv]
   (kein Detail)

──────────────────────────────────────
Letzter Run  ● Erfolg
✓ Korrelationsfilter
   Schwellwert: |r| ≥ 0.9
   Paare: temp ↔ atemp ...
```

**Erwartetes Ergebnis:**

```
Aktive Pipeline  v3
──────────────────────────────────────
1  Fehlende Werte auffüllen   [aktiv]
   Ersetzt: weathersit: 4170  ← Imputation-Daten

2  Zeitmerkmale ableiten      [aktiv]
   Abgeleitet: weekday, month

3  Korrelationsfilter          [aktiv]
   Schwellwert: |r| ≥ 0.9
   Paare: temp ↔ atemp → temp entfernt

──────────────────────────────────────
Letzter Run  ● Erfolg
✓ Fehlende Werte auffüllen (...)
✓ Zeitmerkmale ableiten (...)
✓ Korrelationsfilter (...)
```

---

## Technische Ursachenanalyse — 3 eigenständige Teilprobleme

---

### Bug A — Confirm-Pfad merged die Spec NICHT (Schweregrad: 🔴 Kritisch)

**Datei:** `backend/src/gysi_ml/services/proposal_service.py`

**Ursache:**

`confirm_proposal()` nimmt den gespeicherten Proposal-Spec, der nur die **neu vom LLM vorgeschlagenen Steps** enthält (z.B. `[correlation_filter]`), und führt ihn **direkt** ohne Merge mit der akkumulierten Session-Spec aus:

```python
# proposal_service.py — confirm_proposal()
spec = json.loads(proposal["spec_json"])   # ← nur [correlation_filter]
executor = PipelineExecutor(...)
result = executor.execute(spec=spec, session_id=session_id, db_path=db_path)
# ← kein _merge_specs(current_spec, spec) !
```

Der **message_service.py execute-Pfad** macht das korrekt:

```python
# message_service.py — action == "execute"
current_spec_entry = spec_repository.get_latest_spec(session_id=session_id, ...)
current_spec = current_spec_entry["spec"] if current_spec_entry else None
merged_spec = _merge_specs(current_spec, spec)   # ← akkumuliert vorherige Steps
result = executor.execute(spec=merged_spec, ...)
```

**Konsequenzen:**

1. **Nur der vorgeschlagene Step läuft** — Imputation und Time-Feature-Encoding werden NICHT neu ausgeführt
2. **Der Korrelationsfilter rechnet auf ROHDATEN** (mit fehlenden Werten, ohne abgeleitete Features) — fachlich falsche Ergebnisse
3. **Neue Spec-Version v3 = `[correlation_filter]`** wird in der DB angelegt — vorherige Steps (`impute_missing`, `time_feature_encoding`) **verschwinden aus dem Spec-Baum** (Datenverlust!)
4. **Pipeline-Akkumulation ist gebrochen**: nach jedem Confirm verliert der Nutzer alle bisherigen Steps

**Fix A:**

In `confirm_proposal()` die aktuelle Spec laden und mergen:

```python
# proposal_service.py — confirm_proposal(), nach "spec = json.loads(...)"
from gysi_ml.persistence import spec_repository
from gysi_ml.services.message_service import _merge_specs

current_spec_entry = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
current_spec = current_spec_entry["spec"] if current_spec_entry else None
spec = _merge_specs(current_spec, spec)   # ← NEU: mit akkumulierter Session-Spec zusammenführen

result = executor.execute(spec=spec, session_id=session_id, db_path=db_path)
```

---

### Bug B — Confirm-Response enthält kein `spec`/`version` — Frontend-State bleibt veraltet (Schweregrad: 🔴 Kritisch)

**Datei:** `backend/src/gysi_ml/services/proposal_service.py`

**Ist-Zustand:**

```python
# proposal_service.py — confirm_proposal() Return-Statement
return {
    "type": "result",
    "run_id": result["run_id"],
    "explanation": "Proposal bestätigt und ausgeführt.",
    # ← FEHLT: "spec", "version", "step_results", "artifacts"
}
```

**Vergleich mit message_service.py (korrekt):**

```python
# message_service.py — execute-Pfad Return-Statement
return {
    "type": "result",
    "run_id": result["run_id"],
    "explanation": explanation,
    "post_run_explanation": post_run_explanation,
    "step_results": step_results,        # ← alle Step-Ergebnisse
    "metrics": run_result.get("metrics") or None,
    "artifacts": run_result.get("artifacts", []),
    "spec": spec_for_response,           # ← aktueller Spec (für specSummary-Update)
    "version": version_for_response,     # ← neue Versionsnummer
}
```

**Frontend-Konsequenz (realTransport.ts):**

```ts
// realTransport.ts — toAssistantResponse()
let spec_summary: SpecSummary | undefined
if (isRecord(payload.spec) && payload.version) {
    // ← NICHT betreten, da "spec" und "version" fehlen im Confirm-Response!
    spec_summary = { spec_version_id: ..., steps: [...] }
}
// spec_summary = undefined → wird nicht gebaut
```

**chatReducer.ts:**

```ts
const specSummary =
    response.type === 'result'
        ? response.spec_summary ?? state.specSummary  // ← undefined ?? alter Zustand
        : state.specSummary
// → specSummary bleibt auf v2 ([impute_missing, time_feature_encoding]) — veraltet
```

**Ergebnis:** Der Nutzer sieht nach dem Confirm weiterhin die alte Spec v2. Der Korrelationsfilter erscheint NICHT als Step 3 in der aktiven Pipeline.

**Fix B:**

`confirm_proposal()` muss denselben Return-Aufbau wie der `execute`-Pfad in `message_service.py` liefern:

```python
# proposal_service.py — confirm_proposal(), erweitertes Return-Statement
run_result = result.get("result", {})
return {
    "type": "result",
    "run_id": result["run_id"],
    "explanation": "Proposal bestätigt und ausgeführt.",
    "step_results": run_result.get("step_results", []),
    "metrics": run_result.get("metrics") or None,
    "artifacts": run_result.get("artifacts", []),
    "spec": spec,                         # ← merged spec (nach Fix A)
    "version": result.get("spec_version"),
}
```

---

### Bug C — InfoPanel: Index-basiertes Step-Matching (Schweregrad: 🟠 Hoch)

**Datei:** `frontend/src/components/InfoPanel.tsx`

**Ursache:**

Die "Aktive Pipeline" in `InfoPanel` mappt `step_results` auf Spec-Steps **per Index** — dabei wird angenommen, dass beide Listen exakt gleich lang und in gleicher Reihenfolge sind:

```tsx
// InfoPanel.tsx — Zeile 28
// step_results are in the same order as spec steps — match by index
const stepResults: (StepResult | undefined)[] = lastRun?.step_results ?? []

// ...bei der Render-Logik:
const sr = stepResults[idx]   // ← idx-basiertes Matching
```

**Warum das bricht:**

Wenn `specSummary.steps` = 2 Items (`[impute, time_features]`, veraltet) und `lastRun.step_results` = 1 Item (`[correlation_filter_result]`):

| `idx` | Spec-Step | `stepResults[idx]` | Angezeigt als |
|---|---|---|---|
| 0 | `impute_missing` | `correlation_filter_result` | **Korrelationsfilter-Daten unter "Fehlende Werte auffüllen"** |
| 1 | `time_feature_encoding` | `undefined` | kein Detail |

**Fix C:**

Statt Index-Matching per `step_type` suchen:

```tsx
// InfoPanel.tsx — Fix
{specSummary.steps.map((step, idx) => {
    // NEU: per step_type suchen, nicht per Index
    const sr = stepResults.find(r => r.step_type === step.step_type)
    return (
        <li key={`${step.step_type}-${idx}`} className="infoPipelineStep">
            ...
            {sr && step.enabled && (
                <div className="infoPipelineStepDetail">
                    <StepDetail sr={sr} />
                </div>
            )}
        </li>
    )
})}
```

**Hinweis**: `step_type` ist bei Steps wie `impute_missing` (mehrfach möglich mit unterschiedlichen Strategien) nicht eindeutig. Für den aktuellen Stand reicht `find()`. Falls mehrere Instanzen desselben Step-Typs vorkommen: `filter()` + Index-Offset-Logik erforderlich.

---

## Abhängigkeiten zwischen den Bugs

```
Bug A (kein Merge)
    ↓ erzeugt falsche step_results (nur 1 statt 3)
    ↓ erzeugt falsche neue Spec-Version (nur [correlation_filter])
Bug B (kein spec/version in Response)
    ↓ Frontend-specSummary bleibt veraltet (v2)
Bug C (Index-Matching)
    ↓ veraltet specSummary (v2, 2 Steps) + 1 step_result = falsche Anzeige
```

**Fix-Reihenfolge:** A zuerst (Kernfehler), dann B (Response-Vollständigkeit), dann C (Frontend).

---

## Auswirkung auf ML-Qualität

**Kritisch:** Durch Bug A rechnet der Korrelationsfilter auf Rohdaten ohne Vorverarbeitung:
- `temp` wurde als hoch korreliert mit `atemp` erkannt (Pearson r=0.99) — das stimmt auch auf Rohdaten
- Bei anderen Anwendungsfällen (z.B. nach One-Hot-Encoding, nach Skalierung) wären die Korrelationswerte **systematisch falsch**
- Da vorherige Steps nicht mit ausgeführt werden, führt der Pipeline-Aufruf zu einem **anderen Ergebnis** als erwartet

---

## Notwendige Tests

### Backend — proposal_service.py (Fix A + B)

```python
def test_confirm_merges_with_current_spec():
    """Confirm führt den merged Spec aus (vorherige Steps + neuer proposed Step)."""
    # Session mit v1 = [impute_missing]
    # Proposal = [correlation_filter]
    # Nach Confirm: executor.execute gerufen mit Spec [impute_missing, correlation_filter]

def test_confirm_response_includes_spec_and_version():
    """Confirm-Response enthält 'spec', 'version', 'step_results', 'artifacts'."""
    # Confirm response muss alle Felder wie message_service execute-Pfad liefern

def test_confirm_step_results_contain_all_steps():
    """Confirm-Response.step_results enthält Ergebnisse aller ausgeführten Steps."""
    # [impute_result, correlation_filter_result] — nicht nur [correlation_filter_result]
```

### Frontend — InfoPanel.tsx (Fix C)

```tsx
it('shows correct step detail when step_results count differs from spec steps', () => {
    // specSummary: 2 steps (impute, time_features)
    // lastRun.step_results: 1 item (correlation_filter)
    // → impute step shows NO detail (not correlation filter data)
})

it('matches step detail by step_type, not by index', () => {
    // specSummary: [impute, time_features, correlation_filter]
    // step_results: in different order
    // → each step shows its own correct detail
})
```

---

## Offene Fragen

1. **`_merge_specs` Importpfad**: `_merge_specs()` ist derzeit in `message_service.py` definiert. Für die Nutzung in `proposal_service.py` entweder die Funktion in ein gemeinsames Modul auslagern oder den Import direkt aus `message_service` machen.

2. **Polling-Pfad**: Der Confirm startet einen Run, dann pollt das Frontend via `GET /runs/{run_id}`. Die `spec`/`version`-Felder könnten alternativ auch im Poll-Response geliefert werden statt im Confirm-Response — das wäre aber ein größerer Umbauid.

3. **Bestehender `StepResult`-Import fehlt im `ChatAction`-Typ** (`chatReducer.ts` importiert `StepResult` nicht): prüfen ob der Type-Import korrekt ist (betrifft `RUN_POLL_SUCCEEDED`-Action).
