import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# Load .env into os.environ BEFORE Settings/loader use ${VAR} expansion. The
# YAML loader resolves ${VAR} against os.environ, and pydantic-settings doesn't
# back-fill the process env. This must run at import time, before Settings().
load_dotenv()

from app.admin import api as admin_api  # noqa: E402
from app.admin import collections as admin_collections  # noqa: E402
from app.admin import settings as admin_settings  # noqa: E402
from app.api import auth, collections, files, health, site, sources, web_collections  # noqa: E402
from app.api.responses import CODE_INTERNAL, http_status_for, impulse_response  # noqa: E402
from app.errors import BridgeError  # noqa: E402
from app.loading import load_sources  # noqa: E402
from app.logging_conf import configure_logging  # noqa: E402
from app.registry import registry  # noqa: E402
from app.settings import settings  # noqa: E402
from app.storage import close_storage, open_storage  # noqa: E402

# MIME types Python's mimetypes module doesn't ship with; needed so fallback
# files (app/api/files.py) are served with a content-type Unity can interpret.
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("model/stl", ".stl")
mimetypes.add_type("model/obj", ".obj")

logger = logging.getLogger("impulse_bridge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    logger.info("Impulse Bridge starting (config dir: %s)", settings.config_dir)
    open_storage(settings.database_file)
    await load_sources()
    yield
    logger.info("Impulse Bridge stopping")
    await registry.clear()
    close_storage()


app = FastAPI(
    title="Impulse Bridge",
    description="Adapter bridge between the Impulse 3D platform and external cultural heritage archives",
    version="0.1.0",
    lifespan=lifespan,
)

class ImpulseApiCORSMiddleware(CORSMiddleware):
    """CORS for the Impulse API only.

    The Impulse web frontend runs on another origin and calls /collections…
    cross-origin, possibly with credentials (then Starlette reflects the
    caller's Origin instead of "*"). The web app API (/api/…) and the admin
    are same-origin only: they carry sessions and edit keys, so no other
    site — not even a sibling subdomain — gets CORS access to them.
    Restrict the allowed origins via BRIDGE_CORS_ALLOW_ORIGINS.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith(("/api/", "/admin")):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


app.add_middleware(
    ImpulseApiCORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_web_api(request: Request) -> bool:
    """The web app API (/api/...) uses plain JSON errors; everything else
    answers in the Impulse envelope."""
    return request.url.path.startswith("/api/")


@app.exception_handler(BridgeError)
async def bridge_error_handler(request: Request, exc: BridgeError):
    if _is_web_api(request):
        return JSONResponse(
            status_code=http_status_for(exc.code),
            content={"detail": exc.message, "code": exc.code},
        )
    return impulse_response(data=[], code=exc.code, message=exc.message)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    if _is_web_api(request):
        return JSONResponse(status_code=500, content={"detail": "Internal error", "code": CODE_INTERNAL})
    return impulse_response(data=[], code=CODE_INTERNAL, message="Internal bridge error")


app.include_router(health.router)
app.include_router(collections.router)
app.include_router(site.router)
app.include_router(sources.router)
app.include_router(web_collections.router)
app.include_router(auth.router)
app.include_router(admin_api.router)
app.include_router(admin_collections.router)
app.include_router(admin_settings.router)
app.include_router(files.router)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("static/index.html", media_type="text/html")


@app.get("/admin", include_in_schema=False)
async def admin_index():
    return FileResponse("static/admin.html", media_type="text/html")


_DOCS_DIR = Path("docs")


@app.get("/help", include_in_schema=False)
async def help_index():
    return FileResponse("static/help.html", media_type="text/html")


@app.get("/help/files/{name}", include_in_schema=False)
async def help_file(name: str):
    # Path-sanitize: only allow plain *.md filenames in the docs directory.
    if "/" in name or "\\" in name or ".." in name or not name.endswith(".md"):
        raise HTTPException(status_code=404, detail="not found")
    target = _DOCS_DIR / name
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(target, media_type="text/markdown; charset=utf-8")
