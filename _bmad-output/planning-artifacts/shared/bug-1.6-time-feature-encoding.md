# Bug 1.6 — `time_feature_encoding`: Halluziniertes Feature, unkommuniziertes Drop, fehlendes Frontend-Rendering, kein Artefakt

**Status:** Analysiert, Fix ausstehend — **4 offene Designentscheidungen (siehe Ende des Dokuments)**
**Schweregrad:** Kritisch + Hoch + Mittel + Niedrig (4 eigenständige Teilprobleme)
**Kategorie:** Backend (Step-Implementierung + LLM-Prompt) + Frontend (ResultCard-Renderer)
**Analysiert von:** Amelia (Developer Agent), 2026-04-04

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| "Extrahiere neue Time Features aus dteday. Erzeuge eine neue Spalte namens day_of_month" | `day_of_month` (dt.day) wird als neue Spalte hinzugefügt; `dteday` bleibt erhalten oder Nutzer wird informiert dass es entfernt wird; Artefakt mit Zwischenstand | `day_of_month` existiert NICHT; `dteday` wird still gelöscht; Metadata-JSON als Rohtext im UI |

**LLM-Explanation aus dem Chat (faktisch falsch):**

```
Ich habe neue Zeitmerkmale aus der Spalte 'dteday' extrahiert und eine neue Spalte
namens 'day_of_month' erstellt. Diese neue Spalte enthält den Tag des Monats...
```

**Tatsächliche `get_metadata()`-Ausgabe des Steps:**

```json
{"derived_features": ["weekday", "month"], "dropped_column": "dteday"}
```

Widerspruch: LLM behauptet `day_of_month` erstellt → Metadata belegt eindeutig, dass nur `weekday` und `month` existieren.

---

## Technische Ursachenanalyse — 4 eigenständige Teilprobleme

---

### Problem A — `day_of_month` nicht implementiert, LLM halluziniert Erfolg (Schweregrad: Kritisch)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/time_features.py`

**Ist-Zustand `_apply()` (Zeilen 27–33):**

```python
def _apply(self, df: pd.DataFrame) -> pd.DataFrame:
    if self._column not in df.columns:
        return df.copy()
    result = df.copy()
    dates = pd.to_datetime(result[self._column])
    result["weekday"] = dates.dt.dayofweek   # ← hardcodiert
    result["month"] = dates.dt.month         # ← hardcodiert
    result = result.drop(columns=[self._column])
    return result
```

**Ist-Zustand `get_metadata()` (Zeilen 34–38):**

```python
def get_metadata(self) -> dict:
    return {
        "derived_features": ["weekday", "month"],   # ← hardcodierte Liste, kein Bezug zu Params
        "dropped_column": self._column,
    }
```

**Was fehlt:**

`dates.dt.day` — der Pandas-Accessor für den Tag-des-Monats — wird nirgendwo aufgerufen. Der Step kennt nur `dayofweek` und `month`. Es gibt weder einen Parameter noch eine Erweiterungslogik, die `day_of_month` erzeugen würde.

**Warum halluziniert das LLM:**

Das LLM interpretiert „Erzeuge `day_of_month`" als ausführbare Anfrage, weil der Step-Typ `time_feature_encoding` im Capabilities-Schema registriert ist (`capabilities.py` liest `param_schema` aller Steps). Das `param_schema` des Steps:

```python
param_schema = {"column": {"type": "string", "default": "dteday"}}
```

Es gibt nur den Parameter `column` — keine `features`-Liste. Das LLM hat keine Möglichkeit, `day_of_month` als Parameter weiterzugeben, und der Step hat keine Logik, ihn zu verarbeiten. Das LLM erzeugt dennoch `execute` + eine Erfolgs-Explanation, weil es keine Rückmeldung erhält, dass das gewünschte Feature nicht unterstützt wird.

**Auswirkung:**

Nach Ausführung des Steps existiert `day_of_month` **nicht** im DataFrame. Nachfolgende Steps oder das Modell die auf diese Spalte zugreifen würden einen `KeyError` werfen. Der Nutzer glaubt auf Basis der LLM-Erklärung, dass die Spalte vorhanden ist.

**Verify-Beweis aus `test_time_features.py`:**

Der bestehende Test `test_metadata_derived_features` (Zeile 185–191) prüft explizit:

```python
assert "weekday" in meta["derived_features"]
assert "month" in meta["derived_features"]
# Kein Test für day_of_month — er würde scheitern
```

