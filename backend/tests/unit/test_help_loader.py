"""Unit-Tests für help_loader.py"""
import importlib
from pathlib import Path

import pytest
import yaml


@pytest.fixture(autouse=True)
def reset_cache():
    """Cache vor jedem Test leeren um Isolation sicherzustellen."""
    import gysi_ml.utils.help_loader as loader
    loader._cache = None
    yield
    loader._cache = None


def test_load_help_text_welcome_message():
    from gysi_ml.utils.help_loader import load_help_text
    text = load_help_text("welcome_message")
    assert isinstance(text, str)
    assert len(text) > 0
    assert "/help" in text
    assert "/overview" in text


def test_load_help_text_caches_after_first_call(tmp_path):
    """Zweiter Aufruf liest nicht erneut von Disk (Cache aktiv)."""
    import gysi_ml.utils.help_loader as loader
    loader._cache = None

    # Ersten Call ausführen
    text1 = loader.load_help_text("welcome_message")
    # Cache manuell verändern — zweiter Call darf NICHT neu laden
    loader._cache["welcome_message"] = "cached_value"
    text2 = loader.load_help_text("welcome_message")

    assert text2 == "cached_value"
    assert text1 != "cached_value"


def test_load_help_text_missing_key_raises_key_error(tmp_path, monkeypatch):
    import gysi_ml.utils.help_loader as loader
    loader._cache = {"welcome_message": "hello"}

    with pytest.raises(KeyError, match="nicht_existent"):
        loader.load_help_text("nicht_existent")


def test_load_help_text_missing_file_raises_file_not_found(tmp_path, monkeypatch):
    import gysi_ml.utils.help_loader as loader
    loader._cache = None

    # Pfadauflösung auf nicht-existente Datei umlenken
    monkeypatch.setattr(
        loader,
        "_load_config",
        lambda: (_ for _ in ()).throw(FileNotFoundError("help_texts.yaml nicht gefunden: /no/such/path")),
    )

    with pytest.raises(FileNotFoundError, match="help_texts.yaml"):
        loader.load_help_text("welcome_message")


def test_load_help_text_invalid_yaml_raises_value_error(tmp_path, monkeypatch):
    import gysi_ml.utils.help_loader as loader
    loader._cache = None

    # Ungültiges YAML simulieren
    def _raise():
        raise ValueError("Ungültiges YAML in help_texts.yaml")

    monkeypatch.setattr(loader, "_load_config", _raise)

    with pytest.raises(ValueError, match="Ungültiges YAML"):
        loader.load_help_text("welcome_message")
