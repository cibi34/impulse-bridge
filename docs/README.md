# Impulse Bridge — Documentation

This folder is the complete reference for the **Impulse Bridge** — the adapter service that exposes external digital-heritage archives to the Impulse 3D platform.

It is meant for two audiences:

- **Operators / integrators** who run the bridge and configure new sources via YAML or the admin UI.
- **The Impulse consortium** — to understand how this component fits into the wider platform, and what guarantees it provides against the published Impulse API specification.

The docs are written as a freestanding wiki. You can browse them in any of three ways:

| Medium | URL |
|---|---|
| Inside the running bridge | http://localhost:8080/help |
| As markdown files in this repository | `docs/*.md` |
| Imported into Confluence / Notion / GitHub wiki | copy-paste each file |

## Reading order

If you have **5 minutes**, read just [01-overview](01-overview.md).

If you have **30 minutes**, read [01-overview](01-overview.md) → [02-architecture](02-architecture.md) → [03-yaml-reference](03-yaml-reference.md).

If you are **configuring a new external archive**, read [04-admin-ui](04-admin-ui.md) and [05-cookbook](05-cookbook.md).

If you are **deploying or troubleshooting**, read [06-operations](06-operations.md).

## Contents

| # | Document | What it covers |
|---|---|---|
| 01 | [Overview](01-overview.md) | What the bridge is, what problem it solves, and where it sits relative to Impulse |
| 02 | [Architecture](02-architecture.md) | Components, request flow, hot-reload, error codes, mapping to the Impulse spec |
| 03 | [YAML reference](03-yaml-reference.md) | Every field of a source config, with type, purpose, and examples |
| 04 | [Admin UI](04-admin-ui.md) | A walkthrough of every form section, the YAML tab, and the live-test tab |
| 05 | [Cookbook](05-cookbook.md) | Step-by-step recipes for common patterns (add REST source, add IIIF, map nested JSON, …) |
| 06 | [Operations](06-operations.md) | Running, environment variables, error codes, common upstream issues, observability |
| 07 | [Deployment](07-deployment.md) | Step-by-step: Oracle Cloud VPS + nginx + Let's Encrypt + Basic Auth on `/admin` |

## Versioning

This documentation describes the bridge code that lives in this repository. When the YAML schema or the Impulse protocol contract changes, the corresponding doc must change with it — see the "Last verified" footer at the bottom of each file.
