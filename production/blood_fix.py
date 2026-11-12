"""Chasse au sang dans les images d'un projet (films zombie Last Safe Door, 12 nov. : traces de mains rouges sur une
porte de l'hôpital) : contrôle en vision de chaque image, puis retouche des images touchées (même image, sang retiré).

  python production/blood_fix.py <dossier> [--scan-only]
Écrit <dossier>/blood.json (scènes touchées) ; la retouche crée un nouveau fichier et met à jour la scène."""
import base64
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import WORK, folder  # noqa: F401
from services import ai, pov_engine as E, pov_store as store

D = folder(sys.argv[1])
pid = open(os.path.join(D, "pid.txt")).read().strip()
pdir = os.path.dirname(store.project_path(pid))
Q = ("Look at this cartoon image. Is there ANY blood or blood-like mark: red handprints, red smears, drips, splatter, "
     "red stains or puddles on doors, walls, floors, clothes or bodies, wounds or gore? Red emergency lights, red exit "
     "signs, red stripes on an ambulance, red clothes, red objects and red reflections of lights do NOT count. "
     'Return JSON {"blood": true|false, "where": "short"}.')
FIX = ("Reference image 1 = the image to edit: keep EVERYTHING exactly the same (characters, faces, poses, outfits, "
       "background, camera, colors, style, lighting) except: remove every blood mark (red handprints, smears, drips, "
       "splatter, stains, puddles) and replace it with the clean surface underneath (plain door paint, clean wall, "
       "clean floor). No blood anywhere. No text.")


def check(s):
    p = os.path.join(pdir, s["image"])
    try:
        blob = E._jpeg(open(p, "rb").read(), side=768)
        r = ai.chat_json([{"role": "user", "content": [{"type": "text", "text": Q}, {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(blob).decode()}}]}], model=ai.text_model(), timeout=240)
        return s["i"], bool(r.get("blood")), r.get("where", "")
    except Exception as e:  # noqa: BLE001
        return s["i"], None, str(e)[:80]


def fix(s):
    src = os.path.join(pdir, s["image"])
    for _ in range(2):
        try:
            blob = ai.generate_image(FIX, width=1920, height=1080, refs=[src])
            from PIL import Image
            w, h = Image.open(os.path.join(pdir, s["image"])).size  # même taille que l'image d'origine
            rel = os.path.join(os.path.dirname(s["image"]), f"nob_{s['i']}_{int(time.time())}.jpg")
            ai.fit_cover(blob, w, h, os.path.join(pdir, rel))
            i, bad, _ = check({"i": s["i"], "image": rel})
            if bad is False:
                return s["i"], rel
            src = os.path.join(pdir, rel)  # encore du sang : on repart de la retouche
        except Exception as e:  # noqa: BLE001
            print("échec", s["i"], e, flush=True)
    return s["i"], None


scenes = [s for s in store.get_project(pid)["scenes"] if s.get("image")]
with ThreadPoolExecutor(24) as ex:
    res = list(ex.map(check, scenes))
bad = [i for i, b, _ in res if b]
again = [s for s in scenes if s["i"] in {i for i, b, _ in res if b is None}]
if again:
    with ThreadPoolExecutor(8) as ex:
        bad += [i for i, b, _ in ex.map(check, again) if b]
print("sang :", sorted(bad), flush=True)
json.dump({"bad": sorted(bad), "where": {i: w for i, b, w in res if b}}, open(os.path.join(D, "blood.json"), "w"))
if "--scan-only" in sys.argv or not bad:
    sys.exit()
todo = [s for s in scenes if s["i"] in bad]
with ThreadPoolExecutor(16) as ex:
    done = dict(ex.map(fix, todo))
ok = {i: r for i, r in done.items() if r}


def upd(x):
    for s in x["scenes"]:
        if s["i"] in ok:
            s["image"] = ok[s["i"]]


store.update_project(pid, upd)
print("corrigées", len(ok), "/", len(bad), "restantes", sorted(set(bad) - set(ok)), flush=True)
