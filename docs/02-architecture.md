# 02 — Architecture

How the Curator is built, how requests travel through it, and how it meets the Impulse Collections-and-Assets specification.

## Components

```
                    ┌───────────────────────────────────────────────────────────────┐
  Browser ─────────►│  FastAPI app (app/main.py)                                    │
  (web app, admin)  │                                                               │
                    │  Web app (frontend/build, app/frontend.py)                    │
  Unity / Impulse ─►│                                                               │
                    │  Impulse API ─────────┐      Web app API      Admin API       │
                    │  /collections/…       │      /api/…           /admin/api/…    │
                    │                       │        │    │            │     │      │
                    │                       ▼        │    ▼            │     ▼      │
                    │   ┌───────────────────────┐    │  ┌──────────┐   │  YAML files│
                    │   │ Curation              │◄───┘  │ Registry │◄──┘  configs/  │
                    │   │ store + service       │──────►│ id→Source│      sources/  │
                    │   │ (app/curation/)       │snap-  └────┬─────┘                │
                    │   └──────────┬────────────┘shots       │                      │
                    │              ▼                         ▼                      │
                    │   SQLite data/curator.db      Adapters (REST, fallback, IIIF) │
                    │   collections, items,         + transform engine (JMESPath)   │
                    │   site settings, sign-in      + TTL cache (raw upstream JSON) │
                    └────────────────────────────────────────┬──────────────────────┘
                                                             ▼ HTTPS
                                            Europeana, Wikimedia, Smithsonian, IIIF …
```

## Module layout

```
app/
├── main.py              # FastAPI app, lifespan, CORS, security headers, error handlers, routers
├── settings.py          # Pydantic settings (BRIDGE_* env vars / .env)
├── loading.py           # (re)load all source configs into the registry
├── registry.py          # source id → Source map; atomic swap; RETIRE_GRACE_SECONDS
├── cache.py             # in-process TTL cache for raw upstream responses
├── errors.py            # BridgeError hierarchy with Impulse codes
├── storage.py           # opens SQLite and hands the stores to endpoints (dependencies)
├── site_settings.py     # admin-edited settings (submission address, SMTP) in SQLite
├── auth.py              # login tokens and sessions (passwordless sign-in)
├── mail.py              # SMTP sending, log-only mode
├── ratelimit.py         # per-client sliding-window limits
├── frontend.py          # serves the SvelteKit build (prerendered pages + SPA fallback)
├── logging_conf.py
│
├── api/
│   ├── collections.py   # Impulse API, served from curated collections
│   ├── params.py        # o/c parsing per the spec (illegal values → everything)
│   ├── responses.py     # impulse_response(): the {code, message, data} envelope
│   ├── health.py        # /health
│   ├── files.py         # /sources/{id}/files/{path}: local files of fallback sources
│   ├── sources.py       # web app API: search sources
│   ├── web_collections.py  # web app API: create / read / edit curated collections
│   ├── auth.py          # web app API: sign-in by email link, sessions, /api/me/collections
│   └── site.py          # web app API: /api/config
│
├── admin/
│   ├── api.py           # sources by id, test runs, templates, reload
│   ├── files.py         # source configs as files, live validation
│   ├── validation.py    # YAML/schema validation with line numbers
│   ├── collections.py   # list, lock, delete curated collections; new edit key
│   └── settings.py      # site settings, test email
│
├── curation/
│   ├── db.py            # SQLite connection, versioned migrations
│   ├── store.py         # data access (collections, items)
│   └── service.py       # ids, edit keys, snapshots, Impulse serialization
│
├── config/
│   ├── schema.py        # Pydantic models of a source YAML
│   └── loader.py        # YAML parsing, ${ENV_VAR} expansion, tolerant load_all()
│
├── transform/
│   ├── engine.py        # transform_item(), extract_items()
│   └── helpers.py       # slugify, base32_id, slug_to_regex, strip_html, file_title, matches_pattern …
│
└── adapter/
    ├── base.py          # Source protocol, SearchPage, search_page()
    ├── factory.py       # SourceConfig → Source
    ├── rest.py          # GenericRestSource
    ├── fallback.py      # FallbackSource (local JSON manifest)
    └── custom/iiif.py   # IIIFManifestSource

frontend/                # SvelteKit 3 + Svelte 5, adapter-static
├── src/routes/(site)/   # prerendered: home, legal pages, credits, report
├── src/routes/(app)/    # SPA: explore, c/[id], c/[id]/edit, my, signin
├── src/routes/(admin)/  # SPA: admin, admin/sources, admin/settings
└── src/lib/             # API client, components, stores
```

