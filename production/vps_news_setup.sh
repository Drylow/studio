#!/bin/bash
# Serveur de montage des vidéos d'actu Drylow (Cage Dispatch…) sur ce VPS. À lancer en root.
# Fichier généré par production/vps_news_setup.py : ne pas modifier à la main.
set -e
DIR=/opt/drylow-news
mkdir -p "$DIR"
cat > "$DIR/worker.py" <<'DRYLOW_NEWS_EOF'
"""Serveur de montage des vidéos d'actu sur le VPS de l'utilisateur (YouTube bloque le cloud, pas ce VPS).

Installé par production/vps_news_setup.sh (Docker, derrière HTTPS). Aucune dépendance hors stdlib pour le serveur ;
au démarrage il installe yt-dlp, ffmpeg (imageio-ffmpeg), Pillow et le moteur JavaScript deno dans DATA_DIR.
Chaque requête porte l'en-tête X-Worker-Token (= WORKER_TOKEN).

  GET  /status                 {busy, job, stage, error, youtube, proxy, cookies (oui/non), log: fin de build.log}
  POST /ytcheck                test de téléchargement YouTube depuis ce VPS → {ok, detail}
  PUT  /job?name=NOM[&upload=0] corps = .tgz avec code/ (le code du montage) et job/ (plan.json, narration/,
                               rangé dans jobs/NOM/NOM) :
                               lance le montage (téléchargement, montage, Gofile, puis clips et vidéo supprimés)
  GET  /file?name=NOM&path=P   résultat : result.json, build.log, check/sheet_XX.jpg
  DELETE /job?name=NOM         efface le dossier de la vidéo
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = os.environ.get("DATA_DIR", "/data")
TOKEN = os.environ.get("WORKER_TOKEN", "")
JOBS = os.path.join(DATA, "jobs")
DENO_DIR = os.path.join(DATA, "tools", "deno")
MODULES = ["yt-dlp[default]", "imageio-ffmpeg", "Pillow", "python-dotenv", "requests"]
TEST_VIDEO = "MeFQgiVHNoA"   # vidéo publique courte (son seul, quelques Mo) pour le test YouTube
# Proxy résidentiel (payé au Go) : seulement pour YouTube. Donné en YTDLP_PROXY ou en HTTPS_PROXY : dans les deux
# cas il est retiré de l'environnement général (pip, deno, envoi Gofile de 1 Go ne passent jamais par lui).
PROXY = (os.environ.get("YTDLP_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "").strip()
for _k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
if PROXY:
    os.environ["YTDLP_PROXY"] = PROXY
# cookies.txt d'un compte YouTube (jetable) si YouTube bloque même le proxy : docker cp cookies.txt drylow-news:/data/
COOKIES = os.environ.get("YTDLP_COOKIES") or os.path.join(DATA, "cookies.txt")


def cookie_args():
    if os.path.isfile(COOKIES):
        os.environ["YTDLP_COOKIES"] = COOKIES
        return ["--cookies", COOKIES]
    os.environ.pop("YTDLP_COOKIES", None)
    return []
st = {"busy": False, "job": None, "stage": "starting", "error": None, "youtube": None, "since": time.time(),
      "proxy": bool(PROXY)}
lock = threading.Lock()


def env():
    e = dict(os.environ, PYTHONIOENCODING="utf-8", STUDIO_WORK=os.path.join(DATA, "work"))
    e["PATH"] = DENO_DIR + os.pathsep + e.get("PATH", "")
    return e


def setup():
    """Modules Python à jour (yt-dlp change souvent) + deno pour les signatures YouTube."""
    st["stage"] = "setup"
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "--disable-pip-version-check",
                    "--root-user-action=ignore", *MODULES], check=False)
    exe = os.path.join(DENO_DIR, "deno")
    if not os.path.isfile(exe):
        os.makedirs(DENO_DIR, exist_ok=True)
        url = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip"
        with urllib.request.urlopen(url, timeout=300) as r:
            zipfile.ZipFile(io.BytesIO(r.read())).extract("deno", DENO_DIR)
        os.chmod(exe, 0o755)
    st["stage"] = "idle"


def ytcheck():
    tmp = os.path.join(DATA, "ytcheck")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "ba[abr<=80]/ba", "-o", "t.%(ext)s",
                        *(["--proxy", PROXY] if PROXY else []), *cookie_args(),
                        f"https://www.youtube.com/watch?v={TEST_VIDEO}"], cwd=tmp, env=env(), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    got = [f for f in os.listdir(tmp) if f.startswith("t.") and not f.endswith(".part")]
    ok = bool(got) and os.path.getsize(os.path.join(tmp, got[0])) > 100_000
    shutil.rmtree(tmp, ignore_errors=True)
    st["youtube"] = ok
    return {"ok": ok, "detail": "" if ok else (r.stderr or r.stdout)[-600:]}


def jobdir(name):
    """Dossier de la vidéo (au nom de la vidéo : c'est aussi le nom du fichier envoyé sur Gofile)."""
    return os.path.join(JOBS, name, name)


def build(name, upload=True):
    d = os.path.join(JOBS, name)
    log = open(os.path.join(jobdir(name), "worker.log"), "a", encoding="utf-8")
    try:
        setup()
        st.update(stage="build", error=None)
        cookie_args()  # YTDLP_COOKIES pour le montage si le fichier est là
        p = subprocess.run([sys.executable, os.path.join(d, "code", "production", "news.py"), "build",
                            jobdir(name)] + ([] if upload else ["--no-upload"]), cwd=os.path.join(d, "code"), env=env(), stdout=log,
                           stderr=subprocess.STDOUT)
        if p.returncode != 0:
            st["error"] = f"montage : code {p.returncode} (voir build.log / worker.log)"
    except Exception as e:  # noqa: BLE001
        st["error"] = str(e)[:500]
    finally:
        log.close()
        shutil.rmtree(os.path.join(DATA, "work"), ignore_errors=True)  # rien ne reste : clips, segments, vidéo
        st.update(busy=False, stage="done")


def tail(path, n=40):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, data=None, ctype="application/json"):
        body = data if data is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        if TOKEN and self.headers.get("X-Worker-Token") != TOKEN:
            self._send(401, {"error": "token"})
            return False
        return True

    def _q(self):
        u = urllib.parse.urlparse(self.path)
        return u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def _name(self, q):
        n = q.get("name", "")
        return n if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", n) and n not in ("code", "job") else None

    def log_message(self, *a):
        pass

    def do_GET(self):
        if not self._auth():
            return
        path, q = self._q()
        if path == "/status":
            job = st.get("job")
            out = dict(st, cookies=os.path.isfile(COOKIES),
                       log=tail(os.path.join(jobdir(job), "build.log")) if job else [])
            return self._send(200, out)
        if path == "/file":
            n, rel = self._name(q), q.get("path", "")
            if not n or not re.fullmatch(r"(result\.json|build\.log|worker\.log|check/sheet_\d{2}\.jpg)", rel):
                return self._send(400, {"error": "path"})
            f = os.path.join(jobdir(n), rel)
            if not os.path.isfile(f):
                return self._send(404, {"error": "absent"})
            with open(f, "rb") as fh:
                return self._send(200, data=fh.read(), ctype="application/octet-stream")
        return self._send(404, {"error": "route"})

    def do_POST(self):
        if not self._auth():
            return
        path, _ = self._q()
        if path == "/ytcheck":
            if st["busy"]:
                return self._send(409, {"error": "busy"})
            return self._send(200, ytcheck())
        return self._send(404, {"error": "route"})

    def do_PUT(self):
        if not self._auth():
            return
        path, q = self._q()
        n = self._name(q)
        if path != "/job" or not n:
            return self._send(400, {"error": "name"})
        with lock:
            if st["busy"]:
                return self._send(409, {"error": "busy", "job": st["job"]})
            st.update(busy=True, job=n, stage="upload", error=None)
        try:
            size = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(size)
            d = os.path.join(JOBS, n)
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as t:
                for m in t.getmembers():
                    if not (m.isfile() or m.isdir()) or m.name.startswith(("/", "..")) or "/../" in m.name:
                        raise ValueError(f"entrée refusée : {m.name}")
                t.extractall(d)
            os.rename(os.path.join(d, "job"), jobdir(n))
        except Exception as e:  # noqa: BLE001
            st.update(busy=False, stage="idle", error=str(e)[:300])
            return self._send(400, {"error": str(e)[:300]})
        threading.Thread(target=build, args=(n, q.get("upload") != "0"), daemon=True).start()
        return self._send(200, {"ok": True})

    def do_DELETE(self):
        if not self._auth():
            return
        path, q = self._q()
        n = self._name(q)
        if path != "/job" or not n or (st["busy"] and st["job"] == n):
            return self._send(400, {"error": "name"})
        shutil.rmtree(os.path.join(JOBS, n), ignore_errors=True)
        return self._send(200, {"ok": True})


