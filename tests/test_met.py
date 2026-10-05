"""The Met adapter: a page of ids becomes a page of objects, fetched in
parallel; highlights without a search term; CC0 stated for public domain."""

import httpx
import pytest
import respx

from app.adapter.custom.met import MetSource
from app.cache import cache
from app.config.schema import SourceConfig
from app.errors import AssetNotFound

BASE = "https://collectionapi.metmuseum.org"


def _source(**adapter) -> MetSource:
    cache._store.clear()
    return MetSource(SourceConfig.model_validate({
        "collection": {"id": "met", "name": "The Met", "organization": "Met", "owner_id": "t"},
        "adapter": {"kind": "custom", "custom_class": "x.Y", "base_url": BASE, **adapter},
    }))


def _object(object_id: int, **extra) -> dict:
    return {
        "objectID": object_id,
        "isPublicDomain": True,
        "primaryImage": f"https://images.metmuseum.org/CRDImages/ep/original/DP{object_id}.jpg",
        "primaryImageSmall": f"https://images.metmuseum.org/CRDImages/ep/web-large/DP{object_id}.jpg",
        "title": f"Object {object_id}",
        "artistDisplayName": "Johannes Vermeer",
        "objectDate": "ca. 1662",
        "medium": "Oil on canvas",
        "objectName": "Painting",
        "culture": "",
        "dimensions": "18 x 16 in. (45.7 x 40.6 cm)",
        "creditLine": "Marquand Collection, 1889",
        "objectURL": f"https://www.metmuseum.org/art/collection/search/{object_id}",
        "tags": [{"term": "Women"}, {"term": "Interiors"}],
        **extra,
    }


@respx.mock
async def test_search_fetches_the_objects_of_a_page():
    search = respx.get(f"{BASE}/public/collection/v1.1/search").mock(
        return_value=httpx.Response(200, json={"total": 3, "objectIDs": [1, 2, 3]})
    )
    respx.get(f"{BASE}/public/collection/v1/objects/1").mock(return_value=httpx.Response(200, json=_object(1)))
    respx.get(f"{BASE}/public/collection/v1/objects/2").mock(
        return_value=httpx.Response(200, json=_object(2, primaryImage="", primaryImageSmall=""))
    )
    respx.get(f"{BASE}/public/collection/v1/objects/3").mock(return_value=httpx.Response(404, json={"message": "no"}))
    source = _source()

    page = await source.search_page(query="vermeer", offset=0, count=3)
    await source.aclose()

    params = search.calls.last.request.url.params
    assert (params["q"], params["isPublicDomain"], params["hasImages"], params["offset"], params["limit"]) == (
        "vermeer", "true", "true", "0", "3",
    )
    assert "isHighlight" not in params
    assert [a["assetID"] for a in page.items] == ["1"]  # 2 has no image, 3 is gone
    assert (page.upstream_count, page.page_size, page.has_more) == (3, 3, True)
    asset = page.items[0]
    assert asset["rights"] == "CC0 1.0"
    assert asset["creator"] == "Johannes Vermeer"
    assert asset["previewURI"].endswith("/web-large/DP1.jpg")
    assert asset["assetURI"].endswith("/original/DP1.jpg")
    assert (asset["type"], asset["format"], asset["subject"]) == ("Painting", "Oil on canvas", "Women, Interiors")
    assert "coverage" not in asset
    assert asset["details"] == [
        {"label": "Dimensions", "value": "18 x 16 in. (45.7 x 40.6 cm)"},
        {"label": "Credit line", "value": "Marquand Collection, 1889"},
    ]


@respx.mock
async def test_no_search_term_means_highlights():
    search = respx.get(f"{BASE}/public/collection/v1.1/search").mock(
        return_value=httpx.Response(200, json={"total": 0, "objectIDs": []})
    )
    source = _source()
    page = await source.search_page(query=None, offset=12, count=12)
    await source.aclose()

    params = search.calls.last.request.url.params
    assert params["isHighlight"] == "true" and "q" not in params and params["offset"] == "12"
    assert page.items == [] and not page.has_more


@respx.mock
async def test_default_query_narrows_every_search():
    search = respx.get(f"{BASE}/public/collection/v1.1/search").mock(
        return_value=httpx.Response(200, json={"total": 0, "objectIDs": []})
    )
    source = _source(default_query={"departmentId": "11"})
    await source.search(query="rembrandt", offset=0, count=5)
    await source.aclose()

    params = search.calls.last.request.url.params
    assert (params["departmentId"], params["q"]) == ("11", "rembrandt")


@respx.mock
async def test_lookup_uses_the_cache_and_knows_what_is_missing():
    objects = respx.get(f"{BASE}/public/collection/v1/objects/1").mock(return_value=httpx.Response(200, json=_object(1)))
    respx.get(f"{BASE}/public/collection/v1/objects/9").mock(return_value=httpx.Response(404, json={}))
    source = _source()

    first = await source.get_asset("1")
    second = await source.get_asset("1")
    with pytest.raises(AssetNotFound):
        await source.get_asset("9")
    with pytest.raises(AssetNotFound):
        await source.get_asset("not-a-number")
    await source.aclose()

    assert first == second and first["title"] == "Object 1"
    assert objects.call_count == 1
