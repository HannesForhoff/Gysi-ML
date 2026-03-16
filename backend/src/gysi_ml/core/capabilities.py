"""Capabilities-Service: liefert maschinenlesbare Infos über alle registrierten Steps."""
from gysi_ml.steps.registry import get_all_steps


def get_capabilities() -> dict:
    """Gibt alle registrierten Steps alphabetisch sortiert mit Metadaten zurück."""
    steps = get_all_steps()
    return {
        "steps": [
            {
                "type": step_type,
                "description": step_cls.description,
                "params": step_cls.param_schema,
            }
            for step_type, step_cls in sorted(steps.items())
        ]
    }
