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
    assert RareCategoryBucketingStep.requires_split is True


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
