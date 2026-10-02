"""Vidéo History Docs sans surveillance (chaînes The Survivor's Account, Frontier Blood), avec reprise.

  python production/history_video.py new <dossier> <chaîne> <script.md> [--title "…"]
      crée le projet à partir d'un script déjà écrit et relu (texte FacelessOS : hook, puis « ## chapitre »)
  python production/history_video.py run <dossier>
      voix → plan visuel → images → rendu (par morceaux) → miniature → Gofile → planches de vérification (check/)
      → attente de review_ok (vidéo regardée image par image) → paquet Discord ; réessaie tant que l'IA sature

Le dossier de travail ($STUDIO_WORK/…) garde pid.txt, pipeline.log (« ALL DONE » à la fin) et gofile_link.txt ;
le fichier « history » le signale à resume_all.sh. Le projet lui-même est dans $HISTORY_DATA_DIR."""
import glob
import json
import os
import subprocess
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
from services import media  # noqa: E402
from services import pov_script as S  # noqa: E402


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
    video = os.path.join(H.project_dir(pid), pr["render"]["file"])
    link = gofile_upload(video, os.path.join(d, "gofile_link.txt"), log)
    log("gofile", link)
    if not os.path.isfile(os.path.join(d, "discord_done")):
        package(d, pr, log)
        sheets(d, pr, video)
        log("vérification prête (check/sheet_*.jpg) → attente du fichier review_ok")
        while not os.path.isfile(os.path.join(d, "review_ok")):
            time.sleep(30)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "discord_send.py"), d, link], check=True)
        open(os.path.join(d, "discord_done"), "w").write(link)
    log("ALL DONE", link)


def package(d, pr, log):
    """Paquet de publication pour discord_send.py : meta.json (FacelessOS packaging + chapitres),
    video.json (nom de la chaîne), thumb_choice.txt (miniature du projet)."""
    key = open(os.path.join(d, "history")).read().strip()
    path = os.path.join(d, "meta.json")
    for k in range(20):
        if os.path.isfile(path):
            break
        try:
            meta = S.package(HC.fos_channel(key), {"title": pr["title"],
                                                   "script": (pr.get("fos") or {}).get("text") or H.HA.narration(pr["script"])})
            meta["chapters"] = H.chapters(pr)
            json.dump(meta, open(path, "w"), indent=1, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            log("métadonnées : échec", str(e)[:200])
            time.sleep(min(600, 60 * (k + 1)))
    json.dump({"brand": HC.channel(key)["name"], "title": pr["title"]}, open(os.path.join(d, "video.json"), "w"))
    open(os.path.join(d, "thumb_choice.txt"), "w").write(os.path.join(H.project_dir(pr["id"]), pr["thumbnail"]))


def sheets(d, pr, video, per=16):
    """Une image par plan (animations : vers la fin, une fois construites), 16 par planche, pour tout regarder."""
    from PIL import Image, ImageDraw
    out = os.path.join(d, "check")
    os.makedirs(out, exist_ok=True)
    shots = []
    for s in pr["plan"]["segments"]:
        dur = s["end"] - s["start"]
        t = s["start"] + (dur * 0.5 if s["type"] in ("image", "video") else max(dur * 0.5, dur - 0.6))
        shots.append((t, s["type"]))
    for k in range(0, len(shots), per):
        sheet = Image.new("RGB", (1600, 900), "white")
        for j, (t, kind) in enumerate(shots[k:k + per]):
            f = os.path.join(out, "frame.jpg")
            media.run(["-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=400:-1", f])
            x, y = (j % 4) * 400, (j // 4) * 225
            sheet.paste(Image.open(f).convert("RGB"), (x, y))
            ImageDraw.Draw(sheet).rectangle([x, y, x + 120, y + 16], fill="black")
            ImageDraw.Draw(sheet).text((x + 3, y + 2), f"{int(t) // 60}:{int(t) % 60:02d} {kind}", fill="yellow")
        sheet.save(os.path.join(out, f"sheet_{k // per:02d}.jpg"), quality=85)
    try:
        os.remove(os.path.join(out, "frame.jpg"))
    except OSError:
        pass


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 4 and a[0] == "new":
        new(os.path.abspath(a[1]), a[2], a[3], a[a.index("--title") + 1] if "--title" in a else None)
    elif len(a) == 2 and a[0] == "run":
        run(os.path.abspath(a[1]))
    else:
        raise SystemExit(__doc__)
