"""Admin API for curated collections: overview, listing in /collections,
locking, deleting, issuing a new edit key (e.g. for a creator who lost the
link) and changing a collection's id. Protected like the rest of /admin
(basic auth at the proxy)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.curation.service import collection_id_problem, collection_uri, new_edit_key
from app.curation.store import CollectionRecord, CollectionStore, IdTaken
from app.storage import get_store

router = APIRouter(prefix="/admin/api/collections", tags=["admin"])
logger = logging.getLogger(__name__)

Store = Annotated[CollectionStore, Depends(get_store)]


def _out(record: CollectionRecord, aliases: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "id": record.id,
        "former_ids": aliases.get(record.id, []),
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
    aliases = store.aliases()
    return {"collections": [_out(r, aliases) for r in store.list_all()]}


@router.patch("/{collection_id}")
def update(collection_id: str, body: AdminUpdate, store: Store):
    _get(store, collection_id)
    fields = {k: int(v) for k, v in body.model_dump(exclude_none=True).items()}
    store.update(collection_id, **fields)
    return _out(_get(store, collection_id), store.aliases())


@router.delete("/{collection_id}", status_code=204)
def delete(collection_id: str, store: Store):
    _get(store, collection_id)
    store.delete(collection_id)
    return Response(status_code=204)


class RenameBody(BaseModel):
    new_id: str = Field(max_length=200)
    confirm: str = Field(max_length=200)
    """The current id, typed again: guards against renaming the wrong
    collection, or one by accident."""


@router.post("/{collection_id}/rename")
def rename(collection_id: str, body: RenameBody, store: Store):
    """Change a collection's id — and with it its URI, which is how Impulse
    and Unity load it. The old id stays as an alias, so old URIs, edit links
    and browsers keep finding the collection. Items, edit key, flags and the
    creation date stay."""
    record = _get(store, collection_id)
    if body.confirm.strip() != record.id:
        raise HTTPException(status_code=422, detail="Type the current ID exactly to confirm.")
    new_id = body.new_id.strip()
    if new_id == record.id:
        raise HTTPException(status_code=422, detail="That is already the collection's ID.")
    problem = collection_id_problem(new_id)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    try:
        store.rename(record.id, new_id)
    except KeyError:  # deleted in the meantime
        raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found") from None
    except IdTaken as taken:
        detail = (
            f"“{new_id}” is a former ID of “{taken.owner.name}”; its old links lead there."
            if taken.former
            else f"The ID “{new_id}” is already used by “{taken.owner.name}”."
        )
        raise HTTPException(status_code=409, detail=detail) from None
    logger.info("Collection %r renamed to %r by an admin", record.id, new_id)
    return {**_out(_get(store, new_id), store.aliases()), "previous_id": record.id}


@router.post("/{collection_id}/key")
def new_key(collection_id: str, store: Store):
    """A new edit key; the creator's old edit link stops working."""
    _get(store, collection_id)
    key, key_hash = new_edit_key()
    store.update(collection_id, edit_key_hash=key_hash)
    return {"edit_key": key}
