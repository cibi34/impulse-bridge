"""Detail lookup variants: exact `{asset_id}` against a content endpoint
whose envelope differs from search (the item shape is the same), and
reversible `base32` assetIDs with the `{asset_id_from_base32}` placeholder."""

from urllib.parse import urlparse

import httpx
import pytest
import respx

from app.adapter.rest import GenericRestSource
from app.cache import cache
from app.config.schema import SourceConfig
from app.errors import AssetNotFound
from app.transform.helpers import base32_id

BASE = "https://api.example.org"

ROWS = {
    "rec-1643407190095-2": "Sweet flag",
    "inv_1981.0296.06": "Underscore & dots",
}


def _row(rid: str) -> dict:
    return {
        "id": rid,
        "title": ROWS[rid],
        "content": {
            "record": {
                "online_media": {
                    "media": [
                        {
                            "type": "Images",
                            "content": f"{BASE}/media/{rid}.jpg",
                            "thumbnail": f"{BASE}/thumb/{rid}.jpg",
                        }
                    ]
                }
            }
        },
    }


def _cfg(id_transform: str, detail_path: str) -> SourceConfig:
    return SourceConfig.model_validate(
        {
            "collection": {
                "id": "test-detail",
                "name": "Test",
                "organization": "Test",
                "owner_id": "t@example.org",
            },
            "adapter": {
                "kind": "rest",
                "base_url": BASE,
                "auth": {"type": "query_param", "name": "api_key", "value": "K"},
            },
            "search": {
                "path": "/search",
                "pagination": {
                    "style": "page_size",
                    "page_param": "start",
                    "size_param": "rows",
                    "max_size": 100,
                },
                "query": {"pattern_param": "q", "pattern_when_empty": "*"},
            },
            "mapping": {
                "items_path": "response.rows",
                "fields": {
                    "assetID": {"expr": "id", "transform": id_transform},
                    "title": {"expr": "title"},
                    "assetURI": {
                        "expr": "content.record.online_media.media[0].content"
                    },
                    "previewURI": {
                        "expr": "content.record.online_media.media[0].thumbnail"
                    },
                    "contentType": {"literal": "image/jpeg"},
                },
            },
            "asset_detail": {
                "enabled": True,
                "path": detail_path,
                "query": {},
                # envelope differs, item shape is the same -> only items_path
                "mapping": {"items_path": "response"},
            },
        }
    )


def _content_endpoint(request: httpx.Request) -> httpx.Response:
    rid = urlparse(str(request.url)).path.rsplit("/", 1)[-1]
    if rid in ROWS:
        return httpx.Response(200, json={"status": 200, "response": _row(rid)})
    return httpx.Response(
        404, json={"status": 404, "response": {"error": "not found"}}
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache._store.clear()
    yield
    cache._store.clear()


@pytest.fixture
def upstream():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        mock.get("/search").mock(
            return_value=httpx.Response(
                200, json={"response": {"rows": [_row(r) for r in ROWS]}}
            )
        )
        mock.route(path__regex=r"^/content/.*").mock(side_effect=_content_endpoint)
        yield mock


async def test_exact_lookup_reuses_search_fields_with_detail_items_path(upstream):
    src = GenericRestSource(_cfg("slugify", "/content/{asset_id}"))
    try:
        asset = await src.get_asset("rec-1643407190095-2")
    finally:
        await src.aclose()
    assert asset["assetID"] == "rec-1643407190095-2"
    assert asset["title"] == "Sweet flag"
    assert asset["assetURI"].endswith("rec-1643407190095-2.jpg")
    req = upstream.calls.last.request
    assert urlparse(str(req.url)).path == "/content/rec-1643407190095-2"
    assert "api_key=K" in str(req.url)  # auth still injected on detail calls


async def test_slugified_unsafe_id_cannot_be_looked_up_exactly(upstream):
    """Documents the limitation that motivates base32: slugify turns
    'inv_1981.0296.06' into an id the exact endpoint does not know."""
    src = GenericRestSource(_cfg("slugify", "/content/{asset_id}"))
    try:
        with pytest.raises(AssetNotFound):
            await src.get_asset("inv-1981-0296-06")
    finally:
        await src.aclose()


async def test_base32_ids_are_id_schema_safe_and_reversible(upstream):
    src = GenericRestSource(_cfg("base32", "/content/{asset_id_from_base32}"))
    try:
        found = await src.search(query=None, offset=0, count=None)
        ids = [a["assetID"] for a in found]
        assert ids == [base32_id(r) for r in ROWS]
        import re

        assert all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", i) for i in ids)

        cache._store.clear()  # defeat the seen-index: force the upstream lookup
        target = base32_id("inv_1981.0296.06")
        asset = await src.get_asset(target)
    finally:
        await src.aclose()
    assert asset["assetID"] == target
    assert asset["title"] == "Underscore & dots"
    assert urlparse(str(upstream.calls.last.request.url)).path == (
        "/content/inv_1981.0296.06"
    )


async def test_base32_lookup_with_non_base32_id_is_not_found_without_upstream_call(upstream):
    src = GenericRestSource(_cfg("base32", "/content/{asset_id_from_base32}"))
    try:
        with pytest.raises(AssetNotFound):
            await src.get_asset("does-not-exist-evaluation")
    finally:
        await src.aclose()
    assert len(upstream.calls) == 0


async def test_base32_lookup_unknown_upstream_id_is_not_found(upstream):
    src = GenericRestSource(_cfg("base32", "/content/{asset_id_from_base32}"))
    try:
        with pytest.raises(AssetNotFound):
            await src.get_asset(base32_id("inv_0000"))
    finally:
        await src.aclose()
