# Bug 1.8 — DataLoader: `windspeed` wird als String eingelesen (ein `'-'`-Sentinel)

**Gefunden**: 2026-04-15
**Status**: Dokumentiert, Entscheidung getroffen, Fix ausstehend
**Priorität**: 🔴 Kritisch (Kernfunktionen wie Imputation schlagen bei windspeed fehl)
**Kategorie**: Backend — `utils/data_loader.py`

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
| --- | --- | --- |
| "Imputiere fehlende Werte in der Spalte windspeed mit dem Median" | `windspeed: 1 Wert(e) ersetzt` | Fehlermeldung: `Imputation: Nicht-numerische Spalten können nicht imputiert werden: ['windspeed']` |

**Ausgabe im Chat:**

```
Imputation: Nicht-numerische Spalten können nicht imputiert werden: ['windspeed'].
Verfügbare numerische Spalten: ['atemp', 'cnt', 'holiday', 'hr', 'hum', 'mnth',
'season', 'temp', 'weathersit', 'yr']
```

---

## Technische Ursachenanalyse

### Root Cause — Eine einzige fehlerhafte Datenzelle

**Verifiziert mit:**

```python
df = pd.read_csv("data/raw/bikes.csv")
print(df["windspeed"].dtype)   # → str
non_num = df[pd.to_numeric(df["windspeed"], errors="coerce").isna()]["windspeed"].unique()
print(non_num)                 # → ['-']   (genau 1 Wert)
```

**Befund:** Die gesamte `windspeed`-Spalte (17.379 Zeilen) hat als `dtype` `str`, weil genau
**eine Zelle den Wert `'-'`** (ein ASCII-Bindestrich) enthält. Dieser Wert ist vermutlich ein
ursprünglicher Excel/CSV-Platzhalter für fehlende Werte (N/A-Sentinel).

Pandas wählt den Dtype einer Spalte anhand aller Werte. Weil `'-'` nicht zu `float64`
konvertierbar ist, liest pandas die **gesamte** Spalte als `StringDtype` ein — auch wenn alle
anderen ~17.378 Werte technisch Zahlen sind (`'0.0'`, `'0.1697'` etc., als Strings gespeichert).

### Kausalkette

```
bikes.csv hat eine Zelle: windspeed = '-'
    ↓
pd.read_csv() kann '-' nicht als float parsen
    ↓
windspeed-Spalte wird als StringDtype eingelesen
    ↓
ImputationStep.fit(): select_dtypes(include="number") findet windspeed nicht
    ↓
Strict-Validierung aus Bug-1.1-Fix: "Nicht-numerische Spalten können nicht imputiert werden"
    ↓
Fehlermeldung für Nutzer obwohl windspeed faktisch numerisch ist
```

### Betroffene Datei

`backend/src/gysi_ml/utils/data_loader.py`

**Ist-Zustand:**

```python
def load_bikes_dataset(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep=",", header=0)
```

Kein `na_values`-Parameter → `'-'` wird als String-Wert interpretiert, nicht als NaN.

---

## Getroffene Entscheidung

**Option A + Winston's Defensiv-Erweiterung** (beschlossen in Party-Mode-Session 2026-04-15)

### Fix-Plan

**Schritt 1 — `na_values` erweitern:**

Pandas-eigene Erkennung von N/A-Sentinel-Werten ist zu eng. Wir übergeben ein breites
Set gängiger Platzhalter:

```python
_EXTRA_NA_VALUES = ["-", "NA", "N/A", "n/a", "na", "?", ""]
```

Damit wird `'-'` beim Laden direkt zu `NaN` konvertiert. Da die restlichen `windspeed`-Werte
echte Floats sind, wählt pandas automatisch `float64` als Dtype.

**Schritt 2 — `convert_dtypes()` nach dem Laden:**

