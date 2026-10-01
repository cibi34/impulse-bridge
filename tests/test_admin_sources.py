"""Admin API: creating never overwrites, saving survives broken files on disk,
and the reload endpoint picks up edits made directly on disk."""

from fastapi.testclient import TestClient

from app.main import app
from conftest import BROKEN_YAML, write_fallback

# Configs are written before entering TestClient, whose lifespan loads them.


def _yaml_of(client, cid: str) -> str:
    return client.get(f"/admin/api/sources/{cid}").json()["yaml"]


def test_create_refuses_an_existing_id(config_dir):
    original = write_fallback(config_dir, "alpha", name="Original")
    before = original.read_text(encoding="utf-8")
    with TestClient(app) as client:
        yaml_text = _yaml_of(client, "alpha").replace("Original", "Impostor")
        r = client.put("/admin/api/sources/alpha?create=true", json={"yaml": yaml_text})

    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]
    assert original.read_text(encoding="utf-8") == before


def test_renaming_onto_another_sources_id_is_refused(config_dir):
    write_fallback(config_dir, "alpha")
    beta = write_fallback(config_dir, "beta", name="Beta")
    with TestClient(app) as client:
        yaml_text = _yaml_of(client, "alpha").replace("id: alpha", "id: beta")
        r = client.put("/admin/api/sources/alpha", json={"yaml": yaml_text})

    assert r.status_code == 409
    assert 'name: "Beta"' in beta.read_text(encoding="utf-8")


def test_create_writes_a_new_file_and_registers_it(config_dir):
    template = write_fallback(config_dir, "alpha")
    with TestClient(app) as client:
        yaml_text = template.read_text(encoding="utf-8").replace("id: alpha", "id: gamma")
        r = client.put("/admin/api/sources/gamma?create=true", json={"yaml": yaml_text})
        ids = [s["id"] for s in client.get("/api/sources").json()["sources"]]

    assert r.status_code == 200
    assert (config_dir / "gamma.yaml").is_file()
    assert ids == ["alpha", "gamma"]


def test_create_does_not_clobber_a_file_that_holds_another_id(config_dir):
    # gamma.yaml exists but defines "delta"; creating "gamma" must not reuse it.
    write_fallback(config_dir, "delta", filename="gamma.yaml")
    with TestClient(app) as client:
        yaml_text = (config_dir / "gamma.yaml").read_text(encoding="utf-8").replace(
            "id: delta", "id: gamma"
        )
        r = client.put("/admin/api/sources/gamma?create=true", json={"yaml": yaml_text})

    assert r.status_code == 200
    assert "id: delta" in (config_dir / "gamma.yaml").read_text(encoding="utf-8")
    assert "id: gamma" in (config_dir / "gamma-2.yaml").read_text(encoding="utf-8")


def test_saving_with_a_broken_file_on_disk_keeps_all_valid_sources(config_dir):
    write_fallback(config_dir, "alpha")
    write_fallback(config_dir, "beta")
    with TestClient(app) as client:
        (config_dir / "broken.yaml").write_text(BROKEN_YAML, encoding="utf-8")
        r = client.put("/admin/api/sources/alpha", json={"yaml": _yaml_of(client, "alpha")})
        ids = [s["id"] for s in client.get("/api/sources").json()["sources"]]
        listing = client.get("/admin/api/sources").json()

    assert r.status_code == 200
    assert ids == ["alpha", "beta"]
    broken = next(s for s in listing["sources"] if s["filename"] == "broken.yaml")
    assert broken["loaded"] is False
    assert "collection.name" in broken["error"]


def test_reload_picks_up_edits_made_on_disk(config_dir):
    path = write_fallback(config_dir, "alpha", name="Before")
    with TestClient(app) as client:
        path.write_text(path.read_text(encoding="utf-8").replace("Before", "After"), encoding="utf-8")
        r = client.post("/admin/api/reload")
        name = client.get("/api/sources").json()["sources"][0]["name"]

    assert r.status_code == 200
    assert r.json()["loaded_count"] == 1
    assert name == "After"
