"""Loading and hot-reloading sources: broken configs are isolated, reloads swap
the registry atomically, and replaced sources are closed after a grace period."""

import asyncio

import app.registry as registry_module
from app.loading import load_sources
from app.registry import Registry
from conftest import BROKEN_YAML, write_fallback


async def test_broken_config_only_disables_its_own_source(config_dir, clean_registry):
    write_fallback(config_dir, "alpha")
    write_fallback(config_dir, "beta")
    (config_dir / "broken.yaml").write_text(BROKEN_YAML, encoding="utf-8")

    await load_sources()

    assert sorted(c["id"] for c in clean_registry.list_meta()) == ["alpha", "beta"]
    [(filename, message)] = clean_registry.errors()
    assert filename == "broken.yaml"
    assert "collection.name" in message


async def test_reload_with_a_broken_file_keeps_serving_valid_sources(config_dir, clean_registry):
    write_fallback(config_dir, "alpha")
    await load_sources()
    (config_dir / "broken.yaml").write_text(BROKEN_YAML, encoding="utf-8")

    await load_sources()

    assert [c["id"] for c in clean_registry.list_meta()] == ["alpha"]


async def test_duplicate_id_is_reported_and_first_file_wins(config_dir, clean_registry):
    first = write_fallback(config_dir, "alpha", name="First", filename="a.yaml")
    write_fallback(config_dir, "alpha", name="Second", filename="b.yaml")

    await load_sources()

    assert clean_registry.get("alpha").collection_meta["name"] == "First"
    assert clean_registry.file_for("alpha") == first
    [(filename, message)] = clean_registry.errors()
    assert filename == "b.yaml"
    assert "Duplicate collection id 'alpha'" in message


async def test_unbuildable_source_is_reported(config_dir, clean_registry):
    yaml_path = write_fallback(config_dir, "alpha")
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8").replace("manifest.json", "missing.json"),
        encoding="utf-8",
    )

    await load_sources()

    assert clean_registry.list_meta() == []
    [(filename, message)] = clean_registry.errors()
    assert filename == "alpha.yaml"
    assert "manifest not found" in message


class _FakeSource:
    def __init__(self, cid: str) -> None:
        self.collection_meta = {"id": cid}
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


async def test_swap_closes_replaced_sources_after_grace_period(monkeypatch):
    monkeypatch.setattr(registry_module, "RETIRE_GRACE_SECONDS", 0.01)
    reg = Registry()
    old = _FakeSource("x")
    reg.swap({"x": old}, {}, [])
    reg.swap({"x": _FakeSource("x")}, {}, [])

    assert not old.closed  # still usable by requests that are already running
    await asyncio.sleep(0.05)
    assert old.closed
    await reg.clear()


async def test_clear_closes_retiring_and_current_sources_immediately():
    reg = Registry()
    old, current = _FakeSource("x"), _FakeSource("x")
    reg.swap({"x": old}, {}, [])
    reg.swap({"x": current}, {}, [])

    await reg.clear()

    assert old.closed and current.closed
    assert reg.list_meta() == []
