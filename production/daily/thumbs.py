"""Fait les propositions de miniature d'un épisode avec le modèle d'image du studio (proxy CLI).

    python production/daily/thumbs.py <dossier_épisode> ideas.json --ref <image> [--ref <image> ...]

ideas.json : [{"text": "PAID IN SCRAPS", "picture": "…"}, …]. Les références (miniature validée de la
chaîne, personnages) donnent le style. Sortie : <dossier>/thumbnails/proposal-A.jpg… (1280×720, < 2 Mo)
et une planche `proposals.jpg` pour les comparer. Le choix final est copié en <dossier>/thumbnail.jpg.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from services import ai  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

RULES = ("YouTube thumbnail, 16:9, in EXACTLY the same flat 2D cartoon style, character design and colours as the "
         "reference images: same round-headed characters, black outlines, matte colours. One clear dramatic "
         "situation, very expressive simple face, readable from far away, strong contrast, no clutter. "
         "Big bold text '{text}' in {text_style}, perfectly spelled, "
         "nothing else written anywhere. No logos, no watermark, no real people. Scene: {picture}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("ideas", type=Path)
    ap.add_argument("--ref", action="append", default=[])
    a = ap.parse_args()
    ideas = json.loads(a.ideas.read_text(encoding="utf-8"))
    out = a.episode / "thumbnails"
    out.mkdir(parents=True, exist_ok=True)

    def one(i, idea):
        letter = "ABCD"[i]
        path = out / f"proposal-{letter}.jpg"
        idea = {"text_style": "YELLOW rounded comic letters with a thick BLACK outline, top-left"} | idea
        blob = ai.generate_image(RULES.format(**idea), width=1536, height=1024, refs=a.ref, quality="high",
                                 model="gpt-image-2", timeout=400)
        ai.fit_cover(blob, 1280, 720, str(path), quality=90)
        return letter, path

    with ThreadPoolExecutor(4) as pool:
        done = list(pool.map(lambda x: one(*x), enumerate(ideas[:4])))
    big = Image.new("RGB", (1280, 760), "white")
    for k, (letter, path) in enumerate(done):
        im = Image.open(path).resize((636, 358))
        x, y = (k % 2) * 642, (k // 2) * 380 + 20
        big.paste(im, (x, y))
        ImageDraw.Draw(big).text((x + 4, y - 16), letter, fill="black")
    big.save(out / "proposals.jpg", quality=85)
    print("miniatures :", ", ".join(str(p) for _, p in done))


if __name__ == "__main__":
    main()
