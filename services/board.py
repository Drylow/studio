"""Mise en page « tableau » (façon Marcus Explains) : fond quadrillé + panneau + présentateur.

    ┌──────────────────────────────────────┐
    │ ░░░░░░░░ fond quadrillé ░░░░░░░░░░░░ │
    │ ░░ ┌────────────────────────────┐ ░░ │
    │ ░░ │  illustration de la scène  │ ░░ │
    │ ░░ │   (zoom lent à l'intérieur) │ ░░ │
    │ ☺╱ │                            │ ░░ │
    │ █  └────────────────────────────┘ ░░ │
    └──────────────────────────────────────┘
      └ présentateur (PNG transparent), en bas à gauche, qui déborde sur le panneau

Le fond est généré par Pillow (aucune IA), le présentateur est un PNG détouré
stocké dans la chaîne. Les proportions sont relevées sur les vidéos de référence :
panneau 16:9 à 85 % de la largeur, centré ; présentateur ≈ 37 % de la hauteur.
"""
import io
import os

DEFAULT_BOARD = {
    "enabled": False,
    "theme": "cream_graph",
    "bg_color": "#F3EAD3",      # papier crème
    "line_color": "#E4D5AE",    # lignes fines
    "major_color": "#D3BC86",   # lignes fortes (papier millimétré)
    "pattern": "graph",         # grid | graph | dots | chalk | plain
    "cell": 30,                 # taille d'une case à 1080p
    "major_every": 5,
    "paper": True,              # léger grain de papier
    "panel_width": 0.85,        # largeur du panneau (fraction de l'image)
    "border": 6,                # contour du panneau (px à 1080p)
    "border_color": "#111111",
    "radius": 16,               # coins arrondis
    "shadow": "hard",           # none | hard (ombre décalée façon BD) | soft
    "shadow_color": "#111111",
    "shadow_offset": 12,
    "presenter": None,          # chemin relatif (refs/...) de l'image de base détourée
    "rig": None,                # dossier relatif du rig animé (refs/rig_*/)
    "presenter_height": 0.40,   # hauteur du présentateur (fraction de la hauteur)
    "presenter_x": 0.004,       # marge gauche
    "bob": False,               # mouvement vertical (désactivé : donnait l'impression qu'il lévite)
    "animate": True,            # prof animé (voir "anim")
    "anim": "poses",            # poses = gestes de baguette (bras redessiné par l'IA) · none = image fixe
    "presenter_outline": 0,     # contour « sticker » autour du prof (px à 1080p, 0 = aucun)
    "outline_color": "#FFFFFF",
    "spot": 0.0,                # halo lumineux derrière le prof (0 à 1) — utile sur fond sombre
    "spot_color": "#FFFFFF",
    "mascot": "",
}

