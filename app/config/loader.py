"""YAML config loader with ${ENV_VAR} expansion and strict Pydantic validation.

`load_one` raises ConfigError for invalid YAML or a schema violation.
`load_all` collects those errors per file instead, so one broken config only
disables its own source (the admin UI shows the error) and never the bridge.
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


def load_all(
    config_dir: Path,
) -> tuple[list[tuple[Path, SourceConfig]], list[tuple[str, str]]]:
    """Load every *.yaml / *.yml file in `config_dir`, ordered by filename.

    A broken file does not stop the others from loading: it is reported in the
    second list as (filename, error message) and skipped. Returns
    ((path, config) pairs, errors)."""
    if not config_dir.exists():
        logger.warning("Config dir %s does not exist — no sources will load", config_dir)
        return [], []
    files = sorted(
        [p for p in config_dir.iterdir() if p.suffix in {".yaml", ".yml"} and p.is_file()]
    )
    configs: list[tuple[Path, SourceConfig]] = []
    errors: list[tuple[str, str]] = []
    for f in files:
        try:
            cfg = load_one(f)
        except ConfigError as e:
            errors.append((f.name, e.message))
            continue
        logger.info("Loaded source config: %s -> collection '%s'", f.name, cfg.collection.id)
        configs.append((f, cfg))
    return configs, errors
