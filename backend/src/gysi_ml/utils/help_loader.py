from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_cache: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    global _cache
    if _cache is None:
        config_path = Path(__file__).parents[3] / "configs" / "help_texts.yaml"
        try:
            with open(config_path, encoding="utf-8") as f:
                _cache = yaml.safe_load(f) or {}
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"help_texts.yaml nicht gefunden: {config_path}"
            ) from exc
        except yaml.YAMLError as exc:
            raise ValueError(f"Ungültiges YAML in help_texts.yaml: {exc}") from exc
    return _cache


def load_help_text(key: str) -> str:
    data = _load_config()
    value = data.get(key)
    if not value:
        raise KeyError(f"Schlüssel '{key}' nicht in help_texts.yaml gefunden")
    return str(value)
