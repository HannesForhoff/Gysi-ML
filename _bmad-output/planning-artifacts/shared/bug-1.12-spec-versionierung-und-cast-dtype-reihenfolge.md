# Bug 1.12 — Spec-Versionierung: Zwei gekoppelte Probleme (Idempotenz + cast_dtype-Reihenfolge)

**Gefunden**: 2026-04-25
**Status**: ✅ Gefixt (2026-04-30)
**Priorität**: 🔴 Hoch (One-Hot-Encoding auf kategorischen Spalten vollständig wirkungslos)
**Kategorie**: Backend (`spec_repository.py`, `message_service.py`) + LLM-Prompt
**Analysiert von**: Party-Mode Session (Winston/Amelia/Quinn), 2026-04-25

---

## Beobachtetes Fehlverhalten

| Nutzeranfrage | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| "Führe One-Hot-Encoding für season aus" (season=int64) | Encoding wird übersprungen, **keine neue Spec-Version** (Daten unverändert) | Encoding übersprungen, aber **neue Spec-Version wird trotzdem angelegt** |
| "Wandle season von int64 auf category" | `cast_dtype` wird in Spec **vor** `encode_categorical` eingefügt | `cast_dtype` wird **hinter** `encode_categorical` angehängt → Spec: `[encode_categorical, cast_dtype]` |
| "Führe One-Hot-Encoding für season aus" (erneut) | `cast_dtype` läuft zuerst, danach greift `encode_categorical` | `encode_categorical` läuft zuerst (season=int64, übersprungen), `cast_dtype` danach (zu spät) → Encoding schlägt erneut fehl |

**Reproduzierter Chat-Verlauf (25.04.2026):**

```
User: Führe ein One Hot Encoding für season aus
→ Encoding übersprungen (season=int64), aber neue Spec-Version angelegt

User: Wandle die Spalte season von int64 in eine kategoriale um
→ Spec: [encode_categorical(onehot), cast_dtype({season: category})]
→ Im Frontend angezeigt: "Datentypen anpassen: season: int64 → category" ✓
→ Aber: cast_dtype ist HINTER encode_categorical in der Spec

User: Führe ein One Hot Encoding für season aus
→ Spec: [encode_categorical(onehot, season), cast_dtype({season: category})]
→ Pipeline führt encode_categorical zuerst aus (season=int64 → übersprungen)
→ danach cast_dtype (umwandlung erfolgt aber encode ist bereits gelaufen)
→ LLM-Antwort: "Das One Hot Encoding wurde für 'season' nicht durchgeführt, da diese als int64 erkannt wurde"
```

---

## Technische Ursachenanalyse — 2 eigenständige Teilprobleme

---

### Problem A — Neue Spec-Version obwohl Daten/Spec unverändert (Idempotenz fehlt)

**Schweregrad:** Mittel — Versionsbaum wird durch leere Runs aufgebläht, irreführend für Nutzer

**Datei:** `backend/src/gysi_ml/persistence/spec_repository.py`

**Ist-Zustand `create_spec_version()` (Zeilen 12–36):**

```python
def create_spec_version(
    session_id: str, spec: dict, db_path: str | None = None
) -> dict:
    previous = get_latest_spec(session_id=session_id, db_path=db_path)
    if previous is None:
        version = "v1"
    else:
        num = int(previous["version"].lstrip("v"))
        version = f"v{num + 1}"   # ← IMMER hochgezählt, kein Idempotenz-Check

    # ... INSERT wird immer ausgeführt
```

**Ursache:** `create_spec_version()` prüft nicht ob `spec == previous["spec"]`. Der Executor ruft diese Funktion bei jedem `execute`-Aufruf auf — auch wenn `encode_categorical` intern nichts verändert hat (Warnung "Oversprungen" im Log, aber neue Spec-Version in DB).

**Konkretes Beispiel:**
- Spec v1: `[encode_categorical(onehot, season)]` — Encoding übersprungen (season=int64)
- Daten: unverändert
- Aber: v2 wird trotzdem angelegt mit identischer Spec → Nutzer sieht im Versionsbaum eine neue Version ohne inhaltliche Änderung

