#!/bin/bash
# Agent du studio (vidéos Oddly Specific Lives : voix, images, montage) sur ce VPS. À lancer en root, une fois :
#   curl -fsSL https://raw.githubusercontent.com/drylow/studio/main/production/vps_studio_setup.sh | bash
# Docker (python:3.12), HTTPS automatique : Traefik de Coolify s'il est là, sinon un Caddy si 80/443 sont libres,
# sinon un tunnel Cloudflare (aucun port à ouvrir). Affiche STUDIO_AGENT_URL / STUDIO_AGENT_TOKEN à envoyer à Claude.
# Relancer le script met l'agent à jour (même jeton). Aucun secret dans ce fichier : le jeton est créé ici.
set -e
DIR=/opt/drylow-studio
mkdir -p "$DIR"
curl -fsSL https://raw.githubusercontent.com/drylow/studio/main/production/studio_agent.py -o "$DIR/agent.py"
[ -s "$DIR/token" ] || (openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$DIR/token"
chmod 600 "$DIR/token"
TOKEN=$(cat "$DIR/token")
IP=$(curl -fs4 https://api.ipify.org || curl -fs4 https://ifconfig.me)
HOST=${DOMAIN:-studio.$(echo "$IP" | tr . -).sslip.io}
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
IMAGE=python:3.12-bookworm
docker pull -q $IMAGE >/dev/null
docker rm -f drylow-studio drylow-studio-caddy drylow-studio-tunnel >/dev/null 2>&1 || true
docker network create drylow-studio >/dev/null 2>&1 || true
RUN=(-d --name drylow-studio --restart unless-stopped --shm-size=2g -e WORKER_TOKEN="$TOKEN"
     -v "$DIR/agent.py:/agent.py:ro" -v drylow-studio-data:/data)
MODE=""
if docker ps --format '{{.Names}}' | grep -qx coolify-proxy; then
  MODE=coolify
  docker run "${RUN[@]}" --network coolify \
    -l traefik.enable=true \
    -l "traefik.http.routers.drylow-studio.rule=Host(\`$HOST\`)" \
    -l traefik.http.routers.drylow-studio.entrypoints=https \
    -l traefik.http.routers.drylow-studio.tls=true \
    -l traefik.http.routers.drylow-studio.tls.certresolver=letsencrypt \
    -l traefik.http.services.drylow-studio.loadbalancer.server.port=8000 \
    $IMAGE python /agent.py
  URL="https://$HOST"
elif ! ss -ltn 2>/dev/null | grep -qE ':(80|443)\s' && ! docker ps --format '{{.Ports}}' | grep -qE ':(80|443)->'; then
  MODE=caddy
  command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q active && ufw allow 80/tcp && ufw allow 443/tcp || true
  docker run "${RUN[@]}" --network drylow-studio $IMAGE python /agent.py
  docker run -d --name drylow-studio-caddy --restart unless-stopped --network drylow-studio -p 80:80 -p 443:443 \
    -v drylow-studio-caddy:/data caddy:2 caddy reverse-proxy --from "$HOST" --to drylow-studio:8000
  URL="https://$HOST"
else
  MODE=tunnel  # 80/443 déjà pris par un autre site : tunnel sortant, rien à ouvrir
  docker run "${RUN[@]}" --network drylow-studio $IMAGE python /agent.py
  docker run -d --name drylow-studio-tunnel --restart unless-stopped --network drylow-studio \
    cloudflare/cloudflared:latest tunnel --no-autoupdate --url http://drylow-studio:8000
  URL=""
  for i in $(seq 1 30); do
    URL=$(docker logs drylow-studio-tunnel 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
    [ -n "$URL" ] && break
    sleep 2
  done
fi
echo "Démarrage de l'agent (clonage du studio + installation, 2-4 min)…"
OK=""
for i in $(seq 1 90); do
  curl -fs -H "X-Worker-Token: $TOKEN" "$URL/status" >/dev/null 2>&1 && { OK=1; break; }
  sleep 4
done
echo
echo "=== À envoyer à Claude ($MODE) ==="
echo "STUDIO_AGENT_URL=$URL"
echo "STUDIO_AGENT_TOKEN=$TOKEN"
[ -n "$OK" ] && echo "(test OK)" || { echo "(test KO : envoie aussi ceci)"; docker logs --tail 30 drylow-studio 2>&1; }
