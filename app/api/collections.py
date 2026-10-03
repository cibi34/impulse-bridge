"""Impulse Collections-and-Assets API, served from the curated collections.

This is what the Impulse platform and Unity clients consume. The archives
behind the web app (Europeana, Wikimedia, …) are not collections here; they
are only searchable through the web app API (app/api/sources.py).

Only assets the editor left visible and whose licence IMPULSE accepts are
served (`served()`).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.params import pagination
from app.api.responses import impulse_response
from app.curation.service import impulse_asset, impulse_collection, served
from app.curation.store import CollectionRecord, CollectionStore
from app.errors import AssetNotFound, CollectionNotFound
from app.storage import get_licence_conditions, get_store
from app.transform.helpers import matches_pattern

router = APIRouter(tags=["impulse"])

Store = Annotated[CollectionStore, Depends(get_store)]
Accepted = Annotated[frozenset[str], Depends(get_licence_conditions)]


def _published(store: CollectionStore, collection_id: str) -> CollectionRecord:
    record = store.get(collection_id)
    if record is None or record.disabled:
        raise CollectionNotFound(f"Collection '{collection_id}' not found")
    return record


@router.get("/collections")
def list_collections(store: Store):
    """Collections an administrator listed. Every other collection is still
    reachable through its own URI."""
    return impulse_response(data=[impulse_collection(r) for r in store.list_listed()])


@router.get("/collections/{collection_id}")
def get_collection(collection_id: str, store: Store):
    return impulse_response(data=impulse_collection(_published(store, collection_id)))


@router.get("/collections/{collection_id}/assets")
def list_assets(
    collection_id: str,
    store: Store,
    accepted: Accepted,
    s: Annotated[str | None, Query(description="Search pattern, '*' wildcards allowed")] = None,
    o: Annotated[str | None, Query(description="Result offset (integer >= 0)")] = None,
    c: Annotated[str | None, Query(description="Result count (integer >= 1)")] = None,
):
    _published(store, collection_id)
    offset, count = pagination(o, c)
    assets = [
        impulse_asset(item)
        for item in store.items(collection_id, published_only=True)
        if served(item, accepted)
    ]
    matched = [a for a in assets if matches_pattern(a, s)]
    end = offset + count if count is not None else None
    return impulse_response(data=matched[offset:end])


@router.get("/collections/{collection_id}/asset/{asset_id}")
def get_asset(collection_id: str, asset_id: str, store: Store, accepted: Accepted):
    _published(store, collection_id)
    item = store.item(collection_id, asset_id)
    if item is None or not served(item, accepted):
        raise AssetNotFound(f"Asset '{asset_id}' not found in collection '{collection_id}'")
    return impulse_response(data=impulse_asset(item))
