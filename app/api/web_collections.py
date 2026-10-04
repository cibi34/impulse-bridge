"""Web app API: create and edit curated collections.

Reading is public (only the items Unity gets). Changing a collection needs either
its edit key, sent as `Authorization: Bearer <key>` (handed out once, when
the collection is created, and resettable), or a login session for the email
address the collection was created with (app/api/auth.py).
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.auth import AuthStore, normalize_email, session_cookie_name
from app.curation.service import (
    AssetRef,
    CollectionFull,
    Failure,
    add_items,
    collection_uri,
    create_collection,
    edit_key_matches,
    new_edit_key,
    refresh_items,
    served,
    web_asset,
)
from app.curation.store import CollectionRecord, CollectionStore, ItemRecord, utcnow
from app.licensing import classify
from app.mail import MailError, build_message, mail_available, send
from app.ratelimit import create_limit, write_limit
from app.settings import settings
from app.site_settings import SiteSettingsStore
from app.storage import get_auth_store, get_licence_conditions, get_site_store, get_store

router = APIRouter(prefix="/api/collections", tags=["web"])

Store = Annotated[CollectionStore, Depends(get_store)]
Auth = Annotated[AuthStore, Depends(get_auth_store)]
Site = Annotated[SiteSettingsStore, Depends(get_site_store)]
Accepted = Annotated[frozenset[str], Depends(get_licence_conditions)]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PREVIEWS_PER_COLLECTION = 4
_MAX_SUMMARY_IDS = 100
_MAX_ITEMS_PER_REQUEST = 500
"""Upper bound for one request body; the collection limit itself
(BRIDGE_MAX_ASSETS_PER_COLLECTION) is checked when adding."""


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
    items: list[AssetRefIn] = Field(default_factory=list, max_length=_MAX_ITEMS_PER_REQUEST)

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
    items: list[AssetRefIn] = Field(min_length=1, max_length=_MAX_ITEMS_PER_REQUEST)


class ItemUpdate(BaseModel):
    published: bool


class OrderUpdate(BaseModel):
    asset_ids: list[str]


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

def _item_out(item: ItemRecord, accepted: frozenset[str]) -> dict[str, Any]:
    return {
        "asset_id": item.asset_id,
        "source": item.source_id,
        "source_asset_id": item.source_asset_id,
        "published": item.published,
        "licence": classify(item.asset.get("rights")).as_dict(accepted),
        "asset": web_asset(item),
        "added_at": item.added_at,
        "refreshed_at": item.refreshed_at,
    }


def _failure_out(failure: Failure) -> dict[str, str]:
    return {"source": failure.source, "asset_id": failure.asset_id, "reason": failure.reason}


def _collection_out(
    record: CollectionRecord, items: list[ItemRecord], accepted: frozenset[str], *, editor: bool
) -> dict[str, Any]:
    """The editor's view has every item; the public view what Unity gets."""
    if not editor:
        items = [i for i in items if served(i, accepted)]
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
        "items": [_item_out(i, accepted) for i in items],
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
    """The collection, also by a former id (after an admin renamed it): the
    response carries the current id, and the web app updates its links."""
    record = store.resolve(collection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return record


def session_email(request: Request, auth: AuthStore) -> str | None:
    session_id = request.cookies.get(session_cookie_name())
    return auth.session_email(session_id) if session_id else None


def _access(
    record: CollectionRecord, request: Request, authorization: str | None, auth: AuthStore
) -> str | None:
    """How the request may edit the collection: "key", "session" or None."""
    key = _bearer(authorization)
    if key is not None and edit_key_matches(key, record.edit_key_hash):
        return "key"
    email = session_email(request, auth)
    if email is not None and record.owner_email and normalize_email(record.owner_email) == email:
        return "session"
    return None


def _public_origin() -> str:
    scheme, _, rest = settings.public_base_url.partition("://")
    return f"{scheme}://{rest.split('/', 1)[0]}"


def editable(
    collection_id: str,
    request: Request,
    store: Store,
    auth: Auth,
    authorization: Annotated[str | None, Header()] = None,
) -> CollectionRecord:
    """The collection, if the request may edit it and it isn't locked."""
    record = _visible(store, collection_id)
    access = _access(record, request, authorization, auth)
    if access is None:
        if _bearer(authorization) is None and session_email(request, auth) is None:
            raise HTTPException(
                status_code=401,
                detail="This action needs the collection's edit link",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(status_code=403, detail="You can't edit this collection")
    if access == "session" and request.method not in ("GET", "HEAD"):
        # Defense in depth next to the SameSite cookie: browsers send Origin
        # with every cross-origin write; refuse writes from other sites.
        origin = request.headers.get("origin")
        if origin is not None and origin != _public_origin():
            raise HTTPException(status_code=403, detail="Cross-site request refused")
    if record.disabled:
        raise HTTPException(status_code=403, detail="This collection was locked by an administrator")
    return record


Editable = Annotated[CollectionRecord, Depends(editable)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201, dependencies=[Depends(create_limit)])
async def create(body: CollectionCreate, store: Store, accepted: Accepted):
    refs = [AssetRef(i.source, i.asset_id) for i in body.items]
    try:
        record, key, failures = await create_collection(
            store,
            name=body.name,
            description=body.description,
            organization=body.organization,
            owner_email=body.email,
            refs=refs,
            accepted=accepted,
        )
    except CollectionFull:
        raise _full_error() from None
    items = await run_in_threadpool(store.items, record.id)
    return {
        "collection": _collection_out(record, items, accepted, editor=True),
        "edit_key": key,
        "failed": [_failure_out(f) for f in failures],
    }


def summaries_out(store: CollectionStore, records: list[CollectionRecord]) -> dict[str, Any]:
    previews = store.preview_items([r.id for r in records], _PREVIEWS_PER_COLLECTION)
    return {
        "collections": [
            {
                "id": r.id,
                "uri": collection_uri(r.id),
                "name": r.name,
                "description": r.description,
                "item_count": r.item_count,
                "updated_at": r.updated_at,
                "submitted_at": r.submitted_at,
                "previews": [i.asset.get("previewURI") for i in previews[r.id]],
            }
            for r in records
        ]
    }


@router.get("")
def summaries(
    store: Store,
    ids: Annotated[str, Query(description="Comma-separated collection ids")] = "",
):
    """Short public overviews of several collections (the browser's "My
    collections" list). Unknown and locked ids are left out. So the browser
    can tidy up what it stored: `moved` maps former ids to current ones,
    `missing` lists ids that do not exist (any more) — locked ones do."""
    wanted = [i for i in dict.fromkeys(ids.split(",")) if i][:_MAX_SUMMARY_IDS]
    found = {r.id: r for r in store.get_many(wanted)}
    moved: dict[str, str] = {}
    missing: list[str] = []
    for requested in wanted:
        if requested in found:
            continue
        record = store.resolve(requested)
        if record is None:
            missing.append(requested)
        else:
            found.setdefault(record.id, record)
            moved[requested] = record.id
    records = [r for r in found.values() if not r.disabled]
    return {**summaries_out(store, records), "moved": moved, "missing": missing}


@router.get("/{collection_id}")
def read(
    collection_id: str,
    request: Request,
    store: Store,
    auth: Auth,
    accepted: Accepted,
    authorization: Annotated[str | None, Header()] = None,
):
    """Public view (what Unity gets), or the editor's view (all items, plus
    email and lock state) for a request that may edit it."""
    record = _visible(store, collection_id)
    editor = _access(record, request, authorization, auth) is not None
    if record.disabled and not editor:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = store.items(record.id, published_only=not editor)
    return _collection_out(record, items, accepted, editor=editor)


@router.patch("/{collection_id}", dependencies=[Depends(write_limit)])
def update(body: CollectionUpdate, record: Editable, store: Store, accepted: Accepted):
    fields: dict[str, Any] = {}
    for name in ("name", "description", "organization"):
        value = getattr(body, name)
        if value is not None:
            fields[name] = value
    if "email" in body.model_fields_set:
        fields["owner_email"] = body.email
    store.update(record.id, **fields)
    return _collection_out(store.get(record.id), store.items(record.id), accepted, editor=True)  # type: ignore[arg-type]


@router.delete("/{collection_id}", status_code=204, dependencies=[Depends(write_limit)])
def delete(record: Editable, store: Store):
    store.delete(record.id)
    return Response(status_code=204)


@router.post("/{collection_id}/items", dependencies=[Depends(write_limit)])
async def add(body: ItemsAdd, record: Editable, store: Store, accepted: Accepted):
    try:
        added, failures = await add_items(
            store, record, [AssetRef(i.source, i.asset_id) for i in body.items], accepted
        )
    except CollectionFull:
        raise _full_error() from None
    return {
        "added": [_item_out(i, accepted) for i in added],
        "failed": [_failure_out(f) for f in failures],
    }


@router.patch("/{collection_id}/items/{asset_id}", dependencies=[Depends(write_limit)])
def update_item(
    asset_id: str, body: ItemUpdate, record: Editable, store: Store, accepted: Accepted
):
    if not store.set_published(record.id, asset_id, body.published):
        raise HTTPException(status_code=404, detail="Asset not found in this collection")
    return _item_out(store.item(record.id, asset_id), accepted)  # type: ignore[arg-type]


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


@router.post("/{collection_id}/email-link", status_code=202, dependencies=[Depends(write_limit)])
async def email_edit_link(
    record: Editable,
    site: Site,
    authorization: Annotated[str | None, Header()] = None,
):
    """Send the edit link to the collection's email address."""
    key = _bearer(authorization)
    if key is None or not edit_key_matches(key, record.edit_key_hash):
        raise HTTPException(status_code=403, detail="Sending the edit link needs the edit link itself")
    if not record.owner_email:
        raise HTTPException(status_code=422, detail="Add an email address to the collection first")
    site_settings = await run_in_threadpool(site.load)
    if not mail_available(site_settings):
        raise HTTPException(status_code=503, detail="Email is not available on this server")
    link = f"{settings.public_base_url.rstrip('/')}/c/{record.id}/edit#key={key}"
    message = build_message(
        site_settings,
        record.owner_email,
        f"Edit link for “{record.name}”",
        [
            f"Here is the edit link for your IMPULSE Curator collection “{record.name}”.",
            "Anyone with this link can change the collection, so keep it private.",
        ],
        link=("Open the collection", link),
    )
    try:
        await send(site_settings, message)
    except MailError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    return {"sent_to": record.owner_email}


@router.post("/{collection_id}/key", dependencies=[Depends(write_limit)])
def reset_key(record: Editable, store: Store):
    """Replace the edit key (e.g. after sharing the edit link by mistake).
    The old link stops working immediately."""
    key, key_hash = new_edit_key()
    store.update(record.id, edit_key_hash=key_hash)
    return {"edit_key": key}
