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

_LANGUAGES = ("en", "de", "none", "@none")


def _label_to_str(label: Any) -> str | None:
    """Normalize IIIF text values: a v2 string, a v2 `{"@language", "@value"}`
    (or a list of them), or a v3 language-keyed dict."""
    if isinstance(label, str):
        return label
    if isinstance(label, list):
        by_lang = {
            str(v.get("@language") or "none"): v.get("@value")
            for v in label
            if isinstance(v, dict) and v.get("@value")
        }
        if by_lang:
            return _label_to_str({k: [v] for k, v in by_lang.items()})
        for v in label:
            if text := _label_to_str(v):
                return text
        return None
    if isinstance(label, dict):
        if "@value" in label:
            return _label_to_str(label["@value"])
        for k in _LANGUAGES:
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
_MEANINGFUL = re.compile(r"\w")
# Canvas labels that only number the page: "3r", "fol. 12v", "p. 7", "page 3", "xii".
_PAGE_NUMBER = re.compile(
    r"(?:(?:p|pp|page|pages|fol|folio|f|s|seite|bl|blatt)\.?\s*)?[\divxlc]+\s*[rvab]?", re.I
)


def _to_image_url(body_id: str, size: str = "max") -> str:
    """Derive a Image-API URL with a specific size from a canvas body URL.

    Many manifests provide a body.id that's already a /full/.../default.jpg
    URL — we just rewrite the size segment. If the URL doesn't look like a
    Image API URL, return it unchanged."""
    if _IIIF_IMAGE_API_PATH.search(body_id):
        return _IIIF_IMAGE_API_PATH.sub(f"/full/{size}/0/default.jpg", body_id)
    return body_id


def _service_id(resource: dict) -> str | None:
    """The Image API service behind an image resource, if it names one."""
    service = resource.get("service")
    if isinstance(service, list):
        service = service[0] if service else None
    if isinstance(service, dict):
        sid = service.get("@id") or service.get("id")
        return sid.rstrip("/") if isinstance(sid, str) else None
    return None


def _extract_canvases_v3(manifest: dict) -> list[dict]:
    return [c for c in (manifest.get("items") or []) if c.get("type") == "Canvas"]


def _extract_canvases_v2(manifest: dict) -> list[dict]:
    out: list[dict] = []
    for seq in manifest.get("sequences") or []:
        out.extend(seq.get("canvases") or [])
    return out


def _canvas_image_v3(canvas: dict) -> dict | None:
    for ap in canvas.get("items") or []:
        for ann in ap.get("items") or []:
            if ann.get("motivation") != "painting":
                continue
            body = ann.get("body") or {}
            if isinstance(body, list):
                body = body[0] if body else {}
            if isinstance(body.get("id"), str):
                return body
    return None


def _canvas_image_v2(canvas: dict) -> dict | None:
    for img in canvas.get("images") or []:
        resource = img.get("resource") or {}
        if isinstance(resource.get("@id") or resource.get("id"), str):
            return resource
    return None


def _canvas_sections(manifest: dict) -> dict[str, str]:
    """Canvas id → the label of the section (IIIF range) it belongs to, from
    the manifest's table of contents. A canvas keeps the first section that
    lists it directly, so wrapper ranges that only hold other ranges don't
    claim it."""
    sections: dict[str, str] = {}

    def visit(range_: dict) -> None:
        label = _label_to_str(range_.get("label"))
        members = list(range_.get("canvases") or [])  # v2
        for item in list(range_.get("items") or []) + list(range_.get("members") or []):
            if isinstance(item, dict) and item.get("type") == "Canvas":
                members.append(item.get("id"))
            elif isinstance(item, dict) and item.get("@type") == "sc:Canvas":
                members.append(item.get("@id"))
            elif isinstance(item, dict) and item.get("type") == "Range":
                visit(item)
        for member in members:
            if isinstance(member, str) and label and member not in sections:
                sections[member.split("#", 1)[0]] = label

    for range_ in manifest.get("structures") or []:
        if isinstance(range_, dict):
            visit(range_)
    return sections


def _metadata(manifest: dict, *labels: str) -> str | None:
    """The first manifest `metadata` entry whose label is one of `labels`."""
    wanted = {label.lower() for label in labels}
    for entry in manifest.get("metadata") or []:
        if not isinstance(entry, dict):
            continue
        label = (_label_to_str(entry.get("label")) or "").strip().lower()
        if label in wanted and (value := _label_to_str(entry.get("value"))):
            return value
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
        if isinstance(rights, list):
            rights = rights[0] if rights else "See manifest"
        # Who holds the work: v2 `attribution`, v3 `requiredStatement`.
        holder = _label_to_str(manifest.get("attribution")) or _label_to_str(
            (manifest.get("requiredStatement") or {}).get("value")
        )
        description = _label_to_str(manifest.get("description")) or _label_to_str(
            (manifest.get("summary") or None)
        )
        date = _metadata(manifest, "date", "dates", "datum", "created", "publication date")
        place = _metadata(manifest, "location", "place", "ort", "origin")
        sections = _canvas_sections(manifest)

        assets: list[dict] = []
        for idx, canvas in enumerate(canvases):
            image = _canvas_image_v3(canvas) if is_v3 else _canvas_image_v2(canvas)
            if not image:
                continue
            body_id = image.get("id") or image.get("@id")
            canvas_id = canvas.get("id") or canvas.get("@id") or f"canvas-{idx}"
            label = _label_to_str(canvas.get("label"))
            if not label or not _MEANINGFUL.search(label):
                # Many manifests label canvases "-" or leave them empty.
                label = f"page {idx + 1}"
            section = sections.get(canvas_id)
            # "Kaiser Heinrich — 6r" when the table of contents names the
            # section, else "Book of Wonders — 6r" for a bare page number.
            if section:
                title = f"{section} — {label}"
            elif _PAGE_NUMBER.fullmatch(label):
                title = f"{manifest_label} — {label}"
            else:
                title = label
            # Prefer the Image API service: it sizes the image and sends
            # CORS headers, which a plain file URL next to it may not.
            service = _service_id(image)
            asset = {
                "assetID": slugify(canvas_id.rsplit("/", 1)[-1] or f"canvas-{idx}"),
                "title": title,
                "assetURI": (
                    f"{service}/full/max/0/default.jpg"
                    if service
                    else _to_image_url(body_id, "max")
                ),
                "previewURI": (
                    f"{service}/full/!400,400/0/default.jpg"
                    if service
                    else _to_image_url(body_id, "!400,400")
                ),
                "contentType": image.get("format") or "image/jpeg",
                "scale": "1",
                "rights": str(rights),
                "identifier": canvas_id,
                "contributor": holder or manifest_label,
                "type": "Image",
                "published": 1,
            }
            if description:
                asset["description"] = description
            if section:
                asset["subject"] = section
            if date:
                asset["date"] = date
            if place:
                asset["coverage"] = place
            # The page's size in pixels (the canvas, or the image on it).
            for key in ("width", "height"):
                size = canvas.get(key) or image.get(key)
                if isinstance(size, int) and size > 0:
                    asset[key] = size
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
                hay = " ".join(str(a.get(k, "")) for k in ("title", "subject", "identifier"))
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
