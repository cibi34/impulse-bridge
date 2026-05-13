# 02 — Architecture

This document describes how the bridge is built, how a request travels through it, and how each component fulfils the Impulse Collections-and-Assets specification.

## High-level component diagram

```
                       ┌──────────────────────────────────────────────────────┐
                       │                    Impulse Bridge                    │
                       │                                                      │
   HTTP request ──────►│  ┌────────────┐    ┌────────────┐                   │
   (from Impulse,      │  │ HTTP layer │───►│  Registry  │                   │
    Unity, or admin    │  │  (FastAPI) │    │            │                   │
    UI)                │  │  routers:  │    │  id→Source │                   │
                       │  │  • public  │    │   map      │                   │
                       │  │  • admin   │    └─────┬──────┘                   │
                       │  └────────────┘          │                          │
                       │         │                ▼                          │
                       │         │     ┌────────────────────────────┐        │
                       │         │     │   Adapter (per Source)     │        │
                       │         │     │  ─ GenericRestSource       │        │
                       │         │     │  ─ FallbackSource          │        │
                       │         │     │  ─ Custom (e.g. IIIF)      │        │
                       │         │     └─────────┬──────────────────┘        │
                       │         │               │                           │
                       │         │     ┌─────────▼──────┐    ┌─────────┐    │
                       │         │     │ Transform engine│───►│  Cache  │    │
                       │         │     │  (JMESPath)     │    │ (TTL)   │    │
                       │         │     └─────────┬──────┘    └─────────┘    │
                       │         │               │                           │
                       │         ▼               ▼                           │
                       │   ┌──────────────────────────────┐                 │
                       │   │  Response wrapped in         │                 │
                       │   │  Impulse envelope            │                 │
                       │   │  {code, message, data}       │                 │
                       │   └──────────────────────────────┘                 │
                       └────────────────────────│─────────────────────────────┘
                                                ▼
                                       External upstream
                                       (HTTPS to archive)
```

## Module layout

```
app/
├── main.py             # FastAPI app, lifespan, exception handlers, route mounting
├── settings.py         # Pydantic settings — reads env / .env
├── registry.py         # In-memory collection_id → Source map (+ hot-reload primitives)
├── cache.py            # TTL cache wrapper (cachetools) keyed by source+path+params
├── errors.py           # BridgeError hierarchy; maps to Impulse `code` values
├── logging_conf.py
│
├── api/                # Public, Impulse-protocol endpoints
│   ├── responses.py    # impulse_response() — the single source of truth for {code, message, data}
│   ├── health.py
│   ├── collections.py  # /collections and /collections/{id}
│   └── assets.py       # /collections/{id}/assets and /collections/{id}/asset/{asset_id}
│
├── admin/              # Admin API used by the bundled admin UI (NOT part of the Impulse protocol)
│   └── api.py          # /admin/api/sources, /admin/api/test, /admin/api/templates, …
│
├── config/             # YAML schema and loader
│   ├── schema.py       # Pydantic models that fully describe one source config
│   └── loader.py       # YAML parse + ${ENV_VAR} expansion + validation
│
├── transform/          # Mapping engine
│   ├── engine.py       # transform_item / extract_items
│   ├── jmes.py         # JMESPath thin wrapper
│   └── helpers.py      # slugify, strip_html, mime_from_url, …
│
└── adapter/
    ├── base.py         # Source protocol — what every adapter must implement
    ├── factory.py      # Build a Source from a SourceConfig
    ├── rest.py         # GenericRestSource — the 95% case
    ├── fallback.py     # FallbackSource — local JSON manifest + static file serving
    └── custom/
        └── iiif.py     # IIIFManifestSource — example of a hand-written adapter
```

Three top-level external folders complete the picture:

```
configs/sources/*.yaml    # One file per virtual collection
data/fallback/            # Local demo assets (manifest.json + binary media)
static/                   # The two bundled UIs (index.html, admin.html) and help viewer
docs/                     # This documentation
```

