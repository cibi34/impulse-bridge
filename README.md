# IMPULSE Curator (impulse-bridge)

A collection creator for the [IMPULSE](https://euimpulse.eu/) cultural-heritage platform. Users search open archives (Europeana, Wikimedia Commons, Smithsonian Open Access, IIIF manifests), pick assets, and save them as **curated collections**. Each curated collection is served to Impulse and its Unity clients through the Impulse Collections-and-Assets API.

The archives are configured as **sources**: one YAML file per archive describes how to query and map it. Adding a new archive is normally a YAML-only change — no Python code required.

## What it does

```
 Web app (browser)                          Impulse platform / Unity
   │  search sources, pick assets              │  GET /collections/{id}/assets
   ▼                                           ▼
┌───────────────────────────────────────────────────────────────────┐
│  IMPULSE Curator                                                  │
│   /api/sources/...      search the archives (live, cached)        │
│   /api/collections/...  create & edit curated collections         │
│   /collections/...      Impulse API, served from SQLite snapshots │
└───────────────┬───────────────────────────────────────────────────┘
                │ live search + asset lookups
     ┌──────────┼───────────────┬─────────────────┐
     ▼          ▼               ▼                 ▼
 Europeana  Wikimedia      Smithsonian       IIIF manifests
            Commons        Open Access       (e.g. Wellcome)
```

Asset content is **not** proxied — browsers and Unity load media directly from the original hosts. The bridge serves metadata and URLs. When an asset is added to a collection, its metadata is stored as a snapshot, so Unity requests never wait for an upstream archive.

## Quick start

```powershell
# 1. Create venv + install
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 2. Copy env template and fill in any keys you have
cp .env.example .env
# Edit .env: EUROPEANA_API_KEY=...  SMITHSONIAN_API_KEY=...

# 3. Run
.venv\Scripts\python -m uvicorn app.main:app --port 8080
```

Visit `http://localhost:8080/api/sources` — you should see all configured sources.

## Endpoints

### Impulse API (consumed by Impulse / Unity)

| Method | Path | Purpose |
|---|---|---|
| GET | `/collections` | Curated collections an administrator listed |
| GET | `/collections/{id}` | A curated collection's metadata (every collection, listed or not) |
| GET | `/collections/{id}/assets` | Its assets. Supports `?s=<pattern>`, `?o=<offset>`, `?c=<count>` |
| GET | `/collections/{id}/asset/{asset_id}` | Single asset |
| GET | `/health` | Liveness, source ids and number of collections |

All responses follow the Impulse envelope `{code, message, data}`. Illegal `o`/`c` values return the entire result set, as the spec requires. Codes used:

| code | meaning |
|---|---|
| 0 | OK |
| 1 | Collection not found |
| 2 | Asset not found |
| 10 | Upstream source unavailable |
| 11 | Upstream rate limit reached |
| 12 | Upstream returned malformed data |
| 20 | Bridge configuration error (e.g. missing API key, auth rejected) |
| 99 | Internal bridge error |

### Web app API (consumed by the browser app)

Plain JSON; errors are `{"detail": "...", "code": <int>}` with a matching HTTP status.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/sources` | Configured sources |
| GET | `/api/sources/{id}/assets` | Search a source: `?s=`, `?o=`, `?c=` (≤ 100), `?type=image` or `model`. Returns `items` and `next_offset` |
| GET | `/api/sources/{id}/assets/{asset_id}` | One asset of a source |
| POST | `/api/collections` | Create a collection from `items: [{source, asset_id}]`. Returns the **edit key** (once) |
| GET | `/api/collections?ids=a,b` | Overviews of several collections ("My collections") |
| GET | `/api/collections/{id}` | Public view; with the edit key: editor view incl. hidden assets |
| PATCH / DELETE | `/api/collections/{id}` | Edit name, description, organization, email / delete |
| POST | `/api/collections/{id}/items` | Add assets |
| PATCH / DELETE | `/api/collections/{id}/items/{asset_id}` | Show/hide in Unity (`published`) / remove |
| PUT | `/api/collections/{id}/order` | Reorder |
| POST | `/api/collections/{id}/refresh` | Re-fetch all snapshots from the sources |
| POST | `/api/collections/{id}/submitted` | Record that it was submitted to the Impulse team |
| POST | `/api/collections/{id}/key` | Replace the edit key |

Write endpoints need `Authorization: Bearer <edit key>` and are rate-limited per client.

### Admin API (behind basic auth in production)

`/admin/api/sources/...` (source configs: list, edit, test, reload) and `/admin/api/collections/...` (list, `listed` / `disabled` flags, delete, issue a new edit key).

## Example requests

```bash
# Search Wikimedia Commons, first 3 results
curl 'http://localhost:8080/api/sources/wikimedia-commons-images/assets?s=van+gogh&c=3'

# Create a curated collection from two assets
curl -X POST http://localhost:8080/api/collections -H 'Content-Type: application/json' \
  -d '{"name": "Demo", "items": [{"source": "bridge-demo", "asset_id": "demo-cube"},
                                 {"source": "wikimedia-commons-images", "asset_id": "151972"}]}'

