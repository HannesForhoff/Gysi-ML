# Bug 1.9 — `outlier_handling`: Drei gekoppelte Probleme (columns-Parameter, Schema-Beschreibung, Binär-Warnung)

**Gefunden**: 2026-04-15
**Status**: Dokumentiert, Entscheidung getroffen, Fix ausstehend
**Priorität**: 🟠 Hoch (Step läuft, aber ignoriert Nutzerwille und produziert irreführende Ausgaben)
**Kategorie**: Backend — `steps/preprocessing/outlier_handling.py` + `llm/prompts.py`

---

## Beobachtetes Fehlverhalten

### Fehlverhalten A — LLM erzeugt keine gültige Aktion bei "IQR-Methode"

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
| --- | --- | --- |
| "Führe ein Outlier-Handling mit IQR-Methode durch" | `outlier_handling` mit `method="iqr"` wird ausgeführt | `"Das Sprachmodell konnte keine gültige Aktion erzeugen."` |

Das LLM erkennt den Nutzerbegriff "IQR-Methode" + "Winzorization" nicht sicher als Mappings
zu den Schema-Werten `"iqr"` / `"zscore"`. Da das `param_schema` keine `description` für
die `method`-Werte enthält, ist das Mapping Nutzerbegriff → Enum-Wert komplett dem LLM überlassen.

### Fehlverhalten B — `columns`-Parameter fehlt, alle numerischen Spalten werden behandelt

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
| --- | --- | --- |
| "Führe eine Winzorization für cnt durch" | Nur `cnt` wird behandelt | Alle numerischen Spalten werden behandelt |

**Ausgabe im Chat:**

```
✓ outlier_handling
holiday: 500 Ausreißer [0 – 0], weathersit: 4498 Ausreißer [1 – 1],
hum: 22 Ausreißer [0.5 – 124.5], cnt: 488 Ausreißer [-323 – 645]
```

Der Nutzer bat um Behandlung von `cnt` — 3 weitere Spalten wurden still verändert.

### Fehlverhalten C — Irreführende Ausgabe für binäre / kategorische Spalten

`holiday: 500 Ausreißer [0 – 0]` und `weathersit: 4498 Ausreißer [1 – 1]`:

- `holiday` ist eine binäre Spalte (0/1): IQR = 0 → untere Bound = Q1 - 1.5×0 = 0, obere Bound = Q3 + 1.5×0 = 0.
  → Alle Werte ≠ 0 gelten als "Ausreißer" — fachlich komplett falsch.
- `weathersit` ist eine ordinale Kategorie (1–4): IQR ≈ 0 → ähnliches Problem.

Der Nutzer sieht `4498 Ausreißer` in weathersit und `500 Ausreißer` in holiday und denkt,
da stimme etwas grundlegend nicht. Tatsächlich ist der IQR-Algorithmus für diese Spalten
schlicht nicht angemessen.

---

## Technische Ursachenanalyse

### Problem A — Kein `description`-Feld im `method`-Parameter

**Datei:** `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py`

**Ist-Zustand:**

```python
param_schema = {
    "method": {
        "type": "string",
        "enum": ["iqr", "zscore"],
        "default": "iqr",
    },
    "zscore_threshold": {"type": "number", "default": 3.0},
}
```

Das LLM sieht im System-Prompt nur `"enum": ["iqr", "zscore"]`. Nutzerbegriffe wie
"IQR-Methode", "Winzorization", "Winsorization", "Z-Score-Methode", "Standardabweichung" sind
sprachliche Varianten, die ohne Beschreibung nicht sicher gemappt werden können.

**Fix:** `description`-Felder ergänzen:

```python
"method": {
    "type": "string",
    "enum": ["iqr", "zscore"],
    "default": "iqr",
    "description": (
        "Ausreißer-Erkennungsmethode. "
        "'iqr' = IQR-Methode / Winzsorizierung / Winsorization: Capping auf [Q1-1.5×IQR, Q3+1.5×IQR]. "
        "'zscore' = Z-Score / Standardabweichungs-Methode: Capping auf [µ-k×σ, µ+k×σ] (k = zscore_threshold)."
    ),
},
```

