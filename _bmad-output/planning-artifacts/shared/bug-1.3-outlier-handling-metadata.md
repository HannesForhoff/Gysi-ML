# Bug 1.3 — `outlier_handling` Metadata: Typ-Mismatch und fehlende Bound-Informationen

**Status:** Analysiert, Fix ausstehend
**Schweregrad:** Mittel — Ausreißerbehandlung funktioniert korrekt, aber alle Rückmeldeinformationen gehen verloren
**Kategorie:** Backend (Step-Implementierung) + Frontend (ResultCard-Renderer)
**Analysiert von:** Amelia (Developer Agent), 2026-04-04

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| "Mache für `temp` outlier_handling mit method=iqr" | Anzeige: welche Spalte, wie viele Werte angepasst, auf welche Grenzen | Anzeige: `✓ outlier_handling — Ausreißer-Behandlung abgeschlossen.` |

Die Pipeline läuft durch, die Daten werden technisch korrekt geclipt — aber der Nutzer erhält **null Informationen** darüber, was konkret passiert ist.

---

## Technische Ursachenanalyse

Der Bug setzt sich aus **zwei unabhängigen, gekoppelten Problemen** zusammen.

---

### Problem A — Backend: `get_metadata()` liefert falschen Typ (Priorität: Hoch)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py`, Zeilen 25, 73–81

**Ist-Zustand:**

```python
# Zeile 25 — Initialisierung als int
self._outliers_treated: int = 0

# Zeile 73–77 — Akkumulation als int (alle Spalten summiert)
self._outliers_treated = total_treated  # ← ein einzelner int

# Zeile 80–81 — Rückgabe als int
def get_metadata(self) -> dict:
    return {"outliers_treated": self._outliers_treated}
    # Beispiel-Rückgabe: {"outliers_treated": 42}
```

**Was das Frontend erwartet (Problem B zeigt es):**

```tsx
// frontend/src/components/ResultCard.tsx, Zeile 36–40
const treated = m.outliers_treated
if (treated && typeof treated === 'object') {   // ← int ist kein object → IMMER false
    const entries = Object.entries(treated as Record<string, number>)
    ...
}
```

Das Frontend erwartet `outliers_treated` als `Record<string, number>` (Dict: Spaltenname → Anzahl behandelter Werte, z.B. `{"temp": 5, "windspeed": 0}`). Das Backend liefert aber einen einzelnen `int`. Der `typeof treated === 'object'`-Check schlägt deshalb **immer fehl**, und der Renderer fällt in den Fallback: `"Ausreißer-Behandlung abgeschlossen."`.

**Korrekte Ziel-Struktur für `outliers_treated`:**

```python
# Ziel: pro Spalte aufschlüsseln, Train und Test zusammen zählen
{"temp": 5, "hum": 0, "windspeed": 2, ...}
# statt: 7
```

Dies passt zum Muster anderer Steps im selben Codebase (z.B. `impute_missing` → `imputed_values_per_column: dict[str, int]`).

---

### Problem B — Frontend: `typeof treated === 'object'` schlägt bei `int` auch nach Fix fehl (Priorität: Niedrig, aber zu prüfen)

**Datei:** `frontend/src/components/ResultCard.tsx`, Zeilen 36–41

**Ist-Zustand:**

```tsx
case 'outlier_handling': {
  const treated = m.outliers_treated
  if (treated && typeof treated === 'object') {
    const entries = Object.entries(treated as Record<string, number>)
    if (entries.length === 0) return 'Keine Ausreißer behandelt.'
    return entries.map(([col, n]) => `${col}: ${n} Ausreißer`).join(', ')
  }
  return 'Ausreißer-Behandlung abgeschlossen.'
}
```

Nach dem Backend-Fix liefert `outliers_treated` ein `Record<string, number>`. Der `typeof treated === 'object'` Check wird dann korrekt `true`. **Dieser Teil ist nach dem Backend-Fix wahrscheinlich ohne Änderung korrekt funktionsfähig**, sofern kein leeres Objekt `{}` geliefert wird, wenn keine Ausreißer gefunden wurden. Das muss geprüft werden.

