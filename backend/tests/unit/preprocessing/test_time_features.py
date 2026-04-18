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
    step = TimeFeatureEncodingStep(params={"column": "dteday", "drop_original": True})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "dteday" not in result_train.columns


def test_transform_dteday_removed_from_test(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday", "drop_original": True})
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
    step = TimeFeatureEncodingStep(params={"column": "event_date", "drop_original": True})
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
    step = TimeFeatureEncodingStep(params={"column": "dteday", "drop_original": True})
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert "dropped_column" in meta
    assert meta["dropped_column"] == "dteday"


# ---------------------------------------------------------------------------
# features-Parameter — day_of_month
# ---------------------------------------------------------------------------


def test_day_of_month_value_correct(df_with_dates):
    """day_of_month muss den korrekten Tageswert liefern."""
    step = TimeFeatureEncodingStep(params={"column": "dteday", "features": ["day_of_month"]})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "day_of_month" in result_train.columns
    assert result_train["day_of_month"].iloc[0] == 6   # 2020-01-06
    assert result_train["day_of_month"].iloc[1] == 10  # 2020-03-10
    assert result_train["day_of_month"].iloc[2] == 15  # 2020-07-15
    assert result_train["day_of_month"].iloc[3] == 25  # 2020-12-25


def test_day_of_month_present_in_metadata(df_with_dates):
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "features": ["weekday", "month", "day_of_month"]}
    )
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert "day_of_month" in meta["derived_features"]


# ---------------------------------------------------------------------------
# features-Parameter — benutzerdefinierte Feature-Listen
# ---------------------------------------------------------------------------


def test_features_custom_list_only_requested_columns_created(df_with_dates):
    """Nur die angeforderten Features werden erzeugt."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "features": ["year", "quarter"]}
    )
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "year" in result_train.columns
    assert "quarter" in result_train.columns
    assert "weekday" not in result_train.columns
    assert "month" not in result_train.columns
    assert "day_of_month" not in result_train.columns


def test_features_year_value_correct(df_with_dates):
    step = TimeFeatureEncodingStep(params={"column": "dteday", "features": ["year"]})
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert result_train["year"].iloc[0] == 2020


def test_features_all_supported_features(df_with_dates):
    """Alle fünf unterstützten Features gleichzeitig erzeugen."""
    all_features = ["weekday", "month", "day_of_month", "year", "quarter"]
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "features": all_features}
    )
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    for feat in all_features:
        assert feat in result_train.columns


def test_features_unknown_feature_ignored(df_with_dates):
    """Unbekannte Feature-Namen werden still ignoriert, kein Fehler."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "features": ["weekday", "unknown_feature"]}
    )
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "weekday" in result_train.columns
    assert "unknown_feature" not in result_train.columns


def test_features_metadata_reflects_requested_list(df_with_dates):
    """get_metadata() gibt genau die angeforderte Feature-Liste zurück."""
    requested = ["month", "day_of_month", "year"]
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "features": requested}
    )
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert meta["derived_features"] == requested


# ---------------------------------------------------------------------------
# drop_original-Parameter
# ---------------------------------------------------------------------------


def test_drop_original_false_keeps_column(df_with_dates):
    """Bei drop_original=False bleibt die Original-Spalte erhalten."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "drop_original": False}
    )
    step.fit(df_with_dates)
    result_train, result_test = step.transform(df_with_dates, df_with_dates.copy())
    assert "dteday" in result_train.columns
    assert "dteday" in result_test.columns


def test_drop_original_false_features_still_added(df_with_dates):
    """Bei drop_original=False werden die Zeitfeatures trotzdem hinzugefügt."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "drop_original": False}
    )
    step.fit(df_with_dates)
    result_train, _ = step.transform(df_with_dates, df_with_dates.copy())
    assert "weekday" in result_train.columns
    assert "month" in result_train.columns


def test_drop_original_false_metadata_has_no_dropped_column(df_with_dates):
    """Bei drop_original=False enthält get_metadata() kein dropped_column-Feld."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "drop_original": False}
    )
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert "dropped_column" not in meta


def test_drop_original_true_explicit_metadata_has_dropped_column(df_with_dates):
    """Bei explizitem drop_original=True enthält get_metadata() dropped_column."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "drop_original": True}
    )
    step.fit(df_with_dates)
    meta = step.get_metadata()
    assert meta.get("dropped_column") == "dteday"


# ---------------------------------------------------------------------------
# generate_artifact
# ---------------------------------------------------------------------------


def test_generate_artifact_before_transform_returns_none(df_with_dates, tmp_path):
    """Vor transform() gibt generate_artifact() None zurück."""
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    result = step.generate_artifact(str(tmp_path), "run-001")
    assert result is None


def test_generate_artifact_creates_csv(df_with_dates, tmp_path):
    """Nach transform() erzeugt generate_artifact() eine CSV-Datei."""
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    step.transform(df_with_dates, df_with_dates.copy())
    result = step.generate_artifact(str(tmp_path), "run-001")
    assert result is not None
    assert len(result) == 1
    assert result[0]["type"] == "time_features_result"
    assert (tmp_path / "run-001_time_features.csv").exists()


def test_generate_artifact_csv_contains_derived_features(df_with_dates, tmp_path):
    """Die Artefakt-CSV enthält die abgeleiteten Feature-Spalten."""
    step = TimeFeatureEncodingStep(
        params={"column": "dteday", "features": ["weekday", "month", "day_of_month"]}
    )
    step.fit(df_with_dates)
    step.transform(df_with_dates, df_with_dates.copy())
    step.generate_artifact(str(tmp_path), "run-002")
    df_artifact = pd.read_csv(tmp_path / "run-002_time_features.csv")
    assert "weekday" in df_artifact.columns
    assert "month" in df_artifact.columns
    assert "day_of_month" in df_artifact.columns


def test_generate_artifact_creates_output_directory(df_with_dates, tmp_path):
    """generate_artifact() erstellt den Ausgabeordner wenn nötig."""
    nested_path = tmp_path / "nested" / "output"
    step = TimeFeatureEncodingStep(params={"column": "dteday"})
    step.fit(df_with_dates)
    step.transform(df_with_dates, df_with_dates.copy())
    step.generate_artifact(str(nested_path), "run-003")
    assert (nested_path / "run-003_time_features.csv").exists()
