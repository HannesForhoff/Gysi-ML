"""Unit-Tests für get_capabilities() (Story 1.6, AC 1-4)."""
import pytest

from gysi_ml.core.capabilities import get_capabilities
from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import _registry, register_step

ALL_EXPECTED_TYPES = {
    "correlation_filter",
    "dedup",
    "encode_categorical",
    "impute_missing",
    "outlier_handling",
    "rare_category_bucketing",
    "split",
    "time_feature_encoding",
}


@pytest.fixture(autouse=True)
def clean_registry():
    """Registry vor/nach jedem Test auf bekannten Zustand zurücksetzen."""
    original = dict(_registry)
    yield
    _registry.clear()
    _registry.update(original)


def test_get_capabilities_returns_dict_with_steps_key():
    result = get_capabilities()
    assert isinstance(result, dict)
    assert "steps" in result


def test_all_registered_steps_present():
    """AC2: Alle 8 registrierten Steps sind im Ergebnis enthalten."""
    result = get_capabilities()
    types = {s["type"] for s in result["steps"]}
    assert ALL_EXPECTED_TYPES <= types


def test_steps_count_matches_registry():
    result = get_capabilities()
    assert len(result["steps"]) == len(_registry)


def test_steps_sorted_alphabetically():
    """AC4: Ausgabe ist alphabetisch nach type sortiert."""
    result = get_capabilities()
    types = [s["type"] for s in result["steps"]]
    assert types == sorted(types)


def test_each_step_has_required_keys():
    """AC2: Jeder Step hat type, description und params."""
    result = get_capabilities()
    for step in result["steps"]:
        assert "type" in step
        assert "description" in step
        assert "params" in step


def test_description_is_nonempty_string():
    result = get_capabilities()
    for step in result["steps"]:
        assert isinstance(step["description"], str)
        assert len(step["description"]) > 0


def test_params_is_dict():
    result = get_capabilities()
    for step in result["steps"]:
        assert isinstance(step["params"], dict)


def test_auto_discovery_new_step():
    """AC3: Neuer @register_step erscheint automatisch ohne manuelle Pflege."""

    @register_step("zzz_auto_discovery_test")
    class _NewStep(BaseStep):
        description = "Ein automatisch entdeckter Test-Step"
        param_schema = {"x": {"type": "number", "default": 1}}

        def fit(self, df_train):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    result = get_capabilities()
    types = [s["type"] for s in result["steps"]]
    assert "zzz_auto_discovery_test" in types
    # Alphabetische Sortierung bleibt erhalten
    assert types == sorted(types)


def test_split_step_has_expected_description():
    """Smoke-Test: split-Step hat die erwartete Beschreibung."""
    result = get_capabilities()
    split = next(s for s in result["steps"] if s["type"] == "split")
    assert "Train" in split["description"] or "Teilt" in split["description"]


def test_split_step_params_contain_test_size():
    result = get_capabilities()
    split = next(s for s in result["steps"] if s["type"] == "split")
    assert "test_size" in split["params"]