**Anzeigeformat nach dem Fix (angestrebt):**

```
✓ outlier_handling — temp: 5 Ausreißer, hum: 0 Ausreißer, windspeed: 2 Ausreißer
```

Oder alternativ: nur Spalten mit `n > 0` anzeigen:

```
✓ outlier_handling — temp: 5 Ausreißer, windspeed: 2 Ausreißer
```

→ Entscheidung erforderlich (siehe Offene Entscheidung C).

---

### Problem C — Backend: Quartil-/Bound-Informationen werden nicht zurückgegeben (Priorität: Mittel)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py`, Zeilen 26–36

**Ist-Zustand:** Die berechneten Grenzen sind intern gespeichert:

```python
# self._bounds wird in fit() befüllt (Zeile 27–36):
self._bounds[col] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)
# Beispiel: {"temp": (0.14, 0.74), "hum": (0.0, 1.0)}

# self._stats wird in fit() befüllt für zscore (Zeile 37–40):
self._stats[col] = (mean, std)
```

Diese Informationen werden in `get_metadata()` **nicht zurückgegeben**. Der Nutzer sieht weder die Quartilwerte noch die Clip-Grenzen.

**Ziel-Struktur (IQR-Methode):**

```python
def get_metadata(self) -> dict:
    return {
        "outliers_treated": {"temp": 5, "hum": 0, ...},   # neu: dict statt int
        "bounds": {
            "temp": {"lower": 0.14, "upper": 0.74, "q1": 0.34, "q3": 0.66},
            "hum": {"lower": 0.0, "upper": 1.0, "q1": 0.47, "q3": 0.77},
            ...
        }
    }
```

**Ziel-Struktur (Z-Score-Methode):**

```python
def get_metadata(self) -> dict:
    return {
        "outliers_treated": {"temp": 3, ...},
        "bounds": {
            "temp": {"lower": 0.12, "upper": 0.84, "mean": 0.50, "std": 0.19},
            ...
        }
    }
```

Das Frontend muss anschließend entscheiden, ob und wie `bounds` dargestellt wird (siehe Offene Entscheidung D).

---

## Betroffene Dateien (vollständig)

| Datei | Rolle | Änderung nötig | Begründung |
|---|---|---|---|
| `backend/src/gysi_ml/steps/preprocessing/outlier_handling.py` | Step-Implementierung | **Ja — Kern des Bugs** | `_outliers_treated` auf `dict[str, int]` umstellen; `_bounds`/`_stats` in `get_metadata()` zurückgeben |
| `frontend/src/components/ResultCard.tsx` | Step-Result-Renderer | **Ja — Anzeige erweitern** | Bounds-Anzeige ergänzen; Anzeige-Logik prüfen ob Filter `n > 0` gewünscht |
| `backend/tests/preprocessing/test_outlier_handling.py` | Unit-Tests | **Ja** | Tests für `get_metadata()` Rückgabetyp und Bounds-Inhalt erforderlich |
| `frontend/src/types.ts` | TypeScript-Typen | **Ggf.** | Nur wenn `StepResult.metadata` stärker typisiert wird — derzeit `any`/`dict`, kein Handlungsbedarf |
| `backend/src/gysi_ml/core/capabilities.py` | LLM-Capabilities | **Nein** | Kein neuer Parameter im `param_schema` — kein Einfluss auf LLM-Prompt |

---

## Änderungsdetails Backend

### `outlier_handling.py` — `__init__`

**Alt:**

```python
self._outliers_treated: int = 0
```

**Neu:**

```python
self._outliers_treated: dict[str, int] = {}
```

---

### `outlier_handling.py` — `transform()` (IQR-Branch)

**Alt (Zeilen 51–62):**

```python
total_treated = 0
# ...
total_treated += int(...)
# ...
self._outliers_treated = total_treated
```

