"""Tests für spec_diff — AC 1–7, 9 aus Story 8.1."""

import pytest

from gysi_ml.spec.spec_diff import spec_diff


# Hilfs-Factories
def _step(type_: str, params: dict | None = None, enabled: bool = True) -> dict:
    s: dict = {"type": type_}
    if params is not None:
        s["params"] = params
    if not enabled:
        s["enabled"] = False
    return s


def _spec(*steps) -> dict:
    return {"steps": list(steps)}


# ---------------------------------------------------------------------------
# AC 1 — Hinzugefügter Step
# ---------------------------------------------------------------------------


def test_added_step():
    """spec_diff meldet neu hinzugefügten Step mit Parameterhinweis."""
    old = _spec(_step("imputation", {"method": "median"}))
    new = _spec(
        _step("imputation", {"method": "median"}),
        _step("outlier_handling", {"method": "IQR"}),
    )
    result = spec_diff(old, new)
    assert "+ outlier_handling" in result
    assert "IQR" in result


# ---------------------------------------------------------------------------
# AC 2 — Entfernter Step
# ---------------------------------------------------------------------------


def test_removed_step():
    """spec_diff meldet entfernten Step mit '−'-Präfix."""
    old = _spec(
        _step("imputation", {"method": "median"}),
        _step("correlation_filter", {"threshold": 0.9}),
    )
    new = _spec(_step("imputation", {"method": "median"}))
    result = spec_diff(old, new)
    assert "− correlation_filter" in result


# ---------------------------------------------------------------------------
# AC 3 — Geänderter Parameter
# ---------------------------------------------------------------------------


def test_changed_param():
    """spec_diff zeigt Parameteränderung im Format 'step: alt → neu'."""
    old = _spec(_step("imputation", {"method": "median"}))
    new = _spec(_step("imputation", {"method": "mean"}))
    result = spec_diff(old, new)
    assert "imputation: median → mean" in result


# ---------------------------------------------------------------------------
# AC 4 — Deaktivierter Step
# ---------------------------------------------------------------------------


def test_deactivated_step():
    """spec_diff meldet Deaktivierung eines Steps."""
    old = _spec(_step("encoding", {"strategy": "onehot"}))
    new = _spec(_step("encoding", {"strategy": "onehot"}, enabled=False))
    result = spec_diff(old, new)
    assert "encoding" in result
    assert "deaktiviert" in result


# ---------------------------------------------------------------------------
# AC 5 — Mehrere Änderungen kommasepariert
# ---------------------------------------------------------------------------


def test_multiple_changes():
    """spec_diff kombiniert mehrere Änderungen kommasepariert in einem String."""
    old = _spec(
        _step("imputation", {"method": "median"}),
    )
    new = _spec(
        _step("imputation", {"method": "mean"}),
        _step("outlier_handling", {"method": "IQR"}),
    )
    result = spec_diff(old, new)
    # Beide Änderungen müssen vorhanden sein
    assert "imputation" in result
    assert "outlier_handling" in result
    # Kommasepariert
    assert "," in result


# ---------------------------------------------------------------------------
# AC 6 — Keine Änderungen → leerer String
# ---------------------------------------------------------------------------


def test_no_changes_empty_string():
    """spec_diff gibt exakt '' zurück, wenn sich Specs nicht unterscheiden."""
    spec = _spec(_step("imputation", {"method": "median"}))
    result = spec_diff(spec, spec)
    assert result == ""


# ---------------------------------------------------------------------------
# AC 7 — Unveränderte Parameter nicht aufgelistet
# ---------------------------------------------------------------------------


def test_unchanged_params_not_listed():
    """Unveränderte Parameter tauchen nicht im Diff auf."""
    old = _spec(_step("imputation", {"method": "median", "fill_value": 0}))
    new = _spec(_step("imputation", {"method": "mean", "fill_value": 0}))
    result = spec_diff(old, new)
    # Nur 'method' hat sich geändert — fill_value darf nicht erscheinen
    assert "fill_value" not in result
    assert "imputation: median → mean" in result


# ---------------------------------------------------------------------------
# L1 — Reaktivierter Step (Branch lines 51-52 in spec_diff.py)
# ---------------------------------------------------------------------------


def test_reactivated_step():
    """spec_diff meldet Reaktivierung eines zuvor deaktivierten Steps."""
    old = _spec(_step("encoding", {"strategy": "onehot"}, enabled=False))
    new = _spec(_step("encoding", {"strategy": "onehot"}))
    result = spec_diff(old, new)
    assert "encoding: aktiviert" in result


# ---------------------------------------------------------------------------
# impute_missing: verschiedene Strategien als separate Steps
# ---------------------------------------------------------------------------


def test_second_impute_different_strategy_shown_as_added():
    """Ein zweiter impute_missing mit anderer Strategie ist ein neuer Step, kein Ersatz."""
    old = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed"]}))
    new = _spec(
        _step("impute_missing", {"strategy": "median", "columns": ["windspeed"]}),
        _step("impute_missing", {"strategy": "mean", "columns": ["cnt"]}),
    )
    result = spec_diff(old, new)
    # Neuer Step wird als Hinzufügung gezeigt
    assert "+ impute_missing" in result
    # Bestehender Median-Step wird NICHT als geändert angezeigt
    assert "windspeed → cnt" not in result
    assert "median → mean" not in result


def test_same_strategy_column_merge_shown_as_change():
    """Gleiche Strategie, neue Spalte hinzugefügt → Parameteränderung im Diff."""
    old = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed"]}))
    new = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed", "cnt"]}))
    result = spec_diff(old, new)
    assert "impute_missing" in result
    assert "windspeed" in result or "cnt" in result


# ---------------------------------------------------------------------------
# Informative Hints — _format_step_hint
# ---------------------------------------------------------------------------


def test_added_impute_shows_columns_and_strategy():
    """Neuer impute_missing-Step zeigt Spalten + Strategie."""
    old = {"steps": []}
    new = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed"]}))
    result = spec_diff(old, new)
    assert "windspeed" in result
    assert "median" in result


def test_added_outlier_without_columns_shows_all():
    """outlier_handling ohne columns → '(IQR, alle Spalten)'."""
    old = {"steps": []}
    new = _spec(_step("outlier_handling", {"method": "iqr"}))
    result = spec_diff(old, new)
    assert "IQR" in result
    assert "alle" in result


def test_added_outlier_with_columns():
    """outlier_handling mit columns → Spaltenname sichtbar."""
    old = {"steps": []}
    new = _spec(_step("outlier_handling", {"method": "iqr", "columns": ["windspeed"]}))
    result = spec_diff(old, new)
    assert "windspeed" in result


def test_added_decision_tree_shows_max_depth():
    """train_decision_tree zeigt max_depth."""
    old = {"steps": []}
    new = _spec(_step("train_decision_tree", {"max_depth": 4, "random_state": 42}))
    result = spec_diff(old, new)
    assert "max_depth=4" in result
    assert "cnt" in result


def test_added_split_shows_test_size():
    """split zeigt test_size."""
    old = {"steps": []}
    new = _spec(_step("split", {"test_size": 0.2}))
    result = spec_diff(old, new)
    assert "test_size=0.2" in result


def test_changed_list_param_readable():
    """Geänderte Listen-Parameter werden ohne eckige Klammern angezeigt."""
    old = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed"]}))
    new = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed", "cnt"]}))
    result = spec_diff(old, new)
    # Keine eckigen Klammern
    assert "[" not in result
    assert "]" not in result