Other top-level folders:

```
configs/sources/*.yaml   # one file per source
data/fallback/           # demo files for the bridge-demo source
data/curator.db          # curated collections, site settings, sign-in (created at first start)
deploy/                  # Dockerfile, docker-compose.yml, Traefik, host bootstrap
tests/                   # pytest
docs/                    # this documentation
```

## Three API surfaces

| Surface | Paths | Response shape | Consumer | CORS |
|---|---|---|---|---|
| Impulse API | `/collections…`, `/health` | `{code, message, data}` envelope | Impulse platform, Unity | yes (`BRIDGE_CORS_ALLOW_ORIGINS`) |
| Web app API | `/api/…` | Plain JSON; errors `{"detail": …}` | The bundled web app | no — same origin only |
| Admin API | `/admin/api/…` | Plain JSON; errors `{"detail": …}` | The admin pages | no — same origin only |

Also served: the web app itself (every path that is not a backend path), local fallback files at `/sources/{id}/files/{path}` (CORS-enabled, like the Impulse API), and FastAPI's `/docs` and `/openapi.json` (ReDoc is switched off).

The CORS middleware ([`app/main.py`](../app/main.py)) skips every path that starts with `/api/` or `/admin`: those carry sessions and edit keys, so no other site gets CORS access to them.

## The contract with Impulse

The Curator is a pure server to Impulse: Impulse calls it, it never calls Impulse. The contract is [`Collections-and-assets-schema,-discovery-and-access.md`](../Collections-and-assets-schema,-discovery-and-access.md).

### Endpoint mapping

| Specification endpoint | Route | Backed by |
|---|---|---|
| `GET <platform_api>/collections` | `GET /collections` | `CollectionStore.list_listed()` — listed and not locked, ordered by name |
| `GET <collection_uri>` | `GET /collections/{id}` | `CollectionStore.get()` — any collection that is not locked |
| `GET <collection_uri>/assets` | `GET /collections/{id}/assets` | items with `published = 1`, in the editor's order |
| `GET <collection_uri>/asset/<asset_id>` | `GET /collections/{id}/asset/{asset_id}` | one item; hidden items are *Asset not found* |

All four read SQLite only — no upstream request is made while serving Impulse.

- **Search** `?s=`: case-insensitive match over `title`, `description`, `subject`, `creator`, `contributor`, `type` and `assetID`. `*` separates chunks that must all appear in order; empty or `*` matches everything (`matches_pattern()` in [`app/transform/helpers.py`](../app/transform/helpers.py)).
- **Paging** `?o=&c=`: offset and count over the matching assets. Non-integers, a negative offset or a count below 1 return the entire result set ([`app/api/params.py`](../app/api/params.py)).

### What Impulse sees

Collection metadata (`impulse_collection()` in [`app/curation/service.py`](../app/curation/service.py)):

| Field | Value |
|---|---|
| `id` | The collection id, e.g. `masters-of-light-k3m9x2` |
| `uri` | `<BRIDGE_PUBLIC_BASE_URL>/collections/<id>` |
| `name`, `description` | As the editor set them |
| `organization` | As set via the API, else `BRIDGE_DEFAULT_ORGANIZATION` (the web app does not ask for it) |
| `owner_id` | `BRIDGE_COLLECTION_OWNER_ID` for every collection — never the creator's email, because collection metadata is public |
| `published` | Always `1` |

