from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.errors import AssetNotFound, ConfigError

logger = logging.getLogger(__name__)


def _matches(asset: dict, pattern: str) -> bool:
    """Case-insensitive substring search across the typical text fields.

    Pattern '*' (or empty after stripping) matches everything. Internal '*' wildcards
    behave like substring delimiters (split on '*' and require each chunk to appear
    in order)."""
    if not pattern or pattern == "*":
        return True
    chunks = [c.lower() for c in pattern.split("*") if c]
    haystack_parts: list[str] = []
    for key in ("title", "description", "subject", "creator", "contributor", "type", "assetID"):
        v = asset.get(key)
        if isinstance(v, str):
            haystack_parts.append(v.lower())
    haystack = " | ".join(haystack_parts)
    pos = 0
    for chunk in chunks:
        idx = haystack.find(chunk, pos)
        if idx < 0:
            return False
        pos = idx + len(chunk)
    return True


class FallbackSource:
    """A source backed by static JSON files on disk. Useful as a guaranteed-working
    demo collection, and as a stand-in when external archives are unreachable."""

    def __init__(
        self,
        collection_meta: dict[str, Any],
        manifest_path: Path,
    ) -> None:
        self.collection_meta = collection_meta
        cid = collection_meta["id"]
        if not manifest_path.exists():
            raise ConfigError(f"Fallback manifest not found: {manifest_path}")
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(f"Fallback manifest is not valid JSON ({manifest_path}): {e}") from e
        if not isinstance(raw, list):
            raise ConfigError(f"Fallback manifest must be a JSON array: {manifest_path}")
        self._assets: list[dict] = raw
        self._by_id: dict[str, dict] = {a["assetID"]: a for a in raw if "assetID" in a}
        logger.info("FallbackSource '%s' loaded %d assets", cid, len(self._assets))

    async def search(
        self, query: str | None, offset: int, count: int | None
    ) -> list[dict]:
        pattern = (query or "").strip()
        matched = [a for a in self._assets if _matches(a, pattern)]
        end = (offset + count) if count is not None else None
        return matched[offset:end]

    async def get_asset(self, asset_id: str) -> dict:
        try:
            return self._by_id[asset_id]
        except KeyError as e:
            raise AssetNotFound(
                f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
            ) from e
