from typing import Annotated

from fastapi import APIRouter, Query

from app.api.responses import impulse_response
from app.registry import registry

router = APIRouter()


@router.get("/collections/{collection_id}/assets")
async def list_assets(
    collection_id: str,
    s: Annotated[str | None, Query(description="Search pattern, '*' wildcards allowed")] = None,
    o: Annotated[int, Query(ge=0, description="Result offset")] = 0,
    c: Annotated[int | None, Query(ge=1, description="Result count")] = None,
):
    source = registry.get(collection_id)
    assets = await source.search(query=s, offset=o, count=c)
    return impulse_response(data=assets)


@router.get("/collections/{collection_id}/asset/{asset_id}")
async def get_asset(collection_id: str, asset_id: str):
    source = registry.get(collection_id)
    asset = await source.get_asset(asset_id)
    return impulse_response(data=asset)
