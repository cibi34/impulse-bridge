# 03 — YAML reference

Every external archive is described by **one YAML file** in `configs/sources/`. This document is a complete reference for that file. Each section maps directly to a Pydantic model in [`app/config/schema.py`](../app/config/schema.py); any field not listed here will be rejected as unknown (`extra="forbid"`).

## Top-level structure

```yaml
collection: ...     # Impulse-protocol metadata (always required)
adapter: ...        # how the bridge talks to the upstream (always required)
search: ...         # search & pagination (REST only)
mapping: ...        # JMESPath rules to translate upstream JSON → Impulse asset
filter: ...         # post-mapping drop rules
asset_detail: ...   # optional per-asset lookup (REST only)
cache: ...          # per-source cache TTL
```

`collection` and `adapter` are mandatory. The rest have sensible defaults; omitting them means "use defaults".

---

## `collection`

Impulse-protocol metadata for this virtual collection. Returned verbatim by `GET /collections` and `GET /collections/{id}`.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Must match the Impulse **id-schema**: lowercase letters, digits, hyphens; must start with a letter or digit. Used as the path segment in `/collections/{id}`. |
| `name` | string | yes | Human-readable name shown in the Impulse UI. |
| `description` | string | no | One- or two-sentence description. May be null. |
| `organization` | string | yes | The institution responsible for the source (e.g. "Europeana Foundation"). |
| `owner_id` | string | yes | Email or identifier of the bridge operator responsible for this collection. |
| `published` | int | no | `1` = visible to clients, `0` = hidden. Default `1`. |

The `uri` field of the Impulse collection metadata is **not** specified here. The bridge fills it in at startup as `<public_base_url>/collections/<id>`, matching the spec's resolution semantics for relative asset URIs.

### Example

```yaml
collection:
  id: europeana-public-domain-images
  name: "Europeana Public Domain Images"
  description: "Open-licensed images aggregated from European cultural heritage institutions."
  organization: "Europeana Foundation"
  owner_id: "bridge@impulse.eu"
  published: 1
```

---

## `adapter`

How the bridge connects to the upstream archive. The `kind` field selects which adapter implementation to use; some fields below are relevant only for specific kinds.

| Field | Type | Required | For kind | Description |
|---|---|---|---|---|
| `kind` | enum | yes | all | `rest` (generic REST API), `fallback` (local files), or `custom` (user-provided Python class). |
| `base_url` | string | depends | rest, custom | Base URL for HTTP requests. For IIIF this is the manifest URL. |
| `auth` | block | no | rest | Authentication details (see below). |
| `timeout_seconds` | float | no | rest, custom | HTTP timeout in seconds. Default `10.0`. |
| `default_query` | dict[str,str] | no | rest | Query params sent with every search request (static filters, format flags, etc.). |
| `manifest_path` | string | yes (fallback) | fallback | Filesystem path to a JSON file containing pre-mapped Impulse assets. Relative paths resolve against the project root. |
| `static_mount` | bool | no | fallback | If true, the bridge serves files from the manifest's directory under `/collections/{id}/`. Default `true`. |
| `custom_class` | string | yes (custom) | custom | Dotted Python path to a class implementing the `Source` protocol (e.g. `app.adapter.custom.iiif.IIIFManifestSource`). |

### `adapter.auth`

```yaml
auth:
  type: query_param   # one of: none | query_param | header
  name: wskey         # query/header name
  value: "${EUROPEANA_API_KEY}"
```

Any string field, anywhere in the YAML, can reference an environment variable with the `${VAR}` syntax. Missing variables expand to the empty string, which usually leads to a 401/403 from the upstream — handled as code `20` (configuration error) by the bridge.

### Examples

#### REST API with key in query parameter

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

#### REST API without auth

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

#### REST API with header auth

```yaml
adapter:
  kind: rest
  base_url: "https://api.example.org"
  auth:
    type: header
    name: Authorization
    value: "Bearer ${MY_TOKEN}"
```