Um gegen ähnliche Probleme bei anderen Spalten oder zukünftigen Datensätzen abgesichert
zu sein, rufen wir nach dem Laden `df.convert_dtypes()` auf. Pandas konvertiert dabei
alle Spalten in den engstmöglichen Nullable-Dtype:

- Spalten die faktisch numerisch sind → `Float64` / `Int64`
- Spalten mit echten Strings → `StringDtype`

**Achtung:** `convert_dtypes()` verändert u.U. Dtypes bestehender Spalten. Alle Steps
die `select_dtypes(include="number")` verwenden, müssen mit `Float64`/`Int64` (nullable)
kompatibel sein — das ist in pandas mit numpy-funcions standardmäßig der Fall.

**Resultat-Implementierung:**

```python
_EXTRA_NA_VALUES = ["-", "NA", "N/A", "n/a", "na", "?", ""]

def load_bikes_dataset(path: str) -> pd.DataFrame:
    """Lädt das Bike-Dataset als DataFrame.

    Defensive Ladelogik:
    - na_values: breites Set gängiger Sentinel-Werte (z.B. '-' in windspeed)
    - convert_dtypes(): konvertiert alle Spalten in engstmögliche Nullable-Typen
      → schützt vor String-Dtypes bei faktisch numerischen Spalten
    """
    df = pd.read_csv(path, sep=",", header=0, na_values=_EXTRA_NA_VALUES,
                     keep_default_na=True)
    return df.convert_dtypes()
```

### Auswirkung auf bestehende Steps

| Step | Kompatibel nach Fix? | Anmerkung |
| --- | --- | --- |
| `ImputationStep` | ✅ | `select_dtypes(include="number")` erfasst `Float64` |
| `OutlierHandlingStep` | ✅ | `select_dtypes(include="number")` erfasst `Float64` |
| `CorrelationFilterStep` | ✅ | `df.corr()` funktioniert mit nullable types |
| `RareCategoryBucketingStep` | ✅ | Nur String-Dtypes ohne columns-Param |
| `CategoricalEncodingStep` | ✅ | Nur object/category/string-Dtypes |
| `TimeFeatureEncodingStep` | ✅ | Nur datetime-Konversion |
| `SplitStep` | ✅ | Nur row-level Operationen |

### Betroffene Tests

`backend/tests/unit/` — die Fixtures in `test_imputation.py` etc. verwenden eigene minimale
DataFrames und sind nicht vom DataLoader abhängig. **Kein Änderungsbedarf an bestehenden Tests.**

Neuer Test in `backend/tests/unit/utils/test_data_loader.py` (muss ggf. erstellt werden):

```python
def test_windspeed_loaded_as_numeric(tmp_path):
    """'-' in windspeed wird als NaN erkannt, Spalte hat numerischen Dtype."""
    csv = tmp_path / "bikes.csv"
    csv.write_text("windspeed,cnt\n0.1,500\n-,300\n0.3,200\n")
    df = load_bikes_dataset(str(csv))
    assert pd.api.types.is_numeric_dtype(df["windspeed"])
    assert df["windspeed"].isna().sum() == 1   # '-' → NaN

def test_no_string_dtypes_for_numeric_columns(data_path):
    """Nach dem Laden hat keine faktisch-numerische Spalte StringDtype."""
    df = load_bikes_dataset(data_path)
    for col in ["windspeed", "temp", "hum", "cnt"]:
        assert pd.api.types.is_numeric_dtype(df[col]), f"{col} ist nicht numerisch"
```

---

## Offene Entscheidungen

Keine — Fix-Strategie vollständig definiert.

---

## Dringlichkeit

🔴 Kritisch — Der häufigste Explorations-Use-Case ("Imputiere windspeed") schlägt fehl.
Nutzer erhält eine technische Fehlermeldung die den Eindruck erweckt,
`windspeed` sei prinzipiell nicht imputierbar. Einzeilige CSV-Anomalie
blockiert die Kernfunktion.
