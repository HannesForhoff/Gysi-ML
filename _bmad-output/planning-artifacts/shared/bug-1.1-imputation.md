# Bug 1.1 — Imputation: Mehrere zusammenhängende Fehler

**Gefunden**: 2026-04-04
**Status**: Dokumentiert, noch nicht gefixt
**Priorität**: 🔴 Kritisch (Kernfunktion liefert falsche Resultate)
**Bereich**: Backend (Steps, Executor, LLM-Prompt) + Frontend (StatusPanel)

---

## Kontext des Auftretens

User-Anfrage im Chat:
> "Imputiere fehlende Werte in der Spalte windspeed mit dem Median"

Beobachtetes Verhalten:
- windspeed wurde NICHT imputiert
- Stattdessen wurden ALLE 10 numerischen Spalten imputiert (season, yr, mnth, hr, holiday, weathersit, temp, atemp, hum, cnt)
- Die angezeigten Ersetzungsmengen sind doppelt so groß wie erwartet (z.B. weathersit: 8340 statt 4170)
- Im StatusPanel ("Ausgeführte Steps") erscheint `imputed_values_per_column: [object Object]` statt der eigentlichen Werte

---

## Sub-Bug 1A — Kein `columns`-Parameter: Imputation ignoriert Zielspalte

### Schweregrad

🔴 Kritisch — Kernanforderung "Imputiere Spalte X" wird nie korrekt umgesetzt

### Betroffene Datei

`backend/src/gysi_ml/steps/preprocessing/imputation.py`

### Exakte Ursache

`param_schema` definiert ausschließlich `strategy`, aber KEINEN `columns`-Parameter:

```python
# imputation.py, Zeilen 10–16
param_schema = {
    "strategy": {
        "type": "string",
        "enum": ["median", "mean", "most_frequent"],
        "default": "median",
    }
}
```

Das `get_capabilities()`-System in `core/capabilities.py` (Zeile 13) liest genau dieses `param_schema` aus und übermittelt es als JSON an das LLM im System-Prompt. Das LLM kann deshalb strukturell gar keinen `columns`-Parameter erzeugen — er ist schlicht nicht im Schema.

`fit()` iteriert daher immer hart über ALLE numerischen Spalten:

```python
# imputation.py, Zeile 24–31
def fit(self, df_train: pd.DataFrame) -> None:
    numeric_cols = df_train.select_dtypes(include="number").columns
    for col in numeric_cols:  # ← nie gefiltert, immer alle 10 Spalten
        if self.strategy == "median":
            self._fill_values[col] = df_train[col].median()
        elif self.strategy == "mean":
            self._fill_values[col] = df_train[col].mean()
        elif self.strategy == "most_frequent":
            self._fill_values[col] = df_train[col].value_counts().idxmax()
```

### Auswirkung

User sagt "Imputiere windspeed" → LLM erzeugt `{"type": "impute_missing", "params": {"strategy": "median"}}` — es gibt kein `columns`-Feld — alle numerischen Spalten werden imputiert.

### Fix-Optionen

**Option A (empfohlen)**: `columns`-Parameter optional hinzufügen, Fallback = alle numerischen Spalten

```python
param_schema = {
    "strategy": {"type": "string", "enum": ["median", "mean", "most_frequent"], "default": "median"},
    "columns":  {"type": "array", "items": {"type": "string"}, "description": "Spalten die imputiert werden sollen. Leer = alle numerischen Spalten."}
}
```

In `fit()`:
```python
cols_param = self.params.get("columns", [])
numeric_cols = df_train.select_dtypes(include="number").columns
target_cols = [c for c in cols_param if c in numeric_cols] if cols_param else list(numeric_cols)
```

**Option B**: In `fit()` `columns` aus `self.params` lesen ohne `param_schema`-Änderung (Parameter wird dann nicht an LLM kommuniziert → LLM weiß trotzdem nicht, dass er es setzen kann).

→ **Option A ist zwingend**, weil dem LLM die Möglichkeit via `param_schema → capabilities → system prompt` explizit bekannt gemacht werden muss.

### Betroffene Tests

`backend/tests/unit/preprocessing/test_imputation.py` — alle Tests verwenden implizit "alle Spalten". Neue Tests für `columns`-Filterung müssen ergänzt werden. Bestehende Tests müssen NICHT geändert werden, wenn `columns=[]` (leer) korrekt als "alle Spalten" interpretiert wird.

### ⚠️ Offene Entscheidung 1A-1

