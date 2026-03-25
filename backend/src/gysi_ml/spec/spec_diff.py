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
