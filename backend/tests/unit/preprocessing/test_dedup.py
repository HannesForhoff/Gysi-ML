"""Unit-Tests für DeduplicationStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.dedup import DeduplicationStep


@pytest.fixture
def df_no_dupes():
    return pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})


@pytest.fixture
def df_with_dupes():
    return pd.DataFrame({"a": [1, 2, 2, 3], "b": [4, 5, 5, 6]})


# ---------------------------------------------------------------------------
# fit
# ---------------------------------------------------------------------------


def test_fit_does_not_raise(df_no_dupes):
    step = DeduplicationStep()
    step.fit(df_no_dupes)  # kein Fehler erwartet


# ---------------------------------------------------------------------------
# transform — keine Duplikate
# ---------------------------------------------------------------------------


def test_transform_no_dupes_unchanged(df_no_dupes):
    step = DeduplicationStep()
    step.fit(df_no_dupes)
    result_train, result_test = step.transform(df_no_dupes, df_no_dupes.copy())
    assert len(result_train) == 3
    assert len(result_test) == 3


def test_transform_no_dupes_metadata_zero(df_no_dupes):
    step = DeduplicationStep()
    step.fit(df_no_dupes)
    step.transform(df_no_dupes, df_no_dupes.copy())
    assert step.get_metadata()["removed_duplicates"] == 0


# ---------------------------------------------------------------------------
# transform — mit Duplikaten
# ---------------------------------------------------------------------------


def test_transform_removes_duplicates(df_with_dupes):
    step = DeduplicationStep()
    step.fit(df_with_dupes)
    result_train, _ = step.transform(df_with_dupes, df_with_dupes.copy())
    assert len(result_train) == 3


def test_transform_metadata_counts_removed(df_with_dupes):
    step = DeduplicationStep()
    step.fit(df_with_dupes)
    step.transform(df_with_dupes, df_with_dupes.copy())
    # 1 Duplikat im Train + 1 Duplikat im Test = 2
    assert step.get_metadata()["removed_duplicates"] == 2


# ---------------------------------------------------------------------------
# transform — verschiedene DataFrames für train/test
# ---------------------------------------------------------------------------


def test_transform_deduplicates_independently():
    df_train = pd.DataFrame({"x": [1, 1, 2]})
    df_test = pd.DataFrame({"x": [3, 3, 4, 4]})
    step = DeduplicationStep()
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert len(result_train) == 2
    assert len(result_test) == 2
    assert step.get_metadata()["removed_duplicates"] == 3


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_is_false():
    assert DeduplicationStep.requires_split is False


def test_is_splitter_is_false():
    assert DeduplicationStep.is_splitter is False
