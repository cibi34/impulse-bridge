"""Fallback files under the collection URI: served from the current source's
directory (also right after a reload), never from outside of it."""

from fastapi.testclient import TestClient

from app.main import app
from conftest import write_fallback

# Configs are written before entering TestClient, whose lifespan loads them.


def test_serves_files_next_to_the_manifest(config_dir):
    write_fallback(config_dir, "demo", files={"demo.glb": "GLB"})
    with TestClient(app) as client:
        r = client.get("/collections/demo/demo.glb")
        head = client.head("/collections/demo/demo.glb")

    assert r.status_code == 200
    assert r.text == "GLB"
    assert r.headers["content-type"] == "model/gltf-binary"
    assert head.status_code == 200


def test_api_routes_take_precedence_over_files(config_dir):
    write_fallback(config_dir, "demo", files={"assets": "not me"})
    with TestClient(app) as client:
        r = client.get("/collections/demo/assets")

    assert r.json()["data"][0]["assetID"] == "demo"


def test_paths_outside_the_directory_are_rejected(config_dir):
    write_fallback(config_dir, "demo")
    (config_dir.parent / "data" / "secret.txt").write_text("secret", encoding="utf-8")
    with TestClient(app) as client:
        encoded = client.get("/collections/demo/%2e%2e/secret.txt")
        nested = client.get("/collections/demo/sub/%2e%2e/%2e%2e/secret.txt")

    assert encoded.status_code == 404
    assert nested.status_code == 404


def test_after_reload_files_come_from_the_new_directory(config_dir):
    path = write_fallback(config_dir, "demo", files={"demo.glb": "OLD"})
    new_dir = config_dir.parent / "data" / "moved"
    new_dir.mkdir()
    (new_dir / "manifest.json").write_text("[]", encoding="utf-8")
    (new_dir / "demo.glb").write_text("NEW", encoding="utf-8")
    with TestClient(app) as client:
        before = client.get("/collections/demo/demo.glb").text
        path.write_text(
            path.read_text(encoding="utf-8").replace("/demo/manifest.json", "/moved/manifest.json"),
            encoding="utf-8",
        )
        client.post("/admin/api/reload")
        after = client.get("/collections/demo/demo.glb").text

    assert (before, after) == ("OLD", "NEW")


def test_no_files_without_static_mount(config_dir):
    write_fallback(config_dir, "demo", files={"demo.glb": "GLB"}, static_mount=False)
    with TestClient(app) as client:
        r = client.get("/collections/demo/demo.glb")

    assert r.status_code == 404
