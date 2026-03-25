# Story 8.1: Spec-Diff-Utility (`spec_diff`)

Status: done

## Story

Als ein Entwickler,
möchte ich eine reine Utility-Funktion `spec_diff(old_spec, new_spec) -> str`, die eine kompakte, menschenlesbare Zusammenfassung der Änderungen zwischen zwei Specs generiert,
damit `change_summary` automatisch beim Erstellen jeder neuen Spec-Version befüllt wird.

## Acceptance Criteria

1. **[Hinzugefügter Step]** `spec_diff(old, new)` mit neuem Step `outlier_handling` → enthält `"+ outlier_handling (IQR)"`.

2. **[Entfernter Step]** `spec_diff(old, new)` mit fehlendem Step `correlation_filter` → enthält `"− correlation_filter"`.

3. **[Geänderter Parameter]** `imputation.params.method` von `"median"` zu `"mean"` → enthält `"imputation: median → mean"`.

4. **[Deaktivierter Step]** `enabled: false` für `encoding` → enthält `"encoding: deaktiviert"`.

5. **[Mehrere Änderungen kommasepariert]** Alle Änderungen in einem String: `"+ outlier_handling (IQR), imputation: median → mean"`.

6. **[Keine Änderungen → leerer String]** Gleiche Specs → `""` (kein Fehler, kein Leerstring mit Whitespace).

7. **[Unveränderte Parameter nicht aufgelistet]** Nur tatsächlich geänderte Parameter erscheinen — kein Noise.

8. **[Integration in `spec_repository.py`]** `create_spec_version()` befüllt `change_summary` automatisch via `spec_diff()`.

9. **[Test-Coverage ≥ 85%]** Alle 7 ACs haben dedizierte Tests.

## Tasks / Subtasks

- [x] **T1 — `spec/spec_diff.py` anlegen** (AC: 1–7)
  - [x] Datei: `backend/src/gysi_ml/spec/spec_diff.py` (neu, neben `schema.py`)
  - [x] Implementierung:
    ```python
    """Spec-Diff-Utility: menschenlesbare Zusammenfassung der Änderungen zwischen zwei Pipeline-Specs."""
    from __future__ import annotations
    
    
    def spec_diff(old_spec: dict, new_spec: dict) -> str:
        """Gibt eine kommaseparierte, menschenlesbare Zusammenfassung der Spec-Änderungen zurück.
        
        Format:
          + step_type (key_param)    — neuer Step
          − step_type                — Step entfernt
          step_type: old → new       — Parameter geändert
          step_type: deaktiviert     — Step deaktiviert
        
        Returns "" wenn keine Änderungen.
        """
        old_steps = {s["type"]: s for s in old_spec.get("steps", [])}
        new_steps = {s["type"]: s for s in new_spec.get("steps", [])}
    
        changes = []
    
        # Entfernte Steps
        for step_type in old_steps:
            if step_type not in new_steps:
                changes.append(f"− {step_type}")
    
        # Neue Steps
        for step_type, step in new_steps.items():
            if step_type not in old_steps:
                # Zeige ersten Parameter als Hinweis
                params = step.get("params", {})
                param_hint = ""
                if params:
                    first_key = next(iter(params))
                    param_hint = f" ({params[first_key]})"
                changes.append(f"+ {step_type}{param_hint}")
    
        # Geänderte Steps (beide vorhanden)
        for step_type in old_steps:
            if step_type not in new_steps:
                continue
            old_step = old_steps[step_type]
            new_step = new_steps[step_type]
    
            # Aktivierung/Deaktivierung
            old_enabled = old_step.get("enabled", True)
            new_enabled = new_step.get("enabled", True)
            if old_enabled and not new_enabled:
                changes.append(f"{step_type}: deaktiviert")
                continue  # Keine weiteren Parameter-Diffs bei Deaktivierung
            elif not old_enabled and new_enabled:
                changes.append(f"{step_type}: aktiviert")
                continue
    
            # Parameter-Diffs
            old_params = old_step.get("params", {})
            new_params = new_step.get("params", {})
            for key in set(list(old_params.keys()) + list(new_params.keys())):
                old_val = old_params.get(key)
                new_val = new_params.get(key)
                if old_val != new_val:
                    changes.append(f"{step_type}: {old_val} → {new_val}")
    
        return ", ".join(changes)
    ```

