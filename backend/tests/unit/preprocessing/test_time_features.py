"""Unit-Tests für TimeFeatureEncodingStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.time_features import TimeFeatureEncodingStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_with_dates():
    return pd.DataFrame({
        "dteday": [
            "2020-01-06",  # Montag → weekday=0, month=1
            "2020-03-10",  # Dienstag → weekday=1, month=3

            "2020-07-15",  # Mittwoch → weekday=2, month=7
            "2020-12-25",  # Freitag → weekday=4, month=12
        ],
        "cnt": [100, 200, 300, 400],
    })


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_false():
    """TimeFeatureEncodingStep ist stateless → kein Split erforderlich."""
    assert TimeFeatureEncodingStep.requires_split is False


def test_description_set():
    assert TimeFeatureEncodingStep.description != ""


# ---------------------------------------------------------------------------
# fit — stateless (kein State gelernt)
# ---------------------------------------------------------------------------


def test_fit_does_not_raise(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)  # kein Fehler erwartet


def test_fit_no_state_changed(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    # _column bleibt wie parametrisiert
    assert step._column == "dteday"


# ---------------------------------------------------------------------------
# transform — weekday
# ---------------------------------------------------------------------------


def test_transform_weekday_monday_is_zero(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["weekday"].iloc[0] == 0  # 2020-01-06 ist Montag


def test_transform_weekday_tuesday_is_one(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["weekday"].iloc[1] == 1  # 2020-03-10 ist Dienstag


def test_transform_weekday_friday_is_four(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["weekday"].iloc[3] == 4  # 2020-12-25 ist Freitag


# ---------------------------------------------------------------------------
# transform — month
# ---------------------------------------------------------------------------


def test_transform_month_january_is_one(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["month"].iloc[0] == 1


def test_transform_month_december_is_twelve(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["month"].iloc[3] == 12


def test_transform_month_range_one_to_twelve(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["month"].min() >= 1
    assert result_train["month"].max() <= 12


# ---------------------------------------------------------------------------
# transform — original Spalte entfernt
# ---------------------------------------------------------------------------


def test_transform_dteday_removed_from_train(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "dteday" not in result_train.columns


def test_transform_dteday_removed_from_test(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    _, result_test = step.transform(df_with_dates, df_with_dates.copy())
    assert "dteday" not in result_test.columns


def test_transform_non_date_columns_preserved(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "cnt" in result_train.columns
    assert result_train["cnt"].tolist() == [100, 200, 300, 400]


# ---------------------------------------------------------------------------
# transform — fehlende Spalte (graceful handling)
# ---------------------------------------------------------------------------


def test_transform_missing_column_returns_unchanged():
    """Wenn die Datumsspalte nicht vorhanden ist → DataFrame unverändert."""
    df = pd.DataFrame({"cnt": [1, 2, 3]})
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df)
    result_train, result_test = step.transform(df, df.copy())
    assert "cnt" in result_train.columns
    assert "weekday" not in result_train.columns
    assert "month" not in result_train.columns


# ---------------------------------------------------------------------------
# Benutzerdefinierte Spalte
# ---------------------------------------------------------------------------


def test_transform_custom_column_name():
    df = pd.DataFrame({
        "event_date": ["2021-06-15"],  # Dienstag, Monat 6
        "val": [42],
    })
    step = TimeFeatureEncodingStep(params={"column": "event_date"})
    step.fit(df)
    result_train, _ = step.transform(df, df.copy())
    assert "event_date" not in result_train.columns
    assert "weekday" in result_train.columns
    assert "month" in result_train.columns
    assert result_train["month"].iloc[0] == 6


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


def test_metadata_derived_features(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert "derived_features" in meta
    assert "weekday" in meta["derived_features"]
    assert "month" in meta["derived_features"]


def test_metadata_dropped_column(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert "dropped_column" in meta
    assert meta["dropped_column"] == "dteday"
