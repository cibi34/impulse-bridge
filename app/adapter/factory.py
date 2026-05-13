"""Build a concrete Source instance from a validated SourceConfig.

The factory is also responsible for mounting any per-source static directories
(used by the fallback adapter to serve local asset files).
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.adapter.base import Source
from app.adapter.fallback import FallbackSource
from app.adapter.rest import GenericRestSource
from app.config.schema import SourceConfig
from app.errors import ConfigError

logger = logging.getLogger(__name__)


def build_source(cfg: SourceConfig, config_path: Path, app: FastAPI) -> Source:
    kind = cfg.adapter.kind
    if kind == "fallback":
        return _build_fallback(cfg, config_path, app)
    if kind == "rest":
        return GenericRestSource(cfg)
    if kind == "custom":
        return _build_custom(cfg)
    raise ConfigError(f"Unknown adapter.kind: {kind}")


def _build_fallback(cfg: SourceConfig, config_path: Path, app: FastAPI) -> Source:
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
    source = FallbackSource(
        collection_meta=cfg.collection.model_dump(),
        manifest_path=manifest,
    )
    if cfg.adapter.static_mount:
        static_dir = manifest.parent
        mount_path = f"/collections/{cfg.collection.id}"
        app.mount(
            mount_path,
            StaticFiles(directory=static_dir),
            name=f"static-{cfg.collection.id}",
        )
        logger.info(
            "Mounted static files for '%s' at %s -> %s",
            cfg.collection.id,
            mount_path,
            static_dir,
        )
    return source


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