# What Unity sees
curl http://localhost:8080/collections/<collection-id>/assets
```

## Adding a new source

A source is one YAML file in `configs/sources/`. The bridge auto-discovers any `*.yaml` / `*.yml` files in that directory at startup.

### Pattern 1: REST API (most cases)

For any external archive with a JSON search endpoint, write a YAML like this:

```yaml
collection:
  id: my-archive              # lowercase, digits, hyphens only (id-schema)
  name: "My Archive"
  description: "..."
  organization: "Provider"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: rest
  base_url: "https://api.myarchive.org"
  auth:
    type: query_param          # or "header" or "none"
    name: api_key
    value: "${MY_ARCHIVE_KEY}" # ${VAR} is expanded from the environment / .env
  timeout_seconds: 15
  default_query:               # always sent
    format: json

search:
  path: "/search"
  pagination:
    style: page_size           # or "offset_limit" or "cursor" or "none"
    page_param: page
    size_param: per_page
    page_base: 1               # 0 for zero-based APIs
    max_size: 100
  query:
    pattern_param: q           # Impulse's ?s=... is sent as this param
    pattern_when_empty: "*"    # query used when ?s is not provided

mapping:
  items_path: "results"        # JMESPath to the array of items
  fields:
    assetID:    { expr: "id", transform: slugify }
    title:      { expr: "title", default: "Untitled" }
    assetURI:   { expr: "media.url" }
    previewURI: { expr: "media.thumb" }
    contentType: { expr: "media.mime", default: "image/jpeg" }
    rights:     { expr: "license.name" }
    contributor: { literal: "My Archive" }
    scale:      { literal: "1" }

filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI", "previewURI"]   # skip items missing these

asset_detail:                  # optional: only if upstream has a per-asset endpoint
  enabled: true
  path: "/items/{asset_id}"    # {asset_id} = the Impulse asset id verbatim
  query:                       # complete query for this endpoint (default_query is NOT merged in)
    expand: full
  # If assetID is slugified (irreversible) and the upstream search is Solr-based,
  # look the asset up case-insensitively instead — see configs/sources/europeana.yaml:
  #   path: "/search"
  #   query: { q: "id_field:/{asset_id_regex}/" }

cache:
  ttl_seconds: 600
```

Reload (admin **↻**, `POST /admin/api/reload`) or restart the bridge. The new source shows up in `/api/sources` immediately.

### Pattern 2: Filesystem / static (fallback)

`adapter.kind: fallback` reads pre-built Impulse-schema JSON from disk. Useful for demos and for guaranteed-working offline mode. See `configs/sources/fallback-demo.yaml`.

### Pattern 3: Custom Python (last resort)

When a source can't be described declaratively (e.g. IIIF manifests, GraphQL), point at a Python class via `adapter.kind: custom`:

```yaml
adapter:
  kind: custom
  custom_class: "app.adapter.custom.iiif.IIIFManifestSource"
  base_url: "https://iiif.example.org/manifest/123.json"
