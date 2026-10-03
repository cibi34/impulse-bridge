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

from app.adapter.base import SearchPage, Source
from app.cache import cache
from app.config.schema import PaginationCfg, SourceConfig
from app.errors import (
    AssetNotFound,
    ConfigError,
    UpstreamMalformed,
    UpstreamNotFound,
    UpstreamRateLimited,
    UpstreamUnavailable,
)
from app.settings import settings
from app.transform.engine import extract_items, transform_item
from app.transform.helpers import base32_id_decode, slug_to_regex

logger = logging.getLogger(__name__)


def _substitute(template: str, substitutions: dict[str, str]) -> str:
    for placeholder, value in substitutions.items():
        template = template.replace(placeholder, value)
    return template


class GenericRestSource(Source):
    """A Source backed by an HTTP REST API, configured entirely via YAML."""

    def __init__(self, cfg: SourceConfig) -> None:
        self._cfg = cfg
        self.collection_meta = cfg.collection.model_dump()
        if not cfg.adapter.base_url:
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
        return (await self.search_page(query=query, offset=offset, count=count)).items

    async def search_page(
        self, query: str | None, offset: int, count: int | None
    ) -> SearchPage:
        params = self._build_params(query=query, offset=offset, count=count)
        raw = await self._http_get(self._cfg.search.path, params)
        items = extract_items(raw, self._cfg.mapping.items_path)
        page_size = None if self._cfg.search.pagination.style == "none" else min(
            count if count is not None else self._cfg.search.pagination.max_size,
            self._cfg.search.pagination.max_size,
        )
        return SearchPage(
            items=self._map_and_filter(items),
            upstream_count=len(items),
            page_size=page_size,
        )

    async def get_asset(self, asset_id: str) -> dict:
        # 1. Cheapest and most reliable: the asset was returned by a recent
        #    search() on this bridge. We index the *raw* upstream item by its
        #    mapped assetID (see _map_and_filter) and re-run the current mapping
        #    here, so YAML mapping edits still take effect immediately.
        seen = self._recently_seen(asset_id)
        if seen is not None:
            return seen

        detail = self._cfg.asset_detail
        if not detail.enabled or not detail.path:
            # 2. No detail endpoint configured: scan the default search result.
            #    Works for small collections; sources with many assets should
            #    configure asset_detail with a proper upstream lookup.
            assets = await self.search(query=None, offset=0, count=None)
            for a in assets:
                if a.get("assetID") == asset_id:
                    return a
            raise AssetNotFound(
                f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
            )

        # 3. Configured detail lookup.
        return await self.lookup(asset_id)

    async def lookup(self, asset_id: str) -> dict:
        """The asset_detail lookup alone, without the recently-seen shortcut:
        what get_asset() falls back to, and what the admin's lookup test runs.

        Placeholders available in path and query:

        * `{asset_id}`: the Impulse asset id verbatim.
        * `{asset_id_regex}`: a case-insensitive regex matching every upstream
          id that slugifies to this asset id, for ids produced with
          `transform: slugify`, which cannot be reversed (Europeana
          "/90402/SK_A_3262" -> "90402-sk-a-3262"). Meant for Solr-style
          `field:/regex/` queries on a search endpoint.
        * `{asset_id_from_base32}`: the original upstream id, for assetIDs
          produced with `transform: base32`, for exact-match detail endpoints
          without regex search.
        """
        detail = self._cfg.asset_detail
        if not detail.enabled or not detail.path:
            raise AssetNotFound("This source has no single-asset lookup (asset_detail) configured")
        substitutions = {
            "{asset_id}": asset_id,
            "{asset_id_regex}": slug_to_regex(asset_id),
        }
        needs_decode = "{asset_id_from_base32}" in detail.path or any(
            "{asset_id_from_base32}" in v for v in detail.query.values()
        )
        if needs_decode:
            decoded = base32_id_decode(asset_id)
            if decoded is None:
                # Not one of our base32 ids -> cannot exist upstream.
                raise AssetNotFound(
                    f"Asset '{asset_id}' not found in collection "
                    f"'{self.collection_meta['id']}'"
                )
            substitutions["{asset_id_from_base32}"] = decoded
        path = _substitute(detail.path, substitutions)
        # detail.query is the COMPLETE query for the detail endpoint (not merged
        # with search's default_query, since the two endpoints typically take
        # different params — e.g. MediaWiki's generator=search vs. pageids=X).
        params: dict[str, str] = {}
        auth = self._cfg.adapter.auth
        if auth.type == "query_param" and auth.name and auth.value:
            params[auth.name] = auth.value
        for k, v in detail.query.items():
            params[k] = _substitute(v, substitutions)
        try:
            raw = await self._http_get(path, params)
        except UpstreamNotFound as e:
            # An exact-match detail endpoint saying 404 means "no such asset",
            # not "upstream broken": report it as Impulse code 2, not 12.
            raise AssetNotFound(
                f"Asset '{asset_id}' not found in collection '{self.collection_meta['id']}'"
            ) from e
        mapping = detail.mapping or self._cfg.mapping
        if not mapping.fields:
            # Detail mapping only overrides the envelope (items_path); the item
            # shape is the same as in search, so reuse the search fields.
            mapping = mapping.model_copy(update={"fields": self._cfg.mapping.fields})
        items = extract_items(raw, mapping.items_path) if mapping.items_path else [raw]

        # Prefer the item whose mapped assetID equals the requested one. This
        # matters when the detail lookup goes through a search endpoint, which
        # may legitimately return more than one candidate. Only when the detail
        # mapping produces no assetID at all do we trust the first item blindly.
        unverified: dict | None = None
        for item in items:
            asset = transform_item(item, mapping, self._cfg.filter)
            if asset is None:
                continue
            mapped_id = asset.get("assetID")
            if mapped_id == asset_id:
                return asset
            if mapped_id is None and unverified is None:
                unverified = asset
        if unverified is not None:
            return unverified
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
        query_cfg = self._cfg.search.query
        if not q:
            q = query_cfg.pattern_when_empty
        else:
            wc = query_cfg.wildcard_translation
            if wc.from_ and wc.from_ != wc.to:
                q = q.replace(wc.from_, wc.to)
            if query_cfg.pattern_template:
                q = query_cfg.pattern_template.replace("{pattern}", q)
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
            params[p.offset_param] = str(offset + p.offset_base)
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
        # The public site carries the imprint with the contact details.
        h: dict[str, str] = {
            "User-Agent": f"IMPULSE-Curator/0.1 (+{settings.public_base_url})",
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
            # Keep the inspection state accurate for the admin UI's test run.
            self.last_upstream_url = str(self._client.build_request("GET", path, params=params).url)
            self.last_raw_response = cached
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
        if response.status_code == 404:
            raise UpstreamNotFound(f"Upstream 404: {response.text[:200]}")
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
                asset_id = asset.get("assetID")
                if isinstance(asset_id, str) and asset_id:
                    # Remember the raw item so get_asset() can serve any asset a
                    # client just discovered without a second upstream round-trip
                    # (and, for sources without a detail endpoint, at all).
                    cache.set(self._seen_key(asset_id), raw)
        return out

    def _seen_key(self, asset_id: str) -> str:
        return cache.key(self.collection_meta["id"], "__asset__", {"id": asset_id})

    def _recently_seen(self, asset_id: str) -> dict | None:
        """Re-map a raw item cached by a recent search(), if there is one and it
        still maps to the requested assetID under the current mapping."""
        raw = cache.get(self._seen_key(asset_id))
        if not isinstance(raw, dict):
            return None
        asset = transform_item(raw, self._cfg.mapping, self._cfg.filter)
        if asset is None or asset.get("assetID") != asset_id:
            return None
        logger.debug(
            "asset served from recent search results: source=%s id=%s",
            self.collection_meta["id"],
            asset_id,
        )
        return asset