### Problem B — Kein `columns`-Parameter

**Datei:** `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py`

Die `fit()`-Methode iteriert immer über `df_train.select_dtypes(include="number").columns`
ohne Möglichkeit, dies zu überschreiben. Identisches Muster wie Bug 1.1 (Imputation) und
Bug 1.2 (Encoding — jeweils schon gefixt).

**Fix:** Gleiches Muster wie bei `ImputationStep`:

```python
param_schema = {
    ...,
    "columns": {
        "type": "array",
        "items": {"type": "string"},
        "default": [],
        "description": "Numerische Spalten die behandelt werden sollen. Leer = alle numerischen Spalten.",
    },
}
```

In `__init__`: `self._columns: list[str] = list(self.params.get("columns") or [])`

In `fit()`:

```python
numeric_cols = df_train.select_dtypes(include="number").columns.tolist()
if self._columns:
    non_existent = [c for c in self._columns if c not in df_train.columns]
    if non_existent:
        raise ValueError(f"outlier_handling: Spalten nicht gefunden: {non_existent}")
    non_numeric = [c for c in self._columns if c not in numeric_cols]
    if non_numeric:
        raise ValueError(f"outlier_handling: Nicht-numerische Spalten: {non_numeric}")
    target_cols = list(self._columns)
else:
    target_cols = numeric_cols
```

### Problem C — Kein Schutz vor binären / low-variance Spalten

**Datei:** `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py`

Wenn `IQR = 0` ist (binäre oder konstante Spalten), sind die Bounds identisch
(`[Q1, Q3]` = gleicher Wert), und praktisch alle Werte werden als Ausreißer klassifiziert.

**Fix:** In `fit()` eine IQR-Null-Prüfung einbauen:

```python
for col in target_cols:
    q1 = float(df_train[col].quantile(0.25))
    q3 = float(df_train[col].quantile(0.75))
    iqr = q3 - q1
    if iqr == 0:
        # Spalte hat keine Varianz oder ist binär/konstant → überspringen
        self._skipped_cols[col] = "IQR=0 (binäre oder konstante Spalte)"
        continue
    self._bounds[col] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)
    self._q1q3[col] = (q1, q3)
```

`get_metadata()` gibt `skipped_columns`-Feld zurück wenn `_skipped_cols` nicht leer ist.

**Frontend-Anzeige** in `ResultCard.tsx` soll Spalten mit `iqr=0` als hinweis anzeigen:

```
✓ outlier_handling — cnt: 488 Ausreißer [-323 – 645]
  ℹ holiday, weathersit: übersprungen (IQR=0, nicht für Outlier-Handling geeignet)
```

---

## Betroffene Dateien

| Datei | Änderung |
| --- | --- |
| `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py` | `columns`-Parameter, `description` für `method`, IQR=0-Guard |
| `frontend/src/components/ResultCard.tsx` | Anzeige für `skipped_columns` |
| `backend/tests/unit/preprocessing/test_outlier_handling.py` | Tests für `columns`, IQR=0-Warnung |

---

## Getroffene Entscheidungen

- **Problem A**: `description`-Felder im `param_schema` ergänzen (alle Nutzervarianten abdecken)
- **Problem B**: `columns`-Parameter nach gleichem Muster wie Bug 1.1/1.2 implementieren
- **Problem C**: IQR=0-Guard + `skipped_columns`-Metadata + Frontend-Hinweis

---

## Offene Entscheidungen

Keine — alle drei Teilprobleme sind vollständig spezifiziert.

---

## Dringlichkeit

🟠 Hoch — Three issues in einem Step:
1. Step schlägt bei natürlichen Formulierungen ("IQR-Methode") komplett fehl
2. Nutzerwille (spaltenspezifisch) wird ignoriert
3. Irreführende Ausgabe erweckt den Eindruck von Datenfehlern
