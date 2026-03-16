"""Unit-Tests für llm/prompts.py."""
from gysi_ml.llm.prompts import build_retry_prompt, build_system_prompt


_SAMPLE_CAPABILITIES = [
    {
        "type": "dedup",
        "description": "Entfernt doppelte Zeilen",
        "params": {},
    },
    {
        "type": "split",
        "description": "Train/Test-Split",
        "params": {"test_size": 0.2, "random_state": 42},
    },
]


def test_build_system_prompt_contains_capabilities():
    """Capabilities werden als JSON in den Prompt eingebettet."""
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES)
    assert "dedup" in prompt
    assert "split" in prompt
    assert "Entfernt doppelte Zeilen" in prompt


def test_build_system_prompt_contains_schema_instruction():
    """JSON-Format-Anweisung ist enthalten."""
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES)
    assert '"action"' in prompt
    assert '"spec"' in prompt
    assert '"explanation"' in prompt


def test_build_system_prompt_contains_dataset_context():
    """Bike-Datensatz-Kontext ist im Prompt."""
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES)
    assert "cnt" in prompt
    assert "Bike" in prompt or "bike" in prompt.lower()


def test_build_system_prompt_contains_vagheits_instruction():
    """Vagheits-Unterscheidung (execute/propose) ist erklärt."""
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES)
    assert "execute" in prompt
    assert "propose" in prompt


def test_build_retry_prompt_contains_error():
    """Fehlermeldung wird im Retry-Prompt eingefügt."""
    error_msg = "Schema-Verletzung: 'action' is required"
    prompt = build_retry_prompt(error_msg)
    assert error_msg in prompt
    assert "JSON" in prompt


def test_build_retry_prompt_is_string():
    """Rückgabe ist immer ein String."""
    result = build_retry_prompt("some error")
    assert isinstance(result, str)
    assert len(result) > 0
