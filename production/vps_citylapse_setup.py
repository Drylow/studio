"""Écrit production/vps_citylapse_setup.sh : installe sur le VPS le serveur de rendu des timelapses 3D Keystone
(citylapse/tools/vps_worker.mjs). Pas de carte graphique : WebGL logiciel, une ville par morceaux sur plusieurs cœurs.

  python production/vps_citylapse_setup.py   → régénère le .sh (à committer après chaque changement du serveur)

Sur le VPS (root), une ligne :
  curl -fsSL https://raw.githubusercontent.com/drylow/studio/main/production/vps_citylapse_setup.sh | bash
Docker (image Playwright 1.48.2 : Chromium + Node) derrière HTTPS sur city.<ip>.sslip.io, avec le même proxy que
le serveur d'actu s'il existe (Traefik de Coolify ou drylow-caddy), sinon un Caddy à lui. Affiche CITY_WORKER_URL et
CITY_WORKER_TOKEN (pour le .env du cloud, jamais dans git). Relancer le script met le serveur à jour."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "..", "citylapse", "tools", "vps_worker.mjs")
OUT = os.path.join(HERE, "vps_citylapse_setup.sh")

TEMPLATE = r"""#!/bin/bash
# Serveur de rendu des timelapses 3D Keystone sur ce VPS. À lancer en root.
# Fichier généré par production/vps_citylapse_setup.py : ne pas modifier à la main.
set -e
DIR=/opt/drylow-city
mkdir -p "$DIR"
cat > "$DIR/worker.mjs" <<'DRYLOW_CITY_EOF'
__WORKER__
DRYLOW_CITY_EOF
[ -s "$DIR/token" ] || (openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$DIR/token"
TOKEN=$(cat "$DIR/token")
IP=$(curl -fs4 https://api.ipify.org || curl -fs4 https://ifconfig.me)
HOST=${DOMAIN:-city.$(echo "$IP" | tr . -).sslip.io}
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
IMAGE=mcr.microsoft.com/playwright:v1.48.2-jammy
docker pull -q $IMAGE >/dev/null
docker rm -f drylow-city >/dev/null 2>&1 || true
RUN="(command -v ffmpeg >/dev/null || (apt-get update -qq && apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null)) && mkdir -p /opt/tl && cd /opt/tl && ([ -d node_modules/playwright-core ] || npm i -s --no-audit --no-fund playwright-core@1.48.2 >/dev/null) && exec node /w.mjs"
BASE=(-d --name drylow-city --restart unless-stopped -e WORKER_TOKEN="$TOKEN" -e DATA_DIR=/data --shm-size=2g
      -v "$DIR/worker.mjs:/w.mjs:ro" -v drylow-city:/data -v drylow-city-tl:/opt/tl)
if docker ps --format '{{.Names}}' | grep -qx coolify-proxy; then
  docker run "${BASE[@]}" --network coolify \
    -l traefik.enable=true \
    -l "traefik.http.routers.drylow-city.rule=Host(\`$HOST\`)" \
    -l traefik.http.routers.drylow-city.entrypoints=https \
    -l traefik.http.routers.drylow-city.tls=true \
    -l traefik.http.routers.drylow-city.tls.certresolver=letsencrypt \
    -l traefik.http.services.drylow-city.loadbalancer.server.port=8000 \
    $IMAGE sh -c "$RUN"
elif docker ps --format '{{.Names}}' | grep -qx drylow-caddy; then
  # le Caddy déjà là (serveur de rendu / d'actu) : on lui ajoute cette adresse, certificats gardés
  docker run "${BASE[@]}" --network drylow $IMAGE sh -c "$RUN"
  CF=$(docker inspect drylow-caddy --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}')
  if [ -z "$CF" ]; then
    # Caddy lancé en « reverse-proxy --from A --to B » : on écrit un Caddyfile avec les deux
    CF="$DIR/Caddyfile"
    ARGS=$(docker inspect drylow-caddy --format '{{join .Args " "}}')
    FROM=$(echo "$ARGS" | sed -n 's/.*--from \([^ ]*\).*/\1/p'); TO=$(echo "$ARGS" | sed -n 's/.*--to \([^ ]*\).*/\1/p')
    [ -n "$FROM" ] && printf '%s {\n\treverse_proxy %s\n}\n' "$FROM" "$TO" > "$CF" || : > "$CF"
  fi
  grep -q "drylow-city:8000" "$CF" || printf '%s {\n\treverse_proxy drylow-city:8000\n}\n' "$HOST" >> "$CF"
  docker rm -f drylow-caddy >/dev/null
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data -v "$CF:/etc/caddy/Caddyfile:ro" caddy:2
else
  if ss -ltn 2>/dev/null | grep -qE ':(80|443)\s' || docker ps --format '{{.Ports}}' | grep -qE ':(80|443)->'; then
    echo "!! Les ports 80/443 sont déjà pris : envoie ceci à Claude :"
    ss -ltnp | grep -E ':(80|443)\s'; docker ps --format '{{.Names}} {{.Ports}}' | grep -E ':(80|443)->'
    exit 1
  fi
  command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q active && ufw allow 80/tcp && ufw allow 443/tcp || true
  docker network create drylow >/dev/null 2>&1 || true
  docker run "${BASE[@]}" --network drylow $IMAGE sh -c "$RUN"
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data caddy:2 caddy reverse-proxy --from "$HOST" --to drylow-city:8000
fi
echo "Démarrage (1 à 3 min)…"
OK=""
for i in $(seq 1 40); do
  curl -fs -H "X-Worker-Token: $TOKEN" "https://$HOST/status" >/dev/null 2>&1 && OK=1 && break
  sleep 6
done
echo
echo "=== À envoyer à Claude ==="
echo "CITY_WORKER_URL=https://$HOST"
echo "CITY_WORKER_TOKEN=$TOKEN"
echo "Serveur : ${OK:+OK}${OK:-pas de réponse (envoie aussi : docker logs drylow-city | tail -30)}"
echo "Cœurs : $(nproc) — disque libre : $(df -h / | awk 'NR==2{print $4}')"
"""


def main():
    worker = open(WORKER, encoding="utf-8").read()
    if "DRYLOW_CITY_EOF" in worker:
        raise SystemExit("le serveur contient le marqueur de fin du heredoc")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(TEMPLATE.replace("__WORKER__", worker.rstrip("\n")))
    os.chmod(OUT, 0o755)
    print(OUT)


if __name__ == "__main__":
    main()
