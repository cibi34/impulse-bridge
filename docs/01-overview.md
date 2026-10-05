# 01 — Overview

## What the Curator is

IMPULSE Curator is a web app with a small HTTP backend, built for the EU project [IMPULSE](https://euimpulse.eu/) (Horizon Europe, GA 101132704). Visitors search open cultural-heritage archives, pick assets and save them as **curated collections**. Every curated collection is served through the Impulse **Collections-and-Assets API**, so the Impulse platform and its Unity clients can load it like any other Impulse collection.

In one sentence: **the Curator turns a visitor's selection from open archives into a native Impulse collection**, without copying any media and without changing the platform.

## Why it exists

The Impulse platform hosts collections that consortium partners upload. Many relevant assets, however, live in third-party archives: Europeana aggregates millions of items from European institutions, Wikimedia Commons holds open-licensed media, and museums and libraries expose IIIF manifests.

The Curator lets people browse those archives in one place, put together a themed selection, and hand it to Impulse as a collection. Media stays where it is hosted; the Curator stores only metadata and URLs.

## Concepts

| Concept | Where it lives | Who uses it |
|---|---|---|
| **Source** — an archive, described by one YAML file | `configs/sources/*.yaml`, loaded into an in-memory registry | The web app searches it via `/api/sources/…` |
| **Curated collection** — a named, ordered list of assets | SQLite, `data/curator.db` | Visitors create and edit it in the web app; Impulse/Unity read it via `/collections/{id}` |
| **Snapshot** — the asset's metadata at the time it was added | Inside the collection, in SQLite | Served to Unity; refreshed on demand ("Update from sources") |
| **Licence** — what an asset's `rights` value allows | Read from each snapshot (`app/licensing.py`); which conditions are accepted is an admin setting | Only assets with an accepted licence are offered, added and served; each collection lists its licences and credits |

Sources are **not** Impulse collections any more. Earlier versions exposed each archive as a "virtual collection" under `/collections`; now `/collections` serves only curated collections.

## Where it sits

```
   Unity client ──► Impulse platform (collection list)
                         │  registered collection URIs, e.g.
                         │  https://curator.example/collections/masters-of-light-k3m9x2
                         ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  IMPULSE Curator                                             │
   │                                                              │
   │  Impulse API     /collections/{id}[/assets|/asset/{aid}]     │ ◄── Unity / platform
   │                  served from SQLite snapshots                │
   │                                                              │
   │  Web app         /, /explore, /c/{id}, /c/{id}/edit, /my …   │ ◄── visitors (browser)
   │  Web app API     /api/sources/…, /api/collections/…, …       │
   │                                                              │
   │  Admin           /admin, /admin/api/…  (basic auth at proxy) │ ◄── operators
   └───────────────┬──────────────────────────────────────────────┘
                   │ live search and asset lookups (cached)
      ┌────────────┼───────────────┐
      ▼            ▼               ▼
  Europeana    Wikimedia      IIIF manifests
               Commons        (e.g. Codex Manesse)
```

The Curator is a peer **asset-service node**, of the same kind that hosts the consortium's own collections. It is not the platform API: the platform keeps its own list of collections, and a curated collection gets into that list when the IMPULSE team registers its URI (see [05 — Cookbook, "How a curated collection reaches Unity"](05-cookbook.md#recipe-13--how-a-curated-collection-reaches-unity)).

## The Impulse endpoints it implements

| Specification endpoint | Curator endpoint | Notes |
|---|---|---|
| `GET <platform_api>/collections` | `GET /collections` | Curated collections an administrator **listed** |
| `GET <collection_uri>` | `GET /collections/{id}` | Every collection that is not locked, listed or not |
| `GET <collection_uri>/assets` | `GET /collections/{id}/assets` | Assets visible in Unity; `?s=`, `?o=`, `?c=` |
| `GET <collection_uri>/asset/<asset_id>` | `GET /collections/{id}/asset/{asset_id}` | One asset |

Every response uses the spec's envelope `{code, message, data}`. Search (`s`, with `*` wildcards) and paging (`o`, `c`) work inside the collection's own assets; illegal `o`/`c` values return the entire result set, as the spec requires.

## Sources in the box

Five sources are configured out of the box. They are examples; operators add their own.

| Source id | Backend | Key needed | Notes |
|---|---|---|---|
| `bridge-demo` | Local files (`data/fallback/assets/`) | No | Three generated glTF models (textured cube, sphere, column) and an image, CC0. Work offline; for end-to-end tests with Unity. |
| `wikimedia-commons-images` | Wikimedia Commons (MediaWiki API) | No | Open-licensed images; titles cleaned with `file_title`. |
| `europeana-public-domain-images` | Europeana Search API | Yes (`EUROPEANA_API_KEY`) | Open-licensed images from European institutions. |
| `iiif-codex-manesse` | One IIIF manifest | No | The Codex Manesse (Heidelberg University Library, public domain), 871 pages named after the manuscript's table of contents; shows the IIIF adapter. |
| `smk-open-art` | SMK Open API (Statens Museum for Kunst) | No | Public-domain paintings, prints and drawings of the Danish National Gallery; images sized through the IIIF Image API. |

## What the Curator intentionally does not do

- **It does not re-host media.** Browsers and Unity load assets directly from the original hosts (`upload.wikimedia.org`, `digi.ub.uni-heidelberg.de`, …). Only local fallback files are served by the Curator itself.
- **It does not write to archives.** Sources are read-only.
- **It does not register collections in the Impulse platform.** "Submit to IMPULSE" opens a pre-filled email to the IMPULSE team; the team adds the collection URI to the platform.
- **It has no user accounts.** Editing is protected by an edit key; an optional passwordless sign-in by email lets creators reach their collections on other devices. The admin area relies on HTTP basic auth at the reverse proxy.

## A five-minute demo

1. Open `http://localhost:8080/`. The home page explains the four steps (Find, Select, Create, Submit).
2. Go to **Explore**, pick **Wikimedia Commons Images** (or **All sources**) and search for `sunflowers`.
3. Select a few works. The selection bar at the bottom counts them; keep searching other sources if you like.
4. Create the collection: give it a name and an optional description. The app opens the edit page and keeps the edit link in this browser.
5. On the edit page, reorder assets, switch one off under **Visible in Unity**, and copy the **Collection URL**.
6. Ask the Impulse API what Unity would get:
   ```bash
   curl http://localhost:8080/collections/<collection-id>/assets
   ```
   The hidden asset is missing; the others come back in your order.
7. Open `http://localhost:8080/admin`. On **Collections**, switch **Listed** on — the collection now appears in `GET /collections`.
8. On **Sources**, open `wikimedia-commons.yaml`, run a **Test run**, change a mapping (for example drop `transform: file_title`), run it again, and see the difference before saving anything.

---

_Last verified against the code: October 2026._

_Continue to [02 — Architecture](02-architecture.md)._