def main():
    os.makedirs(JOBS, exist_ok=True)
    threading.Thread(target=lambda: (setup(), ytcheck()), daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), H).serve_forever()


if __name__ == "__main__":
    main()
DRYLOW_NEWS_EOF
[ -s "$DIR/token" ] || (openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$DIR/token"
TOKEN=$(cat "$DIR/token")
# proxy résidentiel pour YouTube seulement (YTDLP_PROXY=http://user:pass@hôte:port bash vps_news_setup.sh) : gardé
if [ -n "$YTDLP_PROXY" ]; then echo "$YTDLP_PROXY" > "$DIR/proxy"; chmod 600 "$DIR/proxy"; fi
PROXY=$(cat "$DIR/proxy" 2>/dev/null || true)
IP=$(curl -fs4 https://api.ipify.org || curl -fs4 https://ifconfig.me)
HOST=${DOMAIN:-news.$(echo "$IP" | tr . -).sslip.io}
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
IMAGE=python:3.12-slim
docker pull -q $IMAGE >/dev/null
docker rm -f drylow-news >/dev/null 2>&1 || true
RUN="apt-get update -qq && apt-get install -y -qq --no-install-recommends curl ca-certificates fontconfig >/dev/null && exec python -u /w.py"
BASE=(-d --name drylow-news --restart unless-stopped -e WORKER_TOKEN="$TOKEN" -e DATA_DIR=/data -e YTDLP_PROXY="$PROXY"
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
