# 04 — Admin UI

The admin UI is the day-to-day tool for managing sources. It lives at `http://localhost:8080/admin` and talks to the bridge through the `/admin/api/...` endpoints.

This doc walks through every section of the UI. For the underlying field semantics see [03 — YAML reference](03-yaml-reference.md).

## Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Impulse Bridge — Admin    [5 loaded / 5 on disk]    ☀ Light  Help  Browser  API
├──────────────────────────┬───────────────────────────────────────────────────┤
│ + New source ▾    ↻      │ Source detail header — id, status, actions        │
├──────────────────────────│───────────────────────────────────────────────────│
│                          │ [ Form ] [ YAML ] [ Test ]                        │
│ ● europeana-public-…     │                                                   │
│   rest · api.europeana.eu│ ┌─────────────────────────────────────────────┐  │
│                          │ │  Currently selected tab's content           │  │
│ ● bridge-demo            │ │                                             │  │
│   fallback · …           │ │                                             │  │
│                          │ │                                             │  │
│ ● iiif-wellcome-…        │ │                                             │  │
│   custom · iiif…         │ │                                             │  │
│                          │ │                                             │  │
│ ● smithsonian-open-…     │ │                                             │  │
│   rest · api.si.edu      │ │                                             │  │
│                          │ │                                             │  │
│ ● wikimedia-commons-…    │ │                                             │  │
│   rest · commons.wiki…   │ │                                             │  │
│                          │ │                                             │  │
└──────────────────────────┴───────────────────────────────────────────────────┘
```

Three sections: the **header**, the **sidebar**, and the **detail pane**.

## Header

| Element | Purpose |
|---|---|
| Title | Just the product name. |
| Count chip | "N loaded / M on disk" — N = sources currently in the live registry, M = YAML files found on disk. If N < M, some files failed validation (look for the red ● in the sidebar). |
| ☀ Light / 🌙 Dark | Theme toggle. Preference persisted in `localStorage`. |
| Help | Opens this documentation in the browser. |
| Browser | Switch to the public browser UI (`/`) for visual asset inspection. |
| API | Opens the auto-generated FastAPI Swagger UI at `/docs`. Useful for testing the Impulse-protocol endpoints directly. |

## Sidebar

The left column lists every YAML file in `configs/sources/`. Each entry shows:

- A colored **status dot**:
  - **● green** — config loaded and active in the registry
  - **● red** — config exists on disk but failed to load (the row's second line shows the error)
  - **● grey** — config not loaded for some other reason (rare)
- The **display name** (from `collection.name`)
- A **kind pill** — `rest`, `fallback`, or `custom`
- A muted second line showing the upstream `base_url` or the error message

Two controls at the top of the sidebar:

- **+ New source ▾** — opens a dropdown with starter templates:
  - **REST API (generic)** — fully-wired skeleton for any JSON API
  - **IIIF Presentation API manifest** — wraps a single IIIF manifest as a collection
  - **Fallback (local files)** — points at a local JSON manifest
- **↻** — re-scans the YAML directory from disk without saving anything. Useful after editing files directly with a text editor.

Clicking a source loads it into the right pane. Clicking again is a no-op. If the current pane has unsaved changes, a confirmation dialog appears.

## Detail header

When a source is selected (or a new one is being drafted), the right pane shows:

| Element | Purpose |
|---|---|
| Title | The collection's `name`. |
| `id: …` pill | The collection's `id`. |
| Status pill | **Saved** if the in-memory state matches disk; **Unsaved changes** (amber) if not. |
| Discard | Visible only when there are unsaved changes — reverts to the last saved YAML. |
| Save & Reload | Persists changes to disk, validates, and triggers a registry hot-reload. Keyboard shortcut: **Ctrl+S**. |
| Delete | (Only for existing sources.) Asks for confirmation, then unlinks the YAML file and removes the collection from the registry. |

## Tabs

Three tabs share the same in-memory config object. Edits in one tab are reflected in the others when you switch:

- **Form** — structured editor with one section per top-level YAML block.
- **YAML** — raw text editor on the same content. Edits here override the form on the next save.
- **Test** — runs a live upstream call against the current (unsaved) configuration and shows the raw response next to the mapped Impulse output.

If you edit in the YAML tab and then switch back to Form, the YAML is parsed and the form is re-rendered from it. If parsing fails, you get a toast and the form is not updated until you fix the syntax.

---

## The Form tab

### Section: Collection

The Impulse-protocol metadata returned by `GET /collections` and `GET /collections/{id}`. Maps directly to YAML's `collection` block.

| Field | Purpose |
|---|---|
| **ID** | The collection identifier. Validated against id-schema (lowercase, digits, hyphens). Cannot collide with another loaded source. |
| **Name** | Display name shown in the Impulse UI and the public browser. |
| **Description** | Free-text description, multi-line. Optional. |
| **Organization** | Institution name. Returned in `GET /collections`. |
| **Owner ID** | Email or identifier of the bridge operator responsible for this source. |
| **Published** | `1` to expose to clients, `0` to hide (useful for staging changes). |

### Section: Adapter

The adapter kind drives most of the rest of the form.

#### Kind: `rest`

| Field | Purpose |
|---|---|
| **Base URL** | The HTTPS root the bridge calls. All `search.path` and `asset_detail.path` are relative to this. |
| **Auth Type** | `none`, `query_param`, or `header`. |
| **Auth Name / Value** | (Only shown if auth is enabled.) The parameter or header name and value. Use `${ENV_VAR}` for secrets — they expand from `.env` at startup. |
| **Timeout (sec)** | HTTP timeout. Default 10. |
| **Default query params** | Key/value list. Sent with **every** search request. Use for static filters (`format=json`), aggregation flags (`profile=rich`), or content filters (`qf=TYPE:IMAGE`). The **+ add** button creates a new row; the **×** removes one. |

#### Kind: `fallback`

| Field | Purpose |
|---|---|
| **Manifest path** | Relative path to a JSON file containing pre-mapped Impulse assets. |
| **Static mount** | If checked, the bridge serves the manifest's directory under `/collections/{id}/` so relative `assetURI` values resolve correctly. Usually leave this on. |

#### Kind: `custom`

| Field | Purpose |
|---|---|
| **Custom class** | Dotted Python path to a class implementing the `Source` protocol. The class must exist in the running bridge process; you cannot add custom Python code through the UI. |
| **Base URL / manifest URL** | Adapter-specific; for IIIF, the manifest URL. |
| **Timeout (sec)** | HTTP timeout for any HTTP work the custom adapter does. |

### Section: Search (REST only)

How Impulse's pagination and search parameters are translated upstream.

| Field | Purpose |
|---|---|
| **Search path** | Appended to the base URL on every search call. |
| **Method** | `GET` (the only supported value in practice). |
| **Search param (Impulse s=)** | The upstream parameter that receives Impulse's `?s=` value. |
| **Default pattern (when ?s missing)** | Sent when the Impulse client did not supply `s`. Some upstreams require a non-empty query — `*` is a common choice. |
| **Pagination style** | Switch between page/size, offset/limit, cursor, or none. The form changes shape to show only the parameters relevant for the chosen style. |
| **Page/Size/Offset/Limit/Cursor params** | Names of the upstream parameters that receive the page or offset and the size or limit. |
| **Page base** | `0` if upstream pages are zero-based, `1` if one-based. |
| **Max page size** | Hard upper bound on the size sent upstream — protects against expensive queries. |

### Section: Mapping

The most important section. Translates upstream JSON into Impulse asset dictionaries.

#### `items_path`

A single JMESPath expression that resolves to the **array** of upstream items. Some examples:

| Upstream shape | `items_path` |
|---|---|
| `{ "items": [...], "totalResults": 42 }` | `items` |
| `{ "response": { "rows": [...], "rowCount": 7 } }` | `response.rows` |
| `{ "query": { "pages": { "151972": {...}, "12345": {...} } } }` | `values(query.pages \|\| \`{}\`)` |
| The whole response IS the array | leave blank |

#### Mapping table

Below `items_path` is a table with one row per Impulse asset field. By default it shows the **internal** (mandatory management) fields and **DC required** fields. Toggle **Show optional Dublin Core fields** to reveal the rest.

Each row has five cells:

| Cell | Meaning |
|---|---|
| **Impulse field** | The field name from the spec. Read-only. |
| **Type** | `expr` (a JMESPath against the raw item) or `literal` (a constant value). |
| **Value** | The expression or literal. |
| **Default** | A fallback used when the expression returns nothing. |
| **Transform** | One of `slugify`, `strip_html`, `lower`, `upper`, or empty. Applied **after** the default and any value-map. |

Leaving a row blank means "don't populate this Impulse field". Filters in the next section can drop assets where required fields turned out empty.

### Section: Filter

Final pass before the asset is returned to the client.

| Field | Purpose |
|---|---|
| **Allowed content types** | Comma-separated MIME types. An asset is dropped if its `contentType` (after mapping) is not in this list. Leave empty to allow any. |
| **Drop if missing** | Comma-separated Impulse field names. An asset is dropped if **any** named field is missing/empty after mapping. Useful for upstreams that mix "has-media" and "no-media" items. |

### Section: Asset detail (REST only)

Optional per-asset lookup. If disabled, `GET /collections/{id}/asset/{aid}` falls back to scanning the default search result.

| Field | Purpose |
|---|---|
| **Enabled** | Off by default. Turn on to use a dedicated upstream endpoint. |
| **Path** | URL path for the detail endpoint. May contain a `{asset_id}` placeholder, e.g. `/items/{asset_id}`. |
| **Detail query params** | Key/value list. **Replaces** (does not merge with) the adapter's `default_query`, because detail and search endpoints typically take different parameter sets. Values may contain `{asset_id}`. |

### Section: Cache

| Field | Purpose |
|---|---|
| **TTL (seconds)** | How long raw upstream responses are kept in memory. Default `600`. Currently shared with the global cache (see [02 — Architecture](02-architecture.md#cache)). |

---

## The YAML tab

A monospace textarea showing the same content as the Form, but as raw YAML. Anything you can do in the Form, you can do here, plus things the Form doesn't expose (comments, unusual ordering, niche features).

Two notes:

- **Edits here override the Form on the next switch.** A dot in the tab label (`YAML •`) means the textarea was edited and the Form will be re-rendered from it.
- **Comments are not preserved across saves through the admin UI.** The bridge re-serializes the parsed config when saving. If you want comments in your YAML files, edit them directly on disk and use the **↻** button.

A status banner under the textarea is:

- **Green** — Pydantic considers the YAML valid.
- **Red** — list of validation errors with `loc` and `msg`. The same list appears as a badge on the Form tab if you switch back without fixing.

---

## The Test tab

Runs the current (unsaved) configuration against the real upstream and shows what comes back.

| Control | Purpose |
|---|---|
| **Query** | The search pattern. Empty = use the configured `pattern_when_empty`. |
| **Count** | How many items to ask for. |
| **Run test** | Sends the current YAML to `POST /admin/api/test`. The bridge constructs an ephemeral Source from the YAML, calls `search()`, and returns both the raw upstream JSON and the mapped Impulse assets. Nothing is saved. |

The result area shows:

- **Upstream URL** — the exact URL the bridge hit, including query string. Copy-paste into curl to verify outside the bridge.
- **Raw upstream response** — the full JSON from the upstream, pretty-printed. Used to figure out which fields to map and where they live.
- **Mapped Impulse output** — what each item looks like after the mapping/filter pipeline. Should match what Unity will see.
- **Errors** — any validation or upstream errors are surfaced above the panes.

Typical workflow:

1. Pick a source. Open the **Test** tab. Click **Run test** with an empty query — confirm you get items.
2. Open the **Form** tab. Notice that some Impulse field is empty or wrong.
3. Look at the **Raw upstream response** in the **Test** tab — find the field you actually want.
4. Open the **Form** tab again. Set the JMESPath in the mapping row for that Impulse field.
5. Switch back to **Test**, click **Run test** again — see the new output.
6. When happy, click **Save & Reload**. The change is persisted and live.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| **Ctrl/Cmd + S** | Save & Reload the current source |
| **Esc** | Close the delete-confirmation modal |

---

## What the admin UI cannot do

- **Add custom Python adapter code.** The `custom_class` field points at code that must already exist in the bridge process. To add a new adapter implementation, edit `app/adapter/custom/` and restart the server.
- **Edit `.env` or environment variables.** Secrets live outside the YAML on purpose. To rotate an API key, edit `.env` and restart.
- **Replace the manifest file used by a fallback source.** The `manifest_path` points at a file the operator must maintain separately.
- **Migrate IDs across collections.** Each collection's data lives upstream. If you rename a collection `id`, Impulse will see it as a new collection — there is no link between old and new.

---

_Continue to [05 — Cookbook](05-cookbook.md)._