#### Fallback (local files)

```yaml
adapter:
  kind: fallback
  manifest_path: "data/fallback/assets/manifest.json"
  static_mount: true
```

#### Custom adapter (IIIF)

```yaml
adapter:
  kind: custom
  custom_class: "app.adapter.custom.iiif.IIIFManifestSource"
  base_url: "https://iiif.wellcomecollection.org/presentation/b18035723"
  timeout_seconds: 20
```

---

## `search`

How Impulse's `?s=`, `?o=`, `?c=` are translated into the upstream's parameters. **REST adapter only**; the fallback and custom adapters define their own search semantics.

### `search.path`

The path appended to `adapter.base_url`. Together they form the URL hit on every search.

```yaml
search:
  path: "/search.json"
```

### `search.method`

`GET` or `POST`. Default `GET`. (POST is supported in schema but only GET is currently exercised by the bundled sources.)

### `search.pagination`

| Field | Type | Description |
|---|---|---|
| `style` | enum | `page_size`, `offset_limit`, `cursor`, or `none`. |
| `page_param` | string | (page_size) upstream param for the page number. |
| `size_param` | string | (page_size) upstream param for the page size. |
| `page_base` | int | (page_size) 0 or 1 — zero-based or one-based pages. |
| `offset_param` | string | (offset_limit) upstream param for the result offset. |
| `limit_param` | string | (offset_limit / cursor) upstream param for the count. |
| `cursor_param` | string | (cursor) upstream param that takes the cursor token. |
| `cursor_response_path` | string | (cursor) JMESPath to extract the next-cursor from the response. |
| `max_size` | int | Upper bound on the size sent upstream. Default `100`. |

Impulse semantics: `o` is an offset, `c` is a count. The bridge converts them:

- **page_size**: `page = (offset / size) + page_base`, `size = min(count, max_size)`. The conversion assumes pages are full and roughly aligned with offset; if the upstream and Impulse offsets diverge across pages, the count of results may not match exactly — this is expected for page-based APIs.
- **offset_limit**: pass-through.
- **cursor**: only the size is sent; the bridge does not retain state across requests. Cursor-based archives are best wrapped at the upstream side.
- **none**: no pagination params sent.

#### Page-based (Europeana)

```yaml
search:
  path: "/record/v2/search.json"
  pagination:
    style: page_size
    page_param: start
    size_param: rows
    page_base: 1
    max_size: 100
```

#### Offset-based (Wikimedia Commons)

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

```yaml
search:
  query:
    pattern_param: query        # upstream param that receives Impulse's ?s=…
    pattern_when_empty: "*"     # query sent when ?s is omitted
    wildcard_translation:
      from: "*"                 # the Impulse wildcard character
      to: "*"                   # what to rewrite it to upstream (use "" if upstream doesn't support wildcards)
```

`pattern_when_empty` matters in two cases: when Impulse omits the `s` parameter, and when the upstream API requires a non-empty query to return anything (Europeana). Set it to a broad filter that returns "anything useful".

---

## `mapping`

The heart of the adapter: how to translate upstream items into Impulse asset dictionaries.

| Field | Type | Description |
|---|---|---|
| `items_path` | string | JMESPath against the upstream response that resolves to the **array** of items. For object-shaped responses (e.g. `query.pages` in MediaWiki), use `values(query.pages)`. |
| `total_path` | string | (optional, informational only) JMESPath to the total-results count. Currently used only for logging. |
| `fields` | dict[str, FieldMapping] | One entry per Impulse asset field you want to populate. Keys are Impulse field names (`assetID`, `title`, …). |

### Impulse asset field catalogue

The Impulse spec defines a fixed set of asset fields. The mapping table supports all of them:

