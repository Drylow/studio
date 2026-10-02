"""Miniatures des vidéos d'actu sport (façon Fight Night MMA) : vraies photos des deux personnes de
l'histoire, face à face, et une énorme citation (vraiment dite dans la vidéo) en blanc + couleur.

Photos : miniatures des vidéos sources où la personne parle (i.ytimg.com) + recherche d'images Bing ;
l'IA en vision note chaque photo (une seule personne bien visible, net, pas de texte ni de filigrane)
et donne la boîte du visage pour cadrer. Tout le montage de la miniature est fait par le code.

  make(job_dir) → thumb_A.jpg, thumb_B.jpg, thumb_C.jpg + thumbs.jpg (planche) ; le choix → thumb.jpg
"""
import base64
import io
import json
import os
import re
import urllib.parse
import urllib.request

from services import ai

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(REPO, "static", "fonts", "Anton-Regular.ttf")
TW, TH = 1280, 720
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0 Safari/537.36"}


def _get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def bing_images(query, n=12):
    """URLs d'images (Bing, sans clé)."""
    try:
        html = _get("https://www.bing.com/images/async?q=" + urllib.parse.quote(query) +
                    "&first=0&count=35&mmasync=1").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return []
    urls = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
    return [u for u in dict.fromkeys(urls) if u.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp"))][:n]


def yt_thumb(video_id):
    for q in ("maxresdefault", "hqdefault"):
        try:
            b = _get(f"https://i.ytimg.com/vi/{video_id}/{q}.jpg")
            if len(b) > 5000:
                return b
        except Exception:  # noqa: BLE001
            continue
    return None


def _load(blob):
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(blob))
        im.load()
        return im.convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def rate(im, who):
    """Vision : photo utilisable pour la miniature ? → {"ok", "score", "face": [x0, y0, x1, y1] (fractions)}."""
    small = im.copy()
    small.thumbnail((768, 768))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    prompt = (f"This photo is meant to show {who} for a sports news YouTube thumbnail. Answer about the image only. "
              "Is there ONE main person, clearly visible, face large enough and sharp (not tiny, not blurry, not cut "
              "off), with NO big text, logo overlay, watermark (Getty, Alamy, Shutterstock…), collage or split screen? "
              "Give the face box of that main person as fractions of the width/height. Score 1-10 for a dramatic, "
              "expressive thumbnail photo (strong emotion, close framing, good light = high). Return JSON "
              '{"ok": true|false, "score": n, "face": [x0, y0, x1, y1], "expression": "angry|smiling|serious|shocked|hurt|other"}')
    content = [{"type": "text", "text": prompt},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                                    base64.b64encode(buf.getvalue()).decode()}}]
    try:
        r = ai.chat_json([{"role": "user", "content": content}], model=ai.fast_model(), timeout=120)
    except Exception:  # noqa: BLE001
        return {"ok": False}
    f = r.get("face")
    if not (isinstance(f, list) and len(f) == 4):
        return {"ok": False}
    try:
        r["face"] = [max(0.0, min(1.0, float(v))) for v in f]
    except (TypeError, ValueError):
        return {"ok": False}
    return r


def candidates(job_dir, plan, who, log=print):
    """Photos notées de `who` (miniatures des vidéos où il parle d'abord, puis Bing), meilleures d'abord."""
    from concurrent.futures import ThreadPoolExecutor
    blobs = []
    vids = [s["video"] for s in plan["segments"] if s["type"] == "clip" and (s.get("speaker") or "").lower() == who.lower()]
    for v in list(dict.fromkeys(vids))[:4]:
        b = yt_thumb(v)
        if b:
            blobs.append(("yt:" + v, b))
    for u in bing_images(f"{who} UFC", 10) + bing_images(f"{who} face off", 6):
        try:
            b = _get(u, 15)
            if len(b) > 20000:
                blobs.append((u, b))
        except Exception:  # noqa: BLE001
            continue
    ims = [(src, _load(b)) for src, b in blobs]
    ims = [(src, im) for src, im in ims if im and min(im.size) >= 360]

    def one(x):
        return x[0], x[1], rate(x[1], who)
    with ThreadPoolExecutor(max_workers=6) as ex:
        rated = list(ex.map(one, ims))
    good = [(src, im, r) for src, im, r in rated if r.get("ok")]
    good.sort(key=lambda x: -float(x[2].get("score") or 0))
    log(f"{who} : {len(good)}/{len(rated)} photos utilisables")
    return good


def crop_face(im, face, w, h, zoom=2.6, top=0.32):
    """Cadre w×h centré sur le visage (le visage fait ~1/zoom de la hauteur, yeux vers le tiers haut)."""
    from PIL import Image
    W, H = im.size
    fx0, fy0, fx1, fy1 = face[0] * W, face[1] * H, face[2] * W, face[3] * H
    fh = max(20.0, fy1 - fy0)
    ch = min(H, fh * zoom)
    cw = ch * w / h
    if cw > W:
        cw = W
        ch = cw * h / w
    cx, cy = (fx0 + fx1) / 2, fy0 + fh * 0.5
    x0 = min(max(0.0, cx - cw / 2), W - cw)
    y0 = min(max(0.0, cy - ch * top), H - ch)
    return im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.LANCZOS)


def _grade(im):
    from PIL import ImageEnhance
    im = ImageEnhance.Contrast(im).enhance(1.18)
    im = ImageEnhance.Color(im).enhance(1.15)
    return ImageEnhance.Sharpness(im).enhance(1.3)


