# Bug 1.2 — `encode_categorical` ignoriert angeforderte Zielspalte

**Status:** Analysiert, Fix ausstehend
**Schweregrad:** Hoch — Nutzerwille wird vollständig ignoriert, falsche Spalten werden verändert
**Kategorie:** Backend — Step-Implementierung + LLM-Schema
**Analysiert von:** Amelia (Developer Agent), 2026-04-04
**Korrelation:** Siehe Bug 1.1 (gemeinsamer Abschnitt unten)

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| "Mach ein One-Hot-Encoding für `weathersit`" | Nur `weathersit` wird encodet | `dteday` und `windspeed` werden encodet, `weathersit` nicht |
| "Mache ein OneHot Encoding für `windspeed`" | Nur `windspeed` wird encodet | `dteday` und `windspeed` werden encodet |

**Frontend-Anzeige** (ResultCard): `✓ encode_categorical — Kodiert: dteday, windspeed`

Der Nutzer sieht in beiden Fällen dasselbe falsche Ergebnis, unabhängig von der Ziel-Spalte.

---

## Technische Ursachenanalyse

### Ursache 1 — Kein `columns`-Parameter im `param_schema`

**Datei:** `backend/src/gysi_ml/steps/preprocessing/encoding.py`

Das `param_schema` definiert ausschließlich `method`:

```python
param_schema = {
    "method": {
        "type": "string",
        "enum": ["label", "onehot"],
        "default": "label",
    }
    # ← KEIN "columns"-Parameter vorhanden
}
```

`get_capabilities()` in `backend/src/gysi_ml/core/capabilities.py` rendert dieses Schema direkt in den LLM-System-Prompt (`capabilities_json`). Das LLM sieht daher keine Möglichkeit, eine Spalte zu übergeben. Selbst wenn das LLM trotzdem `"columns": ["weathersit"]` im JSON generieren würde, wird dieser Wert in `fit()` nie ausgelesen.

### Ursache 2 — `fit()` wählt Spalten ausschließlich per dtype-Autoerkennung

**Datei:** `backend/src/gysi_ml/steps/preprocessing/encoding.py`, Zeile 25

```python
def fit(self, df_train: pd.DataFrame) -> None:
    cat_cols = list(df_train.select_dtypes(include=["object", "category", "string"]).columns)
    self._encoded_columns = cat_cols
    # ...
```

Der Step wählt eigenständig **alle** Spalten mit `object`-, `category`- oder `string`-dtype — völlig unabhängig von dem, was der Nutzer wünscht. Es gibt keine Möglichkeit, dieses Verhalten zu überschreiben.

### Warum `dteday` immer auftaucht

`dteday` ist im `bike.csv` ein Datumsstring (`"2011-01-01"`) und wird von pandas als `object`-dtype eingelesen. Damit landet `dteday` **immer und zwingend** in `cat_cols` und wird bei **jedem** Aufruf von `encode_categorical` encodet — auch wenn der Nutzer es nicht verlangt hat und kein `extract_time_features`-Step vorher ausgeführt wurde.

### Warum `windspeed` unerwartet auftaucht (Session-State-Effekt)

`windspeed` ist im Original-CSV `float64` und würde **nicht** von `select_dtypes` erfasst. Das Auftauchen in den Ergebnissen ist ein **Folge-Effekt aus dem Session-State**: Ein vorheriger Step in der Session (z.B. `rare_category_bucketing`, `outlier_handling` oder ein anderes Encoding) hat `windspeed` in einen `category`- oder `object`-dtype umgewandelt. Da der Session-Kontext (`df_full` / `df_train`) zwischen Steps akkumuliert wird, erbt `encode_categorical` diesen veränderten Dtype.

Dieser Effekt ist **nicht deterministisch reproduzierbar** ohne die vollständige Session-Spec. Er tritt nur auf, wenn bestimmte Steps vorher ausgeführt wurden.

---

## Betroffene Dateien

| Datei | Rolle | Änderung nötig |
|---|---|---|
| `backend/src/gysi_ml/steps/preprocessing/encoding.py` | Step-Implementierung | **Ja** — Kern des Bugs |
| `backend/src/gysi_ml/llm/prompts.py` | LLM-System-Prompt | **Nein** — wird automatisch über `capabilities_json` aktualisiert |
| `backend/src/gysi_ml/core/capabilities.py` | Capabilities-Service | **Nein** — rendert Schema automatisch |
| `frontend/src/components/ResultCard.tsx` | Anzeige `Kodiert: ...` | **Nein** — liest `encoded_columns` korrekt, zeigt nur falsche Daten |
| `backend/tests/...` | Unit-Tests für Encoding-Step | **Ja** — Tests für `columns`-Parameter erforderlich |

---

## Fix-Strategie (Entscheidungen ausstehend — siehe unten)

Der Fix ist **minimal und chirurgisch** — nur `encoding.py` wird verändert:

**Schritt 1 — `param_schema` erweitern:**

```python
param_schema = {
    "method": {
        "type": "string",
        "enum": ["label", "onehot"],
        "default": "label",
    },
    "columns": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Liste der zu encodierenden Spalten. Wenn leer oder nicht angegeben: automatische Erkennung per dtype.",
        # default: None oder [] → Fallback-Verhalten
    }
}
```

