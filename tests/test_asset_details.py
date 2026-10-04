"""Technical details of assets (pixels, bytes): what sources provide, what the
web app shows, and how the Impulse API sums them up in `format`."""

import json
import struct
import zlib

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.adapter.custom.iiif import IIIFManifestSource
from app.adapter.fallback import FallbackSource
from app.cache import cache
from app.config.schema import SourceConfig
from app.curation.service import format_summary, human_size
from app.main import app
from conftest import write_fallback


@pytest.mark.parametrize(
    ("size", "text"),
    [(8770678, "8.8 MB"), (76336, "76.3 KB"), (3000, "3 KB"), (999, "999 bytes"), (2_000_000_000, "2 GB")],
)
def test_human_size(size, text):
    assert human_size(size) == text


def test_format_summary():
    assert format_summary({"width": 3606, "height": "2894", "fileSize": 8770678}) == "3606 × 2894 px, 8.8 MB"
    assert format_summary({"fileSize": 3284}) == "3.3 KB"
    assert format_summary({"width": 10}) is None
    assert format_summary({"width": "n/a", "height": None, "fileSize": -1}) is None


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00" + b"\x00\x00\x00" * width)  # one row is enough for the header
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def test_fallback_sources_measure_their_local_files(tmp_path):
    (tmp_path / "pic.png").write_bytes(_png(640, 480))
    (tmp_path / "model.glb").write_bytes(b"glTF" + b"\0" * 96)
    (tmp_path / "manifest.json").write_text(json.dumps([
        {"assetID": "pic", "assetURI": "pic.png"},
        {"assetID": "model", "assetURI": "model.glb", "fileSize": 1},  # stated values win
        {"assetID": "remote", "assetURI": "https://example.org/x.png"},
        {"assetID": "outside", "assetURI": "../secret.png"},
    ]), encoding="utf-8")
    (tmp_path.parent / "secret.png").write_bytes(_png(1, 1))

    source = FallbackSource({"id": "local"}, tmp_path / "manifest.json")
    by_id = {a["assetID"]: a for a in source._assets}

    assert (by_id["pic"]["width"], by_id["pic"]["height"]) == (640, 480)
    assert by_id["pic"]["fileSize"] == (tmp_path / "pic.png").stat().st_size
    assert by_id["model"]["fileSize"] == 1
    assert "fileSize" not in by_id["remote"]
    assert "fileSize" not in by_id["outside"]  # nothing outside the manifest's folder


@respx.mock
async def test_iiif_pages_carry_their_pixel_size():
    cache._store.clear()
    url = "https://iiif.example.org/manifest.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={
        "type": "Manifest",
        "label": {"en": ["Book"]},
        "items": [{
            "id": "https://iiif.example.org/canvas/c1", "type": "Canvas", "width": 2400, "height": 3200,
            "items": [{"items": [{"motivation": "painting", "body": {
                "id": "https://iiif.example.org/image/c1/full/max/0/default.jpg"}}]}],
        }],
    }))
    source = IIIFManifestSource(SourceConfig.model_validate({
        "collection": {"id": "iiif-test", "name": "T", "organization": "T", "owner_id": "t"},
        "adapter": {"kind": "custom", "custom_class": "x.Y", "base_url": url},
    }))
    assets = await source.search(query=None, offset=0, count=None)
    await source.aclose()
    assert (assets[0]["width"], assets[0]["height"]) == (2400, 3200)


ASSETS = [
    {"assetID": "photo", "title": "Photo", "assetURI": "https://example.org/p.jpg", "rights": "CC0",
     "width": 3606, "height": 2894, "fileSize": 8770678},
    {"assetID": "model", "title": "Model", "assetURI": "https://example.org/m.glb", "rights": "CC0",
     "format": "glTF 2.0 binary", "fileSize": 76336},
]


@pytest.fixture
def client(config_dir):
    write_fallback(config_dir, "demo")
    (config_dir.parent / "data" / "demo" / "manifest.json").write_text(json.dumps(ASSETS), encoding="utf-8")
    with TestClient(app) as c:
        yield c


def test_web_app_gets_the_details_impulse_gets_format(client):
    body = {"name": "Details", "items": [{"source": "demo", "asset_id": a["assetID"]} for a in ASSETS]}
    cid = client.post("/api/collections", json=body).json()["collection"]["id"]

    web = {i["source_asset_id"]: i["asset"] for i in client.get(f"/api/collections/{cid}").json()["items"]}
    impulse = {a["title"]: a for a in client.get(f"/collections/{cid}/assets").json()["data"]}

    assert (web["photo"]["width"], web["photo"]["height"], web["photo"]["fileSize"]) == (3606, 2894, 8770678)
    assert impulse["Photo"]["format"] == "3606 × 2894 px, 8.8 MB"
    assert impulse["Model"]["format"] == "glTF 2.0 binary, 76.3 KB"
    assert not {"width", "height", "fileSize"} & set(impulse["Photo"])
