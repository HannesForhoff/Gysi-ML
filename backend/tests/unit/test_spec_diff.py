"""Tests für spec_diff — AC 1–7, 9 aus Story 8.1."""

import pytest

from gysi_ml.spec.spec_diff import spec_diff


# Hilfs-Factories
def _step(type_: str, params: dict | None = None, enabled: bool = True) -> dict:
    s: dict = {"type": type_}
    if params is not None:
        s["params"] = params
    if not enabled:
        s["enabled"] = False
    return s


def _spec(*steps) -> dict:
    return {"steps": list(steps)}


# ---------------------------------------------------------------------------
# AC 1 — Hinzugefügter Step
# ---------------------------------------------------------------------------


def test_added_step():
    """spec_diff meldet neu hinzugefügten Step mit Parameterhinweis."""
    old = _spec(_step("imputation", {"method": "median"}))
    new = _spec(
        _step("imputation", {"method": "median"}),
        _step("outlier_handling", {"method": "IQR"}),
    )
    result = spec_diff(old, new)
    assert "+ outlier_handling (IQR)" in result


# ---------------------------------------------------------------------------
# AC 2 — Entfernter Step
# ---------------------------------------------------------------------------


def test_removed_step():
    """spec_diff meldet entfernten Step mit '−'-Präfix."""
    old = _spec(
        _step("imputation", {"method": "median"}),
        _step("correlation_filter", {"threshold": 0.9}),
    )
    new = _spec(_step("imputation", {"method": "median"}))
    result = spec_diff(old, new)
    assert "− correlation_filter" in result


# ---------------------------------------------------------------------------
# AC 3 — Geänderter Parameter
# ---------------------------------------------------------------------------


def test_changed_param():
    """spec_diff zeigt Parameteränderung im Format 'step: alt → neu'."""
    old = _spec(_step("imputation", {"method": "median"}))
    new = _spec(_step("imputation", {"method": "mean"}))
    result = spec_diff(old, new)
    assert "imputation: median → mean" in result


# ---------------------------------------------------------------------------
# AC 4 — Deaktivierter Step
# ---------------------------------------------------------------------------


def test_deactivated_step():
    """spec_diff meldet Deaktivierung eines Steps."""
    old = _spec(_step("encoding", {"strategy": "onehot"}))
    new = _spec(_step("encoding", {"strategy": "onehot"}, enabled=False))
    result = spec_diff(old, new)
    assert "encoding" in result
    assert "deaktiviert" in result


# ---------------------------------------------------------------------------
# AC 5 — Mehrere Änderungen kommasepariert
# ---------------------------------------------------------------------------


def test_multiple_changes():
    """spec_diff kombiniert mehrere Änderungen kommasepariert in einem String."""
    old = _spec(
        _step("imputation", {"method": "median"}),
    )
    new = _spec(
        _step("imputation", {"method": "mean"}),
        _step("outlier_handling", {"method": "IQR"}),
    )
    result = spec_diff(old, new)
    # Beide Änderungen müssen vorhanden sein
    assert "imputation" in result
    assert "outlier_handling" in result
    # Kommasepariert
    assert "," in result


# ---------------------------------------------------------------------------
# AC 6 — Keine Änderungen → leerer String
# ---------------------------------------------------------------------------


def test_no_changes_empty_string():
    """spec_diff gibt exakt '' zurück, wenn sich Specs nicht unterscheiden."""
    spec = _spec(_step("imputation", {"method": "median"}))
    result = spec_diff(spec, spec)
    assert result == ""


# ---------------------------------------------------------------------------
# AC 7 — Unveränderte Parameter nicht aufgelistet
# ---------------------------------------------------------------------------


def test_unchanged_params_not_listed():
    """Unveränderte Parameter tauchen nicht im Diff auf."""
    old = _spec(_step("imputation", {"method": "median", "fill_value": 0}))
    new = _spec(_step("imputation", {"method": "mean", "fill_value": 0}))
    result = spec_diff(old, new)
    # Nur 'method' hat sich geändert — fill_value darf nicht erscheinen
    assert "fill_value" not in result
    assert "imputation: median → mean" in result


# ---------------------------------------------------------------------------
# L1 — Reaktivierter Step (Branch lines 51-52 in spec_diff.py)
# ---------------------------------------------------------------------------


def test_reactivated_step():
    """spec_diff meldet Reaktivierung eines zuvor deaktivierten Steps."""
    old = _spec(_step("encoding", {"strategy": "onehot"}, enabled=False))
    new = _spec(_step("encoding", {"strategy": "onehot"}))
    result = spec_diff(old, new)
    assert "encoding: aktiviert" in result
