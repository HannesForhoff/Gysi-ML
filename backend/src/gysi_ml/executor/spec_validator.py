"""Spec-Order-Validierung: prüft ob Split-abhängige Steps nach dem Split kommen."""

# Nur Modeling-Steps erfordern einen vorherigen Split (Data-Leakage-Schutz).
# Preprocessing-Steps (impute_missing, outlier_handling, encode_categorical etc.)
# können pädagogisch sinnvoll auch auf dem Gesamtdatensatz ausgeführt werden.
REQUIRES_SPLIT: frozenset[str] = frozenset({
    # Modeling Steps (Epic 2) — zwingend nach Split wegen Data Leakage
    "train_decision_tree",
    "train_ebm",
    "catboost_feature_selection",
})


class SpecOrderError(ValueError):
    """Wird geworfen wenn ein Split-abhängiger Step vor dem Split-Step liegt."""


def validate_spec_order(steps: list[dict]) -> None:
    """Prüft ob alle Split-abhängigen Steps nach einem 'split'-Step kommen.

    Args:
        steps: Liste von Spec-Step-Dicts mit Pflichtfeld ``type``.

    Raises:
        SpecOrderError: wenn ein Step in REQUIRES_SPLIT vor dem Split-Step liegt.
    """
    split_seen = False
    for step in steps:
        if not step.get("enabled", True):
            continue
        step_type = step["type"]
        if step_type == "split":
            split_seen = True
        elif step_type in REQUIRES_SPLIT and not split_seen:
            raise SpecOrderError(
                f"Step '{step_type}' benötigt einen vorherigen 'split'-Step, "
                "aber kein Split-Step wurde vor diesem Step gefunden."
            )