> Soll der `columns`-Parameter die Spalten auf **numerische** einschränken (Fehler wenn nicht-numerische Spalte angegeben), oder soll er **still ignorieren** wenn die Spalte nicht im `_fill_values`-Mapping ist (bereits so implementiert in `transform()` Zeile 10: `if col not in result_train.columns: continue`)?

### ⚠️ Offene Entscheidung 1A-2

> Wenn `columns` angegeben, aber eine genannte Spalte hat **keine fehlenden Werte** — soll das einen Hinweis im Metadata liefern oder still `0 Wert(e) ersetzt` melden?

---

## Sub-Bug 1B — Metadata-Zählung doppelt im Pre-Split-Kontext

### Schweregrad

🟠 Hoch — Falsche Zahlen werden dem User angezeigt (8340 statt 4170 bei `weathersit`)

### Betroffene Datei

`backend/src/gysi_ml/executor/executor.py`, Zeilen 203–206

### Exakte Ursache

Im Pre-Split-Zweig des Executors (kein Split-Step in der Spec) wird `df_full` als **beide** Argumente an `transform()` übergeben:

```python
# executor.py, Zeilen 203–206
else:
    step.fit(context.df_full)
    result_train, _ = step.transform(
        context.df_full, context.df_full  # ← gleiche Referenz zweimal
    )
    context.df_full = result_train
```

`transform()` kopiert intern beide Argumente (`result_train = df_train.copy()`, `result_test = df_test.copy()`) und zählt danach NaN-Werte **aus beiden Kopien**:

```python
# imputation.py, Zeilen 38–43
n_train = int(result_train[col].isna().sum())   # z.B. 4170
n_test  = int(result_test[col].isna().sum())    # ← ebenfalls 4170 (Kopie von df_full)
self._imputed_per_col[col] = n_train + n_test   # = 8340 ← falsch
```

Da pre-split kein echter Train/Test-Split existiert, ist das Doppelzählen konzeptuell falsch: Der gesamte Datensatz wird nur einmal imputiert.

### Wichtig: Die eigentliche Imputation ist KORREKT

```python
# executor.py, Zeile 207
context.df_full = result_train  # ← nur result_train wird verwendet, NICHT result_test
```

Die Daten werden korrekt imputiert. Nur die angezeigte Zahl ist falsch.

### Wichtig: Bestehender Test erwartet dieses (falsch) verhalten explizit

```python
# test_imputation.py, Zeilen 94–101
def test_metadata_counts_imputed(df_with_missing):
    step.fit(df_with_missing)
    step.transform(df_with_missing, df_with_missing.copy())  # ← copy(), getrennte Objekte
    meta = step.get_metadata()["imputed_values_per_column"]
    # df_with_missing hat je 1 NaN in a und b, bei train UND test (copy) je 1+1=2
    assert meta["a"] == 2   # ← test erwartet Train+Test summiert
    assert meta["b"] == 2
```

Der Test übergibt bewusst `df_with_missing.copy()` als zweites Argument (getrennte Objekte). Das ist das korrekte Verhalten für den **Post-Split-Fall** (wo Train ≠ Test). Der Test selbst ist für Post-Split korrekt.

### Fix-Optionen

**Option A (empfohlen)**: Im Executor pre-split-Zweig einen leeren DataFrame als zweites Argument übergeben:

```python
import pandas as pd
else:
    step.fit(context.df_full)
    result_train, _ = step.transform(
        context.df_full, pd.DataFrame(columns=context.df_full.columns)
    )
    context.df_full = result_train
```

→ `n_test = 0` für alle Spalten, da der leere DataFrame keine NaNs hat. Zählung = nur train = korrekt.
→ Kein Einfluss auf `transform()` selbst, only executor-change.
→ `test_imputation.py` bleibt unverändert (testet step direkt, nicht den executor-pfad).

**Option B**: In `transform()` eine `is_full_dataset: bool = False` Flag einführen, die nur `n_train` zählt.
→ Ändert das BaseStep-Interface — Breakage-Risiko für alle anderen Steps.

**Option C**: Separate Methode `fit_transform_full(df)` auf BaseStep.
→ Größte Umstrukturierung, aber semantisch sauberste Lösung.

→ **Option A** hat den geringsten Blast-Radius und erfordert keine Änderung am Step-Interface.

### Auswirkende Tests beim Fix

- `test_imputation.py` — **kein Änderungsbedarf** (testet Step direkt, nicht Executor)
- Executor-Integrationstests — prüfen, ob Pre-Split-Metadata korrekte Zahlen enthält (ggf. neu)

### ⚠️ Offene Entscheidung 1B-1

