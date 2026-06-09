"""Unit-Tests für DropColumnsStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.drop_columns import DropColumnsStep
from gysi_ml.steps.registry import get_step_class


@pytest.fixture
def df():
    return pd.DataFrame({
        "season": [1, 2, 3],
        "temp": [0.3, 0.4, 0.5],
        "windspeed": [0.1, 0.2, 0.3],
        "cnt": [100, 200, 300],
    })


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------


def test_step_is_registered():
    cls = get_step_class("drop_columns")
    assert cls is DropColumnsStep


# ---------------------------------------------------------------------------
# fit – Fehlerbehandlung
# ---------------------------------------------------------------------------


def test_fit_raises_if_no_columns(df):
    step = DropColumnsStep(params={})
    with pytest.raises(ValueError, match="Keine Spalten angegeben"):
        step.fit(df)


def test_fit_raises_if_target_column_in_list(df):
    step = DropColumnsStep(params={"columns": ["cnt"]})
    with pytest.raises(ValueError, match="Zielspalte.*cnt.*darf nicht entfernt werden"):
        step.fit(df)


def test_fit_raises_if_column_not_found(df):
    step = DropColumnsStep(params={"columns": ["nonexistent"]})
    with pytest.raises(ValueError, match="nicht im Datensatz gefunden"):
        step.fit(df)


# ---------------------------------------------------------------------------
# transform – Normalfall
# ---------------------------------------------------------------------------


def test_transform_drops_specified_columns(df):
    step = DropColumnsStep(params={"columns": ["season", "windspeed"]})
    step.fit(df)
    result_train, result_test = step.transform(df, df.copy())
    assert "season" not in result_train.columns
    assert "windspeed" not in result_train.columns
    assert "temp" in result_train.columns
    assert "cnt" in result_train.columns


def test_transform_does_not_modify_original(df):
    original_cols = list(df.columns)
    step = DropColumnsStep(params={"columns": ["temp"]})
    step.fit(df)
    step.transform(df, df.copy())
    assert list(df.columns) == original_cols


def test_transform_applies_to_test_as_well(df):
    step = DropColumnsStep(params={"columns": ["season"]})
    step.fit(df)
    _, result_test = step.transform(df, df.copy())
    assert "season" not in result_test.columns


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


def test_get_metadata_returns_dropped_columns(df):
    step = DropColumnsStep(params={"columns": ["temp", "windspeed"]})
    step.fit(df)
    step.transform(df, df.copy())
    meta = step.get_metadata()
    assert set(meta["dropped_columns"]) == {"temp", "windspeed"}
