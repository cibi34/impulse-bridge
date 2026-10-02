# 06 — Operations

How to run, configure, back up and troubleshoot the Curator. For the Docker deployment see [07 — Deployment](07-deployment.md).

## Requirements

| What | Version / note |
|---|---|
| Python | 3.12 or newer |
| Node.js | 22.17 or newer, only to build the web app (`engine-strict`; the Docker build uses Node 24) |
| SQLite | the one bundled with Python; nothing to install |
| Network | outbound HTTPS to the archives; an SMTP server for sign-in and edit-link emails (optional) |
| Process model | **one** process (one uvicorn worker): registry, cache and rate limits are in memory |

## Installation

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

cd frontend
npm ci
npm run build          # → frontend/build, served by FastAPI
cd ..
```

On Linux/macOS use `.venv/bin/python`. Without the build, the API works and every page answers 503 "The web app has not been built".

## Running

### Backend

```powershell
cp .env.example .env
.venv\Scripts\python -m uvicorn app.main:app --port 8080
```

- `http://localhost:8080/` — web app, `/admin` — admin (no login locally), `/docs` — OpenAPI UI.
- Add `--reload` to restart on Python changes.
- `.env.example` sets `BRIDGE_MAIL_LOG_ONLY=true`: sign-in and edit-link emails are written to the console, so you can copy the links from there.
- The database `data/curator.db` is created and migrated at first start.

Detached on Windows:

```powershell
Start-Process -FilePath .venv\Scripts\python.exe `
    -ArgumentList "-m","uvicorn","app.main:app","--port","8080" `
    -RedirectStandardOutput bridge.log -RedirectStandardError bridge.err -NoNewWindow

# stop
(Get-NetTCPConnection -LocalPort 8080 -State Listen).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

### Web app development

```bash
cd frontend
npm run dev            # http://localhost:5173
```

The dev server proxies `/api`, `/collections`, `/sources`, `/admin/api` and `/health` to `CURATOR_BACKEND` (default `http://127.0.0.1:8080`), so run the backend as well. Signed-in edits are only accepted from the origin of `BRIDGE_PUBLIC_BASE_URL`; to test sign-in through the dev server, start the backend with `BRIDGE_PUBLIC_BASE_URL=http://localhost:5173`.

### Tests and checks

```powershell
.venv\Scripts\python -m pytest -q     # backend, ~135 tests, no network needed

cd frontend
npm test              # vitest unit tests
npm run check         # svelte-check / TypeScript
npm run lint          # prettier --check + eslint
```

## Configuration

Precedence: process environment > `.env` in the working directory > defaults in [`app/settings.py`](../app/settings.py). Source configs live in `configs/sources/*.yaml`; site settings (submission address, SMTP) live in the database and are edited in the admin.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BRIDGE_PUBLIC_BASE_URL` | `http://localhost:8080` | The public address, **without** trailing path. Used for collection URIs, fallback file URLs stored in snapshots, sign-in and edit links, and the origin check of signed-in writes. An `https://` value also turns on secure `__Host-` session cookies and HSTS. In Docker it is set from `BRIDGE_DOMAIN`. |
| `BRIDGE_CONFIG_DIR` | `configs/sources` | Source YAML files. |
| `BRIDGE_DATA_DIR` | `data` | Directory of the default database file. (Fallback `manifest_path`s resolve against the working directory, not this.) |
| `BRIDGE_DATABASE_PATH` | `<BRIDGE_DATA_DIR>/curator.db` | SQLite file. |
| `BRIDGE_FRONTEND_DIR` | `frontend/build` | The web app build. |
| `BRIDGE_LOG_LEVEL` | `INFO` | Python logging level. |
| `BRIDGE_DEFAULT_CACHE_TTL` | `600` | TTL of the upstream cache, seconds. |
| `BRIDGE_CORS_ALLOW_ORIGINS` | `*` | Comma-separated origins allowed to call the Impulse API (and fallback files) from a browser. Never applies to `/api` or `/admin`. |
| `BRIDGE_COLLECTION_OWNER_ID` | `impulse-curator` | `owner_id` of every curated collection in the Impulse API. |
| `BRIDGE_DEFAULT_ORGANIZATION` | `IMPULSE Curator` | `organization` of collections that have none. |
| `BRIDGE_MAX_ASSETS_PER_COLLECTION` | `500` | Size limit of a collection. (A single create request carries at most 500 items, an add request at most 200.) |
| `BRIDGE_SMTP_PASSWORD` | — | SMTP password; overrides the one stored in the admin, for secrets that must stay out of the database. |
| `BRIDGE_MAIL_LOG_ONLY` | `false` | Log emails (with their links) instead of sending them. Development only. |
| `EUROPEANA_API_KEY` | — | Referenced by the bundled source configs as `${…}`. Any other `${VAR}` in a YAML is read the same way. |
| `BRIDGE_DOMAIN`, `BRIDGE_BASIC_AUTH` | — | Docker Compose / Traefik only (see [07](07-deployment.md)). |
| `CURATOR_BACKEND` | `http://127.0.0.1:8080` | `npm run dev` only: where the dev server proxies API calls. |

