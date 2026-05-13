#!/usr/bin/env bash
# Impulse Bridge — host bootstrap.
#
# Runs ONCE on a fresh Ubuntu 22.04 / 24.04 VM (Oracle Cloud free-tier or any
# other Ubuntu host). After this script completes, the server is ready to host
# any number of containerised projects — the Impulse Bridge is just the first.
#
# What it does:
#   1. Installs Docker Engine + Compose plugin from Docker's official apt repo.
#   2. Configures UFW to allow SSH + 80 + 443.
#   3. Creates the shared "edge" Docker network for Traefik service discovery.
#   4. Installs and starts Traefik at /srv/traefik.
#
# Usage:
#     sudo LE_EMAIL=you@example.com bash deploy/host-bootstrap.sh
#
# Idempotent — safe to re-run.

set -euo pipefail

LE_EMAIL="${LE_EMAIL:-}"
TRAEFIK_DIR="/srv/traefik"

step() { echo; echo "==> $*"; }

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: run with sudo" >&2
    exit 1
fi

if [ -z "$LE_EMAIL" ]; then
    echo "ERROR: set LE_EMAIL=... (Let's Encrypt registration address)" >&2
    exit 1
fi

# ---- system prep -------------------------------------------------------
step "Updating apt and installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release ufw git rsync

# ---- Docker Engine (official repository) -------------------------------
if ! command -v docker >/dev/null 2>&1; then
    step "Installing Docker Engine"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
else
    step "Docker already installed — skipping"
fi

# ---- Let the SSH user run docker without sudo --------------------------
SUDO_USER_NAME="${SUDO_USER:-}"
if [ -n "$SUDO_USER_NAME" ] && [ "$SUDO_USER_NAME" != "root" ]; then
    step "Adding '$SUDO_USER_NAME' to the docker group"
    usermod -aG docker "$SUDO_USER_NAME"
    echo "    (log out and back in to take effect)"
fi

# ---- Firewall (UFW) ----------------------------------------------------
step "Configuring UFW: SSH + 80 + 443"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp  >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable

# ---- Shared Docker network --------------------------------------------
step "Creating shared 'edge' Docker network"
docker network inspect edge >/dev/null 2>&1 || docker network create edge

# ---- Traefik directory & config ---------------------------------------
step "Installing Traefik at $TRAEFIK_DIR"
mkdir -p "$TRAEFIK_DIR/letsencrypt"
chmod 700 "$TRAEFIK_DIR/letsencrypt"

# Copy the compose file next to the bootstrap script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -m 644 "$SCRIPT_DIR/traefik/docker-compose.yml" "$TRAEFIK_DIR/docker-compose.yml"

# Traefik env file.
if [ ! -f "$TRAEFIK_DIR/.env" ]; then
    cat > "$TRAEFIK_DIR/.env" <<EOF
LE_EMAIL=$LE_EMAIL
EOF
    chmod 600 "$TRAEFIK_DIR/.env"
fi

# Touch acme.json with the exact mode Traefik requires.
touch "$TRAEFIK_DIR/letsencrypt/acme.json"
chmod 600 "$TRAEFIK_DIR/letsencrypt/acme.json"

# ---- Start Traefik -----------------------------------------------------
step "Starting Traefik"
(cd "$TRAEFIK_DIR" && docker compose up -d)

# ---- Summary -----------------------------------------------------------
echo
echo "==============================================================="
echo " Host bootstrap complete."
echo
echo " Traefik is running at $TRAEFIK_DIR — discovers any container"
echo " on the 'edge' Docker network with traefik.enable=true labels."
echo
echo " Next: deploy the Impulse Bridge as a project:"
echo "   1.  sudo mkdir -p /srv/impulse-bridge"
echo "   2.  rsync / git the bridge source into /srv/impulse-bridge"
echo "   3.  cd /srv/impulse-bridge && cp deploy/.env.production.example .env"
echo "   4.  edit .env (BRIDGE_DOMAIN, API keys, BRIDGE_BASIC_AUTH)"
echo "   5.  cp deploy/docker-compose.yml ./docker-compose.yml"
echo "   6.  docker compose up -d --build"
echo
echo " To add another project later: same recipe, different folder under /srv."
echo "==============================================================="