## The contract with Impulse

The bridge is a pure server to the Impulse platform: Impulse calls the bridge, the bridge never calls Impulse. The contract is the Impulse "Collections and assets schema, discovery and access" specification.

### Endpoint mapping (spec → bridge)

| Specification endpoint | Bridge route | Backed by |
|---|---|---|
| `GET <platform_api>/collections` | `GET /collections` | `app/api/collections.py` → `Registry.list_collections()` |
| `GET <collection_uri>` | `GET /collections/{id}` | `app/api/collections.py` → `Registry.get(id).collection_meta` |
| `GET <collection_uri>/assets` | `GET /collections/{id}/assets` | `app/api/assets.py` → `Source.search()` |
| `GET <collection_uri>/asset/<asset_id>` | `GET /collections/{id}/asset/{asset_id}` | `app/api/assets.py` → `Source.get_asset()` |

Pagination (`?o=offset&c=count`) and search (`?s=pattern`) parameters are accepted exactly as written in the spec. Each adapter translates them into the upstream archive's own dialect.

### Response envelope

Every public endpoint returns:

```json
{"code": 0, "message": "OK", "data": <list-or-object>}
```

The `data` field is an **array** for list endpoints (collections, asset discovery) and an **object** for single-resource endpoints (single collection metadata, single asset detail). On error, `data` is `[]` (lists) or `null` (objects) and `code` reflects what went wrong.

This shape is locked in one place — [`app/api/responses.py`](../app/api/responses.py) — so every endpoint goes through the same helper and cannot accidentally drift.

### `code` reference

| `code` | meaning | HTTP status | typical cause |
|---|---|---|---|
| 0 | OK | 200 | success |
| 1 | Collection not found | 404 | unknown collection id |
| 2 | Asset not found | 404 | unknown asset id within an existing collection |
| 10 | Upstream source unavailable | 503 | network error, timeout, 5xx from upstream |
| 11 | Upstream rate limit reached | 503 | upstream returned 429 |
| 12 | Upstream returned malformed data | 502 | upstream returned non-JSON or 4xx other than 401/403 |
| 20 | Bridge configuration error | 500 | missing API key, 401/403 from upstream, invalid YAML at startup |
| 99 | Internal bridge error | 500 | unhandled exception |

## Request flow — asset discovery

Tracing `GET /collections/wikimedia-commons-images/assets?s=van+gogh&c=3`:

```
1.  FastAPI matches the route in app/api/assets.py.
       list_assets(collection_id="wikimedia-commons-images", s="van gogh", o=0, c=3)

2.  Registry lookup
       source = registry.get("wikimedia-commons-images")
       → returns a GenericRestSource instance built from configs/sources/wikimedia-commons.yaml

3.  Source.search()  (in app/adapter/rest.py)
       3a. _build_params() consults the YAML:
              - search.query.pattern_param      → ?gsrsearch=van+gogh
              - adapter.default_query           → action=query, format=json, generator=search, …
              - search.pagination (offset_limit) → ?gsroffset=0&gsrlimit=3
       3b. Cache lookup keyed by source_id + path + sorted params.
              Miss → continue. Hit → skip step 3c.
       3c. HTTP GET against adapter.base_url + search.path
              https://commons.wikimedia.org/w/api.php?…
              On 4xx/5xx, raise a BridgeError; the exception handler turns it into the right `code`.
       3d. Response body cached under the key from 3b.

4.  Transform engine  (in app/transform/engine.py)
       For each raw item from items_path:
         For each Impulse field declared in mapping.fields:
           - Evaluate JMESPath, apply default, apply value-map, apply transform.
         Drop the item if it fails the filter (allowed_content_types / drop_if_missing).
       Returns list[dict] in Impulse asset shape.

5.  app/api/responses.py wraps the list in {code: 0, message: "OK", data: […]}.

6.  FastAPI serializes and sends.
```

