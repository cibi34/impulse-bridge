"""Ids of curated collections and their assets read well in ASCII."""

from app.curation.service import item_asset_id, new_collection_id


def test_asset_ids_transliterate_accents():
    asset_id = item_asset_id("König Tyro von Schotten — 8r", "manesse", "0011", set())
    assert asset_id.startswith("konig-tyro-von-schotten-8r-")


def test_collection_ids_transliterate_ligatures():
    assert new_collection_id("Straße & Œuvre", lambda _id: False).startswith("strasse-oeuvre-")
