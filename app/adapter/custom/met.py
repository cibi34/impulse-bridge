"""The Metropolitan Museum of Art's Open Access API.

The Met's search (`/public/collection/v1.1/search`) answers with object ids
only, a page at a time; every object is a second request
(`/public/collection/v1/objects/{id}`). This adapter fetches a page's
objects in parallel and keeps each in the cache, so paging back and the
single-asset lookup cost nothing. Public-domain works are released under
CC0, which the adapter states as the rights; everything else is left out
upstream (`isPublicDomain=true`).

Without a search term the museum's highlights are shown, since the whole
collection sorted by id starts with centuries of unremarkable fragments.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.adapter.base import SearchPage, Source
from app.cache import cache
from app.config.schema import SourceConfig
from app.errors import AssetNotFound, UpstreamMalformed, UpstreamUnavailable
from app.settings import settings

logger = logging.getLogger(__name__)

_SEARCH = "/public/collection/v1.1/search"
_OBJECT = "/public/collection/v1/objects/{id}"
_DEFAULT_PAGE = 12
_MAX_PAGE = 50
_PARALLEL_OBJECTS = 6


class MetSource(Source):
    def __init__(self, cfg: SourceConfig) -> None:
        self._cfg = cfg
        self.collection_meta = cfg.collection.model_dump()
        self._base_url = (cfg.adapter.base_url or "https://collectionapi.metmuseum.org").rstrip("/")
        self._ttl = cfg.cache.ttl_seconds
        self._client = httpx.AsyncClient(
            timeout=cfg.adapter.timeout_seconds,
            headers={"User-Agent": f"IMPULSE-Curator/0.1 (+{settings.public_base_url})"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- upstream -------------------------------------------------------

    async def _get_json(self, path: str, params: dict[str, str]) -> Any:
        key = cache.key(self.collection_meta["id"], path, params)
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            response = await self._client.get(self._base_url + path, params=params)
        except httpx.HTTPError as e:
            raise UpstreamUnavailable(f"The Met did not answer: {e}") from e
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise UpstreamUnavailable(f"The Met answered {response.status_code}")
        try:
            data = response.json()
        except ValueError as e:
            raise UpstreamMalformed(f"The Met sent no JSON: {e}") from e
        cache.set(key, data, ttl=self._ttl)
        return data

    async def _object(self, object_id: int) -> dict | None:
        data = await self._get_json(_OBJECT.format(id=object_id), {})
        return data if isinstance(data, dict) else None

    async def _objects(self, ids: list[int]) -> list[dict]:
        """The objects behind `ids`, in order; one that fails is left out."""
        gate = asyncio.Semaphore(_PARALLEL_OBJECTS)

        async def one(object_id: int) -> dict | None:
            async with gate:
                try:
                    return await self._object(object_id)
                except (UpstreamUnavailable, UpstreamMalformed) as e:
                    logger.warning("The Met: object %s skipped: %s", object_id, e)
                    return None

        found = await asyncio.gather(*(one(i) for i in ids))
        return [o for o in found if o]

    # ---- Impulse assets ----------------------------------------------------

    @staticmethod
    def _asset(o: dict) -> dict | None:
        image = o.get("primaryImage")
        if not image:
            return None
        tags = [t.get("term") for t in o.get("tags") or [] if isinstance(t, dict) and t.get("term")]
        rights = "CC0 1.0" if o.get("isPublicDomain") else (o.get("rightsAndReproduction") or "See source for license")
        details = [
            {"label": label, "value": str(o[key]).strip()}
            for label, key in (
                ("Artist", "artistDisplayBio"),
                ("Dimensions", "dimensions"),
                ("Classification", "classification"),
                ("Period", "period"),
                ("Culture", "culture"),
                ("Department", "department"),
                ("Credit line", "creditLine"),
                ("Accession number", "accessionNumber"),
                ("Accession year", "accessionYear"),
                ("Gallery", "GalleryNumber"),
            )
            if o.get(key) not in (None, "", [])
        ]
        asset = {
            "assetID": str(o.get("objectID")),
            "title": o.get("title") or "Untitled",
            "creator": o.get("artistDisplayName") or None,
            "date": o.get("objectDate") or None,
            "rights": rights,
            "identifier": o.get("objectURL") or None,
            "assetURI": image,
            "previewURI": o.get("primaryImageSmall") or image,
            "contentType": "image/jpeg",
            "contributor": "The Metropolitan Museum of Art",
            "scale": "1",
            "type": o.get("objectName") or o.get("classification") or None,
            "format": o.get("medium") or None,
            "coverage": o.get("culture") or o.get("country") or None,
            "subject": ", ".join(tags[:5]) or None,
            "details": details or None,
            "published": 1,
        }
        return {k: v for k, v in asset.items() if v is not None}

    # ---- Source protocol ---------------------------------------------------

    async def search_page(self, query: str | None, offset: int, count: int | None) -> SearchPage:
        size = min(count or _DEFAULT_PAGE, _MAX_PAGE)
        # adapter.default_query narrows every search, e.g. to one department.
        params = {str(k): str(v) for k, v in (self._cfg.adapter.default_query or {}).items()}
        params.update({
            "hasImages": "true",
            "isPublicDomain": "true",
            "offset": str(max(offset, 0)),
            "limit": str(size),
        })
        q = (query or "").strip()
        if q and q != "*":
            params["q"] = q
        else:
            params["isHighlight"] = "true"
        data = await self._get_json(_SEARCH, params)
        ids = [i for i in ((data or {}).get("objectIDs") or []) if isinstance(i, int)]
        objects = await self._objects(ids)
        assets = [a for a in (self._asset(o) for o in objects) if a]
        return SearchPage(items=assets, upstream_count=len(ids), page_size=size)

    async def search(self, query: str | None, offset: int, count: int | None) -> list[dict]:
        return (await self.search_page(query=query, offset=offset, count=count)).items

    async def get_asset(self, asset_id: str) -> dict:
        not_found = AssetNotFound(
            f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
        )
        if not asset_id.isdigit():
            raise not_found
        o = await self._object(int(asset_id))
        asset = self._asset(o) if o else None
        if asset is None:
            raise not_found
        return asset
