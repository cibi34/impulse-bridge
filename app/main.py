import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Load .env into os.environ BEFORE Settings/loader use ${VAR} expansion. The
# YAML loader resolves ${VAR} against os.environ, and pydantic-settings doesn't
# back-fill the process env. This must run at import time, before Settings().
load_dotenv()

from app.adapter.factory import build_source  # noqa: E402
from app.admin import api as admin_api  # noqa: E402
from app.api import assets, collections, health  # noqa: E402
from app.api.responses import CODE_INTERNAL, impulse_response  # noqa: E402
from app.config.loader import load_all  # noqa: E402
from app.errors import BridgeError  # noqa: E402
from app.logging_conf import configure_logging  # noqa: E402
from app.registry import registry  # noqa: E402
from app.settings import settings  # noqa: E402

# MIME types Python's mimetypes module doesn't ship with; needed so StaticFiles
# serves 3D models with a content-type Unity can interpret.
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("model/stl", ".stl")
mimetypes.add_type("model/obj", ".obj")

logger = logging.getLogger("impulse_bridge")


async def _load_sources(app: FastAPI) -> None:
    await registry.clear()
    for path, cfg in load_all(settings.config_dir):
        try:
            source = build_source(cfg, path, app)
        except Exception as e:  # noqa: BLE001
            registry._load_errors.append((path.name, str(e)))
            logger.exception("Failed to build source from %s", path.name)
            continue
        meta = source.collection_meta
        meta.setdefault(
            "uri",
            f"{settings.public_base_url.rstrip('/')}/collections/{meta['id']}",
        )
        try:
            registry.register(source, source_file=path)
        except ValueError as e:
            registry._load_errors.append((path.name, str(e)))
            logger.error("Cannot register source from %s: %s", path.name, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    logger.info("Impulse Bridge starting on %s:%s", settings.host, settings.port)
    await _load_sources(app)
    logger.info("Registered %d source(s)", len(registry.list_collections()))
    yield
    logger.info("Impulse Bridge stopping")
    await registry.clear()


app = FastAPI(
    title="Impulse Bridge",
    description="Adapter bridge between the Impulse 3D platform and external cultural heritage archives",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — the Impulse web frontend is served from a different origin than the
# bridge, so browser fetch/XHR calls to the API are cross-origin. With
# allow_credentials=True Starlette reflects the caller's Origin back instead of
# a literal "*" (browsers reject "*" together with credentials); this is valid
# for credentialed and non-credentialed requests alike. Restrict the allowed
# origins in production via BRIDGE_CORS_ALLOW_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BridgeError)
async def bridge_error_handler(_request: Request, exc: BridgeError):
    return impulse_response(data=[], code=exc.code, message=exc.message)


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return impulse_response(data=[], code=CODE_INTERNAL, message="Internal bridge error")


app.include_router(health.router)
app.include_router(collections.router)
app.include_router(assets.router)
app.include_router(admin_api.router)


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
