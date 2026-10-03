"""Crée une vidéo : dossier de travail + projet du studio (chaîne d'après le modèle).

  python production/new_video.py oddly_things_en work/ost/watch "Your Life as a Stolen Watch" --notes notes.txt

Le dossier reçoit pid.txt et video.json. notes.txt = faits vérifiés + forme de l'histoire (voir CLAUDE.md)."""
import argparse
import json
import os
import shutil

from common import WORK  # noqa: F401  (charge .env et POV_DATA_DIR)
from services import pov_engine as E, pov_store as store

ap = argparse.ArgumentParser()
ap.add_argument("template", help="modèle de chaîne : oddly_specific_en, oddly_expensive_en, oddly_things_en…")
ap.add_argument("folder")
ap.add_argument("title")
ap.add_argument("--minutes", type=float, default=None)
ap.add_argument("--notes", default=None, help="fichier de notes (sinon <folder>/notes.txt)")
ap.add_argument("--object", default=None, help="objet dessiné quand le titre ne le nomme pas (« the air fryer »)")
a = ap.parse_args()
d = os.path.abspath(a.folder)
os.makedirs(d, exist_ok=True)
notes_path = a.notes or os.path.join(d, "notes.txt")
if a.notes and os.path.abspath(a.notes) != os.path.join(d, "notes.txt"):
    shutil.copy(a.notes, os.path.join(d, "notes.txt"))
notes = open(notes_path).read() if os.path.isfile(notes_path) else ""
ch = E.studio_channel(a.template)
pr = E.new_project(ch, a.title, minutes=a.minutes, notes=notes)
fmt = E.pick_format(ch, a.title)
if fmt:
    store.update_project(pr["id"], lambda x: x.__setitem__("format", fmt))
if a.object:
    store.update_project(pr["id"], lambda x: x.__setitem__("object_noun", a.object))
open(os.path.join(d, "pid.txt"), "w").write(pr["id"])
json.dump({"template": a.template, "title": a.title, "pid": pr["id"]}, open(os.path.join(d, "video.json"), "w"), indent=1)
print(pr["id"], ch["name"], pr["minutes"], "min", fmt or ch.get("format"))