**Schritt 2 — `fit()` anpassen:**

```python
def fit(self, df_train: pd.DataFrame) -> None:
    requested_columns = self.params.get("columns") or []
    if requested_columns:
        # Nutzer hat explizite Spalten angegeben → nur diese verwenden
        cat_cols = [c for c in requested_columns if c in df_train.columns]
    else:
        # Kein Parameter → Fallback: dtype-Autoerkennung (bisheriges Verhalten)
        cat_cols = list(df_train.select_dtypes(include=["object", "category", "string"]).columns)
    self._encoded_columns = cat_cols
```

**Hinweis:** Das LLM bekommt das neue Schema über `capabilities_json` automatisch — keine Änderung an `prompts.py` nötig.

---

## Offene Entscheidungen — müssen vor dem Fix beantwortet werden

Diese Punkte **dürfen beim Fixen nicht vergessen** werden. Der Dev-Agent muss Hannes vor der Implementierung fragen:

### Entscheidung A — Fallback-Verhalten bei leerem `columns`-Parameter

Wenn der Nutzer `encode_categorical` ohne `columns`-Parameter aufruft (z.B. "Encodiere alle kategorischen Spalten"):

- **Option 1:** Beibehaltung der dtype-Autoerkennung (`select_dtypes`) → bisheriges Verhalten, aber nun nur als expliziter Fallback
- **Option 2:** Step schlägt fehl mit einer klaren Fehlermeldung ("Bitte Spalten angeben")
- **Option 3:** LLM muss im System-Prompt angewiesen werden, immer explizit Spalten zu übergeben — Fallback wird entfernt

> **Empfehlung:** Option 1 ist rückwärtskompatibel und am sichersten. Option 3 wäre semantisch sauber, erfordert aber Prompt-Anpassung.

### Entscheidung B — Behandlung von nicht-kategorischen Spalten in `columns`

Wenn der Nutzer `columns: ["windspeed"]` übergibt und `windspeed` ist `float64`:

- **Option 1:** Warnung zurückgeben (`"windspeed ist nicht kategorisch, wird übersprungen"`), kein Encoding
- **Option 2:** Encoding trotzdem durchführen (Nutzer trägt Verantwortung)
- **Option 3:** Fehler werfen (`ValueError`)

> **Empfehlung:** Option 1 — gibt Feedback ohne den ganzen Step abzubrechen. Warnung sollte im `metadata`-Dict sichtbar sein, damit Frontend es anzeigen kann.

### Entscheidung C — Validierung im `spec_validator.py`

Soll `spec_validator.py` prüfen, ob `columns` valide Spaltennamen enthält (gegen bekannte Bike-CSV-Spalten)?

- **Option 1:** Ja, Validierung gegen statische Spaltenliste im Validator
- **Option 2:** Nein, Validierung erst zur Laufzeit im Step (wenn DataFrame bekannt)

> **Empfehlung:** Option 2 — statische Validierung ist fragil, da Spalten durch vorherige Steps entfernt/umbenannt werden können.

---

## Korrelation mit Bug 1.1

**Wichtiger Hinweis für den Fix-Agent:**

Dieser Bug (1.2) korreliert mit Bug 1.1 in einem gemeinsamen Bereich — beide betreffen wie Nutzeranfragen in Stepparameter übersetzt und dann ausgeführt werden. Konkret:

- Wenn Bug 1.1 eine Änderung an `encoding.py`, dem LLM-Prompt oder dem Schema-Mechanismus enthält, **muss vor dem Fix von Bug 1.2 geprüft werden**, welche Teile des Fixes von 1.1 bereits greifen.
- Insbesondere: Falls Bug 1.1 bereits einen `columns`-Parameter oder eine ähnliche Spaltenübergabe einführt, **darf Bug 1.2 nicht dieselbe Funktionalität ein zweites Mal hinzufügen** — sondern muss auf dem Fix von 1.1 aufbauen.
- Der Dev-Agent muss **nach dem Merge/Apply von Bug 1.1** zuerst prüfen, ob `param_schema` in `encoding.py` bereits einen `columns`-Eintrag hat, bevor er diesen neu anlegt.

**Abhängigkeit:** Bug 1.1 zuerst fixen → dann Bug 1.2 erneut prüfen und anpassen.

---

## Test-Anforderungen

Nach dem Fix müssen folgende Tests in `backend/tests/` vorhanden sein und bestehen:

1. `test_encode_categorical_with_explicit_column` — nur die angegebene Spalte wird encodet
2. `test_encode_categorical_multiple_columns` — mehrere explizit angegebene Spalten werden korrekt encodet
3. `test_encode_categorical_fallback_no_columns` — ohne `columns`-Parameter: bisheriges Fallback-Verhalten (je nach Entscheidung A)
4. `test_encode_categorical_nonexistent_column_skipped` — nicht vorhandene Spalte in `columns` → kein Fehler, kein Encoding dieser Spalte
5. `test_encode_categorical_non_categorical_column_warning` — Übergabe einer numerischen Spalte → Warnung oder kein Encoding (je nach Entscheidung B)
6. `test_encode_categorical_onehot_specific_column` — One-Hot auf explizit angegebene Spalte produziert korrekte Dummy-Spalten
