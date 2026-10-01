"""Web app API: create and edit curated collections.

Reading is public (only published items). Changing a collection needs its
edit key, sent as `Authorization: Bearer <key>`; the key is handed out once,
when the collection is created (or reset by its editor or an admin).
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.curation import get_store
from app.curation.service import (
    AssetRef,
    CollectionFull,
    Failure,
    add_items,
    collection_uri,
    create_collection,
    edit_key_matches,
    impulse_asset,
    new_edit_key,
    refresh_items,
)
from app.curation.store import CollectionRecord, CollectionStore, ItemRecord, utcnow
from app.ratelimit import create_limit, write_limit
from app.settings import settings

router = APIRouter(prefix="/api/collections", tags=["web"])

Store = Annotated[CollectionStore, Depends(get_store)]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PREVIEWS_PER_COLLECTION = 4
_MAX_SUMMARY_IDS = 100


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class AssetRefIn(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    asset_id: str = Field(min_length=1, max_length=500)


def _clean_email(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 254 or not _EMAIL.match(value):
        raise ValueError("Enter a valid email address")
    return value


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    organization: str = Field("", max_length=120)
    email: str | None = None
    items: list[AssetRefIn] = Field(default_factory=list, max_length=500)

    @field_validator("name", "description", "organization")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter a name")
        return value

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        return _clean_email(value)


class CollectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    organization: str | None = Field(None, max_length=120)
    email: str | None = None
    """An empty string removes the email address."""

    @field_validator("name", "description", "organization")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("Enter a name")
        return value

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        return _clean_email(value)


class ItemsAdd(BaseModel):
    items: list[AssetRefIn] = Field(min_length=1, max_length=200)


class ItemUpdate(BaseModel):
    published: bool


class OrderUpdate(BaseModel):
    asset_ids: list[str]


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

def _item_out(item: ItemRecord) -> dict[str, Any]:
    return {
        "asset_id": item.asset_id,
        "source": item.source_id,
        "source_asset_id": item.source_asset_id,
        "published": item.published,
        "asset": impulse_asset(item),
        "added_at": item.added_at,
        "refreshed_at": item.refreshed_at,
    }


def _failure_out(failure: Failure) -> dict[str, str]:
    return {"source": failure.source, "asset_id": failure.asset_id, "reason": failure.reason}


def _collection_out(
    record: CollectionRecord, items: list[ItemRecord], *, editor: bool
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": record.id,
        "uri": collection_uri(record.id),
        "name": record.name,
        "description": record.description,
        "organization": record.organization,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "submitted_at": record.submitted_at,
        "listed": record.listed,
        "item_count": record.item_count,
        "items": [_item_out(i) for i in items],
        "can_edit": editor,
    }
    if editor:
        out["email"] = record.owner_email
        out["locked"] = record.disabled
    return out


def _full_error(detail: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=detail or f"A collection can hold at most {settings.max_assets_per_collection} assets",
    )


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------

def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization[:7].lower() == "bearer ":
        return authorization[7:].strip() or None
    return None


def _visible(store: CollectionStore, collection_id: str) -> CollectionRecord:
    record = store.get(collection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return record


def _is_editor(record: CollectionRecord, authorization: str | None) -> bool:
    key = _bearer(authorization)
    return key is not None and edit_key_matches(key, record.edit_key_hash)


def editable(
    collection_id: str,
    store: Store,
    authorization: Annotated[str | None, Header()] = None,
) -> CollectionRecord:
    """The collection, if the request carries its edit key and it isn't locked."""
    record = _visible(store, collection_id)
    if _bearer(authorization) is None:
        raise HTTPException(
            status_code=401,
            detail="This action needs the collection's edit link",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not _is_editor(record, authorization):
        raise HTTPException(status_code=403, detail="The edit link is not valid for this collection")
    if record.disabled:
        raise HTTPException(status_code=403, detail="This collection was locked by an administrator")
    return record


Editable = Annotated[CollectionRecord, Depends(editable)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201, dependencies=[Depends(create_limit)])
async def create(body: CollectionCreate, store: Store):
    refs = [AssetRef(i.source, i.asset_id) for i in body.items]
    try:
        record, key, failures = await create_collection(
            store,
            name=body.name,
            description=body.description,
            organization=body.organization,
            owner_email=body.email,
            refs=refs,
        )
    except CollectionFull:
        raise _full_error() from None
    items = await run_in_threadpool(store.items, record.id)
    return {
        "collection": _collection_out(record, items, editor=True),
        "edit_key": key,
        "failed": [_failure_out(f) for f in failures],
    }


@router.get("")
def summaries(
    store: Store,
    ids: Annotated[str, Query(description="Comma-separated collection ids")] = "",
):
    """Short public overviews of several collections (the browser's "My
    collections" list). Unknown or locked ids are left out."""
    wanted = [i for i in dict.fromkeys(ids.split(",")) if i][:_MAX_SUMMARY_IDS]
    records = [r for r in store.get_many(wanted) if not r.disabled]
    previews = store.preview_items([r.id for r in records], _PREVIEWS_PER_COLLECTION)
    return {
        "collections": [
            {
                "id": r.id,
                "uri": collection_uri(r.id),
                "name": r.name,
                "item_count": r.item_count,
                "updated_at": r.updated_at,
                "submitted_at": r.submitted_at,
                "previews": [i.asset.get("previewURI") for i in previews[r.id]],
            }
            for r in records
        ]
    }


@router.get("/{collection_id}")
def read(
    collection_id: str,
    store: Store,
    authorization: Annotated[str | None, Header()] = None,
):
    """Public view (published items only), or the editor's view (all items,
    plus email and lock state) when the edit key is sent."""
    record = _visible(store, collection_id)
    editor = _is_editor(record, authorization)
    if record.disabled and not editor:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = store.items(collection_id, published_only=not editor)
    return _collection_out(record, items, editor=editor)


@router.patch("/{collection_id}", dependencies=[Depends(write_limit)])
def update(body: CollectionUpdate, record: Editable, store: Store):
    fields: dict[str, Any] = {}
    for name in ("name", "description", "organization"):
        value = getattr(body, name)
        if value is not None:
            fields[name] = value
    if "email" in body.model_fields_set:
        fields["owner_email"] = body.email
    store.update(record.id, **fields)
    return _collection_out(store.get(record.id), store.items(record.id), editor=True)  # type: ignore[arg-type]


@router.delete("/{collection_id}", status_code=204, dependencies=[Depends(write_limit)])
def delete(record: Editable, store: Store):
    store.delete(record.id)
    return Response(status_code=204)


@router.post("/{collection_id}/items", dependencies=[Depends(write_limit)])
async def add(body: ItemsAdd, record: Editable, store: Store):
    try:
        added, failures = await add_items(
            store, record, [AssetRef(i.source, i.asset_id) for i in body.items]
        )
    except CollectionFull:
        raise _full_error() from None
    return {"added": [_item_out(i) for i in added], "failed": [_failure_out(f) for f in failures]}


@router.patch("/{collection_id}/items/{asset_id}", dependencies=[Depends(write_limit)])
def update_item(asset_id: str, body: ItemUpdate, record: Editable, store: Store):
    if not store.set_published(record.id, asset_id, body.published):
        raise HTTPException(status_code=404, detail="Asset not found in this collection")
    return _item_out(store.item(record.id, asset_id))  # type: ignore[arg-type]


@router.delete("/{collection_id}/items/{asset_id}", status_code=204, dependencies=[Depends(write_limit)])
def remove_item(asset_id: str, record: Editable, store: Store):
    if not store.remove_item(record.id, asset_id):
        raise HTTPException(status_code=404, detail="Asset not found in this collection")
    return Response(status_code=204)


@router.put("/{collection_id}/order", dependencies=[Depends(write_limit)])
def reorder(body: OrderUpdate, record: Editable, store: Store):
    if len(body.asset_ids) != len(set(body.asset_ids)) or set(body.asset_ids) != store.asset_ids(record.id):
        raise HTTPException(status_code=422, detail="asset_ids must list every asset of the collection once")
    store.reorder(record.id, body.asset_ids)
    return {"asset_ids": [i.asset_id for i in store.items(record.id)]}


@router.post("/{collection_id}/refresh", dependencies=[Depends(write_limit)])
async def refresh(record: Editable, store: Store):
    """Update every asset's snapshot from its source."""
    refreshed, failures = await refresh_items(store, record)
    return {"refreshed": refreshed, "failed": [_failure_out(f) for f in failures]}


@router.post("/{collection_id}/submitted", dependencies=[Depends(write_limit)])
def mark_submitted(record: Editable, store: Store):
    """Record that the editor sent the collection to the Impulse team. The
    email itself is sent from the editor's mail program."""
    store.update(record.id, submitted_at=utcnow())
    return {"submitted_at": store.get(record.id).submitted_at}  # type: ignore[union-attr]


@router.post("/{collection_id}/key", dependencies=[Depends(write_limit)])
def reset_key(record: Editable, store: Store):
    """Replace the edit key (e.g. after sharing the edit link by mistake).
    The old link stops working immediately."""
    key, key_hash = new_edit_key()
    store.update(record.id, edit_key_hash=key_hash)
    return {"edit_key": key}
