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

Relais vers le PC de l'utilisateur (YouTube bloque ce VPS, pas une connexion de maison) : le cloud dépose la vidéo,
l'agent du PC (standalone/pc_agent/pc_agent.py, tâche Windows toutes les 15 min) la prend, monte, renvoie le résultat.
  PUT  /pcjob?name=NOM         dépose le .tgz (même contenu que /job) pour le PC
  GET  /pc/next                (PC) prochaine vidéo à monter → {name} ou {name: null} ; note l'heure de passage du PC
  GET  /pc/job?name=NOM        (PC) le .tgz
  PUT  /pc/result?name=NOM&path=P  (PC) result.json, build.log, check/sheet_XX.jpg
  POST /pc/done?name=NOM       (PC) fini
  GET  /pc/state?name=NOM      {state: pending|claimed|done, log, pc_seen}
  GET  /pc/file?name=NOM&path=P   un fichier renvoyé par le PC
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
PC = os.path.join(DATA, "pc")
RESULT_PATH = re.compile(r"(result\.json|build\.log|worker\.log|check/sheet_\d{2}\.jpg)")
STALL = 20 * 60   # montage sans nouvelles (le PC renvoie build.log chaque minute) depuis 20 min : reproposé
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


def pc_state(name, **upd):
    path = os.path.join(PC, name, "state.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    if upd:
        s.update(upd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(s, f)
    return s


def pc_next():
    st["pc_seen"] = time.time()
    with lock:
        jobs = []
        for n in os.listdir(PC) if os.path.isdir(PC) else []:
            s = pc_state(n)
            last = max(s.get("claimed", 0), s.get("progress", 0))
            free = s.get("state") == "pending" or (s.get("state") == "claimed" and time.time() - last > STALL)
            if free:
                jobs.append((s.get("t", 0), n))
        if not jobs:
            return None
        n = sorted(jobs)[0][1]
        pc_state(n, state="claimed", claimed=time.time())
        return n


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
        if path == "/pc/next":
            return self._send(200, {"name": pc_next()})
        if path in ("/pc/job", "/pc/state", "/pc/file"):
            n = self._name(q)
            if not n or not os.path.isdir(os.path.join(PC, n)):
                return self._send(404, {"error": "absent"})
            if path == "/pc/job":
                with open(os.path.join(PC, n, "job.tgz"), "rb") as fh:
                    return self._send(200, data=fh.read(), ctype="application/gzip")
            if path == "/pc/state":
                return self._send(200, dict(pc_state(n), pc_seen=st.get("pc_seen"),
                                            log=tail(os.path.join(PC, n, "out", "build.log"))))
            rel = q.get("path", "")
            f = os.path.join(PC, n, "out", rel)
            if not RESULT_PATH.fullmatch(rel) or not os.path.isfile(f):
                return self._send(404, {"error": "absent"})
            with open(f, "rb") as fh:
                return self._send(200, data=fh.read(), ctype="application/octet-stream")
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
        path, q = self._q()
        if path == "/pc/done":
            n = self._name(q)
            if not n or not os.path.isdir(os.path.join(PC, n)):
                return self._send(404, {"error": "absent"})
            pc_state(n, state="done", done=time.time(), ok=q.get("ok") == "1")
            return self._send(200, {"ok": True})
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
        if path in ("/pcjob", "/pc/result") and n:
            size = int(self.headers.get("Content-Length") or 0)
            if size > 200_000_000:
                return self._send(413, {"error": "trop gros"})
            raw = self.rfile.read(size)
            if path == "/pcjob":
                d = os.path.join(PC, n)
                shutil.rmtree(d, ignore_errors=True)
                os.makedirs(d)
                with open(os.path.join(d, "job.tgz"), "wb") as f:
                    f.write(raw)
                pc_state(n, state="pending", t=time.time())
                return self._send(200, {"ok": True})
            rel = q.get("path", "")
            if not RESULT_PATH.fullmatch(rel) or not os.path.isdir(os.path.join(PC, n)):
                return self._send(400, {"error": "path"})
            f = os.path.join(PC, n, "out", rel)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f, "wb") as fh:
                fh.write(raw)
            pc_state(n, progress=time.time())
            return self._send(200, {"ok": True})
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
    os.makedirs(PC, exist_ok=True)
    threading.Thread(target=lambda: (setup(), ytcheck()), daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), H).serve_forever()


if __name__ == "__main__":
    main()
