"""Unit-Tests für DecisionTreeStep.generate_artifact() und BaseStep-Default (Story 2.2)."""
import numpy as np
import pandas as pd
import pytest

from gysi_ml.steps.modeling.decision_tree import DecisionTreeStep


@pytest.fixture
def sample_split():
    """Kleiner synthetischer Split-Datensatz."""
    rng = np.random.default_rng(0)
    n = 100
    df = pd.DataFrame({
        "feature_a": rng.uniform(0, 1, n),
        "feature_b": rng.uniform(0, 10, n),
        "cnt": rng.integers(50, 500, n).astype(float),
    })
    train = df.iloc[:80].reset_index(drop=True)
    test = df.iloc[80:].reset_index(drop=True)
    return train, test


def test_generate_artifact_creates_png(tmp_path, sample_split):
    df_train, df_test = sample_split
    step = DecisionTreeStep(params={})
    step.fit(df_train)
    step.transform(df_train, df_test)

    result = step.generate_artifact(artifacts_path=str(tmp_path), run_id="test-run-id")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) >= 1

    fi_artifact = next(a for a in result if a["type"] == "feature_importance")
    assert "file_path" in fi_artifact
    from pathlib import Path
    assert Path(fi_artifact["file_path"]).exists()
    assert fi_artifact["file_path"].endswith("feature_importance_test-run-id.png")

    # Overfitting-Check als Learning Curve muss ebenfalls erzeugt werden
    ov_artifact = next(a for a in result if a["type"] == "learning_curve")
    assert Path(ov_artifact["file_path"]).exists()


def test_generate_artifact_returns_none_before_fit():
    step = DecisionTreeStep(params={})
    result = step.generate_artifact(artifacts_path="/tmp", run_id="any-id")
    assert result is None


def test_base_step_default_returns_none():
    """Preprocessing-Steps geben per Default None zurück."""
    from gysi_ml.steps.preprocessing.dedup import DeduplicationStep
    step = DeduplicationStep(params={})
    result = step.generate_artifact(artifacts_path="/tmp", run_id="any-id")
    assert result is None
