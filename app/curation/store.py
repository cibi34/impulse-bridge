"""Data access for curated collections (synchronous; see db.py)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.curation.db import Database


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class CollectionRecord:
    id: str
    name: str
    description: str
    organization: str
    owner_email: str | None
    edit_key_hash: str
    listed: bool
    disabled: bool
    submitted_at: str | None
    created_at: str
    updated_at: str
    item_count: int = 0


@dataclass(frozen=True)
class ItemRecord:
    asset_id: str
    source_id: str
    source_asset_id: str
    position: int
    published: bool
    asset: dict[str, Any]
    """Snapshot of the Impulse asset taken from the source (absolute URIs)."""
    added_at: str
    refreshed_at: str


@dataclass(frozen=True)
class NewItem:
    asset_id: str
    source_id: str
    source_asset_id: str
    asset: dict[str, Any]


_COLLECTION_COLUMNS = (
    "c.id, c.name, c.description, c.organization, c.owner_email, c.edit_key_hash, "
    "c.listed, c.disabled, c.submitted_at, c.created_at, c.updated_at, "
    "(SELECT COUNT(*) FROM collection_items i WHERE i.collection_id = c.id) AS item_count"
)


def _collection(row: sqlite3.Row) -> CollectionRecord:
    return CollectionRecord(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        organization=row["organization"],
        owner_email=row["owner_email"],
        edit_key_hash=row["edit_key_hash"],
        listed=bool(row["listed"]),
        disabled=bool(row["disabled"]),
        submitted_at=row["submitted_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        item_count=row["item_count"],
    )


def _item(row: sqlite3.Row) -> ItemRecord:
    return ItemRecord(
        asset_id=row["asset_id"],
        source_id=row["source_id"],
        source_asset_id=row["source_asset_id"],
        position=row["position"],
        published=bool(row["published"]),
        asset=json.loads(row["asset"]),
        added_at=row["added_at"],
        refreshed_at=row["refreshed_at"],
    )


class CollectionStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---- collections ----

    def create(
        self,
        *,
        collection_id: str,
        name: str,
        description: str,
        organization: str,
        owner_email: str | None,
        edit_key_hash: str,
        items: list[NewItem],
    ) -> CollectionRecord:
        now = utcnow()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO collections (id, name, description, organization, owner_email, "
                "edit_key_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (collection_id, name, description, organization, owner_email, edit_key_hash, now, now),
            )
            self._insert_items(conn, collection_id, items, now)
        record = self.get(collection_id)
        assert record is not None
        return record

    def exists(self, collection_id: str) -> bool:
        with self.db.read() as conn:
            return conn.execute(
                "SELECT 1 FROM collections WHERE id = ?", (collection_id,)
            ).fetchone() is not None

    def get(self, collection_id: str) -> CollectionRecord | None:
        with self.db.read() as conn:
            row = conn.execute(
                f"SELECT {_COLLECTION_COLUMNS} FROM collections c WHERE c.id = ?",
                (collection_id,),
            ).fetchone()
        return _collection(row) if row else None

    def get_many(self, collection_ids: list[str]) -> list[CollectionRecord]:
        """Collections with these ids, in the given order; unknown ids are skipped."""
        if not collection_ids:
            return []
        marks = ",".join("?" * len(collection_ids))
        with self.db.read() as conn:
            rows = conn.execute(
                f"SELECT {_COLLECTION_COLUMNS} FROM collections c WHERE c.id IN ({marks})",
                collection_ids,
            ).fetchall()
        by_id = {row["id"]: _collection(row) for row in rows}
        return [by_id[cid] for cid in collection_ids if cid in by_id]

    def count(self) -> int:
        with self.db.read() as conn:
            return conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]

    def list_all(self) -> list[CollectionRecord]:
        with self.db.read() as conn:
            rows = conn.execute(
                f"SELECT {_COLLECTION_COLUMNS} FROM collections c ORDER BY c.updated_at DESC"
            ).fetchall()
        return [_collection(row) for row in rows]

    def list_listed(self) -> list[CollectionRecord]:
        """Collections an admin approved for the public /collections listing."""
        with self.db.read() as conn:
            rows = conn.execute(
                f"SELECT {_COLLECTION_COLUMNS} FROM collections c "
                "WHERE c.listed = 1 AND c.disabled = 0 ORDER BY c.name COLLATE NOCASE"
            ).fetchall()
        return [_collection(row) for row in rows]

    def update(self, collection_id: str, **fields: Any) -> None:
        """Update collection columns (name, description, organization,
        owner_email, edit_key_hash, listed, disabled, submitted_at)."""
        allowed = {
            "name", "description", "organization", "owner_email",
            "edit_key_hash", "listed", "disabled", "submitted_at",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown collection fields: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE collections SET {assignments}, updated_at = ? WHERE id = ?",
                (*fields.values(), utcnow(), collection_id),
            )

    def delete(self, collection_id: str) -> bool:
        with self.db.transaction() as conn:
            return conn.execute(
                "DELETE FROM collections WHERE id = ?", (collection_id,)
            ).rowcount > 0

    # ---- items ----

    def items(self, collection_id: str, *, published_only: bool = False) -> list[ItemRecord]:
        sql = "SELECT * FROM collection_items WHERE collection_id = ?"
        if published_only:
            sql += " AND published = 1"
        with self.db.read() as conn:
            rows = conn.execute(sql + " ORDER BY position", (collection_id,)).fetchall()
        return [_item(row) for row in rows]

    def item(self, collection_id: str, asset_id: str) -> ItemRecord | None:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT * FROM collection_items WHERE collection_id = ? AND asset_id = ?",
                (collection_id, asset_id),
            ).fetchone()
        return _item(row) if row else None

    def preview_items(self, collection_ids: list[str], per_collection: int) -> dict[str, list[ItemRecord]]:
        """The first published items of several collections (for overviews)."""
        out: dict[str, list[ItemRecord]] = {cid: [] for cid in collection_ids}
        if not collection_ids:
            return out
        marks = ",".join("?" * len(collection_ids))
        with self.db.read() as conn:
            rows = conn.execute(
                f"SELECT * FROM collection_items WHERE collection_id IN ({marks}) "
                "AND published = 1 ORDER BY collection_id, position",
                collection_ids,
            ).fetchall()
        for row in rows:
            bucket = out[row["collection_id"]]
            if len(bucket) < per_collection:
                bucket.append(_item(row))
        return out

    def add_items(self, collection_id: str, items: list[NewItem]) -> list[ItemRecord]:
        """Append items; ones whose source asset is already in the collection
        are skipped. Returns the added items."""
        now = utcnow()
        with self.db.transaction() as conn:
            added = self._insert_items(conn, collection_id, items, now)
            if added:
                self._touch(conn, collection_id, now)
        return [self.item(collection_id, asset_id) for asset_id in added]  # type: ignore[misc]

    def _insert_items(
        self, conn: sqlite3.Connection, collection_id: str, items: list[NewItem], now: str
    ) -> list[str]:
        position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM collection_items WHERE collection_id = ?",
            (collection_id,),
        ).fetchone()[0]
        added: list[str] = []
        for item in items:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO collection_items (collection_id, asset_id, source_id, "
                "source_asset_id, position, asset, added_at, refreshed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    collection_id, item.asset_id, item.source_id, item.source_asset_id,
                    position, json.dumps(item.asset, ensure_ascii=False), now, now,
                ),
            )
            if cursor.rowcount:
                added.append(item.asset_id)
                position += 1
        return added

    def source_refs(self, collection_id: str) -> set[tuple[str, str]]:
        """(source_id, source_asset_id) of every item in the collection."""
        with self.db.read() as conn:
            rows = conn.execute(
                "SELECT source_id, source_asset_id FROM collection_items WHERE collection_id = ?",
                (collection_id,),
            ).fetchall()
        return {(row[0], row[1]) for row in rows}

    def asset_ids(self, collection_id: str) -> set[str]:
        with self.db.read() as conn:
            rows = conn.execute(
                "SELECT asset_id FROM collection_items WHERE collection_id = ?", (collection_id,)
            ).fetchall()
        return {row[0] for row in rows}

    def remove_item(self, collection_id: str, asset_id: str) -> bool:
        with self.db.transaction() as conn:
            removed = conn.execute(
                "DELETE FROM collection_items WHERE collection_id = ? AND asset_id = ?",
                (collection_id, asset_id),
            ).rowcount > 0
            if removed:
                self._touch(conn, collection_id, utcnow())
        return removed

    def set_published(self, collection_id: str, asset_id: str, published: bool) -> bool:
        with self.db.transaction() as conn:
            changed = conn.execute(
                "UPDATE collection_items SET published = ? WHERE collection_id = ? AND asset_id = ?",
                (int(published), collection_id, asset_id),
            ).rowcount > 0
            if changed:
                self._touch(conn, collection_id, utcnow())
        return changed

    def reorder(self, collection_id: str, asset_ids: list[str]) -> None:
        """Set the order; `asset_ids` must be exactly the collection's items."""
        with self.db.transaction() as conn:
            for position, asset_id in enumerate(asset_ids):
                conn.execute(
                    "UPDATE collection_items SET position = ? WHERE collection_id = ? AND asset_id = ?",
                    (position, collection_id, asset_id),
                )
            self._touch(conn, collection_id, utcnow())

    def update_snapshot(self, collection_id: str, asset_id: str, asset: dict[str, Any]) -> None:
        now = utcnow()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE collection_items SET asset = ?, refreshed_at = ? "
                "WHERE collection_id = ? AND asset_id = ?",
                (json.dumps(asset, ensure_ascii=False), now, collection_id, asset_id),
            )
            self._touch(conn, collection_id, now)

    @staticmethod
    def _touch(conn: sqlite3.Connection, collection_id: str, now: str) -> None:
        conn.execute("UPDATE collections SET updated_at = ? WHERE id = ?", (now, collection_id))