Never put secrets into YAML files; reference them as `${VAR}` and keep the values in `.env` (ignored by Git).

## Endpoint reference

### Impulse API

Envelope `{code, message, data}`; CORS-enabled.

| Method | Path | Purpose |
|---|---|---|
| GET | `/collections` | Listed, unlocked collections, by name |
| GET | `/collections/{id}` | Collection metadata; code 1 if unknown or locked |
| GET | `/collections/{id}/assets` | Visible assets in order; `?s=` (`*` wildcards), `?o=`, `?c=`; illegal `o`/`c` → everything |
| GET | `/collections/{id}/asset/{asset_id}` | One visible asset; code 2 otherwise |
| GET, HEAD | `/health` | `{status, sources: [ids], collections: <count>}` |

### Web app API

Plain JSON. Errors are `{"detail": "…"}` with a matching status; errors that come from a source also carry the Impulse `code` (`{"detail": "…", "code": 1}`); request validation errors are FastAPI's `{"detail": [{loc, msg, …}]}`.

"Edit" means `Authorization: Bearer <edit key>`, or the session of the email address the collection was created with.

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/config` | — | `app_name`, `submission_email`, `sign_in_available`, `max_assets_per_collection` |
| GET | `/api/sources` | — | Configured sources: `id`, `name`, `description`, `organization` |
| GET | `/api/sources/{id}/assets` | — | Search: `?s=`, `?o=`, `?c=` (default 24, max 100), `?type=image\|model` → `{source, items, offset, next_offset}` |
| GET | `/api/sources/{id}/assets/{asset_id}` | — | One asset of a source |
| POST | `/api/collections` | create limit | `{name, description?, organization?, email?, items: [{source, asset_id}]}` → `201 {collection, edit_key, failed}` |
| GET | `/api/collections?ids=a,b` | — | Overviews with up to 4 previews (≤ 100 ids; unknown and locked ids are left out) |
| GET | `/api/collections/{id}` | optional | Public view (visible items); with edit access the editor view (all items, `email`, `locked`) |
| PATCH | `/api/collections/{id}` | edit | `name`, `description`, `organization`, `email` (`""` removes it) |
| DELETE | `/api/collections/{id}` | edit | Delete → 204 |
| POST | `/api/collections/{id}/items` | edit | Add `{items: [{source, asset_id}]}` (1–200) → `{added, failed}`; assets already present are skipped |
| PATCH | `/api/collections/{id}/items/{asset_id}` | edit | `{published: true\|false}` — visible in Unity |
| DELETE | `/api/collections/{id}/items/{asset_id}` | edit | Remove → 204 |
| PUT | `/api/collections/{id}/order` | edit | `{asset_ids: [...]}` — every item exactly once |
| POST | `/api/collections/{id}/refresh` | edit | Re-fetch snapshots → `{refreshed, failed}` |
| POST | `/api/collections/{id}/submitted` | edit | Record the submission → `{submitted_at}` |
| POST | `/api/collections/{id}/email-link` | edit key only | Email the edit link to the collection's address → `202 {sent_to}` |
| POST | `/api/collections/{id}/key` | edit | New edit key → `{edit_key}`; the old one stops working |
| POST | `/api/auth/login` | login limit | `{email}` → `202`, always the same answer; 503 if email is not available |
| POST | `/api/auth/verify` | — | `{token}` → session cookie, `{email}`; 400 if invalid or expired |
| GET | `/api/auth/me` | — | `{email}` or `{email: null}` |
| POST | `/api/auth/logout` | — | End the session → 204 |
| GET | `/api/me/collections` | session | Overviews of the signed-in address's collections; 401 without session |

Typical statuses: 401 no credentials (`WWW-Authenticate: Bearer`), 403 wrong key, someone else's collection, locked, or a signed-in write from another origin, 404 unknown, 422 invalid input or collection full, 429 rate limit (`Retry-After`).

### Admin API

Plain JSON; no app-level authentication — protect `/admin` at the proxy.

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/api/collections` | All collections incl. email, `listed`, `disabled`, `submitted_at` |
| PATCH | `/admin/api/collections/{id}` | `{listed?, disabled?}` |
| DELETE | `/admin/api/collections/{id}` | Delete with items → 204 |
| POST | `/admin/api/collections/{id}/key` | New edit key → `{edit_key}` |
| GET | `/admin/api/sources` | Every config file: `filename`, `id`, `name`, `kind`, `base_url`, `loaded`, `error`; plus `loaded_count`, `load_errors` |
| POST | `/admin/api/reload` | Reload all files from disk; returns the same as `GET /admin/api/sources` |
| GET | `/admin/api/files/{filename}` | `{filename, yaml, id, valid, errors: [{loc, msg, line}], loaded, load_error}` |
| POST | `/admin/api/files` | Create from `{yaml}` → 201; file named after the id |
| PUT | `/admin/api/files/{filename}` | Save `{yaml}` verbatim |
| DELETE | `/admin/api/files/{filename}` | Delete the file |
| POST | `/admin/api/validate` | `{yaml}` → `{valid, errors, id}`; never saves |
| POST | `/admin/api/test` | `{yaml, query?, count=5}` → `{valid, errors, transformed, raw_upstream, upstream_url}`; API key masked |
| GET | `/admin/api/templates` | Starter configs `{key, label, yaml}` |
| GET / PUT / DELETE | `/admin/api/sources/{id}` | The same by source id (`PUT ?create=true` refuses existing ids). Not used by the admin pages; kept for scripts. |
| GET | `/admin/api/settings` | Site settings without the password, plus `smtp_password_set`, `smtp_password_from_env`, `mail_configured`, `mail_log_only`, `server` |
| PUT | `/admin/api/settings` | Change the fields sent; `smtp_password: ""` removes it |
| POST | `/admin/api/settings/test-email` | `{to}` → `{sent_to}`; 502 with the SMTP error |

