"""Unit-Tests fuer Pipeline-Spec JSON-Schema-Validierung."""
import pytest
import jsonschema

from gysi_ml.spec.schema import validate_spec


def test_valid_spec_minimal():
    validate_spec({"steps": []})


def test_valid_spec_with_steps():
    validate_spec({
        "steps": [
            {"type": "dedup", "params": {}, "enabled": True},
            {"type": "split", "params": {"test_size": 0.2}},
        ]
    })


def test_valid_spec_step_without_params():
    validate_spec({"steps": [{"type": "dedup"}]})


def test_invalid_spec_missing_steps_key():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({})


def test_invalid_spec_steps_not_array():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({"steps": "not_an_array"})


def test_invalid_spec_step_missing_type():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({"steps": [{"params": {}}]})


def test_invalid_spec_step_type_not_string():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({"steps": [{"type": 42}]})


def test_invalid_spec_params_not_object():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({"steps": [{"type": "x", "params": "bad"}]})


def test_invalid_spec_additional_top_level_property():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({"steps": [], "unknown_field": "x"})


def test_invalid_spec_step_additional_property():
    with pytest.raises(jsonschema.ValidationError):
        validate_spec({"steps": [{"type": "x", "unknown": True}]})
