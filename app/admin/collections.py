"""Admin API for curated collections: overview, listing in /collections,
locking, deleting and issuing a new edit key (e.g. for a creator who lost
the link). Protected like the rest of /admin (basic auth at the proxy)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.curation import get_store
from app.curation.service import collection_uri, new_edit_key
from app.curation.store import CollectionRecord, CollectionStore

router = APIRouter(prefix="/admin/api/collections", tags=["admin"])

Store = Annotated[CollectionStore, Depends(get_store)]


def _out(record: CollectionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "uri": collection_uri(record.id),
        "name": record.name,
        "description": record.description,
        "organization": record.organization,
        "email": record.owner_email,
        "item_count": record.item_count,
        "listed": record.listed,
        "disabled": record.disabled,
        "submitted_at": record.submitted_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _get(store: CollectionStore, collection_id: str) -> CollectionRecord:
    record = store.get(collection_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
    return record


class AdminUpdate(BaseModel):
    listed: bool | None = None
    """Show the collection in GET /collections."""
    disabled: bool | None = None
    """Lock it: hidden from the Impulse API and not editable by its creator."""


@router.get("")
def list_all(store: Store):
    return {"collections": [_out(r) for r in store.list_all()]}


@router.patch("/{collection_id}")
def update(collection_id: str, body: AdminUpdate, store: Store):
    _get(store, collection_id)
    fields = {k: int(v) for k, v in body.model_dump(exclude_none=True).items()}
    store.update(collection_id, **fields)
    return _out(_get(store, collection_id))


@router.delete("/{collection_id}", status_code=204)
def delete(collection_id: str, store: Store):
    _get(store, collection_id)
    store.delete(collection_id)
    return Response(status_code=204)


@router.post("/{collection_id}/key")
def new_key(collection_id: str, store: Store):
    """A new edit key; the creator's old edit link stops working."""
    _get(store, collection_id)
    key, key_hash = new_edit_key()
    store.update(collection_id, edit_key_hash=key_hash)
    return {"edit_key": key}
