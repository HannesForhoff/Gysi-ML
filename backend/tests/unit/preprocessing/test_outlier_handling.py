"""Unit-Tests für OutlierHandlingStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.outlier_handling import OutlierHandlingStep


@pytest.fixture
def df_train_iqr():
    # Werte ohne Ausreißer: Q1=2, Q3=4, IQR=2, Grenzen=[-1, 7]
    return pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})


@pytest.fixture
def df_test_with_outlier():
    # Enthält Ausreißer: -10 und 100
    return pd.DataFrame({"v": [-10.0, 3.0, 100.0]})


# ---------------------------------------------------------------------------
# IQR — fit
# ---------------------------------------------------------------------------


def test_fit_iqr_stores_bounds():
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df)
    assert "v" in step._bounds
    lower, upper = step._bounds["v"]
    assert lower < 1.0
    assert upper > 5.0


def test_fit_iqr_uses_train_data_only():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    train_bounds = step._bounds.copy()
    # Kein erneutes fit auf Test
    step.transform(df_train, pd.DataFrame({"v": [1.0, 999.0]}))
    assert step._bounds == train_bounds


# ---------------------------------------------------------------------------
# IQR — transform / capping
# ---------------------------------------------------------------------------


def test_transform_iqr_caps_outliers(df_test_with_outlier):
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test_with_outlier)
    lower, upper = step._bounds["v"]
    assert result_test["v"].min() >= lower
    assert result_test["v"].max() <= upper


def test_transform_iqr_no_outliers_unchanged(df_train_iqr):
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train_iqr)
    df_test = pd.DataFrame({"v": [2.0, 3.0, 4.0]})
    _, result_test = step.transform(df_train_iqr, df_test)
    pd.testing.assert_frame_equal(result_test, df_test)


# ---------------------------------------------------------------------------
# IQR — metadata
# ---------------------------------------------------------------------------


def test_metadata_iqr_counts_treated():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    df_test = pd.DataFrame({"v": [-10.0, 3.0, 100.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    step.transform(df_train, df_test)
    meta = step.get_metadata()
    assert meta["outliers_treated"]["v"] == 2  # -10 und 100 in test


def test_metadata_iqr_zero_when_no_outliers(df_train_iqr):
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train_iqr)
    df_test = pd.DataFrame({"v": [2.0, 3.0]})
    step.transform(df_train_iqr, df_test)
    assert step.get_metadata()["outliers_treated"]["v"] == 0


# ---------------------------------------------------------------------------
# IQR — metadata (Bug 1.3: dict-Typ, bounds, q1/q3)
# ---------------------------------------------------------------------------


def test_metadata_iqr_outliers_treated_is_dict():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    df_test = pd.DataFrame({"v": [-10.0, 3.0, 100.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    step.transform(df_train, df_test)
    assert isinstance(step.get_metadata()["outliers_treated"], dict)


def test_metadata_iqr_bounds_present():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    step.transform(df_train, df_train)
    meta = step.get_metadata()
    assert "bounds" in meta
    assert "v" in meta["bounds"]
    b = meta["bounds"]["v"]
    assert "lower" in b and "upper" in b
    assert "q1" in b and "q3" in b


def test_metadata_iqr_q1_q3_values():
    # Für [1,2,3,4,5]: Q1=2.0, Q3=4.0, IQR=2.0 → lower=-1.0, upper=7.0
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    step.transform(df_train, df_train)
    b = step.get_metadata()["bounds"]["v"]
    assert b["q1"] == pytest.approx(2.0)
    assert b["q3"] == pytest.approx(4.0)
    assert b["lower"] == pytest.approx(-1.0)
    assert b["upper"] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# Bug 1.9 — columns-Parameter
# ---------------------------------------------------------------------------


def test_columns_param_restricts_to_specified_columns():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [10.0, 20.0, 30.0, 40.0, 50.0]})
    step = OutlierHandlingStep(params={"method": "iqr", "columns": ["a"]})
    step.fit(df)
    assert "a" in step._bounds
    assert "b" not in step._bounds


def test_columns_param_nonexistent_raises():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    step = OutlierHandlingStep(params={"method": "iqr", "columns": ["x"]})
    with pytest.raises(ValueError, match="nicht gefunden"):
        step.fit(df)


def test_columns_param_non_numeric_raises():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": ["x", "y", "z"]})
    step = OutlierHandlingStep(params={"method": "iqr", "columns": ["b"]})
    with pytest.raises(ValueError, match="Nicht-numerische"):
        step.fit(df)


def test_columns_param_empty_uses_all_numeric():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "iqr", "columns": []})
    step.fit(df)
    assert "a" in step._bounds
    assert "b" in step._bounds


# ---------------------------------------------------------------------------
# Bug 1.9 — IQR=0-Guard (binäre / konstante Spalten)
# ---------------------------------------------------------------------------


def test_binary_col_skipped_when_iqr_zero():
    # holiday: 7×0 und 1×1 → Q1=Q3=0 → IQR=0 → Spalte überspringen
    df = pd.DataFrame({"holiday": [0, 0, 0, 0, 0, 0, 0, 1], "cnt": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df)
    assert "holiday" not in step._bounds
    assert "holiday" in step._skipped_cols
    assert "cnt" in step._bounds


def test_metadata_contains_skipped_columns():
    # holiday: 4×0 und 1×1 → Q1=Q3=0 → IQR=0
    df = pd.DataFrame({"holiday": [0, 0, 0, 0, 1], "cnt": [100.0, 200.0, 300.0, 400.0, 500.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df)
    step.transform(df, df)
    meta = step.get_metadata()
    assert "skipped_columns" in meta
    assert "holiday" in meta["skipped_columns"]


def test_skipped_col_not_in_outliers_treated():
    df = pd.DataFrame({"holiday": [0, 0, 0, 0, 1], "cnt": [100.0, 200.0, 300.0, 400.0, 500.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df)
    step.transform(df, df)
    meta = step.get_metadata()
    assert "holiday" not in meta["outliers_treated"]


def test_no_skipped_columns_key_when_none_skipped():
    df = pd.DataFrame({"cnt": [100.0, 200.0, 300.0, 400.0, 500.0]})
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df)
    step.transform(df, df)
    meta = step.get_metadata()
    assert "skipped_columns" not in meta


def test_metadata_iqr_all_columns_in_outliers_treated():
    # Spalten die keine Ausreißer haben, sollen mit 0 im Dict erscheinen
    df_train = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [10.0, 20.0, 30.0, 40.0, 50.0]})
    df_test = pd.DataFrame({"a": [3.0], "b": [30.0]})  # keine Ausreißer
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train)
    step.transform(df_train, df_test)
    treated = step.get_metadata()["outliers_treated"]
    assert "a" in treated
    assert "b" in treated


# ---------------------------------------------------------------------------
# Z-Score — metadata (Bug 1.3: bounds mit mean/std, kein q1/q3)
# ---------------------------------------------------------------------------


def test_metadata_zscore_bounds_present():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "zscore", "zscore_threshold": 2.0})
    step.fit(df_train)
    step.transform(df_train, df_train)
    meta = step.get_metadata()
    assert "bounds" in meta
    b = meta["bounds"]["v"]
    assert "lower" in b and "upper" in b
    assert "mean" in b and "std" in b


def test_metadata_zscore_no_q1_q3():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "zscore"})
    step.fit(df_train)
    step.transform(df_train, df_train)
    b = step.get_metadata()["bounds"]["v"]
    assert "q1" not in b
    assert "q3" not in b


def test_metadata_zscore_outliers_treated_is_dict():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    df_test = pd.DataFrame({"v": [3.0, 999.0]})
    step = OutlierHandlingStep(params={"method": "zscore", "zscore_threshold": 2.0})
    step.fit(df_train)
    step.transform(df_train, df_test)
    treated = step.get_metadata()["outliers_treated"]
    assert isinstance(treated, dict)
    assert treated["v"] >= 1  # 999 ist definitiv ein Ausreißer


def test_fit_zscore_stores_stats():
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    step = OutlierHandlingStep(params={"method": "zscore"})
    step.fit(df)
    assert "v" in step._stats
    mean, std = step._stats["v"]
    assert mean == pytest.approx(3.0)
    assert std > 0


# ---------------------------------------------------------------------------
# Z-Score — transform / capping
# ---------------------------------------------------------------------------


def test_transform_zscore_caps_outlier():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    df_test = pd.DataFrame({"v": [3.0, 999.0]})
    step = OutlierHandlingStep(params={"method": "zscore", "zscore_threshold": 2.0})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test)
    mean, std = step._stats["v"]
    upper = mean + 2.0 * std
    assert result_test["v"].iloc[1] <= upper


def test_transform_zscore_no_outlier_unchanged():
    df_train = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    df_test = pd.DataFrame({"v": [2.0, 3.0]})
    step = OutlierHandlingStep(params={"method": "zscore", "zscore_threshold": 3.0})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test)
    pd.testing.assert_frame_equal(result_test, df_test)


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_is_true():
    assert not getattr(OutlierHandlingStep, 'requires_split', False)


def test_default_method():
    step = OutlierHandlingStep()
    assert step.method == "iqr"


def test_default_zscore_threshold():
    step = OutlierHandlingStep()
    assert step.zscore_threshold == pytest.approx(3.0)
