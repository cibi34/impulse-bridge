from fastapi import APIRouter

from app.api.responses import impulse_response
from app.registry import registry

router = APIRouter()


@router.get("/health")
async def health():
    return impulse_response(
        data={
            "status": "ok",
            "sources": [c["id"] for c in registry.list_collections()],
        }
    )