**Fix A (empfohlen):**

In `create_spec_version()` vor dem INSERT prüfen, ob die neue Spec identisch zur vorherigen ist:

```python
def create_spec_version(
    session_id: str, spec: dict, db_path: str | None = None
) -> dict:
    previous = get_latest_spec(session_id=session_id, db_path=db_path)

    # NEU: Idempotenz-Check — keine neue Version wenn Spec unverändert
    if previous is not None and previous["spec"] == spec:
        return previous  # bestehende Version zurückgeben, kein INSERT

    if previous is None:
        version = "v1"
    else:
        num = int(previous["version"].lstrip("v"))
        version = f"v{num + 1}"
    # ... restliche Logik unverändert
```

**Auswirkung auf Tests:** `test_execute_persists_spec_version` und `test_create_spec_version_increments_to_v2` bleiben grün (Spec-Inhalte unterscheiden sich). Neu: Test der prüft dass identische Spec keine neue Version anlegt.

---

### Problem B — `cast_dtype` wird hinter `encode_categorical` gemergt (falsche Reihenfolge)

**Schweregrad:** 🔴 Hoch — One-Hot-Encoding auf Spalten mit Typ-Konvertierung ist dauerhaft wirkungslos

**Datei:** `backend/src/gysi_ml/services/message_service.py`

**Ursache — `_merge_specs()` Append-Logik:**

```python
# message_service.py — _merge_specs(), relevante Stelle
for new_step in new_steps:
    key = _merge_key(new_step)
    if key in key_to_idx:
        # Bestehender Step → an gleicher Position ersetzen
        merged[key_to_idx[key]] = new_step
    else:
        # Neuer Step-Typ → IMMER am Ende anhängen
        key_to_idx[key] = len(merged)
        merged.append(new_step)   # ← kein Bewusstsein für semantische Abhängigkeiten
```

**Konkrete Ablauffolge die den Bug produziert:**

1. Spec nach Run 1: `[encode_categorical(onehot, season)]` ← encode zuerst, cast fehlt
2. User: "Wandle season auf category" → LLM generiert `cast_dtype({season: category})`
3. Merge: `cast_dtype` ist neuer Key → wird hinter `encode_categorical` angehängt
4. Resultierende Spec: `[encode_categorical, cast_dtype]`
5. Pipeline-Ausführung: `encode_categorical` läuft zuerst (season=int64 → übersprungen), dann `cast_dtype` (wandelt um, aber re-encoding findet nicht statt)
6. Richtige Reihenfolge wäre: `[cast_dtype, encode_categorical]`

**Betroffener Ablauf (Pipeline-Executor):**

Der Executor (`executor.py`) führt Steps **strikt in Spec-Reihenfolge** aus — es gibt kein Retry oder Re-Scheduling. Was einmal übersprungen wurde, wird nicht nachgeholt.

---

## Fix-Optionen für Problem B

### Option 1 — Merge-Logik: Abhängigkeits-aware Insert (empfohlen)

In `_merge_specs()`: Wenn ein `cast_dtype`-Step gemergt wird und im aktuellen Spec bereits ein `encode_categorical`-Step existiert, `cast_dtype` **vor** `encode_categorical` einfügen.

```python
# In _merge_specs(), nach der key-Prüfung:
else:
    # Neuer Step — prüfen ob Abhängigkeits-Umkehrung nötig
    new_type = new_step.get("type")
    if new_type == "cast_dtype" and "encode_categorical" in key_to_idx:
        # cast_dtype muss VOR encode_categorical stehen
        encode_idx = key_to_idx["encode_categorical"]
        merged.insert(encode_idx, new_step)
        # Index-Map aktualisieren (alle Positionen nach dem Insert verschieben)
        for k, idx in key_to_idx.items():
            if idx >= encode_idx:
                key_to_idx[k] = idx + 1
        key_to_idx["cast_dtype"] = encode_idx
    else:
        key_to_idx[key] = len(merged)
        merged.append(new_step)
```

