#!/usr/bin/env bash
# One-paste setup for a fresh AWS Lightsail / EC2 server (Ubuntu 22.04+ or Amazon Linux 2023).
# Needs a server with >= 2 GB RAM (or it will add swap) and ports 80 + 443 open in the firewall.
#
#   ADMIN_EMAIL=you@company.com bash aws-setup.sh
# Private repo? also set GITHUB_TOKEN=<a fine-grained token with read access to the repo>.
# Optional: DOMAIN=gcc.yourdomain.com (DNS A record must already point to this server); default is <ip>.sslip.io
set -euo pipefail
: "${ADMIN_EMAIL:?set ADMIN_EMAIL=you@company.com (this signup becomes the admin)}"
REPO="${REPO:-github.com/hemanthpeddintii-svg/listmonk.git}"
BRANCH="${BRANCH:-claude/gcc-companies-portal-arqoke}"
DIR="${DIR:-$HOME/gcc-intel}"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== 1/5 installing Docker and git"
if command -v apt-get >/dev/null; then
  $SUDO apt-get update -y && $SUDO apt-get install -y docker.io docker-compose-v2 git curl openssl
elif command -v dnf >/dev/null; then
  $SUDO dnf install -y docker git openssl
  $SUDO mkdir -p /usr/local/lib/docker/cli-plugins
  $SUDO curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
  $SUDO chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
else echo "unsupported OS"; exit 1; fi
$SUDO systemctl enable --now docker

echo "== 2/5 swap (Next.js build needs memory)"
if [ "$(free -m | awk '/^Mem:/{print $2}')" -lt 3000 ] && [ ! -f /swapfile ]; then
  $SUDO fallocate -l 2G /swapfile && $SUDO chmod 600 /swapfile && $SUDO mkswap /swapfile && $SUDO swapon /swapfile
fi

echo "== 3/5 fetching the code"
URL="https://${GITHUB_TOKEN:+x-access-token:${GITHUB_TOKEN}@}${REPO}"
if [ -d "$DIR/.git" ]; then git -C "$DIR" fetch origin "$BRANCH" && git -C "$DIR" checkout "$BRANCH" && git -C "$DIR" pull origin "$BRANCH"
else git clone --branch "$BRANCH" --depth 1 "$URL" "$DIR"; fi
cd "$DIR/gcc-portal"

echo "== 4/5 configuring"
IP="$(curl -fsS -m 5 https://checkip.amazonaws.com || curl -fsS -m 5 https://ifconfig.me)"
DOMAIN="${DOMAIN:-${IP}.sslip.io}"
if [ ! -f .env ]; then
  cat > .env <<ENV
POSTGRES_USER=gcc
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=gcc
JWT_SECRET=$(openssl rand -hex 32)
BILLING_WEBHOOK_SECRET=$(openssl rand -hex 24)
BILLING_MODE=test
ADMIN_EMAILS=${ADMIN_EMAIL}
SITE_URL=https://${DOMAIN}
DOMAIN=${DOMAIN}
SEED_DATA=1
WEB_BIND=127.0.0.1
WEB_PORT=3000
ENV
  chmod 600 .env
fi

echo "== 5/5 building and starting (first build takes 5-10 minutes)"
$SUDO docker compose --profile caddy up -d --build
echo
echo "Done. Open:  https://${DOMAIN}"
echo "Sign up with ${ADMIN_EMAIL} to become the admin. If the page does not load, open ports 80 and 443 in the Lightsail/EC2 firewall."
echo "Logs:  cd $DIR/gcc-portal && sudo docker compose logs -f web"
