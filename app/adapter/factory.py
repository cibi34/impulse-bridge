"""Build a concrete Source instance from a validated SourceConfig."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

from app.adapter.base import Source
from app.adapter.fallback import FallbackSource
from app.adapter.rest import GenericRestSource
from app.config.schema import SourceConfig
from app.errors import ConfigError

logger = logging.getLogger(__name__)


def build_source(cfg: SourceConfig) -> Source:
    kind = cfg.adapter.kind
    if kind == "fallback":
        return _build_fallback(cfg)
    if kind == "rest":
        return GenericRestSource(cfg)
    if kind == "custom":
        return _build_custom(cfg)
    raise ConfigError(f"Unknown adapter.kind: {kind}")


def _build_fallback(cfg: SourceConfig) -> Source:
    if not cfg.adapter.manifest_path:
        raise ConfigError(
            f"fallback adapter requires adapter.manifest_path "
            f"(collection '{cfg.collection.id}')"
        )
    # Manifest paths are resolved relative to the project root (CWD), matching
    # how other path-style settings (data_dir, config_dir) behave.
    manifest = Path(cfg.adapter.manifest_path)
    if not manifest.is_absolute():
        manifest = Path.cwd() / manifest
    return FallbackSource(
        collection_meta=cfg.collection.model_dump(),
        manifest_path=manifest,
        # Relative assetURIs/previewURIs in the manifest resolve against the
        # collection URI, so the files next to the manifest are served there
        # (see app/api/files.py).
        files_dir=manifest.parent if cfg.adapter.static_mount else None,
    )


def _build_custom(cfg: SourceConfig) -> Source:
    if not cfg.adapter.custom_class:
        raise ConfigError("adapter.kind=custom requires adapter.custom_class")
    module_name, _, class_name = cfg.adapter.custom_class.rpartition(".")
    if not module_name:
        raise ConfigError(
            f"adapter.custom_class must be a dotted path, got '{cfg.adapter.custom_class}'"
        )
    try:
        module = importlib.import_module(module_name)
        klass = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ConfigError(f"Cannot load custom class '{cfg.adapter.custom_class}': {e}") from e
    return klass(cfg)
