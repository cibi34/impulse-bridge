"""Curated collections: ids, edit keys, snapshots and Impulse serialization.

A curated collection stores a *snapshot* of every asset (the source's Impulse
asset dict at the time it was added), so Unity clients are served from the
database: fast, and independent of upstream rate limits and outages. The
editor can refresh snapshots on demand.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from starlette.concurrency import run_in_threadpool

from app.curation.store import CollectionRecord, CollectionStore, ItemRecord, NewItem
from app.errors import AssetNotFound, BridgeError, SourceNotFound
from app.licensing import classify
from app.registry import registry
from app.settings import settings
from app.transform.helpers import slugify

SNAPSHOT_CONCURRENCY = 6
"""Parallel upstream lookups while adding assets (most are cache hits)."""

_ID_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no 0/o, 1/l
_SLUG_MAX = 48


# ---------------------------------------------------------------------------
# Ids and edit keys
# ---------------------------------------------------------------------------

def _short_slug(text: str, fallback: str) -> str:
    slug = slugify(text)
    if slug == "untitled":
        slug = fallback
    if len(slug) > _SLUG_MAX:
        slug = slug[:_SLUG_MAX].rsplit("-", 1)[0] or slug[:_SLUG_MAX]
    return slug


_COLLECTION_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COLLECTION_ID_LENGTH = (3, 80)


def collection_id_problem(value: str) -> str | None:
    """Why `value` cannot be a collection id, or None. The Impulse id-schema:
    lowercase letters and digits, words joined by single hyphens."""
    shortest, longest = COLLECTION_ID_LENGTH
    if len(value) < shortest:
        return f"Use at least {shortest} characters."
    if len(value) > longest:
        return f"Use at most {longest} characters."
    if not _COLLECTION_ID.fullmatch(value):
        return (
            "Use only lowercase letters a–z, digits and single hyphens, "
            "starting and ending with a letter or digit."
        )
    return None


def new_collection_id(name: str, exists) -> str:
    """Readable and unguessable: "masters-of-light-k3m9x2"."""
    base = _short_slug(name, "collection")
    while True:
        suffix = "".join(secrets.choice(_ID_ALPHABET) for _ in range(6))
        candidate = f"{base}-{suffix}"
        if not exists(candidate):
            return candidate


def item_asset_id(title: str | None, source_id: str, source_asset_id: str, taken: set[str]) -> str:
    """Stable assetID within a collection: title slug + a hash of the source
    reference, so the same asset always gets the same id and assets from
    different sources never collide."""
    digest = hashlib.sha1(f"{source_id}\0{source_asset_id}".encode()).hexdigest()
    base = _short_slug(title or "", "asset")
    for length in (6, 10, 40):
        candidate = f"{base}-{digest[:length]}"
        if candidate not in taken:
            return candidate
    raise RuntimeError("asset id collision")  # pragma: no cover — sha1 prefix of 40


def new_edit_key() -> tuple[str, str]:
    """(key for the creator, hash to store)."""
    key = secrets.token_urlsafe(24)
    return key, hash_edit_key(key)


def hash_edit_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def edit_key_matches(key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_edit_key(key), stored_hash)


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssetRef:
    source: str
    asset_id: str


@dataclass(frozen=True)
class Failure:
    source: str
    asset_id: str
    reason: str


def source_files_base(source_id: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/sources/{source_id}/files/"


def absolutize(asset: dict[str, Any], source_id: str) -> dict[str, Any]:
    """Resolve relative assetURI/previewURI (fallback sources) to absolute URLs.
    Per the Impulse spec they are relative to the collection URI, which a
    curated collection does not share with its source."""
    out = dict(asset)
    for key in ("assetURI", "previewURI"):
        value = out.get(key)
        if isinstance(value, str) and value and not urlparse(value).scheme:
            out[key] = urljoin(source_files_base(source_id), value.lstrip("/"))
    return out


async def fetch_asset(ref: AssetRef) -> dict[str, Any] | Failure:
    """The source's current asset (absolute URIs), or why it is unavailable."""
    try:
        source = registry.get(ref.source)
    except SourceNotFound:
        return Failure(ref.source, ref.asset_id, "Unknown source")
    try:
        asset = await source.get_asset(ref.asset_id)
    except AssetNotFound:
        return Failure(ref.source, ref.asset_id, "Asset not found")
    except BridgeError as e:
        return Failure(ref.source, ref.asset_id, e.message)
    return absolutize(asset, ref.source)


async def fetch_assets(refs: list[AssetRef]) -> list[dict[str, Any] | Failure]:
    semaphore = asyncio.Semaphore(SNAPSHOT_CONCURRENCY)

    async def one(ref: AssetRef):
        async with semaphore:
            return await fetch_asset(ref)

    return await asyncio.gather(*(one(ref) for ref in refs))


def unique_refs(refs: list[AssetRef]) -> list[AssetRef]:
    return list(dict.fromkeys(refs))


