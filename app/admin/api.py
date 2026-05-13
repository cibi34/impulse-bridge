"""Admin API for inspecting, editing, testing and hot-reloading sources.

These endpoints are not part of the Impulse Collections-and-Assets protocol —
they exist purely so the admin browser UI can manage YAML configs at runtime
without restarting the server. They use plain JSON responses (no `{code,
message, data}` envelope) since their consumer is the bundled admin UI."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from app.adapter.factory import build_source
from app.config.schema import SourceConfig
from app.config.loader import _expand_env
from app.registry import registry
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api", tags=["admin"])


_SLUG = re.compile(r"[^a-z0-9-]+")


def _filename_from_id(collection_id: str) -> str:
    """Map a collection id to a stable filename inside configs/sources/."""
    safe = _SLUG.sub("-", collection_id.lower()).strip("-") or "source"
    return f"{safe}.yaml"


def _list_yaml_files() -> list[Path]:
    if not settings.config_dir.exists():
        return []
    return sorted(
        p for p in settings.config_dir.iterdir()
        if p.suffix in {".yaml", ".yml"} and p.is_file()
    )


def _load_raw_yaml(path: Path) -> tuple[str, dict | None, str | None]:
    """Return (raw_text, parsed_dict_or_None, error_message_or_None)."""
    text = path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(text)
        if parsed is not None and not isinstance(parsed, dict):
            return text, None, "Top-level YAML must be a mapping"
        return text, parsed, None
    except yaml.YAMLError as e:
        return text, None, f"YAML parse error: {e}"


# --------------------------------------------------------------------------
# Listing & inspection
# --------------------------------------------------------------------------

@router.get("/sources")
async def list_sources() -> dict:
    """List all source configs found on disk, with their loaded status."""
    out: list[dict] = []
    loaded_ids = {c["id"] for c in registry.list_collections()}
    error_by_file = dict(registry.errors())

    for path in _list_yaml_files():
        text, parsed, parse_err = _load_raw_yaml(path)
        info: dict[str, Any] = {
            "filename": path.name,
            "id": None,
            "name": None,
            "kind": None,
            "base_url": None,
            "loaded": False,
            "error": parse_err or error_by_file.get(path.name),
        }
        if parsed:
            collection = parsed.get("collection") or {}
            adapter = parsed.get("adapter") or {}
            info["id"] = collection.get("id")
            info["name"] = collection.get("name")
            info["kind"] = adapter.get("kind")
            info["base_url"] = adapter.get("base_url") or adapter.get("manifest_path")
            info["loaded"] = info["id"] in loaded_ids
        out.append(info)

    return {
        "sources": out,
        "loaded_count": len(loaded_ids),
        "load_errors": [{"file": f, "error": e} for f, e in registry.errors()],
    }


@router.get("/sources/{collection_id}")
async def get_source(collection_id: str) -> dict:
    """Return the full YAML (text + parsed) for one source, plus validation."""
    path = _find_file_by_id(collection_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Source '{collection_id}' not found")
    text, parsed, parse_err = _load_raw_yaml(path)
    validation = _validate_cfg(parsed)
    return {
        "filename": path.name,
        "yaml": text,
        "parsed": parsed,
        "valid": validation["valid"],
        "errors": validation["errors"],
        "loaded": collection_id in {c["id"] for c in registry.list_collections()},
    }


# --------------------------------------------------------------------------
# Save / create
# --------------------------------------------------------------------------

class SaveBody(BaseModel):
    yaml: str
    """The full YAML text to write to disk."""
    filename: str | None = None
    """If provided, write to this filename. Otherwise derive from collection.id."""


@router.put("/sources/{collection_id}")
async def upsert_source(collection_id: str, body: SaveBody, request: Request) -> dict:
    """Create-or-update a source. The URL collection_id matches the parsed
    YAML's collection.id (the YAML is authoritative); if they differ, the
    parsed id wins and the file may be renamed accordingly."""
    parsed = _parse_or_400(body.yaml)
    validation = _validate_cfg(parsed)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail={"errors": validation["errors"], "parsed": parsed},
        )

    new_id = parsed["collection"]["id"]
    existing = _find_file_by_id(collection_id)
    target_filename = (
        body.filename
        or (existing.name if existing else _filename_from_id(new_id))
    )
    target = settings.config_dir / target_filename
    target.parent.mkdir(parents=True, exist_ok=True)

    # If renaming the source (id changed) and an old file exists, delete it
    # after writing the new one — but only if the new and old paths differ.
    target.write_text(body.yaml, encoding="utf-8")
    if existing and existing.resolve() != target.resolve():
        existing.unlink(missing_ok=True)

    await _reload(request.app)
    return await get_source(new_id)


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------

@router.delete("/sources/{collection_id}")
async def delete_source(collection_id: str, request: Request) -> dict:
    path = _find_file_by_id(collection_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Source '{collection_id}' not found")
    path.unlink()
    await _reload(request.app)
    return {"deleted": collection_id, "filename": path.name}


# --------------------------------------------------------------------------
# Live test (does not save)
# --------------------------------------------------------------------------

class TestBody(BaseModel):
    yaml: str
    query: str | None = None
    count: int = 5


@router.post("/test")
async def test_source(body: TestBody) -> dict:
    """Build an ephemeral Source from the submitted YAML, run a search, and
    return both the raw upstream JSON and the transformed Impulse assets."""
    parsed = _parse_or_400(body.yaml)
    validation = _validate_cfg(parsed)
    if not validation["valid"]:
        return {
            "valid": False,
            "errors": validation["errors"],
            "transformed": [],
            "raw_upstream": None,
            "upstream_url": None,
        }
    cfg = SourceConfig.model_validate(_expand_env(parsed))

    # Build the source without mounting static files (would conflict with the
    # live registry, and isn't needed to test search()).
    try:
        source = build_source(cfg, settings.config_dir / "__test__.yaml", _NoMountApp())
    except Exception as e:  # noqa: BLE001
        return {
            "valid": True,
            "errors": [{"loc": ["adapter"], "msg": str(e)}],
            "transformed": [],
            "raw_upstream": None,
            "upstream_url": None,
        }

    try:
        transformed = await source.search(query=body.query, offset=0, count=body.count)
    except Exception as e:  # noqa: BLE001
        msg = getattr(e, "message", None) or str(e)
        return {
            "valid": True,
            "errors": [{"loc": ["upstream"], "msg": msg}],
            "transformed": [],
            "raw_upstream": getattr(source, "last_raw_response", None),
            "upstream_url": getattr(source, "last_upstream_url", None),
        }
    finally:
        closer = getattr(source, "aclose", None)
        if closer is not None:
            try:
                await closer()
            except Exception:  # noqa: BLE001
                pass

    return {
        "valid": True,
        "errors": [],
        "transformed": transformed,
        "raw_upstream": getattr(source, "last_raw_response", None),
        "upstream_url": getattr(source, "last_upstream_url", None),
    }


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

@router.get("/templates")
async def templates() -> dict:
    return {"templates": _TEMPLATES}


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------

def _parse_or_400(text: str) -> dict:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}") from e
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="YAML root must be a mapping")
    return parsed


def _validate_cfg(parsed: dict | None) -> dict:
    if not parsed:
        return {"valid": False, "errors": [{"loc": [], "msg": "Empty config"}]}
    try:
        SourceConfig.model_validate(_expand_env(parsed))
    except ValidationError as e:
        return {
            "valid": False,
            "errors": [
                {"loc": list(err["loc"]), "msg": err["msg"]}
                for err in e.errors()
            ],
        }
    return {"valid": True, "errors": []}


def _find_file_by_id(collection_id: str) -> Path | None:
    # Try registry first (covers the loaded case quickly).
    p = registry.file_for(collection_id)
    if p is not None and p.exists():
        return p
    # Fall back to scanning disk — handles configs that failed to load and
    # therefore aren't in the registry.
    for path in _list_yaml_files():
        text, parsed, _ = _load_raw_yaml(path)
        if parsed and (parsed.get("collection") or {}).get("id") == collection_id:
            return path
    return None


async def _reload(app: Any) -> None:
    """Hot-reload all sources. Imported lazily to avoid a circular import."""
    from app.main import _load_sources
    await _load_sources(app)
    logger.info("Admin: registry reloaded — %d source(s) active", len(registry.list_collections()))


class _NoMountApp:
    """A drop-in stand-in for FastAPI app used by build_source during /test.

    The fallback adapter calls app.mount() to expose static files; for an
    ephemeral test source we don't want that side effect, so we hand the
    factory a fake app whose mount() is a no-op."""

    def mount(self, *_args: Any, **_kwargs: Any) -> None:
        return None


# --------------------------------------------------------------------------
# Starter templates (presented in the admin UI's "New source" dropdown)
# --------------------------------------------------------------------------

_TEMPLATES: list[dict] = [
    {
        "key": "rest-generic",
        "label": "REST API (generic search/discovery)",
        "yaml": """collection:
  id: my-new-source
  name: "My New Source"
  description: "Replace with a short, user-facing description."
  organization: "Provider"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: rest
  base_url: "https://api.example.org"
  auth:
    type: none           # or "query_param" / "header"
    # name: api_key
    # value: "${MY_API_KEY}"
  timeout_seconds: 12
  default_query: {}