> Soll der Fix in Option A (leerer DataFrame) oder doch als separater Pfad im Step (Option C) umgesetzt werden?
> Option A ist safer. Option C ist sauberer. Trade-off: Scope des Changes.

### ⚠️ Offene Entscheidung 1B-2

> Wenn Option A gewählt: Soll `BaseStep.transform()` explizit documentiert werden, dass ein leerer DataFrame als `df_test` ein gültiger Aufruf ist (Pre-Split-Marker), oder kommt das als Kommentar nur im Executor?

---

## Sub-Bug 1C — `[object Object]` im StatusPanel

### Schweregrad

🟡 Mittel — UI unlesbar, kein falsches Ergebnis in den Daten

### Betroffene Datei

`frontend/src/components/StatusPanel.tsx`, Zeilen 130–134

### Exakte Ursache

Das StatusPanel rendert Step-Metadata generisch mit `String(v)`. Wenn der Wert ein verschachteltes Objekt ist — wie `imputed_values_per_column` (ein `Record<string, number>`) — ergibt `String({...})` → `"[object Object]"`:

```tsx
// StatusPanel.tsx, Zeilen 128–135
{Object.entries(sr.metadata).map(([k, v]) => (
  <div key={k} className="statusMeta">
    {k}: {String(v)}   {/* ← kein JSON-Serializer, kein type-check */}
  </div>
))}
```

### Vergleich: ResultCard macht es richtig

`frontend/src/components/ResultCard.tsx` hat einen dedizierten `formatStepResult(sr: StepResult)` mit einem `switch (sr.step_type)`, der für `impute_missing` explizit `Object.entries(perCol)` rendert. Die ResultCard zeigt die korrekte Ausgabe. Das StatusPanel hat diese Logik nicht.

### Fix-Optionen

**Option A (minimal, kein Breaking Change)**: In `StatusPanel.tsx` prüfen ob `v` ein Objekt ist, und dann `JSON.stringify(v)` oder eine kompakte Darstellung verwenden:

```tsx
const displayValue = (v: unknown): string => {
  if (v === null || v === undefined) return '–'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
```

**Option B (korrekte Lösung)**: `formatStepResult()` aus `ResultCard.tsx` in eine gemeinsame util-Funktion extrahieren und im StatusPanel importieren.
→ DRY, kein doppelter Format-Code. Aber erfordert Refactoring in ResultCard.

**Option C**: StatusPanel zeigt Metadata mit `JSON.stringify` immer vollständig (kein type-spezifisches Formatting).
→ Schnell, aber unschön für komplexe Objekte.

### Betroffene Tests

- `frontend/src/components/MessageList.test.tsx` — Kein direkter Test für StatusPanel-Metadata
- Neue Tests für StatusPanel-Metadata-Rendering ggf. sinnvoll

### ⚠️ Offene Entscheidung 1C-1

> Option A (lokaler Fix mit JSON.stringify) oder Option B (gemeinsame util-Funktion)?
> Option B ist nachhaltiger, aber wenn `ResultCard.tsx` korrekt funktioniert und nicht angefasst werden soll, lieber Option A.

---

## Sub-Bug 1D — LLM halluziniert falschen `most_frequent`-Wert

### Schweregrad

🟠 Hoch — Falsche Information gegenüber User, Vertrauensverlust

### Betroffene Datei

`backend/src/gysi_ml/llm/prompts.py` (System-Prompt)

### Exakte Ursache

Das LLM hat **keinen Zugriff auf tatsächliche Datenstatistiken**. Wenn der User einen festen Wert anfragt (z.B. `"impute weathersit mit dem Wert 4"`), kann das LLM keinen festen Wert in die Spec schreiben (nicht unterstützt), wählt stattdessen `most_frequent` — und halluziniert dann, dass `most_frequent = 4` wäre.

Tatsächlich: `weathersit`-Verteilung im Bike-Datensatz ist `1=9.004, 2=5.168, 3=2.117, 4=90`. Der häufigste Wert ist **1**, nicht 4.

Das LLM kennt die Verteilung nicht, weil der System-Prompt keine Spaltenstatistiken enthält.

Zusätzliches UX-Problem: Das LLM sagt dem User nicht klar, was möglich ist. Eine gute Antwort wäre:
> "Feste Werte werden nicht unterstützt. Mögliche Strategien: median (= X), mean (= Y), most_frequent (= 1). Welche soll ich verwenden?"

Das geschieht nicht weil kein Prompt-Instruction dafür existiert.

### Fix-Optionen

**Option A**: System-Prompt explizit instruieren: Wenn User festen Wert angibt und das nicht unterstützt wird, soll das LLM in der `explanation` alle verfügbaren Strategien mit ihren konkreten Werten nennen.