# Thèmes prêts à l'emploi (sélecteur de l'UI) — aucun ne reprend le bleu de la référence.
THEMES = {
    "cream_graph": {"name": "Papier millimétré crème", "bg_color": "#F3EAD3", "line_color": "#E4D5AE",
                    "major_color": "#D3BC86", "pattern": "graph", "cell": 30, "major_every": 5, "paper": True,
                    "border": 6, "border_color": "#111111", "radius": 16, "shadow": "hard",
                    "shadow_color": "#111111", "shadow_offset": 12},
    "yellow_grid": {"name": "Cahier jaune", "bg_color": "#FFD447", "line_color": "#F5C125",
                    "major_color": "#EAB210", "pattern": "grid", "cell": 44, "major_every": 0, "paper": True,
                    "border": 6, "border_color": "#111111", "radius": 16, "shadow": "hard",
                    "shadow_color": "#111111", "shadow_offset": 12},
    "orange_dots": {"name": "Pois orange", "bg_color": "#FF7A33", "line_color": "#FFA06B",
                    "major_color": "#FFA06B", "pattern": "dots", "cell": 40, "major_every": 0, "paper": False,
                    "border": 8, "border_color": "#FFFFFF", "radius": 22, "shadow": "soft",
                    "shadow_color": "#7A2E00", "shadow_offset": 10},
    "chalkboard": {"name": "Tableau à craie", "bg_color": "#2F4A3E", "line_color": "#3C5A4C",
                   "major_color": "#45665A", "pattern": "chalk", "cell": 54, "major_every": 0, "paper": True,
                   "border": 7, "border_color": "#F4F1E8", "radius": 10, "shadow": "soft",
                   "shadow_color": "#0E1A15", "shadow_offset": 10},
    "mint_graph": {"name": "Millimétré menthe", "bg_color": "#D5EEDD", "line_color": "#BCE0C8",
                   "major_color": "#98CCAA", "pattern": "graph", "cell": 30, "major_every": 5, "paper": True,
                   "border": 6, "border_color": "#111111", "radius": 16, "shadow": "hard",
                   "shadow_color": "#111111", "shadow_offset": 12},
    "graphite": {"name": "Graphite (sombre) + jaune", "bg_color": "#222226", "line_color": "#303036",
                 "major_color": "#46464E", "pattern": "graph", "cell": 30, "major_every": 5, "paper": True,
                 "border": 6, "border_color": "#FFD447", "radius": 16, "shadow": "hard",
                 "shadow_color": "#000000", "shadow_offset": 12, "presenter_outline": 0,
                 "outline_color": "#FFFFFF", "spot": 0.0, "spot_color": "#FFFFFF"},
    "black_yellow": {"name": "Noir + quadrillage jaune", "bg_color": "#121212", "line_color": "#29240F",
                     "major_color": "#3A3213", "pattern": "grid", "cell": 44, "major_every": 0, "paper": True,
                     "border": 6, "border_color": "#FFD447", "radius": 16, "shadow": "hard",
                     "shadow_color": "#FFD447", "shadow_offset": 10, "presenter_outline": 0,
                 "outline_color": "#FFFFFF", "spot": 0.0, "spot_color": "#FFFFFF"},
    "slate": {"name": "Ardoise bleu nuit", "bg_color": "#1E2530", "line_color": "#2C3542", "major_color": "#2C3542",
              "pattern": "dots", "cell": 40, "major_every": 0, "paper": True, "border": 6,
              "border_color": "#FFFFFF", "radius": 18, "shadow": "soft", "shadow_color": "#000000",
              "shadow_offset": 12, "presenter_outline": 0, "outline_color": "#FFFFFF", "spot": 0.0,
              "spot_color": "#9FC4FF"},
    "blue_grid": {"name": "Plan bleu (classique)", "bg_color": "#08A8E6", "line_color": "#7DEAFF",
                  "major_color": "#7DEAFF", "pattern": "grid", "cell": 48, "major_every": 0, "paper": False,
                  "border": 4, "border_color": "#FFFFFF", "radius": 0, "shadow": "none",
                  "shadow_color": "#000000", "shadow_offset": 0},
}

def _rgb(hex_color, default=(255, 255, 255)):
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return default
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def _even(v):
    v = int(round(v))
    return v - (v % 2)


def geometry(board, width=1920, height=1080):
    """Position du panneau et du présentateur pour une taille de vidéo donnée."""
    k = height / 1080.0
    pw = _even(width * max(0.5, min(0.95, float(board.get("panel_width") or 0.85))))
    ph = _even(pw * 9 / 16)
    if ph > height - 40 * k:  # sécurité (formats non 16:9)
        ph = _even(height - 40 * k)
        pw = _even(ph * 16 / 9)
    px, py = _even((width - pw) / 2), _even((height - ph) / 2)
    pres_h = _even(height * max(0.15, min(0.6, float(board.get("presenter_height") or 0.4))))
    pres_x = _even(width * max(0.0, min(0.3, float(board.get("presenter_x") or 0.0))))
    pres_bottom = height - _even(4 * k)
    return {"panel": (px, py, pw, ph), "presenter_h": pres_h, "presenter_x": pres_x,
            "presenter_bottom": pres_bottom, "border": max(0, int(round(float(board.get("border") or 0) * k))),
            "radius": max(0, int(round(float(board.get("radius") or 0) * k))),
            "shadow_offset": max(0, int(round(float(board.get("shadow_offset") or 0) * k)))}


