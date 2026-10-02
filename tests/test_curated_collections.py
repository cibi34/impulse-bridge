"""Curated collections end to end: created in the web app API, served to
Unity through the Impulse API, edited with the edit key, managed by admins."""

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import create_limit
from app.settings import settings
from conftest import write_fallback

ASSETS = [
    {"assetID": "cube", "title": "Demo Cube", "contentType": "model/gltf-binary",
     "assetURI": "cube.glb", "previewURI": "cube.png", "rights": "CC0"},
    {"assetID": "hare", "title": "Young Hare", "contentType": "image/jpeg",
     "assetURI": "https://example.org/hare.jpg", "previewURI": "https://example.org/hare-s.jpg",
     "creator": "Albrecht Dürer"},
    {"assetID": "wave", "title": "The Great Wave", "contentType": "image/jpeg",
     "assetURI": "https://example.org/wave.jpg", "previewURI": "https://example.org/wave-s.jpg"},
]


def _manifest(config_dir):
    return config_dir.parent / "data" / "demo" / "manifest.json"


@pytest.fixture
def client(config_dir):
    write_fallback(config_dir, "demo")
    _manifest(config_dir).write_text(json.dumps(ASSETS), encoding="utf-8")
    with TestClient(app) as c:
        yield c


def _create(client, *asset_ids, **fields):
    body = {"name": "Masters of light", "items": [{"source": "demo", "asset_id": a} for a in asset_ids]}
    body.update(fields)
    r = client.post("/api/collections", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    return data["collection"], {"Authorization": f"Bearer {data['edit_key']}"}, data


def _impulse_assets(client, cid, query=""):
    body = client.get(f"/collections/{cid}/assets{query}").json()
    assert body["code"] == 0
    return body["data"]


# ---- creating and serving ----

def test_create_snapshots_assets_and_serves_them_to_impulse(client):
    collection, _, data = _create(client, "cube", "hare", description="Gallery scene")

    assert re.fullmatch(r"masters-of-light-[a-z2-9]{6}", collection["id"])
    assert collection["uri"] == f"http://bridge.test/collections/{collection['id']}"
    assert data["failed"] == []
    meta = client.get(f"/collections/{collection['id']}").json()["data"]
    assert meta == {
        "id": collection["id"],
        "uri": collection["uri"],
        "name": "Masters of light",
        "description": "Gallery scene",
        "organization": settings.default_organization,
        "owner_id": settings.collection_owner_id,
        "published": 1,
    }
    assets = _impulse_assets(client, collection["id"])
    assert [a["title"] for a in assets] == ["Demo Cube", "Young Hare"]
    cube = assets[0]
    assert re.fullmatch(r"demo-cube-[0-9a-f]{6}", cube["assetID"])
    assert cube["assetURI"] == "http://bridge.test/sources/demo/files/cube.glb"
    assert cube["published"] == 1
    detail = client.get(f"/collections/{collection['id']}/asset/{cube['assetID']}").json()
    assert detail["data"]["title"] == "Demo Cube"


def test_impulse_search_and_paging_within_a_collection(client):
    collection, _, _ = _create(client, "cube", "hare", "wave")
    cid = collection["id"]
    assert [a["title"] for a in _impulse_assets(client, cid, "?s=hare")] == ["Young Hare"]
    assert [a["title"] for a in _impulse_assets(client, cid, "?s=d*rer")] == ["Young Hare"]
    assert [a["title"] for a in _impulse_assets(client, cid, "?o=1&c=1")] == ["Young Hare"]
    assert len(_impulse_assets(client, cid, "?c=abc")) == 3


def test_new_collections_are_not_listed_until_an_admin_lists_them(client):
    collection, _, _ = _create(client, "cube")
    assert client.get("/collections").json()["data"] == []

    client.patch(f"/admin/api/collections/{collection['id']}", json={"listed": True})

    assert [c["id"] for c in client.get("/collections").json()["data"]] == [collection["id"]]


def test_unknown_collection_and_asset_use_impulse_codes(client):
    collection, _, _ = _create(client, "cube")
    missing = client.get("/collections/nope/assets")
    missing_asset = client.get(f"/collections/{collection['id']}/asset/nope")
    assert (missing.status_code, missing.json()["code"]) == (404, 1)
    assert (missing_asset.status_code, missing_asset.json()["code"]) == (404, 2)


def test_failed_items_are_reported_and_the_rest_is_kept(client):
    body = {
        "name": "Mixed",
        "items": [
            {"source": "demo", "asset_id": "cube"},
            {"source": "demo", "asset_id": "missing"},
            {"source": "nowhere", "asset_id": "x"},
            {"source": "demo", "asset_id": "cube"},
        ],
    }
    data = client.post("/api/collections", json=body).json()
    assert data["collection"]["item_count"] == 1
    assert data["failed"] == [
        {"source": "demo", "asset_id": "missing", "reason": "Asset not found"},
        {"source": "nowhere", "asset_id": "x", "reason": "Unknown source"},
    ]


@pytest.mark.parametrize(
    "body",
    [{"name": "   "}, {"name": "x" * 121}, {"name": "Ok", "email": "not-an-email"}],
)
def test_invalid_input_is_rejected(client, body):
    assert client.post("/api/collections", json=body).status_code == 422


# ---- editing ----

def test_editing_requires_the_edit_key(client):
    collection, key, _ = _create(client, "cube")
    url = f"/api/collections/{collection['id']}"

    assert client.patch(url, json={"name": "New"}).status_code == 401
    assert client.patch(url, json={"name": "New"}, headers={"Authorization": "Bearer wrong"}).status_code == 403
    r = client.patch(url, json={"name": "New", "email": "me@example.org"}, headers=key)

    assert r.status_code == 200
    assert (r.json()["name"], r.json()["email"]) == ("New", "me@example.org")
    assert "email" not in client.get(url).json()  # never shown publicly


def test_hidden_assets_are_not_served_to_impulse(client):
    collection, key, _ = _create(client, "cube", "hare")
    cid = collection["id"]
    cube_id = collection["items"][0]["asset_id"]

    r = client.patch(f"/api/collections/{cid}/items/{cube_id}", json={"published": False}, headers=key)

    assert r.json()["published"] is False
    assert [a["title"] for a in _impulse_assets(client, cid)] == ["Young Hare"]
    assert client.get(f"/collections/{cid}/asset/{cube_id}").json()["code"] == 2
    assert len(client.get(f"/api/collections/{cid}").json()["items"]) == 1
    assert len(client.get(f"/api/collections/{cid}", headers=key).json()["items"]) == 2


def test_add_remove_and_reorder(client):
    collection, key, _ = _create(client, "cube")
    cid = collection["id"]

    added = client.post(
        f"/api/collections/{cid}/items",
        json={"items": [{"source": "demo", "asset_id": "hare"}, {"source": "demo", "asset_id": "cube"},
                        {"source": "demo", "asset_id": "wave"}]},
        headers=key,
    ).json()
    assert [i["asset"]["title"] for i in added["added"]] == ["Young Hare", "The Great Wave"]  # cube: already in

    ids = [i["asset_id"] for i in client.get(f"/api/collections/{cid}", headers=key).json()["items"]]
    bad = client.put(f"/api/collections/{cid}/order", json={"asset_ids": ids[:2]}, headers=key)
    assert bad.status_code == 422
    client.put(f"/api/collections/{cid}/order", json={"asset_ids": list(reversed(ids))}, headers=key)
    assert [a["title"] for a in _impulse_assets(client, cid)] == ["The Great Wave", "Young Hare", "Demo Cube"]

    assert client.delete(f"/api/collections/{cid}/items/{ids[0]}", headers=key).status_code == 204
    assert [a["title"] for a in _impulse_assets(client, cid)] == ["The Great Wave", "Young Hare"]


def test_collection_size_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "max_assets_per_collection", 2)
    collection, key, _ = _create(client, "cube", "hare")

    r = client.post(
        f"/api/collections/{collection['id']}/items",
        json={"items": [{"source": "demo", "asset_id": "wave"}]},
        headers=key,
    )
    assert r.status_code == 422
    assert "at most 2 assets" in r.json()["detail"]


