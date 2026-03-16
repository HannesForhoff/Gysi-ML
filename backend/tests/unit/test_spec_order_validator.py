"""Unit-Tests für validate_spec_order und SpecOrderError (Story 1.5)."""
import pytest

from gysi_ml.executor.spec_validator import SpecOrderError, validate_spec_order


# ---------------------------------------------------------------------------
# Gültige Reihenfolgen — kein Fehler erwartet
# ---------------------------------------------------------------------------


def test_empty_steps_ok():
    validate_spec_order([])


def test_split_first_then_requires_split_ok():
    steps = [
        {"type": "split"},
        {"type": "impute_missing"},
    ]
    validate_spec_order(steps)


def test_stateless_step_without_split_ok():
    steps = [{"type": "dedup"}]
    validate_spec_order(steps)


def test_time_feature_before_split_ok():
    steps = [
        {"type": "time_feature_encoding"},
        {"type": "split"},
        {"type": "impute_missing"},
    ]
    validate_spec_order(steps)


def test_multiple_requires_split_steps_after_split_ok():
    steps = [
        {"type": "split"},
        {"type": "impute_missing"},
        {"type": "outlier_handling"},
        {"type": "encode_categorical"},
        {"type": "correlation_filter"},
        {"type": "rare_category_bucketing"},
    ]
    validate_spec_order(steps)


def test_disabled_step_before_split_ok():
    steps = [
        {"type": "impute_missing", "enabled": False},
        {"type": "split"},
        {"type": "impute_missing"},
    ]
    validate_spec_order(steps)


# ---------------------------------------------------------------------------
# Ungültige Reihenfolgen — SpecOrderError erwartet
# ---------------------------------------------------------------------------


def test_impute_missing_before_split_raises():
    steps = [{"type": "impute_missing"}]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


def test_outlier_handling_before_split_raises():
    steps = [{"type": "outlier_handling"}]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


def test_encode_categorical_before_split_raises():
    steps = [{"type": "encode_categorical"}]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


def test_correlation_filter_before_split_raises():
    steps = [{"type": "correlation_filter"}]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


def test_rare_category_bucketing_before_split_raises():
    steps = [{"type": "rare_category_bucketing"}]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


def test_train_decision_tree_before_split_raises():
    steps = [{"type": "train_decision_tree"}]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


def test_impute_after_stateless_but_before_split_raises():
    steps = [
        {"type": "dedup"},
        {"type": "impute_missing"},
        {"type": "split"},
    ]
    with pytest.raises(SpecOrderError):
        validate_spec_order(steps)


# ---------------------------------------------------------------------------
# Fehlernachricht enthält Step-Typ
# ---------------------------------------------------------------------------


def test_error_message_contains_step_type():
    steps = [{"type": "impute_missing"}]
    with pytest.raises(SpecOrderError) as exc_info:
        validate_spec_order(steps)
    assert "impute_missing" in str(exc_info.value)


def test_error_str_is_useful():
    steps = [{"type": "outlier_handling"}]
    with pytest.raises(SpecOrderError) as exc_info:
        validate_spec_order(steps)
    # Should mention "split" in the message
    assert "split" in str(exc_info.value).lower()
