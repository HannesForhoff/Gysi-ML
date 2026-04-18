# Bug 1.4 — `correlation_filter`: Fehlende Metadaten, Sofortausführung ohne Rückfrage, kein Artefakt

**Status:** Analysiert, Fix ausstehend — **3 offene Designentscheidungen (siehe Ende des Dokuments)**
**Schweregrad:** Kritisch + Hoch + Mittel + Niedrig (4 eigenständige Teilprobleme)
**Kategorie:** Backend (Step-Implementierung + LLM-Prompt) + Frontend (ResultCard-Renderer)
**Analysiert von:** Amelia (Developer Agent), 2026-04-04

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| "Wende einen Correlation Filter auf den Datensatz an und sag mir welche Variablen stark miteinander korrelieren und damit entfernt werden könnten" | LLM schlägt Korrelationsanalyse vor (`propose`), zeigt Paare mit Korrelationswerten, fragt User welches Feature entfernt wird | LLM führt sofort `execute` aus, entfernt `temp` still, Ausgabe: `✓ correlation_filter — Entfernt: temp` |

**Konkrete User-Aussagen zu den Mängeln:**

1. Korrelationspaare werden ohne Zahlenwerte angezeigt (kein `0.985` o.ä.)
2. `temp` wird sofort entfernt ohne Rückfrage — der User fühlt sich ausgeschlossen
3. Kein Hinweis welches Feature aus einem Paar entfernt wurde und warum
4. Keine Information über Features die mit keinem anderen Feature korrelieren
5. Obwohl eine Spalte dauerhaft entfernt wurde, wird kein Zwischen-Artefakt (CSV) erstellt

---

## Technische Ursachenanalyse — 4 eigenständige Teilprobleme

---

### Problem A — Keine Korrelationswerte in der Metadata (Schweregrad: Hoch)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/correlation_filter.py`

**Ist-Zustand `fit()` (Zeilen 17–33):**

```python
def fit(self, df_train: pd.DataFrame) -> None:
    numeric_cols = df_train.select_dtypes(include="number").columns.tolist()
    if len(numeric_cols) < 2:
        self._features_to_drop = []
        return

    corr_matrix = df_train[numeric_cols].corr().abs()  # ← wird lokal berechnet
    to_drop: set[str] = set()

    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            if corr_matrix.iloc[i, j] >= self.threshold:
                col_a = numeric_cols[i]
                col_b = numeric_cols[j]
                to_drop.add(max(col_a, col_b))           # ← nur Drop-Kandidaten gespeichert

    self._features_to_drop = sorted(to_drop)             # ← corr_matrix danach weggeworfen
```

**Ist-Zustand `get_metadata()` (Zeile 44–45):**

```python
def get_metadata(self) -> dict:
    return {"dropped_features": self._features_to_drop}
    # Beispiel-Rückgabe: {"dropped_features": ["temp"]}
```

Die Korrelationsmatrix `corr_matrix` wird während `fit()` vollständig berechnet, aber nach der Schleife nicht gespeichert. Nach Abschluss von `fit()` sind die konkreten Korrelationswerte (z.B. `0.985` zwischen `atemp` und `temp`) dauerhaft verloren. `get_metadata()` kann daher nur zurückgeben **was entfernt wurde** — nicht **warum** und **wie stark**.

**Ist-Zustand Frontend `ResultCard.tsx` (Zeilen 50–57):**

```tsx
case 'correlation_filter': {
  const dropped = m.dropped_features
  if (Array.isArray(dropped)) {
    if (dropped.length === 0) return 'Keine hochkorrelierten Features gefunden.'
    return `Entfernt: ${(dropped as string[]).join(', ')}`
    // → "Entfernt: temp"  (kein Paar, kein Wert)
  }
  return 'Korrelations-Filter abgeschlossen.'
}
```

Das Frontend könnte korrelierte Paare mit Werten anzeigen — es **bekommt sie aber nicht geliefert**, weil das Backend sie nicht zurückgibt.

**Ziel-Metadata-Struktur nach dem Fix:**

