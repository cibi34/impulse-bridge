from fastapi import APIRouter

from app.api.responses import impulse_response
from app.registry import registry

router = APIRouter()


@router.get("/collections")
async def list_collections():
    return impulse_response(data=registry.list_collections())


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str):
    source = registry.get(collection_id)
    return impulse_response(data=source.collection_meta)
