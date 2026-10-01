"""GenericRestSource.get_asset() lookup strategies, exercised against a mocked
Europeana-shaped upstream with respx."""

import re
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from app.adapter.rest import GenericRestSource
from app.cache import cache
from app.config.schema import SourceConfig
from app.errors import AssetNotFound

BASE = "https://api.example.org"


def _item(record_id: str, title: str) -> dict:
    return {
        "id": record_id,
        "title": [title],
        "edmIsShownBy": [f"{BASE}/media/{record_id}.jpg"],
        "edmPreview": [f"{BASE}/thumb/{record_id}.jpg"],
    }


VAN_GOGH = _item("/90402/SK_A_3262", "Self-portrait")
LEUVEN = _item("/2024903/photography_ProvidedCHO_KU_Leuven_9990940230101488", "Leuven")
OTHER = _item("/1234/OTHER_THING", "Something else")


def _cfg(asset_detail: dict | None = None) -> SourceConfig:
    raw = {
        "collection": {
            "id": "test-europeana",
            "name": "Test",
            "organization": "Test",
            "owner_id": "t@example.org",
        },
        "adapter": {"kind": "rest", "base_url": BASE},
        "search": {
            "path": "/search.json",
            "pagination": {
                "style": "page_size",
                "page_param": "start",
                "size_param": "rows",
                "page_base": 1,
                "max_size": 100,
            },
            "query": {"pattern_param": "query", "pattern_when_empty": "*"},
        },
        "mapping": {
            "items_path": "items",
            "fields": {
                "assetID": {"expr": "id", "transform": "slugify"},
                "title": {"expr": "title[0]"},
                "assetURI": {"expr": "edmIsShownBy[0]"},
                "previewURI": {"expr": "edmPreview[0]"},
                "contentType": {"literal": "image/jpeg"},
            },
        },
        "filter": {"drop_if_missing": ["assetURI", "previewURI"]},
    }
    if asset_detail is not None:
        raw["asset_detail"] = asset_detail
    return SourceConfig.model_validate(raw)


REGEX_DETAIL = {
    "enabled": True,
    "path": "/search.json",
    "query": {"query": "europeana_id:/{asset_id_regex}/", "rows": "1"},
}


def _solr_like_search(request: httpx.Request) -> httpx.Response:
    """Mimic the upstream: a plain query returns a fixed page; a Solr regex
    query `europeana_id:/.../` returns the records whose id matches the regex
    (Lucene regexes here are a subset of Python's)."""
    q = parse_qs(urlparse(str(request.url)).query).get("query", ["*"])[0]
    m = re.fullmatch(r"europeana_id:/(.+)/", q)
    if m:
        items = [
            it
            for it in (VAN_GOGH, LEUVEN, OTHER)
            if re.fullmatch(m.group(1), it["id"])
        ]
        return httpx.Response(200, json={"items": items})
    if q == "van gogh":
        return httpx.Response(200, json={"items": [VAN_GOGH, LEUVEN]})
    # default search page: the van gogh item is deliberately NOT on it
    return httpx.Response(200, json={"items": [OTHER]})


@pytest.fixture(autouse=True)
def _clear_cache():
    cache._store.clear()
    yield
    cache._store.clear()


@pytest.fixture
def upstream():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        mock.get("/search.json").mock(side_effect=_solr_like_search)
        yield mock


async def test_detail_lookup_via_regex_placeholder(upstream):
    src = GenericRestSource(_cfg(REGEX_DETAIL))
    try:
        asset = await src.get_asset("90402-sk-a-3262")
    finally:
        await src.aclose()
    assert asset["assetID"] == "90402-sk-a-3262"
    assert asset["title"] == "Self-portrait"
    sent = parse_qs(urlparse(str(upstream.calls.last.request.url)).query)
    assert sent["query"] == [
        "europeana_id:/[^a-zA-Z0-9]*90402[^a-zA-Z0-9]+[sS][kK][^a-zA-Z0-9]+"
        "[aA][^a-zA-Z0-9]+3262[^a-zA-Z0-9]*/"
    ]
    assert sent["rows"] == ["1"]
    # detail query replaces the search's params: no pagination leaked in
    assert "start" not in sent


async def test_detail_lookup_handles_mixed_case_ids(upstream):
    src = GenericRestSource(_cfg(REGEX_DETAIL))
    try:
        asset = await src.get_asset(
            "2024903-photography-providedcho-ku-leuven-9990940230101488"
        )
    finally:
        await src.aclose()
    assert asset["title"] == "Leuven"


async def test_detail_lookup_unknown_id_raises(upstream):
    src = GenericRestSource(_cfg(REGEX_DETAIL))
    try:
        with pytest.raises(AssetNotFound):
            await src.get_asset("does-not-exist-evaluation")
    finally:
        await src.aclose()


async def test_detail_lookup_rejects_item_with_different_id(upstream):
    """If the detail request returns a record whose mapped assetID differs from
    the requested one, it must not be served as that asset."""
    cfg = _cfg(
        {
            "enabled": True,
            "path": "/search.json",
            # a literal query: upstream answers with the default page (OTHER)
            "query": {"query": "*"},
        }
    )
    src = GenericRestSource(cfg)
    try:
        with pytest.raises(AssetNotFound):
            await src.get_asset("90402-sk-a-3262")
    finally:
        await src.aclose()


async def test_recently_searched_asset_is_found_without_detail_config(upstream):
    """Every asset a search returned must be retrievable afterwards, even when
    no asset_detail is configured and the default search page lacks it."""
    src = GenericRestSource(_cfg())
    try:
        found = await src.search(query="van gogh", offset=0, count=5)
        assert [a["assetID"] for a in found] == [
            "90402-sk-a-3262",
            "2024903-photography-providedcho-ku-leuven-9990940230101488",
        ]
        calls_before = len(upstream.calls)
        asset = await src.get_asset("90402-sk-a-3262")
        assert asset["title"] == "Self-portrait"
        assert len(upstream.calls) == calls_before  # served from the seen index
    finally:
        await src.aclose()


async def test_without_detail_config_and_never_searched_falls_back_to_scan(upstream):
    src = GenericRestSource(_cfg())
    try:
        # OTHER is on the default page -> found via scan
        asset = await src.get_asset("1234-other-thing")
        assert asset["title"] == "Something else"
        # VAN_GOGH is not -> not found
        with pytest.raises(AssetNotFound):
            await src.get_asset("90402-sk-a-3262")
    finally:
        await src.aclose()
