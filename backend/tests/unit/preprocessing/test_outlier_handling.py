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
    assert meta["outliers_treated"] == 2  # -10 und 100 in test


def test_metadata_iqr_zero_when_no_outliers(df_train_iqr):
    step = OutlierHandlingStep(params={"method": "iqr"})
    step.fit(df_train_iqr)
    df_test = pd.DataFrame({"v": [2.0, 3.0]})
    step.transform(df_train_iqr, df_test)
    assert step.get_metadata()["outliers_treated"] == 0


# ---------------------------------------------------------------------------
# Z-Score — fit
# ---------------------------------------------------------------------------


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
    assert OutlierHandlingStep.requires_split is True


def test_default_method():
    step = OutlierHandlingStep()
    assert step.method == "iqr"


def test_default_zscore_threshold():
    step = OutlierHandlingStep()
    assert step.zscore_threshold == pytest.approx(3.0)
