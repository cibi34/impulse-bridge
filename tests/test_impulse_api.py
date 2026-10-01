"""Impulse API conformance: offset/count handling per the spec and the
{code, message, data} envelope."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import write_fallback


@pytest.fixture
def client(config_dir):
    write_fallback(config_dir, "demo")
    manifest = config_dir.parent / "data" / "demo" / "manifest.json"
    manifest.write_text(
        json.dumps([{"assetID": f"a{i}", "title": f"Asset {i}"} for i in range(5)]),
        encoding="utf-8",
    )
    with TestClient(app) as c:
        yield c


def _ids(client, query: str) -> list[str]:
    body = client.get(f"/collections/demo/assets{query}").json()
    assert body["code"] == 0
    return [a["assetID"] for a in body["data"]]


def test_offset_and_count(client):
    assert _ids(client, "?o=1&c=2") == ["a1", "a2"]
    assert _ids(client, "?o=3") == ["a3", "a4"]
    assert _ids(client, "?c=1") == ["a0"]


@pytest.mark.parametrize("query", ["?o=-1", "?c=0", "?c=abc", "?o=1.5&c=2", "?o=x&c=x"])
def test_illegal_values_return_the_entire_result_set(client, query):
    assert _ids(client, query) == ["a0", "a1", "a2", "a3", "a4"]


def test_unknown_collection_uses_the_envelope(client):
    r = client.get("/collections/nope/assets")
    assert r.status_code == 404
    assert r.json() == {
        "code": 1,
        "message": "Collection 'nope' is not registered with this bridge",
        "data": [],
    }
