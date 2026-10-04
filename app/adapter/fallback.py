from __future__ import annotations

import json
import logging
import struct
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.errors import AssetNotFound, ConfigError
from app.transform.helpers import matches_pattern

logger = logging.getLogger(__name__)


class FallbackSource:
    """A source backed by static JSON files on disk. Useful as a guaranteed-working
    demo collection, and as a stand-in when external archives are unreachable."""

    def __init__(
        self,
        collection_meta: dict[str, Any],
        manifest_path: Path,
        files_dir: Path | None = None,
    ) -> None:
        self.collection_meta = collection_meta
        self.files_dir = files_dir
        """Directory whose files are served at /sources/{id}/files/, or None."""
        cid = collection_meta["id"]
        if not manifest_path.exists():
            raise ConfigError(f"Fallback manifest not found: {manifest_path}")
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(f"Fallback manifest is not valid JSON ({manifest_path}): {e}") from e
        if not isinstance(raw, list):
            raise ConfigError(f"Fallback manifest must be a JSON array: {manifest_path}")
        self._assets: list[dict] = [self._with_details(a, manifest_path.parent) for a in raw]
        self._by_id: dict[str, dict] = {a["assetID"]: a for a in self._assets if "assetID" in a}
        logger.info("FallbackSource '%s' loaded %d assets", cid, len(self._assets))

    @staticmethod
    def _with_details(asset: Any, folder: Path) -> Any:
        """Add the file size (and a PNG's pixel size) of a local media file
        the manifest doesn't state itself."""
        uri = asset.get("assetURI") if isinstance(asset, dict) else None
        if not isinstance(uri, str) or urlparse(uri).scheme:
            return asset
        path = (folder / uri).resolve()
        if folder.resolve() not in path.parents or not path.is_file():
            return asset
        out = dict(asset)
        out.setdefault("fileSize", path.stat().st_size)
        if path.suffix.lower() == ".png" and "width" not in out:
            with path.open("rb") as f:
                head = f.read(24)
            if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
                out["width"], out["height"] = struct.unpack(">II", head[16:24])
        return out

    async def search(
        self, query: str | None, offset: int, count: int | None
    ) -> list[dict]:
        matched = [a for a in self._assets if matches_pattern(a, query)]
        end = (offset + count) if count is not None else None
        return matched[offset:end]

    async def get_asset(self, asset_id: str) -> dict:
        try:
            return self._by_id[asset_id]
        except KeyError as e:
            raise AssetNotFound(
                f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
            ) from e
