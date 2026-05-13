# 06 — Operations

How to run, configure, and troubleshoot the bridge.

## System requirements

- Python 3.12 or newer (tested with 3.12 and 3.13).
- No database, no Redis — everything is in-process.
- Outbound HTTPS to the configured archives (no inbound dependencies beyond the bridge itself).
- A few hundred MB of memory; CPU is negligible for any realistic POC traffic.

## Installation

```powershell
# In the project directory
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

On Linux/macOS the same commands work with `.venv/bin/python`.

## Configuration

The bridge reads its configuration from three places, in order of precedence:

1. Environment variables (or a `.env` file in the project root).
2. The YAML files in `configs/sources/`.
3. Compiled-in defaults in `app/settings.py`.

### Environment variables

Copy `.env.example` to `.env` and edit as needed. The bridge reads `.env` once at process start; restart the server to pick up changes.

| Variable | Default | Purpose |
|---|---|---|
| `BRIDGE_HOST` | `0.0.0.0` | Listen address (advisory — `uvicorn` honors its own `--host` flag if passed). |
| `BRIDGE_PORT` | `8080` | Listen port. |
| `BRIDGE_CONFIG_DIR` | `configs/sources` | Where the bridge looks for YAML files. |
| `BRIDGE_DATA_DIR` | `data` | Root for fallback adapter data files. |
| `BRIDGE_LOG_LEVEL` | `INFO` | Standard Python logging level. |
| `BRIDGE_DEFAULT_CACHE_TTL` | `600` | Default cache TTL in seconds. |
| `BRIDGE_PUBLIC_BASE_URL` | `http://localhost:8080` | Used to construct the `uri` field on each collection. Set this to the externally-visible URL if the bridge is behind a reverse proxy. |
| `EUROPEANA_API_KEY` | _(empty)_ | Used by `configs/sources/europeana.yaml` via `${EUROPEANA_API_KEY}`. |
| `SMITHSONIAN_API_KEY` | _(empty)_ | Used by `configs/sources/smithsonian.yaml`. |

Any other variable referenced as `${MY_VAR}` in a YAML file should also live in `.env`.

### Where to put API keys

Inside YAML files, **never** hard-code secrets. Always use `${VAR}` and put the real value in `.env`. `.env` is excluded by `.gitignore`. `.env.example` is committed but contains only placeholder values.

## Running the bridge

### Foreground (development)

```powershell
.venv\Scripts\python -m uvicorn app.main:app --port 8080
```

The terminal will print structured logs. Press Ctrl+C to stop. **Do not** type curl commands in this window — uvicorn blocks the terminal. Open a second window for testing.

### Background

For longer-running test sessions, start uvicorn detached. On Windows PowerShell:

```powershell
Start-Process -FilePath .venv\Scripts\python.exe `
    -ArgumentList "-m","uvicorn","app.main:app","--port","8080" `
    -RedirectStandardOutput bridge.log -RedirectStandardError bridge.err -NoNewWindow
```

To stop it later:

```powershell
(Get-NetTCPConnection -LocalPort 8080 -State Listen).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

### Behind a reverse proxy

Set `BRIDGE_PUBLIC_BASE_URL` to the external URL (e.g. `https://bridge.impulse.eu`). Forward `/collections/*`, `/admin/*`, `/help/*`, `/` to the bridge; the rest does not need to be exposed.

### Containerized

A Dockerfile is not bundled with the bridge (POC). For deployment, a Dockerfile would only need:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Mount `configs/` and `.env` as volumes so they're operator-managed; the rest is immutable code.

## Health check

```bash
curl http://localhost:8080/health
```

Returns the Impulse envelope. The `data` field includes the list of registered source IDs, which is useful for monitoring (e.g. alert if a known source disappears).

```json
{"code": 0, "message": "OK", "data": {"status": "ok", "sources": ["bridge-demo", "wikimedia-commons-images", ...]}}
```

## Hot-reload vs server restart

| Change | Action |
|---|---|
| Edit a YAML file via the admin UI | Hot-reload happens automatically on Save. |
| Edit a YAML file directly on disk | Click **↻** in the admin sidebar, or `POST /admin/api/sources/...` to force a reload. |
| Add or remove a YAML file | Same — hot-reload via the admin UI. |
| Change a value in `.env` | **Restart the server.** `.env` is read once at process start. |
| Change Python code (adapters, transform, …) | **Restart the server.** No code reload. |
| Change `app/settings.py` defaults | **Restart the server.** |

## Error codes (reference)

Every public response has a `code` field. The full list:

| `code` | meaning | HTTP status | typical fix |
|---|---|---|---|
| 0 | OK | 200 | — |
| 1 | Collection not found | 404 | Check `/collections` — is the source registered? Did the YAML fail to load? |
| 2 | Asset not found | 404 | The asset id was not in the (cached or live) result set. Configure `asset_detail` for direct lookup. |
| 10 | Upstream source unavailable | 503 | Network problem, timeout, or upstream 5xx. Retry; check upstream's status page. |
| 11 | Upstream rate limit reached | 503 | Slow down; check the upstream's rate-limit policy. Increase `cache.ttl_seconds` to reduce request volume. |
| 12 | Upstream returned malformed data | 502 | Often a 400 from the upstream — bad query syntax. Check **Test** tab's upstream URL. |
| 20 | Bridge configuration error | 500 | Missing/invalid API key, 401/403 from upstream, or invalid YAML at startup. Check the `error` field in `/admin/api/sources`. |
| 99 | Internal bridge error | 500 | Unhandled exception. Check the server logs. |