Problem: Das LLM kennt die konkreten Werte (Median von weathersit = ?) nicht — nur wenn diese als Kontext übergeben werden.

**Option B**: Datenstatistiken (Median, Mean, Most-Frequent pro Spalte) beim Start der Session einmalig berechnen und als Teil des System-Prompts übergeben.

Dies würde ermöglichen: "Most-frequent von weathersit = 1. Median = 1. Mean = 1.4."
→ LLM kann dann korrekt informieren.

**Option C**: Im System-Prompt nur instruieren "Kommuniziere Unsicherheit explizit. Wenn du keinen Wert kennst, sage das." — ohne echte Daten.
→ Verhindert Halluzination nicht zuverlässig, aber verbessert Transparenz.

### ⚠️ Offene Entscheidung 1D-1

> Option A (rein Prompt-Instruction ohne echte Werte) vs. Option B (echte Spaltenstatistiken im System-Prompt)?
> Option B ist die korrekte Lösung, hat aber Implementierungsaufwand (wo werden die Stats berechnet? In `build_system_prompt()`? Wird ein neuer Service benötigt?).

### ⚠️ Offene Entscheidung 1D-2

> Wenn Option B: Sollen Statistiken bei jedem LLM-Aufruf neu berechnet werden (immer aktuell, da sich der Datensatz theoretisch durch Filterung ändern kann), oder einmalig beim Session-Start gespeichert?

---

## Sub-Bug 1E — `modify_spec` statt `execute`, und Info-Fragen crashen

### Schweregrad

🟠 Hoch — Inkonsistentes LLM-Verhalten; Informationsfragen produzieren harten Fehler

### Zwei getrennte Teilprobleme

#### Teil E1: `modify_spec` statt `execute` bei klarer Ausführungsanfrage

**Betroffene Datei**: `backend/src/gysi_ml/llm/prompts.py` (System-Prompt)

**Ursache**: Die Grenze zwischen `execute` und `modify_spec` im System-Prompt ist für das LLM mehrdeutig:

```
"Setze Imputationsstrategie auf mean" → modify_spec (laut Prompt)
"Impute fehlende Werte in weathersit mit most_frequent" → sollte execute sein
```

Das LLM interpretiert die zweite Formulierung als "Strategie ändern" → `modify_spec`. Resultat: Im UI erscheint "Strategie geändert auf most_frequent", aber keine Pipeline-Ausführung. Kein Fehler, kein sichtbarer Hinweis.

**Fix-Richtung**: System-Prompt präzisieren. Klares Beispiel ergänzen:

```
"Impute fehlende Werte in [Spalte] mit [Strategie]" → execute (direkte Ausführungsanfrage)
"Setze die Imputationsstrategie in der Spec auf [Strategie]" → modify_spec (reine Spec-Änderung ohne Ausführung)
```

#### Teil E2: Informationsfragen produzieren Hard-Error

**Betroffene Dateien**:
- `backend/src/gysi_ml/llm/response_schema.py`, Zeile 11 (Action-Enum)
- `backend/src/gysi_ml/services/message_service.py`, Zeilen 120–132 (Retry-Logik)

**Ursache**: Das Action-Enum erlaubt nur:

```python
"enum": ["execute", "propose", "modify_spec", "compare_runs", "rollback", "abort_step_by_step"]
```

Reine Informationsanfragen ("Welcher war der most_frequent Wert?", "Was haben wir bisher gemacht?") können in keines dieser Schemas passen. Das LLM versucht es und scheitert — Retry scheitert ebenfalls → Error: "Das Sprachmodell konnte keine gültige Aktion erzeugen."

**Fix-Optionen für E2**:

**Option A**: Neuen `action`-Typ `"info"` hinzufügen.

Anforderungen:
1. `response_schema.py` Enum um `"info"` erweitern
2. `message_service.py` Handler für `action == "info"` ergänzen → gibt `explanation` als Chat-Nachricht zurück, kein Execute
3. JSON-Schema validiert weiterhin, aber kein Execute ausgelöst

```python
if action == "info":
    return {"type": "assistant", "message": explanation}
```

**Option B**: System-Prompt instruieren, bei reinen Informationsfragen `action: "propose"` mit `steps: []` zu verwenden und die Antwort in `explanation` zu formulieren.
→ Kein Code-Change nötig, aber semantisch missbraucht `propose` als Info-Carrier.
→ Der leere `steps`-Array könnte Folgeprobleme erzeugen (leer = Re-Run der aktuellen Spec, siehe `_merge_specs()`).

**Achtung bezüglich Option B und `_merge_specs()`**:

In `message_service.py` Zeile 22–56 ist `_merge_specs()` implementiert:
```python
if not new_steps:
    return {**new_spec, "steps": current_steps}  # ← leere Spec = Re-Run!
```

`propose` mit leerem `steps`-Array würde bei Bestätigung die aktuelle Spec neu ausführen. Das ist für einen Info-Use-Case falsch.

→ **Option A ist sicherer**, aber erfordert Änderungen in 2 Backend-Dateien + Schema-Update.

### ⚠️ Offene Entscheidung 1E-1

> Soll `action: "info"` als neuer Schema-Typ implementiert werden (Option A, Code-Change), oder reicht ein Prompt-Instruction-Fix (Option B, aber mit `_merge_specs`-Kollision)?

### ⚠️ Offene Entscheidung 1E-2

> Wenn `action: "info"` implementiert wird — soll die Info-Antwort auch in der Message-History gespeichert werden? (Aktuell werden alle Antworten gespeichert. Info-Antworten enthalten keine Spec-Daten.)

### ⚠️ Offene Entscheidung 1E-3

> Für Teil E1: Soll der System-Prompt stärker differenzieren, oder soll eine Nutzerdokumentation klarstellen, wie User korrekt formulieren (z.B. "Führe Imputation aus" vs. "Ändere Strategie")? Oder beides?

---

## Abhängigkeiten zwischen den Sub-Bugs

```
Bug 1A (keine columns) ──────────────────────────────────────────────── eigenständig
Bug 1B (doppelte Zählung) ────────────────────────────────────────────── eigenständig
Bug 1C (StatusPanel [object Object]) ────────────────────────────────── eigenständig
Bug 1D (halluzinierter most_frequent) ────────────────────────────────── eigenständig
Bug 1E (modify_spec statt execute + Info-Crash) ─────────────────────── eigenständig

Bug 1D + Bug 1E (Teil E2, Option B): ACHTUNG Konflikt
→ Wenn Bug 1D via Option B (Spaltenstatistiken im Prompt) gefixt wird
   und Bug 1E via Option A (action: "info") gefixt wird,
   können Infofragen wie "Welcher ist der most_frequent Wert?"
   korrekt als action:info mit echten Stats beantwortet werden.
   Das wäre die ideale Kombination.
```

---

## Empfohlene Fix-Reihenfolge

| Reihenfolge | Sub-Bug | Begründung |
|-------------|---------|------------|
| 1. | 1A | Kernfunktion defekt, einfachster isolierter Fix |
| 2. | 1E (Teil E2) | `action:info` brauchen auch Bug-1D-Fixes als Grundlage |
| 3. | 1B | Kleiner Executor-Fix, kein Interface-Change |
| 4. | 1D | Braucht Entscheidung über Stats-Kontext (größerer Scope) |
| 5. | 1C | UI-only, geringster Impact |
| 6. | 1E (Teil E1) | Prompt-Tuning nach Entscheidung 1D |

---

## Betroffene Dateien (Übersicht)

| Datei | Bug | Art der Änderung |
|-------|-----|------------------|
| `backend/src/gysi_ml/steps/preprocessing/imputation.py` | 1A | `param_schema` + `fit()` erweitern |
| `backend/src/gysi_ml/executor/executor.py` | 1B | Pre-Split-Zweig: leerer DataFrame als zweites Argument |
| `frontend/src/components/StatusPanel.tsx` | 1C | Metadata-Rendering verbessern |
| `backend/src/gysi_ml/llm/prompts.py` | 1D, 1E (E1) | System-Prompt anpassen |
| `backend/src/gysi_ml/llm/response_schema.py` | 1E (E2) | Action-Enum um `"info"` erweitern |
| `backend/src/gysi_ml/services/message_service.py` | 1E (E2) | Handler für `action == "info"` |
| `backend/tests/unit/preprocessing/test_imputation.py` | 1A | Neue Tests für `columns`-Parameter |

---

## Dateien die NICHT geändert werden dürfen

| Datei | Begründung |
|-------|------------|
| `frontend/src/components/ResultCard.tsx` | Funktioniert korrekt, darf nicht angefasst werden |
| `backend/src/gysi_ml/steps/base.py` | BaseStep-Interface stabil halten (außer bei Option C für 1B) |
| `backend/src/gysi_ml/spec/schema.py` | PIPELINE_SPEC_SCHEMA nicht ändern, `columns` gehört in param_schema des Steps |
| `backend/tests/unit/preprocessing/test_imputation.py` | Bestehende Tests dürfen nur ergänzt, nicht verändert werden |