File endpoints answer 422 `{"detail": {"errors": [...]}}` for invalid text and 409 when the id belongs to another file. Filenames must match `[A-Za-z0-9][A-Za-z0-9._-]*.yaml|.yml`.

### Other

| Method | Path | Purpose |
|---|---|---|
| GET, HEAD | `/sources/{id}/files/{path}` | Files next to a fallback source's manifest (`static_mount: true`) |
| GET | `/docs`, `/openapi.json` | FastAPI's API documentation |
| GET | everything else | The web app |

## Health check

```bash
curl http://localhost:8080/health
# {"code":0,"message":"OK","data":{"status":"ok","sources":["europeana-public-domain-images","bridge-demo",…],"collections":3}}
```

`HEAD /health` works too, for monitors that only check the status. Alert when an expected source id is missing from `data.sources`.

## What needs a restart

| Change | Action |
|---|---|
| A source YAML via the admin | Nothing — saving hot-reloads. |
| A source YAML on disk, a new or removed file | **Reload from disk** in the admin, or `POST /admin/api/reload`. |
| Site settings (submission address, SMTP) | Nothing — read on every use. |
| `.env` / environment (API keys, `BRIDGE_*`) | **Restart.** |
| Python code | **Restart** (or run with `--reload`). |
| Web app code, legal pages | `npm run build` in `frontend/` (in Docker: rebuild the image). No backend restart needed for a local build. |
| Database schema | Migrations run automatically at start. |

## Email

Emails sent by the server: sign-in links, "Email me the edit link", admin test emails. The **Submit to IMPULSE** email is *not* sent by the server — it opens the visitor's mail program.

Set up:

1. **Admin → Settings → Email (SMTP):** server, port, encryption (STARTTLS on 587, or SSL/TLS on 465), username, password, sender (`IMPULSE Curator <curator@example.org>`). Email counts as set up when server and sender are set.
2. **Save settings**, then **Send a test email**.
3. Optionally keep the password out of the database: set `BRIDGE_SMTP_PASSWORD` and restart; the password field is then disabled.
4. **Submissions → Submission address:** where "Submit to IMPULSE" goes.

The sender domain should allow the SMTP server to send for it (SPF/DKIM), or the links land in spam. SMTP connections time out after 15 s.

