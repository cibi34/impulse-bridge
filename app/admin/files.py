"""Admin API: source configs as files.

The admin UI edits each config as the YAML text on disk, so comments and
formatting survive a save. Working by filename also lets it open and repair
files that are broken (no parsable id). Every change hot-reloads the
registry; a file never takes over another file's source id.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.admin.api import _filename_from_id, _free_path, _list_yaml_files
from app.admin.validation import validate_text
from app.loading import load_sources
from app.registry import registry
from app.settings import settings

router = APIRouter(prefix="/admin/api", tags=["admin"])

_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml$")


class YamlBody(BaseModel):
    yaml: str


def _path(filename: str) -> Path:
    if not _FILENAME.match(filename):
        raise HTTPException(status_code=404, detail="Config file not found")
    return settings.config_dir / filename


def _existing(filename: str) -> Path:
    path = _path(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Config file '{filename}' not found")
    return path


def _info(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    result = validate_text(text)
    source_id = result["id"]
    loaded_from = registry.file_for(source_id) if source_id else None
    load_error = dict(registry.errors()).get(path.name)
    return {
        "filename": path.name,
        "yaml": text,
        "id": source_id,
        "valid": result["valid"],
        "errors": result["errors"],
        "loaded": loaded_from is not None and loaded_from.name == path.name,
        "load_error": load_error,
    }


def _id_owner(source_id: str, other_than: Path | None) -> Path | None:
    """Another config file that defines this source id."""
    for path in _list_yaml_files():
        if other_than is not None and path.resolve() == other_than.resolve():
            continue
        if validate_text(path.read_text(encoding="utf-8"))["id"] == source_id:
            return path
    return None


def _checked(text: str, target: Path | None) -> str:
    result = validate_text(text)
    if not result["valid"]:
        raise HTTPException(status_code=422, detail={"errors": result["errors"]})
    owner = _id_owner(result["id"], target)
    if owner is not None:
        raise HTTPException(
            status_code=409,
            detail=f"The source id '{result['id']}' is already used by {owner.name}",
        )
    return result["id"]


@router.post("/validate")
def validate(body: YamlBody) -> dict:
    """Validate YAML text without saving it (live feedback in the editor)."""
    result = validate_text(body.yaml)
    return {"valid": result["valid"], "errors": result["errors"], "id": result["id"]}


@router.get("/files/{filename}")
def read_file(filename: str) -> dict:
    return _info(_existing(filename))


@router.post("/files", status_code=201)
async def create_file(body: YamlBody) -> dict:
    """Create a config file; its name is derived from the source id."""
    source_id = _checked(body.yaml, None)
    path = _free_path(_filename_from_id(source_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.yaml, encoding="utf-8", newline="")
    await load_sources()
    return _info(path)


@router.put("/files/{filename}")
async def update_file(filename: str, body: YamlBody) -> dict:
    path = _existing(filename)
    _checked(body.yaml, path)
    # newline="": keep the text exactly as edited (no CRLF translation on Windows).
    path.write_text(body.yaml, encoding="utf-8", newline="")
    await load_sources()
    return _info(path)


@router.delete("/files/{filename}")
async def delete_file(filename: str) -> dict:
    path = _existing(filename)
    path.unlink()
    await load_sources()
    return {"deleted": filename}
