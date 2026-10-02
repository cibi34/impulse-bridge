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