Sign-in rules: links only go to addresses that collections were created with; the answer never reveals whether a mail was sent; at most 5 links per address and hour; a link works once, for 15 minutes; a session lasts 30 days. Without email, sign-in is hidden in the web app and `POST /api/auth/login` answers 503.

Development: `BRIDGE_MAIL_LOG_ONLY=true` logs every mail at `WARNING` level with its text and link instead of sending it.

## Rate limits

Per client IP, sliding window, in memory ([`app/ratelimit.py`](../app/ratelimit.py), [`app/api/auth.py`](../app/api/auth.py)):

| Limit | Applies to | Value |
|---|---|---|
| Create | `POST /api/collections` | 30 per hour |
| Write | every other write under `/api/collections/…` (shared budget) | 1,200 per hour |
| Sign-in | `POST /api/auth/login` | 10 per hour |
| Links per address | sign-in emails to one address | 5 per hour (silently skipped) |

Exceeding a limit answers 429 with `Retry-After`. Counters reset on restart. Reads, the Impulse API and the admin are not limited.

The client IP is `request.client.host`. Behind a reverse proxy, uvicorn must trust the proxy headers, otherwise all visitors share the proxy's address and its limits: the Docker image runs `uvicorn --proxy-headers --forwarded-allow-ips=*`.

## Backups

| What | Why |
|---|---|
| `data/curator.db` | **Everything visitors created:** collections, snapshots, edit-key hashes, site settings, sessions. Not in Git. |
| `configs/sources/` | Source configs (may be edited in the admin). |
| `.env` | Secrets and deployment settings. |
| `data/fallback/` | Only if you added your own local files. |

The database runs in WAL mode (`curator.db-wal`, `curator.db-shm` next to it). Do not copy the file while the server runs; use SQLite's backup API, which is safe while it runs:

```powershell
# local
.venv\Scripts\python -c "import sqlite3; sqlite3.connect('data/curator.db').backup(sqlite3.connect('data/curator-backup.db'))"
```

```bash
# Docker (the image has Python but no sqlite3 CLI); the file appears in the host's data/
docker compose exec bridge python -c "import sqlite3; sqlite3.connect('data/curator.db').backup(sqlite3.connect('data/curator-backup.db'))"
```

Copy the backup off the machine. Restore: stop the server, replace `data/curator.db` with the backup, delete `curator.db-wal` and `curator.db-shm`, start.

Losing the cache or the registry loses nothing; both are rebuilt.

## Upgrading

```powershell
# back up data/curator.db first
git pull
.venv\Scripts\python -m pip install -e ".[dev]"
cd frontend; npm ci; npm run build; cd ..
# restart the server
```

New database migrations run at start (`Applying database migration N` in the log). There are no down-migrations: to go back, restore the backup taken before the upgrade.

## Error codes

Impulse `code` values (also in web app API errors that come from a source):

