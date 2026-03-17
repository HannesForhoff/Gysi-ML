"""Unit-Tests für DecisionTreeStep (Story 2.1)."""
import numpy as np
import pandas as pd
import pytest

from gysi_ml.steps.modeling.decision_tree import DecisionTreeStep
from gysi_ml.steps.registry import get_step_class
from gysi_ml.core.capabilities import get_capabilities


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    """Kleiner synthetischer DataFrame mit cnt-Spalte."""
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
# T6 Tests
# ---------------------------------------------------------------------------

def test_transform_before_fit_raises_error(split_data):
    _, df_test = split_data
    step = DecisionTreeStep(params={})
    with pytest.raises(RuntimeError, match="transform\\(\\) wurde vor fit\\(\\) aufgerufen"):
        step.transform(pd.DataFrame(), df_test)


def test_step_is_registered():
    cls = get_step_class("train_decision_tree")
    assert cls is DecisionTreeStep


def test_fit_does_not_use_test_data(split_data):
    df_train, _ = split_data
    step = DecisionTreeStep(params={})
    step.fit(df_train)
    assert step.model.n_features_in_ == len(df_train.columns) - 1


def test_transform_returns_unchanged_dataframes(split_data):
    df_train, df_test = split_data
    step = DecisionTreeStep(params={})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert result_train.shape == df_train.shape
    assert result_test.shape == df_test.shape
    pd.testing.assert_frame_equal(result_train, df_train)
    pd.testing.assert_frame_equal(result_test, df_test)


def test_metrics_are_computed(split_data):
    df_train, df_test = split_data
    step = DecisionTreeStep(params={})
    step.fit(df_train)
    step.transform(df_train, df_test)
    metadata = step.get_metadata()
    metrics = metadata["metrics"]
    assert "rmse" in metrics and "mae" in metrics and "r2" in metrics
    assert isinstance(metrics["rmse"], float)
    assert isinstance(metrics["mae"], float)
    assert isinstance(metrics["r2"], float)
    assert metrics["r2"] <= 1.0  # R² ist nach oben durch 1 begrenzt; nach unten unbegrenzt


def test_default_random_state(split_data):
    df_train, df_test = split_data
    step1 = DecisionTreeStep(params={})
    step1.fit(df_train)
    step1.transform(df_train, df_test)
    metrics1 = step1.get_metadata()["metrics"]

    step2 = DecisionTreeStep(params={})
    step2.fit(df_train)
    step2.transform(df_train, df_test)
    metrics2 = step2.get_metadata()["metrics"]

    assert metrics1["rmse"] == pytest.approx(metrics2["rmse"])
    assert metrics1["r2"] == pytest.approx(metrics2["r2"])


def test_max_depth_parameter(split_data):
    df_train, df_test = split_data

    # max_depth=1 → Modell darf nur bis Tiefe 1 wachsen
    step_shallow = DecisionTreeStep(params={"max_depth": 1})
    step_shallow.fit(df_train)
    step_shallow.transform(df_train, df_test)
    assert step_shallow.model.get_depth() <= 1

    # max_depth=None → Baum wächst unbegrenzt, muss tiefer als 1 sein (genügend Daten)
    step_deep = DecisionTreeStep(params={"max_depth": None})
    step_deep.fit(df_train)
    assert step_deep.model.get_depth() > 1


def test_capabilities_contains_decision_tree():
    caps = get_capabilities()
    step_types = [s["type"] for s in caps["steps"]]
    assert "train_decision_tree" in step_types
