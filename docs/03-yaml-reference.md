# 03 — YAML reference

Every source (archive) is described by **one YAML file** in `configs/sources/` (`BRIDGE_CONFIG_DIR`). This document is the complete reference for that file. Each section maps to a Pydantic model in [`app/config/schema.py`](../app/config/schema.py); unknown fields are rejected (`extra="forbid"`), and the admin's Sources editor shows such errors on the offending line.

## Top-level structure

```yaml
collection: ...     # describes the source: id, name, … (required)
adapter: ...        # how to reach the upstream (required)
search: ...         # search pattern and pagination (REST only)
mapping: ...        # JMESPath rules: upstream JSON → Impulse asset
filter: ...         # drop rules applied after mapping
asset_detail: ...   # optional single-asset lookup (REST only)
cache: ...          # cache TTL (advisory, see below)
```

`collection` and `adapter` are required; every other block has defaults.

## Environment variables

Any string value can reference an environment variable as `${VAR}` (uppercase letters, digits, underscores). Values come from the process environment and `.env`, read once at start. A missing variable expands to an empty string — for an API key that usually means an upstream 401/403, reported as code `20`.

Never write a secret into a YAML file; reference it. The admin test run masks query-parameter API keys as `***` in the URL it shows, and replaces the key wherever it appears in the raw response.

---

## `collection`

Describes the **source**. The block keeps its historical name; it no longer becomes an Impulse collection. `name`, `description` and `organization` are what the web app shows in its source picker (`GET /api/sources`).

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | The source id. Impulse id-schema: lowercase letters, digits and hyphens, starting with a letter or digit. Used in `/api/sources/{id}/…` and `/sources/{id}/files/…`, and stored with every curated asset taken from this source. Must be unique across all files. |
| `name` | string | yes | Display name in the web app. |
| `description` | string | no | One or two sentences; shown in the web app. |
| `organization` | string | yes | The institution behind the archive. |
| `owner_id` | string | yes | Contact of whoever maintains this config. Required by the schema; not published anywhere. |
| `published` | int | no | Accepted for compatibility (default `1`); **currently has no effect** — a source with `published: 0` is still offered. To take a source offline, delete its file or move it out of the config directory. |

Changing a source's `id` is a rename: existing curated collections keep their snapshots, but "Update from sources" can no longer find those assets, and fallback file URLs stored as `/sources/<old id>/files/…` stop working.

```yaml
collection:
  id: europeana-public-domain-images
  name: "Europeana Public Domain Images"
  description: "Open-licensed images aggregated from European cultural heritage institutions via Europeana."
  organization: "Europeana Foundation"
  owner_id: "bridge@impulse.eu"
```

---

## `adapter`

| Field | Type | Default | For kind | Description |
|---|---|---|---|---|
| `kind` | enum | — | all | `rest` (generic REST API), `fallback` (local files) or `custom` (Python class). |
| `base_url` | string | — | rest, custom | Base URL of the API. Required for `rest`. For the IIIF adapter: the manifest URL. |
| `auth` | block | `type: none` | rest | See below. |
| `timeout_seconds` | float | `10.0` | rest, custom | HTTP timeout. The REST adapter retries once after a timeout. |
| `default_query` | dict[str, str] | `{}` | rest | Query parameters sent with every **search** request (static filters, format flags). Not sent with `asset_detail` requests. |
| `manifest_path` | string | — | fallback | JSON file with pre-mapped Impulse assets. Relative paths resolve against the working directory (the project root; `/app` in the Docker image). |
| `static_mount` | bool | `true` | fallback | Serve the files next to the manifest at `/sources/{id}/files/<path>`, so relative `assetURI` / `previewURI` values work. |
| `custom_class` | string | — | custom | Dotted path to a class implementing the `Source` protocol, e.g. `app.adapter.custom.iiif.IIIFManifestSource`. |

### `adapter.auth`

| Field | Type | Description |
|---|---|---|
| `type` | `none` \| `query_param` \| `header` | Default `none`. |
| `name` | string | Query parameter or header name. |
| `value` | string | The secret, normally `"${VAR}"`. |

A `query_param` key is added to search **and** detail requests; a `header` value is sent with every request.

### Examples

REST API with the key in a query parameter (Europeana):