```python
# get_metadata() Ziel-Rückgabe
{
    "dropped_features": ["temp"],
    "corr_pairs": [
        {"col_a": "atemp", "col_b": "temp", "value": 0.985},   # Paar + Wert + welches entfernt
        {"col_a": "casual", "col_b": "registered", "value": 0.946}
    ],
    "independent_features": ["instant", "season", "yr", ...]    # ← siehe Problem C
}
```

**Nötige Änderung im Backend:**

In `fit()` müssen die Korrelationspaare als Instanzvariable gespeichert werden:

```python
# __init__ — neu hinzufügen:
self._corr_pairs: list[dict] = []

# fit() — nach der Schleife statt `self._features_to_drop = sorted(to_drop)`:
self._corr_pairs = []
for i in range(len(numeric_cols)):
    for j in range(i + 1, len(numeric_cols)):
        val = corr_matrix.iloc[i, j]
        if val >= self.threshold:
            col_a = numeric_cols[i]
            col_b = numeric_cols[j]
            dropped = max(col_a, col_b)
            self._corr_pairs.append({
                "col_a": col_a,
                "col_b": col_b,
                "value": round(float(val), 4),
                "dropped": dropped,           # ← klar was entfernt wird
            })
            to_drop.add(dropped)
```

**Nötige Änderung im Frontend `ResultCard.tsx`:**

Den `correlation_filter`-Case um Paar-Anzeige erweitern:

```tsx
case 'correlation_filter': {
  const dropped = m.dropped_features as string[] | undefined
  const pairs = m.corr_pairs as Array<{col_a: string, col_b: string, value: number, dropped: string}> | undefined
  const independent = m.independent_features as string[] | undefined

  const parts: string[] = []

  if (pairs && pairs.length > 0) {
    const pairStr = pairs
      .map(p => `${p.col_a}↔${p.col_b} (r=${p.value}, entfernt: ${p.dropped})`)
      .join(' | ')
    parts.push(`Korrelierte Paare: ${pairStr}`)
  }
  if (dropped && dropped.length > 0) {
    parts.push(`Entfernt: ${dropped.join(', ')}`)
  } else {
    parts.push('Keine hochkorrelierten Features gefunden.')
  }
  // independent_features: Anzeige je nach Entscheidung C

  return parts.join(' — ')
}
```

---

### Problem B — Sofortausführung ohne Nutzerfrage, hartcodierte Feature-Wahl (Schweregrad: Kritisch)

Dieses Problem besteht aus **zwei voneinander unabhängigen Ursachen**.

#### B1 — LLM wählt `execute` statt `propose`

**Datei:** `backend/src/gysi_ml/llm/prompts.py`

**Ist-Zustand (Zeilen 41–46):**

```python
## Regeln für action-Wahl

- **"execute"**: Verwende dies wenn der Nutzer eine klare, eindeutige Aktion beschreibt...
- **"propose"**: Verwende dies wenn:
  - die Eingabe vage ist, mehrere Interpretationen zulässt, oder wichtige Parameter fehlen
  - der Nutzer explizit nach Empfehlungen fragt
```

Die Nutzeranfrage `"sag mir welche Variablen stark miteinander korrelieren und damit entfernt werden könnten"` ist **klar eine Informationsanfrage** (Konjunktiv: "könnten"). Sie nennt keinen Parameter-Threshold und gibt keine Auswahl vor welches Feature entfernt werden soll.

Das LLM interpretiert sie dennoch als `execute` — wahrscheinlich weil `correlation_filter` klar benannt ist und der Nutzer scheinbar weiss was er will. Der Prompt klärt nicht explizit, dass beim `correlation_filter` immer `propose` genutzt werden soll, da die Feature-Auswahl beim User liegt.

**Nötige Änderung im Prompt:**

In den `## Regeln für action-Wahl`-Abschnitt eine spezifische Regel für `correlation_filter` ergänzen:

```
- **Sonderregel `correlation_filter`**: Verwende IMMER `propose`, auch wenn der Nutzer
  klar `correlation_filter` nennt. Der Grund: Die Entscheidung welches Feature aus einem
  korrelierten Paar entfernt werden soll, liegt IMMER beim Nutzer. Das LLM darf diese
  Entscheidung niemals automatisch treffen. Zeige in der `explanation` die Paare mit
  Korrelationswerten und frage den Nutzer welches Feature er entfernen möchte.
```

#### B2 — Step entfernt automatisch das alphabetisch spätere Feature

**Datei:** `backend/src/gysi_ml/steps/preprocessing/correlation_filter.py`, Zeile 30–31

**Ist-Zustand:**

```python
# Alphabetisch späteres Feature entfernen
to_drop.add(max(col_a, col_b))
```

`max("temp", "atemp")` = `"temp"` (da "t" > "a" alphabetisch). Die Entscheidung wird **stillschweigend und ohne Kommunikation** getroffen. Es könnte aus fachlicher Sicht sinnvoller sein, `atemp` zu entfernen (z.B. weil `temp` direkter interpretierbar ist). Der User hat keine Möglichkeit, das zu steuern.

**Offene Designentscheidung 1 (siehe Ende des Dokuments):** Hier liegt eine Designentscheidung vor — zwei Optionen:

- **Option A (Prompt-Fix):** Das LLM erzeugt immer `propose` → User sieht Paare → User bestätigt selektiv welche Features entfernt werden → Die `max()`-Logik bleibt als Fallback, wird aber durch User-Bestätigung übersteuert
- **Option B (Step-Parameter-Fix):** Der Step erhält einen neuen Parameter `features_to_drop: list[str]`, der explizit die zu entfernenden Features enthält. Die `max()`-Automatik entfällt komplett. Das LLM befüllt diesen Parameter nach User-Bestätigung.

---

### Problem C — Keine Information über isolierte/unkorrelierte Features (Schweregrad: Niedrig, Feature)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/correlation_filter.py`

**Ist-Zustand:** Der `fit()`-Algorithmus erfasst ausschließlich Features, deren Korrelationswert zu irgendeinem anderen Feature den Threshold überschreitet. Features die mit **keinem** anderen Feature stark korrelieren, werden nicht identifiziert.

**Wunsch-Verhalten:** Der Nutzer möchte sehen, welche Features **eigenständig** sind — also informativer Alleinstand, maximale Korrelation zu allen anderen Features liegt unter dem Threshold. Das ist analytisch wertvoll: Ein Feature das mit nichts korrleiert, enthält möglicherweise einzigartigen Informationsgehalt.

**Technische Machbarkeit:** Vollständig realisierbar ohne Architekturänderung. Da `fit()` bereits die vollständige `corr_matrix` berechnet, genügt ein zusätzlicher Loop nach der bestehenden Schleife:

```python
# Nach der bestehenden Paar-Schleife in fit():
correlated_features: set[str] = set()
for p in self._corr_pairs:
    correlated_features.add(p["col_a"])
    correlated_features.add(p["col_b"])

self._independent_features = sorted(
    col for col in numeric_cols if col not in correlated_features
)
```

**Offene Designentscheidung 2 (siehe Ende des Dokuments):** Soll `independent_features` in `get_metadata()` zurückgegeben und im Frontend angezeigt werden?

---

### Problem D — Kein Zwischenartefakt nach Spaltenentfernung (Schweregrad: Mittel)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/correlation_filter.py` + `backend/src/gysi_ml/steps/base.py`

**Ist-Zustand:**

`CorrelationFilterStep` überschreibt `generate_artifact()` nicht. Der Default aus `BaseStep` gibt `None` zurück:

```python
# base.py, Zeile 31–38
def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | dict | None:
    """Preprocessing-Steps geben immer None zurück (Default)."""
    return None
```

**Vergleich mit `SplitStep`:**

`SplitStep` überschreibt `generate_artifact()` und schreibt zwei CSVs:
```python
# split.py, Zeile 67–80
def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | None:
    # Schreibt run_id_train.csv und run_id_test.csv
    return [
        {"type": "split_train", "file_path": train_path},
        {"type": "split_test", "file_path": test_path},
    ]
```