def _pattern(im, board, k):
    from PIL import ImageDraw
    w, h = im.size
    d = ImageDraw.Draw(im)
    pattern = board.get("pattern") or "grid"
    cell = max(8, int(round(float(board.get("cell") or 40) * k)))
    line = _rgb(board.get("line_color"), (200, 200, 200))
    major = _rgb(board.get("major_color") or board.get("line_color"), line)
    every = int(board.get("major_every") or 0)
    ox, oy = (w % cell) // 2, (h % cell) // 2
    if pattern == "dots":
        r = max(2, int(round(3.2 * k)))
        for y in range(oy, h + 1, cell):
            for x in range(ox, w + 1, cell):
                d.ellipse([x - r, y - r, x + r, y + r], fill=line)
        return
    if pattern == "plain":
        return
    thin = max(1, int(round((1.6 if pattern == "graph" else 3) * k)))
    thick = max(thin + 1, int(round(3.2 * k)))
    if pattern == "chalk":
        thin = max(1, int(round(2 * k)))
    for i, x in enumerate(range(ox, w + 1, cell)):
        big = every and i % every == 0
        lw = thick if big else thin
        d.rectangle([x - lw // 2, 0, x - lw // 2 + lw - 1, h], fill=major if big else line)
    for i, y in enumerate(range(oy, h + 1, cell)):
        big = every and i % every == 0
        lw = thick if big else thin
        d.rectangle([0, y - lw // 2, w, y - lw // 2 + lw - 1], fill=major if big else line)


def _texture(im, board, k):
    """Grain de papier / poussière de craie (déterministe)."""
    from PIL import Image, ImageChops, ImageFilter
    import random
    w, h = im.size
    rnd = random.Random(42)
    small = Image.new("L", (max(8, w // 6), max(8, h // 6)))
    small.putdata([rnd.randint(0, 255) for _ in range(small.width * small.height)])
    noise = small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2 * k))
    amp = 22 if board.get("pattern") == "chalk" else 12
    noise = noise.point(lambda p: 128 + (p - 128) * amp // 128)
    rgb = Image.merge("RGB", (noise, noise, noise))
    return ImageChops.overlay(im, rgb)


def make_background(board, dest, width=1920, height=1080):
    """Fond (motif + ombre du panneau) → PNG. Le panneau est recouvert ensuite par la scène."""
    from PIL import Image, ImageDraw, ImageFilter
    k = height / 1080.0
    g = geometry(board, width, height)
    im = Image.new("RGB", (width, height), _rgb(board.get("bg_color"), (243, 234, 211)))
    _pattern(im, board, k)
    if board.get("paper"):
        im = _texture(im, board, k)
    spot = float(board.get("spot") or 0)
    if spot > 0:  # halo derrière le prof (le détache d'un fond sombre)
        cx = g["presenter_x"] + g["presenter_h"] * 0.3
        cy = g["presenter_bottom"] - g["presenter_h"] * 0.5
        rad = g["presenter_h"] * 0.85
        layer = Image.new("L", (width, height), 0)
        ImageDraw.Draw(layer).ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=int(255 * min(1.0, spot)))
        layer = layer.filter(ImageFilter.GaussianBlur(rad * 0.45))
        im = Image.composite(Image.new("RGB", (width, height), _rgb(board.get("spot_color"))), im, layer)
    px, py, pw, ph = g["panel"]
    b, r, off = g["border"], g["radius"], g["shadow_offset"]
    shadow = board.get("shadow") or "none"
    if shadow != "none" and off:
        sc = _rgb(board.get("shadow_color"), (17, 17, 17))
        box = [px - b + off, py - b + off, px + pw + b - 1 + off, py + ph + b - 1 + off]
        if shadow == "hard":
            ImageDraw.Draw(im).rounded_rectangle(box, radius=r + b, fill=sc)
        else:
            layer = Image.new("L", (width, height), 0)
            ImageDraw.Draw(layer).rounded_rectangle(box, radius=r + b, fill=150)
            layer = layer.filter(ImageFilter.GaussianBlur(max(4, off)))
            im = Image.composite(Image.new("RGB", (width, height), sc), im, layer)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    im.save(dest, "PNG")
    return dest


def make_frame(board, bg_path, dest, width=1920, height=1080):
    """Calque posé PAR-DESSUS le panneau : contour + coins arrondis (le fond réapparaît aux coins).

    Transparent partout ailleurs → l'image de la scène reste visible à l'intérieur."""
    from PIL import Image, ImageDraw
    g = geometry(board, width, height)
    px, py, pw, ph = g["panel"]
    b, r = g["border"], g["radius"]
    bg = Image.open(bg_path).convert("RGBA")
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if r:  # coins : on remet le fond là où le panneau rectangulaire déborde de l'arrondi
        corner = Image.new("L", (width, height), 0)
        dc = ImageDraw.Draw(corner)
        dc.rectangle([px, py, px + pw - 1, py + ph - 1], fill=255)
        dc.rounded_rectangle([px, py, px + pw - 1, py + ph - 1], radius=r, fill=0)
        out.paste(bg, (0, 0), corner)
    if b:
        d = ImageDraw.Draw(out)
        d.rounded_rectangle([px - b, py - b, px + pw + b - 1, py + ph + b - 1], radius=r + b if r else 0,
                            outline=_rgb(board.get("border_color")) + (255,), width=b)
    out.save(dest, "PNG")
    return dest


def cutout(blob, tolerance=38):
    """PNG du présentateur → RGBA détouré et recadré au plus juste.

    Si l'IA a déjà rendu un fond transparent, on recadre simplement. Sinon on retire
    le fond uni par remplissage depuis les bords (les zones de même couleur À L'INTÉRIEUR
    du perso, entourées par son contour noir, sont conservées)."""
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(blob)).convert("RGBA")
    alpha = im.getchannel("A")
    lo, _ = alpha.getextrema()
    if lo > 250:  # opaque → détourage du fond uni
        rgb = im.convert("RGB")
        w, h = rgb.size
        mask = Image.new("L", (w, h), 0)
        seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2), (w - 1, h // 2)]
        work = rgb.copy()
        marker = (255, 0, 254)
        from PIL import ImageDraw
        for s in seeds:
            if work.getpixel(s) != marker:
                ImageDraw.floodfill(work, s, marker, thresh=tolerance)
        px_w, px_m = work.load(), mask.load()
        for y in range(h):
            for x in range(w):
                if px_w[x, y] != marker:
                    px_m[x, y] = 255
        mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
        im.putalpha(mask)
    else:
        # nettoie le halo semi-transparent éventuel
        im.putalpha(alpha.point(lambda a: 0 if a < 12 else a))
    bbox = im.getchannel("A").getbbox()
    if bbox:
        im = im.crop(bbox)
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


def outline(im, width, color="#FFFFFF"):
    """Contour « sticker » autour d'un PNG détouré (même taille d'image, marges ajoutées)."""
    from PIL import Image, ImageFilter
    width = int(width)
    if width <= 0:
        return im
    pad = width + 2
    src = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    src.paste(im, (pad, pad))
    a = src.getchannel("A").point(lambda v: 255 if v > 60 else 0)
    grown = a.filter(ImageFilter.MaxFilter(2 * width + 1)).filter(ImageFilter.GaussianBlur(0.8))
    out = Image.new("RGBA", src.size, _rgb(color) + (0,))
    out.putalpha(grown)
    out.alpha_composite(src)
    return out


def compose_still(board, scene_image, presenter_path, dest, width=1920, height=1080, bg_path=None):
    """Aperçu fixe de la mise en page (vignettes, test de style, miniature de contrôle)."""
    from PIL import Image
    g = geometry(board, width, height)
    tmp_bg = None
    if not (bg_path and os.path.isfile(bg_path)):
        tmp_bg = bg_path = dest + ".bg.png"
        make_background(board, bg_path, width, height)
    im = Image.open(bg_path).convert("RGBA").resize((width, height))
    px, py, pw, ph = g["panel"]
    sc = Image.open(scene_image).convert("RGB")
    sw, sh = sc.size
    s = max(pw / sw, ph / sh)
    sc = sc.resize((max(pw, round(sw * s)), max(ph, round(sh * s))), Image.LANCZOS)
    l, t = (sc.width - pw) // 2, (sc.height - ph) // 2
    im.paste(sc.crop((l, t, l + pw, t + ph)), (px, py))
    fr = dest + ".frame.png"
    make_frame(board, bg_path, fr, width, height)
    im.alpha_composite(Image.open(fr))
    os.remove(fr)
    if presenter_path and os.path.isfile(presenter_path):
        pr = Image.open(presenter_path).convert("RGBA")
        ph_ = g["presenter_h"]
        pr = pr.resize((max(1, round(pr.width * ph_ / pr.height)), ph_), Image.LANCZOS)
        ow = int(round(float(board.get("presenter_outline") or 0) * height / 1080.0))
        if ow:
            pr = outline(pr, ow, board.get("outline_color") or "#FFFFFF")
            im.alpha_composite(pr, (max(0, g["presenter_x"] - ow - 2), g["presenter_bottom"] - ph_ - ow - 2))
        else:
            im.alpha_composite(pr, (g["presenter_x"], g["presenter_bottom"] - ph_))
    if tmp_bg:
        os.remove(tmp_bg)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    im = im.convert("RGB")
    im.save(dest, "JPEG" if dest.lower().endswith((".jpg", ".jpeg")) else "PNG", quality=90)
    return dest
