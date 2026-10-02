# 05 — Cookbook

Recipes for common tasks. Source recipes use the admin's **Sources** page (`/admin/sources`, see [04 — Admin UI](04-admin-ui.md)); every YAML can also be written to `configs/sources/` directly, followed by **Reload from disk**.

Examples use `http://localhost:8080`; replace it with your public address in production (and add `-u admin:<password>` for `/admin/api/…`).

## Recipe 1 — Add a REST source (no auth)

**When:** the archive has a public JSON search API that returns items with media URLs.

1. **Sources → New → REST API (generic search/discovery).** The template opens in the editor, unsaved.
2. Set `collection.id` (lowercase, digits, hyphens), `name`, `description`, `organization`, `owner_id`.
3. Set `adapter.base_url`, `search.path`, the pagination parameters and `search.query.pattern_param`.
4. **Run test** with an empty pattern. Open **Raw upstream response**: find the array of items and the fields for id, title, media URL, thumbnail, licence.
5. Set `mapping.items_path` and the fields `assetID`, `title`, `assetURI`, `previewURI`, `contentType`, `rights`, `contributor`, `scale`.
6. Run the test again until **Mapped assets** look right and the thumbnails show.
7. **Create source.** The status turns **Live**; the source appears in `/explore` and in `GET /api/sources`.

An illustrative config (Openverse):

```yaml
collection:
  id: openverse-images
  name: "Openverse Images"
  description: "Openly licensed images indexed by Openverse."
  organization: "WordPress Foundation"
  owner_id: "you@example.org"

adapter:
  kind: rest
  base_url: "https://api.openverse.org/v1"
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
    assetID:     { expr: "id" }            # a UUID: already id-schema safe
    title:       { expr: "title", default: "Untitled" }
    creator:     { expr: "creator" }
    rights:      { expr: "license" }
    identifier:  { expr: "foreign_landing_url" }
    assetURI:    { expr: "url" }
    previewURI:  { expr: "thumbnail" }
    contentType: { literal: "image/jpeg" }
    contributor: { expr: "source" }
    scale:       { literal: "1" }

filter:
  allowed_content_types: ["image/jpeg", "image/png"]
  drop_if_missing: ["assetURI", "previewURI"]
```

Before visitors use the source, configure `asset_detail` (Recipe 8): adding assets to a collection looks every asset up again.

## Recipe 2 — A source that needs an API key

