"""The app's SQLite-backed stores, opened by the lifespan in app/main.py and
handed to endpoints as FastAPI dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.auth import AuthStore
from app.curation.db import Database
from app.curation.store import CollectionStore
from app.site_settings import SiteSettingsStore


@dataclass(frozen=True)
class Storage:
    db: Database
    collections: CollectionStore
    site: SiteSettingsStore
    auth: AuthStore


_storage: Storage | None = None


def open_storage(path: Path) -> Storage:
    global _storage
    db = Database(path)
    _storage = Storage(db, CollectionStore(db), SiteSettingsStore(db), AuthStore(db))
    return _storage


def close_storage() -> None:
    global _storage
    if _storage is not None:
        _storage.db.close()
        _storage = None


def _current() -> Storage:
    if _storage is None:
        raise RuntimeError("Storage is not open")
    return _storage


def get_store() -> CollectionStore:
    return _current().collections


def get_site_store() -> SiteSettingsStore:
    return _current().site


def get_auth_store() -> AuthStore:
    return _current().auth
