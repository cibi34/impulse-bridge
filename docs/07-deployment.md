# 07 — Deployment

This guide deploys the Curator to a free Oracle Cloud VPS with **Docker + Traefik**, set up as a small multi-project host: after the bootstrap, the same VM can host more projects with one `docker-compose.yml` each. Any Ubuntu 22.04 / 24.04 server works the same way.

The first run takes **30–45 minutes**. Updates are `git pull` + `docker compose up -d --build`.

## Target architecture

```
                          Internet
                              │
                              ▼ HTTPS (443) + HTTP → HTTPS redirect (80)
                       ┌──────────────┐
                       │   Traefik    │  reverse proxy, Let's Encrypt,
                       │              │  routing by Docker labels,
                       │              │  basic auth on /admin, /docs, /openapi.json
                       └──────┬───────┘
                              │ Docker network "edge"
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ impulse- │    │  future  │    │  future  │
        │  bridge  │    │ project  │    │ project  │
        └──────────┘    └──────────┘    └──────────┘

Disk layout on the VM:
/srv/
├── traefik/                    ← platform (set up once)
│   ├── docker-compose.yml
│   ├── .env                    ← LE_EMAIL
│   └── letsencrypt/acme.json   ← certificates
└── impulse-bridge/
    ├── docker-compose.yml      ← copy of deploy/docker-compose.yml
    ├── deploy/Dockerfile
    ├── .env                    ← BRIDGE_DOMAIN, BRIDGE_BASIC_AUTH, API keys, …
    ├── configs/                ← bind-mounted: source configs (admin saves land here)
    ├── data/                   ← bind-mounted: curator.db (BACK IT UP) + fallback files
    └── (rest of the source)
```

### The image

[`deploy/Dockerfile`](../deploy/Dockerfile) is a two-stage build:

