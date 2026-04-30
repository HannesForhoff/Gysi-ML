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


def test_build_system_prompt_rollback_section_with_history():
    """spec_history → Rollback-Abschnitt mit Versionstabelle im Prompt."""
    history = [
        {"version": "v1", "created_at": "2026-04-25 10:42:00", "change_summary": None},
        {"version": "v2", "created_at": "2026-04-25 10:48:00", "change_summary": "impute_missing hinzugefügt"},
    ]
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES, spec_history=history)
    assert "v1" in prompt
    assert "v2" in prompt
    assert "Initialversion" in prompt
    assert "impute_missing hinzugefügt" in prompt
    assert "target_version" in prompt


def test_build_system_prompt_rollback_section_empty_without_history():
    """Ohne spec_history kein Versionstabellen-Block im Prompt."""
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES)
    assert "Verfügbare Spec-Versionen" not in prompt


def test_build_system_prompt_rollback_section_no_hallucination_instruction():
    """Rollback-Abschnitt enthält Hinweis gegen Halluzination von UUIDs."""
    history = [{"version": "v1", "created_at": "2026-04-25 10:00:00", "change_summary": None}]
    prompt = build_system_prompt(_SAMPLE_CAPABILITIES, spec_history=history)
    assert "NIEMALS" in prompt or "Halluziniere" in prompt
