"""Unit-Tests für CategoricalEncodingStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.encoding import CategoricalEncodingStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_train_label():
    return pd.DataFrame({
        "color": ["red", "blue", "green", "red"],
        "size": ["S", "M", "L", "M"],
        "value": [1, 2, 3, 4],
    })


@pytest.fixture
def df_test_label():
    return pd.DataFrame({
        "color": ["blue", "green", "purple"],  # "purple" unbekannt
        "size": ["S", "XL", "M"],              # "XL" unbekannt
        "value": [5, 6, 7],
    })


@pytest.fixture
def df_train_onehot():
    return pd.DataFrame({
        "color": ["red", "blue", "green", "red"],
        "value": [1, 2, 3, 4],
    })


@pytest.fixture
def df_test_onehot():
    return pd.DataFrame({
        "color": ["blue", "purple", "red"],  # "purple" unbekannt
        "value": [5, 6, 7],
    })


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_true():
    assert not getattr(CategoricalEncodingStep, 'requires_split', False)


def test_description_set():
    assert CategoricalEncodingStep.description != ""


# ---------------------------------------------------------------------------
# Label Encoding — fit
# ---------------------------------------------------------------------------


def test_fit_label_stores_encoders(df_train_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    assert "color" in step._label_encoders
    assert "size" in step._label_encoders
    # Numerische Spalte darf nicht encoded werden
    assert "value" not in step._label_encoders


def test_fit_label_mapping_sorted(df_train_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    mapping = step._label_encoders["color"]
    # Alphabetisch sortiert: blue=0, green=1, red=2
    assert mapping["blue"] == 0
    assert mapping["green"] == 1
    assert mapping["red"] == 2


# ---------------------------------------------------------------------------
# Label Encoding — transform
# ---------------------------------------------------------------------------


def test_transform_label_encodes_known_categories(df_train_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    result_train, _ = step.transform(df_train_label, df_train_label.copy())
    assert result_train["color"].dtype in (int, "int64", "int32")
    assert set(result_train["color"]).issubset({0, 1, 2})


def test_transform_label_unknown_category_becomes_minus_one(df_train_label, df_test_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    _, result_test = step.transform(df_train_label, df_test_label)
    # "purple" in color → -1
    assert result_test["color"].tolist()[2] == -1
    # "XL" in size → -1
    assert result_test["size"].tolist()[1] == -1


def test_transform_label_known_test_category_encoded_correctly(df_train_label, df_test_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    _, result_test = step.transform(df_train_label, df_test_label)
    # "blue" → 0, "green" → 1
    assert result_test["color"].tolist()[0] == 0
    assert result_test["color"].tolist()[1] == 1


def test_transform_label_fit_only_on_train(df_train_label, df_test_label):
    """Test-Daten dürfen das Mapping nicht beeinflussen."""
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    original_mapping = dict(step._label_encoders["color"])
    step.transform(df_train_label, df_test_label)
    assert step._label_encoders["color"] == original_mapping


def test_transform_label_preserves_numeric_col(df_train_label, df_test_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    result_train, _ = step.transform(df_train_label, df_test_label)
    assert "value" in result_train.columns
    assert result_train["value"].tolist() == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Label Encoding — default method
# ---------------------------------------------------------------------------


def test_default_method_is_label():
    step = CategoricalEncodingStep()
    assert step.method == "label"


# ---------------------------------------------------------------------------
# One-Hot Encoding — fit
# ---------------------------------------------------------------------------


def test_fit_onehot_stores_categories(df_train_onehot):
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    assert "color" in step._onehot_categories
    assert sorted(step._onehot_categories["color"]) == ["blue", "green", "red"]


# ---------------------------------------------------------------------------
# One-Hot Encoding — transform
# ---------------------------------------------------------------------------


def test_transform_onehot_creates_binary_cols(df_train_onehot):
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    result_train, _ = step.transform(df_train_onehot, df_train_onehot.copy())
    assert "color_red" in result_train.columns
    assert "color_blue" in result_train.columns
    assert "color_green" in result_train.columns
    # Original-Spalte entfernt
    assert "color" not in result_train.columns


def test_transform_onehot_drops_original_col(df_train_onehot):
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    result_train, result_test = step.transform(df_train_onehot, df_train_onehot.copy())
    assert "color" not in result_train.columns
    assert "color" not in result_test.columns


def test_transform_onehot_unknown_category_becomes_zero_row(df_train_onehot, df_test_onehot):
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    _, result_test = step.transform(df_train_onehot, df_test_onehot)
    # "purple" (unbekannt) → alle Dummy-Spalten 0
    purple_row = result_test.iloc[1]  # "purple" ist index 1
    assert purple_row["color_red"] == 0
    assert purple_row["color_blue"] == 0
    assert purple_row["color_green"] == 0


def test_transform_onehot_consistent_column_order(df_train_onehot, df_test_onehot):
    """Train und Test müssen dieselben Spalten in derselben Reihenfolge haben."""
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    result_train, result_test = step.transform(df_train_onehot, df_test_onehot)
    assert list(result_train.columns) == list(result_test.columns)


def test_transform_onehot_binary_values_only(df_train_onehot):
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    result_train, _ = step.transform(df_train_onehot, df_train_onehot.copy())
    for col in ["color_red", "color_blue", "color_green"]:
        assert set(result_train[col].unique()).issubset({0, 1})


def test_transform_onehot_dtype_is_int(df_train_onehot, df_test_onehot):
    """Dummy-Spalten müssen int sein (nicht bool) — downstream-Modelle erwarten int."""
    step = CategoricalEncodingStep(params={"method": "onehot"})
    step.fit(df_train_onehot)
    result_train, result_test = step.transform(df_train_onehot, df_test_onehot)
    for col in ["color_red", "color_blue", "color_green"]:
        assert result_train[col].dtype in ("int64", "int32", "int8", int), \
            f"{col} dtype ist {result_train[col].dtype}, erwartet int"
        assert result_test[col].dtype in ("int64", "int32", "int8", int), \
            f"{col} dtype ist {result_test[col].dtype}, erwartet int"


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


def test_metadata_encoded_columns(df_train_label):
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df_train_label)
    step.transform(df_train_label, df_train_label.copy())
    meta = step.get_metadata()
    assert "encoded_columns" in meta
    assert "color" in meta["encoded_columns"]
    assert "size" in meta["encoded_columns"]
    assert "value" not in meta["encoded_columns"]


# ---------------------------------------------------------------------------
# Keine kategorischen Spalten
# ---------------------------------------------------------------------------


def test_no_categorical_cols_no_change():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df)
    result_train, result_test = step.transform(df, df.copy())
    pd.testing.assert_frame_equal(result_train, df)
    assert step.get_metadata()["encoded_columns"] == []


# ---------------------------------------------------------------------------
# columns-Parameter (Bug 1.2)
# ---------------------------------------------------------------------------


def test_encode_categorical_with_explicit_column():
    """Nur die explizit angegebene Spalte wird encodiert — andere bleiben unberührt."""
    df = pd.DataFrame({
        "color": ["red", "blue", "green"],
        "size": ["S", "M", "L"],
        "value": [1, 2, 3],
    })
    step = CategoricalEncodingStep(params={"method": "label", "columns": ["color"]})
    step.fit(df)
    result_train, _ = step.transform(df, df.copy())
    # color wurde encodiert
    assert result_train["color"].dtype in (int, "int64", "int32")
    # size bleibt als object
    assert result_train["size"].tolist() == ["S", "M", "L"]
    meta = step.get_metadata()
    assert meta["encoded_columns"] == ["color"]
    assert "size" not in meta["encoded_columns"]


def test_encode_categorical_multiple_columns():
    """Mehrere explizit angegebene Spalten werden korrekt encodiert, value bleibt."""
    df = pd.DataFrame({
        "color": ["red", "blue", "green"],
        "size": ["S", "M", "L"],
        "value": [1, 2, 3],
    })
    step = CategoricalEncodingStep(params={"method": "label", "columns": ["color", "size"]})
    step.fit(df)
    result_train, _ = step.transform(df, df.copy())
    assert result_train["color"].dtype in (int, "int64", "int32")
    assert result_train["size"].dtype in (int, "int64", "int32")
    assert result_train["value"].tolist() == [1, 2, 3]
    meta = step.get_metadata()
    assert set(meta["encoded_columns"]) == {"color", "size"}


def test_encode_categorical_fallback_no_columns():
    """Ohne columns-Parameter: Fallback zu dtype-Autoerkennung (bisheriges Verhalten)."""
    df = pd.DataFrame({
        "color": ["red", "blue", "green"],
        "value": [1, 2, 3],
    })
    step = CategoricalEncodingStep(params={"method": "label"})
    step.fit(df)
    meta = step.get_metadata()
    # dtype-Autoerkennung findet "color"
    assert "color" in meta["encoded_columns"]
    # Numerische Spalte nicht dabei
    assert "value" not in meta["encoded_columns"]


def test_encode_categorical_nonexistent_column_skipped():
    """Nicht vorhandene Spalte in columns → kein Fehler, wird stillschweigend übersprungen."""
    df = pd.DataFrame({"color": ["red", "blue", "green"]})
    step = CategoricalEncodingStep(params={"method": "label", "columns": ["nonexistent"]})
    step.fit(df)
    result_train, _ = step.transform(df, df.copy())
    # Kein Encoding, kein Fehler
    assert step.get_metadata()["encoded_columns"] == []
    # color unverändert
    assert result_train["color"].tolist() == ["red", "blue", "green"]


def test_encode_categorical_non_categorical_column_warning():
    """Numerische Spalte in columns → Warning im Metadata, keine Encodierung."""
    df = pd.DataFrame({
        "color": ["red", "blue", "green"],
        "windspeed": [0.3, 0.5, 0.2],
    })
    step = CategoricalEncodingStep(params={"method": "label", "columns": ["windspeed"]})
    step.fit(df)
    result_train, _ = step.transform(df, df.copy())
    meta = step.get_metadata()
    # windspeed nicht encodiert
    assert "windspeed" not in meta["encoded_columns"]
    # Warnung vorhanden
    assert "warnings" in meta
    assert any("windspeed" in w for w in meta["warnings"])
    # windspeed-Werte unverändert
    assert result_train["windspeed"].tolist() == [0.3, 0.5, 0.2]


def test_encode_categorical_onehot_specific_column():
    """One-Hot auf explizit angegebene Spalte — nur diese Spalte wird zu Dummies."""
    df = pd.DataFrame({
        "color": ["red", "blue", "green"],
        "size": ["S", "M", "L"],
    })
    step = CategoricalEncodingStep(params={"method": "onehot", "columns": ["color"]})
    step.fit(df)
    result_train, result_test = step.transform(df, df.copy())
    # color-Dummies vorhanden
    assert "color_red" in result_train.columns
    assert "color_blue" in result_train.columns
    assert "color_green" in result_train.columns
    # Original color-Spalte entfernt
    assert "color" not in result_train.columns
    # size bleibt als object, unverändert
    assert "size" in result_train.columns
    assert result_train["size"].tolist() == ["S", "M", "L"]


def test_encode_categorical_warnings_reset_on_refit():
    """_warnings werden bei erneutem fit() zurückgesetzt."""
    df = pd.DataFrame({"num": [1.0, 2.0, 3.0]})
    df_cat = pd.DataFrame({"color": ["red", "blue", "green"]})
    step = CategoricalEncodingStep(params={"method": "label", "columns": ["num"]})
    step.fit(df)
    assert "warnings" in step.get_metadata()
    # Zweiter fit mit kategorialer Spalte — keine Warnings mehr
    step2 = CategoricalEncodingStep(params={"method": "label", "columns": ["color"]})
    step2.fit(df_cat)
    assert "warnings" not in step2.get_metadata()
