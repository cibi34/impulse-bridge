"""Tiny in-process TTL cache for raw upstream responses.

We cache raw JSON (not the transformed Impulse asset list) so mapping changes
take effect immediately without manual cache invalidation, and so the same cache
entry can serve search and detail lookups that share underlying state.

The cache is intentionally simple — single TTLCache, no LRU sizing pressure, no
persistence. POC scale is well within these limits."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cachetools import TTLCache

from app.settings import settings


class BridgeCache:
    def __init__(self, maxsize: int = 1024, default_ttl: int | None = None) -> None:
        self._ttl = default_ttl or settings.default_cache_ttl
        self._store: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=self._ttl)

    def key(self, source_id: str, path: str, params: dict[str, str]) -> str:
        canonical = json.dumps(
            {"src": source_id, "path": path, "params": dict(sorted(params.items()))},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha1(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        # cachetools.TTLCache uses a single global TTL per instance; per-key TTL
        # would require a different structure. We currently honor the per-source
        # `cache.ttl_seconds` by sizing the global TTL to the configured max,
        # and let shorter TTLs simply behave as the global one. For POC this is
        # an acceptable simplification.
        self._store[key] = value


cache = BridgeCache()
