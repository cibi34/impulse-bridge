"""Serve the web app (SvelteKit static build in frontend/build).

Prerendered pages (home, legal) are files; every other page is rendered in
the browser from the SPA fallback (200.html). API paths never fall through to
the web app: an unknown /api/… path is a 404, not an HTML page.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.settings import settings

logger = logging.getLogger(__name__)

# Paths owned by the backend; they must never be answered with the web app.
_BACKEND_PREFIXES = ("api/", "admin/api/", "collections", "sources/", "health", "docs", "openapi.json")
# Client-side routes (served from the SPA fallback with status 200).
_APP_ROUTES = ("explore", "my", "signin", "c", "admin")

_IMMUTABLE = "public, max-age=31536000, immutable"
_REVALIDATE = "no-cache"
_STATIC = "public, max-age=86400"


class _ImmutableFiles(StaticFiles):
    """Hashed build assets (/_app/immutable/…) never change."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = _IMMUTABLE
        return response


def _not_built() -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><title>IMPULSE Curator</title>"
        "<p>The web app has not been built. Run <code>npm ci &amp;&amp; npm run build</code> in "
        "<code>frontend/</code>, or use the Docker image.</p>",
        status_code=503,
    )


def mount_frontend(app: FastAPI) -> None:
    root = settings.frontend_dir.resolve()
    immutable = root / "_app" / "immutable"
    if immutable.is_dir():
        app.mount("/_app/immutable", _ImmutableFiles(directory=immutable), name="frontend-immutable")
    else:
        logger.warning("Web app build not found in %s — serving API only", root)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def web_app(path: str):
        if path.startswith(_BACKEND_PREFIXES):
            raise HTTPException(status_code=404, detail="Not Found")
        if not root.is_dir():
            return _not_built()

        for candidate in (path, f"{path}.html", f"{path}/index.html") if path else ("index.html",):
            target = _inside(root, candidate)
            if target is not None:
                cache = _REVALIDATE if target.suffix == ".html" or target.name == "version.json" else _STATIC
                return FileResponse(target, headers={"Cache-Control": cache})

        fallback = root / "200.html"
        if not fallback.is_file():
            return _not_built()
        # Unknown paths still get the app shell (it renders the "not found"
        # page), but with an honest status code.
        first = path.split("/", 1)[0]
        status = 200 if first in _APP_ROUTES and (first != "c" or "/" in path) else 404
        return FileResponse(fallback, status_code=status, headers={"Cache-Control": _REVALIDATE})


def _inside(root: Path, relative: str) -> Path | None:
    target = (root / relative).resolve()
    if target.is_relative_to(root) and target.is_file():
        return target
    return None
