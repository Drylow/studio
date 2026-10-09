"""Accès au serveur o2switch (cPanel) depuis une session cloud, sans jamais afficher un identifiant.

    python production/cpanel.py sh 'commande'          # une commande dans le terminal cPanel
    python production/cpanel.py get <dossier_local> <chemin absolu> ...   # télécharge des fichiers
    python production/cpanel.py put <dossier distant> <fichier local> ... # envoie des fichiers
    python production/cpanel.py deploy <étiquette>     # met en ligne origin/main sur le site

Identifiants : CPANEL_USER et CPANEL_PASSWORD de l'environnement (ou du .env local). La session cPanel reste en
mémoire (aucun cookie écrit). `sh` passe par le websocket du terminal : il faut
`pip install websocket-client`. Une réponse « Handshake status 400 » est passagère : relancer.
`deploy` refuse si le dépôt du serveur a des changements locaux ou si un travail tourne, sauvegarde la
base dans ~/edgerunners_backups/before-<étiquette>-<date>.db, avance le serveur sur origin/main, écrit
work/studio/runtime-revision (le worker se relance tout seul) et relance le site.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import uuid

SITE = "edgerunners.fr"
HOST = "cpanel.edgerunners.fr"   # cPanel joint par son sous-domaine, port 443
CA = "/root/.ccr/ca-bundle.crt"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def local_env(names=("CPANEL_URL", "CPANEL_USER", "CPANEL_PASSWORD")):
    """Accès cPanel lus aussi dans le .env local (Codex sur le PC), si absents de l'environnement."""
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k in names and v and not os.environ.get(k):
                os.environ[k] = v.strip().strip('"').strip("'")


def _context():
    return ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()


def _open(req, timeout):
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=_context())).open(req, timeout=timeout)


def login():
    local_env()
    last = None
    for attempt in range(4):
        try:
            data = urllib.parse.urlencode({"user": os.environ["CPANEL_USER"],
                                           "pass": os.environ["CPANEL_PASSWORD"]}).encode()
            req = urllib.request.Request(f"https://{SITE}/login/?login_only=1", data=data, headers={"Host": HOST})
            with _open(req, 30) as r:
                body = json.loads(r.read())
                cookie = "; ".join(h.split(";", 1)[0] for h in r.headers.get_all("Set-Cookie") or [])
            if body.get("status") != 1:
                raise SystemExit("connexion cPanel refusée")
            return body["security_token"], cookie
        except KeyError:
            raise SystemExit("CPANEL_USER / CPANEL_PASSWORD absents de l'environnement")
        except SystemExit:
            raise
        except Exception as e:   # coupures passagères du proxy
            last = e
            time.sleep(3 * (attempt + 1))
    raise last


def shell(command, timeout=600):
    try:
        import websocket
    except ImportError:
        raise SystemExit("pip install websocket-client")
    token, cookie = login()
    marker = "__CPDONE_%d__" % int(time.time() * 1000)
    proxy = urllib.parse.urlparse(os.environ.get("HTTPS_PROXY", ""))
    options = {"http_proxy_host": proxy.hostname, "http_proxy_port": proxy.port, "proxy_type": "http"} \
        if proxy.hostname else {}
    ws = websocket.create_connection(f"wss://{SITE}{token}/websocket/Shell?rows=50&cols=250", host=HOST,
                                     origin=f"https://{HOST}", cookie=cookie,
                                     sslopt={"ca_certs": CA} if os.path.exists(CA) else {},
                                     timeout=timeout, **options)
    ws.send(f"stty -echo; export PS1=''; {{\n{command}\n}} 2>&1; echo; echo {marker} $?\n".encode(),
            opcode=websocket.ABNF.OPCODE_BINARY)
    out, end = b"", time.time() + timeout
    while time.time() < end:
        frame = ws.recv()
        out += frame if isinstance(frame, bytes) else frame.encode()
        text = out.decode("utf-8", "replace")
        m = re.search(re.escape(marker) + r" (\d+)\s", text)
        if m:
            ws.close()
            body = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\r", "", text[:m.start()])
            body = "\n".join(l for l in body.splitlines() if marker not in l and "stty -echo" not in l)
            return body.strip("\n"), int(m.group(1))
    ws.close()
    raise SystemExit("délai dépassé")


def fetch(remote, local):
    token, cookie = login()
    url = f"https://{SITE}{token}/download?" + urllib.parse.urlencode({"skipencode": 1, "file": remote})
    with _open(urllib.request.Request(url, headers={"Host": HOST, "Cookie": cookie}), 120) as r:
        data = r.read()
    with open(local, "wb") as f:
        f.write(data)
    return len(data)


def put(local, remote_dir):
    token, cookie = login()
    boundary = uuid.uuid4().hex
    with open(local, "rb") as f:
        payload = f.read()
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
             for k, v in (("dir", remote_dir), ("overwrite", "1"))]
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file-1\"; "
                 f"filename=\"{os.path.basename(local)}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
                 + payload + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"https://{SITE}{token}/execute/Fileman/upload_files", data=b"".join(parts),
                                 headers={"Host": HOST, "Cookie": cookie,
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with _open(req, 300) as r:
        body = json.loads(r.read())
    return body.get("status"), body.get("errors") or ""


DEPLOY = r"""cd ~/drylow_studio &&
test -z "$(git status --porcelain)" && echo "dépôt propre" &&
test ! -e work/studio/development-maintenance.json &&
flock -n work/studio/developer.lock true &&
~/edgerunners_venv/bin/python - 2>&1 <<'PY' &&
import os, sqlite3, time
db = sqlite3.connect('drylow_studio.db')
running = db.execute("SELECT count(*) FROM studio_jobs WHERE status IN ('running','queued')").fetchone()[0]
print('travaux en cours :', running)
assert running == 0, 'travail en cours : réessayer plus tard'
target = os.path.join(os.path.expanduser('~/edgerunners_backups'), 'before-LABEL-' + time.strftime('%Y%m%dT%H%M%S') + '.db')
copy = sqlite3.connect(target); db.backup(copy); copy.close(); os.chmod(target, 0o600)
print('sauvegarde :', target)
PY
git fetch -q origin main && git merge -q --ff-only origin/main && git log -1 --format='code : %h %s' &&
git rev-parse HEAD > work/studio/runtime-revision && mkdir -p tmp && touch tmp/restart.txt &&
sleep 75 && P=$(pgrep -f 'python -m studio.worker' | tail -1) &&
echo "worker $P depuis $(ps -o etime= -p $P), fils : $(grep Threads /proc/$P/status | awk '{print $2}')" &&
curl -s -o /dev/null -w 'site : %{http_code}\n' https://edgerunners.fr/"""


def main(argv):
    if len(argv) < 2 or argv[1] not in ("sh", "get", "put", "deploy"):
        raise SystemExit(__doc__)
    if argv[1] == "sh":
        body, code = shell(argv[2], timeout=int(os.environ.get("CP_TIMEOUT", "600")))
        print(body)
        print(f"[exit {code}]")
        return code
    if argv[1] == "deploy":
        label = re.sub(r"[^a-z0-9-]", "-", (argv[2] if len(argv) > 2 else "deploy").lower())
        body, code = shell(DEPLOY.replace("LABEL", label), timeout=300)
        print(body)
        print(f"[exit {code}]")
        return code
    if argv[1] == "get":
        for remote in argv[3:]:
            print(remote, fetch(remote, os.path.join(argv[2], remote.replace("/", "_")[-80:])))
    else:
        for local in argv[3:]:
            print(local, put(local, argv[2]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
