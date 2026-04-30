"""Unit-Tests für _merge_specs() in message_service.py."""
import pytest

from gysi_ml.services.message_service import _merge_specs


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _step(type_: str, **params) -> dict:
    s: dict = {"type": type_}
    if params:
        s["params"] = params
    return s


def _spec(*steps: dict) -> dict:
    return {"steps": list(steps)}


# ---------------------------------------------------------------------------
# Keine aktuelle Spec (Erstausführung)
# ---------------------------------------------------------------------------


def test_no_current_spec_returns_new_spec_unchanged():
    new = _spec(_step("split", test_size=0.2))
    assert _merge_specs(None, new) == new


def test_no_current_spec_with_empty_new_steps_returns_new_spec():
    new = {"steps": []}
    assert _merge_specs(None, new) == new


# ---------------------------------------------------------------------------
# Leere neue Spec → Re-Run des aktuellen Stands
# ---------------------------------------------------------------------------


def test_empty_new_steps_returns_current_steps():
    current = _spec(_step("split", test_size=0.2), _step("dedup"))
    new = {"steps": []}
    result = _merge_specs(current, new)
    assert result["steps"] == current["steps"]


# ---------------------------------------------------------------------------
# Neuer Step-Typ → anhängen
# ---------------------------------------------------------------------------


def test_new_step_type_appended_after_existing():
    current = _spec(_step("split", test_size=0.2))
    new = _spec(_step("train_decision_tree", max_depth=4, target="cnt"))
    result = _merge_specs(current, new)
    assert [s["type"] for s in result["steps"]] == ["split", "train_decision_tree"]


def test_multiple_new_step_types_all_appended_in_order():
    current = _spec(_step("split"))
    new = _spec(_step("impute_missing"), _step("train_decision_tree"))
    result = _merge_specs(current, new)
    assert [s["type"] for s in result["steps"]] == ["split", "impute_missing", "train_decision_tree"]


# ---------------------------------------------------------------------------
# Bestehender Step-Typ → ersetzen (Parameter-Update), Position beibehalten
# ---------------------------------------------------------------------------


def test_existing_step_type_replaced_with_new_params():
    current = _spec(_step("split", test_size=0.2, random_state=42))
    new = _spec(_step("split", test_size=0.3, random_state=42))
    result = _merge_specs(current, new)
    # Nur ein Step in der Ausgabe
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"]["test_size"] == 0.3


def test_existing_step_position_preserved():
    current = _spec(_step("split"), _step("dedup"), _step("impute_missing"))
    # Nutzer ändert dedup-Parameter (kein Param hier, aber Typ vorhanden)
    new = _spec(_step("dedup"))
    result = _merge_specs(current, new)
    # Reihenfolge unverändert, dedup ersetzt an Position 1
    assert [s["type"] for s in result["steps"]] == ["split", "dedup", "impute_missing"]


# ---------------------------------------------------------------------------
# Mix: vorhandene ersetzen + neue anhängen
# ---------------------------------------------------------------------------


def test_mixed_replace_and_append():
    current = _spec(_step("split", test_size=0.2), _step("dedup"))
    new = _spec(
        _step("dedup"),                             # ersetzt bestehenden
        _step("train_decision_tree", max_depth=4),  # neuer Step
    )
    result = _merge_specs(current, new)
    assert [s["type"] for s in result["steps"]] == ["split", "dedup", "train_decision_tree"]


# ---------------------------------------------------------------------------
# enabled-Flag wird aus dem neuen Step übernommen
# ---------------------------------------------------------------------------


def test_enabled_flag_from_new_step_preserved():
    current = _spec(_step("dedup"))
    new = _spec({"type": "dedup", "enabled": False})
    result = _merge_specs(current, new)
    assert result["steps"][0].get("enabled") is False


# ---------------------------------------------------------------------------
# Weitere Felder der neuen Spec werden durchgereicht
# ---------------------------------------------------------------------------


def test_additional_spec_fields_passed_through():
    current = _spec(_step("split"))
    new = {"steps": [_step("train_decision_tree")], "metadata": {"note": "test"}}
    result = _merge_specs(current, new)
    assert result.get("metadata") == {"note": "test"}