**Vorteil:** Deterministisch, kein LLM-Abhängigkeit.
**Nachteil:** Nur `cast_dtype` ↔ `encode_categorical` berücksichtigt — andere Abhängigkeiten nicht.

### Option 2 — LLM-Prompt: Reihenfolge-Instruktion (einfachster Fix, unzuverlässig)

Im System-Prompt ergänzen:

```
REIHENFOLGE: Wenn `cast_dtype` und `encode_categorical` für dieselbe Spalte vorgesehen sind,
muss `cast_dtype` IMMER VOR `encode_categorical` in der Spec stehen.
```

**Vorteil:** Minimale Code-Änderung.
**Nachteil:** LLM-Compliance nicht garantiert; hilft nur wenn LLM beide Steps in einem Aufruf generiert.

### Option 3 — Spec-Validator: Reihenfolge-Invariante prüfen (robusteste Lösung, additive Sicherheit)

In `spec_validator.py` eine neue Regel:

```python
# Wenn cast_dtype und encode_categorical beide vorhanden:
# cast_dtype muss vor encode_categorical kommen
cast_idx = next((i for i, s in enumerate(steps) if s["type"] == "cast_dtype"), None)
encode_idx = next((i for i, s in enumerate(steps) if s["type"] == "encode_categorical"), None)
if cast_idx is not None and encode_idx is not None and cast_idx > encode_idx:
    raise SpecOrderError(
        "cast_dtype muss vor encode_categorical stehen, "
        "damit Typ-Konvertierungen vor dem Encoding wirksam sind."
    )
```

**Vorteil:** Fängt falsche Specs auch aus anderen Quellen ab.
**Nachteil:** Gibt Fehler zurück statt automatisch zu korrigieren — benötigt User-Interaktion.

---

## Empfohlene Fix-Reihenfolge

1. **Problem A** (Idempotenz in `spec_repository.py`) — Einzeiler, sofort umsetzbar, kein Risiko
2. **Problem B Option 1** (Merge-Logik) — deterministisch, keine LLM-Abhängigkeit
3. **Problem B Option 3** (Spec-Validator) — additiv auf Option 1, als Safety-Net

---

## Notwendige Tests

### Für Problem A
```python
def test_create_spec_version_idempotent():
    """Identische Spec → keine neue Version angelegt, bestehende zurückgegeben."""
    session_id = _insert_session(db)
    spec = {"steps": [{"type": "dedup"}]}
    v1 = create_spec_version(session_id, spec, db_path=db)
    v2 = create_spec_version(session_id, spec, db_path=db)  # identische Spec
    assert v1["version"] == v2["version"]
    assert v1["spec_id"] == v2["spec_id"]
```

### Für Problem B
```python
def test_cast_dtype_inserted_before_encode_categorical():
    """cast_dtype als neuer Step → vor encode_categorical eingefügt, nicht dahinter."""
    current = _spec(_step("encode_categorical", method="onehot"))
    new = _spec({"type": "cast_dtype", "params": {"columns": {"season": "category"}}})
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    assert types == ["cast_dtype", "encode_categorical"]

def test_cast_dtype_before_encode_does_not_affect_unrelated_steps():
    """cast_dtype ohne encode_categorical → normales Append-Verhalten."""
    current = _spec(_step("dedup"), _step("split"))
    new = _spec({"type": "cast_dtype", "params": {"columns": {"season": "category"}}})
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    assert types == ["dedup", "split", "cast_dtype"]
```

---

## Offene Designentscheidungen

1. **Idempotenz**: Soll die Methode `create_spec_version()` die Gleichheit über `==` auf Dict-Ebene prüfen oder gibt es Felder (z.B. Timestamp) die ignoriert werden sollen? → Nur `spec["steps"]` vergleichen, nicht Metadaten.

2. **Merge-Reihenfolge allgemein**: Gibt es weitere Step-Paare mit impliziter Abhängigkeit die ähnlich behandelt werden müssen (z.B. `outlier_handling` vor `encode_categorical`)? → Separates Ticket wenn neue Fälle auftreten.
