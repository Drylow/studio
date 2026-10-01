"""Production sans surveillance d'une vidéo, étape par étape, qui reprend là où elle en est :

  script → (relecture : fichier script_ok) → prod → qa → rendu (un à la fois par chaîne) → Gofile (md5)
  → verify.py (contrôles + planches) → (vérification humaine : fichier review_ok) → Discord.

  python production/pipeline.py <folder> [--gate] [--replan] [--no-discord]

--gate    : attend le fichier script_ok après le script (relecture obligatoire du script).
--replan  : refait le plan d'animations après le contrôle images (si les règles du réalisateur ont changé).
Les étapes faites (marqueurs dans les logs, gofile_link.txt, discord_done) ne sont jamais refaites."""
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

from common import WORK, folder, log_to, pid_of

HERE = os.path.dirname(os.path.abspath(__file__))
D = folder(sys.argv[1])
FLAGS = set(sys.argv[2:])
log = log_to(D, "pipeline.log")


def done(logname, marker):
    try:
        return marker in open(os.path.join(D, logname)).read()
    except OSError:
        return False


def step(name, logname, marker, tries=5):
    for k in range(tries):
        if done(logname, marker):
            return True
        log("lance", name, "essai", k + 1)
        with open(os.path.join(D, logname), "a") as out:
            subprocess.run([sys.executable, os.path.join(HERE, "steps.py"), name, D], stdout=out,
                           stderr=subprocess.STDOUT)
        if done(logname, marker):
            return True
        log(name, "a échoué, nouvel essai dans", 60 * (k + 1), "s")
        time.sleep(60 * (k + 1))
    raise SystemExit(f"{name} : échec après {tries} essais")


def wait_file(name, why):
    if not os.path.isfile(os.path.join(D, name)):
        log(why, "→ attente du fichier", name)
    while not os.path.isfile(os.path.join(D, name)):
        time.sleep(30)


step("script", "script.log", "AUDIT DONE", 3)
if "--gate" in FLAGS:
    wait_file("script_ok", "script à relire (script.txt), puis : production/steps.py save + touch script_ok")
log("script ok")
step("prod", "prod.log", "PROD DONE")
step("qa", "qa.log", "QA DONE", 3)
if "--replan" in FLAGS:
    step("replan", "replan.log", "REPLAN DONE", 3)
lock = os.path.join(os.path.dirname(D), "render.lock")  # un rendu à la fois par dossier de chaîne
with open(lock, "w") as lk:
    log("attente du verrou de rendu")
    fcntl.flock(lk, fcntl.LOCK_EX)
    log("rendu")
    step("render", "render.log", "RENDER DONE", 4)

os.environ.setdefault("POV_DATA_DIR", os.path.join(WORK, "prod"))
from services import pov_store as store  # noqa: E402
pid = pid_of(D)
pr = store.get_project(pid)
path = os.path.join(store.project_dir(pid), pr["render"]["file"])
md5 = hashlib.md5(open(path, "rb").read()).hexdigest()
log("vidéo", path, os.path.getsize(path), md5)
lf = os.path.join(D, "gofile_link.txt")
link = open(lf).read().strip() if os.path.isfile(lf) else None
for k in range(6):
    if link:
        break
    r = subprocess.run(["curl", "-sS", "--max-time", "1800", "-F", f"file=@{path}", "https://upload.gofile.io/uploadfile"],
                       capture_output=True, text=True)
    try:
        data = json.loads(r.stdout).get("data") or {}
        if data.get("downloadPage") and data.get("md5", md5) == md5:
            link = data["downloadPage"]
            open(lf, "w").write(link)
            break
        log("gofile réponse inattendue", r.stdout[:200])
    except Exception as e:  # noqa: BLE001
        log("gofile erreur", str(e)[:100], r.stderr[:200])
    time.sleep(20 * (k + 1))
if not link:
    raise SystemExit("Gofile : échec")
log("gofile", link)
if "--no-discord" not in FLAGS and not os.path.isfile(os.path.join(D, "discord_done")):
    # jamais d'envoi sans vérification : contrôles automatiques + planches à regarder, puis review_ok
    subprocess.run([sys.executable, os.path.join(HERE, "verify.py"), D])
    wait_file("review_ok", "vérification prête (check/report.txt, check/fx_*.jpg)")
    subprocess.run([sys.executable, os.path.join(HERE, "discord_send.py"), D, link], check=True)
    open(os.path.join(D, "discord_done"), "w").write(link)
log("ALL DONE", link)
