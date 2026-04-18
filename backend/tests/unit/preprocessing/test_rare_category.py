"""Unit-Tests für RareCategoryBucketingStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.rare_category import RareCategoryBucketingStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_train():
    """
    Spalte 'color': red=8, blue=4, rare_green=1 → rare_green hat 1/13 ≈ 7.7%
    Mit min_frequency=0.1 ist rare_green selten.
    """
    return pd.DataFrame({
        "color": ["red"] * 8 + ["blue"] * 4 + ["rare_green"] * 1,
        "value": list(range(13)),
    })


@pytest.fixture
def df_test(df_train):
    return pd.DataFrame({
        "color": ["red", "blue", "rare_green", "unknown_cat"],
        "value": [0, 1, 2, 3],
    })


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_true():
    assert not getattr(RareCategoryBucketingStep, 'requires_split', False)


def test_description_set():
    assert RareCategoryBucketingStep.description != ""


# ---------------------------------------------------------------------------
# fit — seltene Kategorien erkannt
# ---------------------------------------------------------------------------


def test_fit_identifies_rare_categories(df_train):
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    assert "color" in step._rare_categories
    assert "rare_green" in step._rare_categories["color"]


def test_fit_frequent_categories_not_rare(df_train):
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    assert "red" not in step._rare_categories["color"]
    assert "blue" not in step._rare_categories["color"]


def test_fit_threshold_boundary_exact():
    """Kategorie mit exakt min_frequency ist NICHT selten (< nicht <=)."""
    df = pd.DataFrame({"cat": ["a"] * 10 + ["b"] * 10})  # b = 50%
    step = RareCategoryBucketingStep(params={"min_frequency": 0.5})
    step.fit(df)
    # b ist 50% → nicht selten (< 0.5 ist false)
    assert "b" not in step._rare_categories["cat"]


def test_fit_uses_only_train_data():
    """Test-Daten beeinflussen das Rare-Mapping nicht."""
    df_train = pd.DataFrame({"cat": ["a"] * 9 + ["b"] * 1})  # b selten (10%)
    df_test = pd.DataFrame({"cat": ["a"] * 1 + ["b"] * 9})   # auf Test b häufig → egal
    step = RareCategoryBucketingStep(params={"min_frequency": 0.15})
    step.fit(df_train)
    original_rare = dict(step._rare_categories)
    step.transform(df_train, df_test)
    assert step._rare_categories == original_rare


# ---------------------------------------------------------------------------
# transform — Ersetzung
# ---------------------------------------------------------------------------


def test_transform_rare_becomes_rare_marker(df_train, df_test):
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert "__rare__" in result_train["color"].values
    # "rare_green" → "__rare__" im Train
    mask = df_train["color"] == "rare_green"
    assert (result_train.loc[mask, "color"] == "__rare__").all()


def test_transform_frequent_categories_unchanged(df_train, df_test):
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    result_train, _ = step.transform(df_train, df_test)
    mask = df_train["color"] == "red"
    assert (result_train.loc[mask, "color"] == "red").all()


def test_transform_rare_replaced_in_test_too(df_train, df_test):
    """rare_green im Test → auch durch __rare__ ersetzt."""
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test)
    mask = df_test["color"] == "rare_green"
    assert (result_test.loc[mask, "color"] == "__rare__").all()


def test_transform_unseen_test_category_unchanged(df_train, df_test):
    """Kategorie nur im Test (nicht in Train) → bleibt unverändert."""
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test)
    mask = df_test["color"] == "unknown_cat"
    assert (result_test.loc[mask, "color"] == "unknown_cat").all()


def test_transform_numeric_col_unchanged(df_train, df_test):
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    result_train, _ = step.transform(df_train, df_test)
    assert result_train["value"].tolist() == list(range(13))


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


def test_metadata_rare_counts(df_train):
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df_train)
    meta = step.get_metadata()
    assert "rare_categories_per_column" in meta
    assert "color" in meta["rare_categories_per_column"]
    assert meta["rare_categories_per_column"]["color"] == 1


def test_metadata_zero_when_no_rare():
    df = pd.DataFrame({"cat": ["a"] * 5 + ["b"] * 5})
    step = RareCategoryBucketingStep(params={"min_frequency": 0.01})
    step.fit(df)
    meta = step.get_metadata()
    assert meta["rare_categories_per_column"]["cat"] == 0


# ---------------------------------------------------------------------------
# Keine kategorischen Spalten
# ---------------------------------------------------------------------------


def test_no_categorical_cols_no_change():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df)
    result_train, _ = step.transform(df, df.copy())
    pd.testing.assert_frame_equal(result_train, df)


# ---------------------------------------------------------------------------
# Bug 1.5 — numerisch-typisierte Spalten via explizitem columns-Parameter
# ---------------------------------------------------------------------------


def test_fit_int64_col_via_columns_param():
    """int64-Spalte mit explizitem columns-Parameter → seltene Werte erkannt."""
    # 1→8×, 2→4×, 4→1× — 4 hat 1/13 ≈ 7.7% → mit min_frequency=0.1 selten
    df = pd.DataFrame({"weathersit": [1] * 8 + [2] * 4 + [4] * 1})
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1, "columns": ["weathersit"]})
    step.fit(df)
    assert "weathersit" in step._rare_categories
    assert 4 in step._rare_categories["weathersit"]


def test_fit_float64_col_via_columns_param():
    """float64-Spalte mit explizitem columns-Parameter → seltene Werte erkannt."""
    df = pd.DataFrame({"weathersit": [1.0] * 8 + [2.0] * 4 + [4.0] * 1})
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1, "columns": ["weathersit"]})
    step.fit(df)
    assert "weathersit" in step._rare_categories
    assert 4.0 in step._rare_categories["weathersit"]


def test_columns_param_limits_scope_to_specified_only():
    """Wenn columns gesetzt, werden nur diese Spalten verarbeitet (nicht andere)."""
    df = pd.DataFrame({
        "weathersit": [1] * 8 + [2] * 4 + [4] * 1,
        "cnt": list(range(13)),  # kontinuierlich — soll NICHT verarbeitet werden
    })
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1, "columns": ["weathersit"]})
    step.fit(df)
    assert "cnt" not in step._rare_categories


def test_transform_int64_rare_replaced():
    """transform() ersetzt seltene int64-Werte korrekt durch '__rare__'."""
    df_train = pd.DataFrame({"weathersit": [1] * 8 + [2] * 4 + [4] * 1})
    df_test = pd.DataFrame({"weathersit": [1, 2, 4]})
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1, "columns": ["weathersit"]})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert "__rare__" in result_train["weathersit"].values
    assert "__rare__" in result_test["weathersit"].values
    assert 1 in result_train["weathersit"].values
    assert 2 in result_train["weathersit"].values


def test_without_columns_param_numeric_not_processed():
    """Ohne columns-Parameter werden int64-Spalten NICHT verarbeitet (Backward-Compat)."""
    df = pd.DataFrame({"weathersit": [1] * 8 + [2] * 4 + [4] * 1})
    step = RareCategoryBucketingStep(params={"min_frequency": 0.1})
    step.fit(df)
    # Kein columns-Param → nur object/category/string → weathersit (int64) unberührt
    assert "weathersit" not in step._rare_categories