def _text_block(canvas, text, highlight, accent, y_bottom, max_w):
    """Citation énorme sur 1-2 lignes, blanche, mots mis en avant en couleur, contour noir épais."""
    from PIL import ImageDraw, ImageFont
    words = text.upper().split()
    hl = {w.strip(".,!?\"'“”").upper() for w in re.findall(r"\S+", highlight or "")}
    lines = [words] if len(" ".join(words)) <= 16 else None
    if not lines:
        best = None
        for k in range(1, len(words)):
            a, b = " ".join(words[:k]), " ".join(words[k:])
            score = abs(len(a) - len(b))
            if best is None or score < best[0]:
                best = (score, [words[:k], words[k:]])
        lines = best[1]
    d = ImageDraw.Draw(canvas)
    size = 190
    while size > 60:
        f = ImageFont.truetype(FONT, size)
        if all(d.textlength(" ".join(ln), font=f) <= max_w for ln in lines) and size * 1.02 * len(lines) <= 330:
            break
        size -= 4
    f = ImageFont.truetype(FONT, size)
    lh = size * 1.02
    y = y_bottom - lh * len(lines)
    for ln in lines:
        x = (TW - d.textlength(" ".join(ln), font=f)) / 2
        for w in ln:
            col = accent if w.strip(".,!?\"'“”") in hl else (255, 255, 255)
            d.text((x, y), w, font=f, fill=col, stroke_width=max(6, size // 16), stroke_fill=(0, 0, 0))
            x += d.textlength(w + " ", font=f)
        y += lh


def compose(left, right, text, highlight, accent, inset=None, variant="A"):
    """A = deux photos face à face ; B = deux photos + photo encadrée au centre ; C = un seul visage géant."""
    from PIL import Image, ImageDraw, ImageFilter
    canvas = Image.new("RGB", (TW, TH), (8, 8, 10))
    if variant == "C":
        canvas.paste(_grade(crop_face(left[0], left[1], TW, TH, zoom=1.9, top=0.28)), (0, 0))
    else:
        half = TW // 2 + 60
        a = _grade(crop_face(left[0], left[1], half, TH))
        b = _grade(crop_face(right[0], right[1], half, TH))
        canvas.paste(a, (0, 0))
        mask = Image.new("L", (TW, TH), 0)
        ImageDraw.Draw(mask).polygon([(TW // 2 + 40, 0), (TW, 0), (TW, TH), (TW // 2 - 40, TH)], fill=255)
        layer = Image.new("RGB", (TW, TH))
        layer.paste(b, (TW - half, 0))
        canvas = Image.composite(layer, canvas, mask)
        d = ImageDraw.Draw(canvas)
        d.line([(TW // 2 + 40, 0), (TW // 2 - 40, TH)], fill=accent, width=10)
    # ombre en bas pour la citation
    grad = Image.new("L", (1, TH))
    for y in range(TH):
        grad.putpixel((0, y), int(255 * max(0.0, (y - TH * 0.38) / (TH * 0.62)) ** 1.3))
    shade = Image.new("RGB", (TW, TH), (0, 0, 0))
    canvas = Image.composite(shade, canvas, grad.resize((TW, TH)).point(lambda v: int(v * 0.88)))
    # liseré rouge sur les bords (lueur)
    glow = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(glow).rectangle((0, 0, TW - 1, TH - 1), outline=255, width=26)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.composite(Image.new("RGB", (TW, TH), accent), canvas, glow.point(lambda v: int(v * 0.6)))
    if variant == "B" and inset is not None:
        iw, ih = 360, 250
        im = _grade(crop_face(inset[0], inset[1], iw, ih, zoom=2.2))
        x0, y0 = (TW - iw) // 2, 34
        d = ImageDraw.Draw(canvas)
        d.rectangle((x0 - 8, y0 - 8, x0 + iw + 7, y0 + ih + 7), fill=(30, 220, 60))
        canvas.paste(im, (x0, y0))
    _text_block(canvas, text, highlight, accent, TH - 26, TW - 90)
    return canvas


def make(job_dir, log=print):
    from PIL import Image
    with open(os.path.join(job_dir, "plan.json"), "r", encoding="utf-8") as f:
        plan = json.load(f)
    th = plan.get("thumb") or {}
    people = (th.get("people") or [])[:2]
    if len(people) < 2:
        raise RuntimeError("thumb.people : il faut deux personnes")
    accent = tuple(int((plan.get("accent2") or "#FFD21F").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    red = tuple(int((plan.get("accent") or "#E10600").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    pics = {p: candidates(job_dir, plan, p, log) for p in people}
    for p in people:
        if not pics[p]:
            raise RuntimeError(f"aucune photo utilisable de {p}")
    A, B = pics[people[0]], pics[people[1]]
    left, right = (A[0][1], A[0][2]["face"]), (B[0][1], B[0][2]["face"])
    inset = (B[1][1], B[1][2]["face"]) if len(B) > 1 else (A[1][1], A[1][2]["face"]) if len(A) > 1 else None
    text, hl = th.get("text") or "", th.get("highlight") or ""
    out = []
    for v, col in (("A", accent), ("B", red), ("C", accent)):
        im = compose(left, right, text, hl, col, inset=inset, variant=v)
        path = os.path.join(job_dir, f"thumb_{v}.jpg")
        im.save(path, quality=90)
        out.append(path)
    sheet = Image.new("RGB", (TW * 3 // 2 + 20, TH // 2), (255, 255, 255))
    for k, p in enumerate(out):
        sheet.paste(Image.open(p).resize((TW // 2, TH // 2)), (k * (TW // 2 + 10), 0))
    sheet.save(os.path.join(job_dir, "thumbs.jpg"), quality=85)
    log("miniatures :", ", ".join(os.path.basename(p) for p in out))
    return out
