"""Unit-Tests für CatBoostFeatureSelectionStep (Story 4.3)."""
import numpy as np
import pandas as pd
import pytest

from gysi_ml.core.capabilities import get_capabilities
from gysi_ml.steps.modeling.catboost_feature_selection import CatBoostFeatureSelectionStep
from gysi_ml.steps.registry import get_step_class


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    """Minimaler DataFrame mit cnt + 5 Features (30 Zeilen für CatBoost)."""
    rng = np.random.default_rng(42)
    n = 30
    return pd.DataFrame({
        "feat_a": rng.uniform(0, 1, n),
        "feat_b": rng.uniform(0, 1, n),
        "feat_c": rng.uniform(0, 1, n),
        "feat_d": rng.uniform(0, 1, n),
        "feat_e": rng.uniform(0, 1, n),
        "cnt": rng.uniform(0, 100, n),
    })


@pytest.fixture
def split_data(sample_df):
    train = sample_df.iloc[:24].reset_index(drop=True)
    test = sample_df.iloc[24:].reset_index(drop=True)
    return train, test


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fit_transform_reduces_features_to_top_n(split_data):
    """Nach fit/transform sind nur top_n + 1 Spalten vorhanden (inkl. cnt)."""
    df_train, df_test = split_data
    step = CatBoostFeatureSelectionStep(params={"top_n": 3, "random_state": 42})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert result_train.shape[1] == 3 + 1  # top_n + cnt
    assert result_test.shape[1] == 3 + 1


def test_cnt_column_preserved(split_data):
    """cnt ist immer in df_train und df_test nach transform."""
    df_train, df_test = split_data
    step = CatBoostFeatureSelectionStep(params={"top_n": 2, "random_state": 42})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert "cnt" in result_train.columns
    assert "cnt" in result_test.columns


def test_get_metadata_returns_selected_and_removed(split_data):
    """Metadata enthält selected_features und removed_features, Vereinigung = alle Features."""
    df_train, df_test = split_data
    step = CatBoostFeatureSelectionStep(params={"top_n": 3, "random_state": 42})
    step.fit(df_train)
    metadata = step.get_metadata()

    assert len(metadata["selected_features"]) == 3
    assert len(metadata["removed_features"]) == 2  # 5 total - 3 selected
    all_features = set(metadata["selected_features"]) | set(metadata["removed_features"])
    expected = {"feat_a", "feat_b", "feat_c", "feat_d", "feat_e"}
    assert all_features == expected


def test_default_top_n_is_8(split_data):
    """Default top_n=8 → bei 5 Features werden alle behalten."""
    df_train, df_test = split_data
    step = CatBoostFeatureSelectionStep(params={})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    # 5 Features < 8 → alle behalten + cnt
    assert result_train.shape[1] == 5 + 1
    assert result_test.shape[1] == 5 + 1


def test_registered_in_capabilities():
    """catboost_feature_selection ist in GET /v1/capabilities sichtbar."""
    caps = get_capabilities()
    step_types = [s["type"] for s in caps["steps"]]
    assert "catboost_feature_selection" in step_types


def test_step_is_registered():
    """Step ist über die Registry abrufbar."""
    cls = get_step_class("catboost_feature_selection")
    assert cls is CatBoostFeatureSelectionStep


def test_generate_artifact_returns_none(split_data):
    """generate_artifact gibt None zurück (kein Plot für Feature Selection)."""
    df_train, _ = split_data
    step = CatBoostFeatureSelectionStep(params={"top_n": 3, "random_state": 42})
    step.fit(df_train)
    result = step.generate_artifact(artifacts_path="/tmp", run_id="test")
    assert result is None


def test_reproducibility_with_random_state(split_data):
    """Gleicher random_state → gleiche Feature-Selektion."""
    df_train, _ = split_data
    step1 = CatBoostFeatureSelectionStep(params={"top_n": 3, "random_state": 42})
    step1.fit(df_train)
    meta1 = step1.get_metadata()

    step2 = CatBoostFeatureSelectionStep(params={"top_n": 3, "random_state": 42})
    step2.fit(df_train)
    meta2 = step2.get_metadata()

    assert meta1["selected_features"] == meta2["selected_features"]
