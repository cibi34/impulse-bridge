"""Admin file API: configs are edited as text (comments survive), broken files
can be repaired, ids stay unique, and errors point at their line."""

from fastapi.testclient import TestClient

from app.admin.validation import validate_text
from app.main import app
from conftest import BROKEN_YAML, write_fallback

# Configs are written before entering TestClient, whose lifespan loads them.


def test_schema_errors_point_at_the_deepest_existing_key():
    text = "collection:\n  id: x\n  name: X\nadapter:\n  kind: rest\nsearch:\n  pagination:\n    style: pages\n"
    result = validate_text(text)
    by_loc = {".".join(map(str, e["loc"])): e["line"] for e in result["errors"]}

    assert result["valid"] is False
    assert by_loc["search.pagination.style"] == 8
    assert by_loc["collection.organization"] == 1  # missing: points at its parent


def test_yaml_syntax_errors_have_a_line():
    result = validate_text("collection:\n  id: x\n  name: [unclosed\n")
    assert result["valid"] is False
    assert result["errors"][0]["msg"].startswith("YAML syntax:")
    assert result["errors"][0]["line"] is not None


def test_saving_keeps_the_text_including_comments(config_dir):
    path = write_fallback(config_dir, "alpha")
    with TestClient(app) as client:
        text = "# Explains why this source exists\n" + path.read_text(encoding="utf-8")
        r = client.put("/admin/api/files/alpha.yaml", json={"yaml": text})

    assert r.status_code == 200
    assert path.read_text(encoding="utf-8").startswith("# Explains why this source exists\n")
    assert r.json()["loaded"] is True


def test_a_broken_file_can_be_opened_and_repaired(config_dir):
    write_fallback(config_dir, "alpha")
    (config_dir / "broken.yaml").write_text(BROKEN_YAML, encoding="utf-8")
    fixed = (config_dir / "alpha.yaml").read_text(encoding="utf-8").replace("id: alpha", "id: repaired")
    with TestClient(app) as client:
        opened = client.get("/admin/api/files/broken.yaml").json()
        saved = client.put("/admin/api/files/broken.yaml", json={"yaml": fixed})
        ids = [s["id"] for s in client.get("/api/sources").json()["sources"]]

    assert opened["valid"] is False and opened["yaml"] == BROKEN_YAML
    assert saved.status_code == 200
    assert sorted(ids) == ["alpha", "repaired"]


def test_invalid_text_is_not_saved(config_dir):
    path = write_fallback(config_dir, "alpha")
    before = path.read_text(encoding="utf-8")
    with TestClient(app) as client:
        r = client.put("/admin/api/files/alpha.yaml", json={"yaml": BROKEN_YAML})

    assert r.status_code == 422
    assert r.json()["detail"]["errors"]
    assert path.read_text(encoding="utf-8") == before


def test_ids_stay_unique(config_dir):
    write_fallback(config_dir, "alpha")
    beta = write_fallback(config_dir, "beta")
    with TestClient(app) as client:
        stolen = beta.read_text(encoding="utf-8").replace("id: beta", "id: alpha")
        update = client.put("/admin/api/files/beta.yaml", json={"yaml": stolen})
        create = client.post("/admin/api/files", json={"yaml": stolen})

    assert update.status_code == 409 and "alpha.yaml" in update.json()["detail"]
    assert create.status_code == 409


def test_create_and_delete(config_dir):
    template = write_fallback(config_dir, "alpha").read_text(encoding="utf-8")
    with TestClient(app) as client:
        created = client.post("/admin/api/files", json={"yaml": template.replace("id: alpha", "id: gamma")})
        deleted = client.delete("/admin/api/files/gamma.yaml")
        ids = [s["id"] for s in client.get("/api/sources").json()["sources"]]

    assert (created.status_code, created.json()["filename"]) == (201, "gamma.yaml")
    assert deleted.json() == {"deleted": "gamma.yaml"}
    assert ids == ["alpha"]


def test_unsafe_filenames_are_rejected(config_dir):
    with TestClient(app) as client:
        for name in ["..%2Fsecret.yaml", "notyaml.txt", ".hidden.yaml"]:
            assert client.get(f"/admin/api/files/{name}").status_code == 404