1. Get a key from the provider (Europeana keys are free).
2. Add it to `.env`: `MY_PROVIDER_KEY=...` (in Docker: the project's `.env` next to `docker-compose.yml`).
3. **Restart** the server (`docker compose up -d` in production) — environment variables are read once at start. YAML edits later need no restart.
4. Reference the variable in the YAML:

```yaml
adapter:
  kind: rest
  base_url: "https://api.example.org"
  auth:
    type: query_param      # or: header
    name: api_key
    value: "${MY_PROVIDER_KEY}"
```

Bearer token in a header:

```yaml
adapter:
  auth:
    type: header
    name: Authorization
    value: "Bearer ${MY_PROVIDER_TOKEN}"
```

A missing variable becomes an empty string; the upstream then usually answers 401/403, shown as code `20` ("Upstream auth failed … check API key"). The test run shows the request with the key masked as `***`, so an empty `api_key=` in the **Upstream request** means the variable did not expand.

## Recipe 3 — Add an IIIF manifest

1. Find the manifest URL (often behind a "IIIF manifest" link on the object page).
2. **Sources → New → IIIF Presentation API manifest.**
3. Set `adapter.base_url` to the manifest URL and give the source a meaningful `collection.id` and `name`.
4. **Run test**, then **Create source**.

```yaml
collection:
  id: bnf-medieval-bestiary
  name: "BnF — Medieval Bestiary"
  organization: "Bibliothèque nationale de France"
  owner_id: "you@example.org"

adapter:
  kind: custom
  custom_class: "app.adapter.custom.iiif.IIIFManifestSource"
  base_url: "https://gallica.bnf.fr/iiif/ark:/12148/btv1b8451637b/manifest.json"
  timeout_seconds: 20
```

The adapter handles Presentation API v2 and v3. One canvas = one asset: full-size and 400 px preview URLs come from the IIIF Image API; canvases without a usable label are titled "<manifest> — page N". One YAML per manifest. The manifest is read once per source and kept until the next reload.

## Recipe 4 — Map nested JSON with JMESPath

| Goal | Pattern |
|---|---|
| Top-level field | `id` |
| First element of a list | `dcTitle[0]` |
| Number to string | `to_string(pageid)` |
| Nested field | `imageinfo[0].extmetadata.LicenseShortName.value` |
| First list element matching a filter | `media[?type=='Images'] \| [0].content` |
| Object of items → list | ``values(query.pages \|\| `{}`)`` |
| First non-empty of several | `[title[0], dcTitle.def[0]] \| [?@] \| [0]` |
| First value that is not a URI, else a fallback | `(dcCreator[?!starts_with(@, 'http')] \| [0]) \|\| edmAgentLabel[0].def` |

Iterate in the test run: change the expression, **Run test**, compare **Mapped assets**. For harder expressions, paste the raw response into the playground at https://jmespath.org/.

## Recipe 5 — Keep only usable assets

Unity cannot show a metadata-only record, and the web app needs a thumbnail. Drop such items and restrict the content types:

```yaml
filter:
  allowed_content_types: ["image/jpeg", "image/png", "image/webp", "model/gltf-binary"]
  drop_if_missing: ["assetURI", "previewURI"]
```

Both rules work on **mapped** Impulse fields. Normalize upstream type codes first with a value map:

```yaml
mapping:
  fields:
    contentType:
      expr: "media.type"
      map:
        "IMAGE": "image/jpeg"
        "MODEL": "model/gltf-binary"
      default: "image/jpeg"
```

`contentType` also drives the web app's **Images / 3D models** filter (`image/…` / `model/…`).

For Europeana keep `media: "true"` in `default_query` and require `assetURI` (from `edmIsShownBy`): many records only link to a landing page.

## Recipe 6 — Clean up text

```yaml
title:
  expr: "title"
  transform: file_title     # "File:Young_Hare.jpg" -> "Young Hare"
description:
  expr: "imageinfo[0].extmetadata.ImageDescription.value"
  transform: strip_html     # removes tags; entities are kept
```

## Recipe 7 — Pagination and an always-on filter

```yaml
# Zero-based item offset (MediaWiki)
search:
  pagination: { style: offset_limit, offset_param: gsroffset, limit_param: gsrlimit, max_size: 50 }

# One-based item offset (Europeana: start=1 is the first record)
search:
  pagination: { style: offset_limit, offset_param: start, limit_param: rows, offset_base: 1, max_size: 100 }

# Page numbers starting at 1
search:
  pagination: { style: page_size, page_param: page, size_param: per_page, page_base: 1, max_size: 50 }
```

If paging repeats or skips items in the web app, check `offset_base` / `page_base` first.

To apply a filter to everything a visitor types, wrap the pattern — and repeat the filter for the empty search, which is not wrapped:

```yaml
search:
  query:
    pattern_param: q
    pattern_when_empty: "type:image AND license:cc0"
    pattern_template: "({pattern}) AND license:cc0"
```

## Recipe 8 — Configure `asset_detail`

Every asset added to a collection, and every "Update from sources", is looked up with `get_asset()`. Right after a search that is a cache hit; later (refresh, adding from an old selection, an API client) it needs a real lookup. Without `asset_detail` the source can only scan its default search page.

Exact endpoint, id passed verbatim (Wikimedia):

```yaml
asset_detail:
  enabled: true
  path: "/w/api.php"
  query:                    # replaces default_query: list everything the endpoint needs
    action: "query"
    format: "json"
    pageids: "{asset_id}"
    prop: "imageinfo"
    iiprop: "url|mime|extmetadata|size"
    iiurlwidth: "1024"
```

Same item, different envelope (a REST API whose detail endpoint wraps the item in `response`):

```yaml
asset_detail:
  enabled: true
  path: "/api/v1/content/{asset_id}"
  query: {}
  mapping:
    items_path: "response"  # search: response.rows; fields are reused
```

### Variant: the assetID is slugified

Europeana ids such as `/90402/SK_A_3262` become `90402-sk-a-3262` with `transform: slugify` — irreversible, so the exact Record API cannot be used. If the upstream search is Solr-based (Europeana, DPLA, Trove, Blacklight), query the search endpoint with `{asset_id_regex}`:

```yaml
asset_detail:
  enabled: true
  path: "/record/v2/search.json"
  query:
    query: "europeana_id:/{asset_id_regex}/"
    profile: "rich"
    rows: "1"
```

### Variant: no regex search, but an exact endpoint

Make the id reversible instead of readable:

```yaml
mapping:
  fields:
    assetID: { expr: "id", transform: base32 }

asset_detail:
  enabled: true
  path: "/items/{asset_id_from_base32}"
  query: {}
```

### Decision guide

1. The upstream has an identifier that is already lowercase letters, digits and hyphens? Use it, `{asset_id}`.
2. Otherwise, Solr/Lucene search? `slugify` + `{asset_id_regex}` on the search endpoint.
3. Otherwise, `base32` + `{asset_id_from_base32}` on the exact endpoint.
4. Neither? Leave `asset_detail` off. Adding assets right after a search still works (cache TTL); refreshes may report "Asset not found".

Check a lookup:

```bash
curl http://localhost:8080/api/sources/<source-id>/assets/<assetID>
```

## Recipe 9 — A local (fallback) source

For demos, offline use and assets that live on this server:

1. Create `data/fallback/<name>/` with the media files.
2. Write `data/fallback/<name>/manifest.json`: a JSON array of Impulse assets; `assetURI` / `previewURI` may be file names relative to that directory. See `data/fallback/assets/manifest.json`.
3. **Sources → New → Fallback (local files)**, set `manifest_path: "data/fallback/<name>/manifest.json"`, **Create source**.

The files are served at `/sources/<source-id>/files/<path>`; curated collections store those absolute URLs. Do not rename such a source or change `BRIDGE_PUBLIC_BASE_URL` once collections use it — the stored file URLs would break (see [06](06-operations.md#troubleshooting)).

In Docker, `data/` is bind-mounted: put the files on the host and make them readable for uid 10001.

## Recipe 10 — Edit files on disk, take a source offline

- **Edited a YAML on the server?** **Sources → Reload from disk** (or `POST /admin/api/reload`). Broken files get a red dot; all others stay live.
- **Take a source offline:** **Delete** it in the editor, or move the file out of `configs/sources/` and reload. `collection.published: 0` has no effect. Existing collections keep their snapshots.

## Recipe 11 — Rotate an API key

1. Change the value in `.env`.
2. Restart (`docker compose up -d`).
3. **Sources → open the source → Run test** to confirm.

The YAML does not change; it keeps referencing `${MY_API_KEY}`.

## Recipe 12 — "No items" in a source

The web app shows nothing, or `GET /api/sources/{id}/assets` returns `"items": []`. In the test run:

1. **Upstream request** — right path, search parameter, paging parameters?
2. **Raw upstream response** — does it contain items?
   - Yes: does `items_path` resolve to them? Are all items dropped by `filter`? Clear the filter temporarily and run again. Are `assetURI` / `previewURI` empty after mapping?
   - No: `default_query` or `pattern_when_empty` is too restrictive, or the API needs other parameters.
3. Errors above the results show the upstream status (code `20`: key; `11`: rate limit; `12`: bad request).

## Recipe 13 — How a curated collection reaches Unity

```
visitor          web app / Curator                    IMPULSE team        Unity
───────          ─────────────────                    ────────────        ─────
search, select ─► POST /api/collections
                  → snapshots in SQLite, edit key
edit, hide,    ─► /c/{id}/edit  (PATCH …, PUT …/order)
reorder
"Submit to     ─► mail program opens, pre-filled  ──► registers the
 IMPULSE"         to the submission address           collection URI in
                  (+ POST …/submitted)                the platform list ──► GET {uri}
                                                                            GET {uri}/assets
                                                                            GET {uri}/asset/{aid}
admin "Listed" ─► appears in GET /collections (optional)
```

1. **Create.** In `/explore` the visitor selects assets and creates a collection. The server snapshots every asset (failures are reported, the rest is kept) and returns the edit key once; the web app stores it in the browser and opens `/c/{id}/edit`.
2. **Curate.** On the edit page: name, description, order, **Visible in Unity** per asset, add more assets, **Update from sources**. Every change is in the Impulse API immediately — Unity reads SQLite.
3. **Submit.** **Submit to IMPULSE** opens the visitor's mail program with a message to the **Submission address** (admin Settings). It contains the collection URI and its Impulse entry (`id`, `uri`, `name`, `description`, `organization`, `owner_id`, `published`). The dialog can also copy the text instead; if it is too long for a `mailto:` link (about 1,800 characters), the full text goes to the clipboard and the mail program opens with a short message to paste it into. Either way the collection is marked as submitted (`POST /api/collections/{id}/submitted`). Several collections can be submitted at once from **My collections**. Without a submission address, visitors are asked to send the details to their IMPULSE contact.
4. **Register.** The IMPULSE team adds the collection URI to the platform's collection list. From then on, Unity loads `<uri>/assets`.
5. **List (optional).** On **Admin → Collections**, switch **Listed** on so the collection also appears in the Curator's own `GET /collections`.

Check what Unity gets:

```bash
curl http://localhost:8080/collections/<id>                 # metadata (code 1 if unknown or locked)
curl http://localhost:8080/collections/<id>/assets          # visible assets, in order
curl 'http://localhost:8080/collections/<id>/assets?s=sun*flower&o=0&c=10'
curl http://localhost:8080/collections/<id>/asset/<assetID>
curl http://localhost:8080/collections                      # listed collections only
```

## Recipe 14 — Create and edit a collection with the API

```bash
B=http://localhost:8080

# Create (returns the edit key once)
curl -s -X POST $B/api/collections -H 'Content-Type: application/json' -d '{
  "name": "Demo",
  "description": "Two assets",
  "items": [{"source": "bridge-demo", "asset_id": "demo-cube"},
            {"source": "wikimedia-commons-images", "asset_id": "151972"}]}'
# → {"collection": {"id": "demo-k3m9x2", …}, "edit_key": "…", "failed": []}

ID=demo-k3m9x2; KEY='<edit key>'

# Add, hide, reorder, rename
curl -s -X POST  $B/api/collections/$ID/items -H "Authorization: Bearer $KEY" \
     -H 'Content-Type: application/json' -d '{"items": [{"source": "bridge-demo", "asset_id": "demo-sphere"}]}'
curl -s -X PATCH $B/api/collections/$ID/items/<assetID> -H "Authorization: Bearer $KEY" \
     -H 'Content-Type: application/json' -d '{"published": false}'
curl -s -X PUT   $B/api/collections/$ID/order -H "Authorization: Bearer $KEY" \
     -H 'Content-Type: application/json' -d '{"asset_ids": ["<id-1>", "<id-2>", "<id-3>"]}'
curl -s -X PATCH $B/api/collections/$ID -H "Authorization: Bearer $KEY" \
     -H 'Content-Type: application/json' -d '{"name": "Demo, renamed"}'
```

`asset_id` in requests is the **source's** assetID; in the collection each item gets its own `assetID` (e.g. `demo-cube-0d373d`), used for `/items/{assetID}` and `order`. `order` must list every item exactly once. The edit link for a browser is `<public base URL>/c/<id>/edit#key=<edit key>`.

## Recipe 15 — A creator lost the edit link

- **With email:** if the collection has an email address and email is set up, the creator signs in at `/signin` with that address and gets a one-time link; afterwards **My collections** lists all collections created with it.
- **Without:** **Admin → Collections → key icon → Create new link**, then send the link to the creator. The old link stops working.

## Recipe 16 — Deal with a reported collection

Reports arrive by email (`/report` describes the procedure).

1. **Admin → Collections**, search for the id from the reported URL.
2. Switch **Locked** on: the collection disappears from the Impulse API and its pages, and its creator can no longer change it. Nothing is deleted.
3. Unlock, or **Delete** it for good.

## Recipe 17 — Check Impulse compliance

```bash
B=http://localhost:8080; ID=<collection id>

curl -s $B/collections | python -m json.tool                     # envelope, listed collections
curl -s "$B/collections/$ID/assets?o=abc"                        # illegal o → entire result set
curl -s "$B/collections/$ID/assets?c=0"                          # illegal c → entire result set
curl -s $B/collections/does-not-exist                            # {"code": 1, …} with HTTP 404
curl -s $B/collections/$ID/asset/does-not-exist                  # {"code": 2, …} with HTTP 404

# Can the first asset be downloaded directly (what Unity does)?
curl -I "$(curl -s $B/collections/$ID/assets?c=1 | python -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["assetURI"])')"
```

---

_Last verified against the code: October 2026._

_Continue to [06 — Operations](06-operations.md)._