Das Split-Artefakt erscheint im Frontend als Download-Link in der `ResultCard`.

**Inkonsistenz:**

| Step | Strukturelle Änderung am Datensatz | Artefakt erzeugt? |
|---|---|---|
| `split` | Datensatz → 2 Teile | ✅ 2 CSVs |
| `correlation_filter` | Datensatz → 1 Spalte weniger (permanent) | ❌ kein CSV |
| `outlier_handling` | Werte werden geclippt | ❌ kein CSV |
| `impute_missing` | NaN-Werte werden ersetzt | ❌ kein CSV |
| `encode_categorical` | Spalten werden kodiert/erweitert | ❌ kein CSV |

Die Entfernung einer Spalte durch `correlation_filter` ist strukturell einschneidender als z.B. Werte-Imputation — ein Feature ist danach dauerhaft nicht mehr im Datensatz vorhanden. Ein persistiertes CSV wäre für spätere Nachvollziehbarkeit und für das Frontend als Referenz nützlich.

**Nötige Änderung:** `generate_artifact()` in `CorrelationFilterStep` überschreiben. Der Post-Filter-Datensatz (`df_train` nach `transform()`) muss dafür als Instanzvariable gespeichert werden — analog zu `SplitStep._df_train`.

```python
# __init__ — neu:
self._df_filtered: pd.DataFrame | None = None

# transform() — am Ende:
self._df_filtered = df_train  # gespeichert für generate_artifact()
return df_train.drop(...), df_test.drop(...)

# generate_artifact() — neu überschreiben:
def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | None:
    if self._df_filtered is None:
        return None
    import os
    os.makedirs(artifacts_path, exist_ok=True)
    path = os.path.join(artifacts_path, f"{run_id}_correlation_filter.csv")
    self._df_filtered.to_csv(path, index=False)
    return [{"type": "correlation_filter_result", "file_path": path}]
```

**Offene Designentscheidung 3 (siehe Ende des Dokuments):** Soll das Artefakt den **gefilterten Train-Datensatz** enthalten, den **Gesamtdatensatz** (pre-Split), oder **beide** (Train + Test)?

---

## Betroffene Dateien

| Datei | Rolle | Änderung nötig | Begründung |
|---|---|---|---|
| `backend/src/gysi_ml/steps/preprocessing/correlation_filter.py` | Step-Implementierung | **Ja — Kern des Bugs** | `_corr_pairs` + `_independent_features` speichern; `get_metadata()` erweitern; `generate_artifact()` überschreiben; optional: `features_to_drop`-Parameter |
| `backend/src/gysi_ml/llm/prompts.py` | LLM System-Prompt | **Ja** | Sonderregel für `correlation_filter` → immer `propose` |
| `frontend/src/components/ResultCard.tsx` | Step-Result-Renderer | **Ja** | `correlation_filter`-Case um Paar-Anzeige, Korrelationswerte und optional `independent_features` erweitern |
| `backend/tests/preprocessing/test_correlation_filter.py` | Unit-Tests | **Ja** | Tests für neue Metadata-Felder (`corr_pairs`, `independent_features`), `generate_artifact()` |
| `frontend/src/components/ResultCard.test.tsx` | Frontend-Tests | **Ja** | Render-Tests für neuen `correlation_filter`-Case |
| `backend/src/gysi_ml/core/capabilities.py` | LLM-Capabilities | **Ggf.** | Nur wenn `features_to_drop`-Parameter laut Entscheidung 1 Option B hinzukommt → `param_schema` aktualisieren |

---

## Reihenfolge-Empfehlung für den Fix

1. **Problem A** zuerst (Backend `correlation_filter.py` — `_corr_pairs` speichern + `get_metadata()`) — alle anderen Teile bauen darauf auf
2. **Problem B1** (Prompt-Regel) — unabhängig, kann parallel zu A erledigt werden
3. **Problem B2** (nach Entscheidung 1 — `max()`-Logik oder `features_to_drop`-Parameter)
4. **Problem D** (Artefakt) — nach Entscheidung 3
5. **Problem C** (independent_features) — nach Entscheidung 2, zuletzt da geringster Impact
6. Frontend `ResultCard.tsx` — nach Abschluss aller Backend-Änderungen
7. Tests — parallel zu jedem Schritt

