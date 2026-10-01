"""Per-client rate limits for the anonymous write endpoints.

Without accounts, creating collections is open to anyone; a sliding window per
client IP keeps scripted abuse in check. In-memory and per process, which fits
the single-container deployment. Behind Traefik, uvicorn's --proxy-headers
makes `request.client.host` the real client address.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimit:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = int(hits[0] + self.window - now) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


create_limit = RateLimit(limit=30, window_seconds=3600)
"""New collections per client and hour."""

write_limit = RateLimit(limit=1200, window_seconds=3600)
"""Edits per client and hour (adding, reordering, toggling…)."""