The cache caches **raw upstream JSON**, not transformed assets. Editing the YAML mapping therefore takes effect on the next request even if the cache is warm — no cache flush needed.

## Request flow — single asset

`GET /collections/wikimedia-commons-images/asset/151972`:

If the YAML has `asset_detail.enabled: true` and a `path` (it does for Wikimedia, with `pageids={asset_id}`), the source builds a fresh URL using `asset_detail.query` (which **replaces** `default_query`, not merges with it — because search and detail endpoints typically take different parameters), calls the upstream, and runs the same transform.

If `asset_detail` is disabled, the source falls back to calling its own `search()` with no query, scanning the result for a matching `assetID`, and returning that. This is the easy path for sources where individual detail lookups are awkward (Europeana, IIIF).

## Hot-reload mechanism

`POST/PUT/DELETE` on `/admin/api/sources/...` triggers `_load_sources(app)` in [`app/main.py`](../app/main.py):

1. `registry.clear()` — closes every `httpx.AsyncClient`, empties the `id → Source` map.
2. `load_all(settings.config_dir)` — parses every YAML in `configs/sources/`, validates each against the Pydantic schema, expanding `${ENV_VAR}` references.
3. For each valid config, `build_source()` constructs the correct adapter (REST, fallback, or custom) and `registry.register()` indexes it.
4. Any per-source errors are kept in `registry._load_errors` and surfaced in the admin API's `/sources` response — the rest of the bridge keeps serving valid sources.

Net effect: changing a YAML file (via the admin UI or directly on disk + admin `↻` button) updates the live registry within milliseconds; no server restart required.

## The Source protocol

Every adapter implements the same minimal interface defined in [`app/adapter/base.py`](../app/adapter/base.py):

```python
class Source(Protocol):
    collection_meta: dict                   # what /collections/{id} returns
    async def search(query, offset, count) -> list[dict]
    async def get_asset(asset_id) -> dict
```

That's it. The HTTP layer never knows whether it is talking to a REST adapter, a filesystem adapter, or a custom Python class. Adding a new adapter kind (GraphQL, SPARQL, …) means writing one class that satisfies this protocol and registering it via `adapter.kind: custom` in YAML.

## The three adapter kinds

### `kind: rest` — `GenericRestSource`

The workhorse. Configured entirely from YAML. Handles:

