"""Illustrations en pixel art pour les vidéos TikTok, dans la palette de la chaîne.

Voie normale depuis le 9 oct. 2026 : Algrow (1 crédit l'image, modèle nano-banana-2), sans Replicate.
    python tiktok_engine/art.py prompts videos/<nom>/script.json   # consignes Algrow des images manquantes
    (générer chaque image avec l'outil Algrow generate_image : prompt, aspect_ratio et références donnés)
    python tiktok_engine/art.py fit videos/<nom>/script.json nom=<url ou fichier> [nom=...]
fit recadre au format demandé, réduit en vrais pixels sur la palette, rend le fond noir transparent
et refait la planche art_review.jpg (vérifier mains, doigts, visages).

Ancienne voie Replicate (clé REPLICATE_API_TOKEN dans .env, crédits presque épuisés) :
    python tiktok_engine/art.py gen <sortie.png> "<prompt>" [--model rd|flux] [--size 256x256] [--keep-bg]
- rd   : retro-diffusion/rd-plus, vrai pixel art, guidé par l'image de palette et fond retiré.
- flux : black-forest-labs/flux-1.1-pro, puis réduit en pixels et tramé (Bayer) sur la palette.
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# même palette que engine.js : noir, bleu nuit, bleu sombre, bleu vif, bleu clair, blanc, gris, peau
PALETTE = ["#05060c", "#0b1452", "#14259a", "#2347ff", "#8197ff", "#eceaf2", "#8d91a5", "#2b2e3b", "#dcc6bc"]
RAMP = ["#05060c", "#0b1452", "#14259a", "#2347ff", "#8197ff", "#eceaf2"]   # du sombre au clair, pour le tramage
STYLE = ("pixel art, limited palette of deep blues, white and grey, high contrast, dramatic rim light, "
         "pure black background, centered subject, no text")


def token():
    tok = os.environ.get("REPLICATE_API_TOKEN")
    if not tok:
        for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
            if line.startswith("REPLICATE_API_TOKEN="):
                tok = line.split("=", 1)[1].strip()
    if not tok:
        raise SystemExit("REPLICATE_API_TOKEN absente du .env")
    return tok


def replicate(model, inputs, timeout=300):
    req = urllib.request.Request(f"https://api.replicate.com/v1/models/{model}/predictions",
                                 data=json.dumps({"input": inputs}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json",
                                          "Prefer": "wait=60"})
    pred = json.load(urllib.request.urlopen(req, timeout=120))
    t0 = time.time()
    while pred.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > timeout:
            raise SystemExit(f"Replicate trop long ({pred.get('id')})")
        time.sleep(2)
        pred = json.load(urllib.request.urlopen(urllib.request.Request(
            pred["urls"]["get"], headers={"Authorization": f"Bearer {token()}"}), timeout=60))
    if pred["status"] != "succeeded":
        raise SystemExit(f"Replicate : {pred.get('error')}")
    out = pred["output"]
    urls = out if isinstance(out, list) else [out]
    return [urllib.request.urlopen(u, timeout=120).read() for u in urls]


def palette_png():
    img = Image.new("RGB", (len(PALETTE) * 8, 8))
    for i, c in enumerate(PALETTE):
        img.paste(tuple(int(c[k:k + 2], 16) for k in (1, 3, 5)), (i * 8, 0, i * 8 + 8, 8))
    buf = io.BytesIO(); img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5


def pixelize(img, width=96, keep_bg=False, black=0.07):
    """Réduit en vrais pixels et tramage ordonné sur la rampe de bleus ; le noir devient transparent."""
    img = img.convert("RGB")
    h = round(img.height * width / img.width)
    small = np.asarray(img.resize((width, h), Image.LANCZOS)).astype(float) / 255
    lum = small @ np.array([0.299, 0.587, 0.114])
    ramp = np.array([[int(c[k:k + 2], 16) for k in (1, 3, 5)] for c in RAMP], float)
    n = len(RAMP) - 1
    yy, xx = np.mgrid[0:h, 0:width]
    v = np.clip(lum * n + BAYER[yy % 4, xx % 4] * 0.9, 0, n)
    idx = np.rint(v).astype(int)
    out = np.zeros((h, width, 4), np.uint8)
    out[..., :3] = ramp[idx]
    out[..., 3] = 255 if keep_bg else np.where(lum < black, 0, 255)
    return Image.fromarray(out, "RGBA")


def generate(dest, prompt, model="rd", size=(256, 256), keep_bg=False, seed=None):
    if model == "rd":
        inputs = {"prompt": f"{prompt}, {STYLE}", "width": size[0], "height": size[1], "style": "default",
                  "remove_bg": not keep_bg, "input_palette": palette_png()}
        if seed is not None:
            inputs["seed"] = seed
        data = replicate("retro-diffusion/rd-plus", inputs)[0]
        Image.open(io.BytesIO(data)).convert("RGBA").save(dest)
    else:
        inputs = {"prompt": f"{prompt}, dramatic chiaroscuro, single subject isolated on pure black background, "
                            "high contrast, no text", "aspect_ratio": "1:1", "output_format": "png"}
        if seed is not None:
            inputs["seed"] = seed
        data = replicate("black-forest-labs/flux-1.1-pro", inputs)[0]
        raw = Image.open(io.BytesIO(data))
        raw.save(dest.replace(".png", "_src.png"))
        pixelize(raw, width=max(48, size[0] // 2), keep_bg=keep_bg).save(dest)
    return dest


def batch(script_path, only=None, workers=4):
    """Génère les images listées dans "art" du script (seulement celles qui manquent, ou --only nom)."""
    from concurrent.futures import ThreadPoolExecutor
    script = json.load(open(script_path, encoding="utf-8"))
    base = os.path.join(os.path.dirname(os.path.abspath(script_path)), "art")
    os.makedirs(base, exist_ok=True)
    jobs = []
    for name, spec in script.get("art", {}).items():
        dest = os.path.join(base, name + ".png")
        if (only and name not in only) or (not only and os.path.exists(dest)):
            continue
        w, h = map(int, spec.get("size", "256x256").split("x"))
        jobs.append((dest, spec["prompt"], spec.get("model", "rd"), (w, h), spec.get("keep_bg", False), spec.get("seed")))

    def run(j):
        try:
            generate(*j)
            return f"{os.path.basename(j[0])} ok"
        except BaseException as e:  # noqa: BLE001 — une image ratée ne bloque pas les autres
            return f"{os.path.basename(j[0])} ERREUR {e}"
    with ThreadPoolExecutor(workers) as ex:
        for line in ex.map(run, jobs):
            print(line, flush=True)
    review_sheet(base)
    print("ART DONE", flush=True)


# Algrow : nos anciennes illustrations rd-plus (dépôt public) servent de référence de style.
REF = "https://raw.githubusercontent.com/Drylow/studio/main/tiktok_engine/videos/"
REFS = {
    "person": [REF + "joconde_vol/art/detective.png", REF + "napoleon_russie/art/napoleon_portrait.png"],
    "scene": [REF + "napoleon_russie/art/blizzard.png", REF + "joconde_vol/art/thief.png"],
}
ALGROW_STYLE = (
    "Pixel art illustration in exactly the same style as the reference images: low-resolution retro pixel "
    "art with big visible square pixels, checkerboard dithering, strictly limited palette of deep navy blue, "
    "vivid royal blue, light periwinkle blue, off-white and grey, with muted pale skin tones only, dramatic "
    "rim light, pure solid black background, centered, no text, no border, anatomically correct hands with "
    "five fingers. Subject: "
)
RATIOS = {"1:1": 1, "3:4": 3 / 4, "4:3": 4 / 3, "16:9": 16 / 9, "9:16": 9 / 16}


def algrow_request(spec):
    """Prompt, format and style references for Algrow generate_image."""
    w, h = map(int, spec.get("size", "256x256").split("x"))
    ratio = min(RATIOS, key=lambda r: abs(RATIOS[r] - w / h))
    kind = spec.get("kind") or ("person" if w <= h else "scene")
    return {"prompt": ALGROW_STYLE + spec["prompt"], "aspect_ratio": ratio, "model": "nano-banana-2",
            "reference_image_urls": REFS[kind]}


def prompts(script_path, only=None):
    script = json.load(open(script_path, encoding="utf-8"))
    base = os.path.join(os.path.dirname(os.path.abspath(script_path)), "art")
    todo = {n: algrow_request(s) for n, s in script.get("art", {}).items()
            if (only and n in only) or (not only and not os.path.exists(os.path.join(base, n + ".png")))}
    print(json.dumps(todo, ensure_ascii=False, indent=2))


def fit_palette(img, size, keep_bg=False):
    """Image Algrow -> vrais pixels de la palette, au format exact ; le noir relié aux bords devient transparent."""
    from scipy import ndimage
    w, h = size
    img = img.convert("RGB")
    if img.width / img.height > w / h:          # recadrage au centre sur le format demandé
        cw = round(img.height * w / h)
        img = img.crop(((img.width - cw) // 2, 0, (img.width - cw) // 2 + cw, img.height))
    else:
        ch = round(img.width * h / w)
        img = img.crop((0, (img.height - ch) // 2, img.width, (img.height - ch) // 2 + ch))
    x = np.asarray(img.resize((w, h), Image.BOX)).astype(float)
    pal = np.array([[int(c[k:k + 2], 16) for k in (1, 3, 5)] for c in PALETTE], float)
    d = (((x[..., None, :] - pal[None, None]) / 255) ** 2 * np.array([0.3, 0.59, 0.11])).sum(-1)
    idx = d.argmin(-1)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = pal[idx]
    out[..., 3] = 255
    if not keep_bg:
        labels, _ = ndimage.label(idx == 0)
        edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
        out[..., 3] = np.where(np.isin(labels, list(edge)), 0, 255)
    return Image.fromarray(out, "RGBA")


def fit(script_path, pairs):
    script = json.load(open(script_path, encoding="utf-8"))
    base = os.path.join(os.path.dirname(os.path.abspath(script_path)), "art")
    os.makedirs(base, exist_ok=True)
    for pair in pairs:
        name, src = pair.split("=", 1)
        spec = script["art"][name]
        if src.startswith("https://"):
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})  # CDN Algrow : client navigateur
            raw = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=120).read()))
        else:
            raw = Image.open(src)
        size = tuple(map(int, spec.get("size", "256x256").split("x")))
        fit_palette(raw, size, spec.get("keep_bg", False)).save(os.path.join(base, name + ".png"))
        print(f"{name} ok", flush=True)
    review_sheet(base)
    print("ART DONE", flush=True)


def review_sheet(base):
    """Planche des illustrations en grand (pixels ×3) pour vérifier mains, doigts, bras et visages."""
    import glob
    files = sorted(f for f in glob.glob(os.path.join(base, "*.png")) if not f.endswith("_src.png"))
    if not files:
        return
    tiles = []
    for f in files:
        im = Image.open(f).convert("RGBA")
        im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
        bg = Image.new("RGBA", im.size, (3, 4, 7, 255)); bg.alpha_composite(im)
        tiles.append(bg.convert("RGB"))
    cols = 3
    cw, ch = max(t.width for t in tiles), max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * cw, -(-len(tiles) // cols) * ch), (30, 30, 36))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * cw, (i // cols) * ch))
    sheet.save(os.path.join(base, "..", "art_review.jpg"), quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "batch", "prompts", "fit"])
    ap.add_argument("dest", help="gen : image de sortie ; batch, prompts, fit : script.json")
    ap.add_argument("prompt", nargs="*", help="gen : le prompt ; fit : nom=url_ou_fichier …")
    ap.add_argument("--model", default="rd", choices=["rd", "flux"])
    ap.add_argument("--size", default="256x256")
    ap.add_argument("--keep-bg", action="store_true")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    if a.cmd == "batch":
        return batch(a.dest, a.only)
    if a.cmd == "prompts":
        return prompts(a.dest, a.only)
    if a.cmd == "fit":
        return fit(a.dest, a.prompt)
    w, h = map(int, a.size.split("x"))
    print(generate(a.dest, " ".join(a.prompt), a.model, (w, h), a.keep_bg, a.seed))


if __name__ == "__main__":
    sys.exit(main())
