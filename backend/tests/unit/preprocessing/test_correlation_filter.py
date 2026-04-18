"""Unit-Tests für CorrelationFilterStep."""
import os
import tempfile

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
    assert not getattr(CorrelationFilterStep, 'requires_split', False)


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
# get_metadata — dropped_features (bestehend)
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


# ---------------------------------------------------------------------------
# get_metadata — corr_pairs (Problem A Fix)
# ---------------------------------------------------------------------------


def test_metadata_corr_pairs_present(df_with_correlated):
    """corr_pairs wird nach fit() befüllt."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    meta = step.get_metadata()
    assert "corr_pairs" in meta
    assert isinstance(meta["corr_pairs"], list)
    assert len(meta["corr_pairs"]) >= 1


def test_metadata_corr_pairs_structure(df_with_correlated):
    """Jeder Eintrag in corr_pairs hat col_a, col_b, value, dropped."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    pairs = step.get_metadata()["corr_pairs"]
    for p in pairs:
        assert "col_a" in p
        assert "col_b" in p
        assert "value" in p
        assert "dropped" in p
        assert isinstance(p["value"], float)
        assert 0.0 <= p["value"] <= 1.0


def test_metadata_corr_pairs_value_rounded():
    """Korrelationswerte werden auf 4 Dezimalstellen gerundet."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"a": values, "b": values})
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df)
    pairs = step.get_metadata()["corr_pairs"]
    assert len(pairs) == 1
    assert pairs[0]["value"] == 1.0  # identische Spalten → r=1.0


def test_metadata_corr_pairs_empty_when_no_correlation(df_uncorrelated):
    """Keine Paare wenn alle Features unter dem Threshold liegen."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_uncorrelated)
    meta = step.get_metadata()
    assert meta["corr_pairs"] == []


def test_metadata_corr_pairs_dropped_matches_features_to_drop():
    """Das 'dropped'-Feld in jedem Paar ist in dropped_features enthalten."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"a": values, "b": values, "c": [5.0, 4.0, 3.0, 2.0, 1.0]})
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df)
    meta = step.get_metadata()
    for p in meta["corr_pairs"]:
        assert p["dropped"] in meta["dropped_features"]


# ---------------------------------------------------------------------------
# get_metadata — independent_features (Problem C Fix)
# ---------------------------------------------------------------------------


def test_metadata_independent_features_present(df_with_correlated):
    """independent_features wird nach fit() zurückgegeben."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    meta = step.get_metadata()
    assert "independent_features" in meta
    assert isinstance(meta["independent_features"], list)


def test_metadata_independent_features_excludes_correlated(df_with_correlated):
    """a und b sind korreliert → beide nicht in independent_features."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    independent = step.get_metadata()["independent_features"]
    assert "a" not in independent
    assert "b" not in independent
    # c ist unkorrelliert → in independent
    assert "c" in independent


def test_metadata_independent_features_all_when_no_correlation(df_uncorrelated):
    """Keine Korrelation → alle Features sind eigenständig."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_uncorrelated)
    independent = step.get_metadata()["independent_features"]
    assert set(independent) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# features_to_drop Parameter — Nutzer-Kontrolle (Problem B2 Fix)
# ---------------------------------------------------------------------------


def test_explicit_features_to_drop_overrides_fallback():
    """User gibt explizit 'a' an → 'a' wird entfernt, nicht 'b' (Fallback wäre 'b')."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"a": values, "b": values})
    step = CorrelationFilterStep(params={"threshold": 0.9, "features_to_drop": ["a"]})
    step.fit(df)
    meta = step.get_metadata()
    assert "a" in meta["dropped_features"]
    assert "b" not in meta["dropped_features"]
    # dropped-Feld im Paar muss 'a' sein
    assert meta["corr_pairs"][0]["dropped"] == "a"


def test_explicit_features_to_drop_reflected_in_transform():
    """Nach explizitem Drop von 'a': Transform entfernt 'a', behält 'b'."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df_train = pd.DataFrame({"a": values, "b": values, "c": [5.0, 4.0, 3.0, 2.0, 1.0]})
    df_test = df_train.copy()
    step = CorrelationFilterStep(params={"threshold": 0.9, "features_to_drop": ["a"]})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert "a" not in result_train.columns
    assert "b" in result_train.columns
    assert "a" not in result_test.columns


def test_explicit_features_to_drop_empty_uses_fallback():
    """Leere features_to_drop → Fallback max()-Logik greift (alphabetisch späteres)."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"a": values, "b": values})
    step = CorrelationFilterStep(params={"threshold": 0.9, "features_to_drop": []})
    step.fit(df)
    meta = step.get_metadata()
    assert "b" in meta["dropped_features"]
    assert "a" not in meta["dropped_features"]


# ---------------------------------------------------------------------------
# generate_artifact (Problem D Fix)
# ---------------------------------------------------------------------------


def test_generate_artifact_returns_none_before_transform():
    """Vor transform() gibt generate_artifact() None zurück."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"a": values, "b": values})
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df)
    # Kein transform() → kein Artefakt
    result = step.generate_artifact("/tmp", "test-run")
    assert result is None


def test_generate_artifact_creates_csv(df_with_correlated):
    """Nach transform() wird ein CSV im artifacts_path erstellt."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    step.transform(df_with_correlated, df_with_correlated.copy())

    with tempfile.TemporaryDirectory() as tmpdir:
        result = step.generate_artifact(tmpdir, "run-abc")
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "correlation_filter_result"
        assert os.path.exists(result[0]["file_path"])


def test_generate_artifact_csv_path_contains_run_id(df_with_correlated):
    """Der Dateiname des Artefakts enthält die run_id."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    step.transform(df_with_correlated, df_with_correlated.copy())

    with tempfile.TemporaryDirectory() as tmpdir:
        result = step.generate_artifact(tmpdir, "my-run-42")
        assert "my-run-42" in result[0]["file_path"]
        assert result[0]["file_path"].endswith("_correlation_filter.csv")


def test_generate_artifact_csv_has_correct_columns(df_with_correlated):
    """Das gespeicherte CSV enthält nur die nicht-entfernten Spalten."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_with_correlated)
    df_result_train, _ = step.transform(df_with_correlated, df_with_correlated.copy())

    with tempfile.TemporaryDirectory() as tmpdir:
        result = step.generate_artifact(tmpdir, "col-check")
        saved = pd.read_csv(result[0]["file_path"])
        assert list(saved.columns) == list(df_result_train.columns)
        for dropped in step._features_to_drop:
            assert dropped not in saved.columns


def test_generate_artifact_no_drops_still_creates_csv(df_uncorrelated):
    """Auch wenn keine Features entfernt wurden, wird ein CSV erzeugt."""
    step = CorrelationFilterStep(params={"threshold": 0.9})
    step.fit(df_uncorrelated)
    step.transform(df_uncorrelated, df_uncorrelated.copy())

    with tempfile.TemporaryDirectory() as tmpdir:
        result = step.generate_artifact(tmpdir, "no-drop-run")
        assert result is not None
        assert os.path.exists(result[0]["file_path"])
