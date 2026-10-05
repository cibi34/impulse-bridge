"""IIIF manifest source: canvases become assets with readable titles."""

import httpx
import respx

from app.adapter.custom.iiif import IIIFManifestSource
from app.cache import cache
from app.config.schema import SourceConfig

MANIFEST_URL = "https://iiif.example.org/manifest.json"


def _canvas(n: int, label):
    return {
        "id": f"https://iiif.example.org/canvas/c{n}",
        "type": "Canvas",
        "label": label,
        "items": [{"items": [{"motivation": "painting", "body": {
            "id": f"https://iiif.example.org/image/c{n}/full/max/0/default.jpg"}}]}],
    }


@respx.mock
async def test_canvases_without_a_real_label_get_a_page_title():
    cache._store.clear()
    respx.get(MANIFEST_URL).mock(return_value=httpx.Response(200, json={
        "type": "Manifest",
        "label": {"en": ["Book of Wonders"]},
        "items": [_canvas(1, {"none": ["-"]}), _canvas(2, {"en": ["Frontispiece"]}), _canvas(3, None)],
    }))
    source = IIIFManifestSource(SourceConfig.model_validate({
        "collection": {"id": "iiif-test", "name": "T", "organization": "T", "owner_id": "t"},
        "adapter": {"kind": "custom", "custom_class": "x.Y", "base_url": MANIFEST_URL},
    }))

    assets = await source.search(query=None, offset=0, count=None)
    await source.aclose()

    assert [a["title"] for a in assets] == [
        "Book of Wonders — page 1",
        "Frontispiece",
        "Book of Wonders — page 3",
    ]
    assert assets[0]["previewURI"].endswith("/full/!400,400/0/default.jpg")


def _canvas_v2(n: int, label: str) -> dict:
    return {
        "@id": f"https://iiif.example.org/canvas/{n}",
        "@type": "sc:Canvas",
        "label": label,
        "width": 2000,
        "height": 3000,
        "images": [{"resource": {
            "@id": f"https://iiif.example.org/data/{n}.jpg",
            "format": "image/jpeg",
            "service": {"@id": f"https://iiif.example.org/iiif/2/{n}.jpg"},
        }}],
    }


@respx.mock
async def test_v2_pages_are_named_after_their_section_and_holder():
    """A digitised manuscript (Presentation API v2): the table of contents
    names the pages, the attribution names the library, and previews come
    from the Image API service."""
    cache._store.clear()
    respx.get(MANIFEST_URL).mock(return_value=httpx.Response(200, json={
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "label": "Codex Manesse",
        "license": "http://creativecommons.org/publicdomain/mark/1.0/",
        "attribution": [
            {"@language": "de", "@value": "Universitätsbibliothek Heidelberg"},
            {"@language": "en", "@value": "Heidelberg University Library"},
        ],
        "metadata": [{"label": "Date", "value": ["ca. 1300"]}, {"label": "Location", "value": "Zürich"}],
        "sequences": [{"canvases": [_canvas_v2(1, "5v"), _canvas_v2(2, "6r"), _canvas_v2(3, "6v")]}],
        "structures": [
            {"label": "Register", "canvases": ["https://iiif.example.org/canvas/1"]},
            {"label": "Kaiser Heinrich", "canvases": [
                "https://iiif.example.org/canvas/2", "https://iiif.example.org/canvas/3"]},
        ],
    }))
    source = IIIFManifestSource(SourceConfig.model_validate({
        "collection": {"id": "iiif-test", "name": "T", "organization": "T", "owner_id": "t"},
        "adapter": {"kind": "custom", "custom_class": "x.Y", "base_url": MANIFEST_URL},
    }))

    assets = await source.search(query=None, offset=0, count=None)
    found = await source.search(query="heinrich", offset=0, count=None)
    await source.aclose()

    assert [a["title"] for a in assets] == ["Register — 5v", "Kaiser Heinrich — 6r", "Kaiser Heinrich — 6v"]
    assert [a["title"] for a in found] == ["Kaiser Heinrich — 6r", "Kaiser Heinrich — 6v"]
    page = assets[1]
    assert page["subject"] == "Kaiser Heinrich"
    assert page["contributor"] == "Heidelberg University Library"
    assert (page["date"], page["coverage"]) == ("ca. 1300", "Zürich")
    assert page["details"] == [
        {"label": "Page", "value": "6r"},
        {"label": "Date", "value": "ca. 1300"},
        {"label": "Location", "value": "Zürich"},
    ]
    assert page["rights"] == "http://creativecommons.org/publicdomain/mark/1.0/"
    assert page["assetURI"] == "https://iiif.example.org/iiif/2/2.jpg/full/max/0/default.jpg"
    assert page["previewURI"] == "https://iiif.example.org/iiif/2/2.jpg/full/!400,400/0/default.jpg"
    assert (page["width"], page["height"]) == (2000, 3000)


@respx.mock
async def test_bare_page_numbers_get_the_manifest_title():
    cache._store.clear()
    respx.get(MANIFEST_URL).mock(return_value=httpx.Response(200, json={
        "label": "Herbarium",
        "sequences": [{"canvases": [_canvas_v2(1, "fol. 12r"), _canvas_v2(2, "Title page")]}],
    }))
    source = IIIFManifestSource(SourceConfig.model_validate({
        "collection": {"id": "iiif-test", "name": "T", "organization": "T", "owner_id": "t"},
        "adapter": {"kind": "custom", "custom_class": "x.Y", "base_url": MANIFEST_URL},
    }))
    assets = await source.search(query=None, offset=0, count=None)
    await source.aclose()
    assert [a["title"] for a in assets] == ["Herbarium — fol. 12r", "Title page"]
    assert assets[0]["contributor"] == "Herbarium"  # no attribution: the work itself
