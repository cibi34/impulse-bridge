# 07 — Deployment

This guide walks you through deploying the Impulse Bridge to a free Oracle Cloud VPS using **Docker + Traefik** as a multi-project hosting platform. After the bootstrap, the same VM can host any number of additional projects with minimal extra work.

The whole process takes **30–45 minutes** the first time. Updates are a `git pull` + `docker compose up -d --build`. Adding a new project later is a single `docker-compose.yml` file in its own folder.

## Target architecture

```
                          Internet
                              │
                              ▼ HTTPS (443) + HTTP redirect (80)
                       ┌──────────────┐
                       │   Traefik    │  ← reverse proxy
                       │              │     auto Let's Encrypt
                       │              │     Docker label-based routing
                       └──────┬───────┘
                              │ (Docker network "edge")
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ impulse- │    │  future  │    │  future  │
        │  bridge  │    │ project  │    │ project  │
        └──────────┘    └──────────┘    └──────────┘

Disk layout on the VM:
/srv/
├── traefik/                    ← platform (run once, stays up forever)
│   ├── docker-compose.yml
│   ├── .env                    ← LE_EMAIL only
│   └── letsencrypt/acme.json   ← cert storage, persists across restarts
├── impulse-bridge/             ← first project
│   ├── docker-compose.yml      ← copy of deploy/docker-compose.yml
│   ├── Dockerfile              ← deploy/Dockerfile
│   ├── .env                    ← BRIDGE_DOMAIN, BRIDGE_BASIC_AUTH, API keys
│   ├── configs/                ← bind-mounted → admin UI saves persist
│   ├── data/                   ← bind-mounted → fallback assets
│   └── (rest of the source)
└── (future projects in their own folders)
```

## Before you start — checklist

