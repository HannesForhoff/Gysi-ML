"""Unit-Tests für ImputationStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.imputation import ImputationStep


@pytest.fixture
def df_with_missing():
    return pd.DataFrame({
        "a": [1.0, None, 3.0, 5.0],
        "b": [2.0, 4.0, None, 6.0],
    })


@pytest.fixture
def df_no_missing():
    return pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})


# ---------------------------------------------------------------------------
# fit / transform median
# ---------------------------------------------------------------------------


def test_fit_stores_median(df_with_missing):
    step = ImputationStep(params={"strategy": "median"})
    step.fit(df_with_missing)
    # median of [1,3,5] = 3.0
    assert step._fill_values["a"] == pytest.approx(3.0)


def test_transform_median_fills_missing(df_with_missing):
    step = ImputationStep(params={"strategy": "median"})
    step.fit(df_with_missing)
    result_train, _ = step.transform(df_with_missing, df_with_missing.copy())
    assert result_train["a"].isna().sum() == 0
    assert result_train["b"].isna().sum() == 0


def test_transform_median_uses_train_params_on_test():
    df_train = pd.DataFrame({"x": [10.0, 20.0, 30.0]})
    df_test = pd.DataFrame({"x": [None, 50.0]})
    step = ImputationStep(params={"strategy": "median"})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test)
    # median of train [10,20,30] = 20 — not the test median
    assert result_test["x"].iloc[0] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Strategie: mean
# ---------------------------------------------------------------------------


def test_fit_stores_mean():
    df = pd.DataFrame({"v": [1.0, 3.0, 5.0, None]})
    step = ImputationStep(params={"strategy": "mean"})
    step.fit(df)
    assert step._fill_values["v"] == pytest.approx(3.0)


def test_transform_mean_fills_correctly():
    df = pd.DataFrame({"v": [1.0, 3.0, 5.0, None]})
    step = ImputationStep(params={"strategy": "mean"})
    step.fit(df)
    result, _ = step.transform(df, df.copy())
    assert not result["v"].isna().any()
    assert result["v"].iloc[3] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Strategie: most_frequent
# ---------------------------------------------------------------------------


def test_fit_stores_most_frequent():
    df = pd.DataFrame({"v": [1.0, 2.0, 2.0, None, 3.0]})
    step = ImputationStep(params={"strategy": "most_frequent"})
    step.fit(df)
    assert step._fill_values["v"] == pytest.approx(2.0)


def test_transform_most_frequent_fills():
    df = pd.DataFrame({"v": [1.0, 2.0, 2.0, None]})
    step = ImputationStep(params={"strategy": "most_frequent"})
    step.fit(df)
    result, _ = step.transform(df, df.copy())
    assert result["v"].iloc[3] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_metadata_counts_imputed(df_with_missing):
    step = ImputationStep(params={"strategy": "median"})
    step.fit(df_with_missing)
    step.transform(df_with_missing, df_with_missing.copy())
    meta = step.get_metadata()["imputed_values_per_column"]
    # df_with_missing hat je 1 NaN in a und b, bei train UND test (copy) je 1+1=2
    assert meta["a"] == 2
    assert meta["b"] == 2


def test_metadata_zero_when_no_missing(df_no_missing):
    step = ImputationStep(params={"strategy": "median"})
    step.fit(df_no_missing)
    step.transform(df_no_missing, df_no_missing.copy())
    meta = step.get_metadata()["imputed_values_per_column"]
    assert all(v == 0 for v in meta.values())


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_is_true():
    assert ImputationStep.requires_split is True


def test_default_strategy():
    step = ImputationStep()
    assert step.strategy == "median"