| `code` | Meaning | HTTP | Typical fix |
|---|---|---|---|
| 0 | OK | 200 | — |
| 1 | Collection / source not found | 404 | Unknown id, or the collection is locked. For a source: did its YAML load? (Admin → Sources) |
| 2 | Asset not found | 404 | Hidden or removed asset; for a source, configure `asset_detail` (see [05, Recipe 8](05-cookbook.md#recipe-8--configure-asset_detail)). |
| 10 | Upstream unavailable | 503 | Network, timeout or upstream 5xx; retry, check the archive's status. |
| 11 | Upstream rate limit | 503 | Slow down; get a personal API key. |
| 12 | Upstream malformed | 502 | Usually a 400 — bad query; check the test run's upstream request. |
| 20 | Configuration error | 500 | Missing or wrong API key (upstream 401/403), source cannot be built. |
| 99 | Internal error | 500 | See the server log (traceback). |

## Troubleshooting

### The web app

| Symptom | Cause and fix |
|---|---|
| Every page: "The web app has not been built" (503) | Run `npm ci && npm run build` in `frontend/`, or check `BRIDGE_FRONTEND_DIR`. |
| Sign-in is not offered | Email is not set up (Admin → Settings), and `BRIDGE_MAIL_LOG_ONLY` is off. |
| "Cross-site request refused" when editing while signed in | The page's origin differs from `BRIDGE_PUBLIC_BASE_URL`. Set it to the exact address visitors use (scheme, host, port). |
| Sign-in link never arrives | Only addresses with collections get links, at most 5 per hour. Check the log for "Sending the sign-in link failed" and test SMTP in the admin. |
| Sign-in link or edit link points to `localhost` | `BRIDGE_PUBLIC_BASE_URL` is not set to the public address. |
| "Too many requests" for everyone | Proxy headers are not trusted, so all visitors share one IP (see Rate limits). |
| Adding an asset fails with "Asset not found" | The source cannot look the asset up again: configure `asset_detail`. |
| Images of a local (fallback) source are broken in a collection | The source was renamed or removed, or `BRIDGE_PUBLIC_BASE_URL` changed after the asset was added: snapshots store absolute `/sources/{id}/files/…` URLs. Restore the source id, then **Update from sources** on the edit page. |
| A collection is missing from `GET /collections` | It is not listed (Admin → Collections) or it is locked. Its own URI works unless it is locked. |

### Sources

**"Upstream auth failed (401)" / code 20.** The variable in `adapter.auth.value` is empty or wrong: check `.env`, restart, run the test — an empty `api_key=` (instead of `***`) in the upstream request means the variable did not expand.

**A source has a red dot.** Its file failed to parse, validate or build; the message says why. The other sources keep running. Open the file in the editor — problems are marked on their lines.

**Wikimedia 403 "robot policy".** Wikimedia requires a descriptive User-Agent; the REST adapter sends `IMPULSE-Curator/0.1 (+<BRIDGE_PUBLIC_BASE_URL>)` (`app/adapter/rest.py`), and the imprint on that site is the contact. Make sure `BRIDGE_PUBLIC_BASE_URL` is the real public address.


**Europeana returns items without media.** Many records only link to a landing page (`edmIsShownAt`). Keep `media: "true"` in `default_query` and `drop_if_missing: [assetURI, previewURI]`.

**IIIF manifest fails.** Check that the URL loads in a browser and run the test. Exotic manifests (mixed v2/v3, v3 without painting annotations) need changes in `app/adapter/custom/iiif.py`.

**Unity WebGL cannot load a media file (CORS).** Unity loads media directly from the archive's host; whether that host sends `Access-Control-Allow-Origin` is outside the Curator's control. Desktop builds are not affected. Files of local sources (`/sources/{id}/files/…`) are CORS-enabled by `BRIDGE_CORS_ALLOW_ORIGINS`.

## Observability

The log (stdout) contains: source loads and config errors at start and after every reload (`Registered N source(s), M config error(s)`), database migrations, failed mail sends, unhandled exceptions with traceback (`ERROR`), and — at `DEBUG` — cache hits. uvicorn adds the access log.

For monitoring: poll `GET /health`; alert on `ERROR` lines and on `Source config … not loaded`.

## Performance

- Upstream calls are async; cached raw responses are reused for identical requests within the TTL.
- The Impulse API reads SQLite only; it is independent of archive speed, rate limits and outages.
- Media never flows through the Curator (except local fallback files).

The practical bottleneck is upstream rate limits during searching, not the server.

## Security notes

In place:

- Edit keys, login tokens and session ids are stored as SHA-256 hashes; edit keys are compared in constant time.
- Edit links carry the key in the URL fragment, which browsers never send to the server; the web app stores it in `localStorage` and removes it from the address bar.
- Session cookie: `HttpOnly`, `SameSite=Lax`, and `Secure` + `__Host-` prefix for an `https://` public base URL. Signed-in writes from another origin are refused.
- CORS only on the Impulse API and local files; `/api` and `/admin` are same-origin only.
- Archive images are loaded with `crossorigin="anonymous"` and `referrerpolicy="no-referrer"`: the browser sends no cookies and no referrer to the archives and ignores cookies they set (Wikimedia's image servers set an identifier cookie on every image otherwise). Together with the browser storage being limited to what visitors use themselves (selection, their collections and edit keys, appearance, the session cookie after sign-in), the site needs no cookie consent. An image server added later must send `Access-Control-Allow-Origin`, or its previews show as unavailable.
- Security headers on every response (`X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP, HSTS on https); the web app's CSP is hash-based.
- Creator emails are never published; `owner_id` is a fixed value.
- Rate limits on anonymous writes and sign-in.

Not in place — handled by the deployment:

- **No authentication on `/admin` and `/admin/api`.** Anyone who reaches them can change sources, settings and collections. Put them behind basic auth at the proxy (the bundled Traefik setup does).
- **No TLS.** Terminate HTTPS at the proxy.
- **No audit log** of admin changes.

---

_Last verified against the code: October 2026._

_Continue to [07 — Deployment](07-deployment.md)._
