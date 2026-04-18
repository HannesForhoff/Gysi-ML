# Bug 1.4 — `rare_category_bucketing`: Numerisch-typisierte Kategorien werden nie verarbeitet

**Status:** Analysiert, Fix ausstehend
**Schweregrad:** Hoch — Schritt ist für den primären Anwendungsfall des Bike-Datensatzes vollständig wirkungslos
**Kategorie:** Backend (Step-Implementierung) + Frontend/LLM (UX — irreführende Rückmeldung)
**Analysiert von:** Amelia (Developer Agent), 2026-04-04

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| "führe in weathersit ein rare_category_bucketing mit min_frequency=0.01 durch" | `weathersit=4` (3×, 0.017%) wird als `__rare__` gebündelt | "Keine seltenen Kategorien gefunden." — kein Eingriff |
| "führe in holiday ein rare_category_bucketing mit min_frequency=0.01 durch" | `holiday=1` (500×, 2.9%) korrekt NICHT gebündelt; aber Schritt läuft durch | "Keine seltenen Kategorien gefunden." — kein Eingriff |

Die Pipeline läuft ohne Fehler durch. Der Step tut schlicht nichts. Der Nutzer bekommt eine widersprüchliche Rückmeldung (LLM sagt "durchgeführt", Step-Ergebnis sagt "nichts gefunden").

---

## Technische Ursachenanalyse

Dieser Bug setzt sich aus **drei ineinandergreifenden Problemen** zusammen.

---

### Problem A — Backend: `select_dtypes`-Guard schließt alle numerischen Spalten aus (Priorität: Kritisch)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/rare_category.py`, Zeilen 17–23

**Ist-Zustand:**

```python
def fit(self, df_train: pd.DataFrame) -> None:
    cat_cols = df_train.select_dtypes(include=["object", "category", "string"]).columns
    #                                           ↑ nur String-Dtypes
    self._rare_categories = {}
    for col in cat_cols:
        ...
```

**Das Problem:**

Im Bike-Datensatz (`data/raw/bikes.csv`) sind alle kategorischen Spalten als numerische Typen gespeichert:

| Spalte | Dtype | Beispielwerte |
|---|---|---|
| `weathersit` | `float64` | 1.0, 2.0, 3.0, 4.0 |
| `holiday` | `int64` | 0, 1 |
| `season` | `int64` | 1, 2, 3, 4 |
| `yr` | `int64` | 0, 1 |
| `mnth` | `float64` | 1.0 – 12.0 |

`select_dtypes(include=["object", "category", "string"])` findet **keine dieser Spalten**. Das `_rare_categories`-Dict bleibt leer. `transform()` tut daher nichts. Der Step ist für den gesamten Bike-Datensatz ein vollständiges No-Op.

**Konkrete Fakten (verifiziert):**

```
weathersit value_counts:
  1.0 → 8711  (50.1%)
  2.0 → 3427  (19.7%)
  3.0 → 1068  ( 6.1%)
  4.0 →    3  ( 0.017%)  ← mit min_frequency=0.01 (1%) → SOLLTE gebündelt werden

holiday value_counts:
  0 → 16879  (97.1%)
  1 →   500  ( 2.877%)  ← korrekt: >1%, NICHT selten

Gesamt: 17.379 Zeilen
```

`weathersit=4` ist eindeutig ein Kandidat: 0.017% liegt weit unter der 1%-Schwelle. Der Schritt greift ihn nie an weil `float64 ∉ {"object", "category", "string"}`.

---

### Problem B — Backend: Kein `columns`-Parameter im Schema (Priorität: Mittel)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/rare_category.py`, Zeile 11

**Ist-Zustand:**

```python
param_schema = {"min_frequency": {"type": "number", "default": 0.01}}
```

Der Step kennt keinen `columns`-Parameter. Wenn der Nutzer sagt "führe in *weathersit* ein rare_category_bucketing durch", kann das LLM diese Spaltenangabe **nicht als Parameter** weitergeben. Der Step operiert immer auf allen Spalten die der Dtype-Guard durchlässt — der kann nie auf eine einzelne Spalte beschränkt werden.

