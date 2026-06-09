"""Unit-Tests für LinearRegressionStep."""
import numpy as np
import pandas as pd
import pytest

from gysi_ml.steps.modeling.linear_regression import LinearRegressionStep
from gysi_ml.steps.registry import get_step_class
from gysi_ml.core.capabilities import get_capabilities


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    rng = np.random.default_rng(42)
    n = 100
    df = pd.DataFrame({
        "feature_a": rng.uniform(0, 1, n),
        "feature_b": rng.uniform(0, 10, n),
        "cnt": rng.integers(50, 500, n).astype(float),
    })
    return df


@pytest.fixture
def split_data(sample_data):
    train = sample_data.iloc[:80].reset_index(drop=True)
    test = sample_data.iloc[80:].reset_index(drop=True)
    return train, test


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_step_is_registered():
    cls = get_step_class("train_linear_regression")
    assert cls is LinearRegressionStep


def test_transform_before_fit_raises_error(split_data):
    _, df_test = split_data
    step = LinearRegressionStep(params={})
    with pytest.raises(RuntimeError, match="transform\\(\\) wurde vor fit\\(\\) aufgerufen"):
        step.transform(pd.DataFrame(), df_test)


def test_fit_uses_numeric_features_only(split_data):
    df_train, _ = split_data
    step = LinearRegressionStep(params={})
    step.fit(df_train)
    assert step.model.n_features_in_ == len(df_train.select_dtypes(include="number").columns) - 1


def test_transform_returns_unchanged_dataframes(split_data):
    df_train, df_test = split_data
    step = LinearRegressionStep(params={})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert result_train.shape == df_train.shape
    assert result_test.shape == df_test.shape
    pd.testing.assert_frame_equal(result_train, df_train)
    pd.testing.assert_frame_equal(result_test, df_test)


def test_metrics_are_computed(split_data):
    df_train, df_test = split_data
    step = LinearRegressionStep(params={})
    step.fit(df_train)
    step.transform(df_train, df_test)
    metadata = step.get_metadata()
    metrics = metadata["metrics"]
    for key in ("rmse", "mae", "r2", "train_rmse", "train_mae", "train_r2"):
        assert key in metrics, f"Metrik '{key}' fehlt"
        assert isinstance(metrics[key], float)
    assert metrics["r2"] <= 1.0


def test_deterministic_results(split_data):
    """LinearRegression ist deterministisch — zwei Runs liefern identische Metriken."""
    df_train, df_test = split_data

    step1 = LinearRegressionStep(params={})
    step1.fit(df_train)
    step1.transform(df_train, df_test)

    step2 = LinearRegressionStep(params={})
    step2.fit(df_train)
    step2.transform(df_train, df_test)

    assert step1.get_metadata()["metrics"]["rmse"] == pytest.approx(
        step2.get_metadata()["metrics"]["rmse"]
    )


def test_get_metadata_contains_feature_names(split_data):
    df_train, df_test = split_data
    step = LinearRegressionStep(params={})
    step.fit(df_train)
    step.transform(df_train, df_test)
    meta = step.get_metadata()
    assert set(meta["feature_names"]) == {"feature_a", "feature_b"}
    assert meta["target"] == "cnt"


def test_capabilities_contains_linear_regression():
    caps = get_capabilities()
    step_types = [s["type"] for s in caps["steps"]]
    assert "train_linear_regression" in step_types


def test_fit_raises_on_nan_target(split_data):
    df_train, _ = split_data
    df_train_nan = df_train.copy()
    df_train_nan.loc[0, "cnt"] = float("nan")
    step = LinearRegressionStep(params={})
    with pytest.raises(ValueError, match="Zielspalte"):
        step.fit(df_train_nan)
