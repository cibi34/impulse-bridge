"""The admin "Test" run shows the upstream URL and raw response on every run,
including runs answered from the cache."""

import httpx
import respx
from fastapi.testclient import TestClient

from app.cache import cache
from app.main import app

YAML = """
collection:
  id: test-upstream
  name: Test
  organization: Test
  owner_id: t@example.org
adapter:
  kind: rest
  base_url: https://api.example.org
search:
  path: /search
  query: { pattern_param: q }
mapping:
  items_path: items
  fields:
    assetID: { expr: id }
"""


@respx.mock
def test_repeated_test_runs_report_upstream_url_and_response(config_dir):
    cache._store.clear()
    route = respx.get("https://api.example.org/search").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "x1"}]})
    )
    with TestClient(app) as client:
        runs = [
            client.post("/admin/api/test", json={"yaml": YAML, "query": "cats", "count": 3}).json()
            for _ in range(2)
        ]

    assert route.call_count == 1  # the second run is a cache hit
    for run in runs:
        assert run["errors"] == []
        assert run["upstream_url"].startswith("https://api.example.org/search?")
        assert "q=cats" in run["upstream_url"]
        assert run["raw_upstream"] == {"items": [{"id": "x1"}]}
        assert run["transformed"] == [{"assetID": "x1"}]


KEYED_YAML = YAML.replace("base_url: https://api.example.org", """base_url: https://api.example.org
  auth: { type: query_param, name: wskey, value: s3cret-key }""")


@respx.mock
def test_the_api_key_is_masked_in_the_reported_upstream_url(config_dir):
    cache._store.clear()
    respx.get("https://api.example.org/search").mock(
        return_value=httpx.Response(200, json={"apikey": "s3cret-key", "items": [{"id": "x1"}]})
    )
    with TestClient(app) as client:
        run = client.post("/admin/api/test", json={"yaml": KEYED_YAML, "query": "cats"}).json()

    assert "s3cret-key" not in str(run)
    assert "wskey=***" in run["upstream_url"]
    assert "q=cats" in run["upstream_url"]
    assert run["raw_upstream"]["apikey"] == "***"