search:
  path: "/search"
  pagination:
    style: page_size     # page_size | offset_limit | cursor | none
    page_param: page
    size_param: per_page
    page_base: 1
    max_size: 50
  query:
    pattern_param: q
    pattern_when_empty: "*"

mapping:
  items_path: "results"
  fields:
    assetID:     { expr: "id", transform: slugify }
    title:       { expr: "title", default: "Untitled" }
    description: { expr: "description" }
    assetURI:    { expr: "media_url" }
    previewURI:  { expr: "thumb_url" }
    contentType: { expr: "mime", default: "image/jpeg" }
    rights:      { expr: "license" }
    contributor: { literal: "My Source" }
    scale:       { literal: "1" }

filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI", "previewURI"]

cache:
  ttl_seconds: 600
""",
    },
    {
        "key": "iiif-manifest",
        "label": "IIIF Presentation API manifest",
        "yaml": """collection:
  id: my-iiif-source
  name: "My IIIF Source"
  description: "One IIIF manifest exposed as an Impulse collection."
  organization: "Provider"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: custom
  custom_class: "app.adapter.custom.iiif.IIIFManifestSource"
  base_url: "https://iiif.example.org/presentation/manifest.json"
  timeout_seconds: 20
""",
    },
    {
        "key": "fallback-local",
        "label": "Fallback (local files)",
        "yaml": """collection:
  id: my-local-source
  name: "My Local Source"
  description: "Static, locally-hosted demo assets."
  organization: "Impulse Bridge"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: fallback
  manifest_path: "data/fallback/assets/manifest.json"
  static_mount: true
""",
    },
]