```yaml
adapter:
  kind: rest
  base_url: "https://api.europeana.eu"
  auth:
    type: query_param
    name: wskey
    value: "${EUROPEANA_API_KEY}"
  timeout_seconds: 15
  default_query:
    reusability: "open"
    media: "true"
    qf: "TYPE:IMAGE"
    profile: "rich"
```

REST API without auth (Wikimedia Commons):

```yaml
adapter:
  kind: rest
  base_url: "https://commons.wikimedia.org"
  auth:
    type: none
  default_query:
    action: "query"
    format: "json"
    generator: "search"
    gsrnamespace: "6"
    prop: "imageinfo"
    iiprop: "url|mime|extmetadata|size"
    iiurlwidth: "1024"
```

Header auth:

```yaml
adapter:
  kind: rest
  base_url: "https://api.example.org"
  auth:
    type: header
    name: Authorization
    value: "Bearer ${MY_TOKEN}"
```

Fallback (local files):

```yaml
adapter:
  kind: fallback
  manifest_path: "data/fallback/assets/manifest.json"
  static_mount: true
```

Custom adapter (IIIF):

```yaml
adapter:
  kind: custom
  custom_class: "app.adapter.custom.iiif.IIIFManifestSource"
  base_url: "https://iiif.wellcomecollection.org/presentation/b18035723"
  timeout_seconds: 20
```

---

## `search`

How the web app's search (`?s=`, `?o=`, `?c=` on `/api/sources/{id}/assets`) is translated into upstream parameters. **REST adapter only**; fallback and custom adapters search on their own.

| Field | Type | Default | Description |
|---|---|---|---|
| `path` | string | `""` | Appended to `adapter.base_url`. |
| `method` | `GET` \| `POST` | `GET` | Accepted by the schema; only `GET` is implemented. |
| `pagination` | block | `style: offset_limit` | See below. |
| `query` | block | — | See below. |

### `search.pagination`

| Field | Type | Default | Description |
|---|---|---|---|
| `style` | enum | `offset_limit` | `page_size`, `offset_limit`, `cursor` or `none`. |
| `page_param` | string | — | (page_size) upstream parameter for the page number. |
| `size_param` | string | — | (page_size) upstream parameter for the page size. |
| `page_base` | int | `0` | (page_size) number of the first page, `0` or `1`. |
| `offset_param` | string | — | (offset_limit) upstream parameter for the item offset. |
| `offset_base` | int | `0` | (offset_limit) position of the first item, `0` or `1`. Europeana's `start` is 1-based. |
| `limit_param` | string | — | (offset_limit, cursor) upstream parameter for the count. |
| `cursor_param`, `cursor_response_path` | string | — | Accepted; not used (see `cursor`). |
| `max_size` | int | `100` | Upper bound for the size sent upstream. |

The Curator converts offset `o` and count `c` (the web app asks for 24 items per page, or 12 per source when it searches all sources at once; the API caps `c` at 100):

| Style | Sent upstream |
|---|---|
| `offset_limit` | `offset_param = o + offset_base`, `limit_param = min(c, max_size)` |
| `page_size` | `page_param = o // size + page_base`, `size_param = size = min(c, max_size)` — exact only when `o` is a multiple of the size |
| `cursor` | only `limit_param = min(c, max_size)`; no state is kept, so every request returns the first page |
| `none` | nothing |

Both parameter names of a style must be set, otherwise no paging parameters are sent.

Offsets count **upstream** items: the web app's next page starts at `o + <items the upstream returned>`, even if the filter dropped some of them. Read the upstream docs carefully: a parameter named `start` is usually an item offset, not a page number (Europeana, Solr).

Offset-based, one-based (Europeana):

```yaml
search:
  path: "/record/v2/search.json"
  pagination:
    style: offset_limit
    offset_param: start
    limit_param: rows
    offset_base: 1
    max_size: 100
```

Offset-based, zero-based (Wikimedia Commons):

```yaml
search:
  path: "/w/api.php"
  pagination:
    style: offset_limit
    offset_param: gsroffset
    limit_param: gsrlimit
    max_size: 50
```

### `search.query`

