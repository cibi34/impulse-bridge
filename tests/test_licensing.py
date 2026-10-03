"""Licences: how rights values are read, and how the accepted licence
conditions (an admin setting) decide what the web app offers, what can be
added to a collection, and what Unity is served."""

import json

import pytest
from fastapi.testclient import TestClient

from app.licensing import classify
from app.main import app
from conftest import write_fallback


@pytest.mark.parametrize(
    ("rights", "code", "label", "url"),
    [
        # Europeana: Creative Commons and rightsstatements.org URIs
        ("http://creativecommons.org/publicdomain/mark/1.0/", "pd", "Public domain",
         "https://creativecommons.org/publicdomain/mark/1.0/"),
        ("http://creativecommons.org/publicdomain/zero/1.0/", "cc0", "CC0 1.0",
         "https://creativecommons.org/publicdomain/zero/1.0/"),
        ("http://creativecommons.org/licenses/by-sa/3.0/", "by-sa", "CC BY-SA 3.0",
         "https://creativecommons.org/licenses/by-sa/3.0/"),
        ("http://creativecommons.org/licenses/by-nc/4.0/", "by-nc", "CC BY-NC 4.0",
         "https://creativecommons.org/licenses/by-nc/4.0/"),
        ("http://rightsstatements.org/vocab/NoC-NC/1.0/", "noc-nc", "No copyright – non-commercial use only",
         "https://rightsstatements.org/vocab/NoC-NC/1.0/"),
        ("http://rightsstatements.org/vocab/InC/1.0/", "other", "In copyright",
         "https://rightsstatements.org/vocab/InC/1.0/"),
        # Wikimedia: short names and machine codes
        ("CC BY-SA 4.0", "by-sa", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
        ("CC BY-SA 3.0 de", "by-sa", "CC BY-SA 3.0 DE", "https://creativecommons.org/licenses/by-sa/3.0/de/"),
        ("cc-by-4.0", "by", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
        ("CC BY-NC-ND 4.0", "by-nc-nd", "CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
        ("Public domain", "pd", "Public domain", None),
        ("CC0", "cc0", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        ("GFDL", "other", "GFDL", None),
        # Missing or placeholder values
        (None, "other", "Not specified", None),
        ("", "other", "Not specified", None),
        ("See source for license", "other", "Not specified", None),
    ],
)
def test_rights_values_are_classified(rights, code, label, url):
    licence = classify(rights)
    assert (licence.code, licence.label, licence.url) == (code, label, url)


@pytest.mark.parametrize(
    ("rights", "accepted", "allowed"),
    [
        ("Public domain", [], True),
        ("CC0", [], True),
        ("CC BY 4.0", [], False),
        ("CC BY 4.0", ["by"], True),
        ("CC BY-SA 4.0", ["by"], False),
        ("CC BY-SA 4.0", ["by", "sa"], True),
        ("CC BY-NC-SA 4.0", ["by", "sa"], False),
        ("CC BY-NC-SA 4.0", ["by", "sa", "nc"], True),
        ("http://rightsstatements.org/vocab/InC/1.0/", ["by", "sa", "nc", "nd"], False),
        ("Not a licence", ["by", "sa", "nc", "nd"], False),
    ],
)
def test_a_licence_is_allowed_when_all_its_conditions_are_accepted(rights, accepted, allowed):
    assert classify(rights).allowed(accepted) is allowed


ASSETS = [
    {"assetID": "pd", "title": "Old map", "assetURI": "https://example.org/pd.jpg", "rights": "Public domain"},
    {"assetID": "by", "title": "Photo", "assetURI": "https://example.org/by.jpg", "rights": "CC BY 4.0",
     "creator": "Jane Doe"},
    {"assetID": "sa", "title": "Drawing", "assetURI": "https://example.org/sa.jpg", "rights": "CC BY-SA 4.0"},
    {"assetID": "nc", "title": "Book page", "assetURI": "https://example.org/nc.jpg",
     "rights": "http://creativecommons.org/licenses/by-nc/4.0/"},
    {"assetID": "unknown", "title": "Mystery", "assetURI": "https://example.org/x.jpg"},
]


@pytest.fixture
def client(config_dir):
    write_fallback(config_dir, "demo")
    (config_dir.parent / "data" / "demo" / "manifest.json").write_text(json.dumps(ASSETS), encoding="utf-8")
    with TestClient(app) as c:
        yield c


def _ids(body):
    return [a["assetID"] for a in body["items"]]


def test_search_leaves_out_licences_impulse_does_not_accept(client):
    body = client.get("/api/sources/demo/assets").json()
    assert _ids(body) == ["pd", "by", "sa"]
    assert body["hidden"] == 2
    assert body["items"][2]["licence"] == {
        "code": "by-sa",
        "label": "CC BY-SA 4.0",
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "conditions": ["by", "sa"],
        "allowed": True,
    }


def test_search_licence_filter_narrows_further(client):
    free = client.get("/api/sources/demo/assets?licence=free").json()
    attribution = client.get("/api/sources/demo/assets?licence=by").json()
    assert _ids(free) == ["pd"]
    assert _ids(attribution) == ["pd", "by"]
    assert free["hidden"] == attribution["hidden"] == 2  # the filter is the visitor's choice


def test_assets_with_a_licence_not_accepted_cannot_be_added(client):
    body = {"name": "Mixed", "items": [{"source": "demo", "asset_id": a} for a in ("by", "nc", "unknown")]}
    data = client.post("/api/collections", json=body).json()

    assert [i["source_asset_id"] for i in data["collection"]["items"]] == ["by"]
    assert [f["reason"] for f in data["failed"]] == [
        "Licence not accepted: CC BY-NC 4.0",
        "Licence not accepted: Not specified",
    ]


def test_changing_the_accepted_conditions_changes_what_unity_gets(client):
    body = {"name": "Open", "items": [{"source": "demo", "asset_id": a} for a in ("pd", "sa")]}
    data = client.post("/api/collections", json=body).json()
    cid, key = data["collection"]["id"], data["edit_key"]

    client.put("/admin/api/settings", json={"licence_conditions": ["by"]})  # no share-alike any more

    served = client.get(f"/collections/{cid}/assets").json()["data"]
    public = client.get(f"/api/collections/{cid}").json()
    editor = client.get(f"/api/collections/{cid}", headers={"Authorization": f"Bearer {key}"}).json()
    sa_item = next(i for i in editor["items"] if i["source_asset_id"] == "sa")

    assert [a["title"] for a in served] == ["Old map"]
    assert client.get(f"/collections/{cid}/asset/{sa_item['asset_id']}").json()["code"] == 2
    assert [i["source_asset_id"] for i in public["items"]] == ["pd"]
    assert len(editor["items"]) == 2  # the editor still sees it, flagged
    assert sa_item["licence"]["allowed"] is False


def test_accepted_conditions_are_validated_and_published(client):
    saved = client.put("/admin/api/settings", json={"licence_conditions": ["nc", "by", "nc"]})
    invalid = client.put("/admin/api/settings", json={"licence_conditions": ["commercial"]})

    assert saved.json()["licence_conditions"] == ["by", "nc"]
    assert invalid.status_code == 422
    assert client.get("/api/config").json()["licence_conditions"] == ["by", "nc"]
