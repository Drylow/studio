"""Miniatures : une ou plusieurs variantes d'après un prompt et des images de référence (style validé).

  python production/thumb.py <sortie.jpg> "<prompt>" [--ref img1.jpg --ref img2.jpg] [--edit]

--edit : la 1re référence est la miniature à retoucher (« garde tout identique, change seulement X »).
Références de style validées : presets/<modèle>/thumb.jpg (voir CLAUDE.md, une par chaîne)."""
import argparse

from common import WORK  # noqa: F401
from services import ai

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("prompt")
ap.add_argument("--ref", action="append", default=[])
ap.add_argument("--edit", action="store_true")
a = ap.parse_args()
lead = ""
if a.ref and a.edit:
    lead = ("Reference image 1 = the thumbnail to edit: keep EVERYTHING exactly the same (characters, faces, pose, "
            "outfit, background, colors, style, text) except what is asked. ")
elif a.ref:
    lead = ("Reference image 1 = THE CHANNEL'S THUMBNAIL STYLE: copy its rendering, outlines, colors, composition "
            "and text treatment exactly; the subject is new, as described. Never copy the face, hair or look of "
            "a person in the reference: draw a new person (a different woman for every video). ")
blob = ai.generate_image(lead + a.prompt + " No logo, no watermark, no border.", width=1920, height=1080,
                         refs=a.ref, quality="high")
ai.fit_cover(blob, 1280, 720, a.out, quality=92)
print("OK", a.out)