async def snapshot_items(
    refs: list[AssetRef], taken: set[str], accepted: frozenset[str]
) -> tuple[list[NewItem], list[Failure]]:
    """Snapshots of the assets that are available and whose licence IMPULSE
    accepts; the others are reported."""
    items: list[NewItem] = []
    failures: list[Failure] = []
    taken = set(taken)
    for ref, result in zip(refs, await fetch_assets(refs)):
        if isinstance(result, Failure):
            failures.append(result)
            continue
        licence = classify(result.get("rights"))
        if not licence.allowed(accepted):
            failures.append(Failure(ref.source, ref.asset_id, f"Licence not accepted: {licence.label}"))
            continue
        asset_id = item_asset_id(result.get("title"), ref.source, ref.asset_id, taken)
        taken.add(asset_id)
        items.append(NewItem(asset_id, ref.source, ref.asset_id, result))
    return items, failures


# ---------------------------------------------------------------------------
# Operations used by the web API
# ---------------------------------------------------------------------------

class CollectionFull(Exception):
    pass


async def create_collection(
    store: CollectionStore,
    *,
    name: str,
    description: str,
    organization: str,
    owner_email: str | None,
    refs: list[AssetRef],
    accepted: frozenset[str],
) -> tuple[CollectionRecord, str, list[Failure]]:
    refs = unique_refs(refs)
    if len(refs) > settings.max_assets_per_collection:
        raise CollectionFull()
    items, failures = await snapshot_items(refs, set(), accepted)
    key, key_hash = new_edit_key()
    collection_id = await run_in_threadpool(new_collection_id, name, store.exists)
    record = await run_in_threadpool(
        lambda: store.create(
            collection_id=collection_id,
            name=name,
            description=description,
            organization=organization,
            owner_email=owner_email,
            edit_key_hash=key_hash,
            items=items,
        )
    )
    return record, key, failures


async def add_items(
    store: CollectionStore, record: CollectionRecord, refs: list[AssetRef], accepted: frozenset[str]
) -> tuple[list[ItemRecord], list[Failure]]:
    present = await run_in_threadpool(store.source_refs, record.id)
    refs = [ref for ref in unique_refs(refs) if (ref.source, ref.asset_id) not in present]
    free = settings.max_assets_per_collection - record.item_count
    if len(refs) > free:
        raise CollectionFull()
    taken = await run_in_threadpool(store.asset_ids, record.id)
    items, failures = await snapshot_items(refs, taken, accepted)
    added = await run_in_threadpool(store.add_items, record.id, items)
    return added, failures


async def refresh_items(store: CollectionStore, record: CollectionRecord) -> tuple[int, list[Failure]]:
    """Re-fetch every snapshot from its source. Assets that are gone upstream
    keep their last snapshot and are reported. An asset whose licence changed
    to one IMPULSE doesn't accept stays in the collection but is no longer
    served (`served`)."""
    items = await run_in_threadpool(store.items, record.id)
    results = await fetch_assets([AssetRef(i.source_id, i.source_asset_id) for i in items])
    refreshed, failures = 0, []
    for item, result in zip(items, results):
        if isinstance(result, Failure):
            failures.append(result)
            continue
        await run_in_threadpool(store.update_snapshot, record.id, item.asset_id, result)
        refreshed += 1
    return refreshed, failures


# ---------------------------------------------------------------------------
# Impulse serialization (what Unity sees)
# ---------------------------------------------------------------------------

def collection_uri(collection_id: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/collections/{collection_id}"


def impulse_collection(record: CollectionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "uri": collection_uri(record.id),
        "name": record.name,
        "description": record.description,
        "organization": record.organization or settings.default_organization,
        "owner_id": settings.collection_owner_id,
        "published": 1,
    }


DETAIL_FIELDS = ("width", "height", "fileSize")
"""Technical facts a source may map (pixels, bytes): the web app shows them.
They are not part of the Impulse asset schema, so the Impulse API leaves them
out and sums them up in the Dublin Core `format` field instead."""


def _count(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def human_size(size: int) -> str:
    """8770678 → "8.8 MB" (decimal units, like file managers)."""
    for unit, factor in (("GB", 10**9), ("MB", 10**6), ("KB", 10**3)):
        if size >= factor:
            return f"{size / factor:.1f} {unit}".replace(".0 ", " ")
    return f"{size} bytes"


def format_summary(asset: dict[str, Any]) -> str | None:
    """"3606 × 2894 px, 8.8 MB" from the detail fields, or None."""
    width, height, size = (_count(asset.get(k)) for k in DETAIL_FIELDS)
    parts = []
    if width and height:
        parts.append(f"{width} × {height} px")
    if size:
        parts.append(human_size(size))
    return ", ".join(parts) or None


def impulse_asset(item: ItemRecord) -> dict[str, Any]:
    """The asset as the Impulse API serves it: schema fields only, with the
    detail fields folded into `format` ("glTF 2.0 binary, 76 KB")."""
    asset = {k: v for k, v in item.asset.items() if k not in DETAIL_FIELDS}
    summary = format_summary(item.asset)
    if summary:
        mapped = str(asset.get("format") or "").strip()
        asset["format"] = f"{mapped}, {summary}" if mapped and summary not in mapped else mapped or summary
    return {**asset, "assetID": item.asset_id, "published": 1}


def web_asset(item: ItemRecord) -> dict[str, Any]:
    """The asset as the web app shows it: everything the source mapped."""
    return {**item.asset, "assetID": item.asset_id, "published": 1}


def served(item: ItemRecord, accepted: frozenset[str]) -> bool:
    """Whether Unity gets the asset: visible, with a licence IMPULSE accepts."""
    return item.published and classify(item.asset.get("rights")).allowed(accepted)