Es gibt keinen Test der prüft ob `day_of_month` als Feature angelegt wird. Umgekehrt: ein Test `assert "day_of_month" in result_train.columns` würde aktuell **fehlschlagen**.

**Offene Designentscheidung 1 (siehe Ende des Dokuments):** Wie wird das Feature-Set des Steps konfigurierbar gemacht — fester Erweiterungs-Patch oder flexibler `features`-Parameter?

---

### Problem B — `dteday` wird hardcodiert gelöscht, kein Parameter, kein Hinweis an Nutzer (Schweregrad: Hoch)

Dieses Problem besteht aus **zwei voneinander unabhängigen Ursachen**.

#### B1 — Kein `drop_original`-Parameter

**Datei:** `backend/src/gysi_ml/steps/preprocessing/time_features.py`, Zeile 31

**Ist-Zustand:**

```python
result = result.drop(columns=[self._column])   # ← bedingungslos, kein Parameter
```

Das Drop-Verhalten ist nicht konfigurierbar. Der Nutzer hat kein Mittel, `dteday` im DataFrame zu behalten. Der `param_schema` hat nur `column` — kein `drop_original: bool`.

**ML-Kontext (warum das Drop technisch seriös ist):**

Ein roher Datums-String wie `"2020-01-06"` ist als Modell-Feature unbrauchbar (hohe Kardinalität, keine Ordinalsemantik ohne Encoding). Das Drop verhindert, dass `dteday` als `object`-Dtype in nachfolgende Schritte gelangt und dort z.B. `encode_categorical` auslöst oder einen Fehler verursacht. Das ist also **kein reiner Bug**, sondern ein Design-Entscheid ohne Configurierbarkeit.

**Nutzer-Erwartung vs. Realität:**

Die Anfrage „Erzeuge eine neue Spalte" impliziert Ergänzung, nicht Ersatz. Der Nutzer hat nicht gesagt „lösche `dteday`". Die implizite Erwartung war: DataFrame bekommt `day_of_month` hinzu, `dteday` bleibt erhalten (oder wird zumindest kommuniziert, dass es entfernt wird).

**Ist-Zustand Tests — gefährlicher blinder Fleck:**

Die bestehenden Tests **testen das Drop aktiv als korrektes Verhalten**:

```python
# test_time_features.py, Zeile 113–122
def test_transform_dteday_removed_from_train(df_with_dates):
    ...
    assert "dteday" not in result_train.columns  # ← Drop wird als SOLL-Zustand getestet
```

Wenn beim Fix ein `drop_original`-Parameter eingeführt wird, würden diese Tests mit `drop_original=True` (Default) weiterhin passen, aber es fehlt ein Test für `drop_original=False`.

**Offene Designentscheidung 2 (siehe Ende des Dokuments):** Soll `drop_original` ein konfigurierbarer Parameter werden?

#### B2 — LLM kommuniziert das Drop nicht in der `explanation`

**Datei:** `backend/src/gysi_ml/llm/prompts.py`

**Ist-Zustand:**

Der System-Prompt enthält keinen Hinweis, dass `time_feature_encoding` die Original-Spalte entfernt. Das LLM generiert die `explanation` auf Basis des `param_schema` (aus Capabilities) — und das sagt nur:

```json
{
  "type": "time_feature_encoding",
  "description": "Leitet Wochentag und Monat aus Datumsspalte ab",
  "params": {"column": {"type": "string", "default": "dteday"}}
}
```

Kein Hinweis auf das Drop-Verhalten in `description`. Das LLM kann nicht wissen, dass die Spalte entfernt wird, und erwähnt es entsprechend nicht.

**Auswirkung:**

Der Nutzer erfährt das Drop ausschließlich aus der nackten JSON-Metadata `"dropped_column": "dteday"` — die im UI als `JSON.stringify` angezeigt wird (siehe Problem C). Das ist nicht nutzerfreundlich.

**Nötige Änderung im Step (für LLM-Sichtbarkeit):**

Die `description` des Steps sollte das Drop-Verhalten explizit nennen:

```python
# Ist:
description = "Leitet Wochentag und Monat aus Datumsspalte ab"

# Soll (Beispiel nach Entscheidung 2):
description = "Leitet Zeitfeatures aus Datumsspalte ab und entfernt die Original-Spalte danach"
```

