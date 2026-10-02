"""Copie dans le dépôt (dossier chaines/) tout ce qu'il faut pour suivre chaque chaîne sans le studio :
pour chaque vidéo, le script, la recherche (notes), la publication (titres, description, tags, chapitres,
commentaire épinglé) et la miniature choisie. À relancer après chaque vidéo, puis commit (push auto).

  python production/export_channels.py

Les fichiers README.md des chaînes (concept, style, idées) sont écrits à la main et ne sont jamais écrasés.
Les liens Gofile restent dans production/VIDEOS.md (un seul endroit, toujours le bon lien)."""
import ast
import glob
import os
import re

from common import REPO, WORK
from services import pov_store as store
from PIL import Image

OUT = os.path.join(REPO, "chaines")
SLUGS = {"oddly_specific_en": "oddly-specific-lives", "oddly_expensive_en": "oddly-expensive-lives",
         "oddly_things_en": "oddly-specific-things"}


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower().replace("pov:", "")).strip("-")


def as_list(v):
    if isinstance(v, str) and v.startswith("["):
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            pass
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()] if "," in v else ([v] if v else [])
    return list(v or [])


def folders():
    """pid du projet → dossier de travail (notes.txt, thumb_choice.txt...)."""
    found = {}
    for p in glob.glob(os.path.join(WORK, "*", "*", "pid.txt")):
        found[open(p).read().strip()] = os.path.dirname(p)
    return found


def save_thumb(src, dest):
    im = Image.open(src)
    if im.mode != "RGB":
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.convert("RGBA").split()[-1])
        im = bg
    im.thumbnail((1280, 720))
    im.save(dest, quality=85)


def export():
    chans = {c["id"]: c for c in store.list_channels()}
    work = folders()
    index = {}
    for pid in sorted(os.listdir(os.path.join(store.data_dir(), "projects"))):
        try:
            pr = store.get_project(pid)
        except Exception:  # noqa: BLE001
            continue
        if not pr:
            continue
        ch = chans.get(pr.get("channel_id")) or {}
        cslug = SLUGS.get(ch.get("template"))
        if not cslug or not (pr.get("script") or "").strip():
            continue
        wd = work.get(pid)
        if wd and os.path.isfile(os.path.join(wd, "ABANDONED")):  # vidéo abandonnée par l'utilisateur
            continue
        d = os.path.join(OUT, cslug, "videos", slug(pr["title"]))
        os.makedirs(d, exist_ok=True)
        # script
        open(os.path.join(d, "script.md"), "w").write(f"# {pr['title']}\n\n{pr['script'].strip()}\n")
        # recherche
        notes = ""
        if wd and os.path.isfile(os.path.join(wd, "notes.txt")):
            notes = open(os.path.join(wd, "notes.txt")).read()
        notes = notes.strip() or (pr.get("notes") or "").strip()
        if notes:
            open(os.path.join(d, "recherche.md"), "w").write(
                f"# Recherche et consignes — {pr['title']}\n\nFaits vérifiés et règles données au script.\n\n{notes}\n")
        # publication
        m = pr.get("metadata") or {}
        lines = [f"# Publication — {pr['title']}", ""]
        titles = as_list(m.get("titles"))
        if titles:
            lines += ["## Titres proposés", ""] + [f"{k + 1}. {t}" for k, t in enumerate(titles)] + [""]
        if m.get("description"):
            lines += ["## Description", "", m["description"].strip(), ""]
        chapters = as_list(m.get("chapters"))
        if chapters:
            lines += ["## Chapitres", "", *chapters, ""]
        tags = as_list(m.get("tags"))
        if tags:
            lines += ["## Tags", "", ", ".join(tags), ""]
        if m.get("pinned_comment"):
            lines += ["## Commentaire épinglé", "", m["pinned_comment"].strip(), ""]
        open(os.path.join(d, "publication.md"), "w").write("\n".join(lines))
        # miniature choisie (une miniature déjà dans le dépôt n'est remplacée que par un nouveau choix)
        thumb = None
        if wd and os.path.isfile(os.path.join(wd, "thumb_choice.txt")):
            thumb = open(os.path.join(wd, "thumb_choice.txt")).read().strip()
        if thumb and os.path.isfile(thumb):
            save_thumb(thumb, os.path.join(d, "miniature.jpg"))
        index.setdefault(cslug, []).append((pr.get("created") or pid, pr["title"], slug(pr["title"])))
    for cslug, vids in index.items():
        rows = ["# Vidéos", "", "Généré par `production/export_channels.py` (liens et état : `production/VIDEOS.md`).",
                "", "| Vidéo | Script | Recherche | Publication | Miniature |", "|---|---|---|---|---|"]
        for _, title, s in sorted(vids):
            base = os.path.join(OUT, cslug, "videos", s)
            cell = lambda f, n: f"[{n}]({s}/{f})" if os.path.isfile(os.path.join(base, f)) else "—"  # noqa: E731
            mini = [f for f in sorted(os.listdir(base)) if f.startswith("miniature")]
            rows.append(f"| {title} | {cell('script.md', 'script')} | {cell('recherche.md', 'notes')} | "
                        f"{cell('publication.md', 'titre, description, tags')} | "
                        f"{' '.join(f'[{f}]({s}/{f})' for f in mini) or 'à faire'} |")
        open(os.path.join(OUT, cslug, "videos", "README.md"), "w").write("\n".join(rows) + "\n")
        print(cslug, len(vids), "vidéos")


if __name__ == "__main__":
    export()