# ---------------------------------------------------------------------------
# Step ohne type-Feld wird nicht ignoriert sondern angehängt
# ---------------------------------------------------------------------------


def test_step_without_type_appended():
    current = _spec(_step("split"))
    bad_step = {"params": {"foo": 1}}  # kein "type"
    new = {"steps": [bad_step]}
    result = _merge_specs(current, new)
    # Wird angehängt, nicht still verworfen
    assert bad_step in result["steps"]


# ---------------------------------------------------------------------------
# Unveränderlichkeit: current_spec wird nicht mutiert
# ---------------------------------------------------------------------------


def test_current_spec_not_mutated():
    current = _spec(_step("split"))
    original_steps = list(current["steps"])
    new = _spec(_step("train_decision_tree"))
    _merge_specs(current, new)
    assert current["steps"] == original_steps


# ---------------------------------------------------------------------------
# Spalten-Merge: impute_missing mit gleicher Strategie → Spalten zusammenführen
# ---------------------------------------------------------------------------


def test_impute_same_strategy_columns_merged():
    """Zwei impute_missing-Steps mit gleicher Strategie → Spalten zusammenführen."""
    current = _spec(_step("impute_missing", strategy="median", columns=["windspeed"]))
    new = _spec(_step("impute_missing", strategy="median", columns=["cnt"]))
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"]["columns"] == ["windspeed", "cnt"]


def test_impute_columns_deduplication():
    """Doppelt genannte Spalte wird nur einmal aufgenommen."""
    current = _spec(_step("impute_missing", strategy="median", columns=["windspeed"]))
    new = _spec(_step("impute_missing", strategy="median", columns=["windspeed", "cnt"]))
    result = _merge_specs(current, new)
    assert result["steps"][0]["params"]["columns"] == ["windspeed", "cnt"]


def test_impute_different_strategy_adds_new_step():
    """Unterschiedliche Strategie → separater Step, kein Ersetzen."""
    current = _spec(_step("impute_missing", strategy="median", columns=["windspeed"]))
    new = _spec(_step("impute_missing", strategy="mean", columns=["cnt"]))
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 2
    types_and_strategies = [
        (s["type"], s["params"]["strategy"]) for s in result["steps"]
    ]
    assert ("impute_missing", "median") in types_and_strategies
    assert ("impute_missing", "mean") in types_and_strategies


def test_impute_no_columns_replaces():
    """Neuer Step ohne explizite Spalten (= alle) → ersetzt bestehenden Step."""
    current = _spec(_step("impute_missing", strategy="median", columns=["windspeed"]))
    new = _spec(_step("impute_missing", strategy="median"))
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"].get("columns") is None


def test_impute_existing_no_columns_new_with_columns_replaces():
    """Bestehender Step ohne Spalten + neuer Step mit Spalten → ersetzen."""
    current = _spec(_step("impute_missing", strategy="median"))
    new = _spec(_step("impute_missing", strategy="median", columns=["cnt"]))
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"]["columns"] == ["cnt"]


# ---------------------------------------------------------------------------
# Spalten-Merge: cast_dtype mit dict-Columns → dict-Merge (kein TypeError)
# ---------------------------------------------------------------------------


def test_cast_dtype_new_column_added_to_existing():
    """cast_dtype: neues Spalten-Mapping wird zum bestehenden hinzugefügt."""
    current = _spec({"type": "cast_dtype", "params": {"columns": {"windspeed": "object"}}})
    new = _spec({"type": "cast_dtype", "params": {"columns": {"cnt": "float64"}}})
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"]["columns"] == {"windspeed": "object", "cnt": "float64"}


def test_cast_dtype_same_column_new_type_overwrites():
    """cast_dtype: Neuer Typ für bestehende Spalte überschreibt alten (explizite Nutzeranforderung)."""
    current = _spec({"type": "cast_dtype", "params": {"columns": {"windspeed": "object"}}})
    new = _spec({"type": "cast_dtype", "params": {"columns": {"windspeed": "float64"}}})
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"]["columns"] == {"windspeed": "float64"}