- [ ] An Oracle Cloud free account (or any Ubuntu 22.04 / 24.04 VPS)
- [ ] An SSH key on your local machine (`ssh-keygen` if you don't have one)
- [ ] The bridge code locally (this repository)
- [ ] DNS access for your domain (this guide uses `impulse-bridge.octo-code.de`)

---

## Step 1 — Create the Oracle Cloud VM

(Skip if you already have a fresh VM.)

1. Sign in to https://cloud.oracle.com/
2. Top-left menu → **Compute → Instances → Create instance**
3. Configure:
   - **Name**: `impulse-host`
   - **Image**: Ubuntu 24.04 LTS Aarch64 (recommended) or Ubuntu 24.04 LTS x86_64
   - **Shape**: click **Change shape**
     - ARM image: `VM.Standard.A1.Flex`, set **1 OCPU / 6 GB RAM** (well within the free 4 OCPU / 24 GB allowance)
     - AMD image: `VM.Standard.E2.1.Micro`
   - **Primary VNIC**: confirm **Assign a public IPv4 address** is checked
   - **SSH keys**: upload your public key
4. **Create**. After ~1 minute the VM is **Running** with a public IP — note it.

## Step 2 — Open ports 80 and 443 in OCI

**Critical Oracle gotcha #1.** Ports must be opened in TWO places: the cloud-level Security List, and the OS-level firewall (UFW handles that one — script does it for you).

In the OCI console:

1. From the instance details → **Primary VNIC → Subnet** → click the listed subnet
2. Click **Default security list for vcn-...**
3. **Ingress rules → Add Ingress Rules** twice:

| Source CIDR | Source port range | Destination port range | Protocol |
|---|---|---|---|
| 0.0.0.0/0 | All | 80 | TCP |
| 0.0.0.0/0 | All | 443 | TCP |

(Port 22 for SSH is already there by default.)

## Step 3 — DNS

At your DNS provider (where `octo-code.de` is managed):

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `impulse-bridge` | `<VM public IP>` | 300 |

Verify from your local machine:

```bash
dig +short impulse-bridge.octo-code.de
# should print your VM's public IP
```

**Do not proceed until DNS resolves.** Let's Encrypt's HTTP-01 challenge will fail otherwise.

## Step 4 — Bring the code to the VM

SSH in:

```bash
ssh ubuntu@<VM public IP>     # ARM images use "ubuntu"; some others use "opc"
```

Get the bridge code onto the VM. Two options:

### Option A — Git

Push the bridge to a Git repo first (GitHub/GitLab/Codeberg), then on the VM:

```bash
sudo apt-get update && sudo apt-get install -y git
sudo mkdir -p /srv
sudo git clone https://github.com/<you>/impulse-bridge /srv/impulse-bridge
```

### Option B — rsync from your laptop

From your **local machine**, in the bridge project root:

```bash
rsync -avz \
  --exclude .venv --exclude .git --exclude __pycache__ \
  --exclude '*.egg-info' --exclude .env \
  ./ ubuntu@<VM public IP>:/tmp/impulse-bridge/
```

Then on the VM:

```bash
sudo mkdir -p /srv
sudo rsync -a /tmp/impulse-bridge/ /srv/impulse-bridge/
rm -rf /tmp/impulse-bridge
```

## Step 5 — Bootstrap the host (one-time)

On the VM:

```bash
cd /srv/impulse-bridge
sudo LE_EMAIL=you@example.com bash deploy/host-bootstrap.sh
```

What it does:

1. Installs Docker Engine + Compose plugin from Docker's official apt repo.
2. Adds your SSH user to the `docker` group (so you can run `docker` without sudo — log out / back in once for it to take effect).
3. Enables UFW with ports 22, 80, 443 open.
4. Creates the shared `edge` Docker network that Traefik watches for routing.
5. Installs Traefik at `/srv/traefik/` and starts it.

When the script finishes you should see Traefik listening:

```bash
docker ps
# CONTAINER ID   IMAGE          ...   PORTS                                       NAMES
# abc123...      traefik:v3.1   ...   0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp   traefik
```

## Step 6 — Configure the bridge

Still on the VM, in `/srv/impulse-bridge/`:

```bash
cp deploy/.env.production.example .env
cp deploy/docker-compose.yml ./docker-compose.yml
```

Edit `.env`:

```bash
nano .env
```

Required values:

| Variable | Example | Notes |
|---|---|---|
| `BRIDGE_DOMAIN` | `impulse-bridge.octo-code.de` | Public hostname Traefik routes to. |
| `BRIDGE_BASIC_AUTH` | (see below) | htpasswd-format hash, with `$` doubled. |
| `EUROPEANA_API_KEY` | your real key | Free at https://pro.europeana.eu/get-api |
| `SMITHSONIAN_API_KEY` | your real key | Free at https://api.data.gov/signup/ |

### Generating BRIDGE_BASIC_AUTH

Compose treats `$` as a variable marker. To embed an htpasswd hash, **every `$` must be doubled**. This one-liner generates the right format:

```bash
docker run --rm httpd:2.4 htpasswd -nbB admin "YOUR-PASSWORD-HERE" | sed 's/\$/\$\$/g'
```

The output looks like:

```
admin:$$2y$$05$$Vc7M3o2...
```

Paste that whole line as the value of `BRIDGE_BASIC_AUTH=` in `.env`. (The Bridge UI / Swagger / OpenAPI are then gated behind `admin` + that password.)

## Step 7 — Start the bridge

```bash
cd /srv/impulse-bridge
docker compose up -d --build
```

The first build downloads `python:3.12-slim` and installs deps — takes ~1–2 minutes. Subsequent rebuilds are seconds.

Watch logs:

```bash
docker compose logs -f bridge
```

When the bridge prints `Application startup complete.` and `Registered 5 source(s)`, it's ready. Traefik automatically:

1. Discovers the new container (it has `traefik.enable=true`).
2. Requests a Let's Encrypt cert for `impulse-bridge.octo-code.de` via HTTP-01 challenge (takes ~30 seconds on first request).
3. Routes traffic according to the labels.

## Step 8 — Verify

From your local machine:

```bash
curl https://impulse-bridge.octo-code.de/health
# {"code":0,"message":"OK","data":{"status":"ok","sources":[...]}}

curl -I https://impulse-bridge.octo-code.de/admin
# HTTP/2 401  ← good, basic auth is enforced

curl -u admin:<your-password> -I https://impulse-bridge.octo-code.de/admin
# HTTP/2 200  ← admin is accessible with credentials
```

In a browser:

- https://impulse-bridge.octo-code.de/ — public browser UI
- https://impulse-bridge.octo-code.de/help — documentation (public)
- https://impulse-bridge.octo-code.de/admin — admin UI (browser prompts for credentials)

---

## Day-2 operations

### View logs

```bash
# Bridge stdout/stderr (live)
docker compose -f /srv/impulse-bridge/docker-compose.yml logs -f bridge

# Traefik access log + cert provisioning events
docker compose -f /srv/traefik/docker-compose.yml logs -f traefik

# All container logs at once via journald
sudo journalctl -u docker -f
```

### Restart the bridge

```bash
cd /srv/impulse-bridge
docker compose restart bridge      # without rebuilding
docker compose up -d --build       # rebuild (after code change)
```

### Update to a new code version

```bash
cd /srv/impulse-bridge

# Git-tracked:
git pull --ff-only
docker compose up -d --build

# rsync workflow: rsync new code from your laptop, then:
docker compose up -d --build
```

The bridge restarts in seconds and serves the new code. Mounted directories (`configs/`, `data/`) and the `.env` are untouched.

### Change the admin password

Generate a new hash:

```bash
docker run --rm httpd:2.4 htpasswd -nbB admin "NEW-PASSWORD" | sed 's/\$/\$\$/g'
```

Paste it as `BRIDGE_BASIC_AUTH=...` in `/srv/impulse-bridge/.env`, then:

```bash
cd /srv/impulse-bridge
docker compose up -d            # picks up new env without rebuilding
```

Traefik reloads the middleware automatically.

### Rotate an API key

Edit `.env`, then:

```bash
docker compose up -d
```

Compose stops the container, applies new env, starts it again.

### Cert renewal

Traefik checks daily and renews any cert within 30 days of expiry. No action needed. Sanity-check after a few weeks:

```bash
docker compose -f /srv/traefik/docker-compose.yml logs traefik | grep -i acme
```

### Free up space

Old images accumulate after rebuilds. Periodically:

```bash
docker image prune -f
docker container prune -f
```

---

## Adding a second project

This is the payoff of the Docker + Traefik setup. To host another web app at, say, `myapp.octo-code.de`:

1. **DNS** — add an A record for `myapp` pointing to the VM IP.
2. **Folder** — create `/srv/myapp/`.
3. **docker-compose.yml** — minimal example:

```yaml
services:
  app:
    image: my-app-image:latest
    # or build: . if you have a Dockerfile

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

4. **Start it**: `cd /srv/myapp && docker compose up -d`.

Traefik discovers it within seconds, requests a cert, and starts routing. No Traefik restart, no nginx file editing, no SSL config — all of that is automatic.

The same pattern works for static sites (use `nginx:alpine` image), Node.js apps (`node:20-alpine`), Go binaries (your own image), databases (`postgres:16` — usually no Traefik labels, expose only on the internal network), and so on.

---

## Hardening (recommended after the demo phase)

- **Disable SSH password auth.** Edit `/etc/ssh/sshd_config`: `PasswordAuthentication no`, `PermitRootLogin no`, then `sudo systemctl restart sshd`.
- **fail2ban** to block SSH brute-force: `sudo apt-get install -y fail2ban && sudo systemctl enable --now fail2ban`.
- **Unattended security upgrades**: `sudo apt-get install -y unattended-upgrades && sudo dpkg-reconfigure --priority=low unattended-upgrades`.
- **Cloudflare in front** (optional): switch your DNS to Cloudflare proxied (orange cloud), configure SSL mode to **Full (strict)**. Hides the VM IP and adds DDoS protection. The Docker setup itself doesn't change.

---

## Troubleshooting

### Bridge starts but Traefik gives 404 or "no available server"

Most likely the container isn't joined to the `edge` network or `traefik.enable=true` is missing.

```bash
# Confirm the bridge is on edge:
docker network inspect edge | grep impulse-bridge

# Confirm Traefik can see it:
docker compose -f /srv/traefik/docker-compose.yml logs --tail 50 traefik | grep -i "bridge\|provider"
```

### Let's Encrypt rate-limited / cert provisioning fails

Common causes:

- DNS hasn't propagated → `dig +short impulse-bridge.octo-code.de` should show the VM IP.
- Port 80 isn't reachable from the internet → check OCI Security List (Step 2) and `sudo ufw status`.
- You hit Let's Encrypt's staging-vs-production confusion → not relevant unless you customized Traefik.

```bash
docker compose -f /srv/traefik/docker-compose.yml logs traefik | grep -i acme
```

### "permission denied" trying to bind /var/run/docker.sock

You're not in the `docker` group yet. Log out and back in to the VM (`exit` then SSH again) — group changes need a new session.

### Container restart loop

```bash
docker compose -f /srv/impulse-bridge/docker-compose.yml logs --tail 100 bridge
```

The bridge is fail-fast on YAML config errors. If a `configs/sources/*.yaml` is invalid, the load logs will tell you which file and which Pydantic field. Fix the YAML, `docker compose restart bridge`.

### Forgot the admin password

```bash
docker run --rm httpd:2.4 htpasswd -nbB admin "new-password" | sed 's/\$/\$\$/g'
# Paste output as BRIDGE_BASIC_AUTH in /srv/impulse-bridge/.env
cd /srv/impulse-bridge && docker compose up -d
```

### Want to see what Traefik thinks is configured

The dashboard exposes everything. Edit `/srv/traefik/docker-compose.yml`, uncomment the `labels:` block, set `DASHBOARD_DOMAIN` and `DASHBOARD_BASIC_AUTH` in `/srv/traefik/.env`, then:

```bash
cd /srv/traefik && docker compose up -d
```

The dashboard appears at `https://<DASHBOARD_DOMAIN>/` with basic auth.

---

## Quick reference

| What | Command |
|---|---|
| Bridge logs (live) | `docker compose -f /srv/impulse-bridge/docker-compose.yml logs -f bridge` |
| Bridge restart | `cd /srv/impulse-bridge && docker compose restart bridge` |
| Bridge rebuild + restart | `cd /srv/impulse-bridge && docker compose up -d --build` |
| Traefik logs | `docker compose -f /srv/traefik/docker-compose.yml logs -f traefik` |
| Traefik restart | `cd /srv/traefik && docker compose restart traefik` |
| List containers | `docker ps` |
| Inspect edge network | `docker network inspect edge` |
| Cert storage | `/srv/traefik/letsencrypt/acme.json` |
| Bridge env file | `/srv/impulse-bridge/.env` |
| Bridge configs (writable) | `/srv/impulse-bridge/configs/sources/` |
| Health (public) | `curl https://impulse-bridge.octo-code.de/health` |

## What this setup deliberately does not cover

- **High availability** — single VM, single Traefik. For HA, point a load balancer at multiple VMs sharing a database; out of scope here.
- **Centralized logging / metrics** — `docker compose logs` is enough for POC. Add Loki / Prometheus when traffic warrants.
- **CI/CD** — manual `git pull && docker compose up -d --build` is fine for a small team. GitHub Actions can SSH in and run the same command if you want.
- **Backups** — the bridge has no DB. Snapshot `/srv/impulse-bridge/configs/` and `/srv/impulse-bridge/.env` (everything else is in Git or downloadable from upstream archives).

---

_Last verified on Ubuntu 24.04 LTS Aarch64, Oracle Cloud Free Tier, Docker 27.x, Traefik v3.1, 2026._
