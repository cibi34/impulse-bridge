"""The web app lists sources by their `order`, then by filename."""

from fastapi.testclient import TestClient

from app.main import app
from conftest import write_fallback


def test_sources_are_listed_by_order_then_filename(config_dir):
    write_fallback(config_dir, "alpha")                      # no order: 100
    write_fallback(config_dir, "beta")                       # no order: 100, after alpha
    gamma = write_fallback(config_dir, "gamma")
    gamma.write_text("order: 1\n" + gamma.read_text(encoding="utf-8"), encoding="utf-8")

    with TestClient(app) as client:
        ids = [s["id"] for s in client.get("/api/sources").json()["sources"]]

    assert ids == ["gamma", "alpha", "beta"]
