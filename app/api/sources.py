"""Web app API: search the archives (sources) to pick assets from.

Plain JSON (no Impulse envelope); errors are `{"detail": ..., "code": ...}`
with a matching HTTP status (see app/main.py). Relative URIs of local sources
are made absolute so the browser can load them directly.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.adapter.base import search_page
from app.api.params import pagination
from app.curation.service import absolutize
from app.registry import registry

router = APIRouter(prefix="/api/sources", tags=["web"])

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100

_CONTENT_PREFIX = {"image": "image/", "model": "model/"}


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
    s: Annotated[str | None, Query(description="Search pattern")] = None,
    o: Annotated[str | None, Query(description="Offset (upstream items)")] = None,
    c: Annotated[str | None, Query(description=f"Page size, at most {MAX_PAGE_SIZE}")] = None,
    type: Annotated[Literal["image", "model"] | None, Query(description="Content type")] = None,
):
    """One page of search results. `next_offset` is where the next page
    starts (null: no more results). A page can hold fewer than `c` items:
    the source drops upstream items without usable media, and `type` filters
    after fetching."""
    source = registry.get(source_id)
    offset, count = pagination(o, c)
    count = min(count or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    page = await search_page(source, query=s, offset=offset, count=count)
    items = [absolutize(asset, source_id) for asset in page.items]
    if type is not None:
        prefix = _CONTENT_PREFIX[type]
        items = [a for a in items if str(a.get("contentType", "")).startswith(prefix)]
    return {
        "source": source_id,
        "items": items,
        "offset": offset,
        "next_offset": offset + page.upstream_count if page.has_more else None,
    }


@router.get("/{source_id}/assets/{asset_id}")
async def get_asset(source_id: str, asset_id: str):
    source = registry.get(source_id)
    return absolutize(await source.get_asset(asset_id), source_id)
