from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.errors import CollectionNotFound

if TYPE_CHECKING:
    from app.adapter.base import Source

logger = logging.getLogger(__name__)

RETIRE_GRACE_SECONDS = 60.0
"""How long a replaced source stays open after a reload, so requests that are
already running on it (upstream timeout + one retry) can finish."""


async def _close_all(sources: list["Source"]) -> None:
    for source in sources:
        closer = getattr(source, "aclose", None)
        if closer is not None:
            try:
                await closer()
            except Exception as e:  # noqa: BLE001
                logger.warning("error closing source: %s", e)


class Registry:
    """In-memory map collection_id -> Source. Loaded at startup, can be hot-
    reloaded from disk by the admin API."""

    def __init__(self) -> None:
        self._sources: dict[str, "Source"] = {}
        self._files: dict[str, Path] = {}
        self._load_errors: list[tuple[str, str]] = []
        """List of (filename, error_message) collected during the last load."""
        self._retiring: dict[asyncio.Task, list["Source"]] = {}
        """Replaced sources waiting to be closed, keyed by their closing task."""

    def swap(
        self,
        sources: dict[str, "Source"],
        files: dict[str, Path],
        errors: list[tuple[str, str]],
    ) -> None:
        """Replace the whole registry at once, so requests see either the old or
        the new set of sources, never a half-loaded one. Replaced sources are
        closed after RETIRE_GRACE_SECONDS."""
        retired = list(self._sources.values())
        self._sources, self._files, self._load_errors = dict(sources), dict(files), list(errors)
        if retired:
            task = asyncio.create_task(self._close_after(retired, RETIRE_GRACE_SECONDS))
            self._retiring[task] = retired
            task.add_done_callback(self._forget_retired)

    @staticmethod
    async def _close_after(sources: list["Source"], delay: float) -> None:
        await asyncio.sleep(delay)
        await _close_all(sources)

    def _forget_retired(self, task: asyncio.Task) -> None:
        if not task.cancelled():
            self._retiring.pop(task, None)

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
        """Stop all sources (including retired ones) and empty the registry."""
        pending = list(self._retiring.items())
        self._retiring.clear()
        for task, _ in pending:
            task.cancel()
        await asyncio.gather(*(task for task, _ in pending), return_exceptions=True)
        for task, sources in pending:
            # A task cancelled before or while closing leaves the work to us.
            if task.cancelled():
                await _close_all(sources)
        await _close_all(list(self._sources.values()))
        self._sources.clear()
        self._files.clear()
        self._load_errors.clear()


registry = Registry()