- [x] **T2 — `spec_repository.create_spec_version()` integrieren** (AC: 8)
  - [x] Datei: `backend/src/gysi_ml/persistence/spec_repository.py`
  - [x] Import ergänzen: `from gysi_ml.spec.spec_diff import spec_diff`
  - [x] `create_spec_version()` anpassen:
    ```python
    # Vorgänger-Spec laden für Diff
    previous = get_latest_spec(session_id=session_id, db_path=db_path)
    parent_spec_id = previous["spec_id"] if previous else None
    change_summary = spec_diff(previous["spec"], spec) if previous else None
    ```
  - [x] `INSERT INTO spec_versions` muss `parent_spec_id` und `change_summary` mit übergeben:
    ```python
    conn.execute(
        "INSERT INTO spec_versions (spec_id, session_id, version, spec_json, created_at, parent_spec_id, change_summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (spec_id, session_id, version, spec_json, created_at, parent_spec_id, change_summary),
    )
    ```
  - [x] ⚠️ Diese Änderung setzt Story 5.1 voraus — Spalten müssen in der DB existieren

- [x] **T3 — Tests für `spec_diff`** (AC: 1–7, 9)
  - [x] Datei: `backend/tests/unit/test_spec_diff.py` (neu)
  - [x] Tests:
    - `test_added_step()`: + outlier_handling in Ergebnis
    - `test_removed_step()`: − correlation_filter in Ergebnis
    - `test_changed_param()`: "imputation: median → mean" in Ergebnis
    - `test_deactivated_step()`: "encoding: deaktiviert" in Ergebnis
    - `test_multiple_changes()`: Alle Änderungen im kommaseparierten String
    - `test_no_changes_empty_string()`: Gleiche Specs → `""` exakt
    - `test_unchanged_params_not_listed()`: Unveränderte Parameter tauchen nicht auf

## Dev Notes

### Abhängigkeiten

- **Benötigt Story 5.1:** `spec_versions` muss `parent_spec_id` und `change_summary`-Spalten haben, sonst schlägt das UPDATE fehl.
- Story 8.2 und 8.3 setzen `spec_diff` voraus (Versionsbaum-Display + Rollback-Summary).

### Reine Funktion — kein Service, keine Klasse

- `spec_diff` ist eine Modul-Funktion (keine Klasse, kein Service)
- Einfach testbar ohne Mocking oder DB-Zugriff
- Platz: `spec/spec_diff.py` — neben `spec/schema.py`

### Spec-Format

- Spec ist ein dict mit `steps: list[dict]`
- Jeder Step hat mindestens: `type: str`, optional `enabled: bool` (Default: True), optional `params: dict`
- Beispiel: `{"type": "imputation", "enabled": true, "params": {"method": "median"}}`

### Rückwärtskompatibilität `create_spec_version()`

- Bestehende Aufrufer übergeben nur `session_id` + `spec` → Signatur unverändert
- `parent_spec_id` und `change_summary` werden intern generiert — keine Schnittstellen-Änderung

### References

- [Source: backend/src/gysi_ml/persistence/spec_repository.py] — aktuelle `create_spec_version()`
- [Source: backend/src/gysi_ml/spec/schema.py] — Spec-Format-Referenz
- [Source: _bmad-output/planning-artifacts/shared/epics-usability-features-2026-03-21.md#Story-8.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#Spec-Diff]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

Keine Blockaden. Story-5.1-Migrations-Spalten waren bereits vorhanden (`parent_spec_id`, `change_summary` in `schema.py` via ALTER TABLE).

### Completion Notes List

- T1: `spec_diff.py` als reine Modul-Funktion angelegt — keine Klasse, kein Service
- T2: `create_spec_version()` ruft intern `get_latest_spec()` auf; bei erster Version ist `parent_spec_id = None`, `change_summary = None`
- T3: 8 dedizierte Tests (7 AC + 1 Reaktivierungs-Branch) — Coverage 100%; 351/351 Unit-Tests grün
- Signatur von `create_spec_version()` unverändert (keine Breaking Change für Aufrufer)
- **Code Review Fix M1:** Redundante DB-Query entfernt — `get_latest_spec()` wird einmalig vorangestellt, liefert Version + Spec in einem DB-Round-trip
- **Code Review Fix L1:** Test `test_reactivated_step()` ergänzt — Branch Lines 51–52 jetzt abgedeckt (100% Coverage)
- **Code Review Fix L2:** Assertions in `test_added_step` und `test_changed_param` auf exakte Substrings präzisiert
- **Code Review Fix L3:** Implementations-Checkbox T1 geschlossen

### File List

- `backend/src/gysi_ml/spec/spec_diff.py` (neu)
- `backend/src/gysi_ml/persistence/spec_repository.py` (geändert)
- `backend/tests/unit/test_spec_diff.py` (neu)