def test_refresh_updates_snapshots_from_the_source(client, config_dir):
    collection, key, _ = _create(client, "hare")
    changed = [dict(a, title="Feldhase") if a["assetID"] == "hare" else a for a in ASSETS]
    _manifest(config_dir).write_text(json.dumps(changed), encoding="utf-8")
    client.post("/admin/api/reload")

    r = client.post(f"/api/collections/{collection['id']}/refresh", headers=key)

    assert r.json() == {"refreshed": 1, "failed": []}
    assert _impulse_assets(client, collection["id"])[0]["title"] == "Feldhase"


def test_reset_key_invalidates_the_old_link(client):
    collection, old_key, _ = _create(client, "cube")
    url = f"/api/collections/{collection['id']}"
    new_key = client.post(f"{url}/key", headers=old_key).json()["edit_key"]

    assert client.patch(url, json={"name": "x"}, headers=old_key).status_code == 403
    assert client.patch(url, json={"name": "x"}, headers={"Authorization": f"Bearer {new_key}"}).status_code == 200


def test_mark_submitted_and_delete(client):
    collection, key, _ = _create(client, "cube")
    url = f"/api/collections/{collection['id']}"

    submitted = client.post(f"{url}/submitted", headers=key).json()["submitted_at"]
    assert submitted.endswith("Z")
    assert client.delete(url, headers=key).status_code == 204
    assert client.get(f"/collections/{collection['id']}").json()["code"] == 1


