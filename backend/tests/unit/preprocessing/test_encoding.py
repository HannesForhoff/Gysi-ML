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
    assert CategoricalEncodingStep.requires_split is True


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