```

Implement the class in `app/adapter/custom/<name>.py` — it just needs `collection_meta`, `async search()`, and `async get_asset()`. See `app/adapter/custom/iiif.py` for a worked example.

## Field mapping (JMESPath)

Each entry in `mapping.fields` resolves to a value for one Impulse asset field:

| Key | Meaning |
|---|---|
| `expr` | JMESPath against the raw item |
| `literal` | A constant value (no JMESPath) |
| `default` | Used if `expr` returns null / empty / missing |
| `transform` | `slugify` (readable, lossy), `base32` (opaque, reversible), `strip_html`, `file_title`, `lower`, `upper` |
| `map` | Value-to-value mapping, e.g. `{"IMAGE": "image/jpeg"}` |

`mapping.items_path` is a JMESPath to the array of items inside the upstream response. For object-shaped responses (e.g. MediaWiki's `query.pages`), use `values(query.pages)` to flatten to a list.

## Configured sources (out of the box)

| ID | Type | Notes |
|---|---|---|
| `bridge-demo` | fallback | Local placeholder assets in `data/fallback/`. Always works. |
| `wikimedia-commons-images` | rest | No API key needed. Public Commons search via MediaWiki API. |
| `europeana-public-domain-images` | rest | Needs `EUROPEANA_API_KEY` (free, register at [pro.europeana.eu](https://pro.europeana.eu/get-api)). |
| `smithsonian-open-access` | rest | Needs `SMITHSONIAN_API_KEY` (free, register at [api.data.gov](https://api.data.gov/signup/)). Default query targets items with online media. |
| `iiif-wellcome-vererbung` | custom (IIIF) | Single manuscript from Wellcome Collection. Copy + edit YAML to add more IIIF sources. |

## How requests flow

**Searching (web app):** `GET /api/sources/{id}/assets` → the registry finds the source → the source builds the upstream URL (auth, default query, search pattern, pagination) → the HTTP layer answers from the in-process TTL cache or calls the upstream (one retry on timeout) → JMESPath maps each item to an Impulse asset, filter rules drop incomplete ones.

**Adding to a collection:** the server looks each asset up in its source (usually a cache hit right after a search), makes relative URIs absolute and stores the asset as a snapshot in SQLite (`data/curator.db`).

**Serving Unity:** `GET /collections/{id}/assets` reads the snapshots — no upstream request.

## Project layout

```
impulse-bridge/
├── app/
│   ├── main.py              # FastAPI app, lifespan, error handlers, routers
│   ├── settings.py          # Pydantic settings (env-driven)
│   ├── loading.py           # (re)load source configs into the registry
│   ├── registry.py          # source id → Source map, atomic hot-swap
│   ├── cache.py             # TTL cache for raw upstream responses
│   ├── ratelimit.py         # per-client limits for anonymous writes
│   ├── errors.py            # BridgeError hierarchy + Impulse code mapping
│   ├── api/                 # Impulse API, web app API (sources, collections), files, health
│   ├── admin/               # admin API (source configs, collections)
│   ├── curation/            # curated collections: SQLite db, store, service
│   ├── config/              # YAML schema (pydantic) + loader (env expansion)
│   ├── transform/           # JMESPath engine + helpers
│   └── adapter/             # Source protocol, REST, fallback, factory, custom/iiif.py
├── configs/sources/*.yaml   # one file per source
├── data/fallback/           # local demo assets (manifest.json + media files)
├── data/curator.db          # curated collections (created on first start, not in git)
└── tests/
```

## Verification checklist

```bash
# 1. Tests
.venv\Scripts\python -m pytest -q

# 2. App starts; broken source configs are reported, not fatal
.venv\Scripts\python -m uvicorn app.main:app --port 8080
curl http://localhost:8080/health

# 3. Sources answer (bridge-demo works offline, Wikimedia needs no key)
curl 'http://localhost:8080/api/sources/bridge-demo/assets'
curl 'http://localhost:8080/api/sources/wikimedia-commons-images/assets?s=sunflower&c=3'
```

## Known limitations

- **Cache TTL is global**, not per-source (cachetools simplification). Per-source `cache.ttl_seconds` is currently read but effectively shares the global TTL. Replace with `redis` + per-key TTL if you grow out of single-process.
- **Smithsonian 3D content** is not reliably available via the openaccess REST API (3D models live in a separate Voyager-based portal at 3d.si.edu). The current config targets image-bearing items.
- **IIIF cross-provider search** is not standardized; the bundled IIIF adapter handles one manifest per YAML config. Add one YAML per IIIF collection of interest.
- **Single-asset lookups for sources without `asset_detail`** only work for assets that a recent search on this bridge returned (they are indexed for the cache TTL), or that appear in the default search result. All bundled REST sources configure `asset_detail`; see `docs/05-cookbook.md` ("Decision guide") for choosing between `{asset_id}`, `{asset_id_regex}` and `{asset_id_from_base32}` when adding a source.

## License

Internal — Impulse consortium.