Da `capabilities.py` die `description` direkt als JSON ans LLM weitergibt, würde eine aktualisierte `description` das LLM informieren, dass das Drop stattfindet.

---

### Problem C — `ResultCard.tsx` hat keinen Case für `time_feature_encoding` (Schweregrad: Mittel)

**Datei:** `frontend/src/components/ResultCard.tsx`

**Ist-Zustand `formatStepResult()` switch (Zeilen 10–70):**

```typescript
switch (sr.step_type) {
  case 'dedup':              // ✓ eigener Case
  case 'impute_missing':     // ✓ eigener Case
  case 'split':              // ✓ eigener Case
  case 'outlier_handling':   // ✓ eigener Case
  case 'encode_categorical': // ✓ eigener Case
  case 'correlation_filter': // ✓ eigener Case
  case 'rare_category_bucketing': // ✓ eigener Case
  default:
    return JSON.stringify(m)   // ← time_feature_encoding landet HIER
}
```

`time_feature_encoding` hat keinen eigenen Case und fällt auf `default` → `JSON.stringify(m)`.

**Resultat im UI (genau das, was der Nutzer gesehen hat):**

```
✓ time_feature_encoding
{"derived_features":["weekday","month"],"dropped_column":"dteday"}
```

Das rohe JSON wird dem Nutzer als Statustext angezeigt — unformatiert, technisch, nicht nutzerfreundlich.

**Erwartete Anzeige (Beispiel):**

```
✓ time_feature_encoding
Abgeleitet: weekday, month | dteday entfernt
```

**Nötige Änderung in `ResultCard.tsx`:**

Einen neuen Case hinzufügen (nach Entscheidung 1 und 2 entsprechend anpassen):

```typescript
case 'time_feature_encoding': {
  const derived = m.derived_features as string[] | undefined
  const dropped = m.dropped_column as string | undefined
  const parts: string[] = []
  if (derived && derived.length > 0) {
    parts.push(`Abgeleitet: ${derived.join(', ')}`)
  }
  if (dropped) {
    parts.push(`${dropped} entfernt`)
  }
  return parts.length > 0 ? parts.join(' | ') : 'Zeit-Feature-Encoding abgeschlossen.'
}
```

---

### Problem D — Kein Zwischenartefakt nach Zeit-Feature-Extraktion (Schweregrad: Niedrig-Mittel)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/time_features.py` + `backend/src/gysi_ml/steps/base.py`

**Ist-Zustand:**

`TimeFeatureEncodingStep` überschreibt `generate_artifact()` nicht. Der Default aus `BaseStep` (Zeile 31–38) gibt `None` zurück:

```python
# base.py
def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | dict | None:
    """Preprocessing-Steps geben immer None zurück (Default)."""
    return None
```

**Kontext — warum dieses Problem hier besonders relevant ist:**

`time_feature_encoding` ist unter den Preprocessing-Steps derjenige mit der **stärksten strukturellen Änderung**: Eine Spalte (`dteday`) wird gelöscht und zwei (oder mehr) neue Spalten entstehen. Der DataFrame ändert danach seine Schema-Form. Ein Artefakt-CSV würde dem Nutzer erlauben den neuen Zustand einzusehen ohne die Pipeline erneut laufen zu lassen.

**Vergleiche aus Bug 1.4:**

| Step | Strukturelle Änderung am Datensatz | Artefakt erzeugt? |
|---|---|---|
| `split` | Datensatz → 2 Teile | ✅ 2 CSVs |
| `time_feature_encoding` | Schema ändert sich (Spalte weg, neue Spalten hinzu) | ❌ kein CSV |
| `correlation_filter` | Spalte dauerhaft entfernt | ❌ kein CSV (Bug 1.4 Problem D) |

**Nötige Änderung (Beispiel, vor Entscheidung 3 zur Entfernung zu präzisieren):**

Analog zu `split.py`: `_df_result` als Instanzvariable speichern in `_apply()` und `generate_artifact()` überschreiben:

```python
# __init__ — neu:
self._df_full_result: pd.DataFrame | None = None

# _apply() — am Ende speichern (für generate_artifact):
self._df_full_result = result  # vor return

# generate_artifact() — neu überschreiben:
def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | None:
    if self._df_full_result is None:
        return None
    import os
    os.makedirs(artifacts_path, exist_ok=True)
    path = os.path.join(artifacts_path, f"{run_id}_time_features.csv")
    self._df_full_result.to_csv(path, index=False)
    return [{"type": "time_features_result", "file_path": path}]
```

