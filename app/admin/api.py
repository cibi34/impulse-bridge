"""Admin API for inspecting, editing, testing and hot-reloading sources.

These endpoints are not part of the Impulse Collections-and-Assets protocol —
they exist purely so the admin browser UI can manage YAML configs at runtime
without restarting the server. They use plain JSON responses (no `{code,
message, data}` envelope) since their consumer is the bundled admin UI."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from app.adapter.factory import build_source
from app.config.loader import _expand_env
from app.config.schema import SourceConfig
from app.licensing import classify
from app.loading import load_sources
from app.registry import registry
from app.settings import settings
from app.storage import get_licence_conditions

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
    loaded_ids = {c["id"] for c in registry.list_meta()}
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
            loaded_from = registry.file_for(info["id"]) if info["id"] else None
            info["loaded"] = loaded_from is not None and loaded_from.name == path.name
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
        "loaded": collection_id in {c["id"] for c in registry.list_meta()},
    }


# --------------------------------------------------------------------------
# Save / create
# --------------------------------------------------------------------------

class SaveBody(BaseModel):
    yaml: str
    """The full YAML text to write to disk."""


@router.put("/sources/{collection_id}")
async def upsert_source(
    collection_id: str,
    body: SaveBody,
    create: bool = Query(False, description="Refuse (409) instead of overwriting an existing source"),
) -> dict:
    """Create or update a source. The YAML's collection.id is authoritative:
    when it differs from the URL id, the source is renamed (its file keeps its
    name). Writing to an id that another file already defines is refused with
    409, as is `create=true` for an id that exists at all."""
    parsed = _parse_or_400(body.yaml)
    validation = _validate_cfg(parsed)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail={"errors": validation["errors"], "parsed": parsed},
        )

    new_id = parsed["collection"]["id"]
    existing = None if create else _find_file_by_id(collection_id)
    taken_by = _find_file_by_id(new_id)
    if taken_by is not None and (existing is None or taken_by.resolve() != existing.resolve()):
        raise HTTPException(
            status_code=409,
            detail=f"A source with id '{new_id}' already exists ({taken_by.name})",
        )

    target = existing or _free_path(_filename_from_id(new_id))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.yaml, encoding="utf-8")

    await load_sources()
    return await get_source(new_id)


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------

@router.delete("/sources/{collection_id}")
async def delete_source(collection_id: str) -> dict:
    path = _find_file_by_id(collection_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Source '{collection_id}' not found")
    path.unlink()
    await load_sources()
    return {"deleted": collection_id, "filename": path.name}


# --------------------------------------------------------------------------
# Reload (after editing files on disk)
# --------------------------------------------------------------------------

@router.post("/reload")
async def reload_sources() -> dict:
    """Re-read every config file from disk and hot-swap the registry."""
    await load_sources()
    return await list_sources()


# --------------------------------------------------------------------------
# Live test (does not save)
# --------------------------------------------------------------------------

class TestBody(BaseModel):
    yaml: str
    query: str | None = None
    count: int = 5


@router.post("/test")
async def test_source(
    body: TestBody, accepted: Annotated[frozenset[str], Depends(get_licence_conditions)]
) -> dict:
    """Build an ephemeral Source from the submitted YAML, run a search, and
    return both the raw upstream JSON and the transformed Impulse assets,
    with the licence each asset's `rights` value is read as (`licences`)."""
    parsed = _parse_or_400(body.yaml)
    validation = _validate_cfg(parsed)
    if not validation["valid"]:
        return {
            "valid": False,
            "errors": validation["errors"],
            "transformed": [],
            "licences": [],
            "raw_upstream": None,
            "upstream_url": None,
        }
    cfg = SourceConfig.model_validate(_expand_env(parsed))

    # An ephemeral source, never registered: the live registry is untouched.
    try:
        source = build_source(cfg)
    except Exception as e:  # noqa: BLE001
        return {
            "valid": True,
            "errors": [{"loc": ["adapter"], "msg": str(e)}],
            "transformed": [],
            "licences": [],
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
            "licences": [],
            "raw_upstream": _masked_raw(getattr(source, "last_raw_response", None), cfg),
            "upstream_url": _masked_url(getattr(source, "last_upstream_url", None), cfg),
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
        "licences": [classify(a.get("rights")).as_dict(accepted) for a in transformed],
        "raw_upstream": _masked_raw(getattr(source, "last_raw_response", None), cfg),
        "upstream_url": _masked_url(getattr(source, "last_upstream_url", None), cfg),
    }


