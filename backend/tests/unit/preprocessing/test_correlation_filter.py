"""Unit-Tests für CorrelationFilterStep."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.correlation_filter import CorrelationFilterStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_uncorrelated():
    """Drei unabhängige numerische Spalten (keine hohe Korrelation)."""
    return pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0, 5.0],
        "b": [5.0, 3.0, 1.0, 4.0, 2.0],
        "c": [2.0, 4.0, 1.0, 3.0, 5.0],
    })


@pytest.fixture
def df_with_correlated():
    """b ist identisch mit a (Pearson-Korrelation = 1.0)."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    return pd.DataFrame({
        "a": values,
        "b": values,            # korreliert mit a (corr=1.0)
        "c": [5.0, 3.0, 1.0, 4.0, 2.0],  # unkorreliert
    })


# ---------------------------------------------------------------------------
# Klassen-Attribute
# ---------------------------------------------------------------------------


def test_requires_split_true():
    assert CorrelationFilterStep.requires_split is True


def test_description_set():
    assert CorrelationFilterStep.description != ""


# ---------------------------------------------------------------------------
# fit — hochkorrelierte Features erkannt
# ---------------------------------------------------------------------------


def test_fit_identifies_correlated_features(df_with_correlated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    assert len(step._features_to_drop) >= 1


def test_fit_uncorrelated_no_drops(df_uncorrelated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_uncorrelated)
    assert step._features_to_drop == []


# ---------------------------------------------------------------------------
# Determinismus — alphabetisch späteres Feature wird entfernt
# ---------------------------------------------------------------------------


def test_fit_drops_alphabetically_later_feature():
    """Bei Paar (a, b): 'b' > 'a' alphabetisch → 'b' wird entfernt."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"a": values, "b": values})
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df)
    assert "b" in step._features_to_drop
    assert "a" not in step._features_to_drop


def test_fit_drops_z_not_a_in_pair():
    """Bei Paar (a, z): 'z' wird entfernt, nicht 'a'."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    df = pd.DataFrame({"z": values, "a": values, "b": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]})
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df)
    assert "z" in step._features_to_drop
    assert "a" not in step._features_to_drop


# ---------------------------------------------------------------------------
# Threshold-Grenzwerte
# ---------------------------------------------------------------------------


def test_fit_threshold_exactly_at_1_drops_identical(df_with_correlated):
    """Threshold=1.0 → nur identische Spalten werden entfernt."""
    step = CorrelationFilterStep(params={"threshold": 1.0})
    step.fit(df_with_correlated)
    assert "b" in step._features_to_drop


def test_fit_threshold_0_drops_all_but_first():
    """Threshold=0.0 → alle Paare werden als korreliert erkannt."""
    df = pd.DataFrame({
        "x": [1.0, 2.0, 3.0],
        "y": [4.0, 5.0, 6.0],  # perfekte positive Korrelation mit x
    })
    step = CorrelationFilterStep(params={"threshold": 0.0})
    step.fit(df)
    assert len(step._features_to_drop) >= 1


# ---------------------------------------------------------------------------
# transform
# ---------------------------------------------------------------------------


def test_transform_removes_correlated_feature(df_with_correlated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    result_train, result_test = step.transform(df_with_correlated, df_with_correlated.copy())
    for dropped in step._features_to_drop:
        assert dropped not in result_train.columns
        assert dropped not in result_test.columns


def test_transform_keeps_uncorrelated_features(df_uncorrelated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_uncorrelated)
    result_train, _ = step.transform(df_uncorrelated, df_uncorrelated.copy())
    assert set(result_train.columns) == {"a", "b", "c"}


def test_transform_fit_only_on_train():
    """Drops werden auf Basis der Trainingsdaten berechnet — Test hat keinen Einfluss."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df_train = pd.DataFrame({"a": values, "b": values})
    df_test = pd.DataFrame({"a": [9.0, 8.0], "b": [1.0, 0.0]})  # auf Test keine Korrelation
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_train)
    _, result_test = step.transform(df_train, df_test)
    # "b" wurde laut Train-Fit entfernt — auch im Test
    assert "b" not in result_test.columns


def test_transform_drops_from_both_splits(df_with_correlated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    result_train, result_test = step.transform(df_with_correlated, df_with_correlated.copy())
    assert list(result_train.columns) == list(result_test.columns)


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


def test_metadata_dropped_features(df_with_correlated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    step.transform(df_with_correlated, df_with_correlated.copy())
    meta = step.get_metadata()
    assert "dropped_features" in meta
    assert isinstance(meta["dropped_features"], list)
    assert "b" in meta["dropped_features"]


def test_metadata_empty_when_no_drops(df_uncorrelated):
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_uncorrelated)
    meta = step.get_metadata()
    assert meta["dropped_features"] == []