**Offene Designentscheidung 3 (siehe Ende des Dokuments):** Welcher Datensatz-Stand wird als Artefakt gespeichert?

---

## Betroffene Dateien

| Datei | Rolle | Änderung nötig | Begründung |
|---|---|---|---|
| `backend/src/gysi_ml/steps/preprocessing/time_features.py` | Step-Implementierung | **Ja — Kern des Bugs** | `day_of_month`-Feature hinzufügen (Problem A); `drop_original`-Parameter (Entscheidung 2, Problem B1); `description` aktualisieren (Problem B2); `generate_artifact()` überschreiben (Problem D) |
| `backend/src/gysi_ml/llm/prompts.py` | LLM System-Prompt | **Ggf.** | Nur wenn `description`-Fix in `time_features.py` nicht ausreicht; keine explizite Step-Sonderregel nötig (da `execute` für diesen Step grundsätzlich korrekt ist) |
| `frontend/src/components/ResultCard.tsx` | Step-Result-Renderer | **Ja** | Neuer `time_feature_encoding`-Case statt `default → JSON.stringify` (Problem C) |
| `backend/tests/unit/preprocessing/test_time_features.py` | Unit-Tests | **Ja** | Tests für `day_of_month`; Tests für `drop_original=False`; Tests für `generate_artifact()`; ggf. Tests für flexiblen `features`-Parameter (Entscheidung 1) |
| `frontend/src/components/ResultCard.test.tsx` | Frontend-Tests | **Ja** | Render-Test für neuen `time_feature_encoding`-Case |

---

## Reihenfolge-Empfehlung für den Fix

1. **Problem A** zuerst (Backend `time_features.py` — `day_of_month` hinzufügen, nach Entscheidung 1) — Kern-Bug, alle anderen bauen auf korrektem Feature-Set auf
2. **Problem B1** (nach Entscheidung 2 — `drop_original`-Parameter ggf. einführen) — unabhängig von A, kann parallel
3. **Problem B2** (`description` in `time_features.py` aktualisieren) — schnell, kein Risiko
4. **Problem D** (nach Entscheidung 3 — `generate_artifact()` überschreiben) — technisch unabhängig
5. **Problem C** (Frontend `ResultCard.tsx` — neuer Case) — nach finaler Metadata-Struktur aus Backend-Fixes
6. Tests — parallel zu jedem Schritt, vor Merge

---

## Offene Designentscheidungen — müssen VOR dem Fix mit Hannes geklärt werden

### Entscheidung 1 — Wie wird das Feature-Set des `time_feature_encoding`-Steps konfigurierbar?

**Kontext:** Aktuell erzeugt der Step fix `weekday` und `month`. `day_of_month` fehlt. Wie soll das gelöst werden?

**Option A — Einfacher Patch: `day_of_month` hardcodiert hinzufügen (empfohlen als Minimum):**

```python
result["weekday"] = dates.dt.dayofweek
result["month"] = dates.dt.month
result["day_of_month"] = dates.dt.day   # ← neu
```

- Kleinste Änderung, löst den unmittelbaren Bug
- `get_metadata()` muss `"day_of_month"` in `derived_features` ergänzen
- Nachteil: Step bleibt starr, künftige Feature-Wünsche (z.B. `year`, `quarter`) erzeugen erneut diesen Bug

**Option B — Flexibler `features`-Parameter:**

```python
param_schema = {
    "column": {"type": "string", "default": "dteday"},
    "features": {
        "type": "array",
        "default": ["weekday", "month"],
        "items": {"type": "string", "enum": ["weekday", "month", "day_of_month", "year", "quarter"]}
    }
}
```

Das LLM kann dann `"features": ["weekday", "month", "day_of_month"]` in die Spec schreiben. `_apply()` iteriert über die Liste.

- Vollständige Kontrolle für den Nutzer via natürliche Sprache
- Mehr Änderung: `param_schema` erweitern, `_apply()` umbauen, Capabilities reflektieren das automatisch, Tests updaten
- Kein Risiko für bestehende Specs (Default-Liste = bisheriges Verhalten)

**Frage an Hannes:** Option A (schneller Fix) oder Option B (flexibel und zukunftssicher)?

---

### Entscheidung 2 — Soll `drop_original` ein konfigurierbarer Parameter werden?

**Kontext:** `dteday` wird aktuell immer gelöscht. Der Nutzer hat keine Kontrolle darüber.

