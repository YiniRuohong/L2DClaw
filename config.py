from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml

ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_config(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return _expand_env(data)


def load_user_prefs() -> Dict[str, Any]:
    prefs_path = Path.home() / ".l2dclaw" / "user_prefs.yaml"
    if not prefs_path.exists():
        return {}

    with prefs_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return _expand_env(data)


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), value)
    return value
