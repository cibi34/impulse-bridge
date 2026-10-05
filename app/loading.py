"""(Re)load all source configs from disk into the registry.

Used at startup and by the admin API's save / delete / reload actions.
Everything is built first and swapped in at once, so a reload never leaves the
bridge with a partial or empty registry: broken files are skipped and reported
via `registry.errors()`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.adapter.base import Source
from app.adapter.factory import build_source
from app.config.loader import load_all
from app.errors import ConfigError
from app.registry import registry
from app.settings import settings

logger = logging.getLogger(__name__)


async def load_sources() -> None:
    configs, errors = load_all(settings.config_dir)
    sources: dict[str, Source] = {}
    files: dict[str, Path] = {}
    # The web app lists sources in this order: `order` from the YAML, then filename.
    for path, cfg in sorted(configs, key=lambda pair: (pair[1].order, pair[0].name)):
        cid = cfg.collection.id
        if cid in sources:
            errors.append(
                (path.name, f"Duplicate collection id '{cid}' (already defined in {files[cid].name})")
            )
            continue
        try:
            source = build_source(cfg)
        except ConfigError as e:
            errors.append((path.name, str(e)))
            continue
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to build source from %s", path.name)
            errors.append((path.name, str(e)))
            continue
        sources[cid] = source
        files[cid] = path

    for filename, message in errors:
        logger.error("Source config %s not loaded: %s", filename, message)
    registry.swap(sources, files, errors)
    logger.info("Registered %d source(s), %d config error(s)", len(sources), len(errors))