def test_cast_dtype_mixed_columns_merged_correctly():
    """cast_dtype: Mix aus neuen und bestehenden Spalten wird korrekt zusammengeführt."""
    current = _spec({"type": "cast_dtype", "params": {"columns": {"windspeed": "object", "season": "category"}}})
    new = _spec({"type": "cast_dtype", "params": {"columns": {"cnt": "float64", "season": "int64"}}})
    result = _merge_specs(current, new)
    merged_cols = result["steps"][0]["params"]["columns"]
    assert merged_cols == {"windspeed": "object", "season": "int64", "cnt": "float64"}


# ---------------------------------------------------------------------------
# cast_dtype-Reihenfolge vor encode_categorical (Bug 1.12 – Problem B)
# ---------------------------------------------------------------------------


def test_cast_dtype_inserted_before_encode_categorical():
    """cast_dtype als neuer Step → vor encode_categorical eingefügt, nicht dahinter."""
    current = _spec(_step("encode_categorical", method="onehot", columns=["season"]))
    new = _spec({"type": "cast_dtype", "params": {"columns": {"season": "category"}}})
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    assert types == ["cast_dtype", "encode_categorical"]


def test_cast_dtype_before_encode_categorical_with_intermediate_steps():
    """cast_dtype → vor encode_categorical, andere Steps bleiben an ihrer Position."""
    current = _spec(
        _step("impute_missing", strategy="median", columns=["windspeed"]),
        _step("encode_categorical", method="onehot", columns=["season"]),
        _step("split", test_size=0.2),
    )
    new = _spec({"type": "cast_dtype", "params": {"columns": {"season": "category"}}})
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    assert types == ["impute_missing", "cast_dtype", "encode_categorical", "split"]


def test_cast_dtype_without_encode_categorical_appended_normally():
    """cast_dtype ohne encode_categorical in Spec → normales Append-Verhalten."""
    current = _spec(_step("dedup"), _step("split"))
    new = _spec({"type": "cast_dtype", "params": {"columns": {"season": "category"}}})
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    assert types == ["dedup", "split", "cast_dtype"]


def test_cast_dtype_before_encode_full_scenario():
    """Reproduziert den Bug-1.12-Szenario vollständig.

    Ablauf:
    1. Spec enthält encode_categorical (season=int64 → übersprungen)
    2. User: cast_dtype wandelt season auf category
    3. Merge erzeugt korrekte Reihenfolge: cast_dtype → encode_categorical
    """
    # State nach Run 1: encode_categorical in Spec, aber season=int64 → übersprungen
    current = _spec(_step("encode_categorical", method="onehot", columns=["season"]))
    # User: "Wandle season auf category"
    cast_step = {"type": "cast_dtype", "params": {"columns": {"season": "category"}}}
    new = _spec(cast_step)
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    # cast_dtype muss VOR encode_categorical kommen
    assert types.index("cast_dtype") < types.index("encode_categorical")


def test_cast_dtype_replaces_existing_cast_when_encode_present():
    """cast_dtype ersetzt bestehenden cast_dtype-Step (kein Einfügen), auch mit encode_categorical."""
    current = _spec(
        {"type": "cast_dtype", "params": {"columns": {"season": "object"}}},
        _step("encode_categorical", method="onehot", columns=["season"]),
    )
    new = _spec({"type": "cast_dtype", "params": {"columns": {"season": "category"}}})
    result = _merge_specs(current, new)
    types = [s["type"] for s in result["steps"]]
    # cast_dtype war bereits vorhanden → ersetzt (nicht erneut eingefügt)
    assert types == ["cast_dtype", "encode_categorical"]
    assert result["steps"][0]["params"]["columns"] == {"season": "category"}


def test_cast_dtype_no_columns_in_new_replaces():
    """cast_dtype: Neuer Step ohne columns → ersetzt bestehenden."""
    current = _spec({"type": "cast_dtype", "params": {"columns": {"windspeed": "object"}}})
    new = _spec({"type": "cast_dtype", "params": {}})
    result = _merge_specs(current, new)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["params"] == {}
