"""IIIF Presentation-API adapter.

One bridge collection = one IIIF manifest. Each canvas in the manifest becomes
an Impulse asset; the image referenced by the canvas's painting annotation is
the assetURI (high-res via the IIIF Image API), the previewURI uses a smaller
thumbnail size.

Supports both Presentation API v2 (`sequences[].canvases[]`, `@id`) and v3
(top-level `items[]` of Canvases, `id`). Cross-provider search via Change
Discovery is out of scope for the POC — a separate YAML config per manifest
provides predictable, demoable behavior.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.adapter.base import Source
from app.cache import cache
from app.config.schema import SourceConfig
from app.errors import (
    AssetNotFound,
    ConfigError,
    UpstreamMalformed,
    UpstreamUnavailable,
)
from app.transform.helpers import slugify

logger = logging.getLogger(__name__)


def _label_to_str(label: Any) -> str | None:
    """Normalize IIIF label values: v2 is a string, v3 is a language-keyed dict."""
    if isinstance(label, str):
        return label
    if isinstance(label, dict):
        for k in ("en", "none", "@none"):
            v = label.get(k)
            if isinstance(v, list) and v:
                return str(v[0])
            if isinstance(v, str):
                return v
        for v in label.values():
            if isinstance(v, list) and v:
                return str(v[0])
            if isinstance(v, str):
                return v
    return None


_IIIF_IMAGE_API_PATH = re.compile(r"/full/[^/]+/0/default\.\w+$")


def _to_image_url(body_id: str, size: str = "max") -> str:
    """Derive a Image-API URL with a specific size from a canvas body URL.

    Many manifests provide a body.id that's already a /full/.../default.jpg
    URL — we just rewrite the size segment. If the URL doesn't look like a
    Image API URL, return it unchanged."""
    if _IIIF_IMAGE_API_PATH.search(body_id):
        return _IIIF_IMAGE_API_PATH.sub(f"/full/{size}/0/default.jpg", body_id)
    return body_id


def _extract_canvases_v3(manifest: dict) -> list[dict]:
    return [c for c in (manifest.get("items") or []) if c.get("type") == "Canvas"]


def _extract_canvases_v2(manifest: dict) -> list[dict]:
    out: list[dict] = []
    for seq in manifest.get("sequences") or []:
        out.extend(seq.get("canvases") or [])
    return out


def _canvas_image_url_v3(canvas: dict) -> str | None:
    for ap in canvas.get("items") or []:
        for ann in ap.get("items") or []:
            if ann.get("motivation") != "painting":
                continue
            body = ann.get("body") or {}
            if isinstance(body, list):
                body = body[0] if body else {}
            body_id = body.get("id")
            if isinstance(body_id, str):
                return body_id
    return None


def _canvas_image_url_v2(canvas: dict) -> str | None:
    for img in canvas.get("images") or []:
        resource = img.get("resource") or {}
        rid = resource.get("@id") or resource.get("id")
        if isinstance(rid, str):
            return rid
    return None


class IIIFManifestSource(Source):
    """A Source backed by a single IIIF Presentation API manifest."""

    def __init__(self, cfg: SourceConfig) -> None:
        self._cfg = cfg
        self.collection_meta = cfg.collection.model_dump()
        if not cfg.adapter.base_url:
            raise ConfigError(
                f"IIIF source '{cfg.collection.id}' requires adapter.base_url "
                f"set to the manifest URL"
            )
        self._manifest_url = cfg.adapter.base_url
        self._client = httpx.AsyncClient(timeout=cfg.adapter.timeout_seconds)
        self._assets: list[dict] | None = None
        self._by_id: dict[str, dict] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _load_assets(self) -> list[dict]:
        if self._assets is not None:
            return self._assets
        cache_key = cache.key(self.collection_meta["id"], self._manifest_url, {})
        cached = cache.get(cache_key)
        if cached is not None:
            manifest = cached
        else:
            try:
                response = await self._client.get(
                    self._manifest_url,
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as e:
                raise UpstreamUnavailable(f"IIIF manifest fetch failed: {e}") from e
            if response.status_code >= 400:
                raise UpstreamUnavailable(
                    f"IIIF manifest returned {response.status_code}"
                )
            try:
                manifest = response.json()
            except ValueError as e:
                raise UpstreamMalformed(f"IIIF manifest is not JSON: {e}") from e
            cache.set(cache_key, manifest)

        is_v3 = "items" in manifest and "sequences" not in manifest
        canvases = _extract_canvases_v3(manifest) if is_v3 else _extract_canvases_v2(manifest)
        manifest_label = _label_to_str(manifest.get("label")) or "IIIF Manifest"
        rights = manifest.get("rights") or manifest.get("license") or "See manifest"

        assets: list[dict] = []
        for idx, canvas in enumerate(canvases):
            body_id = (
                _canvas_image_url_v3(canvas) if is_v3 else _canvas_image_url_v2(canvas)
            )
            if not body_id:
                continue
            canvas_id = canvas.get("id") or canvas.get("@id") or f"canvas-{idx}"
            label = _label_to_str(canvas.get("label")) or f"{manifest_label} ({idx + 1})"
            asset = {
                "assetID": slugify(canvas_id.rsplit("/", 1)[-1] or f"canvas-{idx}"),
                "title": label,
                "assetURI": _to_image_url(body_id, "max"),
                "previewURI": _to_image_url(body_id, "!400,400"),
                "contentType": "image/jpeg",
                "scale": "1",
                "rights": str(rights),
                "identifier": canvas_id,
                "contributor": manifest_label,
                "type": "Image",
                "published": 1,
            }
            assets.append(asset)
            self._by_id[asset["assetID"]] = asset

        logger.info(
            "IIIFManifestSource '%s' parsed %d canvases (%d with images)",
            self.collection_meta["id"],
            len(canvases),
            len(assets),
        )
        self._assets = assets
        return assets

    async def search(
        self, query: str | None, offset: int, count: int | None
    ) -> list[dict]:
        assets = await self._load_assets()
        pattern = (query or "").strip().lower()
        if pattern and pattern != "*":
            chunks = [c for c in pattern.split("*") if c]
            def keep(a: dict) -> bool:
                hay = " ".join(str(a.get(k, "")) for k in ("title", "identifier"))
                hay = hay.lower()
                pos = 0
                for ch in chunks:
                    idx = hay.find(ch, pos)
                    if idx < 0:
                        return False
                    pos = idx + len(ch)
                return True
            filtered = [a for a in assets if keep(a)]
        else:
            filtered = assets
        end = (offset + count) if count is not None else None
        return filtered[offset:end]

    async def get_asset(self, asset_id: str) -> dict:
        await self._load_assets()
        try:
            return self._by_id[asset_id]
        except KeyError as e:
            raise AssetNotFound(
                f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
            ) from e
