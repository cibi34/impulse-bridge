from typing import Annotated

from fastapi import APIRouter, Query

from app.api.responses import impulse_response
from app.registry import registry

router = APIRouter()


def _pagination(o: str | None, c: str | None) -> tuple[int, int | None]:
    """Offset and count per the Impulse spec: both are optional positive
    integers, and "in case of illegal values the entire result set shall be
    returned" — so anything unparsable or out of range means no pagination."""
    try:
        offset = int(o) if o else 0
        count = int(c) if c else None
    except ValueError:
        return 0, None
    if offset < 0 or (count is not None and count < 1):
        return 0, None
    return offset, count


@router.get("/collections/{collection_id}/assets")
async def list_assets(
    collection_id: str,
    s: Annotated[str | None, Query(description="Search pattern, '*' wildcards allowed")] = None,
    o: Annotated[str | None, Query(description="Result offset (integer >= 0)")] = None,
    c: Annotated[str | None, Query(description="Result count (integer >= 1)")] = None,
):
    source = registry.get(collection_id)
    offset, count = _pagination(o, c)
    assets = await source.search(query=s, offset=offset, count=count)
    return impulse_response(data=assets)


@router.get("/collections/{collection_id}/asset/{asset_id}")
async def get_asset(collection_id: str, asset_id: str):
    source = registry.get(collection_id)
    asset = await source.get_asset(asset_id)
    return impulse_response(data=asset)