Im Vergleich dazu: `outlier_handling` hat ebenfalls keinen expliziten `columns`-Parameter und läuft über alle numerischen Spalten. Das ist aber dort explizit so gewollt. Bei `rare_category_bucketing` ist die Nutzer-Intent klar spaltenspezifisch.

**Auswirkung (nach Fix von Problem A):**
Nach dem Dtype-Fix würde der Step alle numerischen Spalten des Datensatzes prüfen — also `season`, `yr`, `mnth`, `hr`, `weathersit`, `holiday` etc. In `weathersit` würde dann Wert `4.0` korrekt gebündelt. Aber ohne `columns`-Parameter kann der Nutzer nicht gezielt einzelne Spalten steuern.

---

### Problem C — LLM-Explanation ist vor Ausführung generiert (Priorität: Niedrig-Mittel)

**Sichtbar im UI:**

```
Ergebnis
Ich habe ein Rare Category Bucketing für die Spalte 'weathersit' mit einer minimalen
Häufigkeit von 0.01 durchgeführt. Seltene Kategorien wurden in die neue Kategorie
'__rare__' zusammengefasst, was dazu beiträgt ...
              ↑ faktisch falsch — es wurde NICHTS zusammengefasst

✓ rare_category_bucketing — Keine seltenen Kategorien gefunden.
              ↑ korrekt — aus Frontend-Renderer via get_metadata()
```

**Ursache:**

Das LLM generiert das `explanation`-Feld im `LLM_RESPONSE_SCHEMA` **vor der Ausführung der Pipeline**. Es kann das Ergebnis nicht kennen und formuliert eine optimistisch-antizipatorische Erklärung. Die korrekte Step-Information ("Keine seltenen Kategorien gefunden.") kommt aus dem Frontend-Renderer über `get_metadata()` — diese Information ist korrekt, aber sie widerspricht der LLM-Erklärung darüber.

**Nutzer-Wunsch (aus Bug-Bericht):** Das System soll bei "nichts gefunden" vorschlagen, `min_frequency` anzupassen. Das ist nach der aktuellen Architektur nicht trivial, da das LLM die Ergebnis-Metadata nicht erhält.

---

### Problem D — Unit-Tests haben blinden Fleck für numerische Spalten (Priorität: Mittel)

**Datei:** `backend/tests/unit/preprocessing/test_rare_category.py`

Alle vorhandenen Tests verwenden ausschließlich `object`-typisierte Spalten (Strings: `"red"`, `"blue"`, `"rare_green"`). Der Dtype-Guard wird in keinem Test mit `int64`/`float64` konfrontiert. Die Tests geben fälschlicherweise grünes Licht — der Step scheint korrekt, ist es aber für den realen Datensatz nicht.

```python
# Alle bestehenden Fixtures:
df = pd.DataFrame({"color": ["red"] * 8 + ["blue"] * 4, ...})  # object-dtype
# ← nie getestet:
df = pd.DataFrame({"weathersit": [1, 1, 2, 2, 3, 4]})  # int64-dtype
```

---

## Betroffene Dateien

| Datei | Rolle | Änderung nötig | Begründung |
|---|---|---|---|
| `backend/src/gysi_ml/steps/preprocessing/rare_category.py` | Step-Implementierung | **Ja — Kern des Bugs** | `select_dtypes`-Guard um numerische Typen erweitern; ggf. `columns`-Parameter ergänzen |
| `backend/tests/unit/preprocessing/test_rare_category.py` | Unit-Tests | **Ja** | Testfälle mit `int64`/`float64` Spalten ergänzen |
| `frontend/src/components/ResultCard.tsx` | Step-Result-Renderer | **Ggf.** | Nur bei Entscheidung zu Problem C (Vorschlag bei Null-Ergebnis) |
| `backend/src/gysi_ml/core/capabilities.py` | LLM-Capabilities | **Ggf.** | Nur wenn `columns`-Parameter in `param_schema` ergänzt wird |

---

