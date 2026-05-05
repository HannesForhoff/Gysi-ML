"""Unit-Tests für EBMStep (Story 2.3)."""
import numpy as np
import pandas as pd
import pytest

from gysi_ml.steps.modeling.ebm import EBMStep
from gysi_ml.steps.registry import get_step_class
from gysi_ml.core.capabilities import get_capabilities


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    """Kleiner synthetischer DataFrame mit cnt-Spalte (200 Zeilen)."""
    rng = np.random.default_rng(42)
    n = 200
    df = pd.DataFrame({
        "feature_a": rng.uniform(0, 1, n),
        "feature_b": rng.uniform(0, 10, n),
        "feature_c": rng.integers(0, 5, n).astype(float),
        "cnt": rng.integers(50, 500, n).astype(float),
    })
    return df


@pytest.fixture
def split_data(sample_data):
    train = sample_data.iloc[:160].reset_index(drop=True)
    test = sample_data.iloc[160:].reset_index(drop=True)
    return train, test


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_step_is_registered():
    cls = get_step_class("train_ebm")
    assert cls is EBMStep


def test_transform_before_fit_raises_error(split_data):
    _, df_test = split_data
    step = EBMStep(params={})
    with pytest.raises(RuntimeError, match="transform\\(\\) wurde vor fit\\(\\) aufgerufen"):
        step.transform(pd.DataFrame(), df_test)


def test_fit_trains_on_train_data(split_data):
    df_train, _ = split_data
    step = EBMStep(params={})
    step.fit(df_train)
    assert step.model is not None


def test_transform_returns_unchanged_dataframes(split_data):
    df_train, df_test = split_data
    step = EBMStep(params={})
    step.fit(df_train)
    result_train, result_test = step.transform(df_train, df_test)
    assert result_train.shape == df_train.shape
    assert result_test.shape == df_test.shape
    pd.testing.assert_frame_equal(result_train, df_train)
    pd.testing.assert_frame_equal(result_test, df_test)


def test_metrics_computed(split_data):
    df_train, df_test = split_data
    step = EBMStep(params={})
    step.fit(df_train)
    step.transform(df_train, df_test)
    metadata = step.get_metadata()
    metrics = metadata["metrics"]
    assert "rmse" in metrics and "mae" in metrics and "r2" in metrics
    assert isinstance(metrics["rmse"], float)
    assert isinstance(metrics["mae"], float)
    assert isinstance(metrics["r2"], float)
    assert metrics["r2"] <= 1.0


def test_default_random_state(split_data):
    df_train, df_test = split_data

    step1 = EBMStep(params={})
    step1.fit(df_train)
    step1.transform(df_train, df_test)
    metrics1 = step1.get_metadata()["metrics"]

    step2 = EBMStep(params={})
    step2.fit(df_train)
    step2.transform(df_train, df_test)
    metrics2 = step2.get_metadata()["metrics"]

    assert metrics1["rmse"] == pytest.approx(metrics2["rmse"])
    assert metrics1["r2"] == pytest.approx(metrics2["r2"])


def test_generate_artifact_creates_png(tmp_path, split_data):
    df_train, df_test = split_data
    step = EBMStep(params={})
    step.fit(df_train)
    step.transform(df_train, df_test)

    result = step.generate_artifact(artifacts_path=str(tmp_path), run_id="test-run-id")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) >= 1

    from pathlib import Path
    ebm_artifact = next(a for a in result if a["type"] == "ebm_global_explanation")
    assert "file_path" in ebm_artifact
    assert Path(ebm_artifact["file_path"]).exists()
    assert ebm_artifact["file_path"].endswith("ebm_global_explanation_test-run-id.png")

    # Learning Curve (Overfitting-Check) muss ebenfalls erzeugt werden
    ov_artifact = next(a for a in result if a["type"] == "learning_curve")
    assert Path(ov_artifact["file_path"]).exists()

    # M3: feature_scores müssen skalare Floats sein (kein numpy-Array)
    ebm_global = step.model.explain_global()
    global_data = ebm_global.data()
    scores = global_data["scores"]
    assert len(scores) > 0
    assert isinstance(float(scores[0]), float), "feature_scores[0] muss zu float konvertierbar sein"


def test_generate_artifact_none_before_fit():
    step = EBMStep(params={})
    result = step.generate_artifact(artifacts_path="/tmp", run_id="any-id")
    assert result is None


def test_capabilities_contains_ebm():
    caps = get_capabilities()
    step_types = [s["type"] for s in caps["steps"]]
    assert "train_ebm" in step_types
