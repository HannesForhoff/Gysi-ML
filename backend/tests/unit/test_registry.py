"""Unit-Tests fuer die Step-Registry."""
import pytest

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import (
    _registry,
    get_all_steps,
    get_step_class,
    list_step_types,
    register_step,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Registry vor/nach jedem Test auf bekannten Zustand zurücksetzen."""
    original = dict(_registry)
    yield
    _registry.clear()
    _registry.update(original)


def _make_dummy(name: str = "test_dummy") -> type[BaseStep]:
    @register_step(name)
    class _Dummy(BaseStep):
        def fit(self, df_train):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    return _Dummy


def test_register_and_retrieve():
    cls = _make_dummy("my_step")
    assert get_step_class("my_step") is cls


def test_register_decorator_returns_class():
    original = _make_dummy("returnable")
    assert issubclass(original, BaseStep)


def test_list_step_types_contains_registered():
    _make_dummy("listed_step")
    assert "listed_step" in list_step_types()


def test_get_step_class_unknown_raises_key_error():
    with pytest.raises(KeyError, match="unknown_xyz"):
        get_step_class("unknown_xyz")


def test_get_all_steps_returns_dict():
    _make_dummy("all_steps_test")
    steps = get_all_steps()
    assert isinstance(steps, dict)
    assert "all_steps_test" in steps


def test_overwrite_registration():
    """Zweites Registrieren desselben Typs überschreibt die erste Klasse."""

    @register_step("overwrite_me")
    class First(BaseStep):
        def fit(self, df):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    @register_step("overwrite_me")
    class Second(BaseStep):
        def fit(self, df):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    assert get_step_class("overwrite_me") is Second


def test_step_instance_uses_params():
    @register_step("param_step")
    class ParamStep(BaseStep):
        def fit(self, df):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    instance = get_step_class("param_step")(params={"k": 42})
    assert instance.params["k"] == 42


def test_get_metadata_default_empty():
    @register_step("metadata_step")
    class MetaStep(BaseStep):
        def fit(self, df):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    assert MetaStep().get_metadata() == {}
