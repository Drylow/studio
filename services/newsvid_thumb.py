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
import urllib.error
import urllib.parse
import urllib.request

from services import ai

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(REPO, "static", "fonts", "Anton-Regular.ttf")
TW, TH = 1280, 720
# variantes proposées (couleur du trait et des mots mis en avant) ; A = choisie par défaut
VARIANTS = (("A", "accent2"),)  # validée par l'utilisateur : la A (deux photos, citation jaune)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}   # sans langue : Bing renvoie n'importe quoi


def _get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def bing_images(query, n=12):
    """Images (Bing, sans clé) : [{"url", "title", "page"}]."""
    import html as H
    try:
        page = _get("https://www.bing.com/images/async?q=" + urllib.parse.quote(query) +
                    "&first=0&count=35&mmasync=1&setlang=en-US&cc=US").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return []
    out, seen = [], set()
    for raw in re.findall(r'\bm="(\{[^"]*\})"', page):
        try:
            m = json.loads(H.unescape(raw))
        except ValueError:
            continue
        u = m.get("murl") or ""
        if u in seen or not u.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        seen.add(u)
        out.append({"url": u, "title": m.get("t") or "", "page": m.get("purl") or ""})
    return out[:n]


def wiki_images(who):
    """Photo principale de la page Wikipédia (Commons, libre de droits) : Bing renvoie n'importe quoi depuis le cloud
    (4 oct. : « Tyson Fury » → des affiches de film). Réessaie si Wikipédia limite (429)."""
    import time as _t
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(who.replace(" ", "_"))
    for k in range(4):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "DrylowStudio/1.0 (github.com/drylow/studio)"}), timeout=20).read())
            src = (d.get("originalimage") or {}).get("source") or (d.get("thumbnail") or {}).get("source")
            return [{"url": src, "title": f"{who} (Wikipedia)", "page": url}] if src else []
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return []
            _t.sleep(3 * (k + 1))
        except Exception:  # noqa: BLE001
            return []
    return []


def names_ok(who, text, others):
    """Qui est sur la photo ? On ne reconnaît JAMAIS un visage : seul le texte de l'image (adresse, titre,
    page) compte. Gardée si le nom de famille y est et qu'aucune autre personne de l'histoire n'est citée
    avant (« Holloway beats Gaethje » : c'est la photo de Holloway). L'utilisateur valide la planche."""
    t = re.sub(r"[^a-z]+", " ", (text or "").lower())
    last = who.lower().split()[-1]
    if f" {last} " not in f" {t} ":
        return False
    for o in others:
        for part in o.lower().split()[-1:]:  # un autre nom SEUL (sans le nôtre) a déjà été écarté plus haut
            if len(part) > 3 and part not in who.lower().split() and f" {part} " in f" {t} " and \
                    t.find(part) < t.find(last):
                return False  # « Holloway beats Gaethje » : l'autre est cité d'abord, c'est sa photo
    # les photos de combat (deux combattants) sont les plus fortes : gardées, l'utilisateur valide la planche
    return not re.search(r"alamy|gettyimages|shutterstock|dreamstime|istockphoto|depositphotos", (text or "").lower())


_NOT_NAMES = {"ufc", "mma", "white", "house", "freedom", "hall", "fame", "getty", "images", "las", "vegas", "news",
              "fight", "night", "press", "conference", "champion", "title", "lightweight", "featherweight", "results",
              "highlights", "watch", "the", "and", "after", "before", "with", "his", "her", "new", "york", "post",
              "sports", "live", "video", "photo", "photos", "stock", "picture", "pictures", "octagon", "main", "event",
              "weigh", "ins", "card", "world", "championship", "media", "day", "open", "workouts", "official", "fan",
              "fans", "spanish", "spain", "georgia", "georgian", "america", "american", "united", "states", "trump",
              "donald", "dana", "lincoln", "memorial"}


