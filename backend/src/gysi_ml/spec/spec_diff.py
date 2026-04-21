"""Spec-Diff-Utility: menschenlesbare Zusammenfassung der Änderungen zwischen zwei Pipeline-Specs."""
from __future__ import annotations


def _step_key(step: dict) -> str:
    """Eindeutiger Schlüssel für einen Step.

    impute_missing: Typ + Strategie — verschiedene Strategien sind separate Steps.
    Alle anderen Step-Typen: nur der Typ.
    """
    if step.get("type") == "impute_missing":
        strategy = step.get("params", {}).get("strategy", "median")
        return f"impute_missing:{strategy}"
    return step.get("type", "")


def _format_val(val: object) -> str:
    """Lesbare Darstellung eines einzelnen Param-Werts (inkl. Listen)."""
    if isinstance(val, list):
        if not val:
            return "—"
        items = [str(v) for v in val[:3]]
        suffix = ", …" if len(val) > 3 else ""
        return ", ".join(items) + suffix
    return str(val)


def _format_step_hint(step: dict) -> str:
    """Kompakte, lesbare Beschreibung eines Steps für '+'-Einträge in der change_summary.

    Rückgabe:
    - Beginnt mit Spaltenname(n)  → Aufrufer trennt mit ': '
    - Beginnt mit '('             → Aufrufer trennt mit ' '
    - Leer                        → kein Hinweis
    """
    step_type = step.get("type", "")
    params = step.get("params", {})
    columns: list = params.get("columns") or []
    cols_str = _format_val(columns) if columns else ""

    if step_type == "impute_missing":
        strategy = params.get("strategy", "median")
        return f"{cols_str} ({strategy})" if cols_str else f"({strategy})"

    if step_type == "outlier_handling":
        method = params.get("method", "iqr").upper()
        return f"{cols_str} ({method})" if cols_str else f"({method}, alle Spalten)"

    if step_type == "encode_categorical":
        method = params.get("method", "label")
        return f"{cols_str} ({method})" if cols_str else f"({method})"

    if step_type == "train_decision_tree":
        max_depth = params.get("max_depth")
        return f"(cnt, max_depth={max_depth})" if max_depth is not None else "(cnt)"

    if step_type == "train_ebm":
        return "(cnt)"

    if step_type == "catboost_feature_selection":
        top_n = params.get("top_n")
        return f"(cnt, top_n={top_n})" if top_n is not None else "(cnt)"

    if step_type == "split":
        test_size = params.get("test_size")
        return f"(test_size={test_size})" if test_size is not None else ""

    if step_type == "correlation_filter":
        threshold = params.get("threshold")
        return f"(threshold={threshold})" if threshold is not None else ""

    if step_type == "rare_category_bucketing":
        min_freq = params.get("min_frequency")
        return f"(min_freq={min_freq})" if min_freq is not None else ""

    if step_type == "time_feature_encoding":
        column = params.get("column", "")
        return f"({column})" if column else ""

    if step_type == "cast_dtype":
        dtype = params.get("dtype", "")
        return f"{cols_str} ({dtype})" if cols_str and dtype else f"({dtype})" if dtype else ""

    # Fallback: erster Param-Wert
    if params:
        first_key = next(iter(params))
        return f"({params[first_key]})"
    return ""


def spec_diff(old_spec: dict, new_spec: dict) -> str:
    """Gibt eine kommaseparierte, menschenlesbare Zusammenfassung der Spec-Änderungen zurück.

    Format:
      + step_type (key_param)    — neuer Step
      − step_type                — Step entfernt
      step_type: old → new       — Parameter geändert
      step_type: deaktiviert     — Step deaktiviert

    Returns "" wenn keine Änderungen.
    """
    old_steps = {_step_key(s): s for s in old_spec.get("steps", [])}
    new_steps = {_step_key(s): s for s in new_spec.get("steps", [])}

    changes = []

    # Entfernte Steps
    for key in old_steps:
        if key not in new_steps:
            step_type = old_steps[key]["type"]
            changes.append(f"− {step_type}")

    # Neue Steps
    for key, step in new_steps.items():
        if key not in old_steps:
            step_type = step["type"]
            hint = _format_step_hint(step)
            if hint:
                sep = ": " if not hint.startswith("(") else " "
                changes.append(f"+ {step_type}{sep}{hint}")
            else:
                changes.append(f"+ {step_type}")

    # Geänderte Steps (beide vorhanden)
    for key in old_steps:
        if key not in new_steps:
            continue
        old_step = old_steps[key]
        new_step = new_steps[key]
        step_type = old_step["type"]

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
        for param_key in set(list(old_params.keys()) + list(new_params.keys())):
            old_val = old_params.get(param_key)
            new_val = new_params.get(param_key)
            if old_val != new_val:
                changes.append(f"{step_type}: {_format_val(old_val)} → {_format_val(new_val)}")

    return ", ".join(changes)