**Internal / management** (mandatory in the spec):
- `assetID` — must follow id-schema after slugification
- `assetURI` — direct downloadable URL (or relative literal resolved against the collection URI)
- `contentType` — MIME type (used by Unity to pick a loader)
- `previewURI` — thumbnail URL
- `published` — usually `1`; set via `literal` if needed
- `scale` — string, typically `"1"`

**Dublin Core required**:
- `contributor`, `description`, `identifier`, `rights`, `title`

**Dublin Core optional**:
- `coverage`, `creator`, `date`, `format`, `language`, `publisher`, `relation`, `source`, `subject`, `type`

### `FieldMapping` — one row per Impulse field

```yaml
fields:
  assetID:
    expr: "id"
    transform: slugify
    default: "unknown"
```

| Sub-field | Type | Description |
|---|---|---|
| `expr` | string | JMESPath evaluated against the raw upstream item. Mutually exclusive with `literal`. |
| `literal` | any | Constant value. Use for fields the upstream doesn't provide (e.g. `contributor: "Wikimedia Commons"`). |
| `default` | any | Used if `expr` returns null/empty. |
| `transform` | enum | `slugify`, `strip_html`, `lower`, or `upper`. Applied after default/value-map; only operates on strings. |
| `map` | dict | Value substitution — if the JMESPath result equals a key, replace it with the value. Useful for normalizing MIME types or `type` codes. |

#### Transform reference

| Transform | What it does |
|---|---|
| `slugify` | Lower-cases, replaces any non-alphanumeric run with a single hyphen, strips leading/trailing hyphens. Used to coerce upstream IDs into Impulse id-schema. |
| `strip_html` | Removes HTML tags (Wikimedia returns HTML in description fields). |
| `lower` | `str.lower()` |
| `upper` | `str.upper()` |

#### Example — Wikimedia mapping

```yaml
mapping:
  items_path: "values(query.pages || `{}`)"
  fields:
    assetID:
      expr: "to_string(pageid)"
    title:
      expr: "title"
    description:
      expr: "imageinfo[0].extmetadata.ImageDescription.value"
      transform: strip_html
    creator:
      expr: "imageinfo[0].extmetadata.Artist.value"
      transform: strip_html
    date:
      expr: "imageinfo[0].extmetadata.DateTimeOriginal.value"
      transform: strip_html
    rights:
      expr: "imageinfo[0].extmetadata.LicenseShortName.value"
      default: "See source page for license"
    identifier:
      expr: "imageinfo[0].descriptionurl"
    assetURI:
      expr: "imageinfo[0].url"
    previewURI:
      expr: "imageinfo[0].thumburl"
    contentType:
      expr: "imageinfo[0].mime"
    contributor:
      literal: "Wikimedia Commons"
    scale:
      literal: "1"
```

#### Example — Smithsonian with a value map

```yaml
contentType:
  expr: "content.descriptiveNonRepeating.online_media.media[0].type"
  map:
    "Images":      "image/jpeg"
    "3D Images":   "model/gltf-binary"
    "Audio":       "audio/mpeg"
    "Video":       "video/mp4"
  default: "image/jpeg"
```

When the JMESPath evaluates to a string equal to one of the `map` keys, the value substitution wins. The transform (if any) runs **after** the value map.

### JMESPath cheatsheet

| Expression | Meaning |
|---|---|
| `id` | top-level `id` field |
| `items[0].title` | first item's title |
| `creator[0]` | first element of a list |
| `to_string(pageid)` | coerce a number to string (assetID must be a string) |
| `values(query.pages)` | values of an object — turns `{a:…, b:…}` into `[…, …]` |
| `imageinfo[0].extmetadata.LicenseShortName.value` | nested traversal |
| `content.media[?type=='Images'] \| [0].content` | filter list, take first match |
| `\`{}\`` | a literal empty object |

Full reference: https://jmespath.org/specification.html

---

## `filter`

Post-mapping drop rules. Applied to each asset after the mapping has produced it.