def other_person(who, text):
    """Vrai si le titre de l'image nomme une AUTRE personne (« Gaethje KOs Dustin Poirier »)."""
    mine = {w.lower() for w in who.split()}
    for m in re.finditer(r"\b([A-Z][a-z'’]+)\s+([A-Z][a-z'’]+)\b", text or ""):
        a, b = m.group(1).lower(), m.group(2).lower()
        if a in mine or b in mine or a in _NOT_NAMES or b in _NOT_NAMES:
            continue
        return True
    for m in re.finditer(r"\b(?:KOs?|ko's|knocks? out|beats?|defeats?|stops?|against|faces?|versus|with|over)\s+"
                         r"([A-Z][a-z'’]+)", text or ""):
        w = m.group(1).lower()
        if w not in mine and w not in _NOT_NAMES:
            return True
    return False


def original(url):
    """La plus grande version d'une image : sans les paramètres de redimensionnement (?w=1024, ?resize=…),
    les sites de presse renvoient souvent l'original (Topuria : 1682 px au lieu de 1024)."""
    best, best_px = None, 0
    for u in dict.fromkeys([url.split("?")[0], url]):
        try:
            b = _get(u, 20)
        except Exception:  # noqa: BLE001
            continue
        im = _load(b) if len(b) > 20000 else None
        if im and im.width * im.height > best_px:
            best, best_px = b, im.width * im.height
    return best


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
        from PIL import ImageOps
        im = Image.open(io.BytesIO(blob))
        im.load()
        return ImageOps.exif_transpose(im).convert("RGB")  # photos de téléphone : orientation EXIF
    except Exception:  # noqa: BLE001
        return None


def rate(im, who):
    """Vision : photo utilisable pour la miniature ? → {"ok", "score", "face": [x0, y0, x1, y1] (fractions)}."""
    small = im.copy()
    small.thumbnail((768, 768))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    prompt = (f"This photo is meant to show {who} for a sports news YouTube thumbnail. Answer about the image only. "
              "Find the MAIN person (the largest, sharpest face; other people may be in the image). Return JSON: "
              '{"face": [x0, y0, x1, y1] (that face as fractions of width/height), '
              '"people": how many people have a clearly visible face in the image, '
              '"upright": false if the photo is upside down, sideways, or the main person is upside down, '
              '"clear": true if that face is sharp, not cut off and at least 8% of the image height, '
              '"watermark": true if a stock-agency watermark (Getty, Alamy, Shutterstock, AP…) is printed over the image, '
              '"text": true if big text, a title or a logo is printed over the image (YouTube thumbnail, poster, collage), '
              '"score": 1-10 for a dramatic, expressive thumbnail photo (strong emotion, close framing, good light), '
              '"expression": "angry|smiling|serious|shocked|hurt|other"}')
    content = [{"type": "text", "text": prompt},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                                    base64.b64encode(buf.getvalue()).decode()}}]
    r = None
    for _ in range(3):
        try:
            r = ai.chat_json([{"role": "user", "content": content}], model=ai.fast_model(), timeout=120)
            break
        except Exception:  # noqa: BLE001  (IA saturée : on réessaie)
            continue
    if not r:
        return {"ok": False}
    f = r.get("face")
    if not (isinstance(f, list) and len(f) == 4):
        return {"ok": False}
    try:
        r["face"] = [max(0.0, min(1.0, float(v))) for v in f]
    except (TypeError, ValueError):
        return {"ok": False}
    r["ok"] = r.get("upright", True) is not False and bool(r.get("clear")) and not r.get("watermark") and not r.get("text") and \
        r["face"][2] > r["face"][0] and r["face"][3] > r["face"][1]
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
    others = set(plan.get("people_all") or [])
    try:   # mot du sport dans la recherche (« Jorge Jesus » seul donne des images de Jésus)
        from services import newsvid as N
        kws = N.channel(plan.get("channel") or "").get("photo_kw") or ["UFC", ""]
    except KeyError:
        kws = ["UFC", ""]
    for x in wiki_images(who) + [y for n, k in zip((25, 20), kws) for y in bing_images(f"{who} {k}".strip(), n)] + \
            bing_images(who, 25):
        if not names_ok(who, " ".join((x["url"], x["title"], x["page"])), others - {who}):
            continue
        # jamais une image fabriquée par une IA (craiyon : un faux Ronaldo en maillot du Real, 4 oct.) ni en double
        if re.search(r"craiyon|lexica|openart|nightcafe|midjourney|playground|stablediffusion|artstation|deviantart|"
                     r"aiart|ai-art|generated", (x["url"] + " " + x["page"]).lower()) or \
                x["url"].split("?")[0] in {u.split("?")[0] for u, _ in blobs}:
            continue
        b = original(x["url"])
        if b:
            blobs.append((x["url"], b))
    ims = [(src, _load(b)) for src, b in blobs]
    ims = [(src, im) for src, im in ims if im and min(im.size) >= 360]

    def one(x):
        return x[0], x[1], rate(x[1], who)
    with ThreadPoolExecutor(max_workers=6) as ex:
        rated = list(ex.map(one, ims))
    def sharp(im, r):  # le cadrage de la miniature (visage × 2,6 sur 720 px de haut) sans agrandir plus de 1,25×
        return (r["face"][3] - r["face"][1]) * im.height * 2.6 >= TH / 1.25
    # photo à plusieurs combattants : la vision peut prendre le mauvais visage (Oliveira pris pour Tsarukyan, 3 oct.)
    good = [(src, im, r) for src, im, r in rated if r.get("ok") and sharp(im, r) and int(r.get("people") or 1) <= 2]
    good.sort(key=lambda x: (int(x[2].get("people") or 1) > 1, -float(x[2].get("score") or 0)))
    log(f"{who} : {len(good)}/{len(rated)} photos utilisables")
    return good