**Neu:** Pro Spalte akkumulieren:

```python
# _outliers_treated als dict initiieren/befüllen:
for col, (lower, upper) in self._bounds.items():
    if col not in result_train.columns:
        continue
    n = int(
        ((result_train[col] < lower) | (result_train[col] > upper)).sum()
    ) + int(
        ((result_test[col] < lower) | (result_test[col] > upper)).sum()
    )
    self._outliers_treated[col] = n
    result_train[col] = result_train[col].clip(lower=lower, upper=upper)
    result_test[col] = result_test[col].clip(lower=lower, upper=upper)
```

Analog für `zscore`-Branch.

---

### `outlier_handling.py` — `get_metadata()`

**Alt (Zeilen 80–81):**

```python
def get_metadata(self) -> dict:
    return {"outliers_treated": self._outliers_treated}
```

**Neu:**

```python
def get_metadata(self) -> dict:
    metadata: dict = {"outliers_treated": self._outliers_treated}
    if self.method == "iqr" and self._bounds:
        metadata["bounds"] = {
            col: {"lower": round(lo, 4), "upper": round(hi, 4)}
            for col, (lo, hi) in self._bounds.items()
        }
    elif self.method == "zscore" and self._stats:
        metadata["bounds"] = {
            col: {
                "lower": round(mean - self.zscore_threshold * std, 4),
                "upper": round(mean + self.zscore_threshold * std, 4),
                "mean": round(mean, 4),
                "std": round(std, 4),
            }
            for col, (mean, std) in self._stats.items()
        }
    return metadata
```

> ⚠️ **Hinweis:** Ob Q1/Q3 selbst auch in `bounds` zurückgegeben werden sollen (nicht nur lower/upper), ist offen — siehe Entscheidung D.

---

## Änderungsdetails Frontend

### `ResultCard.tsx` — `case 'outlier_handling'` (Zeilen 35–41)

Nach Backend-Fix wird `treated` ein `Record<string, number>`. Der bestehende `typeof treated === 'object'`-Check greift dann. Folgende Anpassungen sind dennoch sinnvoll:

1. **Filter** — Entscheidung, ob Spalten mit `n === 0` angezeigt werden (Entscheidung C)
2. **Bounds-Anzeige** — Ob/wie `m.bounds` dargestellt wird (Entscheidung D)

Beispiel für erweiterten Renderer (nach Entscheidung):

```tsx
case 'outlier_handling': {
  const treated = m.outliers_treated
  if (treated && typeof treated === 'object') {
    const entries = Object.entries(treated as Record<string, number>)
      .filter(([, n]) => n > 0)  // nur Spalten mit Ausreißern (Option B, Entscheidung C)
    if (entries.length === 0) return 'Keine Ausreißer gefunden.'
    return entries.map(([col, n]) => `${col}: ${n} Ausreißer`).join(', ')
  }
  return 'Ausreißer-Behandlung abgeschlossen.'
}
```

---

## Offene Entscheidungen — müssen vor dem Fix beantwortet werden

Diese Punkte **dürfen beim Fixen nicht vergessen** werden. Der Dev-Agent muss Hannes vor der Implementierung fragen:

### Entscheidung A — `total_treated` als Gesamtzahl zusätzlich behalten?

Soll `get_metadata()` neben dem pro-Spalten-Dict `outliers_treated` auch eine Gesamtzahl zurückgeben?

- **Option 1:** Nur das Dict `{"temp": 5, "hum": 0}` — keine Gesamtzahl
- **Option 2:** Dict + Gesamtzahl: `{"outliers_treated": {"temp": 5}, "total_outliers_treated": 5}`

> **Empfehlung:** Option 1 — die Gesamtzahl ist trivial aus dem Dict berechenbar (im Frontend summierbar), unnötige Redundanz vermeiden.

---

### Entscheidung B — Werden Train und Test bei `outliers_treated` separat ausgewiesen?

