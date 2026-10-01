from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.responses import impulse_response
from app.curation import get_store
from app.curation.store import CollectionStore
from app.registry import registry

router = APIRouter()


@router.get("/health")
def health(store: Annotated[CollectionStore, Depends(get_store)]):
    return impulse_response(
        data={
            "status": "ok",
            "sources": [meta["id"] for meta in registry.list_meta()],
            "collections": store.count(),
        }
    )
