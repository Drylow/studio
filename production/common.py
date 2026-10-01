"""Chemins et petits outils partagés par les scripts de production (une vidéo = un dossier de travail).

Dossier de travail : $STUDIO_WORK (par défaut <repo>/work, ignoré par git). Les projets du studio vont
dans $POV_DATA_DIR (par défaut $STUDIO_WORK/prod). Les secrets restent dans .env (jamais dans git)."""
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO, ".env"))
except ImportError:  # pragma: no cover
    pass
WORK = os.path.abspath(os.environ.get("STUDIO_WORK") or os.path.join(REPO, "work"))
os.environ.setdefault("POV_DATA_DIR", os.path.join(WORK, "prod"))
PROD = os.environ["POV_DATA_DIR"]


class Job:
    """Remplace le job de l'interface : affiche la progression dans le log du dossier."""

    def __init__(self):
        self.last = ""

    def update(self, p, msg=None):
        if msg and msg != self.last:
            print(f"[{p}] {msg}", flush=True)
            self.last = msg

    def cancelled(self):
        return False


def folder(path):
    d = os.path.abspath(path)
    if not os.path.isfile(os.path.join(d, "pid.txt")):
        raise SystemExit(f"{d} : pas de pid.txt (crée la vidéo avec production/new_video.py)")
    return d


def pid_of(d):
    return open(os.path.join(d, "pid.txt")).read().strip()


def log_to(d, name):
    f = open(os.path.join(d, name), "a")

    def log(*a):
        f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
        f.flush()
    return log


def webhook():
    """URL du webhook Discord : DISCORD_WEBHOOK_URL dans .env, sinon $STUDIO_WORK/discord_webhook.txt."""
    url = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    path = os.path.join(WORK, "discord_webhook.txt")
    if not url and os.path.isfile(path):
        url = open(path).read().strip()
    if not url:
        raise SystemExit("Pas de webhook Discord : mets DISCORD_WEBHOOK_URL dans .env")
    return url
