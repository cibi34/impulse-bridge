"""Web app API for searching sources: absolute URIs, paging, type filter."""

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.cache import cache
from app.main import app
from conftest import write_fallback

ASSETS = [
    {"assetID": "cube", "title": "Cube", "contentType": "model/gltf-binary", "assetURI": "cube.glb", "previewURI": "cube.png"},
    {"assetID": "sphere", "title": "Sphere", "contentType": "model/gltf-binary", "assetURI": "sphere.glb"},
    {"assetID": "painting", "title": "Painting", "contentType": "image/png", "assetURI": "https://example.org/p.png"},
]


@pytest.fixture
def client(config_dir):
    write_fallback(config_dir, "demo", name="Demo")
    (config_dir.parent / "data" / "demo" / "manifest.json").write_text(json.dumps(ASSETS), encoding="utf-8")
    with TestClient(app) as c:
        yield c


def test_lists_sources_without_impulse_internals(client):
    assert client.get("/api/sources").json() == {
        "sources": [{"id": "demo", "name": "Demo", "description": None, "organization": "Test"}]
    }


def test_search_makes_relative_uris_absolute(client):
    body = client.get("/api/sources/demo/assets?c=10").json()
    cube = body["items"][0]
    assert cube["assetURI"] == "http://bridge.test/sources/demo/files/cube.glb"
    assert cube["previewURI"] == "http://bridge.test/sources/demo/files/cube.png"
    assert body["items"][2]["assetURI"] == "https://example.org/p.png"


def test_next_offset(client):
    first = client.get("/api/sources/demo/assets?c=2").json()
    last = client.get(f"/api/sources/demo/assets?c=2&o={first['next_offset']}").json()
    assert [a["assetID"] for a in first["items"]] == ["cube", "sphere"]
    assert first["next_offset"] == 2
    assert [a["assetID"] for a in last["items"]] == ["painting"]
    assert last["next_offset"] is None


def test_type_filter(client):
    images = client.get("/api/sources/demo/assets?type=image").json()["items"]
    models = client.get("/api/sources/demo/assets?type=model").json()["items"]
    assert [a["assetID"] for a in images] == ["painting"]
    assert [a["assetID"] for a in models] == ["cube", "sphere"]


def test_asset_detail(client):
    r = client.get("/api/sources/demo/assets/cube")
    assert r.json()["assetURI"] == "http://bridge.test/sources/demo/files/cube.glb"


def test_errors_are_plain_json(client):
    unknown_source = client.get("/api/sources/nope/assets")
    unknown_asset = client.get("/api/sources/demo/assets/nope")
    assert unknown_source.status_code == 404
    assert unknown_source.json() == {"detail": "Source 'nope' is not configured", "code": 1}
    assert unknown_asset.status_code == 404
    assert unknown_asset.json()["code"] == 2


REST_YAML = """
collection: { id: rest, name: Rest, organization: Test, owner_id: t@example.org }
adapter: { kind: rest, base_url: "https://api.example.org" }
search:
  path: /search
  pagination: { style: offset_limit, offset_param: start, limit_param: rows, max_size: 3 }
mapping:
  items_path: items
  fields:
    assetID: { expr: id }
    assetURI: { expr: url }
filter: { drop_if_missing: [assetURI] }
"""


@respx.mock
def test_rest_paging_counts_upstream_items_not_filtered_ones(config_dir):
    cache._store.clear()
    (config_dir / "rest.yaml").write_text(REST_YAML, encoding="utf-8")
    respx.get("https://api.example.org/search").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "a", "url": "https://x/a"}, {"id": "no-media"}, {"id": "c", "url": "https://x/c"}]}
        )
    )
    with TestClient(app) as client:
        body = client.get("/api/sources/rest/assets?o=6&c=10").json()

    # 3 upstream items (page size capped at max_size=3), one dropped by the filter:
    # the next page still starts after all three.
    assert [a["assetID"] for a in body["items"]] == ["a", "c"]
    assert body["next_offset"] == 9
