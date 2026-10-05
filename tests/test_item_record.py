"""item_record: a search (or lookup) that only returns stubs, each completed
from the item's own record before the filter runs."""

import httpx
import pytest
import respx

from app.adapter.rest import GenericRestSource
from app.cache import cache
from app.config.schema import SourceConfig
from app.errors import AssetNotFound

BASE = "https://api.example.org"


def _source() -> GenericRestSource:
    cache._store.clear()
    return GenericRestSource(SourceConfig.model_validate({
        "collection": {"id": "two-step", "name": "T", "organization": "T", "owner_id": "t"},
        "adapter": {"kind": "rest", "base_url": BASE, "auth": {"type": "query_param", "name": "key", "value": "k"}},
        "search": {
            "path": "/search",
            "pagination": {"style": "offset_limit", "offset_param": "start", "limit_param": "rows"},
            "query": {"pattern_param": "q", "pattern_when_empty": "*"},
        },
        "mapping": {
            "items_path": "items",
            "fields": {
                "assetID": {"expr": "id", "transform": "slugify"},
                "title": {"expr": "title"},
                "previewURI": {"expr": "preview"},
                "rights": {"literal": "CC0"},
                "contentType": {"literal": "model/gltf-binary"},
            },
        },
        "item_record": {
            "enabled": True,
            "path": "/records{item_id}.json",
            "query": {"profile": "full"},
            "item_id_path": "id",
            "mapping": {
                "items_path": "object",
                "fields": {"assetURI": {"expr": "file"}, "fileSize": {"expr": "bytes"}, "title": {"expr": "better_title"}},
            },
        },
        "asset_detail": {"enabled": True, "path": "/search", "query": {"q": "id:/{asset_id_regex}/"}},
        "filter": {"drop_if_missing": ["assetURI"], "allowed_content_types": ["model/gltf-binary"]},
    }))


def _stub(rid: str) -> dict:
    return {"id": rid, "title": f"Stub {rid}", "preview": f"https://img.example.org{rid}.jpg"}


def _record(rid: str, **fields) -> dict:
    return {"object": {"file": f"https://files.example.org{rid}.glb", "bytes": 1234, **fields}}


@respx.mock
async def test_search_stubs_are_completed_from_their_records():
    search = respx.get(f"{BASE}/search").mock(
        return_value=httpx.Response(200, json={"items": [_stub("/1/a"), _stub("/1/b"), _stub("/1/c")]})
    )
    a = respx.get(f"{BASE}/records/1/a.json").mock(return_value=httpx.Response(200, json=_record("/1/a", better_title="Record A")))
    respx.get(f"{BASE}/records/1/b.json").mock(return_value=httpx.Response(200, json={"object": {"bytes": 1}}))  # no file
    respx.get(f"{BASE}/records/1/c.json").mock(return_value=httpx.Response(404))
    source = _source()

    page = await source.search_page(query="pots", offset=0, count=3)
    await source.aclose()

    assert search.calls.last.request.url.params["q"] == "pots"
    assert a.calls.last.request.url.params["profile"] == "full"
    assert a.calls.last.request.url.params["key"] == "k"
    assert [x["title"] for x in page.items] == ["Record A"]  # the record's field wins; b, c are out
    item = page.items[0]
    assert (item["assetID"], item["assetURI"], item["fileSize"], item["previewURI"]) == (
        "1-a", "https://files.example.org/1/a.glb", 1234, "https://img.example.org/1/a.jpg",
    )
    assert (page.upstream_count, page.has_more) == (3, True)


@respx.mock
async def test_single_asset_lookups_are_completed_too():
    respx.get(f"{BASE}/search").mock(return_value=httpx.Response(200, json={"items": [_stub("/1/a")]}))
    respx.get(f"{BASE}/records/1/a.json").mock(return_value=httpx.Response(200, json=_record("/1/a")))
    source = _source()

    fresh = await source.get_asset("1-a")           # through asset_detail, then the record
    await source.search(query=None, offset=0, count=1)
    recent = await source.get_asset("1-a")          # through the recently-seen stub, then the record
    with pytest.raises(AssetNotFound):
        await source.get_asset("1-z")
    await source.aclose()

    assert fresh["assetURI"] == recent["assetURI"] == "https://files.example.org/1/a.glb"
    assert fresh["title"] == "Stub /1/a"  # the record has no better title here