def cached_candidates(job_dir, plan, who, log=print):
    """Photos retenues gardées dans <dossier>/photos/ (refaire une miniature ne relance ni recherche ni vision)."""
    from PIL import Image
    d = os.path.join(job_dir, "photos")
    idx = os.path.join(d, "photos.json")
    cache = {}
    if os.path.isfile(idx):
        with open(idx, "r", encoding="utf-8") as f:
            cache = json.load(f)
    if cache.get(who):
        return [(x["src"], Image.open(os.path.join(d, x["file"])).convert("RGB"), x["rate"]) for x in cache[who]]
    good = candidates(job_dir, plan, who, log)
    os.makedirs(d, exist_ok=True)
    rows = []
    for k, (src, im, r) in enumerate(good[:4]):
        fn = f"{re.sub(r'[^a-z0-9]+', '_', who.lower())}_{k}.jpg"
        im.save(os.path.join(d, fn), quality=92)
        rows.append({"src": src, "file": fn, "rate": r})
    if rows:
        cache[who] = rows
        with open(idx, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1)
    return [(x["src"], Image.open(os.path.join(d, x["file"])).convert("RGB"), x["rate"]) for x in rows]


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
    lines = [words] if len(" ".join(words)) <= 10 else None  # au-delà : 2 lignes, plus gros et plus haut
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
    sw = max(6, size // 16)
    # vraie taille des lettres (Anton dépasse sa ligne : avant, le bas du texte sortait de l'image)
    boxes = [d.textbbox((0, 0), " ".join(ln), font=f, stroke_width=sw) for ln in lines]
    gap = size * 0.06
    total = sum(b[3] - b[1] for b in boxes) + gap * (len(lines) - 1)
    y = y_bottom - total
    for ln, b in zip(lines, boxes):
        x = (TW - d.textlength(" ".join(ln), font=f)) / 2
        for w in ln:
            col = accent if w.strip(".,!?\"'“”") in hl else (255, 255, 255)
            d.text((x, y - b[1]), w, font=f, fill=col, stroke_width=sw, stroke_fill=(0, 0, 0))
            x += d.textlength(w + " ", font=f)
        y += (b[3] - b[1]) + gap


def _split(canvas, left, right, accent, zigzag=False):
    """Deux photos face à face, séparées par un trait penché (ou un éclair en zigzag) à la couleur de la chaîne."""
    from PIL import Image, ImageDraw
    half = TW // 2 + 60
    a = _grade(crop_face(left[0], left[1], half, TH))
    b = _grade(crop_face(right[0], right[1], half, TH))
    canvas.paste(a, (0, 0))
    if zigzag:
        xs = [TW // 2 + 50, TW // 2 - 30, TW // 2 + 40, TW // 2 - 40, TW // 2 + 30, TW // 2 - 50]
        pts = [(xs[k], k * TH / (len(xs) - 1)) for k in range(len(xs))]
    else:
        pts = [(TW // 2 + 40, 0), (TW // 2 - 40, TH)]
    mask = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(mask).polygon(pts + [(TW, TH), (TW, 0)], fill=255)
    layer = Image.new("RGB", (TW, TH))
    layer.paste(b, (TW - half, 0))
    canvas = Image.composite(layer, canvas, mask)
    d = ImageDraw.Draw(canvas)
    d.line(pts, fill=(0, 0, 0), width=22, joint="curve")
    d.line(pts, fill=accent, width=12, joint="curve")
    return canvas


def _ring_inset(canvas, inset, ring=(255, 210, 31)):
    """Signature « cible » : la photo du combat dans un rond, gros anneau jaune et contour noir."""
    from PIL import Image, ImageDraw
    r = 150
    cx, cy = TW // 2, 40 + r
    im = _grade(crop_face(inset[0], inset[1], 2 * r, 2 * r, zoom=2.0))
    m = Image.new("L", (2 * r, 2 * r), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    d = ImageDraw.Draw(canvas)
    d.ellipse((cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20), fill=(0, 0, 0))
    d.ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=ring)
    canvas.paste(im, (cx - r, cy - r), m)
    return canvas


def _tape(canvas, brand, color=(255, 210, 31)):
    """Signature « ruban » : bande jaune penchée en haut à gauche avec le nom de la chaîne."""
    from PIL import Image, ImageDraw, ImageFont
    band = Image.new("RGBA", (900, 92), color + (255,))
    d = ImageDraw.Draw(band)
    f = ImageFont.truetype(FONT, 58)
    word = (brand or "NEWS").upper() + "  •  "
    x = 0
    while x < band.width:
        d.text((x, 10), word, font=f, fill=(0, 0, 0))
        x += d.textlength(word, font=f)
    d.rectangle((0, 0, band.width - 1, 6), fill=(0, 0, 0))
    d.rectangle((0, band.height - 7, band.width - 1, band.height - 1), fill=(0, 0, 0))
    band = band.rotate(17, expand=True, resample=Image.BICUBIC)
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(band, (-170, -60))
    return canvas.convert("RGB")


def compose(left, right, text, highlight, accent, inset=None, variant="A", brand=""):
    """A = deux photos face à face ; B = + photo encadrée (façon concurrent) ; C = un seul visage géant ;
    D = + photo du combat dans un rond jaune (notre signature) ; E = ruban jaune avec le nom de la chaîne ;
    F = séparation en éclair + rond jaune."""
    if variant in ("D", "E", "F"):
        from PIL import Image
        canvas = _split(Image.new("RGB", (TW, TH), (8, 8, 10)), left, right, accent, zigzag=variant == "F")
        canvas = _finish(canvas, accent)
        if variant in ("D", "F") and inset is not None:
            canvas = _ring_inset(canvas, inset)
        if variant == "E":
            canvas = _tape(canvas, brand)
        _text_block(canvas, text, highlight, accent, TH - 52, TW - 90)
        return canvas
    from PIL import Image, ImageDraw
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
    canvas = _finish(canvas, accent)
    if variant == "B" and inset is not None:
        iw, ih = 360, 250
        im = _grade(crop_face(inset[0], inset[1], iw, ih, zoom=2.2))
        x0, y0 = (TW - iw) // 2, 34
        d = ImageDraw.Draw(canvas)
        d.rectangle((x0 - 8, y0 - 8, x0 + iw + 7, y0 + ih + 7), fill=(30, 220, 60))
        canvas.paste(im, (x0, y0))
    _text_block(canvas, text, highlight, accent, TH - 52, TW - 90)
    return canvas


def _finish(canvas, accent):
    """Ombre en bas (lisibilité de la citation) + lueur de la couleur de la chaîne sur les bords."""
    from PIL import Image, ImageDraw, ImageFilter
    grad = Image.new("L", (1, TH))
    for y in range(TH):
        grad.putpixel((0, y), int(255 * max(0.0, (y - TH * 0.38) / (TH * 0.62)) ** 1.3))
    shade = Image.new("RGB", (TW, TH), (0, 0, 0))
    canvas = Image.composite(shade, canvas, grad.resize((TW, TH)).point(lambda v: int(v * 0.88)))
    # liseré rouge sur les bords (lueur)
    glow = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(glow).rectangle((0, 0, TW - 1, TH - 1), outline=255, width=26)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    return Image.composite(Image.new("RGB", (TW, TH), accent), canvas, glow.point(lambda v: int(v * 0.6)))


def make(job_dir, log=print):
    from PIL import Image
    with open(os.path.join(job_dir, "plan.json"), "r", encoding="utf-8") as f:
        plan = json.load(f)
    th = plan.get("thumb") or {}
    people = (th.get("people") or [])[:2]
    if len(people) < 2:
        raise RuntimeError("thumb.people : il faut deux personnes")
    from services import newsvid as N
    try:
        tacc = N.channel(plan.get("channel") or "").get("thumb_accent")
    except (KeyError, ValueError, SystemExit):
        tacc = None
    # couleur de la chaîne (l'utilisateur, 3 oct. : « bleu clair dans le thème de @CageDispatch »)
    accent = tuple(int((tacc or plan.get("accent2") or "#FFD21F").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    red = tuple(int((plan.get("accent") or "#E10600").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    names = set(people) | {s.get("speaker") for s in plan["segments"] if s.get("speaker")} | \
        {v for v in (plan.get("spelling") or {}).values() if len(v.split()) >= 2}
    plan = dict(plan, people_all=sorted(n for n in names if n))
    pics = {p: cached_candidates(job_dir, plan, p, log) for p in people}
    for p in people:
        if not pics[p]:
            raise RuntimeError(f"aucune photo utilisable de {p}")
    A, B = pics[people[0]], pics[people[1]]
    left, right = (A[0][1], A[0][2]["face"]), (B[0][1], B[0][2]["face"])
    inset = (B[1][1], B[1][2]["face"]) if len(B) > 1 else (A[1][1], A[1][2]["face"]) if len(A) > 1 else None
    text, hl = th.get("text") or "", th.get("highlight") or ""
    if text and not text.startswith(("“", '"')):
        text = f"“{text}”"   # c'est une citation : entre guillemets (l'utilisateur, 3 oct.)
    out = []
    for v, col in VARIANTS:
        col = accent if col == "accent2" else red
        im = compose(left, right, text, hl, col, inset=inset, variant=v, brand=plan.get("brand") or "")
        path = os.path.join(job_dir, f"thumb_{v}.jpg")
        im.save(path, quality=90)
        out.append(path)
    sheet = Image.new("RGB", (TW + 10, TH + 10), (255, 255, 255))
    for k, p in enumerate(out[:4]):
        sheet.paste(Image.open(p).resize((TW // 2, TH // 2)), ((k % 2) * (TW // 2 + 10), (k // 2) * (TH // 2 + 10)))
    sheet.save(os.path.join(job_dir, "thumbs.jpg"), quality=85)
    log("miniatures :", ", ".join(os.path.basename(p) for p in out))
    return out
