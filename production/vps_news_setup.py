"""Écrit production/vps_news_setup.sh : installe sur le VPS de l'utilisateur le serveur de montage des vidéos d'actu
(production/news_worker.py). YouTube bloque le cloud ; depuis le VPS, le cloud envoie la vidéo préparée et récupère
le lien Gofile + les planches, sans rien sur le PC de l'utilisateur.

  python production/vps_news_setup.py      → régénère production/vps_news_setup.sh (à committer après chaque
                                              changement de news_worker.py)

Sur le VPS (root), une ligne :
  curl -fsSL https://raw.githubusercontent.com/drylow/studio/main/production/vps_news_setup.sh | bash
Docker (image python:3.12-slim) derrière HTTPS automatique sur news.<ip>.sslip.io (ou DOMAIN=…) : le Traefik de
Coolify s'il tient 80/443, sinon le Caddy du serveur de rendu (relancé avec les deux adresses), sinon un Caddy à
lui. Affiche NEWS_WORKER_URL / NEWS_WORKER_TOKEN (pour le .env du cloud, jamais dans git) et le test YouTube.
Relancer le script met le serveur à jour (même jeton, même adresse)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "news_worker.py")
OUT = os.path.join(HERE, "vps_news_setup.sh")

TEMPLATE = r"""#!/bin/bash
# Serveur de montage des vidéos d'actu Drylow (Cage Dispatch…) sur ce VPS. À lancer en root.
# Fichier généré par production/vps_news_setup.py : ne pas modifier à la main.
set -e
DIR=/opt/drylow-news
mkdir -p "$DIR"
cat > "$DIR/worker.py" <<'DRYLOW_NEWS_EOF'
__WORKER__
DRYLOW_NEWS_EOF
[ -s "$DIR/token" ] || (openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$DIR/token"
TOKEN=$(cat "$DIR/token")
IP=$(curl -fs4 https://api.ipify.org || curl -fs4 https://ifconfig.me)
HOST=${DOMAIN:-news.$(echo "$IP" | tr . -).sslip.io}
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
IMAGE=python:3.12-slim
docker pull -q $IMAGE >/dev/null
docker rm -f drylow-news >/dev/null 2>&1 || true
RUN="apt-get update -qq && apt-get install -y -qq --no-install-recommends curl ca-certificates fontconfig >/dev/null && exec python -u /w.py"
BASE=(-d --name drylow-news --restart unless-stopped -e WORKER_TOKEN="$TOKEN" -e DATA_DIR=/data
      -v "$DIR/worker.py:/w.py:ro" -v drylow-news:/data)
if docker ps --format '{{.Names}}' | grep -qx coolify-proxy; then
  # Coolify (Traefik) tient 80/443 : même chemin que les autres sites du VPS
  docker run "${BASE[@]}" --network coolify \
    -l traefik.enable=true \
    -l "traefik.http.routers.drylow-news.rule=Host(\`$HOST\`)" \
    -l traefik.http.routers.drylow-news.entrypoints=https \
    -l traefik.http.routers.drylow-news.tls=true \
    -l traefik.http.routers.drylow-news.tls.certresolver=letsencrypt \
    -l traefik.http.services.drylow-news.loadbalancer.server.port=8000 \
    $IMAGE sh -c "$RUN"
elif docker ps --format '{{.Names}}' | grep -qx drylow-caddy; then
  # le Caddy du serveur de rendu tient 80/443 : relancé avec les deux adresses (certificats gardés)
  RHOST=$(docker inspect drylow-caddy --format '{{join .Args " "}}' | sed -n 's/.*--from \([^ ]*\).*/\1/p')
  [ -z "$RHOST" ] && [ -s "$DIR/Caddyfile" ] && RHOST=$(grep -B1 'drylow-worker' "$DIR/Caddyfile" | head -1 | cut -d' ' -f1)
  docker run "${BASE[@]}" --network drylow $IMAGE sh -c "$RUN"
  { [ -n "$RHOST" ] && printf '%s {\n\treverse_proxy drylow-worker:8000\n}\n' "$RHOST"
    printf '%s {\n\treverse_proxy drylow-news:8000\n}\n' "$HOST"; } > "$DIR/Caddyfile"
  docker rm -f drylow-caddy >/dev/null
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data -v "$DIR/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2
else
  if ss -ltn 2>/dev/null | grep -qE ':(80|443)\s' || docker ps --format '{{.Ports}}' | grep -qE ':(80|443)->'; then
    echo "!! Les ports 80/443 sont déjà pris (nginx, apache, un autre proxy…) : envoie ceci à Claude :"
    ss -ltnp | grep -E ':(80|443)\s'; docker ps --format '{{.Names}} {{.Ports}}' | grep -E ':(80|443)->'
    exit 1
  fi
  command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q active && ufw allow 80/tcp && ufw allow 443/tcp || true
  docker network create drylow >/dev/null 2>&1 || true
  docker run "${BASE[@]}" --network drylow $IMAGE sh -c "$RUN"
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data caddy:2 caddy reverse-proxy --from "$HOST" --to drylow-news:8000
fi
echo "Installation et test YouTube (2 à 5 min)…"
YT=""
for i in $(seq 1 60); do
  S=$(curl -fs -H "X-Worker-Token: $TOKEN" "https://$HOST/status" 2>/dev/null || true)
  echo "$S" | grep -q '"youtube": true' && YT="OK" && break
  echo "$S" | grep -q '"youtube": false' && YT="BLOQUE" && break
  sleep 6
done
echo
echo "=== À envoyer à Claude ==="
echo "NEWS_WORKER_URL=https://$HOST"
echo "NEWS_WORKER_TOKEN=$TOKEN"
echo "YouTube depuis ce VPS : ${YT:-pas de réponse (envoie aussi : docker logs drylow-news | tail -30)}"
"""


def main():
    worker = open(WORKER, encoding="utf-8").read()
    if "DRYLOW_NEWS_EOF" in worker:
        raise SystemExit("le serveur contient le marqueur de fin du heredoc")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(TEMPLATE.replace("__WORKER__", worker.rstrip("\n")))
    os.chmod(OUT, 0o755)
    print(OUT)


if __name__ == "__main__":
    main()