---

## Offene Designentscheidungen — müssen VOR dem Fix mit Hannes geklärt werden

### Entscheidung 1 — Wie wird die Feature-Auswahl beim `correlation_filter` vom User kontrolliert?

**Kontext:** Aktuell wählt die `max()`-Logik automatisch das alphabetisch spätere Feature. Das verletzt die Nutzerkontrolle.

**Option A — Nur Prompt-Fix (empfohlen als Minimum):**
- LLM erzeugt für `correlation_filter` immer `propose`
- User sieht die Paare mit Korrelationswerten und `propose`-Buttons
- User bestätigt den Vorschlag → `max()`-Logik greift dann als Fallback
- Kein neuer Step-Parameter, keine Backend-Änderung an der Auswahllogik
- Nachteil: User kann immer noch nicht explizit sagen „ich will `atemp` statt `temp` entfernen"

**Option B — Step-Parameter `features_to_drop` (vollständige Kontrolle):**
- Neuer optionaler Parameter: `"features_to_drop": ["temp"]` im `param_schema`
- Wenn befüllt: dieser Parameter übersteuert die `max()`-Logik
- Das LLM befüllt ihn nach User-Bestätigung im Proposal-Schritt
- `max()`-Logik bleibt als Fallback wenn Parameter leer
- Mehr Änderung: `param_schema` erweitern, Executor-Logik im Step anpassen, Capabilities aktualisieren

**Frage an Hannes:** Option A oder Option B — oder eine Kombination?

---

### Entscheidung 2 — Soll `independent_features` in der Ausgabe erscheinen?

**Kontext:** Features ohne starke Korrelation zu anderen können angezeigt werden. Das ist informativ aber optional.

**Option A — Ja, immer anzeigen:**
- `independent_features` in `get_metadata()` zurückgeben
- Frontend zeigt diese Liste z.B. als „Eigenständige Features: instant, season, yr, ..."
- Nutzen: Nutzer versteht den Datensatz besser, sieht was behalten wurde

**Option B — Nein, nicht implementieren:**
- Scope klein halten
- Feature kann später separat als eigene User Story umgesetzt werden

**Option C — Ja, aber nur in Metadata, nicht im Frontend:**
- Daten werden zurückgegeben, aber `ResultCard.tsx` zeigt sie nicht an
- Zukunftssicher, kein Frontend-Aufwand jetzt

**Frage an Hannes:** Implementieren — und wenn ja, auch im Frontend anzeigen?

---

### Entscheidung 3 — Welcher Datensatz wird als Artefakt gespeichert?

**Kontext:** Analog zu `split` (Train + Test CSV) soll `correlation_filter` ein CSV-Artefakt erzeugen. Welcher Stand?

**Option A — Nur gefilterter Train-Datensatz:**
- Entspricht `self._df_filtered` nach `transform()` auf `df_train`
- Einfachste Lösung, konsistent mit anderen Steps
- Artefakt-Typ: `"correlation_filter_result"`

**Option B — Gefilterter Train- + Test-Datensatz:**
- Analog zu `split` (zwei Artefakte)
- Vollständiges Bild: beide Hälften haben dieselben Spalten entfernt
- Artefakt-Typen: `"correlation_filter_train"` + `"correlation_filter_test"`
- Nachteil: wenn noch kein Split erfolgt ist, gibt es keinen separaten Test-Datensatz

**Option C — Gesamtdatensatz (pre-Split, post-Filter):**
- Nur sinnvoll wenn `correlation_filter` vor dem `split` läuft (was der Normalfall ist)
- Artefakt-Typ: `"correlation_filter_full"`

**Frage an Hannes:** Option A (einfach), B (vollständig analog zu split) oder C (Gesamtdatensatz)?
