# IMPULSE Curator (impulse-bridge)

A collection creator for the [IMPULSE](https://euimpulse.eu/) cultural-heritage platform (EU project, Horizon Europe GA 101132704). Users search open archives (Europeana, Wikimedia Commons, IIIF manifests), pick assets, and save them as **curated collections**. Each curated collection is served to Impulse and its Unity clients through the Impulse Collections-and-Assets API.

Licences are checked throughout: only works whose licence IMPULSE accepts (an admin setting; by default public domain, CC0, CC BY and CC BY-SA) can be found, added and served, and every collection lists its licences and the credits they require. See [docs/02-architecture.md](docs/02-architecture.md#licences).

The archives are configured as **sources**: one YAML file per archive describes how to query and map it. Adding a new archive is normally a YAML-only change — no Python code required.

Developer and operator documentation: [`docs/`](docs/README.md).

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
     ┌──────────┼───────────────┐
     ▼          ▼               ▼
 Europeana  Wikimedia      IIIF manifests
            Commons        (e.g. Codex Manesse)
```

Asset content is **not** proxied — browsers and Unity load media directly from the original hosts. The Curator serves metadata and URLs. When an asset is added to a collection, its metadata is stored as a snapshot, so Unity requests never wait for an upstream archive.

## Quick start

```powershell
# 1. Create venv + install
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 2. Build the web app (Node.js 22.17+; in Windows PowerShell 5.1 use ";" instead of "&&")
cd frontend && npm ci && npm run build && cd ..

# 3. Copy env template and fill in any keys you have
cp .env.example .env
# Edit .env: EUROPEANA_API_KEY=...
# (.env.example sets BRIDGE_MAIL_LOG_ONLY=true: sign-in links are printed to the console)

# 4. Run
.venv\Scripts\python -m uvicorn app.main:app --port 8080
```

- `http://localhost:8080/` — the web app (without step 2 the API works, pages answer 503 "not built")
- `http://localhost:8080/admin` — the admin (no login locally; in production it sits behind basic auth)
- `http://localhost:8080/api/sources` — all configured sources

The database `data/curator.db` is created on the first start. For working on the web app, `npm run dev` in `frontend/` serves it on port 5173 and proxies the API to the backend on port 8080 — see [docs/06-operations.md](docs/06-operations.md).

## Endpoints

### Impulse API (consumed by Impulse / Unity)

| Method | Path | Purpose |
|---|---|---|
| GET | `/collections` | Curated collections an administrator listed |
| GET | `/collections/{id}` | A curated collection's metadata (every collection that is not locked, listed or not) |
| GET | `/collections/{id}/assets` | Its assets that are visible in Unity, in order. Supports `?s=<pattern>`, `?o=<offset>`, `?c=<count>` |
| GET | `/collections/{id}/asset/{asset_id}` | Single (visible) asset |
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
| 20 | Configuration error (e.g. missing API key, auth rejected) |
| 99 | Internal error |

The Impulse API reads SQLite only; codes 10–20 only appear in the web app API, where sources are searched.

### Web app API (consumed by the browser app)

Plain JSON; errors are `{"detail": "..."}` with a matching HTTP status. Errors that come from a source also carry the Impulse code: `{"detail": "...", "code": <int>}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | Public settings the web app needs (submission address, whether sign-in is available, size limit) |
| GET | `/api/sources` | Configured sources |
| GET | `/api/sources/{id}/assets` | Search a source: `?s=`, `?o=`, `?c=` (≤ 100), `?type=image` or `model`. Returns `items` and `next_offset` |
| GET | `/api/sources/{id}/assets/{asset_id}` | One asset of a source |
| POST | `/api/collections` | Create a collection from `items: [{source, asset_id}]`. Returns the **edit key** (once) |
| GET | `/api/collections?ids=a,b` | Overviews of several collections ("My collections") |
| GET | `/api/collections/{id}` | Public view; with edit access: editor view incl. hidden assets |
| PATCH / DELETE | `/api/collections/{id}` | Edit name, description, organization, email / delete |
| POST | `/api/collections/{id}/items` | Add assets |
| PATCH / DELETE | `/api/collections/{id}/items/{asset_id}` | Show/hide in Unity (`published`) / remove |
| PUT | `/api/collections/{id}/order` | Reorder |
| POST | `/api/collections/{id}/refresh` | Re-fetch all snapshots from the sources |
| POST | `/api/collections/{id}/submitted` | Record that it was submitted to the Impulse team |
| POST | `/api/collections/{id}/email-link` | Email the edit link to the collection's address (needs the edit key) |
| POST | `/api/collections/{id}/key` | Replace the edit key |
| POST | `/api/auth/login`, `/api/auth/verify` | Passwordless sign-in: request a one-time email link / redeem it for a session cookie |
| GET / POST | `/api/auth/me`, `/api/auth/logout` | Current session / sign out |
| GET | `/api/me/collections` | Collections created with the signed-in email address |

Write endpoints need `Authorization: Bearer <edit key>` or the session of the collection's email address, and are rate-limited per client.

### Admin API (behind basic auth in production)

The app has no admin login of its own: protect `/admin` (pages and API) at the reverse proxy.

- `/admin/api/collections/...` — list, `listed` / `disabled` (locked) flags, delete, issue a new edit key
- `/admin/api/sources`, `/admin/api/files/...`, `/admin/api/validate`, `/admin/api/test`, `/admin/api/templates`, `/admin/api/reload` — source configs as files: list, read, create, save (text kept verbatim), delete, live validation with line numbers, test runs (API keys masked), starter templates, reload from disk
- `/admin/api/settings`, `/admin/api/settings/test-email` — submission address and SMTP account (password write-only), test email

Full endpoint reference: [docs/06-operations.md](docs/06-operations.md#endpoint-reference).

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

A source is one YAML file in `configs/sources/`. The Curator loads every `*.yaml` / `*.yml` file in that directory at startup and on every reload; a broken file only disables its own source. The easiest way to write one is the admin's **Sources** editor (`/admin/sources`): live validation with line-marked problems, starter templates and a test run against the real archive — see [docs/04-admin-ui.md](docs/04-admin-ui.md). Full field reference: [docs/03-yaml-reference.md](docs/03-yaml-reference.md).

### Pattern 1: REST API (most cases)

For any external archive with a JSON search endpoint, write a YAML like this:

```yaml
collection:                   # describes the source (historical name)
  id: my-archive              # the source id: lowercase, digits, hyphens only (id-schema)
  name: "My Archive"          # shown in the web app
  description: "..."
  organization: "Provider"
  owner_id: "you@example.org"

adapter:
  kind: rest
  base_url: "https://api.myarchive.org"
  auth:
    type: query_param          # or "header" or "none"
    name: api_key
    value: "${MY_ARCHIVE_KEY}" # ${VAR} is expanded from the environment / .env
  timeout_seconds: 15
  default_query:               # sent with every search
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
    pattern_param: q           # the web app's search (?s=...) is sent as this param
    pattern_when_empty: "*"    # query used for an empty search
    # pattern_template: "({pattern}) AND license:cc0"   # optional: wraps every non-empty search

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

asset_detail:                  # recommended: adding assets to a collection looks them up again
  enabled: true
  path: "/items/{asset_id}"    # {asset_id} = the source's assetID verbatim
  query:                       # complete query for this endpoint (default_query is NOT merged in)
    expand: full
  # If assetID is slugified (irreversible) and the upstream search is Solr-based,
  # look the asset up case-insensitively instead — see configs/sources/europeana.yaml:
  #   path: "/search"
  #   query: { q: "id_field:/{asset_id_regex}/" }

cache:
  ttl_seconds: 600
```

Saving in the admin hot-reloads all sources. For a file written to disk directly, use **Reload from disk** on the admin's Sources page (`POST /admin/api/reload`) or restart. The new source shows up in `/api/sources` and the web app immediately.

### Pattern 2: Filesystem / static (fallback)

`adapter.kind: fallback` reads pre-built Impulse-schema JSON from disk. Useful for demos and for guaranteed-working offline mode. Files next to the manifest are served at `/sources/{id}/files/<path>`. See `configs/sources/fallback-demo.yaml`.

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
| `bridge-demo` | fallback | Three glTF demo models (textured cube, sphere, column) and an image in `data/fallback/`, CC0, regenerated by `scripts/make_demo_assets.py`. Always works, also offline. |
| `wikimedia-commons-images` | rest | No API key needed. Public Commons search via MediaWiki API. |
| `europeana-public-domain-images` | rest | Needs `EUROPEANA_API_KEY` (free, register at [pro.europeana.eu](https://pro.europeana.eu/get-api)). |
| `iiif-codex-manesse` | custom (IIIF) | The Codex Manesse from Heidelberg University Library (public domain). Copy + edit YAML to add more IIIF sources. |
| `smk-open-art` | rest | No API key needed. Public-domain works of the Danish National Gallery (SMK Open), images via IIIF. |
| `zenodo-3d-models` | rest | No API key needed. Openly licensed glTF models (.glb) from Zenodo records, with the record's preview image. |

## How requests flow

**Searching (web app):** `GET /api/sources/{id}/assets` → the registry finds the source → the source builds the upstream URL (auth, default query, search pattern, pagination) → the HTTP layer answers from the in-process TTL cache or calls the upstream (one retry on timeout) → JMESPath maps each item to an Impulse asset, filter rules drop incomplete ones.

**Adding to a collection:** the server looks each asset up in its source (usually a cache hit right after a search), makes relative URIs absolute and stores the asset as a snapshot in SQLite (`data/curator.db`).

**Serving Unity:** `GET /collections/{id}/assets` reads the snapshots — no upstream request.

## Project layout

```
impulse-bridge/
├── app/
│   ├── main.py              # FastAPI app, lifespan, CORS, security headers, error handlers, routers
│   ├── settings.py          # Pydantic settings (BRIDGE_* env vars)
│   ├── loading.py           # (re)load source configs into the registry
│   ├── registry.py          # source id → Source map, atomic hot-swap
│   ├── cache.py             # TTL cache for raw upstream responses
│   ├── ratelimit.py         # per-client limits for anonymous writes
│   ├── errors.py            # BridgeError hierarchy + Impulse code mapping
│   ├── storage.py           # opens SQLite, provides the stores to endpoints
│   ├── site_settings.py     # admin-edited settings (submission address, SMTP)
│   ├── auth.py, mail.py     # passwordless sign-in (tokens, sessions), SMTP
│   ├── frontend.py          # serves the web app build
│   ├── api/                 # Impulse API, web app API (sources, collections, auth, config), files, health
│   ├── admin/               # admin API (sources, files + validation, collections, settings)
│   ├── curation/            # curated collections: SQLite db + migrations, store, service
│   ├── config/              # YAML schema (pydantic) + loader (env expansion)
│   ├── transform/           # JMESPath engine + helpers
│   └── adapter/             # Source protocol, REST, fallback, factory, custom/iiif.py
├── frontend/                # web app: SvelteKit 3 + Svelte 5, static build → frontend/build
├── configs/sources/*.yaml   # one file per source
├── data/fallback/           # local demo assets (manifest.json + media files)
├── data/curator.db          # curated collections, settings, sessions (created on first start, not in git)
├── deploy/                  # Dockerfile (multi-stage), docker-compose.yml (Traefik), host bootstrap
├── docs/                    # developer and operator documentation
└── tests/                   # pytest
```

## Verification checklist

```bash
# 1. Backend tests (no network needed)
.venv\Scripts\python -m pytest -q

# 2. Web app: unit tests, type check, lint
cd frontend && npm test && npm run check && npm run lint && cd ..

# 3. App starts; broken source configs are reported, not fatal
.venv\Scripts\python -m uvicorn app.main:app --port 8080
curl http://localhost:8080/health

# 4. Sources answer (bridge-demo works offline, Wikimedia needs no key)
curl 'http://localhost:8080/api/sources/bridge-demo/assets'
curl 'http://localhost:8080/api/sources/wikimedia-commons-images/assets?s=sunflower&c=3'
```

## Deployment

`deploy/Dockerfile` builds the web app in a Node stage and runs it with the backend in a Python stage; `deploy/docker-compose.yml` routes the container through Traefik, with HTTPS and basic auth on `/admin`, `/docs` and `/openapi.json`. `configs/` and `data/` (including `data/curator.db` — back it up) are bind-mounted from the host. `BRIDGE_PUBLIC_BASE_URL` must be the public https address. Step by step: [docs/07-deployment.md](docs/07-deployment.md).

## Known limitations

- **Single process.** The source registry, the upstream cache and the rate-limit counters live in memory, and the database is a local SQLite file: run one uvicorn worker / one container.
- **Cache TTL is global**, not per-source (cachetools simplification). Per-source `cache.ttl_seconds` is currently read but effectively shares the global TTL. Replace with `redis` + per-key TTL if you grow out of single-process.
- **IIIF cross-provider search** is not standardized; the bundled IIIF adapter handles one manifest per YAML config. Add one YAML per IIIF collection of interest.
- **Single-asset lookups for sources without `asset_detail`** only work for assets that a recent search on this server returned (they are indexed for the cache TTL), or that appear in the default search result. All bundled REST sources configure `asset_detail`; see `docs/05-cookbook.md` ("Decision guide") for choosing between `{asset_id}`, `{asset_id_regex}` and `{asset_id_from_base32}` when adding a source.

## License

Internal — Impulse consortium.