| Field | Type | Description |
|---|---|---|
| `allowed_content_types` | list[string] | If non-empty, an asset is dropped unless its `contentType` is in this list. |
| `drop_if_missing` | list[string] | An asset is dropped if any of these mapped fields is missing/empty. |

### Examples

Only keep images, and drop items where Europeana didn't expose a downloadable URL:

```yaml
filter:
  allowed_content_types:
    - "image/jpeg"
    - "image/png"
  drop_if_missing:
    - "assetURI"
    - "previewURI"
```

Take everything Wikimedia returns, including non-image types:

```yaml
filter:
  allowed_content_types: []  # or omit the block entirely
  drop_if_missing: ["assetURI"]
```

---

## `asset_detail`

Optional per-asset lookup. **REST adapter only**.

```yaml
asset_detail:
  enabled: true
  path: "/w/api.php"        # may contain {asset_id} placeholder
  query:
    action: "query"
    format: "json"
    pageids: "{asset_id}"   # substituted with the asset ID at request time
    prop: "imageinfo"
    iiprop: "url|mime|extmetadata|size"
    iiurlwidth: "1024"
  mapping: ...              # optional; if omitted, reuses the top-level mapping
```

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | If `false` (the default), `get_asset()` falls back to scanning the default search result. |
| `path` | string | URL path for the detail endpoint. May contain `{asset_id}` placeholder. |
| `query` | dict[str, str] | Query parameters. **Replaces** (does not merge with) `adapter.default_query`, because search and detail typically take different params. Values may contain `{asset_id}`. |
| `mapping` | MappingCfg | If omitted, the top-level `mapping` is reused. Override only if the detail endpoint returns a different shape. |

When `asset_detail` is **disabled**, calling `/collections/{id}/asset/{aid}` triggers a default search and scans the result for a matching `assetID`. This is acceptable for small/static collections but inefficient for big ones — enable `asset_detail` for production-quality detail lookups.

---

## `cache`

Per-source cache TTL.

```yaml
cache:
  ttl_seconds: 600
```

| Field | Type | Default | Description |
|---|---|---|---|
| `ttl_seconds` | int | `settings.default_cache_ttl` (env `BRIDGE_DEFAULT_CACHE_TTL`, default `600`) | How long upstream responses are cached. |

Note: due to `cachetools.TTLCache` having one global TTL per instance, the per-source override is currently advisory. The bridge respects the **global** default; per-source values are read but converge to the global setting. Swap in a per-key TTL cache (or Redis) if precise per-source control becomes important.

---

## Full example — Europeana

```yaml
collection:
  id: europeana-public-domain-images
  name: "Europeana Public Domain Images"
  description: "Open-licensed images aggregated from European cultural heritage institutions."
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
  pagination:
    style: page_size
    page_param: start
    size_param: rows
    page_base: 1
    max_size: 100
  query:
    pattern_param: query
    pattern_when_empty: "*"

mapping:
  items_path: "items"
  total_path: "totalResults"
  fields:
    assetID:    { expr: "id", transform: slugify }
    title:      { expr: "title[0]", default: "Untitled" }
    description: { expr: "dcDescription[0]", transform: strip_html }
    creator:    { expr: "dcCreator[0]" }
    date:       { expr: "year[0]" }
    rights:     { expr: "rights[0]", default: "See source for license" }
    identifier: { expr: "guid" }
    assetURI:   { expr: "edmIsShownBy[0]" }
    previewURI: { expr: "edmPreview[0]" }
    contentType: { literal: "image/jpeg" }
    contributor: { expr: "dataProvider[0]" }
    scale:      { literal: "1" }
    subject:    { expr: "dcSubject[0]" }
    language:   { expr: "dcLanguage[0]" }

filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI", "previewURI"]

cache:
  ttl_seconds: 900
```

---

_Continue to [04 — Admin UI](04-admin-ui.md)._
