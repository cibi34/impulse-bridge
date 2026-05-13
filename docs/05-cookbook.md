# 05 — Cookbook

Practical recipes for the most common things you'll do with the bridge. Each recipe ends with a YAML you can paste into the admin UI's **New source ▾ → REST API (generic)** template.

## Recipe 1 — Add a new REST archive (no auth)

**When to use:** the upstream has a public JSON API that returns a list of items with media URLs.

1. Click **+ New source ▾ → REST API (generic)** in the admin UI.
2. Fill in the **Collection** section — `id` (lowercase-hyphens), `name`, `organization`, `owner_id`.
3. Set `adapter.base_url` to the API root.
4. In the **Search** section, set `path` and the pagination params.
5. Open the **Test** tab and run with an empty query — verify you get raw JSON back.
6. Look at the **Raw upstream response** pane. Find the array of items (its JMESPath) and the field names for title, URL, etc.
7. Go to **Form → Mapping**: set `items_path` and fill in the rows for `assetID`, `title`, `assetURI`, `previewURI`, `contentType`, `rights`.
8. Re-run **Test**. The right pane (Mapped Impulse output) should now contain proper Impulse asset dicts.
9. **Save & Reload**.

```yaml
collection:
  id: openverse-images
  name: "Openverse Images"
  organization: "WordPress Foundation"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: rest
  base_url: "https://api.openverse.engineering/v1"
  auth:
    type: none
  default_query:
    license_type: "commercial,modification"

search:
  path: "/images/"
  pagination:
    style: page_size
    page_param: page
    size_param: page_size
    page_base: 1
    max_size: 20
  query:
    pattern_param: q
    pattern_when_empty: "art"

mapping:
  items_path: "results"
  fields:
    assetID:    { expr: "id", transform: slugify }
    title:      { expr: "title", default: "Untitled" }
    creator:    { expr: "creator" }
    rights:     { expr: "license" }
    identifier: { expr: "foreign_landing_url" }
    assetURI:   { expr: "url" }
    previewURI: { expr: "thumbnail" }
    contentType: { literal: "image/jpeg" }
    contributor: { expr: "source" }
    scale:      { literal: "1" }

filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI"]

cache:
  ttl_seconds: 600
```

## Recipe 2 — Add a REST archive with an API key

**When to use:** the upstream requires an API key (Europeana, Smithsonian, Flickr, …).

1. Get the key from the provider (most are free for non-commercial use).
2. Add the key to your `.env` file: `MY_PROVIDER_KEY=...`.
3. **Restart the bridge once** so `.env` is reloaded. (Subsequent YAML edits hot-reload without a restart.)
4. In the new source YAML, reference the env var in `adapter.auth.value`:

```yaml
adapter:
  kind: rest
  base_url: "https://api.example.org"
  auth:
    type: query_param    # or "header" for "Authorization: Bearer …"
    name: api_key
    value: "${MY_PROVIDER_KEY}"
```

The bridge expands `${MY_PROVIDER_KEY}` at startup. If the variable is missing the value becomes an empty string and the upstream will return 401 — which the bridge surfaces as code `20` (configuration error) with a clear message in the admin UI.

For Bearer-style header auth:

```yaml
adapter:
  auth:
    type: header
    name: Authorization
    value: "Bearer ${MY_PROVIDER_TOKEN}"
```

## Recipe 3 — Add a single IIIF manifest

**When to use:** an institution publishes an IIIF Presentation API manifest (most major libraries do).

1. Find the manifest URL on the institution's site (often available behind a "Get IIIF manifest" link on the object's page).
2. Use the **IIIF Presentation API manifest** template in **+ New source ▾**.
3. Replace the `base_url` with your manifest URL.
4. Pick a meaningful `collection.id`.
5. **Save & Reload**.

```yaml
collection:
  id: bnf-illuminations-bestiary
  name: "BnF — Medieval Bestiary"
  organization: "Bibliothèque nationale de France"
  owner_id: "you@example.org"
  published: 1

adapter:
  kind: custom
  custom_class: "app.adapter.custom.iiif.IIIFManifestSource"
  base_url: "https://gallica.bnf.fr/iiif/ark:/12148/btv1b8451637b/manifest.json"
  timeout_seconds: 20
```

