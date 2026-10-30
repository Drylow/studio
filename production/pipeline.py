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


def short_by():
    """Minutes manquantes sous la durée minimum de la chaîne (0 si OK) : voix si elle existe, sinon script."""
    os.environ.setdefault("POV_DATA_DIR", os.path.join(WORK, "prod"))
    from services import pov_store as st
    from services import pov_script as S
    pr = st.get_project(pid_of(D))
    ch = st.get_channel(pr["channel_id"]) or {}
    need = 0.0 if "--pilot" in FLAGS else float(ch.get("min_minutes") or 0)  # essai court (test d'outil)
    v = pr.get("voice") or {}
    # sur le script seul, marge d'1 min : la voix sort parfois plus vite que prévu (Spartan : 26,7 estimées → 24,9)
    have = (v["duration"] / 60.0 if v.get("duration")
            else S.word_count(S.narration(pr.get("script") or "")) / float(ch.get("wpm") or 150) - 1.0)
    log(f"durée : {have:.1f} min (minimum {need:g})")
    return max(0.0, need - have)


step("script", "script.log", "AUDIT DONE", 3)
while True:
    if "--gate" in FLAGS:
        wait_file("script_ok", "script à relire (script.txt), puis : production/steps.py save + touch script_ok")
    miss = short_by()
    if not miss or "--gate" not in FLAGS:
        break
    # 25 min minimum, c'est minimum (l'utilisateur, 18 oct.) : pas de prod sur un script trop court
    os.remove(os.path.join(D, "script_ok"))
    log(f"SCRIPT TROP COURT : il manque {miss:.1f} min → ajouter des scènes, steps.py save, puis touch script_ok")
log("script ok")
step("prod", "prod.log", "PROD DONE")
if short_by():
    raise SystemExit("VOIX TROP COURTE : allonger le script et refaire la voix avant le rendu")
if "--no-qa" not in FLAGS:  # contrôle en vision sauté : relecture des planches à la main (gain ~10 min)
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
