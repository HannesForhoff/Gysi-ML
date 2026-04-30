"""Unit-Tests für PlotDistributionStep."""
import os

import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.plot_distribution import PlotDistributionStep


@pytest.fixture
def df_simple():
    return pd.DataFrame(
        {
            "cnt": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            "temp": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            "season": [1, 1, 2, 2, 3, 3, 4, 4, 1, 2],
            "weathersit": [1, 2, 1, 3, 2, 1, 4, 2, 1, 3],
        }
    )


@pytest.fixture
def df_with_nulls():
    return pd.DataFrame(
        {
            "cnt": [10, None, 30, None, 50],
            "season": [1, 2, None, 1, 2],
        }
    )


# ---------------------------------------------------------------------------
# fit – Validierung
# ---------------------------------------------------------------------------


def test_fit_missing_feature_param_raises():
    step = PlotDistributionStep(params={})
    df = pd.DataFrame({"cnt": [1, 2, 3]})
    with pytest.raises(ValueError, match="'feature' ist erforderlich"):
        step.fit(df)


def test_fit_unknown_feature_raises(df_simple):
    step = PlotDistributionStep(params={"feature": "not_existing"})
    with pytest.raises(ValueError, match="nicht im Datensatz gefunden"):
        step.fit(df_simple)


def test_fit_unknown_group_by_raises(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt", "group_by": "not_existing"})
    with pytest.raises(ValueError, match="group_by-Spalte"):
        step.fit(df_simple)


def test_fit_valid_univariate_does_not_raise(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt"})
    step.fit(df_simple)  # kein Fehler


def test_fit_valid_grouped_does_not_raise(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt", "group_by": "season"})
    step.fit(df_simple)  # kein Fehler


# ---------------------------------------------------------------------------
# transform – Daten unverändert
# ---------------------------------------------------------------------------


def test_transform_does_not_change_data(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt"})
    step.fit(df_simple)
    empty = pd.DataFrame(columns=df_simple.columns)
    result_train, result_test = step.transform(df_simple, empty)
    assert list(result_train["cnt"]) == list(df_simple["cnt"])


def test_transform_returns_same_dataframes(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt", "group_by": "season"})
    step.fit(df_simple)
    empty = pd.DataFrame(columns=df_simple.columns)
    train_out, test_out = step.transform(df_simple, empty)
    assert len(train_out) == len(df_simple)
    assert len(test_out) == 0


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


def test_metadata_univariate(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt"})
    step.fit(df_simple)
    step.transform(df_simple, pd.DataFrame(columns=df_simple.columns))
    meta = step.get_metadata()
    assert meta["feature"] == "cnt"
    assert meta["n_values"] == 10
    assert "mean" in meta
    assert "group_by" not in meta


def test_metadata_grouped(df_simple):
    step = PlotDistributionStep(params={"feature": "cnt", "group_by": "season"})
    step.fit(df_simple)
    step.transform(df_simple, pd.DataFrame(columns=df_simple.columns))
    meta = step.get_metadata()
    assert meta["feature"] == "cnt"
    assert meta["group_by"] == "season"


def test_metadata_with_nulls(df_with_nulls):
    step = PlotDistributionStep(params={"feature": "cnt"})
    step.fit(df_with_nulls)
    step.transform(df_with_nulls, pd.DataFrame(columns=df_with_nulls.columns))
    meta = step.get_metadata()
    assert meta["n_values"] == 3  # 2 NaN-Werte werden ausgelassen


# ---------------------------------------------------------------------------
# generate_artifact
# ---------------------------------------------------------------------------


def test_generate_artifact_univariate_creates_png(df_simple, tmp_path):
    step = PlotDistributionStep(params={"feature": "cnt"})
    step.fit(df_simple)
    step.transform(df_simple, pd.DataFrame(columns=df_simple.columns))
    result = step.generate_artifact(str(tmp_path), "test-run-id")
    assert result is not None
    assert result["type"] == "plot_distribution"
    assert os.path.isfile(result["file_path"])
    assert result["file_path"].endswith(".png")
    assert "cnt" in result["file_path"]


def test_generate_artifact_grouped_creates_png(df_simple, tmp_path):
    step = PlotDistributionStep(params={"feature": "cnt", "group_by": "season"})
    step.fit(df_simple)
    step.transform(df_simple, pd.DataFrame(columns=df_simple.columns))
    result = step.generate_artifact(str(tmp_path), "test-run-id")
    assert result is not None
    assert result["type"] == "plot_distribution"
    assert os.path.isfile(result["file_path"])
    assert "cnt" in result["file_path"]
    assert "season" in result["file_path"]


def test_generate_artifact_before_fit_returns_none(tmp_path):
    step = PlotDistributionStep(params={"feature": "cnt"})
    result = step.generate_artifact(str(tmp_path), "test-run-id")
    assert result is None


def test_generate_artifact_creates_directory(df_simple, tmp_path):
    new_dir = str(tmp_path / "nested" / "artifacts")
    step = PlotDistributionStep(params={"feature": "temp"})
    step.fit(df_simple)
    step.transform(df_simple, pd.DataFrame(columns=df_simple.columns))
    result = step.generate_artifact(new_dir, "run-xyz")
    assert os.path.isdir(new_dir)
    assert result is not None