**Option A — Nein: Always-Drop bleibt, aber `description` macht es transparent:**

```python
description = "Leitet Zeitfeatures aus Datumsspalte ab und entfernt die Original-Spalte danach"
```

Das LLM weiß durch die Capabilities-`description`, dass das Drop stattfindet, und kann es in der `explanation` kommunizieren. Der User wird informiert, kann es aber nicht verhindern.

- Kleinstmögliche Änderung, kein neuer Parameter, kein Änderungsrisiko
- ML-Sinnvoll: `dteday` als Object-Spalte im Modell wäre problematisch
- Kein zusätzlicher Test nötig (bestehende Drop-Tests bleiben gültig)

**Option B — Ja: `drop_original: bool` Parameter (Default `True`):**

```python
param_schema = {
    "column": {"type": "string", "default": "dteday"},
    "drop_original": {"type": "boolean", "default": True}
}
```

```python
if self.params.get("drop_original", True):
    result = result.drop(columns=[self._column])
```

- Gibt dem Nutzer explizite Kontrolle
- `get_metadata()` sollte `drop_original` im Rückgabe-Dict widerspiegeln
- Bestehende Tests `test_transform_dteday_removed_from_train/test` bleiben korrekt (Default `True`)
- Neue Tests nötig: `drop_original=False` → `dteday` noch vorhanden

**Option C — Nein, und auch `description` bleibt wie sie ist:**

Scope minimal halten. Nur Problem A (day_of_month) fixen, B2 ignorieren.

**Frage an Hannes:** Option A (transparent but fixed), B (fully configurable) oder C (ignore B entirely)?

---

### Entscheidung 3 — Welcher Datensatz-Stand wird als Artefakt gespeichert?

**Kontext:** Analog zur Diskussion in Bug 1.4 Problem D. Der Step transformiert `df_full` (vor Split) oder `df_train`/`df_test` (nach Split). Was soll ins CSV?

**Option A — Post-Transform Zustand, je nach Pipeline-Kontext:**

- Vor Split: `df_full` nach Transformation → `{run_id}_time_features.csv`
- Nach Split: `df_train` nach Transformation → `{run_id}_time_features_train.csv`
- Einfachste Implementierung da der Step im `_apply()` den vollständigen Zustand kennt

**Option B — Immer beide: Transform-Train + Transform-Test (analog `split`):**

- Zwei CSVs: `{run_id}_time_features_train.csv` und `{run_id}_time_features_test.csv`
- Vollständiges Bild; aber: wenn noch kein Split erfolgt, gibt es kein `df_test`

**Option C — Implementierung für alle Preprocessing-Steps global in `BaseStep`:**

- Statt Step-spezifischem Override: `BaseStep.generate_artifact()` schreibt immer den aktuellen DataFrame-Zustand als CSV
- Vereinheitlicht das Verhalten für ALLE Preprocessing-Steps (löst gleichzeitig Bug 1.4 Problem D)
- Mehr Aufwand, größere Änderung, aber eliminiert die Inkonsistenz aus der Tabelle oben dauerhaft

**Frage an Hannes:** Option A (einfach), B (vollständig), oder C (global in BaseStep — löst auch Bug 1.4 D)?

---

### Entscheidung 4 — Soll das `ResultCard.tsx`-Frontend den `dropped_column`-Hinweis immer anzeigen?

**Kontext:** Nach dem Fix wird `get_metadata()` je nach Entscheidung 2 entweder immer `dropped_column: "dteday"` oder auch `drop_original: false` zurückgeben. Die `ResultCard`-Anzeige soll das korrekt reflektieren.

**Option A — Immer anzeigen wenn vorhanden:**

```
Abgeleitet: weekday, month, day_of_month | dteday entfernt
```

**Option B — Nur anzeigen wenn `drop_original=True` (d.h. `dropped_column`-Feld vorhanden):**

```
// drop_original=True:  "Abgeleitet: weekday, month, day_of_month | dteday entfernt"
// drop_original=False: "Abgeleitet: weekday, month, day_of_month"
```

**Option C — Immer anzeigen, auch wenn nicht gedroppt (als Hinweis auf Source-Spalte):**

```
Abgeleitet aus dteday: weekday, month, day_of_month
```

**Frage an Hannes:** Diese Entscheidung hängt direkt von Entscheidung 2 ab — kann parallel oder danach beantwortet werden.