| Field | Type | Default | Description |
|---|---|---|---|
| `pattern_param` | string | — | Upstream parameter that receives the search pattern. Without it, no pattern is sent. |
| `pattern_when_empty` | string | `""` | Sent when the visitor's search is empty. Sent as is — not wrapped by `pattern_template`. |
| `pattern_template` | string | — | Wraps every non-empty search; `{pattern}` is replaced by the (wildcard-translated) pattern. |
| `wildcard_translation.from` / `.to` | string | `*` / `*` | Rewrites the wildcard character before sending; `to: ""` strips it for upstreams without wildcards. |

`pattern_when_empty` matters because the web app opens a source with an empty search, and some upstreams return nothing for an empty query (Europeana: use `"*"`). Set it to a broad query that returns something useful.

`pattern_template` adds a filter to everything a visitor types, for upstreams that only have a query string and no separate filter parameter. Because it does not apply to the empty search, repeat the filter in `pattern_when_empty`. For example, only CC0 items from a Solr-style upstream:

```yaml
search:
  query:
    pattern_param: q
    pattern_when_empty: "type:image AND license:cc0"
    pattern_template: "({pattern}) AND license:cc0"
    wildcard_translation:
      from: "*"
      to: "*"
```

---

## `mapping`

How upstream items become Impulse asset dicts. Snapshots in curated collections store exactly what this mapping produced when the asset was added.

| Field | Type | Description |
|---|---|---|
| `items_path` | string | JMESPath to the **array** of items in the response. Empty: the response itself (a list, or one object). For object-shaped responses use `values(...)`, e.g. ``values(query.pages \|\| `{}`)``. Non-object entries are ignored. |
| `total_path` | string | Accepted; currently not used. |
| `fields` | dict[str, FieldMapping] | One entry per Impulse asset field. Keys are Impulse field names. |

### Impulse asset fields

**Internal / management:** `assetID`, `assetURI`, `contentType`, `previewURI`, `published`, `scale`.
**Dublin Core, required:** `contributor`, `description`, `identifier`, `rights`, `title`.
**Dublin Core, optional:** `coverage`, `creator`, `date`, `format`, `language`, `publisher`, `relation`, `source`, `subject`, `type`.

Notes:

- `assetID` identifies the asset **within the source**: the web app adds assets by `(source id, assetID)`, and lookups use it. It must be a string that is stable over time. In a curated collection the item gets its own `assetID` (see [02](02-architecture.md#ids)).
- `assetURI` and `previewURI` should be absolute and directly loadable by a browser and by Unity. Relative values (fallback sources) are made absolute as `/sources/{id}/files/<path>`.
- `contentType` drives the web app's Images / 3D models filter (`image/…`, `model/…`) and Unity's loader choice.
- `published` is always set to `1` when Impulse is served; you do not need to map it.

### `FieldMapping`

```yaml
fields:
  assetID:
    expr: "id"
    transform: slugify
```

| Sub-field | Type | Description |
|---|---|---|
| `expr` | string | JMESPath against the raw item. |
| `literal` | any | A constant. If both are set, `literal` wins. |
| `default` | any | Used when the result is `null`, `""`, `[]` or `{}`. |
| `map` | dict | If the (string) result equals a key, it is replaced by the value. |
| `transform` | enum | `slugify`, `base32`, `strip_html`, `file_title`, `lower`, `upper`. Runs last, on strings only. |

Order: `literal` or `expr` → `default` → `map` → `transform`. A field whose final value is `null` is left out of the asset. If evaluating any field raises, the item is skipped (logged as a warning).

### Transforms

| Transform | What it does |
|---|---|
| `slugify` | Lower-case; every run of non-alphanumerics becomes one hyphen; leading/trailing hyphens removed; empty → `untitled`. Makes ids id-schema safe. **Lossy**: case and separators cannot be recovered (see `{asset_id_regex}`). |
| `base32` | Lowercase, unpadded base32 (`a-z2-7`). Id-schema safe for any input and **reversible** via `{asset_id_from_base32}`; opaque and about 1.6× longer. |
| `strip_html` | Removes HTML tags (regex) and trims. Does not unescape entities. |
| `file_title` | Turns a file name into a title: drops a `File:` / `Image:` / `Datei:` prefix and a media extension, underscores become spaces (`File:Young_Hare.jpg` → `Young Hare`). |
| `lower` / `upper` | `str.lower()` / `str.upper()`. |

### Example — Wikimedia Commons

```yaml
mapping:
  items_path: "values(query.pages || `{}`)"
  fields:
    assetID:     { expr: "to_string(pageid)" }
    title:       { expr: "title", transform: file_title }
    description: { expr: "imageinfo[0].extmetadata.ImageDescription.value", transform: strip_html }
    creator:     { expr: "imageinfo[0].extmetadata.Artist.value", transform: strip_html }
    date:        { expr: "imageinfo[0].extmetadata.DateTimeOriginal.value", transform: strip_html }
    rights:      { expr: "imageinfo[0].extmetadata.LicenseShortName.value", default: "See source page for license" }
    identifier:  { expr: "imageinfo[0].descriptionurl" }
    assetURI:    { expr: "imageinfo[0].url" }
    previewURI:  { expr: "imageinfo[0].thumburl" }
    contentType: { expr: "imageinfo[0].mime" }
    contributor: { literal: "Wikimedia Commons" }
    scale:       { literal: "1" }
```

### Example — value map

```yaml
contentType:
  expr: "media[0].type"
  map:
    "Images":    "image/jpeg"
    "3D Images": "model/gltf-binary"
    "Audio":     "audio/mpeg"
    "Video":     "video/mp4"
  default: "image/jpeg"
```

### JMESPath cheatsheet

| Expression | Meaning |
|---|---|
| `id` | top-level field |
| `title[0]` | first element of a list |
| `to_string(pageid)` | number → string (`assetID` must be a string) |
| `values(query.pages)` | values of an object: `{a: …, b: …}` → `[…, …]` |
| `imageinfo[0].extmetadata.LicenseShortName.value` | nested traversal |
| `media[?type=='Images'] \| [0].content` | first list element matching a filter |
| `(dcCreator[?!starts_with(@, 'http')] \| [0]) \|\| edmAgentLabel[0].def` | first non-URI value, else a fallback |
| `` `{}` `` | a literal empty object |

Full reference: https://jmespath.org/specification.html

---

## `filter`

Applied to every mapped asset (search results and detail lookups).

| Field | Type | Description |
|---|---|---|
| `allowed_content_types` | list[str] | If non-empty, assets whose `contentType` is not listed are dropped. |
| `drop_if_missing` | list[str] | Assets with any of these (Impulse) fields missing or empty are dropped. |

```yaml
filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI", "previewURI"]
```

Dropping items without `assetURI` / `previewURI` is strongly recommended: such assets cannot be shown in the web app or loaded by Unity.

---

## `asset_detail`

Optional single-asset lookup. **REST adapter only.** It matters more than it used to: adding an asset to a curated collection and "Update from sources" both call `get_asset()`.

```yaml
asset_detail:
  enabled: true
  path: "/w/api.php"          # may contain placeholders
  query:
    action: "query"
    format: "json"
    pageids: "{asset_id}"
    prop: "imageinfo"
    iiprop: "url|mime|extmetadata|size"
    iiurlwidth: "1024"
  # mapping: …                # optional
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Without it (or without `path`), a lookup scans the default search result. |
| `path` | string | — | URL path of the detail request. May contain placeholders. |
| `query` | dict[str, str] | `{}` | The **complete** query of the detail request: it **replaces** `adapter.default_query` (a `query_param` API key is still added). Values may contain placeholders. |
| `mapping` | MappingCfg | — | Omitted: the search mapping is reused. Given **without** `fields`: only `items_path` is overridden and the search fields are reused (same item, different envelope, e.g. `response` vs. `response.rows`). Give `fields` only if the item shape differs. |

### Placeholders

| Placeholder | Replaced by |
|---|---|
| `{asset_id}` | The requested `assetID`, verbatim. Use it when the upstream accepts your `assetID` directly (Wikimedia `pageids`, a REST `/items/{id}` endpoint). |
| `{asset_id_regex}` | A case-insensitive regex matching every upstream id that **slugifies to** the requested id. For `transform: slugify` ids and Solr-style search endpoints that accept `field:/regex/`. Europeana: `europeana_id:/{asset_id_regex}/` turns `90402-sk-a-3262` into a pattern matching `/90402/SK_A_3262`. |
| `{asset_id_from_base32}` | The original upstream id, decoded from a `transform: base32` id. For exact-match endpoints without regex search. An id that is not valid base32 is *Asset not found* without an upstream call. |

The response is mapped and filtered; the item whose mapped `assetID` equals the requested id is returned (if the mapping produces no `assetID`, the first item). A 404 from the detail request means *Asset not found* (code 2), not a malformed upstream.

### Choosing an `assetID` strategy

| Upstream id | `assetID` mapping | Detail lookup |
|---|---|---|
| Already id-schema safe (`151972`, `rec-1643407190095-2`) | `expr` only, or `slugify` (a no-op) | exact endpoint with `{asset_id}` — Wikimedia |
| Not safe; upstream search is Solr/Lucene | `slugify` — readable | search endpoint with `field:/{asset_id_regex}/` — Europeana |
| Not safe; only an exact endpoint | `base32` — opaque, reversible | exact endpoint with `{asset_id_from_base32}` |

Prefer the first row whenever the upstream offers any id-schema-safe identifier.

### Lookup order

1. If a recent search on this server returned the asset, its raw item is re-mapped with the current mapping — no upstream call (kept for the cache TTL).
2. Otherwise the configured detail request runs.
3. Without `asset_detail`, the default search result (no query, `max_size` items) is scanned. Fine for small, static sources; configure `asset_detail` for anything larger.

---

## `cache`

```yaml
cache:
  ttl_seconds: 900
```

| Field | Type | Default | Description |
|---|---|---|---|
| `ttl_seconds` | int | — | Intended TTL of this source's cached upstream responses. |

The cache is one `cachetools.TTLCache` with a single global TTL (`BRIDGE_DEFAULT_CACHE_TTL`, default `600` s). `ttl_seconds` is accepted but **not applied**; every source uses the global TTL.

---

## Full example — Europeana

The bundled [`configs/sources/europeana.yaml`](../configs/sources/europeana.yaml), without most comments:

```yaml
collection:
  id: europeana-public-domain-images
  name: "Europeana Public Domain Images"
  description: "Open-licensed images aggregated from European cultural heritage institutions via Europeana."
  organization: "Europeana Foundation"
  owner_id: "bridge@impulse.eu"
  published: 1

adapter:
  kind: rest
  base_url: "https://api.europeana.eu"
  auth:
    type: query_param
    name: wskey
    value: "${EUROPEANA_API_KEY}"
  timeout_seconds: 15
  default_query:
    reusability: "open"
    media: "true"
    qf: "TYPE:IMAGE"
    profile: "rich"

search:
  path: "/record/v2/search.json"
  method: GET
  pagination:
    style: offset_limit
    offset_param: start      # 1-based item position
    limit_param: rows
    offset_base: 1
    max_size: 100
  query:
    pattern_param: query
    pattern_when_empty: "*"

mapping:
  items_path: "items"
  total_path: "totalResults"
  fields:
    assetID:     { expr: "id", transform: slugify }
    title:       { expr: "title[0]", default: "Untitled" }
    description: { expr: "dcDescription[0]", transform: strip_html }
    creator:     { expr: "(dcCreator[?!starts_with(@, 'http')] | [0]) || edmAgentLabel[0].def" }
    date:        { expr: "year[0]" }
    rights:      { expr: "rights[0]", default: "See source for license" }
    identifier:  { expr: "guid" }
    assetURI:    { expr: "edmIsShownBy[0]" }
    previewURI:  { expr: "edmPreview[0]" }
    contentType: { literal: "image/jpeg" }
    contributor: { expr: "dataProvider[0]" }
    scale:       { literal: "1" }
    subject:     { expr: "dcSubject[0]" }
    language:    { expr: "dcLanguage[0]" }

filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI", "previewURI"]

asset_detail:
  enabled: true
  # assetID is a slugified record id, so the exact Record API cannot be used;
  # look the record up case-insensitively through the Search API instead.
  path: "/record/v2/search.json"
  query:
    query: "europeana_id:/{asset_id_regex}/"
    profile: "rich"
    rows: "1"

cache:
  ttl_seconds: 900
```

---

_Last verified against [`app/config/schema.py`](../app/config/schema.py), October 2026._

_Continue to [04 — Admin UI](04-admin-ui.md)._