class LookupBody(BaseModel):
    yaml: str
    asset_id: str = Field(min_length=1, max_length=500)


@router.post("/test-lookup")
async def test_lookup(
    body: LookupBody, accepted: Annotated[frozenset[str], Depends(get_licence_conditions)]
) -> dict:
    """Run the submitted YAML's single-asset lookup (`asset_detail`) for one
    assetID, as adding the asset to a collection later will — without the
    shortcut through recent search results."""
    parsed = _parse_or_400(body.yaml)
    validation = _validate_cfg(parsed)
    if not validation["valid"]:
        return {"found": False, "error": "The configuration has problems; fix them first.",
                "asset": None, "licence": None, "upstream_url": None, "raw_upstream": None}
    cfg = SourceConfig.model_validate(_expand_env(parsed))
    try:
        source = build_source(cfg)
    except Exception as e:  # noqa: BLE001
        return {"found": False, "error": str(e), "asset": None, "licence": None,
                "upstream_url": None, "raw_upstream": None}
    lookup = getattr(source, "lookup", None)
    asset, error = None, None
    try:
        if lookup is None:
            error = "Only REST sources have a configurable single-asset lookup."
        else:
            asset = await lookup(body.asset_id)
    except Exception as e:  # noqa: BLE001
        error = getattr(e, "message", None) or str(e)
    finally:
        closer = getattr(source, "aclose", None)
        if closer is not None:
            try:
                await closer()
            except Exception:  # noqa: BLE001
                pass
    return {
        "found": asset is not None,
        "error": error,
        "asset": asset,
        "licence": classify(asset.get("rights")).as_dict(accepted) if asset else None,
        "upstream_url": _masked_url(getattr(source, "last_upstream_url", None), cfg),
        "raw_upstream": _masked_raw(getattr(source, "last_raw_response", None), cfg),
    }


class LicencesBody(BaseModel):
    values: list[str | None] = Field(max_length=1000)


@router.post("/licences")
def read_licences(
    body: LicencesBody, accepted: Annotated[frozenset[str], Depends(get_licence_conditions)]
) -> dict:
    """How each rights value is read as a licence, and whether IMPULSE accepts
    it (for the mapper's live preview)."""
    return {"licences": [classify(v).as_dict(accepted) for v in body.values]}


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


def _masked_url(url: str | None, cfg: SourceConfig) -> str | None:
    """The upstream URL with the API key replaced, for display: keys are
    confidential (Europeana's terms) and end up in screenshots otherwise."""
    auth = cfg.adapter.auth
    if not url or auth.type != "query_param" or not auth.name or not auth.value:
        return url
    parts = urlsplit(url)
    query = [(k, "***" if k == auth.name else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit(parts._replace(query=urlencode(query, safe="*:")))


def _masked_raw(value: Any, cfg: SourceConfig) -> Any:
    """The raw upstream JSON with the API key replaced wherever it appears
    (Europeana echoes it back as "apikey")."""
    secret = cfg.adapter.auth.value if cfg.adapter.auth.type != "none" else None
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "***")
    if isinstance(value, list):
        return [_masked_raw(v, cfg) for v in value]
    if isinstance(value, dict):
        return {k: _masked_raw(v, cfg) for k, v in value.items()}
    return value


def _free_path(filename: str) -> Path:
    """`filename` in the config dir, or `<stem>-2.yaml`, `-3`, … if a file of
    that name already exists (it may hold a different id)."""
    candidate = settings.config_dir / filename
    stem, suffix = candidate.stem, candidate.suffix
    n = 2
    while candidate.exists():
        candidate = settings.config_dir / f"{stem}-{n}{suffix}"
        n += 1
    return candidate


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
  description: "The pages of one IIIF manifest."
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
  organization: "IMPULSE Curator"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: fallback
  manifest_path: "data/fallback/assets/manifest.json"
  static_mount: true
""",
    },
]
