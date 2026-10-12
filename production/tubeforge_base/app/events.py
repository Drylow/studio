"""Journal d'activité : chaque étape, appel au modèle, image, rendu…

- affiché en direct dans la console (fenêtre noire de start.bat), avec couleurs ;
- gardé dans le projet (p["log"]) pour le panneau « Journal » de l'interface.

Le projet courant est porté par une variable de contexte : tout ce qui tourne pour un projet
(même les appels au modèle au fond de llm.py) est automatiquement rattaché au bon journal.
"""
import contextvars
import os
import sys
import time

current: contextvars.ContextVar = contextvars.ContextVar("tubeforge_project", default=None)

COLORS = {"info": "", "step": "\033[96m", "ok": "\033[92m", "warn": "\033[93m", "error": "\033[91m",
          "api": "\033[90m"}
RESET = "\033[0m"
MAX_LINES = 500
_ready = False


def _setup_console() -> None:
    global _ready
    if _ready:
        return
    _ready = True
    if os.name == "nt":
        os.system("")  # active les couleurs ANSI dans cmd.exe
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # jamais de plantage sur un caractère spécial
        except (AttributeError, ValueError):
            pass


def log(msg: str, level: str = "info", p: dict | None = None) -> None:
    _setup_console()
    p = p if p is not None else current.get()
    if p is not None:
        lines = p.setdefault("log", [])
        lines.append({"t": round(time.time(), 2), "l": level, "m": msg})
        if len(lines) > MAX_LINES:
            del lines[:-MAX_LINES]
        p["last_activity"] = time.time()
    who = (p.get("title") or p.get("id") or "projet")[:34] if p else "TubeForge"
    line = f"{time.strftime('%H:%M:%S')}  [{who}]  {msg}"
    try:
        print(f"{COLORS.get(level, '')}{line}{RESET if COLORS.get(level) else ''}", flush=True)
    except Exception:  # noqa: BLE001 — la console ne doit jamais faire planter une génération
        pass


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} min {s:02d}"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d}"
