"""Vidéo History Docs sans surveillance (chaînes The Survivor's Account, Frontier Blood), avec reprise.

  python production/history_video.py new <dossier> <chaîne> <script.md> [--title "…"]
      crée le projet à partir d'un script déjà écrit et relu (texte FacelessOS : hook, puis « ## chapitre »)
  python production/history_video.py run <dossier>
      voix → plan visuel → images → rendu (par morceaux) → miniature → Gofile ; réessaie tant que l'IA est saturée

Le dossier de travail ($STUDIO_WORK/…) garde pid.txt, pipeline.log (« ALL DONE » à la fin) et gofile_link.txt ;
le fichier « history » le signale à resume_all.sh. Le projet lui-même est dans $HISTORY_DATA_DIR."""
import glob
import os
import re
import sys
import time

from common import Job, gofile_upload, log_to, pid_of

os.environ.setdefault("REMOTION_CONCURRENCY", "4")
if not os.environ.get("REMOTION_BROWSER"):  # cloud : le Chromium déjà installé, pas de téléchargement
    shells = sorted(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell"))
    if shells:
        os.environ["REMOTION_BROWSER"] = shells[-1]

from services import history as H  # noqa: E402
from services import history_channels as HC  # noqa: E402


def new(d, key, script_path, title=None):
    ch = HC.channel(key)
    if not ch:
        raise SystemExit(f"chaîne inconnue : {key} ({', '.join(HC.CHANNELS)})")
    text = open(script_path, encoding="utf-8").read()
    head = re.match(r"\s*# (.+)\n", text)
    title = title or (head.group(1).strip() if head else None)
    if not title:
        raise SystemExit("titre manquant (--title, ou une ligne « # Titre » en tête du script)")
    # en-tête de la fiche (titre, lignes « > ») retiré : seule la narration part à la voix
    text = re.sub(r"\A\s*# .+\n(\s*>.*\n)*", "", text).strip()
    pr = H.new_project(title, ch["minutes"], options={"channel": key, "image_style": ch["image_style"]})
    pr["script"] = H.script_from_fos(text, title)
    pr["fos"] = {"text": text, "verdict": "PASS (relu)"}
    H.save_project(pr)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "pid.txt"), "w").write(pr["id"])
    open(os.path.join(d, "history"), "w").write(key)
    words = len(H.HA.narration(pr["script"]).split())
    print(pr["id"], title, f"{words} mots, {len(pr['script']['sections'])} parties")


def run(d):
    log = log_to(d, "pipeline.log")
    pid = pid_of(d)
    for k in range(1000):
        pr = H.get_project(pid)
        if pr.get("render") and pr.get("thumbnail"):
            break
        log("lance", H.stage(pr), "essai", k + 1)
        try:
            H.job_autopilot(Job(), pid)
            if not H.get_project(pid).get("thumbnail"):
                log("miniature à refaire")
                time.sleep(120)
        except Exception as e:  # noqa: BLE001 — IA saturée, coupure réseau… : on reprend où on en était
            log("échec :", str(e)[:300])
            time.sleep(min(600, 60 * (k + 1)))
    pr = H.get_project(pid)
    log("RENDER DONE", pr["render"]["file"])
    link = gofile_upload(os.path.join(H.project_dir(pid), pr["render"]["file"]), os.path.join(d, "gofile_link.txt"), log)
    log("ALL DONE", link)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 4 and a[0] == "new":
        new(os.path.abspath(a[1]), a[2], a[3], a[a.index("--title") + 1] if "--title" in a else None)
    elif len(a) == 2 and a[0] == "run":
        run(os.path.abspath(a[1]))
    else:
        raise SystemExit(__doc__)
