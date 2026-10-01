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
