from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.responses import impulse_response
from app.curation.store import CollectionStore
from app.registry import registry
from app.storage import get_store

router = APIRouter()


@router.api_route("/health", methods=["GET", "HEAD"])
def health(store: Annotated[CollectionStore, Depends(get_store)]):
    return impulse_response(
        data={
            "status": "ok",
            "sources": [meta["id"] for meta in registry.list_meta()],
            "collections": store.count(),
        }
    )