## Common upstream issues

### "Upstream auth failed (401)"

Cause: the API key environment variable is empty or wrong.

Fix:

1. Confirm the variable name in the YAML (`adapter.auth.value: "${YOUR_KEY}"`).
2. Check `.env` contains the corresponding line with the real key.
3. Restart the server (`.env` is read at startup, not at every request).
4. In the admin UI's **Test** tab, run a query — the upstream URL pane shows the actual params sent. If `wskey=` is empty, the env var didn't expand.

### Wikimedia 403 "robot policy"

Cause: User-Agent header doesn't identify the operator.

Fix: nothing — the bridge already sends a compliant User-Agent (`ImpulseBridge/0.1 (https://github.com/impulse-consortium/impulse-bridge; bridge@impulse.eu)`). If you fork the bridge for a different project, update the User-Agent string in `app/adapter/rest.py` accordingly.

### Smithsonian DEMO_KEY rate-limited

Cause: the DEMO_KEY is shared and very limited.

Fix: register a free key at https://api.data.gov/signup/. Set `SMITHSONIAN_API_KEY` in `.env`. Restart.

### Europeana returns items but no media URLs

Cause: many Europeana records have only `edmIsShownAt` (a landing-page link), not `edmIsShownBy` (a direct media URL).

Fix: keep `filter.drop_if_missing: [assetURI, previewURI]`. This removes records that aren't usable in the 3D world. Also keep `media: "true"` in `default_query` to ask Europeana to pre-filter.

### IIIF manifest 404 or schema mismatch

Cause: the manifest URL has moved, or the manifest uses an unusual structure (mixed v2/v3, or v3 without painting annotations).

Fix:

1. Confirm the manifest loads in a browser.
2. In the admin UI's **Test** tab, the upstream URL and raw response will show what the bridge actually got back.
3. If the manifest is in an exotic shape, extend `app/adapter/custom/iiif.py` to handle it.

### CORS errors in Unity

Cause: Unity is loading the asset URL directly (`upload.wikimedia.org`, `iiif.wellcomecollection.org`, …) and the host doesn't send a permissive `Access-Control-Allow-Origin`.

Note: this is **not** a bridge issue — Unity goes around the bridge for asset bytes. Workarounds:

- For Unity desktop/standalone builds: CORS doesn't apply.
- For Unity WebGL builds: configure a CORS-proxy on the same origin as Unity. The bridge could be extended to proxy a subset of media URLs if needed — but the default design is intentional pass-through.

## Observability

Out of the box, the bridge logs:

- Per-source load events at startup and after every hot-reload.
- Per-request upstream URL (`DEBUG` level).
- Per-request cache hit/miss (`DEBUG`).
- Any caught exception with traceback (`ERROR`).

For production monitoring:

- Scrape `/health` periodically — alert if `data.sources` doesn't include expected IDs.
- Tail logs for `Failed to build source` or `ERROR` lines.
- Optionally instrument with `prometheus-fastapi-instrumentator` (one-line drop-in) for request rate and latency.

## Performance characteristics

- Each upstream request is async. A single bridge process can handle dozens of concurrent in-flight requests with negligible CPU.
- The cache eliminates duplicate upstream calls for identical queries within `cache.ttl_seconds`. In tests, cache hits are ~15× faster than upstream calls.
- Asset bytes never flow through the bridge — bandwidth is therefore decoupled from asset size.

The practical bottleneck is upstream rate limits, not bridge resources.

## Backup and recovery

The bridge has no persistent state of its own. To back up:

- `configs/sources/*.yaml` — the source configurations.
- `data/` — only matters if you have fallback collections with local files.
- `.env` — secrets and per-deployment overrides.

That's it. Lose the cache, lose nothing. Lose the registry, lose nothing. Restore the three things above and the bridge comes back to exactly its previous state.

## Upgrading

Pull the new code, install any new dependencies, restart:

```powershell
git pull
.venv\Scripts\python -m pip install -e ".[dev]"
# Restart the server
```

Source configurations are stable across upgrades unless the YAML schema changes — in which case the changelog will call it out.

## Security notes

The current build is a POC and does **not** implement:

- Authentication on `/admin/*` or `/admin/api/*` — anyone with network access can edit sources.
- HTTPS — terminate TLS at a reverse proxy (nginx, Caddy, Traefik, …).
- Rate limiting on the bridge's own endpoints.
- Audit logging of who changed which YAML.

For local development this is fine. **Do not expose the bridge to the public internet without adding at least HTTPS and admin authentication.**

The simplest authentication option is HTTP Basic Auth at the reverse proxy, restricted to the `/admin/*` and `/admin/api/*` paths.

---

_Continue back to the [README](README.md) for the table of contents._