Assets are the stored snapshot with two fields overridden: `assetID` (the collection's own id for the item) and `published: 1`.

### Response envelope and codes

```json
{"code": 0, "message": "OK", "data": <list-or-object>}
```

`data` is a list for `/collections` and `/assets`, an object for a single collection or asset. Errors raised as `BridgeError` are answered with `data: []` and the matching code ([`app/api/responses.py`](../app/api/responses.py)).

| `code` | Meaning | HTTP status | Typical cause |
|---|---|---|---|
| 0 | OK | 200 | — |
| 1 | Collection not found | 404 | Unknown or locked collection; unknown source id (web app API) |
| 2 | Asset not found | 404 | Unknown or hidden asset; asset not found in a source |
| 10 | Upstream source unavailable | 503 | Network error, timeout, upstream 5xx |
| 11 | Upstream rate limit reached | 503 | Upstream answered 429 |
| 12 | Upstream returned malformed data | 502 | Non-JSON, or a 4xx other than 401/403 |
| 20 | Configuration error | 500 | Missing or rejected API key (upstream 401/403), unbuildable source |
| 99 | Internal error | 500 | Unhandled exception (logged with traceback) |

Codes 10–20 only appear in the web app API (source searches and lookups): the Impulse API never calls upstream.

## Curated collections

### Data model

SQLite file `data/curator.db` (`BRIDGE_DATABASE_PATH` overrides it). One connection per process, serialized by a lock, WAL journal, foreign keys on. The schema version is `PRAGMA user_version`; [`app/curation/db.py`](../app/curation/db.py) applies missing entries of `MIGRATIONS` at start. Applied migrations are never edited — add a new one.

| Table | Content |
|---|---|
| `collections` | id, name, description, organization, `owner_email` (optional, never public), `edit_key_hash`, `listed`, `disabled` (locked), `submitted_at`, `created_at`, `updated_at` |
| `collection_items` | collection id, `asset_id` (collection-internal), `source_id` + `source_asset_id` (unique per collection), `position`, `published`, `asset` (snapshot JSON), `added_at`, `refreshed_at` |
| `site_settings` | key/value JSON: submission address, SMTP account |
| `login_tokens` | SHA-256 hashes of one-time sign-in tokens, email, expiry, `used_at` |
| `sessions` | SHA-256 hashes of session ids, email, expiry |

Deleting a collection deletes its items (`ON DELETE CASCADE`).

### Ids

| Id | Format | Source |
|---|---|---|
| Collection id | `<name slug, ≤ 48 chars>-<6 random chars>`, e.g. `masters-of-light-k3m9x2` | `new_collection_id()` — readable and unguessable; alphabet without `0/o/1/l` |
| Item `assetID` | `<title slug>-<first 6 hex of sha1(source_id, source_asset_id)>` | `item_asset_id()` — stable for the same source asset; longer prefix on collision |
| Edit key | 24 random bytes, URL-safe | `new_edit_key()` — only its SHA-256 hash is stored |

### Snapshots

When assets are added (`POST /api/collections`, `POST /api/collections/{id}/items`), `snapshot_items()` looks each one up with `source.get_asset()` — usually a cache hit right after the search that found it — at most 6 lookups in parallel. The result is stored as the item's `asset`.

`absolutize()` makes relative `assetURI` / `previewURI` values (fallback sources) absolute: `<BRIDGE_PUBLIC_BASE_URL>/sources/<source id>/files/<path>`. Per the spec, relative URIs would resolve against the *collection* URI, which a curated collection does not share with its source.

Assets that cannot be fetched (unknown source, asset not found, upstream error) are reported in `failed` and skipped; the rest is stored.

`POST /api/collections/{id}/refresh` re-fetches every snapshot. Assets that are gone upstream keep their last snapshot and are reported.

## Request flows

### Searching a source (web app)

`GET /api/sources/wikimedia-commons-images/assets?s=van+gogh&c=24`:

```
1. app/api/sources.py   source = registry.get(id)          unknown id → 404, code 1
                        o/c parsed; c defaults to 24, capped at 100
2. adapter/base.py      search_page(source, …)
3. adapter/rest.py      _build_params():
                          default_query + auth query param
                          search.query: pattern_param ← s (wildcards translated,
                            pattern_template applied) or pattern_when_empty
                          pagination: offset/limit or page/size
                        _http_get(): cache hit → raw JSON; miss → GET upstream
                          (one retry after a timeout), cache the raw JSON
4. transform/engine.py  extract_items(items_path) → transform_item() per item
                          → filter (allowed_content_types, drop_if_missing)
                        each mapped asset's raw item is indexed by assetID in the cache
5. app/api/sources.py   absolutize() relative URIs; optional ?type=image|model filter
                        → {source, items, offset, next_offset}
```

`next_offset` is `offset + <items the upstream returned>` — counted before filtering — or `null` when the upstream returned fewer items than requested. A page can therefore hold fewer than `c` items.

### Creating a collection

`POST /api/collections` with `{name, description?, organization?, email?, items: [{source, asset_id}]}`:

1. Rate limit (30 per client and hour), body validation, size check (`BRIDGE_MAX_ASSETS_PER_COLLECTION`).
2. Snapshots of all items (see above), duplicates removed.
3. New collection id and edit key; one transaction inserts the collection and its items.
4. Response `201` with the editor view of the collection, the **edit key** (only here, never again) and `failed`.

### Serving Unity

`GET /collections/{id}/assets` → `CollectionStore.get()` (unknown or locked → code 1) → `items(published_only=True)` → `matches_pattern()` → slice by `o`/`c` → envelope. No upstream request.

## Sources

### The Source protocol

[`app/adapter/base.py`](../app/adapter/base.py):

```python
class Source(Protocol):
    collection_meta: dict      # id, name, description, organization, … from the YAML `collection:` block
    async def search(query, offset, count) -> list[dict]       # Impulse asset dicts
    async def get_asset(asset_id) -> dict                       # or raise AssetNotFound
```

Adapters may also implement `search_page()` to report how many items the upstream returned before filtering (the REST adapter does); `search_page()` in `base.py` falls back to `search()` for the others. Adapters with an `aclose()` are closed when they are replaced or at shutdown.

### Adapter kinds

| `adapter.kind` | Class | Search | Single asset |
|---|---|---|---|
| `rest` | `GenericRestSource` | Upstream search API, configured in YAML | Recently searched items, then `asset_detail`, else scan the default search page |
| `fallback` | `FallbackSource` | `matches_pattern()` over a local JSON manifest | By `assetID` from the manifest |
| `custom` | any class, e.g. `IIIFManifestSource` | Adapter-defined (IIIF: `title` + `identifier`, `*` chunks) | Adapter-defined |

`GenericRestSource` also handles auth (`query_param` or `header`), the error mapping (429 → 11, 401/403 → 20, 5xx/network → 10, 404 → 12 or *Asset not found* in a detail lookup, other 4xx → 12) and keeps `last_upstream_url` / `last_raw_response` for the admin test run. It sends a descriptive `User-Agent` with the public base URL as contact (Wikimedia's robot policy requires one).

`IIIFManifestSource` reads one manifest (Presentation API v2 or v3); every canvas with a painting image becomes an asset, with Image API URLs for full size and a 400 px preview. The parsed manifest is kept for the lifetime of the source, i.e. until the next reload.

### Single-asset lookup (REST)

1. **Recently searched:** every search indexes the raw upstream item under its mapped `assetID` (cache TTL). A hit is re-mapped with the current mapping — no upstream call. This is what makes "search, select, add to a collection" fast.
2. **`asset_detail`** (if enabled): a configured upstream request with the placeholders `{asset_id}`, `{asset_id_regex}`, `{asset_id_from_base32}`; the item whose mapped `assetID` equals the request wins. See [03 — YAML reference](03-yaml-reference.md#asset_detail).
3. **Otherwise:** scan the default search result (no query) for the id.

### Cache

One in-process `cachetools.TTLCache` (1024 entries) keyed by `sha1(source id, path, sorted params)`. It holds **raw upstream JSON**, so mapping changes take effect on the next request without a flush. The TTL is global (`BRIDGE_DEFAULT_CACHE_TTL`, default 600 s); per-source `cache.ttl_seconds` is read but not applied (see [03](03-yaml-reference.md#cache)). The cache is per process and lost on restart, which costs nothing but upstream requests.

## Loading and hot reload

[`app/loading.py`](../app/loading.py) runs at startup and after every admin save, delete and "Reload from disk":

1. `load_all()` parses every `*.yaml` / `*.yml` in `BRIDGE_CONFIG_DIR` (sorted by filename), expands `${ENV_VAR}` from the environment and validates against `SourceConfig`. A broken file is recorded as an error and skipped — it never stops the app or the other sources.
2. Each valid config is built (`build_source()`). Duplicate ids (the first file wins) and configs that fail to build (missing fallback manifest, unknown custom class, …) are recorded as errors, too.
3. `registry.swap()` replaces the whole map at once: requests see the old or the new set of sources, never a half-loaded one.
4. Replaced sources are closed after `RETIRE_GRACE_SECONDS` (60 s, [`app/registry.py`](../app/registry.py)) so running requests can finish.

Errors appear in the admin's Sources list (red dot and message) and in the log. Curated collections are unaffected by reloads: they are served from SQLite. Only refreshing snapshots and fallback file URLs (`/sources/{id}/files/…`) need the source to exist under the same id.

## Access model

| Who | How | Can |
|---|---|---|
| Anyone | — | Search sources, read collections (visible assets only), create collections (rate-limited) |
| Holder of the edit key | `Authorization: Bearer <key>`; the web app keeps it in `localStorage` and in the edit link's fragment (`#key=…`, never sent to the server in the URL) | Edit, reorder, hide, refresh, delete, replace the key, email the edit link |
| Signed-in creator | Session cookie after a one-time email link; only for the email address the collection was created with | Same as the key holder, except emailing the edit link; writes must come from `BRIDGE_PUBLIC_BASE_URL`'s origin |
| Admin | Basic auth at the reverse proxy (the app itself has no admin login) | Everything under `/admin`: list, lock, delete collections, new edit keys, sources, settings |

A locked collection refuses every edit (403) and is hidden from the Impulse API and from other visitors.

Sign-in details: links go only to addresses that collections were created with (at most 5 per address and hour; the response never tells whether one was sent), are valid for 15 minutes and once. Sessions last 30 days. The cookie is `HttpOnly`, `SameSite=Lax`, and — when `BRIDGE_PUBLIC_BASE_URL` is `https://…` — `Secure` with the `__Host-` prefix ([`app/auth.py`](../app/auth.py)).

Rate limits are listed in [06 — Operations](06-operations.md#rate-limits).

## The web app

`frontend/` is a SvelteKit app built with `adapter-static` into `frontend/build` (`BRIDGE_FRONTEND_DIR`). [`app/frontend.py`](../app/frontend.py) serves it from FastAPI, after all API routes:

- Prerendered pages (home, `/legal/*`, `/credits`, `/report`) are plain files.
- App pages (`/explore`, `/my`, `/signin`, `/c/{id}`, `/c/{id}/edit`, `/admin…`) get the SPA fallback `200.html` with status 200; unknown paths get it with status 404.
- Backend paths (`/api/`, `/admin/api/`, `/collections`, `/sources/`, `/health`, `/docs`, `/openapi.json`) never fall through to the web app.
- Caching: `/_app/immutable/…` is `immutable` for a year, HTML `no-cache`, other static files one day.
- Without a build, the API still works and every page answers 503 "The web app has not been built".

The build sets a hash-based Content-Security-Policy; [`app/main.py`](../app/main.py) adds `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `Permissions-Policy`, `Cross-Origin-Opener-Policy` and — for an `https://` public base URL — HSTS.

Pages: `/` (home with an interactive how-to), `/explore`, `/c/{id}` (public view), `/c/{id}/edit`, `/my`, `/signin`, `/legal/{imprint,privacy,terms,accessibility}`, `/credits`, `/report`, `/admin`, `/admin/sources`, `/admin/settings`.

## What is stored where

| State | Where | Survives a restart |
|---|---|---|
| Curated collections, snapshots | SQLite `data/curator.db` | yes — back it up |
| Site settings (submission address, SMTP) | SQLite | yes |
| Sign-in tokens, sessions | SQLite (hashes only) | yes |
| Source configs | `configs/sources/*.yaml` | yes |
| API keys, deployment settings | environment / `.env` | yes |
| Source registry, upstream cache, rate-limit counters | process memory | no (rebuilt) |
| Edit keys of a visitor's collections, current selection | the visitor's `localStorage` | in that browser |

Because of the in-memory registry, cache and rate limits, the Curator runs as **one process** (one uvicorn worker, one container).

---

_Last verified against [`Collections-and-assets-schema,-discovery-and-access.md`](../Collections-and-assets-schema,-discovery-and-access.md) v3.11 (28/11/2025) and the code, October 2026._

_Continue to [03 — YAML reference](03-yaml-reference.md)._
