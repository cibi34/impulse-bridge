"""SQLite storage for curated collections.

One connection per process, serialized by a lock: SQLite handles a few hundred
small writes per second easily, which is far beyond what this app needs, and a
single connection avoids "database is locked" surprises. Callers in async code
run store methods in the threadpool (see app/curation/service.py).

The schema is versioned with `PRAGMA user_version`; add a new entry to
MIGRATIONS for every change and never edit an applied one.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

MIGRATIONS: list[str] = [
    # 1 — collections and their items
    """
    CREATE TABLE collections (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        description     TEXT NOT NULL DEFAULT '',
        organization    TEXT NOT NULL DEFAULT '',
        owner_email     TEXT,
        edit_key_hash   TEXT NOT NULL,
        listed          INTEGER NOT NULL DEFAULT 0,
        disabled        INTEGER NOT NULL DEFAULT 0,
        submitted_at    TEXT,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    );
    CREATE INDEX collections_owner_email ON collections (owner_email);

    CREATE TABLE collection_items (
        collection_id   TEXT NOT NULL REFERENCES collections (id) ON DELETE CASCADE,
        asset_id        TEXT NOT NULL,
        source_id       TEXT NOT NULL,
        source_asset_id TEXT NOT NULL,
        position        INTEGER NOT NULL,
        published       INTEGER NOT NULL DEFAULT 1,
        asset           TEXT NOT NULL,
        added_at        TEXT NOT NULL,
        refreshed_at    TEXT NOT NULL,
        PRIMARY KEY (collection_id, asset_id),
        UNIQUE (collection_id, source_id, source_asset_id)
    );
    CREATE INDEX collection_items_order ON collection_items (collection_id, position);
    """,
    # 2 — site settings (edited in the admin UI), passwordless login
    """
    CREATE TABLE site_settings (
        key             TEXT PRIMARY KEY,
        value           TEXT NOT NULL
    );

    CREATE TABLE login_tokens (
        token_hash      TEXT PRIMARY KEY,
        email           TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        expires_at      TEXT NOT NULL,
        used_at         TEXT
    );

    CREATE TABLE sessions (
        id_hash         TEXT PRIMARY KEY,
        email           TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        expires_at      TEXT NOT NULL
    );
    """,
    # 3 — former ids of renamed collections: they keep leading to the collection
    """
    CREATE TABLE collection_aliases (
        alias           TEXT PRIMARY KEY,
        collection_id   TEXT NOT NULL
                        REFERENCES collections (id) ON DELETE CASCADE ON UPDATE CASCADE,
        created_at      TEXT NOT NULL
    );
    CREATE INDEX collection_aliases_collection ON collection_aliases (collection_id);
    """,
]


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: no implicit transactions; transaction() is explicit.
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
        self._migrate()

    def _migrate(self) -> None:
        with self.transaction() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
                logger.info("Applying database migration %d", number)
                for statement in filter(str.strip, script.split(";")):
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {number}")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run the block atomically; rolls back on any exception."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._conn

    def close(self) -> None:
        with self._lock:
            self._conn.close()