1. **`node:24-alpine`** — `npm ci` and `npm run build` in `frontend/`. Node exists only in this stage.
2. **`python:3.12-slim`** — installs the backend (`pip install .`), copies `app/` and the web app build to `/app/frontend/build`, runs as uid **10001** (`impulse`) and starts:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips=*
   ```
   `--proxy-headers` makes the real client IP visible to the rate limits.

`configs/` and `data/` are **not** in the image; they come from the bind mounts. `.env`, `node_modules`, the local build and `data/*.db` are excluded by `.dockerignore`.

### Routing

[`deploy/docker-compose.yml`](../deploy/docker-compose.yml) defines two Traefik routers for `BRIDGE_DOMAIN`:

| Router | Paths | Auth |
|---|---|---|
| `bridge-admin` | `PathPrefix(/admin)` — the admin pages **and** `/admin/api/…` — plus `PathPrefix(/docs)` and `/openapi.json` | basic auth (`BRIDGE_BASIC_AUTH`) |
| `bridge-public` | everything else: web app, `/api/…`, `/collections…`, `/sources/…`, `/health` | none |

The app itself has no admin login, so the basic-auth router is what protects the admin.

## Before you start

- [ ] An Oracle Cloud free account (or any Ubuntu 22.04 / 24.04 VPS)
- [ ] An SSH key on your machine (`ssh-keygen`)
- [ ] The repository
- [ ] DNS access for your domain (this guide uses `impulse-bridge.octo-code.de`)
- [ ] Optional but recommended: an SMTP account for sign-in and edit-link emails

---

## Step 1 — Create the VM

(Skip if you have a fresh VM.)

1. Sign in to https://cloud.oracle.com/
2. **Compute → Instances → Create instance**
3. Configure:
   - **Image**: Ubuntu 24.04 LTS Aarch64 (recommended) or x86_64
   - **Shape**: ARM `VM.Standard.A1.Flex` with **1 OCPU / 6 GB RAM** (inside the free allowance), or AMD `VM.Standard.E2.1.Micro`
   - **Primary VNIC**: **Assign a public IPv4 address**
   - **SSH keys**: upload your public key
4. **Create** and note the public IP.

The image builds on ARM and x86_64 alike. The Node build stage needs more memory than the running app; on the 1 GB AMD shape it may fail, so prefer the ARM shape.

## Step 2 — Open ports 80 and 443 in OCI

Ports must be opened in **two** places: the cloud Security List (here) and the OS firewall (the bootstrap script does that).

1. Instance → **Primary VNIC → Subnet** → the subnet
2. **Default security list for vcn-…**
3. **Ingress rules → Add Ingress Rules**:

| Source CIDR | Source port range | Destination port range | Protocol |
|---|---|---|---|
| 0.0.0.0/0 | All | 80 | TCP |
| 0.0.0.0/0 | All | 443 | TCP |

## Step 3 — DNS

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `impulse-bridge` | `<VM public IP>` | 300 |

```bash
dig +short impulse-bridge.octo-code.de     # must print the VM's IP
```

Do not continue until DNS resolves — Let's Encrypt's HTTP-01 challenge fails otherwise.

## Step 4 — Bring the code to the VM

```bash
ssh ubuntu@<VM public IP>
```

### Option A — Git

```bash
sudo apt-get update && sudo apt-get install -y git
sudo mkdir -p /srv
sudo git clone https://github.com/<you>/impulse-bridge /srv/impulse-bridge
```

### Option B — rsync from your machine

From the project root on **your machine**:

```bash
rsync -avz \
  --exclude .venv --exclude .git --exclude __pycache__ --exclude '*.egg-info' \
  --exclude .env --exclude .claude --exclude .idea --exclude .vscode \
  --exclude node_modules --exclude frontend/build --exclude frontend/.svelte-kit \
  --exclude 'data/*.db' --exclude 'data/*.db-*' \
  ./ ubuntu@<VM public IP>:/tmp/impulse-bridge/
```

Then on the VM:

```bash
sudo mkdir -p /srv
sudo rsync -a /tmp/impulse-bridge/ /srv/impulse-bridge/
rm -rf /tmp/impulse-bridge
```

**Always exclude `data/*.db*`** — otherwise a later rsync overwrites the production database with your local one.

## Step 5 — Bootstrap the host (once)

```bash
cd /srv/impulse-bridge
sudo LE_EMAIL=you@example.com bash deploy/host-bootstrap.sh
```

The script ([`deploy/host-bootstrap.sh`](../deploy/host-bootstrap.sh), idempotent):

1. Installs Docker Engine and the Compose plugin from Docker's apt repository.
2. Adds your SSH user to the `docker` group (log out and back in once).
3. Enables UFW with SSH, 80 and 443.
4. Creates the shared `edge` Docker network.
5. Installs Traefik (`traefik:v3.6`) at `/srv/traefik/` and starts it.

```bash
docker ps        # traefik listening on 0.0.0.0:80 and :443
```

## Step 6 — Configure the Curator

On the VM, in `/srv/impulse-bridge/`:

```bash
cp deploy/.env.production.example .env
cp deploy/docker-compose.yml ./docker-compose.yml

# The container runs as uid 10001. It writes configs/ (admin saves) and
# data/ (the database), so both must be writable for that uid.
sudo chown -R 10001:10001 configs data
```

> Files you later add under `configs/sources/` or `data/` from the host need the same `chown`. Files created through the admin already belong to 10001.

Edit `.env` (`nano .env`):

| Variable | Required | Notes |
|---|---|---|
| `BRIDGE_DOMAIN` | yes | Public hostname, e.g. `impulse-bridge.octo-code.de`. Compose derives `BRIDGE_PUBLIC_BASE_URL=https://${BRIDGE_DOMAIN}` from it — don't set that yourself; the compose value wins. |
| `BRIDGE_BASIC_AUTH` | yes | htpasswd line for the admin, with every `$` doubled (below). |
| `EUROPEANA_API_KEY` | for Europeana | Free at https://pro.europeana.eu/get-api |
| `BRIDGE_CORS_ALLOW_ORIGINS` | recommended | Origins of the Impulse web frontend(s) that call `/collections` from a browser, comma-separated. `*` allows any. |
| `BRIDGE_COLLECTION_OWNER_ID`, `BRIDGE_DEFAULT_ORGANIZATION` | no | Metadata published for every curated collection (defaults `impulse-curator`, `IMPULSE Curator`). |
| `BRIDGE_SMTP_PASSWORD` | no | SMTP password from the environment instead of the database. |
| `BRIDGE_LOG_LEVEL`, `BRIDGE_DEFAULT_CACHE_TTL` | no | See [06](06-operations.md#environment-variables). |

Do **not** set `BRIDGE_MAIL_LOG_ONLY` in production — mails would only be logged.

`BRIDGE_PUBLIC_BASE_URL` must be the public **https** address. It goes into every collection URI that Impulse registers, into the fallback file URLs stored in snapshots, and into sign-in and edit links; an `https://` value also switches the session cookie to `Secure` / `__Host-`. Decide on the domain before visitors create collections — changing it later breaks registered URIs.

SMTP host, sender and the submission address are not in `.env`; set them in the admin after the first start (Step 9).

### Generating `BRIDGE_BASIC_AUTH`

Compose treats `$` as a variable marker, so every `$` of the hash must be doubled:

```bash
docker run --rm httpd:2.4 htpasswd -nbB admin "YOUR-PASSWORD-HERE" | sed 's/\$/\$\$/g'
# admin:$$2y$$05$$Vc7M3o2...
```

Paste the whole line as `BRIDGE_BASIC_AUTH=…`.

## Step 7 — Build and start

```bash
cd /srv/impulse-bridge
docker compose up -d --build
```

The first build pulls `node:24-alpine` and `python:3.12-slim`, installs the npm and pip dependencies and builds the web app — a few minutes on a small VM. Later builds reuse cached layers.

```bash
docker compose logs -f bridge
```

Ready when the log shows `Registered 4 source(s), 0 config error(s)` (one per file in `configs/sources/`) and `Application startup complete.` On the first start, the database `data/curator.db` is created (`Applying database migration 1`, `… 2`). Traefik then discovers the container, requests the certificate (about 30 s on the first request) and routes by the labels.

## Step 8 — Verify

```bash
B=https://impulse-bridge.octo-code.de

curl $B/health                          # {"code":0,…,"data":{"status":"ok","sources":[…],"collections":0}}
curl $B/api/sources                     # the four sources
curl -I $B/                             # 200, the web app
curl -I $B/admin                        # 401 — basic auth enforced
curl -I $B/admin/api/settings           # 401 — the admin API too
curl -u admin:<password> -I $B/admin    # 200
```

In a browser:

- `https://impulse-bridge.octo-code.de/` — the web app
- `https://impulse-bridge.octo-code.de/admin` — the admin (the browser asks for the credentials)

## Step 9 — First-run checklist

- [ ] **Admin → Sources:** every source has a green dot. Open Europeana and **Run test** — code 20 / "Upstream auth failed" means the API key in `.env` is missing or wrong (fix it, `docker compose up -d`). A missing key does not turn the dot red; only searches fail.
- [ ] **Admin → Settings → Email (SMTP):** server, port, encryption, username, password, sender. **Save settings**, then **Send a test email**.
- [ ] **Admin → Settings → Submissions:** the address of the IMPULSE team that registers collections.
- [ ] **Legal pages:** imprint, privacy, terms, accessibility and the report page (`frontend/src/routes/(site)/legal/*`, `…/report`) ship with placeholder text; [legal-pages.md](legal-pages.md) lists what each must cover. Fill them in and rebuild (`docker compose up -d --build`) before the site goes public.
- [ ] **End to end:** create a test collection in `/explore`, open its edit page, check `curl $B/collections/<id>/assets`, sign in by email once. Delete the test collection in the admin afterwards.
- [ ] **CORS:** set `BRIDGE_CORS_ALLOW_ORIGINS` to the Impulse frontend origin(s) if `*` is too open.
- [ ] **Backups:** schedule the database backup (below) and copy it off the VM.

---

## Day-2 operations

### Logs

```bash
docker compose -f /srv/impulse-bridge/docker-compose.yml logs -f bridge
docker compose -f /srv/traefik/docker-compose.yml logs -f traefik     # access log, certificates
```

### Restart / rebuild

```bash
cd /srv/impulse-bridge
docker compose restart bridge          # same image, e.g. after editing a file on disk
docker compose up -d                   # apply .env changes
docker compose up -d --build           # after a code change
```

### Back up the database

`data/curator.db` holds every collection, snapshot and setting, and is not in Git. It runs in WAL mode; back it up with SQLite's backup API (safe while running):

```bash
cd /srv/impulse-bridge
docker compose exec bridge python -c "import sqlite3; sqlite3.connect('data/curator.db').backup(sqlite3.connect('data/curator-backup.db'))"
# copy data/curator-backup.db off the VM, e.g. with scp or rclone
```

Daily via cron (`crontab -e` as a user in the `docker` group):

```
30 3 * * * cd /srv/impulse-bridge && docker compose exec -T bridge python -c "import sqlite3; sqlite3.connect('data/curator.db').backup(sqlite3.connect('data/curator-backup.db'))"
```

Also keep copies of `configs/sources/` and `.env`. Restore: `docker compose stop bridge`, replace `data/curator.db` with the backup, remove `data/curator.db-wal` and `data/curator.db-shm`, `chown 10001:10001` the file, `docker compose start bridge`.

### Update to a new version

```bash
cd /srv/impulse-bridge
# 1. back up the database (above)
# 2. get the code
git pull --ff-only                   # or rsync (exclude data/*.db*!)
# 3. if deploy/docker-compose.yml changed: cp deploy/docker-compose.yml ./docker-compose.yml
docker compose up -d --build
```

The bind-mounted `configs/` and `data/` and the `.env` stay untouched. Database migrations run automatically at start; there are no down-migrations — restore the backup to go back.

### Change the admin password

```bash
docker run --rm httpd:2.4 htpasswd -nbB admin "NEW-PASSWORD" | sed 's/\$/\$\$/g'
# paste as BRIDGE_BASIC_AUTH=… into /srv/impulse-bridge/.env
cd /srv/impulse-bridge && docker compose up -d
```

### Rotate an API key

Edit `.env`, then `docker compose up -d`.

### Certificates

Traefik renews certificates within 30 days of expiry. Check occasionally:

```bash
docker compose -f /srv/traefik/docker-compose.yml logs traefik | grep -i acme
```

### Free up space

```bash
docker image prune -f
docker builder prune -f      # the multi-stage build leaves build cache behind
```

---

## Adding a second project

1. **DNS:** an A record, e.g. `myapp`, to the VM's IP.
2. **Folder:** `/srv/myapp/`.
3. **docker-compose.yml:**

```yaml
services:
  app:
    image: my-app-image:latest       # or build: .
    networks:
      - edge
    labels:
      - traefik.enable=true
      - traefik.docker.network=edge
      - traefik.http.routers.myapp.rule=Host(`myapp.octo-code.de`)
      - traefik.http.routers.myapp.entrypoints=websecure
      - traefik.http.routers.myapp.tls.certresolver=letsencrypt
      - traefik.http.services.myapp.loadbalancer.server.port=3000

networks:
  edge:
    external: true
    name: edge
```

4. `cd /srv/myapp && docker compose up -d`. Traefik picks it up, requests a certificate and routes — no Traefik restart.

---

## Hardening

- **SSH:** `PasswordAuthentication no`, `PermitRootLogin no` in `/etc/ssh/sshd_config`, then `sudo systemctl restart ssh`.
- **fail2ban:** `sudo apt-get install -y fail2ban && sudo systemctl enable --now fail2ban`.
- **Unattended upgrades:** `sudo apt-get install -y unattended-upgrades && sudo dpkg-reconfigure --priority=low unattended-upgrades`.
- **Cloudflare** (optional): proxied DNS with SSL mode **Full (strict)**. Then the client IP reaches the app via `X-Forwarded-For` through two proxies; check that rate limits still see real visitors.

---

## Troubleshooting

### Traefik answers 404 or "no available server"

The container is not on the `edge` network or `traefik.enable=true` is missing.

```bash
docker network inspect edge | grep impulse-bridge
docker compose -f /srv/traefik/docker-compose.yml logs --tail 50 traefik | grep -i "bridge\|provider"
```

### Certificate provisioning fails

- DNS not propagated: `dig +short impulse-bridge.octo-code.de`.
- Port 80 not reachable: OCI Security List (Step 2), `sudo ufw status`.

```bash
docker compose -f /srv/traefik/docker-compose.yml logs traefik | grep -i acme
```

### `permission denied` on `/var/run/docker.sock`

You are not in the `docker` group yet: log out and back in.

### The container exits or restarts in a loop

```bash
docker compose -f /srv/impulse-bridge/docker-compose.yml logs --tail 100 bridge
```

- `sqlite3.OperationalError: unable to open database file` / `PermissionError` under `/app/data` → `sudo chown -R 10001:10001 data`.
- A broken source YAML does **not** stop the container: it is reported (`Source config … not loaded: …`) and only that source is missing. Fix it in **Admin → Sources**.

### Saving in the admin fails with a permission error

`configs/` is not writable for uid 10001: `sudo chown -R 10001:10001 configs`.

### Collection URIs or email links show `http://` or the wrong host

`BRIDGE_PUBLIC_BASE_URL` comes from `BRIDGE_DOMAIN` in the compose file. Check `BRIDGE_DOMAIN` in `.env` and that you copied the current `deploy/docker-compose.yml`.

### Every visitor gets "Too many requests"

The rate limits see the proxy's IP instead of the visitors'. The image starts uvicorn with `--proxy-headers --forwarded-allow-ips=*`; if you run another command, keep these flags.

### Forgot the admin password

Generate a new hash (see "Change the admin password") and `docker compose up -d`.

### Traefik dashboard

Uncomment the `labels:` block in `/srv/traefik/docker-compose.yml`, set `DASHBOARD_DOMAIN` and `DASHBOARD_BASIC_AUTH` in `/srv/traefik/.env`, then `cd /srv/traefik && docker compose up -d`.

---

## Quick reference

| What | Command / path |
|---|---|
| Logs (live) | `docker compose -f /srv/impulse-bridge/docker-compose.yml logs -f bridge` |
| Restart | `cd /srv/impulse-bridge && docker compose restart bridge` |
| Rebuild + restart | `cd /srv/impulse-bridge && docker compose up -d --build` |
| Back up the database | `docker compose exec bridge python -c "import sqlite3; sqlite3.connect('data/curator.db').backup(sqlite3.connect('data/curator-backup.db'))"` |
| Database | `/srv/impulse-bridge/data/curator.db` |
| Source configs | `/srv/impulse-bridge/configs/sources/` |
| Environment | `/srv/impulse-bridge/.env` |
| Traefik logs | `docker compose -f /srv/traefik/docker-compose.yml logs -f traefik` |
| Certificates | `/srv/traefik/letsencrypt/acme.json` |
| Health | `curl https://impulse-bridge.octo-code.de/health` |

## Not covered

- **High availability.** One VM, one container — required anyway, since registry, cache and rate limits are per process and SQLite is a local file.
- **Centralized logging and metrics.** `docker compose logs` is enough at this scale.
- **CI/CD.** A pipeline can SSH in and run the update commands.

---

_Last verified on Ubuntu 24.04 LTS (Aarch64), Oracle Cloud Free Tier, Docker 27.x, Traefik v3.6, October 2026._
