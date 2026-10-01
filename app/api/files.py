"""Serve the local files of fallback sources under their collection URI.

Relative assetURIs/previewURIs (e.g. "demo-cube.glb") resolve against the
collection URI, so `/collections/bridge-demo/demo-cube.glb` must return the
file next to the manifest. The directory is looked up in the registry on every
request, so a hot-reload that changes or removes a source takes effect
immediately (a Starlette mount per source would outlive the reload).

This router must be included after the asset routes: its catch-all path would
otherwise shadow `/collections/{id}/assets` and `/collections/{id}/asset/{aid}`.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.registry import registry

router = APIRouter()


@router.api_route(
    "/collections/{collection_id}/{file_path:path}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
async def collection_file(collection_id: str, file_path: str):
    source = registry.get(collection_id)
    files_dir: Path | None = getattr(source, "files_dir", None)
    if files_dir is None:
        raise HTTPException(status_code=404, detail="Not Found")
    root = files_dir.resolve()
    target = (root / file_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(target)
