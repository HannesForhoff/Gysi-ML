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


# ---------------------------------------------------------------------------
# _format_val — leere Liste und lange Listen
# ---------------------------------------------------------------------------


def test_format_val_empty_columns_shows_dash():
    """Leere columns-Liste wird als '—' formatiert (via Parameteränderung im Diff)."""
    old = _spec(_step("impute_missing", {"strategy": "median", "columns": ["windspeed"]}))
    new = _spec(_step("impute_missing", {"strategy": "median", "columns": []}))
    result = spec_diff(old, new)
    assert "—" in result


def test_format_val_long_list_truncated():
    """Listen mit mehr als 3 Elementen werden mit '…' abgekürzt."""
    old = _spec(_step("impute_missing", {"strategy": "median", "columns": ["a"]}))
    new = _spec(
        _step(
            "impute_missing",
            {"strategy": "median", "columns": ["a", "b", "c", "d", "e"]},
        )
    )
    result = spec_diff(old, new)
    assert "…" in result


# ---------------------------------------------------------------------------
# _format_step_hint — train_decision_tree ohne max_depth
# ---------------------------------------------------------------------------


def test_added_decision_tree_no_max_depth():
    """train_decision_tree ohne max_depth → '(cnt)' im Hint."""
    old = {"steps": []}
    new = _spec(_step("train_decision_tree", {"random_state": 42}))
    result = spec_diff(old, new)
    assert "train_decision_tree" in result
    assert "cnt" in result
    assert "max_depth" not in result


# ---------------------------------------------------------------------------
# _format_step_hint — encode_categorical
# ---------------------------------------------------------------------------


def test_added_encode_categorical_with_columns():
    """encode_categorical mit columns zeigt Spaltenname und Methode."""
    old = {"steps": []}
    new = _spec(_step("encode_categorical", {"method": "onehot", "columns": ["season"]}))
    result = spec_diff(old, new)
    assert "encode_categorical" in result
    assert "season" in result
    assert "onehot" in result


def test_added_encode_categorical_no_columns():
    """encode_categorical ohne columns zeigt nur die Methode."""
    old = {"steps": []}
    new = _spec(_step("encode_categorical", {"method": "label"}))
    result = spec_diff(old, new)
    assert "encode_categorical" in result
    assert "label" in result


# ---------------------------------------------------------------------------
# _format_step_hint — train_ebm
# ---------------------------------------------------------------------------


def test_added_ebm_shows_cnt():
    """train_ebm → '(cnt)' im Hint."""
    old = {"steps": []}
    new = _spec(_step("train_ebm", {}))
    result = spec_diff(old, new)
    assert "train_ebm" in result
    assert "cnt" in result


# ---------------------------------------------------------------------------
# _format_step_hint — catboost_feature_selection
# ---------------------------------------------------------------------------


def test_added_catboost_with_top_n():
    """catboost_feature_selection mit top_n zeigt 'top_n=...' im Hint."""
    old = {"steps": []}
    new = _spec(_step("catboost_feature_selection", {"top_n": 10}))
    result = spec_diff(old, new)
    assert "catboost_feature_selection" in result
    assert "top_n=10" in result


def test_added_catboost_no_top_n():
    """catboost_feature_selection ohne top_n → '(cnt)' im Hint."""
    old = {"steps": []}
    new = _spec(_step("catboost_feature_selection", {}))
    result = spec_diff(old, new)
    assert "catboost_feature_selection" in result
    assert "cnt" in result


# ---------------------------------------------------------------------------
# _format_step_hint — split ohne test_size
# ---------------------------------------------------------------------------


def test_added_split_no_test_size():
    """split ohne test_size → kein Hint-Inhalt, Step wird aber gemeldet."""
    old = {"steps": []}
    new = _spec(_step("split", {}))
    result = spec_diff(old, new)
    assert "+ split" in result


