"""Agent du studio sur le VPS de l'utilisateur : la machine cloud n'a que le HTTPS en sortie (pas de SSH), et elle
redémarre souvent en tuant les productions. Ce petit serveur fait tourner les vidéos Oddly Specific Lives (voix,
images, montage) sur le VPS, piloté depuis le cloud en HTTPS avec un jeton.

Installé par production/vps_studio_setup.sh (Docker, python:3.12). Dépôt cloné dans /data/studio, travail dans
/data/studio/work. Chaque requête porte l'en-tête X-Worker-Token.

  GET  /status                     → état (version du dépôt, charge, disque)
  POST /exec   {"cmd", "timeout"}  → lance une commande bash dans le dépôt, rend code + sortie (fin)
  POST /spawn  {"cmd", "log"}      → lance en tâche détachée (survit à la requête), sortie dans log
  PUT  /file?path=…                → écrit un fichier (corps brut) sous /data/studio
  GET  /file?path=…                → lit un fichier sous /data/studio
Le .env (clés) est envoyé par le cloud avec PUT /file?path=.env : jamais dans git."""
import json
import os
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TOKEN = os.environ.get("WORKER_TOKEN", "")
ROOT = os.environ.get("STUDIO_ROOT", "/data/studio")
START = time.time()


def _safe(rel):
    path = os.path.realpath(os.path.join(ROOT, rel or ""))
    if not (path == ROOT or path.startswith(ROOT + os.sep)):
        raise ValueError("chemin hors du studio")
    return path


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj=None, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        if not TOKEN or self.headers.get("X-Worker-Token") != TOKEN:
            self._send(401, {"error": "token"})
            return False
        return True

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        if not self._auth():
            return
        u = urlparse(self.path)
        if u.path == "/status":
            rev = subprocess.run("git rev-parse --short HEAD", shell=True, cwd=ROOT, capture_output=True, text=True)
            du = shutil.disk_usage(ROOT if os.path.isdir(ROOT) else "/")
            return self._send(200, {"ok": True, "rev": rev.stdout.strip(), "load": os.getloadavg(),
                                    "cpus": os.cpu_count(), "free_gb": round(du.free / 1e9, 1),
                                    "uptime": int(time.time() - START)})
        if u.path == "/file":
            try:
                path = _safe(parse_qs(u.query).get("path", [""])[0])
                with open(path, "rb") as f:
                    return self._send(200, raw=f.read(), ctype="application/octet-stream")
            except (OSError, ValueError) as e:
                return self._send(404, {"error": str(e)})
        self._send(404, {"error": "route"})

    def do_PUT(self):
        if not self._auth():
            return
        u = urlparse(self.path)
        if u.path != "/file":
            return self._send(404, {"error": "route"})
        try:
            path = _safe(parse_qs(u.query).get("path", [""])[0])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = self._body()
            with open(path, "wb") as f:
                f.write(data)
            if os.path.basename(path) == ".env":
                os.chmod(path, 0o600)
            self._send(200, {"ok": True, "bytes": len(data)})
        except (OSError, ValueError) as e:
            self._send(400, {"error": str(e)})

    def do_POST(self):
        if not self._auth():
            return
        u = urlparse(self.path)
        try:
            req = json.loads(self._body() or b"{}")
        except ValueError:
            return self._send(400, {"error": "json"})
        cmd = req.get("cmd") or ""
        if u.path == "/exec":
            try:
                r = subprocess.run(["bash", "-lc", cmd], cwd=ROOT, capture_output=True, text=True,
                                   timeout=float(req.get("timeout") or 600))
                out = (r.stdout + r.stderr)[-200000:]
                return self._send(200, {"code": r.returncode, "out": out})
            except subprocess.TimeoutExpired as e:
                return self._send(200, {"code": -1, "out": f"timeout {e.timeout}s"})
        if u.path == "/spawn":
            log = _safe(req.get("log") or "work/agent_spawn.log")
            os.makedirs(os.path.dirname(log), exist_ok=True)
            with open(log, "ab") as f:
                p = subprocess.Popen(["bash", "-lc", cmd], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=True)
            return self._send(200, {"pid": p.pid})
        self._send(404, {"error": "route"})


def boot():
    """Clone le dépôt public au premier démarrage, installe les dépendances, relance les productions en cours."""
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        subprocess.run(["git", "clone", "-q", "https://github.com/drylow/studio.git", ROOT], check=True)
    subprocess.run("pip install -q -r requirements.txt", shell=True, cwd=ROOT)
    os.makedirs(os.path.join(ROOT, "work"), exist_ok=True)
    if os.path.isfile(os.path.join(ROOT, "work", "active.txt")):  # redémarrage du conteneur : on reprend tout
        subprocess.Popen(["bash", "-lc", "production/resume_all.sh; setsid nohup production/supervisor.sh "
                          ">> work/supervisor.out 2>&1 < /dev/null &"], cwd=ROOT, start_new_session=True)


if __name__ == "__main__":
    import threading
    threading.Thread(target=boot, daemon=True).start()  # le serveur répond pendant le clonage / l'installation
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), H).serve_forever()
