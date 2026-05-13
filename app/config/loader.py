"""YAML config loader with ${ENV_VAR} expansion and strict Pydantic validation.

Fail-fast on startup: any invalid YAML, schema violation, or missing required ENV
variable raises ConfigError and prevents the app from accepting requests.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.config.schema import SourceConfig
from app.errors import ConfigError

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env(value: object) -> object:
    """Recursively expand ${VAR} references in any nested string values.

    Missing ENV vars become empty strings; the schema's required-field validation
    will catch cases where this leaves a critical field blank."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_one(path: Path) -> SourceConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping in {path}")
    expanded = _expand_env(raw)
    try:
        return SourceConfig.model_validate(expanded)
    except ValidationError as e:
        raise ConfigError(f"Schema validation failed for {path}:\n{e}") from e


def load_all(config_dir: Path) -> list[tuple[Path, SourceConfig]]:
    """Load every *.yaml / *.yml file in `config_dir`. Order by filename for
    determinism. Returns (path, config) pairs so callers can log per-source."""
    if not config_dir.exists():
        logger.warning("Config dir %s does not exist — no sources will load", config_dir)
        return []
    files = sorted(
        [p for p in config_dir.iterdir() if p.suffix in {".yaml", ".yml"} and p.is_file()]
    )
    result: list[tuple[Path, SourceConfig]] = []
    for f in files:
        cfg = load_one(f)
        logger.info("Loaded source config: %s -> collection '%s'", f.name, cfg.collection.id)
        result.append((f, cfg))
    return result
