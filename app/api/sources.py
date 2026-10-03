"""Web app API: search the archives (sources) to pick assets from.

Plain JSON (no Impulse envelope); errors are `{"detail": ..., "code": ...}`
with a matching HTTP status (see app/main.py). Relative URIs of local sources
are made absolute so the browser can load them directly.

Every asset carries its `licence` (app/licensing.py). Search results leave
out assets whose licence IMPULSE doesn't accept and say how many (`hidden`).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.adapter.base import search_page
from app.api.params import pagination
from app.curation.service import absolutize
from app.licensing import LicenceTier, classify
from app.registry import registry
from app.storage import get_licence_conditions

router = APIRouter(prefix="/api/sources", tags=["web"])

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100

_CONTENT_PREFIX = {"image": "image/", "model": "model/"}

Accepted = Annotated[frozenset[str], Depends(get_licence_conditions)]


def with_licence(asset: dict, accepted: frozenset[str]) -> dict:
    return {**asset, "licence": classify(asset.get("rights")).as_dict(accepted)}


def _source_info(meta: dict) -> dict:
    return {
        "id": meta["id"],
        "name": meta.get("name"),
        "description": meta.get("description"),
        "organization": meta.get("organization"),
    }


@router.get("")
async def list_sources():
    return {"sources": [_source_info(meta) for meta in registry.list_meta()]}


@router.get("/{source_id}/assets")
async def search_assets(
    source_id: str,
    accepted: Accepted,
    s: Annotated[str | None, Query(description="Search pattern")] = None,
    o: Annotated[str | None, Query(description="Offset (upstream items)")] = None,
    c: Annotated[str | None, Query(description=f"Page size, at most {MAX_PAGE_SIZE}")] = None,
    type: Annotated[Literal["image", "model"] | None, Query(description="Content type")] = None,
    licence: Annotated[
        LicenceTier | None,
        Query(description="Only licences without conditions (free) or with attribution only (by)"),
    ] = None,
):
    """One page of search results. `next_offset` is where the next page
    starts (null: no more results). A page can hold fewer than `c` items:
    the source drops upstream items without usable media, and the filters
    apply after fetching. `hidden` counts the assets left out because
    IMPULSE doesn't accept their licence."""
    source = registry.get(source_id)
    offset, count = pagination(o, c)
    count = min(count or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    page = await search_page(source, query=s, offset=offset, count=count)
    items, hidden = [], 0
    prefix = _CONTENT_PREFIX[type] if type is not None else ""
    for asset in page.items:
        found = classify(asset.get("rights"))
        if not found.allowed(accepted):
            hidden += 1
        elif found.within(licence) and str(asset.get("contentType", "")).startswith(prefix):
            items.append(with_licence(absolutize(asset, source_id), accepted))
    return {
        "source": source_id,
        "items": items,
        "hidden": hidden,
        "offset": offset,
        "next_offset": offset + page.upstream_count if page.has_more else None,
    }


@router.get("/{source_id}/assets/{asset_id}")
async def get_asset(source_id: str, asset_id: str, accepted: Accepted):
    source = registry.get(source_id)
    return with_licence(absolutize(await source.get_asset(asset_id), source_id), accepted)
