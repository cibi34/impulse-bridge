"""Curated collections: user-made selections of assets from the sources,
served to Impulse/Unity through the Collections-and-Assets API."""

from __future__ import annotations

from app.curation.db import Database
from app.curation.store import CollectionStore

_store: CollectionStore | None = None


def open_store(path) -> CollectionStore:
    global _store
    _store = CollectionStore(Database(path))
    return _store


def close_store() -> None:
    global _store
    if _store is not None:
        _store.db.close()
        _store = None


def get_store() -> CollectionStore:
    """FastAPI dependency; the store is opened by the app lifespan."""
    if _store is None:
        raise RuntimeError("Collection store is not open")
    return _store