The bundled IIIF adapter handles both Presentation API v2 (`sequences[].canvases[]`) and v3 (`items[]`). One canvas = one Impulse asset; the image URL is derived from each canvas's painting annotation.

To expose multiple manifests, create one YAML per manifest. Each manifest becomes its own Impulse collection.

## Recipe 4 — Map nested JSON with JMESPath

The mapping engine uses [JMESPath](https://jmespath.org/). The most useful patterns:

| Goal | Pattern |
|---|---|
| Take a top-level field | `id` |
| First element of a list | `dcTitle[0]` |
| Coerce a number to string | `to_string(pageid)` |
| Reach into a nested dict | `imageinfo[0].extmetadata.LicenseShortName.value` |
| Find a list element matching a filter | `media[?type=='Images'] \| [0].content` |
| Turn an object-shaped collection into a list | `values(query.pages \|\| \`{}\`)` |
| Choose first non-empty value (coalesce) | `[title[0], dcTitle.def[0]] \| [?@] \| [0]` |

Test JMESPath in the **Test** tab: copy the raw upstream JSON, paste it into the [JMESPath playground](https://jmespath.org/), and iterate until the expression returns the value you want.

## Recipe 5 — Drop items that don't have a usable URL

Many archives return mixed records: some items have downloadable media, some don't. The Impulse 3D world cannot render a "metadata-only" record, so it's better to drop those before they reach the client.

```yaml
filter:
  drop_if_missing:
    - "assetURI"     # if there's no downloadable URL, the item is useless to Unity
    - "previewURI"   # without a thumbnail the public browser UI looks broken
```

`drop_if_missing` runs **after** mapping. The fields named here are Impulse field names, not upstream field names.

For Europeana specifically, requiring `edmIsShownBy` (mapped to `assetURI`) tends to remove ~30% of records and dramatically improves the user experience.

## Recipe 6 — Filter by content type

Restrict a source to images only:

```yaml
filter:
  allowed_content_types:
    - "image/jpeg"
    - "image/png"
    - "image/webp"
```

This filter applies to the **mapped** `contentType`, not the upstream's MIME field name. If the upstream returns a non-standard type code, normalize it first via a value map in the mapping:

```yaml
mapping:
  fields:
    contentType:
      expr: "media.type"
      map:
        "IMAGE":   "image/jpeg"
        "VIDEO":   "video/mp4"
        "MODEL":   "model/gltf-binary"
      default: "image/jpeg"
```

## Recipe 7 — Strip HTML from descriptions

Wikimedia (and many others) returns HTML in description fields. Use `transform: strip_html`:

```yaml
description:
  expr: "imageinfo[0].extmetadata.ImageDescription.value"
  transform: strip_html
```

`strip_html` is a regex-based tag remover. It is intentionally simple — it does not unescape HTML entities or normalize whitespace. For most cultural-heritage descriptions this is good enough.

## Recipe 8 — Page-based vs offset-based pagination

The Impulse spec uses `?o=offset&c=count`. The bridge converts:

```yaml
# Wikimedia / MediaWiki — offset-based natively
search:
  pagination:
    style: offset_limit
    offset_param: gsroffset
    limit_param: gsrlimit
    max_size: 50

# Europeana — page-based, one-based
search:
  pagination:
    style: page_size
    page_param: start
    size_param: rows
    page_base: 1
    max_size: 100

# A hypothetical zero-based pages API
search:
  pagination:
    style: page_size
    page_param: page
    size_param: per_page
    page_base: 0
    max_size: 50
```

If the upstream really only does cursor-based pagination, set `style: cursor` and accept that the bridge won't honor `?o=` precisely — it will simply request `c=` items each call.

## Recipe 9 — Configure asset_detail for a clean single-asset endpoint

By default, `GET /collections/{id}/asset/{aid}` falls back to scanning the default search result. This is slow and brittle for large collections.

If the upstream has a per-asset endpoint, configure `asset_detail`:

```yaml
asset_detail:
  enabled: true
  path: "/w/api.php"
  query:
    action: "query"
    format: "json"
    pageids: "{asset_id}"
    prop: "imageinfo"
    iiprop: "url|mime|extmetadata|size"
    iiurlwidth: "1024"
```

`{asset_id}` is substituted with the Impulse asset ID at request time. The query block here **replaces** `adapter.default_query` — list every parameter you need, including `format=json`. (This is intentional: search and detail endpoints typically take incompatible parameters — for MediaWiki, search uses `generator=search` while detail uses `pageids`.)

If the upstream's detail endpoint returns a different JSON shape than search, also provide a `mapping` block inside `asset_detail`. If shapes match, omit it and the top-level mapping is reused.

## Recipe 10 — Test before saving

The fastest way to iterate on a tricky mapping:

1. Open the source in the admin UI.
2. Go straight to the **Test** tab.
3. Set a search term that returns interesting items.
4. Run.
5. Read the **Raw upstream response** — note which fields you need.
6. Switch to **Form**, adjust the mapping rows.
7. Switch back to **Test**, run again.
8. Once the **Mapped Impulse output** looks right, **Save & Reload**.

Nothing is written to disk until you click Save. You can iterate freely.

## Recipe 11 — Build a fallback / offline collection

Useful for demos, integration tests, and as a guaranteed-working stand-in:

1. Create a directory under `data/fallback/<your-collection>/` and place your asset files there (e.g. `.glb`, `.jpg`).
2. Write a `manifest.json` next to them, listing the assets in Impulse asset shape — see `data/fallback/assets/manifest.json` for an example.
3. Create a YAML in `configs/sources/` using the **Fallback (local files)** template, pointing `manifest_path` at your new `manifest.json`.

The fallback adapter serves the asset files via static-file routes under `/collections/{id}/`, matching the spec's relative-URI resolution.

## Recipe 12 — Hide a collection without deleting it

Set `published: 0`:

```yaml
collection:
  published: 0
```

`GET /collections` still includes it in its output (with `published: 0`) but Impulse clients are expected to filter on this. Use this for staging changes or temporarily removing a problematic source without losing its config.

If you want it gone from `/collections` entirely, **Delete** it via the admin UI or simply move/rename the YAML file out of `configs/sources/` and hit **↻**.

## Recipe 13 — Rotate an API key

1. Update the value in `.env`.
2. Restart the bridge — `.env` is only read at process startup.
3. (Optional) Open the admin UI and use **Test** on the affected source to confirm the new key works.

The YAML files do not change; they keep referencing `${MY_API_KEY}` which now resolves to the new value.

## Recipe 14 — Debug a "no items returned" problem

Symptoms: `GET /collections/{id}/assets` returns `{"code": 0, "message": "OK", "data": []}` even though you'd expect results.

In the admin UI's **Test** tab, look at:

1. **Upstream URL** — does it look right? Is the search parameter being passed?
2. **Raw upstream response** — does it contain items at all? If yes:
   - Does `items_path` resolve to the right thing? (Empty `items_path` treats the response as the array.)
   - Are items being dropped by `filter.allowed_content_types` or `filter.drop_if_missing`? Temporarily clear those filters and re-test.
   - Are `assetURI` / `previewURI` being mapped to empty strings? Check the mapping rows.
3. If the raw response is empty, your `pattern_when_empty` or `default_query` is too restrictive.

## Recipe 15 — Verify against the live Impulse API

Once your source is configured and tested, confirm Impulse-protocol compliance from outside the admin UI:

```bash
# List of all virtual collections, including your new one
curl 'http://localhost:8080/collections'

# Detail of your collection
curl 'http://localhost:8080/collections/my-source'

# First page of assets
curl 'http://localhost:8080/collections/my-source/assets?c=5'

# Search
curl 'http://localhost:8080/collections/my-source/assets?s=van+gogh&c=3'

# Single asset
curl 'http://localhost:8080/collections/my-source/asset/some-asset-id'

# Direct download of the first asset's URI (asserts that Unity can download it)
curl -I "$(curl -s 'http://localhost:8080/collections/my-source/assets?c=1' | python -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["assetURI"])')"
```

Every response should match the Impulse envelope `{code, message, data}` and the asset shape from the spec.

---

_Continue to [06 — Operations](06-operations.md)._
