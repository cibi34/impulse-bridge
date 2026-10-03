# 04 — Admin UI

The admin area is part of the web app at `http://localhost:8080/admin`. It has three pages — **Collections**, **Sources** and **Settings** — and talks to the backend only through `/admin/api/…`.

The app has **no admin login of its own**. In production the reverse proxy protects every path that starts with `/admin` (the pages and the API) with HTTP basic auth — see [07 — Deployment](07-deployment.md). Never expose `/admin` without it.

For field semantics of source configs see [03 — YAML reference](03-yaml-reference.md); for the endpoints see [06 — Operations](06-operations.md#admin-api).

## Header

| Element | Purpose |
|---|---|
| IMPULSE logo + **Admin** pill | — |
| **Collections** / **Sources** / **Settings** | The three pages (`/admin`, `/admin/sources`, `/admin/settings`). |
| Theme switcher | Light / dark / system; remembered in this browser. |
| **Open the app** | Goes to `/explore`. |

---

## Collections

`/admin` — every curated collection, newest change first (`GET /admin/api/collections`).

### Overview

- **Stats:** Total, Submitted, Listed, Locked.
- **Search** by name, id, email or description (press Enter to apply).
- **Show:** All · Submitted · Listed · Locked.

### Table

| Column | Content |
|---|---|
| Collection | Name (links to the public page `/c/{id}`) and id |
| Assets | Number of assets, visible or not |
| Contact | The creator's email, if they gave one (never public) |
| Status | **Submitted** *time ago* or **Not submitted**, plus when it was last updated |
| Listed | Switch — see below; disabled while the collection is locked |
| Locked | Switch — see below |
| Actions | **New edit link** (key icon), **Delete** (bin icon) |

### What the switches do

| Action | Effect |
|---|---|
| **Listed** on | The collection appears in the Impulse API's `GET /collections`. Use it for collections the IMPULSE team has accepted. Unlisted collections are still served at their own URI. |
| **Locked** on | `GET /collections/{id}…` answers code `1` (not found) and the collection disappears from `GET /collections`. Visitors get 404 on its pages; its editor still sees it, marked as locked, but every change is refused. Unlocking restores everything. |
| **New edit link** | Creates a new edit key and shows the link `<origin>/c/{id}/edit#key=…` **once**. The previous edit link stops working immediately; a creator who signs in by email keeps access. Use it for a creator who lost the link. |
| **Delete** | Removes the collection and all its items from the database after a confirmation. Impulse can no longer load it. Cannot be undone (except from a backup). |

Admins cannot edit a collection's content here. If you must, create a new edit link and open it — that also takes the old link away from the creator.

---

## Sources

`/admin/sources` — a YAML editor for the files in `configs/sources/`.

```
┌──────────────────────────┬──────────────────────────────────────────────────────┐
│ Sources                  │ Wikimedia Commons Images                             │
│ [New] [Reload from disk] │ [Live] wikimedia-commons.yaml   Revert Delete [Save] │
│                          │ ┌──────────────────────────────────────────────────┐ │
│ ● IMPULSE Demo Models    │ │ 1  collection:                                   │ │
│   fallback-demo.yaml ·   │ │ 2    id: wikimedia-commons-images                │ │
│   fallback               │ │ …   (YAML, syntax-highlighted, problems marked)  │ │
│ ● Europeana Public …     │ └──────────────────────────────────────────────────┘ │
│   europeana.yaml · rest  │ ✓ Valid configuration                                │
│ ● Wikimedia Commons …    │ ┌ Test run ─────────────────── [pattern] [6] [Run] ┐ │
│   wikimedia-commons.yaml │ │ Upstream request, assets, mapped JSON, raw JSON  │ │
│   · rest                 │ └──────────────────────────────────────────────────┘ │
└──────────────────────────┴──────────────────────────────────────────────────────┘
```

### Source list

One entry per `*.yaml` / `*.yml` file (`GET /admin/api/sources`):

- **Dot:** green — loaded and live; red — the file has a problem (parse error, schema error, duplicate id, or the source could not be built), the message is shown below; grey — not loaded.
- **Name** (`collection.name`, else the id or the filename), then **filename · kind**.

Clicking an entry opens it; the URL becomes `/admin/sources?file=<filename>`, so a file can be linked directly.

| Button | Effect |
|---|---|
| **New** | Opens the template picker: **REST API (generic search/discovery)**, **IIIF Presentation API manifest**, **Fallback (local files)** (`GET /admin/api/templates`). The template is loaded into the editor as a new, unsaved file. |
| **Reload from disk** | Re-reads every file and hot-swaps the registry (`POST /admin/api/reload`), e.g. after editing files with a text editor on the server. A toast reports how many sources are live and how many have problems; the open file is re-read if it has no unsaved changes. |

### Editor

| Element | Purpose |
|---|---|
| Title | `collection.name` of the file, or "New source" |
| Status pill | **Live** (loaded), **Not running** (saved, but the source could not start — the reason is shown in a notice below), **Not loaded**, or **New — not saved** |
| Filename | The file on disk |
| **Unsaved changes** | Shown while the text differs from the saved file |
| **Revert** | Back to the saved text |
| **Delete** | Removes the file after a confirmation (`DELETE /admin/api/files/{filename}`). The source disappears from the web app; curated collections keep the assets they already contain. |
| **Save** / **Create source** | Writes the text and hot-reloads (`PUT /admin/api/files/{filename}` / `POST /admin/api/files`) |

The editor is CodeMirror with YAML highlighting, line numbers and the usual shortcuts (undo, search with Ctrl/Cmd+F, …). There is no save shortcut; use the button.

**Live validation.** About 0.4 s after you stop typing, the text is checked (`POST /admin/api/validate`) — YAML syntax first, then the schema with `${ENV_VAR}` expanded. Problems are underlined on their line in the editor and listed below it as *Line N · path · message*; clicking an entry jumps to the line. Schema errors point at the deepest key of the path that exists in the text, e.g. `search.pagination.style`. Without problems the list reads **Valid configuration**.

**Saving** keeps the text exactly as typed — comments, ordering and formatting survive (line endings are not converted). The rules:

| Situation | Result |
|---|---|
| The text has problems | Not saved (422); the problems are shown in the editor |
| The `collection.id` is already defined by another file | Not saved (409) — a file never takes over another file's source |
| New file | Named after the id (`<id>.yaml`; `<id>-2.yaml` if that name is taken) |
| Changed id in an existing file | Allowed — the file keeps its name and the source is renamed (see [03](03-yaml-reference.md#collection) for what that means for existing collections) |
| Saved, but the source cannot start (e.g. the fallback manifest is missing) | Saved; toast "Saved, but the source could not start: …" and status **Not running** |

Every save and delete reloads all sources atomically; a broken file elsewhere never stops the others.

Leaving the page or opening another file with unsaved changes asks for confirmation.

Broken files can be opened and repaired: the editor works on the file by name, so even a file without a parsable id can be fixed and saved.

### Test run

Below the editor. Runs the **editor's current text** — saved or not — against the real archive (`POST /admin/api/test`). Nothing is saved, and the live source is not touched: the test builds a throw-away source from the text.

| Control | Purpose |
|---|---|
| Search pattern | Empty: the config's `pattern_when_empty` |
| Number of results | 1–50 (default 6) |
| **Run test** | Runs one search |

Results:

| Part | Content |
|---|---|
| Errors | Validation, build or upstream errors, with their location (`adapter`, `upstream`, a YAML path) |
| **Upstream request** | The exact URL that was requested, copyable. Query-parameter API keys are shown as `***`. |
| Assets | "N assets after mapping and filters", with thumbnail, title, kind and the licence the `rights` value is read as — "(not accepted)" when IMPULSE doesn't accept it, so the web app won't offer the asset |
| **Mapped assets (JSON)** | What the mapping produced — what a snapshot would store |
| **Raw upstream response** | The upstream JSON (first 60,000 characters), with the API key replaced by `***` wherever it appears |

The test shares the server's upstream cache: if the same request was made recently, the raw response comes from the cache. The mapping is always applied fresh, so mapping changes show up immediately.

Typical workflow:

1. Open a source (or **New** → a template). Run the test with an empty pattern — do you get items?
2. Open **Raw upstream response** and find the fields you need.
3. Edit the mapping in the editor; problems appear as you type.
4. Run the test again and compare **Mapped assets**.
5. **Save**. The source is live immediately; check it in `/explore`.

---

## Settings

`/admin/settings` — settings stored in the database (`GET`/`PUT /admin/api/settings`). They take effect immediately; no restart.

### Submissions

| Field | Purpose |
|---|---|
| **Submission address** | Where "Submit to IMPULSE" emails go (the team that registers collections). The web app opens the visitor's mail program with a pre-filled message to this address. Without one, visitors are asked to copy the collection details and send them to their IMPULSE contact. |

### Licences

Which licence conditions IMPULSE accepts — tick any of **Attribution** (CC BY), **Share-alike** (… SA), **Non-commercial** (… NC), **No derivatives** (… ND). Default: Attribution and Share-alike, i.e. public domain, CC0, CC BY and CC BY-SA.

A licence is accepted when all of its conditions are ticked: CC BY-NC-SA needs Attribution, Share-alike *and* Non-commercial. Public domain and CC0 have no conditions and are always accepted. Unclear rights (in copyright, not evaluated, missing) and licences other than Creative Commons are never accepted.

Works with a licence that isn't accepted don't appear in the search, can't be added and aren't served to Unity. The setting applies **immediately, also to existing collections**: unticking a condition withdraws such assets from Unity (their editors see them marked "Licence not accepted"); ticking it again brings them back. See [02 — Licences](02-architecture.md#licences).

### Email (SMTP)

Used for sign-in links and "Email me the edit link". Without a working setup, sign-in by email is hidden in the web app.

| Field | Purpose |
|---|---|
| **Server**, **Port** | SMTP host and port (default 587) |
| **Encryption** | **STARTTLS** (default), **SSL/TLS** (implicit TLS, usually port 465) or **None** |
| **Username** | Optional; without it, no SMTP login is attempted |
| **Password** | Write-only: never returned by the API. "Saved — type to replace" when one is stored; **Remove it** deletes it. Disabled when `BRIDGE_SMTP_PASSWORD` is set in the environment, which always wins. |
| **Sender** | `From:` address, e.g. `IMPULSE Curator <curator@example.org>` |

The status pill reads **Email is set up** (server and sender are set), **Email is not set up**, or **Log only (development)** when `BRIDGE_MAIL_LOG_ONLY=true` — then mails are written to the server log instead of being sent.

**Revert** discards unsaved edits; **Save settings** stores only the fields that changed. Invalid values (e.g. a port outside 1–65535) are refused.

### Send a test email

Sends a test message with the **saved** settings (`POST /admin/api/settings/test-email`); disabled while there are unsaved changes. SMTP errors are shown as they come from the server (e.g. "The SMTP server rejected the username or password").

### Server

Read-only values from the environment (change them in `.env` and restart): public address (`BRIDGE_PUBLIC_BASE_URL`), `owner_id` of collections, default organization, assets per collection, source config directory, database file.

---

## What the admin cannot do

- **Change environment settings or API keys.** They live in `.env`; edit it and restart.
- **Add Python adapters.** `custom_class` must point at code that is already deployed (`app/adapter/custom/`).
- **Upload fallback files.** Manifests and media of fallback sources are maintained on disk.
- **Edit a collection's content** — only list, lock, delete it or issue a new edit link.
- **Authenticate anyone.** Access control for `/admin` is the reverse proxy's job.

---

_Last verified against the code: October 2026._

_Continue to [05 — Cookbook](05-cookbook.md)._
