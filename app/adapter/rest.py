"""Generic configuration-driven REST adapter.

A single class that — for the 95% case — turns any external REST search/discovery
API into an Impulse-schema source by following a YAML mapping. It handles auth
injection, three pagination styles, search-pattern translation, and delegates
field mapping to the transform engine.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.adapter.base import Source
from app.cache import cache
from app.config.schema import PaginationCfg, SourceConfig
from app.errors import (
    AssetNotFound,
    ConfigError,
    UpstreamMalformed,
    UpstreamRateLimited,
    UpstreamUnavailable,
)
from app.transform.engine import extract_items, transform_item

logger = logging.getLogger(__name__)


class GenericRestSource(Source):
    """A Source backed by an HTTP REST API, configured entirely via YAML."""

    def __init__(self, cfg: SourceConfig) -> None:
        self._cfg = cfg
        self.collection_meta = cfg.collection.model_dump()
        if not cfg.adapter.base_url:
            from app.errors import ConfigError
            raise ConfigError(
                f"rest adapter requires adapter.base_url (collection '{cfg.collection.id}')"
            )
        self._client = httpx.AsyncClient(
            base_url=cfg.adapter.base_url,
            timeout=cfg.adapter.timeout_seconds,
        )
        # Inspection state — populated on every upstream call so the admin UI
        # can show the actual URL we hit and the raw JSON we received.
        self.last_upstream_url: str | None = None
        self.last_raw_response: Any = None

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- public Source protocol ----

    async def search(
        self, query: str | None, offset: int, count: int | None
    ) -> list[dict]:
        params = self._build_params(query=query, offset=offset, count=count)
        raw = await self._http_get(self._cfg.search.path, params)
        items = extract_items(raw, self._cfg.mapping.items_path)
        return self._map_and_filter(items)

    async def get_asset(self, asset_id: str) -> dict:
        detail = self._cfg.asset_detail
        if not detail.enabled or not detail.path:
            # Fallback: scan the default search result for a matching id. Works
            # for small collections; sources with many assets should configure
            # asset_detail with a proper upstream lookup.
            assets = await self.search(query=None, offset=0, count=None)
            for a in assets:
                if a.get("assetID") == asset_id:
                    return a
            raise AssetNotFound(
                f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
            )
        path = detail.path.replace("{asset_id}", asset_id)
        # detail.query is the COMPLETE query for the detail endpoint (not merged
        # with search's default_query, since the two endpoints typically take
        # different params — e.g. MediaWiki's generator=search vs. pageids=X).
        params: dict[str, str] = {}
        auth = self._cfg.adapter.auth
        if auth.type == "query_param" and auth.name and auth.value:
            params[auth.name] = auth.value
        for k, v in detail.query.items():
            params[k] = v.replace("{asset_id}", asset_id)
        raw = await self._http_get(path, params)
        mapping = detail.mapping or self._cfg.mapping
        items = extract_items(raw, mapping.items_path) if mapping.items_path else [raw]
        for item in items:
            asset = transform_item(item, mapping, self._cfg.filter)
            if asset is not None:
                return asset
        raise AssetNotFound(
            f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
        )

    # ---- internals ----

    def _build_params(
        self, query: str | None, offset: int, count: int | None
    ) -> dict[str, str]:
        params: dict[str, str] = dict(self._cfg.adapter.default_query)

        # Auth via query param
        auth = self._cfg.adapter.auth
        if auth.type == "query_param" and auth.name and auth.value:
            params[auth.name] = auth.value

        # Search pattern
        q = (query or "").strip()
        if not q:
            q = self._cfg.search.query.pattern_when_empty
        else:
            wc = self._cfg.search.query.wildcard_translation
            if wc.from_ and wc.from_ != wc.to:
                q = q.replace(wc.from_, wc.to)
        if self._cfg.search.query.pattern_param:
            params[self._cfg.search.query.pattern_param] = q

        # Pagination
        self._apply_pagination_params(params, offset=offset, count=count)
        return params

    def _apply_pagination_params(
        self, params: dict[str, str], offset: int, count: int | None
    ) -> None:
        p = self._cfg.search.pagination
        size = count if count is not None else p.max_size
        size = min(size, p.max_size)
        if p.style == "page_size" and p.page_param and p.size_param:
            # offset -> page number (1-based or 0-based per page_base)
            page = (offset // max(size, 1)) + p.page_base
            params[p.page_param] = str(page)
            params[p.size_param] = str(size)
        elif p.style == "offset_limit" and p.offset_param and p.limit_param:
            params[p.offset_param] = str(offset)
            params[p.limit_param] = str(size)
        elif p.style == "cursor":
            # Cursor pagination is stateful and doesn't compose naturally with
            # Impulse's offset/count semantics; the bridge requests size only.
            if p.limit_param:
                params[p.limit_param] = str(size)
        # style="none": nothing to add

    def _headers(self) -> dict[str, str]:
        # Wikimedia's bot policy requires a contactable UA. Most upstream APIs
        # are happier with a descriptive UA too, so this is the safe default.
        h: dict[str, str] = {
            "User-Agent": (
                "ImpulseBridge/0.1 "
                "(https://github.com/impulse-consortium/impulse-bridge; "
                "bridge@impulse.eu)"
            ),
            "Accept": "application/json",
        }
        auth = self._cfg.adapter.auth
        if auth.type == "header" and auth.name and auth.value:
            h[auth.name] = auth.value
        return h

    async def _http_get(self, path: str, params: dict[str, str]) -> Any:
        source_id = self.collection_meta["id"]
        cache_key = cache.key(source_id, path, params)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("cache hit: source=%s path=%s", source_id, path)
            return cached

        # One retry on transient timeout, otherwise let the error propagate.
        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                response = await self._client.get(
                    path, params=params, headers=self._headers()
                )
                self.last_upstream_url = str(response.url)
                break
            except httpx.TimeoutException as e:
                last_exc = e
                if attempt == 1:
                    await asyncio.sleep(1.0)
                    continue
                raise UpstreamUnavailable(f"Upstream timeout after retry: {e}") from e
            except httpx.HTTPError as e:
                raise UpstreamUnavailable(f"Upstream error: {e}") from e

        if response.status_code == 429:
            raise UpstreamRateLimited("Upstream returned 429")
        if response.status_code in (401, 403):
            raise ConfigError(
                f"Upstream auth failed ({response.status_code}); "
                f"check API key for this source. Upstream said: {response.text[:160]}"
            )
        if response.status_code >= 500:
            raise UpstreamUnavailable(f"Upstream {response.status_code}")
        if response.status_code >= 400:
            raise UpstreamMalformed(
                f"Upstream {response.status_code}: {response.text[:200]}"
            )

        try:
            payload = response.json()
        except ValueError as e:
            raise UpstreamMalformed(f"Upstream returned non-JSON: {e}") from e

        self.last_raw_response = payload
        cache.set(cache_key, payload)
        return payload

    def _map_and_filter(self, raw_items: list[dict]) -> list[dict]:
        out: list[dict] = []
        for raw in raw_items:
            asset = transform_item(raw, self._cfg.mapping, self._cfg.filter)
            if asset is not None:
                out.append(asset)
        return out
