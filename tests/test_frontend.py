"""Serving the web app build: prerendered pages, SPA fallback, caching and
the boundary to the API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.frontend import mount_frontend
from app.settings import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    build = tmp_path / "build"
    (build / "legal").mkdir(parents=True)
    (build / "_app" / "immutable").mkdir(parents=True)
    (build / "index.html").write_text("HOME", encoding="utf-8")
    (build / "200.html").write_text("SHELL", encoding="utf-8")
    (build / "legal" / "privacy.html").write_text("PRIVACY", encoding="utf-8")
    (build / "_app" / "immutable" / "app.js").write_text("JS", encoding="utf-8")
    (build / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(settings, "frontend_dir", build)
    app = FastAPI()
    mount_frontend(app)
    return TestClient(app)


def test_prerendered_pages(client):
    home = client.get("/")
    privacy = client.get("/legal/privacy")
    assert (home.text, home.headers["cache-control"]) == ("HOME", "no-cache")
    assert privacy.text == "PRIVACY"


@pytest.mark.parametrize(
    "path", ["/explore", "/explore?q=x", "/my", "/signin", "/c/abc", "/c/abc/edit", "/admin", "/admin/sources"]
)
def test_app_routes_get_the_shell(client, path):
    r = client.get(path)
    assert (r.status_code, r.text) == (200, "SHELL")


@pytest.mark.parametrize("path", ["/nope", "/c", "/explorer"])
def test_unknown_pages_get_the_shell_with_404(client, path):
    r = client.get(path)
    assert (r.status_code, r.text) == (404, "SHELL")


@pytest.mark.parametrize("path", ["/api/nope", "/admin/api/nope", "/collections/x/y/z", "/sources/x"])
def test_api_paths_never_return_the_web_app(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


def test_caching(client):
    assert client.get("/_app/immutable/app.js").headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/favicon.svg").headers["cache-control"] == "public, max-age=86400"


def test_files_outside_the_build_are_not_served(client):
    assert client.get("/%2e%2e/secret.txt").text != "secret"
    assert client.get("/legal/%2e%2e/%2e%2e/secret.txt").text != "secret"
