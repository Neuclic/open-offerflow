from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from offerflow.errors import ErrorCode, OfferFlowError


DEFAULT_CONFIG = """llm_profiles:
  default:
    provider: openai-compatible
    base_url: https://api.deepseek.com
    model: deepseek-v4-flash
    api_key_env: DEEPSEEK_API_KEY

extractor:
  provider: mineru-html
  llm_profile: default
"""


def config_path(base_dir: Path | None = None) -> Path:
    return (base_dir or Path.cwd()) / "config.yaml"


def env_path(base_dir: Path | None = None) -> Path:
    return (base_dir or Path.cwd()) / ".env"


def ensure_default_config(base_dir: Path | None = None) -> tuple[Path, bool]:
    path = config_path(base_dir)
    if path.exists():
        return path, False
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return path, True


def load_env_file(base_dir: Path | None = None) -> dict[str, str]:
    path = env_path(base_dir)
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def load_config(base_dir: Path | None = None, *, required: bool = True) -> dict[str, Any]:
    path = config_path(base_dir)
    if not path.exists():
        if required:
            raise OfferFlowError(
                ErrorCode.CONFIG_NOT_FOUND,
                "Project config.yaml was not found.",
                {"config_path": str(path)},
                exit_code=1,
            )
        return {}

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "config.yaml must contain a mapping at the top level.",
            {"config_path": str(path)},
            exit_code=1,
        )
    return data
