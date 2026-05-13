from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.errors import CollectionNotFound

if TYPE_CHECKING:
    from app.adapter.base import Source

logger = logging.getLogger(__name__)


class Registry:
    """In-memory map collection_id -> Source. Loaded at startup, can be hot-
    reloaded from disk by the admin API."""

    def __init__(self) -> None:
        self._sources: dict[str, "Source"] = {}
        self._files: dict[str, Path] = {}
        self._load_errors: list[tuple[str, str]] = []
        """List of (filename, error_message) collected during the last load."""

    def register(self, source: "Source", source_file: Path | None = None) -> None:
        cid = source.collection_meta["id"]
        if cid in self._sources:
            raise ValueError(f"Duplicate collection id: {cid}")
        self._sources[cid] = source
        if source_file is not None:
            self._files[cid] = source_file

    def get(self, collection_id: str) -> "Source":
        try:
            return self._sources[collection_id]
        except KeyError as e:
            raise CollectionNotFound(
                f"Collection '{collection_id}' is not registered with this bridge"
            ) from e

    def list_collections(self) -> list[dict]:
        return [s.collection_meta for s in self._sources.values()]

    def list_sources(self) -> list["Source"]:
        return list(self._sources.values())

    def file_for(self, collection_id: str) -> Path | None:
        return self._files.get(collection_id)

    def errors(self) -> list[tuple[str, str]]:
        return list(self._load_errors)

    async def clear(self) -> None:
        """Stop all sources cleanly and empty the registry."""
        for source in self._sources.values():
            closer = getattr(source, "aclose", None)
            if closer is not None:
                try:
                    await closer()
                except Exception as e:  # noqa: BLE001
                    logger.warning("error closing source: %s", e)
        self._sources.clear()
        self._files.clear()
        self._load_errors.clear()


registry = Registry()