## Offene Entscheidungen — vor dem Fix zu klären

### Entscheidung A — Welche Dtypes soll der Step berücksichtigen?

Der Fix für Problem A muss definieren, auf welche Spalten-Typen der Step angewendet wird.

- **Option 1:** Nur `int64` und `float64` zusätzlich aufnehmen
  ```python
  cat_cols = df_train.select_dtypes(include=["object", "category", "string", "int64", "float64"]).columns
  ```
  → Klar und explizit. Deckt den Bike-Datensatz vollständig ab. Risiko: Spalten wie `cnt` (Zielvariable) oder `temp` (kontinuierlich) könnten fälschlich einbezogen werden wenn kein `columns`-Filter vorhanden ist.

- **Option 2:** Alle nicht-float-kontinuierlichen Spalten — heuristisch via Kardinalität
  ```python
  # Nur Spalten mit ≤ N distinct values als "kategorisch" behandeln
  ```
  → Komplizierter, fehleranfällig. Nicht empfohlen.

- **Option 3 (empfohlen):** `columns`-Parameter einführen + Dtype-Guard entfernen
  ```python
  param_schema = {
      "min_frequency": {"type": "number", "default": 0.01},
      "columns": {"type": "array", "items": {"type": "string"}, "default": []}
  }
  # Wenn columns leer: alle object/category/string/int64-Spalten
  # Wenn columns gesetzt: nur diese Spalten
  ```
  → Nutzer-Intent ("in weathersit") wird korrekt umgesetzt. Keine Seiteneffekte auf `cnt`/`temp` etc.

> **Empfehlung:** Option 3 — löst gleichzeitig Problem A und Problem B.

---

### Entscheidung B — Problem C: Vorschlag bei Null-Ergebnis

Wenn `rare_categories_per_column` nach Ausführung leer ist oder alle Werte 0: Soll das System proaktiv vorschlagen, `min_frequency` zu senken?

- **Option 1:** Kein Eingriff — "Keine seltenen Kategorien gefunden." ist ausreichend
- **Option 2 (empfohlen):** Frontend-Renderer erweitern — bei leerem Ergebnis einen Hinweistext zeigen:
  ```
  ✓ rare_category_bucketing — Keine seltenen Kategorien gefunden.
    Hinweis: Mit min_frequency=0.001 würden möglicherweise weitere Kategorien erkannt.
  ```
  Dieser Hinweis würde statisch angezeigt (kein LLM-Call) wenn das Ergebnis leer ist.

- **Option 3:** LLM erhält Step-Ergebnis als Rückmeldung für folgende Nachrichten (Architektur-Änderung) — Aufwand hoch, aktuell nicht im Scope.

> **Empfehlung:** Option 2 — kostengünstig, kein neuer LLM-Call, beantwortet den Nutzer-Wunsch direkt.

---

## Hinweise für den Dev-Agent beim Implementieren

1. **Kein Leakage:** `fit()` berechnet Schwellenwerte nur auf `df_train`. Das darf der Fix nicht ändern.
2. **`transform()`-Guard prüfen:** Die bestehende `if col not in result_train.columns or not rare_cats: continue`-Zeile schützt vor leeren Sets — bleibt unverändert.
3. **Tests zuerst aktualisieren:** Neuen Test mit `int64`-Spalte schreiben der **vor** dem Fix rot und **nach** dem Fix grün ist — als Regressions-Anker.
4. **Kontinuierliche Spalten schützen:** Wenn `columns`-Parameter nicht eingeführt wird, muss verhindert werden dass `temp`, `atemp`, `hum`, `windspeed`, `cnt` processiert werden (alle float64, aber kontinuierlich, nicht kategorisch). Mit `columns`-Parameter ist das Problem selbst lösend.
5. **Kein `param_schema`-Breaking-Change ohne LLM-Capabilities-Update**: Wenn `columns` neu eingeführt wird, muss `capabilities.py` kein Update erhalten (da `get_capabilities()` dynamisch aus `param_schema` liest) — das LLM erhält den neuen Parameter automatisch.
