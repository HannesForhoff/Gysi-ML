"""Unit-Tests für CastDtypeStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.cast_dtype import CastDtypeStep


@pytest.fixture
def df_base():
    return pd.DataFrame({
        "season": [1, 2, 3, 4] * 25,
        "temp": [0.24, 0.36, 0.45, 0.52] * 25,
        "cnt": [100, 200, 300, 400] * 25,
        "flag": [1, 0, 1, 0] * 25,
        "dteday": ["2011-01-01", "2011-01-02", "2011-01-03", "2011-01-04"] * 25,
    })


# ---------------------------------------------------------------------------
# Numerische Casts
# ---------------------------------------------------------------------------


def test_cast_int_to_float(df_base):
    step = CastDtypeStep(params={"columns": {"cnt": "float64"}})
    step.fit(df_base)
    train, test = step.transform(df_base, df_base.copy())
    assert str(train["cnt"].dtype) == "float64"
    assert str(test["cnt"].dtype) == "float64"


def test_cast_float_to_int(df_base):
    step = CastDtypeStep(params={"columns": {"temp": "float64"}})
    step.fit(df_base)
    train, _ = step.transform(df_base, df_base.copy())
    assert str(train["temp"].dtype) == "float64"


def test_cast_int_to_category(df_base):
    step = CastDtypeStep(params={"columns": {"season": "category"}})
    step.fit(df_base)
    train, test = step.transform(df_base, df_base.copy())
    assert str(train["season"].dtype) == "category"
    assert str(test["season"].dtype) == "category"


def test_cast_int_to_bool(df_base):
    step = CastDtypeStep(params={"columns": {"flag": "bool"}})
    step.fit(df_base)
    train, _ = step.transform(df_base, df_base.copy())
    assert str(train["flag"].dtype) == "bool"


def test_cast_int_to_str(df_base):
    step = CastDtypeStep(params={"columns": {"season": "str"}})
    step.fit(df_base)
    train, _ = step.transform(df_base, df_base.copy())
    assert str(train["season"].dtype) == "object"
    assert train["season"].iloc[0] == "1"


# ---------------------------------------------------------------------------
# Datetime Cast
# ---------------------------------------------------------------------------


def test_cast_str_to_datetime_auto(df_base):
    step = CastDtypeStep(params={"columns": {"dteday": "datetime64"}})
    step.fit(df_base)
    train, test = step.transform(df_base, df_base.copy())
    assert pd.api.types.is_datetime64_any_dtype(train["dteday"])
    assert pd.api.types.is_datetime64_any_dtype(test["dteday"])


def test_cast_str_to_datetime_with_format(df_base):
    step = CastDtypeStep(params={
        "columns": {"dteday": "datetime64"},
        "datetime_format": "%Y-%m-%d",
    })
    step.fit(df_base)
    train, _ = step.transform(df_base, df_base.copy())
    assert pd.api.types.is_datetime64_any_dtype(train["dteday"])
    assert train["dteday"].iloc[0] == pd.Timestamp("2011-01-01")


# ---------------------------------------------------------------------------
# Mehrere Spalten in einem Step
# ---------------------------------------------------------------------------


def test_multiple_columns(df_base):
    step = CastDtypeStep(params={"columns": {"season": "category", "cnt": "float64"}})
    step.fit(df_base)
    train, _ = step.transform(df_base, df_base.copy())
    assert str(train["season"].dtype) == "category"
    assert str(train["cnt"].dtype) == "float64"


# ---------------------------------------------------------------------------
# Metadaten
# ---------------------------------------------------------------------------


def test_get_metadata(df_base):
    step = CastDtypeStep(params={"columns": {"season": "category"}})
    step.fit(df_base)
    meta = step.get_metadata()
    assert meta == {"casts_applied": {"season": "category"}}


# ---------------------------------------------------------------------------
# Fehlerbehandlung
# ---------------------------------------------------------------------------


def test_error_missing_columns_param():
    step = CastDtypeStep(params={})
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(ValueError, match="'columns' fehlt"):
        step.fit(df)


def test_error_column_not_in_dataframe(df_base):
    step = CastDtypeStep(params={"columns": {"nicht_vorhanden": "int64"}})
    with pytest.raises(ValueError, match="nicht im Datensatz gefunden"):
        step.fit(df_base)


def test_error_unsupported_dtype(df_base):
    step = CastDtypeStep(params={"columns": {"season": "uint8"}})
    with pytest.raises(ValueError, match="Nicht unterstützte Zieldatentypen"):
        step.fit(df_base)


def test_error_impossible_cast_str_to_int():
    df = pd.DataFrame({"label": ["abc", "def", "ghi"]})
    step = CastDtypeStep(params={"columns": {"label": "int64"}})
    with pytest.raises(ValueError, match="kann nicht.*nach 'int64' konvertiert werden"):
        step.fit(df)


def test_error_impossible_cast_str_to_float():
    df = pd.DataFrame({"label": ["abc", "def", "ghi"]})
    step = CastDtypeStep(params={"columns": {"label": "float64"}})
    with pytest.raises(ValueError, match="kann nicht.*nach 'float64' konvertiert werden"):
        step.fit(df)


def test_error_impossible_datetime_with_bad_format(df_base):
    step = CastDtypeStep(params={
        "columns": {"dteday": "datetime64"},
        "datetime_format": "%d/%m/%Y",  # falsches Format für "2011-01-01"
    })
    with pytest.raises(ValueError, match="kann nicht.*nach 'datetime64' konvertiert werden"):
        step.fit(df_base)


# ---------------------------------------------------------------------------
# Original-DataFrame wird nicht verändert
# ---------------------------------------------------------------------------


def test_transform_does_not_mutate_original(df_base):
    original_dtype = str(df_base["season"].dtype)
    step = CastDtypeStep(params={"columns": {"season": "category"}})
    step.fit(df_base)
    step.transform(df_base, df_base.copy())
    assert str(df_base["season"].dtype) == original_dtype
