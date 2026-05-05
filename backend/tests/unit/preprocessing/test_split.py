"""Unit-Tests für SplitStep (Story 1.5)."""
import pandas as pd
import pytest

from gysi_ml.steps.preprocessing.split import SplitStep


@pytest.fixture
def df_100():
    return pd.DataFrame({"a": range(100), "b": range(100, 200)})


# ---------------------------------------------------------------------------
# Klassenattribute
# ---------------------------------------------------------------------------


def test_is_splitter_flag():
    assert SplitStep.is_splitter is True


def test_requires_split_is_false():
    assert SplitStep.requires_split is False


# ---------------------------------------------------------------------------
# fit ist no-op
# ---------------------------------------------------------------------------


def test_fit_is_no_op(df_100):
    step = SplitStep(params={})
    step.fit(df_100)  # darf nicht werfen


# ---------------------------------------------------------------------------
# Aufteilung — Zeilenzahlen
# ---------------------------------------------------------------------------


def test_default_split_ratio(df_100):
    step = SplitStep(params={})
    step.fit(df_100)
    df_train, df_test = step.transform(df_100, None)
    assert len(df_train) == 80
    assert len(df_test) == 20


def test_custom_test_size(df_100):
    step = SplitStep(params={"test_size": 0.3})
    step.fit(df_100)
    df_train, df_test = step.transform(df_100, None)
    assert len(df_train) == 70
    assert len(df_test) == 30


def test_all_rows_preserved(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    df_train, df_test = step.transform(df_100, None)
    assert len(df_train) + len(df_test) == len(df_100)


def test_no_overlap_between_train_and_test(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    df_train, df_test = step.transform(df_100, None)
    train_set = set(df_train["a"].tolist())
    test_set = set(df_test["a"].tolist())
    assert train_set.isdisjoint(test_set)


# ---------------------------------------------------------------------------
# Index-Reset
# ---------------------------------------------------------------------------


def test_train_index_is_reset(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    df_train, _ = step.transform(df_100, None)
    assert list(df_train.index) == list(range(len(df_train)))


def test_test_index_is_reset(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    _, df_test = step.transform(df_100, None)
    assert list(df_test.index) == list(range(len(df_test)))


# ---------------------------------------------------------------------------
# Reproduzierbarkeit
# ---------------------------------------------------------------------------


def test_reproducibility_same_random_state(df_100):
    step1 = SplitStep(params={"random_state": 42})
    step1.fit(df_100)
    train1, test1 = step1.transform(df_100, None)

    step2 = SplitStep(params={"random_state": 42})
    step2.fit(df_100)
    train2, test2 = step2.transform(df_100, None)

    pd.testing.assert_frame_equal(train1.reset_index(drop=True), train2.reset_index(drop=True))
    pd.testing.assert_frame_equal(test1.reset_index(drop=True), test2.reset_index(drop=True))


def test_different_random_states_yield_different_splits():
    df = pd.DataFrame({"a": range(100)})

    step1 = SplitStep(params={"random_state": 1})
    step1.fit(df)
    train1, _ = step1.transform(df, None)

    step2 = SplitStep(params={"random_state": 99})
    step2.fit(df)
    train2, _ = step2.transform(df, None)

    assert list(train1["a"]) != list(train2["a"])


# ---------------------------------------------------------------------------
# Metadaten
# ---------------------------------------------------------------------------


def test_metadata_train_rows(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    step.transform(df_100, None)
    assert step.get_metadata()["train_rows"] == 80


def test_metadata_test_rows(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    step.transform(df_100, None)
    assert step.get_metadata()["test_rows"] == 20


def test_metadata_test_size(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    step.transform(df_100, None)
    assert step.get_metadata()["test_size"] == pytest.approx(0.2)


def test_metadata_random_state(df_100):
    step = SplitStep(params={"test_size": 0.2, "random_state": 42})
    step.fit(df_100)
    step.transform(df_100, None)
    assert step.get_metadata()["random_state"] == 42


def test_metadata_keys_complete(df_100):
    step = SplitStep(params={"test_size": 0.3, "random_state": 7})
    step.fit(df_100)
    step.transform(df_100, None)
    assert set(step.get_metadata().keys()) == {"train_rows", "test_rows", "test_size", "random_state"}


def test_metadata_default_random_state(df_100):
    step = SplitStep(params={})
    step.fit(df_100)
    step.transform(df_100, None)
    assert step.get_metadata()["random_state"] == 42


# ---------------------------------------------------------------------------
# generate_artifact (B-07) — Methode wurde in Executor verschoben
# SplitStep.generate_artifact() existiert nicht mehr; Train/Test-CSVs werden
# vom Executor nach Abschluss aller Pipeline-Steps geschrieben (Option B).
# ---------------------------------------------------------------------------


def test_generate_artifact_returns_none(tmp_path):
    """SplitStep.generate_artifact() soll None zurückgeben (Basis-Implementierung)."""
    step = SplitStep(params={})
    step.fit(pd.DataFrame({"a": range(10), "cnt": range(10)}))
    step.transform(pd.DataFrame({"a": range(10), "cnt": range(10)}), None)
    result = step.generate_artifact(artifacts_path=str(tmp_path), run_id="run-1")
    assert result is None
