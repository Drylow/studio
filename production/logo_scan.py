"""Cherche les marques déposées sur les images d'une vidéo POV (cercles Mastercard sur une carte, damier ou
matelassé à chaîne façon grande marque sur un sac, logo de voiture ou de téléphone) et, avec --fix, refait ces
images avec la consigne « sans marque ». À lancer avant le rendu, ou avant de vérifier une vidéo déjà rendue
(il faut alors refaire le rendu : python production/steps.py render <dossier>).

  python production/logo_scan.py <dossier> [--fix]"""
import base64
import sys
from concurrent.futures import ThreadPoolExecutor

from common import Job, folder, pid_of
from services import ai, pov_engine as E, pov_store as store

QA = """Look closely at this cartoon image, including small objects held in hands. Is there any REAL brand mark?
Count only these: overlapping circles or any network logo on a payment card; a designer monogram, checkerboard,
plaid or quilted-chain pattern on a bag; a car badge; a fruit or other logo on a phone or laptop; any other
recognizable company logo. Plain cards with only a chip, plain leather bags, blank tags are fine.
Return JSON {"brand": true|false, "what": "short description or empty"}."""
FIX = (" Every payment card is plain with only a chip, every bag is plain smooth leather: no logo, no monogram, "
       "no checkerboard, plaid or quilted-chain pattern, no badge, no brand mark of any kind.")

d = folder(sys.argv[1])
pid = pid_of(d)
pr = store.get_project(pid)
pdir = store.project_dir(pid)


def scan(sc):
    if not sc.get("image") or (sc.get("fx") or {}).get("type") in E._full_panel():
        return sc["i"], False, ""
    with open(f"{pdir}/{sc['image']}", "rb") as f:
        blob = E._jpeg(f.read(), side=1024)
    content = [{"type": "text", "text": QA},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(blob).decode()}}]
    for _ in range(3):
        try:
            res = ai.chat_json([{"role": "user", "content": content}], model=ai.text_model(), timeout=240)
            return sc["i"], bool(res.get("brand")), str(res.get("what") or "")
        except Exception:  # noqa: BLE001 — IA saturée : on réessaie
            continue
    return sc["i"], None, "contrôle impossible"


with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(scan, pr["scenes"]))
bad = [i for i, b, _ in res if b]
for i, b, what in res:
    if b or b is None:
        print(f"scène {i}: {'MARQUE' if b else '?'} {what}")
print(f"{len(bad)} image(s) avec une marque sur {len(res)}")
if bad and "--fix" in sys.argv:
    def f(x):
        for s in x["scenes"]:
            if s["i"] in bad and FIX not in s["prompt"]:
                s["prompt"] = s["prompt"].rstrip() + FIX
    store.update_project(pid, f)
    E.job_images(Job(), pid, only=bad)
    print("refaites :", bad)
