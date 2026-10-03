# IMPULSE Curator — Developer documentation

This folder is the reference for **IMPULSE Curator** (repository `impulse-bridge`), the collection creator of the EU project [IMPULSE](https://euimpulse.eu/) (Horizon Europe, grant agreement 101132704). Visitors search open archives, pick assets and save them as **curated collections**; the Curator serves those collections to the Impulse platform and its Unity clients through the Impulse Collections-and-Assets API.

It is written for:

- **Developers** who work on the backend (`app/`) or the web app (`frontend/`).
- **Operators** who deploy the Curator, configure sources and look after the database.
- **The Impulse consortium**, to see how the component fits into the platform and which parts of the Impulse specification it implements.

These are repository docs. The running app does not serve them; read them on the Git host or in your editor.

## Terms

| Term | Meaning |
|---|---|
| **Source** | An external archive (Europeana, Wikimedia Commons, an IIIF manifest, a local folder). One YAML file in `configs/sources/` each. Searched by the web app through `/api/sources/…`. Not an Impulse collection. |
| **Curated collection** | A visitor's selection of assets, stored in SQLite (`data/curator.db`) and served through the Impulse API at `/collections/{id}`. |
| **Snapshot** | The Impulse asset dict of a source asset, copied into the collection when the asset is added. Unity is served from snapshots, never from the upstream archive. |
| **Edit key / edit link** | Secret that lets someone change a collection: `/c/{id}/edit#key=…`. Shown once at creation; an admin or the editor can replace it. |
| **Listed** | An admin flag: the collection appears in `GET /collections`. Unlisted collections are still reachable by their URI. |
| **Locked** | An admin flag (`disabled` in the API): the collection disappears from the Impulse API and its creator can no longer edit it. |
| **Visible in Unity** | Per asset (`published` in the API). Hidden assets stay in the collection but are not served to Impulse. |
| **Accepted licence** | A licence whose conditions (attribution, share-alike, non-commercial, no derivatives) the admin accepts; default public domain, CC0, CC BY, CC BY-SA. Other assets are not offered, added or served. See [02 — Licences](02-architecture.md#licences). |

## Reading order

- **5 minutes:** [01 — Overview](01-overview.md).
- **30 minutes:** [01](01-overview.md) → [02 — Architecture](02-architecture.md) → [03 — YAML reference](03-yaml-reference.md).
- **Adding or fixing a source:** [04 — Admin UI](04-admin-ui.md) and [05 — Cookbook](05-cookbook.md).
- **Running, deploying, troubleshooting:** [06 — Operations](06-operations.md) and [07 — Deployment](07-deployment.md).

## Contents

| # | Document | What it covers |
|---|---|---|
| 01 | [Overview](01-overview.md) | What the Curator is, the concepts, where it sits relative to Impulse, a demo flow |
| 02 | [Architecture](02-architecture.md) | Components, the three API surfaces, curated collections and snapshots, request flows, hot reload, errors, access model |
| 03 | [YAML reference](03-yaml-reference.md) | Every field of a source config, with type, default and examples |
| 04 | [Admin UI](04-admin-ui.md) | The Collections, Sources (YAML editor, test run) and Settings pages |
| 05 | [Cookbook](05-cookbook.md) | Recipes: add and test a source, map JSON, asset lookups, how a curated collection reaches Unity, … |
| 06 | [Operations](06-operations.md) | Running, environment variables, endpoint reference, mail, rate limits, backups, troubleshooting |
| 07 | [Deployment](07-deployment.md) | Docker + Traefik on a VPS (Oracle Cloud example), basic auth on `/admin`, first-run checklist |
| — | [Legal pages](legal-pages.md) | What imprint, privacy, terms, accessibility and report pages must cover, and the app's facts for them (no cookie consent needed) |

The Impulse specification itself is in the repository root: [`Collections-and-assets-schema,-discovery-and-access.md`](../Collections-and-assets-schema,-discovery-and-access.md).

## Keeping the docs current

The code is the source of truth. When an endpoint, a setting, the YAML schema ([`app/config/schema.py`](../app/config/schema.py)) or the database schema ([`app/curation/db.py`](../app/curation/db.py)) changes, update the matching document in the same change.

---

_Last verified against the code: October 2026._
