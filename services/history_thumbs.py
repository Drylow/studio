"""Miniatures du format Histoire : l'image (style encre et aquarelle) + 2 lignes de texte incrustées,
comme sur les chaînes du créneau (ligne blanche, ligne rouge, gros contour noir, en haut du côté calme).

Le texte est posé par le code, jamais dessiné par l'IA : il est donc toujours juste et lisible."""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from services.pov_store import APP_DIR

FONT = os.path.join(APP_DIR, "static", "fonts", "Anton-Regular.ttf")
WHITE, RED, INK = (255, 255, 255), (227, 32, 39), (0, 0, 0)
W, H = 1280, 720


def _font(size):
    return ImageFont.truetype(FONT, size)


def _fit(lines, max_w):
    """Taille de police : ~11 % de la largeur (comme la maquette), réduite si une ligne déborde."""
    size = int(W * 0.11)
    while size > 40:
        f = _font(size)
        if all(f.getlength(t) <= max_w for t in lines):
            return f
        size -= 4
    return _font(size)


def compose(image, lines, side="right", dest=None):
    """image : chemin ou PIL.Image ; lines : 1-2 lignes (la dernière en rouge) ; side : côté calme de l'image."""
    im = (Image.open(image) if isinstance(image, str) else image).convert("RGB")
    sw, sh = im.size
    scale = max(W / sw, H / sh)
    im = im.resize((max(W, round(sw * scale)), max(H, round(sh * scale))), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    lines = [str(t).upper().strip() for t in lines if str(t).strip()][:2]
    if not lines:
        return _save(im, dest)
    f = _fit(lines, W * 0.6)
    stroke = max(4, round(f.size * 0.045))
    line_h = round(f.size * 0.98)
    y0 = round(H * 0.06)
    shadow = Image.new("L", (W, H), 0)
    text = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dt = ImageDraw.Draw(shadow), ImageDraw.Draw(text)
    for i, t in enumerate(lines):
        w = f.getlength(t)
        x = W * 0.95 - w if side != "left" else W * 0.05
        y = y0 + i * line_h - f.getbbox(t)[1]
        color = RED if i == len(lines) - 1 and len(lines) > 1 else WHITE
        ds.text((x + stroke * 0.6, y + stroke * 1.2), t, font=f, fill=200, stroke_width=stroke * 2)
        dt.text((x, y), t, font=f, fill=color + (255,), stroke_width=stroke, stroke_fill=INK + (255,))
    im = Image.composite(Image.new("RGB", (W, H), INK), im, shadow.filter(ImageFilter.GaussianBlur(stroke * 1.5)))
    im.paste(text, (0, 0), text)
    return _save(im, dest)


def _save(im, dest):
    if dest:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        im.save(dest, "JPEG", quality=92, optimize=True)
    return im


# ── Style « Dose of History » (oct. 2026) ───────────────────────────────────
# Ce qui marche sur leurs miniatures les plus vues (Little Bighorn 387k, New Orleans 356k, Alamo 205k…) : une
# peinture saturée et dramatique (feu, fumée, drapeaux), un personnage au premier plan qui regarde l'objectif,
# parfois le portrait gravé en noir et blanc d'un acteur clé (médaillon), et UNE ligne de 2-4 mots en Anton
# blanc avec le mot fort en rouge, souvent entre guillemets (« I SAW CUSTER DIE »), grosse ombre portée.

def _vignette_cameo(cameo, h):
    """Portrait en médaillon : noir et blanc, bord ovale fondu (comme une gravure collée sur la scène)."""
    from PIL import ImageOps
    c = (Image.open(cameo) if isinstance(cameo, str) else cameo).convert("L")
    w = round(h * 0.78)
    c = ImageOps.fit(c, (w, h), Image.LANCZOS, centering=(0.5, 0.3))
    c = ImageOps.autocontrast(c, cutoff=1)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([w * 0.06, h * 0.04, w * 0.94, h * 0.96], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(h * 0.035))
    return c.convert("RGB"), mask


def compose_doh(image, text, red=(), corner="top-right", cameo=None, cameo_side="right", quotes=False, dest=None):
    """image : la scène ; text : 2-4 mots (une ligne, deux si trop long) ; red : mots en rouge ;
    corner : top-left|top-right|bottom-left|bottom-right ; cameo : portrait à poser en médaillon (facultatif)."""
    im = (Image.open(image) if isinstance(image, str) else image).convert("RGB")
    sw, sh = im.size
    scale = max(W / sw, H / sh)
    im = im.resize((max(W, round(sw * scale)), max(H, round(sh * scale))), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    from PIL import ImageEnhance
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.18)).enhance(1.08)  # plus vif, comme le créneau
    if cameo:
        ch = round(H * 0.5)
        c, mask = _vignette_cameo(cameo, ch)
        x = W - c.width - round(W * 0.03) if cameo_side == "right" else round(W * 0.03)
        y = round(H * 0.08) if corner.startswith("bottom") else H - ch - round(H * 0.05)
        im.paste(c, (x, y), mask)
    words = [w for w in str(text).upper().split() if w]
    if not words:
        return _save(im, dest)
    reds = {r.upper().strip('"“”') for r in red}
    lines = [words]
    f = _font(int(W * 0.105))
    full = lambda ws: " ".join(ws)  # noqa: E731
    if f.getlength(("“" if quotes else "") + full(words) + ("”" if quotes else "")) > W * 0.9 and len(words) > 1:
        cut = max(1, len(words) // 2)
        lines = [words[:cut], words[cut:]]
    size = int(W * 0.105)
    while size > 40 and any(_font(size).getlength(full(ln) + ("““" if quotes else "")) > W * 0.9 for ln in lines):
        size -= 4
    f = _font(size)
    stroke = max(3, round(size * 0.03))
    line_h = round(size * 1.0)
    top = corner.startswith("top")
    y0 = round(H * 0.04) if top else H - round(H * 0.05) - line_h * len(lines)
    shadow = Image.new("L", (W, H), 0)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dt = ImageDraw.Draw(shadow), ImageDraw.Draw(layer)
    for i, ln in enumerate(lines):
        toks = list(ln)
        if quotes:
            if i == 0:
                toks[0] = "“" + toks[0]
            if i == len(lines) - 1:
                toks[-1] = toks[-1] + "”"
        space = f.getlength(" ")
        width = sum(f.getlength(t) for t in toks) + space * (len(toks) - 1)
        x = W * 0.965 - width if corner.endswith("right") else W * 0.035
        y = y0 + i * line_h - f.getbbox("A")[1]
        for t in toks:
            color = RED if t.strip('"“”,.!?') in reds else WHITE
            ds.text((x + 4, y + 7), t, font=f, fill=235, stroke_width=stroke * 3)
            dt.text((x, y), t, font=f, fill=color + (255,), stroke_width=stroke, stroke_fill=INK + (255,))
            x += f.getlength(t) + space
    im = Image.composite(Image.new("RGB", (W, H), INK), im, shadow.filter(ImageFilter.GaussianBlur(stroke * 3)))
    im.paste(layer, (0, 0), layer)
    return _save(im, dest)
