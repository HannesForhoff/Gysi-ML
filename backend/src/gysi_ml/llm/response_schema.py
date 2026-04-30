import json

import jsonschema

from gysi_ml.llm.exceptions import LLMResponseValidationError

LLM_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "required": ["action", "spec", "explanation"],
    "properties": {
        "action": {"type": "string", "enum": ["execute", "propose", "modify_spec", "compare_runs", "rollback", "abort_step_by_step", "info"]},
        "target_spec_id": {"type": "string"},
        "target_version": {"type": "string"},
        "spec": {
            "type": "object",
            "required": ["steps"],
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["type"],
                        "properties": {
                            "type": {"type": "string"},
                            "params": {"type": "object"},
                            "parameters_summary": {"type": "string"},
                        },
                    },
                }
            },
        },
        "explanation": {"type": "string"},
        "spec_version": {"type": "string"},
        "base_spec_version": {"type": "string"},
        "run_id_a": {"type": "string"},
        "run_id_b": {"type": "string"},
    },
    "additionalProperties": False,
}


def validate_llm_response(response_str: str | None) -> dict:
    """Parst und validiert die LLM-Antwort gegen das Schema.

    Returns:
        Geparstes dict bei Erfolg.

    Raises:
        LLMResponseValidationError: Bei ungültigem JSON oder Schema-Verletzung.
    """
    if response_str is None:
        raise LLMResponseValidationError("Ungültiges JSON: LLM hat keinen Inhalt zurückgegeben (None)")

    # Strip potential markdown code blocks (```json ... ```)
    stripped = response_str.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove opening fence (```json or ```)
        lines = lines[1:]
        # Remove closing fence if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LLMResponseValidationError(f"Ungültiges JSON: {exc}") from exc

    try:
        jsonschema.validate(instance=data, schema=LLM_RESPONSE_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise LLMResponseValidationError(f"Schema-Verletzung: {exc.message}") from exc

    return data