Aktuell werden Train- und Test-Ausreißer summiert. Sollen sie separat zurückgegeben werden?

- **Option 1:** Summe Train+Test pro Spalte (einfacher, bisheriger Intent)
- **Option 2:** Getrennte Counts: `{"temp": {"train": 4, "test": 1}}`

> **Empfehlung:** Option 1 — der Nutzer braucht diese Unterscheidung nicht für eine verständliche Übersicht.

---

### Entscheidung C — Frontend: Spalten mit `n === 0` anzeigen oder filtern?

Wenn 15 Spalten behandelt wurden, aber nur 2 tatsächlich Ausreißer hatten:

- **Option A:** Alle Spalten anzeigen: `temp: 5 Ausreißer, hum: 0 Ausreißer, windspeed: 2 Ausreißer, ...`
- **Option B:** Nur Spalten mit `n > 0` anzeigen: `temp: 5 Ausreißer, windspeed: 2 Ausreißer`
- **Option C:** Zusammenfassung: `2 von 15 Spalten betroffen (7 Ausreißer gesamt)`

> **Empfehlung:** Option B — klarer und weniger Rauschen. Bei null Ausreißern: "Keine Ausreißer gefunden."

---

### Entscheidung D — Bounds/Quartile im Frontend anzeigen?

Das Backend berechnet und (nach Fix) liefert die Clip-Grenzen (`lower`, `upper`). Soll das Frontend diese darstellen?

- **Option 1:** Grenzen **nicht** anzeigen — nur Anzahl behandelter Werte (minimal)
- **Option 2:** Grenzen **anzeigen**, z.B. `temp: 5 Ausreißer [Grenzen: 0.14 – 0.74]`
- **Option 3:** Grenzen nur auf Anfrage / in einem Detail-Bereich (Tooltip o.ä.)

> **Empfehlung:** Option 2 — das war der ursprüngliche Wunsch des Nutzers ("welche Werte haben die Quartile"). Ohne diese Info ist das Metadata-Feature wenig nützlich.

---

### Entscheidung E — Q1/Q3-Werte in Bounds mit zurückgeben? (Nur IQR)

Bei `method=iqr` könnte `bounds` zusätzlich Q1 und Q3 enthalten:

```python
{"temp": {"lower": 0.14, "upper": 0.74, "q1": 0.34, "q3": 0.66}}
# vs. nur:
{"temp": {"lower": 0.14, "upper": 0.74}}
```

- **Option 1:** Nur `lower`/`upper` (die tatsächlichen Clip-Grenzen)
- **Option 2:** `lower`, `upper`, `q1`, `q3` (vollständige IQR-Diagnostik)

> **Empfehlung:** Option 2 — Q1/Q3 geben dem Nutzer ein besseres Verständnis der Datenverteilung und kosten nichts.

---

## Hinweise für den Dev-Agent beim Implementieren

1. **Kein Leakage:** Die `fit()`-Methode berechnet Bounds ausschließlich auf `df_train`. `df_test` wird niemals für Bound-Berechnung verwendet. Daran darf der Fix nichts ändern.
2. **`total_treated` Variable entfernen:** Die lokale Variable `total_treated: int = 0` in `transform()` kann nach dem Umbau auf Dict entfallen. Kein separater Akkumulator mehr nötig.
3. **Beide Branches anpassen:** Sowohl `iqr`-Branch als auch `zscore`-Branch in `transform()` müssen auf das Dict-Muster umgestellt werden.
4. **Tests:** Bestehende Tests für `outlier_handling` prüfen (falls vorhanden), ob sie `outliers_treated` als `int` erwarten — diese Tests brechen nach dem Fix und müssen angepasst werden.
5. **Frontend-Typ-Sicherheit:** `m` in `formatStepResult` ist `any`-typed. Kein TypeScript-Fehler zu erwarten, aber der Dev-Agent soll das nicht stärker typisieren als nötig — nur die Render-Logik anpassen.
