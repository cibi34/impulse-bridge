# 01 — Overview

## What the bridge is

The Impulse Bridge is a small HTTP service. From the perspective of the Impulse 3D platform, it looks like an additional **asset-service node** speaking the Impulse Collections-and-Assets API. Internally, it forwards each request to an external digital-heritage archive — Europeana, Wikimedia Commons, Smithsonian Open Access, an IIIF manifest, or any other archive that exposes a JSON API — and translates the response back into the Impulse schema.

In one sentence: **the bridge makes any external archive look like a native Impulse collection**, without modifying the platform itself.

## Why it exists

The Impulse platform has its own database for collections that consortium partners upload. That gives the consortium control over a curated, well-described set of assets, but it is closed: assets that live in third-party archives are not directly reachable from inside the 3D world.

Cultural-heritage assets relevant to the project sit in many places — Europeana aggregates millions of items from European institutions, Wikimedia Commons holds open-licensed media, the Smithsonian publishes CC0 objects (including 3D models), and individual museums expose IIIF manifests. The bridge lets Impulse users browse and place those assets in the 3D world **as if** they were part of an Impulse collection, while leaving the actual hosting where it already is.

## Where it sits

```
                    ┌──────────────────────────────────┐
   Unity client ──► │ Impulse Platform API (discovery) │
                    └──────────────────────────────────┘
                                  │  GET /collections
                                  ▼
                       returns a list including:
              ┌────────────────────────┬────────────────────────┐
              │ uri: …/leuven-vesalius  │ uri: …/wikimedia-…   │ ← bridge
              │ uri: …/leuven-extras    │ uri: …/europeana-…   │ ← bridge
              │ uri: …/leuven-slides    │ uri: …/iiif-…        │ ← bridge
              └────────────────────────┴────────────────────────┘
                            │                       │
                            ▼                       ▼
                ┌──────────────────────┐  ┌────────────────────┐
                │ KU Leuven asset node │  │   Impulse Bridge   │  (this project)
                │  (the platform's     │  │                    │
                │   own collections)   │  │   ┌─────────────┐  │
                └──────────────────────┘  │   │ /collections│  │
                                          │   │ /…/assets   │  │
                                          │   │ /…/asset/X  │  │
                                          │   └─────────────┘  │
                                          └──────────┬─────────┘
                                                     │
                                  ┌──────────────────┼──────────────────┐
                                  ▼                  ▼                  ▼
                          ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                          │  Europeana  │    │  Wikimedia  │    │ Smithsonian │
                          │    API      │    │   Commons   │    │ Open Access │
                          └─────────────┘    └─────────────┘    └─────────────┘
```

The bridge is **not** the platform API. It is a peer asset-service node, of the same kind that hosts the consortium's own collections — just one that happens to delegate to external APIs.

## What "looks like an Impulse asset-service node" means

The bridge implements exactly the four endpoints defined in the Impulse "Collections and assets schema, discovery and access" specification:

| Specification endpoint | Bridge endpoint | Notes |
|---|---|---|
| `GET <platform_api>/collections` | `GET /collections` | Lists all virtual collections configured on this bridge |
| `GET <collection_uri>` | `GET /collections/{id}` | Single collection metadata |
| `GET <collection_uri>/assets` | `GET /collections/{id}/assets` | Asset discovery, supports `?s=`, `?o=`, `?c=` |
| `GET <collection_uri>/asset/<asset_id>` | `GET /collections/{id}/asset/{asset_id}` | Single asset detail |

Every response uses the spec's envelope `{code, message, data}`. Pagination (`o` and `c`) and search patterns (`s` with `*` wildcards) work exactly as the spec describes — the bridge translates them into each upstream archive's particular dialect.

## What's in the box (default configuration)

The bridge ships with five virtual collections preconfigured. They are illustrative — operators are expected to add their own.

| Collection ID | Backend | Key needed | Highlights |
|---|---|---|---|
| `bridge-demo` | Local files | No | Three placeholder assets (.glb, .png). Always works, even offline. Useful as a smoke test. |
| `wikimedia-commons-images` | Wikimedia Commons (MediaWiki API) | No | Open-licensed images. ~100 million items across all topics. |
| `europeana-public-domain-images` | Europeana Record API | Yes (`EUROPEANA_API_KEY`) | Aggregated images from European cultural institutions. |
| `smithsonian-open-access` | Smithsonian openaccess API | Yes (`SMITHSONIAN_API_KEY`) | CC0 objects from US museums. Image-focused by default. |
| `iiif-wellcome-vererbung` | Single IIIF manifest | No | One illustrated 1929 book from the Wellcome Collection. Demonstrates the IIIF custom adapter. |

## What the bridge intentionally does not do

These limitations are deliberate. They keep the bridge small and reduce legal, infrastructure, and operational risk:

- **It does not re-host asset bytes.** Unity downloads assets directly from the original host (`upload.wikimedia.org`, `iiif.wellcomecollection.org`, etc.). The bridge only ships metadata and resolved URLs. This avoids storage costs, bandwidth, license complications, and stale copies.
- **It does not write to external archives.** It is read-only. There is no "upload to Europeana" path through the bridge.
- **It does not implement cross-archive federation.** Each archive is a separate Impulse collection; the bridge does not merge results into a single virtual super-collection.
- **It does not manage Impulse user accounts, permissions, or analytics.** Those belong to the platform itself.

## When the bridge is the right tool

- A user-curated external archive should be browsable from inside Impulse.
- Adding archives should be cheap (a YAML file, not a code release).
- The platform team does not want to take operational responsibility for caching, transforming, and serving external metadata.

## When the bridge is not the right tool

- The asset volume is so high that bandwidth or rate limits become a problem — push the operator toward a periodic ingest into the platform's own DB instead.
- You need write access (uploads, annotations) into an external archive — that's a separate, source-specific integration.
- The external "archive" is a single proprietary system with bespoke auth (OAuth + signed requests + custom pagination) — write a small wrapper service rather than stretching the declarative YAML adapter.

## A 90-second demo flow for the consortium

1. Open `http://localhost:8080/` in a browser. The public browser UI loads.
2. From the **Collection** dropdown, pick "Wikimedia Commons Images".
3. Search for `van gogh sunflowers`. Within a second, a grid of real Commons thumbnails appears.
4. Click one. The detail modal shows mapped Dublin Core metadata and a direct link to the original image.
5. Open `http://localhost:8080/admin`. The admin UI lists all configured sources.
6. Pick the same Wikimedia source. The **Form** tab shows the structured config; the **YAML** tab shows the raw file; the **Test** tab can run a live query and show the raw upstream JSON side-by-side with the mapped Impulse output.
7. Edit the title mapping (e.g. add `transform: strip_html`), click **Test** again, and observe the difference — without saving.
8. Save. The change is written to disk and the registry is hot-reloaded. The public browser UI reflects the new mapping immediately.

That covers everything the bridge does end-to-end.

---

_Continue to [02 — Architecture](02-architecture.md) for the technical details._