def test_summaries_for_my_collections(client):
    first, _, _ = _create(client, "hare", "wave")
    second, _, _ = _create(client, "cube", name="Models")

    body = client.get(f"/api/collections?ids={second['id']},unknown,{first['id']}").json()

    assert [c["name"] for c in body["collections"]] == ["Models", "Masters of light"]
    assert body["collections"][1]["previews"] == [
        "https://example.org/hare-s.jpg", "https://example.org/wave-s.jpg",
    ]
    assert body["collections"][1]["item_count"] == 2


# ---- admin ----

def test_admin_lock_hides_and_freezes_a_collection(client):
    collection, key, _ = _create(client, "cube")
    cid = collection["id"]

    client.patch(f"/admin/api/collections/{cid}", json={"disabled": True})

    assert client.get(f"/collections/{cid}").json()["code"] == 1
    assert client.get(f"/api/collections/{cid}").status_code == 404
    assert client.get(f"/api/collections/{cid}", headers=key).json()["locked"] is True
    r = client.patch(f"/api/collections/{cid}", json={"name": "x"}, headers=key)
    assert (r.status_code, r.json()["detail"]) == (403, "This collection was locked by an administrator")


def test_admin_overview_and_new_key(client):
    collection, old_key, _ = _create(client, "cube", email="me@example.org")
    cid = collection["id"]

    listing = client.get("/admin/api/collections").json()["collections"]
    new_key = client.post(f"/admin/api/collections/{cid}/key").json()["edit_key"]

    assert [(c["id"], c["email"], c["item_count"]) for c in listing] == [(cid, "me@example.org", 1)]
    assert client.patch(f"/api/collections/{cid}", json={"name": "x"}, headers=old_key).status_code == 403
    assert client.patch(
        f"/api/collections/{cid}", json={"name": "x"}, headers={"Authorization": f"Bearer {new_key}"}
    ).status_code == 200


def test_creating_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(create_limit, "limit", 2)
    statuses = [client.post("/api/collections", json={"name": f"c{i}"}).status_code for i in range(3)]
    assert statuses == [201, 201, 429]


def test_health_answers_get_and_head(client):
    get = client.get("/health")
    head = client.head("/health")
    assert get.json()["data"]["status"] == "ok"
    assert (head.status_code, head.content) == (200, b"")


def test_redoc_is_switched_off(client):
    assert client.get("/redoc").status_code == 404
    assert client.get("/docs").status_code == 200
