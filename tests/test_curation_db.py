"""The SQLite schema is migrated once and data survives a restart."""

from app.curation.db import MIGRATIONS, Database
from app.curation.store import CollectionStore, NewItem


def test_reopening_keeps_data_and_does_not_migrate_twice(tmp_path):
    path = tmp_path / "nested" / "curator.db"
    store = CollectionStore(Database(path))
    store.create(
        collection_id="c-1", name="One", description="", organization="", owner_email=None,
        edit_key_hash="h", items=[NewItem("a-1", "src", "a", {"title": "A"})],
    )
    store.db.close()

    reopened = CollectionStore(Database(path))

    with reopened.db.read() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    assert reopened.get("c-1").item_count == 1
    assert reopened.items("c-1")[0].asset == {"title": "A"}
    reopened.db.close()


def test_deleting_a_collection_deletes_its_items(tmp_path):
    store = CollectionStore(Database(tmp_path / "curator.db"))
    store.create(
        collection_id="c-1", name="One", description="", organization="", owner_email=None,
        edit_key_hash="h", items=[NewItem("a-1", "src", "a", {})],
    )

    assert store.delete("c-1") is True

    with store.db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM collection_items").fetchone()[0] == 0
    store.db.close()
