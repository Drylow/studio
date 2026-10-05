"""Écrit le script d'installation de la machine de rendu sur le VPS de l'utilisateur (format Histoire).

  python production/vps_setup.py [sortie.sh]      (défaut : $STUDIO_WORK/vps_setup.sh)

Le script (à lancer en root sur le VPS : bash vps_setup.sh) installe Docker si besoin, lance le serveur de rendu
(production/runpod_worker.js, dans l'image Playwright : Node + Chromium) en HTTPS automatique sur <ip>.sslip.io (ou
DOMAIN=…) : derrière le Traefik de Coolify s'il tient déjà 80/443 (cas du VPS2 de l'utilisateur, labels comme ses
autres sites), sinon derrière un Caddy à lui ; protégé par un jeton, puis affiche URL et jeton à mettre dans
le .env : RENDER_WORKERS=<url> et RENDER_WORKER_TOKEN=<jeton> (jamais dans git). Relancer le script met le serveur
à jour (même jeton, même adresse)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "runpod_worker.js")
IMAGE = "mcr.microsoft.com/playwright:v1.49.1-noble"

TEMPLATE = r"""#!/bin/bash
# Machine de rendu Edgerunners Studio (vidéos History) sur ce VPS : serveur de rendu (Docker, image Playwright)
# derrière Caddy en HTTPS automatique, protégé par un jeton. À lancer en root : bash vps_setup.sh
set -e
DIR=/opt/drylow-render
mkdir -p "$DIR"
cat > "$DIR/worker.js" <<'DRYLOW_WORKER_EOF'
__WORKER__
DRYLOW_WORKER_EOF
[ -s "$DIR/token" ] || (openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$DIR/token"
TOKEN=$(cat "$DIR/token")
IP=$(curl -fs4 https://api.ipify.org || curl -fs4 https://ifconfig.me)
HOST=${DOMAIN:-$(echo "$IP" | tr . -).sslip.io}
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
docker rm -f drylow-worker drylow-caddy >/dev/null 2>&1 || true
docker pull __IMAGE__
if docker ps --format '{{.Names}}' | grep -qx coolify-proxy; then
  # Coolify (Traefik) tient déjà 80/443 : le serveur passe par ce Traefik (labels), comme les autres sites du VPS
  docker run -d --name drylow-worker --restart unless-stopped --network coolify --shm-size=4g \
    -e WORKER_TOKEN="$TOKEN" -e WORK_DIR=/work -v "$DIR/worker.js:/w.js:ro" -v drylow-work:/work \
    -l traefik.enable=true \
    -l "traefik.http.routers.drylow-render.rule=Host(\`$HOST\`)" \
    -l traefik.http.routers.drylow-render.entrypoints=https \
    -l traefik.http.routers.drylow-render.tls=true \
    -l traefik.http.routers.drylow-render.tls.certresolver=letsencrypt \
    -l traefik.http.services.drylow-render.loadbalancer.server.port=8000 \
    __IMAGE__ node /w.js
else
  if ss -ltn 2>/dev/null | grep -qE ':(80|443)\s' || docker ps --format '{{.Ports}}' | grep -qE ':(80|443)->'; then
    echo "!! Les ports 80/443 sont déjà pris (nginx, apache, un autre proxy…) : envoie ceci à Claude :"
    ss -ltnp | grep -E ':(80|443)\s'; docker ps --format '{{.Names}} {{.Ports}}' | grep -E ':(80|443)->'
    exit 1
  fi
  command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q active && ufw allow 80/tcp && ufw allow 443/tcp || true
  docker network create drylow >/dev/null 2>&1 || true
  docker run -d --name drylow-worker --restart unless-stopped --network drylow --shm-size=4g \
    -e WORKER_TOKEN="$TOKEN" -e WORK_DIR=/work -v "$DIR/worker.js:/w.js:ro" -v drylow-work:/work \
    __IMAGE__ node /w.js
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data caddy:2 caddy reverse-proxy --from "$HOST" --to drylow-worker:8000
fi
echo "Attente du certificat HTTPS…"
for i in $(seq 1 30); do
  curl -fs -H "X-Worker-Token: $TOKEN" "https://$HOST/status" >/dev/null 2>&1 && break
  sleep 4
done
echo
echo "=== À envoyer à Claude ==="
echo "RENDER_WORKERS=https://$HOST"
echo "RENDER_WORKER_TOKEN=$TOKEN"
curl -fs -H "X-Worker-Token: $TOKEN" "https://$HOST/status" >/dev/null && echo "(test OK)" || echo "(test KO : envoie aussi la sortie de « docker logs drylow-caddy »)"
"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.environ.get("STUDIO_WORK") or os.path.join(os.path.dirname(HERE), "work"), "vps_setup.sh")
    worker = open(WORKER, encoding="utf-8").read()
    if "DRYLOW_WORKER_EOF" in worker:
        raise SystemExit("le serveur contient le marqueur de fin du heredoc")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("__WORKER__", worker.rstrip("\n")).replace("__IMAGE__", IMAGE))
    os.chmod(out, 0o755)
    print(out)


if __name__ == "__main__":
    main()