# ---------------------------------------------------------------------------
# _format_step_hint — correlation_filter ohne threshold
# ---------------------------------------------------------------------------


def test_added_correlation_filter_no_threshold():
    """correlation_filter ohne threshold → kein Hint-Inhalt."""
    old = {"steps": []}
    new = _spec(_step("correlation_filter", {}))
    result = spec_diff(old, new)
    assert "+ correlation_filter" in result


# ---------------------------------------------------------------------------
# _format_step_hint — rare_category_bucketing
# ---------------------------------------------------------------------------


def test_added_rare_category_with_min_freq():
    """rare_category_bucketing mit min_frequency zeigt '(min_freq=...)' im Hint."""
    old = {"steps": []}
    new = _spec(_step("rare_category_bucketing", {"min_frequency": 0.05}))
    result = spec_diff(old, new)
    assert "rare_category_bucketing" in result
    assert "min_freq=0.05" in result


def test_added_rare_category_no_min_freq():
    """rare_category_bucketing ohne min_frequency → kein Hint-Inhalt."""
    old = {"steps": []}
    new = _spec(_step("rare_category_bucketing", {}))
    result = spec_diff(old, new)
    assert "+ rare_category_bucketing" in result


# ---------------------------------------------------------------------------
# _format_step_hint — time_feature_encoding
# ---------------------------------------------------------------------------


def test_added_time_feature_with_column():
    """time_feature_encoding mit column zeigt Spaltenname im Hint."""
    old = {"steps": []}
    new = _spec(_step("time_feature_encoding", {"column": "dteday"}))
    result = spec_diff(old, new)
    assert "time_feature_encoding" in result
    assert "dteday" in result


def test_added_time_feature_no_column():
    """time_feature_encoding ohne column → kein Hint-Inhalt."""
    old = {"steps": []}
    new = _spec(_step("time_feature_encoding", {}))
    result = spec_diff(old, new)
    assert "+ time_feature_encoding" in result


# ---------------------------------------------------------------------------
# _format_step_hint — cast_dtype
# ---------------------------------------------------------------------------


def test_added_cast_dtype_two_columns():
    """cast_dtype mit ≤2 Spalten zeigt alle Mappings."""
    old = {"steps": []}
    new = _spec(_step("cast_dtype", {"columns": {"season": "category", "yr": "int"}}))
    result = spec_diff(old, new)
    assert "cast_dtype" in result
    assert "season" in result
    assert "category" in result


def test_added_cast_dtype_many_columns():
    """cast_dtype mit >2 Spalten kürzt mit '…' ab."""
    old = {"steps": []}
    new = _spec(
        _step(
            "cast_dtype",
            {"columns": {"a": "int", "b": "float", "c": "category", "d": "str"}},
        )
    )
    result = spec_diff(old, new)
    assert "cast_dtype" in result
    assert "…" in result


def test_added_cast_dtype_no_columns():
    """cast_dtype mit leerem/keinem columns-Dict → kein Hint, Step wird gemeldet."""
    old = {"steps": []}
    new = _spec(_step("cast_dtype", {}))
    result = spec_diff(old, new)
    assert "+ cast_dtype" in result


# ---------------------------------------------------------------------------
# _format_step_hint — Fallback für unbekannte Step-Typen
# ---------------------------------------------------------------------------


def test_added_unknown_step_with_params_shows_first_param():
    """Unbekannter Step-Typ mit params → erster Param-Wert als Fallback."""
    old = {"steps": []}
    new = _spec(_step("some_future_step", {"key": "value"}))
    result = spec_diff(old, new)
    assert "some_future_step" in result
    assert "value" in result


def test_added_unknown_step_no_params():
    """Unbekannter Step-Typ ohne params → nur Step-Name, kein Hint."""
    old = {"steps": []}
    new = _spec(_step("some_future_step", {}))
    result = spec_diff(old, new)
    assert "+ some_future_step" in result
