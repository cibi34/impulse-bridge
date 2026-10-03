"""Shared fixtures: an isolated config directory with small fallback sources, so
tests never touch configs/sources/ or the network."""

import json
from pathlib import Path

import pytest

from app.registry import registry
from app.settings import settings


def write_fallback(
    config_dir: Path,
    collection_id: str,
    *,
    name: str | None = None,
    files: dict[str, str] | None = None,
    filename: str | None = None,
    static_mount: bool = True,
) -> Path:
    """Write a fallback source (YAML + manifest + optional media files) and
    return the YAML path. The manifest lives in its own directory per id."""
    data_dir = config_dir.parent / "data" / collection_id
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = data_dir / "manifest.json"
    manifest.write_text(
        json.dumps([{"assetID": "demo", "title": "Demo", "assetURI": "demo.glb", "rights": "CC0"}]),
        encoding="utf-8",
    )
    for rel, content in (files or {}).items():
        (data_dir / rel).write_text(content, encoding="utf-8")
    yaml_path = config_dir / (filename or f"{collection_id}.yaml")
    yaml_path.write_text(
        f"""collection:
  id: {collection_id}
  name: "{name or collection_id}"
  organization: Test
  owner_id: t@example.org
adapter:
  kind: fallback
  manifest_path: "{manifest.as_posix()}"
  static_mount: {"true" if static_mount else "false"}
""",
        encoding="utf-8",
    )
    return yaml_path


BROKEN_YAML = "collection:\n  id: broken\nadapter:\n  kind: rest\n"
"""Schema-invalid: collection.name / organization / owner_id are missing."""


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test gets its own database and fresh rate limits."""
    from app.ratelimit import create_limit, write_limit

    monkeypatch.setattr(settings, "database_path", tmp_path / "curator.db")
    monkeypatch.setattr(settings, "public_base_url", "http://bridge.test")
    create_limit.reset()
    write_limit.reset()


@pytest.fixture
def config_dir(tmp_path, monkeypatch) -> Path:
    d = tmp_path / "sources"
    d.mkdir()
    monkeypatch.setattr(settings, "config_dir", d)
    return d


@pytest.fixture
async def clean_registry():
    yield registry
    await registry.clear()