- Auth via `query_param` or `header`.
- Three pagination styles: `page_size`, `offset_limit`, `cursor`, plus `none`.
- Search-pattern translation (Impulse `s=` → upstream's own parameter, with optional wildcard rewriting).
- Per-source default query parameters for static filters and headers.
- One retry on transient timeouts.
- Distinct error mapping: 429 → rate-limit, 401/403 → config error, 5xx → unavailable, other 4xx → malformed.
- Two inspection attributes (`last_upstream_url`, `last_raw_response`) used by the admin UI's Test tab.

Used by: Europeana, Wikimedia Commons, Smithsonian Open Access, and any future archive that exposes a JSON search API.

### `kind: fallback` — `FallbackSource`

Reads pre-mapped Impulse-schema JSON from `data/fallback/assets/manifest.json` and returns slices of it. Substring search across `title`, `description`, `subject`, `creator`, `contributor`, `type`, `assetID`. The factory mounts the manifest's parent directory at `/collections/{id}/` so relative `assetURI` / `previewURI` values resolve correctly via static file serving — matching the resolution semantics defined in the spec.

Used for: the `bridge-demo` collection, offline demos, and as a guaranteed-working fallback when external APIs are down.

### `kind: custom` — user-provided Python class

For archives that cannot be described declaratively. The YAML names a dotted Python path (`app.adapter.custom.iiif.IIIFManifestSource`); the factory imports the module, instantiates the class with the `SourceConfig`, and registers the result.

Used for: IIIF Presentation API. One bundled implementation in [`app/adapter/custom/iiif.py`](../app/adapter/custom/iiif.py) handles both Presentation API v2 (`sequences[].canvases[]`) and v3 (`items[]` of Canvases), turning each canvas into one Impulse asset whose URLs are derived via the IIIF Image API.

## Cache

A single in-process `cachetools.TTLCache` keyed by `sha1(source_id|path|sorted_params)`. The cache stores **raw upstream JSON** (one entry per distinct upstream call). The default TTL is 10 minutes; each source can override via `cache.ttl_seconds`. Cache is cleared on `registry.clear()`.

This is intentionally not Redis: single-process POC, no horizontal scaling, no persistence requirement. The interface (`BridgeCache.get/set`) is narrow enough that swapping in Redis later is a 20-minute job.

## Errors are first-class

Adapter errors are exceptions inheriting from `BridgeError`. Each subclass carries its own `code` value:

```python
class CollectionNotFound(BridgeError):  code = 1
class AssetNotFound(BridgeError):       code = 2
class UpstreamUnavailable(BridgeError): code = 10
class UpstreamRateLimited(BridgeError): code = 11
class UpstreamMalformed(BridgeError):   code = 12
class ConfigError(BridgeError):         code = 20
```

A single FastAPI exception handler ([`app/main.py`](../app/main.py)) catches any `BridgeError`, runs it through `impulse_response(code, message)`, and sends the Impulse envelope. Unhandled exceptions become `code: 99` with HTTP 500 — but never an unwrapped Python traceback in the JSON.

This means every endpoint, on every code path, returns the spec-shaped response. Impulse never has to handle anything outside the envelope.

## Public vs. admin endpoints

The bridge serves two API surfaces on the same port. They do **not** share a response shape on purpose:

| Surface | Path prefix | Response shape | Audience |
|---|---|---|---|
| Public (Impulse protocol) | `/collections`, `/health` | `{code, message, data}` (Impulse envelope) | Impulse platform, Unity client |
| Admin | `/admin/api/...` | Plain JSON, FastAPI conventions | Bundled admin UI in the browser |

The admin API is **only** consumed by the bundled admin UI. It is therefore allowed to use FastAPI's normal patterns (HTTP 422 for validation, etc.) and not the Impulse envelope. The two surfaces never mix.

Two HTML pages are served on top:

- `GET /` → `static/index.html` (public browser UI for browsing assets visually)
- `GET /admin` → `static/admin.html` (admin UI for editing configs)
- `GET /help` → `static/help.html` (this documentation, rendered inline)

## Configuration loading

At startup (and after every admin save / delete), the bridge:

1. Reads `.env` (via `python-dotenv`) into `os.environ`. This must happen at import time so `${ENV_VAR}` expansion in YAML works.
2. Discovers `configs/sources/*.yaml` in `settings.config_dir`.
3. For each file: parse YAML → substitute `${VAR}` references → validate against `SourceConfig` (Pydantic) → call `build_source()` → register.

If any single file fails to validate, **the rest still load**. The failing file is reported in `Registry.errors()` and surfaced to the admin UI as a red status dot. This is deliberate: one operator's broken YAML must not take down the bridge for the other operators.

## What the bridge does NOT cache or persist

- **Transformed assets** are computed per-request from cached raw JSON.
- **Pagination state** is stateless — the bridge does not remember cursors between requests (cursor-based upstream archives are converted to offset-based on a best-effort basis).
- **Auth tokens** are not cached; the bridge sends the same `${ENV_VAR}` value every time.
- **User sessions** do not exist. The bridge is a stateless adapter.

This makes the bridge horizontally scalable in principle (multiple replicas, no shared state) once the cache is moved out of process.

---

_Last verified against [`Collections-and-assets-schema,-discovery-and-access.md`](../Collections-and-assets-schema,-discovery-and-access.md) v3.11 (28/11/2025)._

_Continue to [03 — YAML reference](03-yaml-reference.md)._
