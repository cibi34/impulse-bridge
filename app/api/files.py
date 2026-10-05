"""Serve the local files of fallback sources.

Fallback manifests may reference files by relative path ("demo-cube.glb").
They are served at `/sources/{source_id}/files/<path>`, and the web app API
and curated-collection snapshots turn relative URIs into these absolute URLs
(app/curation/service.py: absolutize). The directory is looked up in the
registry on every request, so a hot-reload that changes or removes a source
takes effect immediately.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app.errors import SourceNotFound
from app.registry import registry

router = APIRouter()


@router.api_route(
    "/sources/{source_id}/files/{file_path:path}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
async def source_file(request: Request, source_id: str, file_path: str):
    try:
        source = registry.get(source_id)
    except SourceNotFound:
        raise HTTPException(status_code=404, detail="Not Found") from None
    files_dir: Path | None = getattr(source, "files_dir", None)
    if files_dir is None:
        raise HTTPException(status_code=404, detail="Not Found")
    root = files_dir.resolve()
    target = (root / file_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    # Revalidate on every use (ETag → 304): without a Cache-Control header,
    # browsers keep a file for days on a guess, and a replaced demo asset
    # would still show up broken.
    response = FileResponse(
        target, stat_result=target.stat(), headers={"Cache-Control": "no-cache"}
    )
    etag = response.headers.get("etag")
    held = [t.strip() for t in request.headers.get("if-none-match", "").split(",")]
    if etag and etag in held:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    return response
