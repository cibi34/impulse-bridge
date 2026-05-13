# Impulse Bridge

An adapter bridge between the [Impulse 3D cultural-heritage platform](https://impulse-project.eu/) and external archives (Europeana, Wikimedia Commons, IIIF, Smithsonian Open Access).

The bridge presents itself to Impulse as just another asset-service node speaking the Impulse Collections-and-Assets API. Internally, each "virtual collection" is backed by a YAML config that describes how to query and map an external archive. Adding a new archive is normally a YAML-only change — no Python code required.

## What it does

```
            ┌──────────────┐    /collections                  ┌──────────────────┐
Unity ────► │   Impulse    │ ─────────────────────────────►  │   Impulse        │
            │   Platform   │ ◄─────────────────────────────  │   Bridge         │
            └──────────────┘    {code, message, data}         │  (this project)  │
                                                              └────────┬─────────┘
                                                                       │
                                                  ┌────────────────────┼────────────────────┐
                                                  ▼                    ▼                    ▼
                                          ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                                          │  Europeana   │    │  Wikimedia   │    │  Smithsonian │
                                          │     API      │    │  Commons API │    │  Open Access │
                                          └──────────────┘    └──────────────┘    └──────────────┘
```

Asset content is **not** proxied — Unity downloads bytes directly from the original host. The bridge only serves metadata and resolved URLs.

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

Visit `http://localhost:8080/collections` — you should see all configured virtual collections.

## Endpoints (Impulse-compatible)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, lists registered source IDs |
| GET | `/collections` | List all virtual collections |
| GET | `/collections/{id}` | Single collection's metadata |
| GET | `/collections/{id}/assets` | Search assets in a collection. Supports `?s=<pattern>`, `?o=<offset>`, `?c=<count>` |
| GET | `/collections/{id}/asset/{asset_id}` | Single asset detail |

All responses follow the Impulse envelope `{code, message, data}`. Codes used:

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

## Example requests

```bash
# Wikimedia Commons, search "van gogh", first 3 results
curl 'http://localhost:8080/collections/wikimedia-commons-images/assets?s=van+gogh&c=3'

# Pagination: next page
curl 'http://localhost:8080/collections/wikimedia-commons-images/assets?s=van+gogh&o=3&c=3'

# Single asset by ID
curl 'http://localhost:8080/collections/wikimedia-commons-images/asset/151972'

# IIIF manifest assets (manuscript pages as images)
curl 'http://localhost:8080/collections/iiif-wellcome-vererbung/assets?c=3'

# Local fallback demo (always works, even offline)
curl 'http://localhost:8080/collections/bridge-demo/assets'
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
  path: "/items/{asset_id}"
  query:
    expand: full

cache:
  ttl_seconds: 600
```

Restart the bridge. The new collection shows up in `/collections` immediately.

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
| `transform` | `slugify`, `strip_html`, `lower`, `upper` |
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

1. Impulse / Unity calls `GET /collections/{id}/assets?s=foo&o=10&c=20`.
2. FastAPI routes the request; the registry looks up the Source by `id`.
3. The Source builds an upstream URL: auth params, default query, search-pattern translation, pagination translation.
4. The HTTP layer hits the cache (in-process TTL keyed by source+path+sorted-params). On miss, calls the upstream; one retry on timeout.
5. Raw JSON is cached, then handed to the transform engine.
6. JMESPath extracts each item; the mapping produces an Impulse asset dict; filter rules drop incomplete or wrong-mime items.
7. Result is wrapped in `{code, message, data}` and returned.

## Project layout

```
impulse-bridge/
├── app/
│   ├── main.py              # FastAPI app + lifespan + error handlers
│   ├── settings.py          # Pydantic settings (env-driven)
│   ├── registry.py          # collection_id → Source map
│   ├── cache.py             # TTL cache for raw upstream responses
│   ├── errors.py            # BridgeError hierarchy + Impulse code mapping
│   ├── logging_conf.py
│   ├── api/                 # HTTP layer (collections, assets, health, responses)
│   ├── config/              # YAML schema (pydantic) + loader (env expansion)
│   ├── transform/           # JMESPath engine + helpers
│   └── adapter/
│       ├── base.py          # Source protocol
│       ├── rest.py          # GenericRestSource (the 95% case)
│       ├── fallback.py      # FilesystemSource (demo / offline)
│       ├── factory.py       # builds the right Source from a SourceConfig
│       └── custom/iiif.py   # Example custom adapter
├── configs/sources/*.yaml   # one file per virtual collection
├── data/fallback/           # local demo assets (manifest.json + media files)
├── pyproject.toml
├── .env.example
└── tests/                   # (reserved for future unit tests)
```

## Verification checklist

Quick sanity check after any change:

```bash
# 1. App starts (Pydantic validates YAMLs — bad config = startup error)
.venv\Scripts\python -m uvicorn app.main:app --port 8080

# 2. All sources register
curl http://localhost:8080/health
curl http://localhost:8080/collections

# 3. Fallback works offline
curl http://localhost:8080/collections/bridge-demo/assets

# 4. A no-key source works (Wikimedia)
curl 'http://localhost:8080/collections/wikimedia-commons-images/assets?s=sunflower&c=3'

# 5. Asset URLs actually load
curl -I "$(curl -s 'http://localhost:8080/collections/wikimedia-commons-images/assets?s=sunflower&c=1' | python -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["assetURI"])')"
```

## Known limitations

- **Cache TTL is global**, not per-source (cachetools simplification). Per-source `cache.ttl_seconds` is currently read but effectively shares the global TTL. Replace with `redis` + per-key TTL if you grow out of single-process.
- **Smithsonian 3D content** is not reliably available via the openaccess REST API (3D models live in a separate Voyager-based portal at 3d.si.edu). The current config targets image-bearing items.
- **IIIF cross-provider search** is not standardized; the bundled IIIF adapter handles one manifest per YAML config. Add one YAML per IIIF collection of interest.
- **Europeana `get_asset` uses search-and-find fallback** because record IDs are paths that slug-ify irreversibly. Works fine when the asset is in the first page of the default search.

## License

Internal — Impulse consortium.
