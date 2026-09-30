"""Prof animé en bas à gauche : il fait des gestes de baguette calés sur la voix off.

Deux animations au choix :

« stick » (baguette seule, voir en bas du fichier) — le prof reste UN seul dessin ; sa baguette
   est effacée puis redessinée par le code, derrière son poing, et elle pivote en douceur
   (balancement lent, descente vers le panneau et tapotements sur les chiffres clés), 30 i/s.

« poses » — animation 2D « pose à pose », comme un vrai dessin animé :

1. POSES — à partir d'UNE image de base (fond transparent, baguette levée), l'IA d'images
   redessine SEULEMENT le bras dans 3 autres positions : baguette à mi-hauteur, pointée
   à l'horizontale, puis légèrement vers le bas (tapotement). De chaque retouche on ne garde
   que la zone qui a changé (le bras), recollée sur la base → le corps, la tête et les pieds
   restent identiques au pixel près d'une pose à l'autre.
   Pour aller d'une pose à une autre, le bras passe par les poses intermédiaires (tenues 2
   images, « en deux », comme en dessin animé) : pas de fondu, donc jamais de bras fantôme.

2. PISTE — calée sur les mots : double tapotement vers le panneau sur les chiffres clés
   ($, %, nombres), et un geste « regardez ça » de temps en temps quand il parle.
   Au repos il ne bouge pas (pas de flottement). ffmpeg lit la piste via son demuxer concat.
"""
import io
import json
import os
import random
import re

POSES = ("A", "mid", "point", "tap")          # du plus levé au plus bas
INBETWEEN = 2 / 30                             # durée d'une pose intermédiaire (2 images à 30 i/s)

KEEP = ("Edit this image. Keep EXACTLY the same character, same head, same face, same body, same legs and feet, same "
        "size and same position in the frame, same colors, same line work and the same transparent background. ONLY "
        "redraw the arm that holds the pointer stick, and the stick: ")
POSE_EDITS = {
    "mid": KEEP + "the arm is a little lower and the pointer stick now points diagonally up and to the right, about "
                  "30 degrees above horizontal. Nothing else changes.",
    "point": KEEP + "the arm is extended forward at shoulder height and the pointer stick points straight to the right, "
                    "horizontal, like a teacher pointing at a board. Nothing else changes.",
    "tap": KEEP + "the arm is extended forward, slightly lowered, and the pointer stick points to the right and slightly "
                  "downward, about 15 degrees below horizontal, like a teacher tapping a board. Nothing else changes.",
}

PRESENTER_POSE = ("Full-body presenter character of the channel, alone, standing, body turned three-quarters to the "
                  "right, holding a thin wooden teacher's pointer stick in the right hand, arm raised and the stick "
                  "pointing up and to the right (about 55 degrees), other arm relaxed along the body, confident "
                  "friendly closed-mouth smile, looking at the viewer. The whole body is visible from head to shoes, "
                  "feet flat on the ground, nothing else in the image: no floor, no shadow, no background, no text.")


# ── Construction des poses ──────────────────────────────────────────────────

def _rgba(blob_or_img):
    from PIL import Image
    im = blob_or_img if hasattr(blob_or_img, "size") else Image.open(io.BytesIO(blob_or_img))
    return im.convert("RGBA")


def _on_gray(im):
    from PIL import Image
    bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def _align(base, var, radius=12):
    """Petit recalage (translation) de la retouche sur la base, sur le bas du corps (qui ne bouge pas)."""
    from PIL import Image, ImageChops, ImageStat
    s = 4
    bw, bh = base.width // s, base.height // s
    box = (0, bh // 2, bw, bh)  # jambes / pieds : jamais redessinés
    b = _on_gray(base).convert("L").resize((bw, bh)).crop(box)
    v = _on_gray(var).convert("L").resize((bw, bh))
    best, best_d = (0, 0), None
    r = max(1, radius // s)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = ImageStat.Stat(ImageChops.difference(b, ImageChops.offset(v, dx, dy).crop(box))).mean[0]
            if best_d is None or d < best_d:
                best, best_d = (dx, dy), d
    if best == (0, 0):
        return var
    out = Image.new("RGBA", var.size, (0, 0, 0, 0))
    out.paste(var, (best[0] * s, best[1] * s))
    return out


def _change_mask(base, var, thresh=56):
    """Masque (pleine taille, adouci) de ce qui a vraiment changé : le bras et la baguette.

    Couleur : seuil + érosion (retire le bruit de redessin). Forme (alpha) : sans érosion,
    pour garder la baguette fine. Les petites taches isolées sont ignorées."""
    from PIL import Image, ImageChops, ImageFilter
    s = 4
    w, h = base.width // s, base.height // s
    d = ImageChops.difference(_on_gray(base).resize((w, h)), _on_gray(var).resize((w, h))).convert("L")
    m = d.point(lambda p: 255 if p > thresh else 0).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    da = ImageChops.difference(base.getchannel("A").resize((w, h)), var.getchannel("A").resize((w, h)))
    m = ImageChops.lighter(m, da.point(lambda p: 255 if p > 110 else 0))
    keep = Image.new("L", (w, h), 0)
    px, kp = m.load(), keep.load()
    seen = bytearray(w * h)
    min_area = max(8, (w * h) // 3000)
    for y in range(h):
        for x in range(w):
            if px[x, y] and not seen[y * w + x]:
                stack, pts = [(x, y)], []
                seen[y * w + x] = 1
                while stack:
                    cx, cy = stack.pop()
                    pts.append((cx, cy))
                    for nx in (cx - 1, cx, cx + 1):
                        for ny in (cy - 1, cy, cy + 1):
                            if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and not seen[ny * w + nx]:
                                seen[ny * w + nx] = 1
                                stack.append((nx, ny))
                if len(pts) >= min_area:
                    for p in pts:
                        kp[p] = 255
    grow = max(3, w // 60)
    keep = keep.filter(ImageFilter.MaxFilter(grow | 1))
    return keep.resize(base.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(max(2, base.width // 300)))


MAX_CHANGE = 0.5  # part du perso qui change : ~0.2 quand seul le bras bouge, >0.8 quand l'IA a tout redessiné


def _prepared(base_blob):
    base = _rgba(base_blob)
    base.putalpha(base.getchannel("A").point(lambda a: 0 if a < 16 else a))
    return base


def _pose_layer(base, var_blob):
    """(retouche recalée, masque de ce qui change, part du perso qui change)."""
    v = _align(base, _rgba(var_blob))
    v.putalpha(v.getchannel("A").point(lambda a: 0 if a < 16 else a))
    m = _change_mask(base, v)
    fig = max(1, base.getchannel("A").point(lambda a: 255 if a > 24 else 0).histogram()[255])
    return v, m, m.point(lambda a: 255 if a > 0 else 0).histogram()[255] / fig


def pose_ok(base_blob, var_blob):
    """Faux quand l'IA a redessiné tout le perso (autre taille, autre place) au lieu du seul bras :
    recollée sur la base, une telle retouche laisse un corps fantôme."""
    return _pose_layer(_prepared(base_blob), var_blob)[2] <= MAX_CHANGE


def build_pose_rig(base_blob, variants, out_dir):
    """base + {"mid": blob, "point": blob, "tap": blob} → images alignées (+ transitions) et rig.json.

    Une retouche absente ou ratée (tout le perso redessiné) est remplacée par la pose voisine :
    le rig reste utilisable."""
    from PIL import Image
    base = _prepared(base_blob)
    frames = {"A": base}
    drawn = []
    for k in ("mid", "point", "tap"):
        if not variants.get(k):
            continue
        v, m, ratio = _pose_layer(base, variants[k])
        if ratio > MAX_CHANGE:
            continue
        frames[k] = Image.composite(v, base, m)
        drawn.append(k)
    frames.setdefault("mid", frames["A"])
    frames.setdefault("point", frames["mid"])
    frames.setdefault("tap", frames["point"])

    crop = None  # recadrage commun : toutes les images restent superposables
    for im in frames.values():
        bb = im.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
        if bb:
            crop = bb if crop is None else (min(crop[0], bb[0]), min(crop[1], bb[1]),
                                            max(crop[2], bb[2]), max(crop[3], bb[3]))
    crop = crop or (0, 0, base.width, base.height)
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"mode": "poses", "frames": {}, "size": [crop[2] - crop[0], crop[3] - crop[1]],
                "drawn": sorted(drawn)}
    for name, im in frames.items():
        fn = name + ".png"
        im.crop(crop).save(os.path.join(out_dir, fn), "PNG", compress_level=6)
        manifest["frames"][name] = fn
    with open(os.path.join(out_dir, "rig.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return manifest


def load_manifest(rig_dir):
    """{"mode", "frames": {clé: chemin absolu}} d'un dossier de rig, ou None."""
    try:
        with open(os.path.join(rig_dir, "rig.json"), "r", encoding="utf-8") as f:
            man = json.load(f)
    except (OSError, ValueError):
        return None
    frames = {k: os.path.join(rig_dir, v) for k, v in (man.get("frames") or {}).items()}
    if not frames.get("A") or not all(os.path.isfile(p) for p in frames.values()):
        return None
    return {"mode": man.get("mode") or "poses", "frames": frames}


# ── Piste d'animation calée sur la voix ─────────────────────────────────────

_KEY = re.compile(r"[\d$€£%]")


def _path(seq):
    """Suite de poses → le bras passe par les poses intermédiaires : A→point = A, mid, point."""
    order = {p: i for i, p in enumerate(POSES)}
    out = []
    for name, hold in seq:
        if out:
            i, j = order[out[-1][0]], order[name]
            step = 1 if j > i else -1
            for k in range(i + step, j, step):
                out.append((POSES[k], INBETWEEN))
        out.append((name, hold))
    return out


def timeline(words, total, fps=30, seed=11, every=(4.0, 7.5)):
    """[(clé_image, nb_frames)] couvrant [0, total].

    - chiffre clé ($, %, nombre) → la baguette descend et tapote 2 fois le panneau ;
    - de temps en temps pendant qu'il parle → geste « regardez ça » (baguette pointée ~1 s) ;
    - silence / reste du temps → pose de repos, immobile."""
    fps = int(fps)
    n = max(1, int(round(total * fps)))
    frame = ["A"] * n
    rnd = random.Random(seed)

    def play(t0, seq):
        i = int(round(t0 * fps))
        for name, dur in _path(seq):
            k = max(1, int(round(dur * fps))) if dur > 0 else 0
            for j in range(i, min(n, i + k)):
                frame[j] = name
            i += k
        return i / fps

    busy = -1.0
    items = [(float(w.get("s", 0)), float(w.get("e", 0)), w.get("w") or "") for w in words or []]
    for s, e, w in items:
        if s >= busy and _KEY.search(w):
            busy = play(max(0.0, s - 0.15), [("A", 0.0), ("tap", 0.13), ("point", 0.1), ("tap", 0.13),
                                             ("point", 0.25), ("A", 0.0)]) + 0.8
    t = rnd.uniform(1.5, every[0])
    for s, e, w in items:
        if s < t or s < busy:
            continue
        busy = play(s, [("A", 0.0), ("point", rnd.uniform(0.7, 1.4)), ("A", 0.0)]) + 0.6
        t = s + rnd.uniform(*every)

    out, prev, run = [], None, 0
    for name in frame:
        if name == prev:
            run += 1
        else:
            if prev is not None:
                out.append((prev, run))
            prev, run = name, 1
    out.append((prev, run))
    return out


def track_segments(mode, words, total, fps=30):
    return stick_timeline(words, total, fps) if mode == "stick" else timeline(words, total, fps)


def slice_timeline(segs, start_f, count):
    """Sous-partie [start_f, start_f + count[ d'une timeline (pour les clips du pack)."""
    out, pos, end = [], 0, start_f + count
    for name, k in segs:
        a, b = max(pos, start_f), min(pos + k, end)
        if b > a:
            out.append((name, b - a))
        pos += k
        if pos >= end:
            break
    if not out:
        out = [("A", count)]
    return out


def write_concat(segs, frame_paths, dest, fps=30):
    """Liste pour le demuxer concat d'ffmpeg (images + durées exactes en frames)."""
    fps = int(fps)

    def q(p):
        return "file '" + p.replace("\\", "/").replace("'", "'\\''") + "'"
    lines = ["ffconcat version 1.0"]
    for name, k in segs:
        lines.append(q(frame_paths.get(name) or frame_paths["A"]))
        lines.append(f"duration {k / fps:.6f}")
    lines.append(q(frame_paths.get(segs[-1][0]) or frame_paths["A"]))  # requis par concat
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return dest


# ── Baguette seule : le prof ne bouge pas, la baguette pivote dans son poing ──
# Une seule image du prof (baguette effacée) + une baguette dessinée par le code, derrière le poing,
# qui tourne autour d'un pivot au centre du poing : balancement lent en continu, et elle descend
# vers le panneau (avec deux petits tapotements) sur les chiffres clés. 30 images/s, aucun saut.

STICK_RANGE = (-44.0, 8.0)   # degrés autour de l'angle de repos (négatif = vers le panneau)
STICK_STEP = 0.25            # finesse de l'angle (une image par pas)
SWAY = (2.5, 3.6)            # balancement permanent : amplitude (°), période (s)


def _wood(r, g, b, a):
    return a > 200 and r > 140 and 80 < g < 200 and b < 150 and r - b > 50 and r > g


def _fit(pts):
    import math
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    a = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return mx, my, math.cos(a), math.sin(a)


def find_stick(im):
    """Baguette en bois d'un prof (RGBA) → {entry, tip, pivot, dir, half, outline, fill, light} ou None."""
    import math
    px = im.load()
    W, H = im.size
    bb = im.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
    if not bb:
        return None
    pts = [(x, y) for y in range(bb[1], bb[3]) for x in range(bb[0], bb[2]) if _wood(*px[x, y])]
    if len(pts) < 150:
        return None
    for _ in range(4):  # ligne robuste : on écarte ce qui n'est pas sur la baguette (billets, reflets)
        mx, my, dx, dy = _fit(pts)
        near = [p for p in pts if abs(-(p[0] - mx) * dy + (p[1] - my) * dx) < 9]
        if len(near) == len(pts) or len(near) < 150:
            break
        pts = near
    mx, my, dx, dy = _fit(pts)
    if dy > 0:
        dx, dy = -dx, -dy  # vers le bout de la baguette (le haut)
    ts = sorted((p[0] - mx) * dx + (p[1] - my) * dy for p in pts)
    t0, t1 = ts[int(len(ts) * 0.003)], ts[-1]
    entry = (mx + dx * t0, my + dy * t0)
    perp = sorted(abs(-(p[0] - mx) * dy + (p[1] - my) * dx) for p in pts)
    half = max(2.0, perp[int(len(perp) * 0.95)])
    # contour noir : épaisseur mesurée au milieu de la baguette, de part et d'autre du bois
    cx, cy = mx + dx * (t0 + t1) / 2, my + dy * (t0 + t1) / 2
    widths = []
    for side in (1, -1):
        dark = 0
        for s in range(int(half), int(half) + 16):
            x, y = int(round(cx - dy * s * side)), int(round(cy + dx * s * side))
            if not (0 <= x < W and 0 <= y < H):
                break
            r, g, b, a = px[x, y]
            if a > 120 and max(r, g, b) < 90:
                dark += 1
            elif dark:
                break
        widths.append(dark)
    outline = max(1.5, min(widths) if min(widths) else 3.0)
    # pivot : milieu de la partie blanche (le poing) sous l'entrée de la baguette
    run = []
    for s in range(2, 320):
        x, y = int(round(entry[0] - dx * s)), int(round(entry[1] - dy * s))
        if not (0 <= x < W and 0 <= y < H):
            break
        r, g, b, a = px[x, y]
        if a > 200 and min(r, g, b) > 200:
            run.append(s)
        elif run and s - run[-1] > 14:
            break
    if not run:
        return None
    sp = (run[0] + run[-1]) / 2
    pivot = (entry[0] - dx * sp, entry[1] - dy * sp)
    cols = sorted(px[p][:3] for p in pts[:: max(1, len(pts) // 400)])
    fill = cols[len(cols) // 2]
    light = tuple(min(255, int(c + (255 - c) * 0.35)) for c in fill)
    return {"entry": entry, "tip": (mx + dx * t1, my + dy * t1), "pivot": pivot, "dir": (dx, dy),
            "half": half, "outline": outline, "fill": fill, "light": light,
            "angle": math.degrees(math.atan2(-dy, dx)), "length": math.hypot(mx + dx * t1 - pivot[0],
                                                                              my + dy * t1 - pivot[1])}


def _hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _edge_dist(poly, x, y):
    """Distance signée au bord d'un polygone convexe (positive dedans)."""
    import math
    best = None
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        L = math.hypot(ex, ey) or 1.0
        d = ((x - ax) * ey - (y - ay) * ex) / L  # sens horaire/anti-horaire : on normalise plus bas
        best = d if best is None else (min(best, d) if best >= 0 or d >= 0 else max(best, d))
    return best


def erase_stick(im, st, margin=5):
    """Efface la baguette hors du poing, puis referme le haut du poing (blanc + contour noir) :
    la baguette redessinée peut tourner sans laisser de trou ni de bout fixe."""
    import math
    out = im.copy()
    px = out.load()
    ex, ey = st["entry"]
    dx, dy = st["dir"]
    pvx, pvy = st["pivot"]
    reach = st["half"] + st["outline"] + 2.5
    tip_t = (st["tip"][0] - ex) * dx + (st["tip"][1] - ey) * dy + st["half"] + st["outline"] + 3
    sp = math.hypot(ex - pvx, ey - pvy)

    def band(x, y, t_min, t_max=tip_t, width=reach):
        t = (x - ex) * dx + (y - ey) * dy
        return t_min < t < t_max and abs(-(x - ex) * dy + (y - ey) * dx) <= width

    bb = (int(min(ex, st["tip"][0]) - reach - 4), int(min(ey, st["tip"][1]) - reach - 4),
          int(max(ex, st["tip"][0]) + reach + 4), int(max(ey, st["tip"][1]) + reach + 4))
    for y in range(max(0, bb[1]), min(out.height, bb[3])):
        for x in range(max(0, bb[0]), min(out.width, bb[2])):
            if band(x, y, margin):
                px[x, y] = (0, 0, 0, 0)
    # poing : enveloppe convexe des pixels du perso autour du pivot (hors bande de la baguette)
    R = int(sp * 1.9) + 4
    cand = []
    for y in range(max(0, int(pvy - R)), min(out.height, int(pvy + R))):
        for x in range(max(0, int(pvx - R)), min(out.width, int(pvx + R))):
            if (x - pvx) ** 2 + (y - pvy) ** 2 <= R * R and px[x, y][3] > 120 and \
                    not band(x, y, -sp, width=reach * 1.8):
                cand.append((x, y))
    hull = _hull(cand)
    if len(hull) < 3:
        return out
    # orientation : distance positive à l'intérieur
    area = sum(hull[i][0] * hull[(i + 1) % len(hull)][1] - hull[(i + 1) % len(hull)][0] * hull[i][1]
               for i in range(len(hull)))
    sign = -1 if area > 0 else 1
    whites = sorted(px[x, y][:3] for x, y in cand[:: max(1, len(cand) // 300)] if min(px[x, y][:3]) > 215)
    white = whites[len(whites) // 2] if whites else (250, 250, 250)
    ol = st["outline"]
    for y in range(max(0, int(pvy - R)), min(out.height, int(pvy + R))):
        for x in range(max(0, int(pvx - R)), min(out.width, int(pvx + R))):
            if not band(x, y, -3, t_max=sp * 0.8):
                continue
            r, g, b, a = px[x, y]
            above = (x - ex) * dx + (y - ey) * dy > 0  # au-dessus de l'entrée : tout vient de la baguette
            if not above and a > 120 and not _wood(r, g, b, a) and \
                    not (max(r, g, b) < 90 and abs(-(x - ex) * dy + (y - ey) * dx) > st["half"]):
                continue  # doigts, contour du poing : on n'y touche pas
            d = _edge_dist(hull, x, y) * sign
            if d < 0:
                continue
            px[x, y] = (17, 17, 17, 255) if d <= ol else tuple(white) + (255,)
    return out


def draw_stick(size, pivot, length, angle, half, outline, fill, light, ss=4):
    """Calque RGBA de la baguette (pivot → bout arrondi), dessinée en suréchantillonnage
    dans sa seule boîte (rapide), puis posée sur un calque de la taille demandée."""
    import math
    from PIL import Image, ImageDraw
    W, H = size
    a = math.radians(angle)
    ux, uy = math.cos(a), -math.sin(a)
    tx, ty = pivot[0] + ux * length, pivot[1] + uy * length
    wo = half + outline
    x0, y0 = int(math.floor(min(pivot[0], tx) - wo - 2)), int(math.floor(min(pivot[1], ty) - wo - 2))
    x1, y1 = int(math.ceil(max(pivot[0], tx) + wo + 2)), int(math.ceil(max(pivot[1], ty) + wo + 2))
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    big = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    px_, py_ = (pivot[0] - x0) * ss, (pivot[1] - y0) * ss
    tx_, ty_ = (tx - x0) * ss, (ty - y0) * ss
    W_o = wo * ss
    d.line([(px_, py_), (tx_, ty_)], fill=(17, 17, 17, 255), width=int(round(2 * W_o)))
    d.ellipse([tx_ - W_o, ty_ - W_o, tx_ + W_o, ty_ + W_o], fill=(17, 17, 17, 255))
    wi = half * ss
    ix, iy = tx_ - ux * outline * ss * 0.2, ty_ - uy * outline * ss * 0.2
    d.line([(px_, py_), (ix, iy)], fill=tuple(fill) + (255,), width=int(round(2 * wi)))
    d.ellipse([ix - wi, iy - wi, ix + wi, iy + wi], fill=tuple(fill) + (255,))
    nx, ny = -uy, ux  # reflet clair le long du bord supérieur
    if ny > 0:
        nx, ny = -nx, -ny
    off = wi * 0.45
    d.line([(px_ + nx * off, py_ + ny * off), (ix - ux * wi + nx * off, iy - uy * wi + ny * off)],
           fill=tuple(light) + (255,), width=max(1, int(round(wi * 0.5))))
    small = big.resize((bw, bh), Image.LANCZOS)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.alpha_composite(small, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
    return layer


def build_stick_rig(base_blob, out_dir):
    """Image du prof (baguette en main) → rig « baguette seule » : body.png (sans baguette),
    A.png (au repos, baguette redessinée) et rig.json (pivot, longueur, angle, couleurs).
    None si aucune baguette en bois n'est repérée."""
    base = _prepared(base_blob)
    st = find_stick(base)
    if not st:
        return None
    body = erase_stick(base, st)
    rest = draw_stick(base.size, st["pivot"], st["length"], st["angle"], st["half"], st["outline"],
                      st["fill"], st["light"])
    rest.alpha_composite(body)
    crop = rest.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox() or (0, 0) + base.size
    os.makedirs(out_dir, exist_ok=True)
    body.crop(crop).save(os.path.join(out_dir, "body.png"), "PNG", compress_level=6)
    rest.crop(crop).save(os.path.join(out_dir, "A.png"), "PNG", compress_level=6)
    stick = {"pivot": [st["pivot"][0] - crop[0], st["pivot"][1] - crop[1]], "length": st["length"],
             "angle": st["angle"], "half": st["half"], "outline": st["outline"],
             "fill": list(st["fill"]), "light": list(st["light"])}
    manifest = {"mode": "stick", "frames": {"A": "A.png", "body": "body.png"},
                "size": [crop[2] - crop[0], crop[3] - crop[1]], "stick": stick}
    with open(os.path.join(out_dir, "rig.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return manifest


def load_stick(rig_dir):
    try:
        with open(os.path.join(rig_dir, "rig.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("stick")
    except (OSError, ValueError):
        return None


def stick_key(k):
    return f"d{k}"


def stick_frames(body_path, st, height, workdir):
    """Toutes les images de la baguette (un pas de STICK_STEP), prof mis à `height` px de haut.
    → ({clé: chemin}, marge_haut) ; les images sont agrandies en haut et à droite pour que la
    baguette tienne dans tous ses angles (les pieds restent au même endroit)."""
    import hashlib
    import math
    from PIL import Image
    body = Image.open(body_path).convert("RGBA")
    scale = height / body.height
    body = body.resize((max(2, round(body.width * scale)), int(height)), Image.LANCZOS)
    W, H = body.size
    piv = (st["pivot"][0] * scale, st["pivot"][1] * scale)
    L = st["length"] * scale
    reach = L + (st["half"] + st["outline"]) * scale + 2
    lo, hi = st["angle"] + STICK_RANGE[0], st["angle"] + STICK_RANGE[1]
    top = max(0, math.ceil(reach * max(math.sin(math.radians(a)) for a in (lo, hi, max(lo, min(hi, 90))))
                           - piv[1]))
    right = max(0, math.ceil(piv[0] + reach * max(math.cos(math.radians(a)) for a in (lo, hi, max(lo, min(hi, 0))))
                             - W))
    sig = hashlib.sha1(json.dumps([os.path.basename(body_path), os.path.getsize(body_path),
                                   int(os.path.getmtime(body_path)), round(scale, 5), st, STICK_RANGE,
                                   STICK_STEP]).encode()).hexdigest()[:10]
    d = os.path.join(workdir, f"stick_{sig}")
    os.makedirs(d, exist_ok=True)
    size = (W + right, H + top)
    padded = Image.new("RGBA", size, (0, 0, 0, 0))
    padded.alpha_composite(body, (0, top))
    pv = (piv[0], piv[1] + top)
    frames = {}
    k0, k1 = int(round(STICK_RANGE[0] / STICK_STEP)), int(round(STICK_RANGE[1] / STICK_STEP))
    for k in range(k0, k1 + 1):
        path = os.path.join(d, f"{stick_key(k)}.png")
        if not os.path.isfile(path):
            im = draw_stick(size, pv, L, st["angle"] + k * STICK_STEP, st["half"] * scale,
                            st["outline"] * scale, st["fill"], st["light"], ss=3)
            im.alpha_composite(padded)
            im.save(path + ".tmp.png", "PNG", compress_level=3)
            os.replace(path + ".tmp.png", path)
        frames[stick_key(k)] = path
    frames["A"] = frames[stick_key(0)]
    return frames, top


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def stick_timeline(words, total, fps=30, seed=11, every=(4.0, 7.5)):
    """[(clé_image, nb_frames)] de la baguette : balancement lent permanent + gestes fluides.

    - chiffre clé ($, %, nombre) → elle descend vers le panneau, tapote 2 fois, remonte ;
    - de temps en temps quand il parle → elle se pose vers le panneau ~1 s (« regardez ça »)."""
    import math
    fps = int(fps)
    n = max(1, int(round(total * fps)))
    amp, period = SWAY
    off = [amp * math.sin(2 * math.pi * i / (period * fps)) for i in range(n)]
    rnd = random.Random(seed)

    def gesture(t0, keys):
        """keys = [(durée, angle_cible)] enchaînés en fondu doux depuis 0 ; renvoie la fin (s)."""
        i, cur = int(round(t0 * fps)), 0.0
        for dur, target in keys:
            k = max(1, int(round(dur * fps)))
            for j in range(k):
                if i + j < n:
                    off[i + j] += cur + (target - cur) * _ease((j + 1) / k)
            i += k
            cur = target
        return i / fps

    tap = [(0.35, -30.0), (0.12, -24.0), (0.12, -30.0), (0.12, -24.0), (0.14, -30.0), (0.25, -30.0),
           (0.55, 0.0)]
    busy = -1.0
    items = [(float(w.get("s", 0)), float(w.get("e", 0)), w.get("w") or "") for w in words or []]
    for s, e, w in items:
        if s >= busy and _KEY.search(w):
            busy = gesture(max(0.0, s - 0.2), tap) + 0.9
    t = rnd.uniform(1.5, every[0])
    for s, e, w in items:
        if s < t or s < busy:
            continue
        hold = rnd.uniform(0.7, 1.3)
        busy = gesture(s, [(0.4, -18.0), (hold, -18.0), (0.5, 0.0)]) + 0.7
        t = s + rnd.uniform(*every)

    k0, k1 = int(round(STICK_RANGE[0] / STICK_STEP)), int(round(STICK_RANGE[1] / STICK_STEP))
    out, prev, run = [], None, 0
    for v in off:
        name = stick_key(max(k0, min(k1, int(round(v / STICK_STEP)))))
        if name == prev:
            run += 1
        else:
            if prev is not None:
                out.append((prev, run))
            prev, run = name, 1
    out.append((prev, run))
    return out


# ── Prof « acteur » : une pose par idée, qui change avec un petit rebond ──────
# L'IA dessine une bibliothèque de poses du même prof (même costume) ; le réalisateur (plan de
# montage) choisit la pose de chaque scène ; les poses « qui tiennent » un objet vierge (pancarte,
# téléphone) reçoivent un texte écrit par le code dans la zone crème de l'objet.

HOLD_COLOR = (255, 246, 216)  # #FFF6D8 : couleur imposée à l'objet vierge, repérée ensuite par le code

_POSE_BASE = ("Edit this image. Redraw THE SAME CHARACTER: the same large round plain white head with the same "
              "soft grey shading, the same simple face style (small solid black dot eyes, short simple black "
              "eyebrows, a simple mouth), the same grey three-piece suit, white shirt, black tie, waistcoat buttons, "
              "the same fan of green dollar bills in the breast pocket, grey trousers, black shoes, white mitten "
              "hands, same line work, same colors, same proportions and the same size in the frame. Full body from "
              "head to shoes, feet on the ground, standing slightly turned to the right. NO pointer stick. "
              "Transparent background, nothing else in the image, no text. POSE: ")
POSE_PROMPTS = {
    "idle": "standing relaxed, both hands at his sides, friendly natural closed-mouth smile.",
    "explain": "one hand raised at shoulder height with the open palm up, presenting something to his right, the "
               "other arm relaxed, friendly natural smile.",
    "point": "arm extended to the right at shoulder height, index finger pointing to the right at something "
             "off-frame, friendly confident expression.",
    "arms_crossed": "arms crossed over his chest, calm serious expression with a small flat mouth.",
    "think": "one hand on his chin, thinking, eyes looking up, small neutral mouth.",
    "shrug": "both hands raised to his sides with the palms up in a shrug, eyebrows raised, small uncertain mouth.",
    "shocked": "both hands on his cheeks, eyes wide, mouth open in a round O of shock.",
    "money": "holding a fan of green dollar bills in one hand and counting them with the other hand, pleased smile.",
    "facepalm": "one hand covering his eyes in a facepalm, the other hand on his hip, disappointed.",
    "calculator": "holding a big grey pocket calculator in both hands in front of his belly and looking down at it "
                  "with a worried frown.",
    "thumbs_down": "one hand giving a thumbs down, the other hand on his hip, unimpressed flat mouth.",
    "wave": "waving hello with one raised open hand, friendly smile.",
    "hold_sign": "holding with both hands, in front of his chest, a large blank rectangular card facing the viewer "
                 "(about as wide as his shoulders). The card is plain flat pale cream color #FFF6D8 with a thick "
                 "black outline, completely empty, no text, no shading on it. Friendly smile.",
    "hold_phone": "holding up with one hand, at chest height, a big smartphone facing the viewer. The phone screen "
                  "is plain flat pale cream color #FFF6D8, completely empty, no text, no icons. Serious expression.",
}


def build_pose_library(base_blob, out_dir, names=None, workers=5, log=print):
    """Génère les poses (IA, en parallèle) → out_dir/<pose>.png (brutes) ; renvoie {pose: chemin}."""
    from concurrent.futures import ThreadPoolExecutor
    from services import ai
    os.makedirs(out_dir, exist_ok=True)
    names = names or list(POSE_PROMPTS)

    def one(name):
        path = os.path.join(out_dir, f"{name}.png")
        if os.path.isfile(path):
            return name, path
        for _ in range(2):
            try:
                blob = ai.generate_image(_POSE_BASE + POSE_PROMPTS[name], width=1024, height=1536,
                                         refs=[base_blob], quality="high", transparent=True)
            except ai.AIError as e:
                if getattr(e, "status", None) == 4290:
                    raise
                log(f"pose {name} : {str(e)[:100]}")
                continue
            with open(path, "wb") as f:
                f.write(blob)
            log(f"pose {name} ok")
            return name, path
        return name, None
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return {k: v for k, v in ex.map(one, names) if v}


def _white_component_box(im, top_frac=0.45):
    """Boîte de l'intérieur blanc de la tête (plus grande zone quasi blanche du haut du perso)."""
    s = 4
    w, h = max(1, im.width // s), max(1, im.height // s)
    sm = im.resize((w, h))
    a = list(sm.getchannel("A").getdata())
    rgb = list(sm.convert("RGB").getdata())
    px = [1 if (aa > 200 and min(c) > 215) else 0 for aa, c in zip(a, rgb)]
    fig = sm.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not fig:
        return None
    lim = fig[1] + int((fig[3] - fig[1]) * top_frac)
    seen = bytearray(w * h)
    best = []
    for y in range(fig[1], lim):
        for x in range(w):
            i = y * w + x
            if px[i] and not seen[i]:
                st, pts = [i], []
                seen[i] = 1
                while st:
                    j = st.pop()
                    pts.append(j)
                    cx, cy = j % w, j // w
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h:
                            kk = ny * w + nx
                            if px[kk] and not seen[kk]:
                                seen[kk] = 1
                                st.append(kk)
                if len(pts) > len(best):
                    best = pts
    if not best:
        return None
    xs, ys = [j % w for j in best], [j // w for j in best]
    return [min(xs) * s, min(ys) * s, (max(xs) + 1) * s, (max(ys) + 1) * s]


def _hold_box(im):
    """Zone vierge crème (pancarte, écran) d'une pose « qui tient » : boîte intérieure, ou None."""
    s = 2
    w, h = max(1, im.width // s), max(1, im.height // s)
    sm = im.resize((w, h))
    a = list(sm.getchannel("A").getdata())
    rgb = list(sm.convert("RGB").getdata())
    hr, hg, hb = HOLD_COLOR
    px = [1 if aa > 200 and abs(c[0] - hr) < 22 and abs(c[1] - hg) < 22 and abs(c[2] - hb) < 30 else 0
          for aa, c in zip(a, rgb)]
    seen = bytearray(w * h)
    best = []
    for i0 in range(w * h):
        if px[i0] and not seen[i0]:
            st, pts = [i0], []
            seen[i0] = 1
            while st:
                j = st.pop()
                pts.append(j)
                cx, cy = j % w, j // w
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        kk = ny * w + nx
                        if px[kk] and not seen[kk]:
                            seen[kk] = 1
                            st.append(kk)
            if len(pts) > len(best):
                best = pts
    if len(best) < 200:
        return None
    xs, ys = sorted(j % w for j in best), sorted(j // w for j in best)
    q = lambda v, f: v[int(len(v) * f)]  # noqa: E731  (bords robustes : ignore les pixels isolés)
    return [q(xs, 0.01) * s, q(ys, 0.01) * s, (q(xs, 0.99) + 1) * s, (q(ys, 0.99) + 1) * s]


def prepare_poses(raw_dir, out_dir):
    """Poses brutes (1024×1536, fond transparent) → poses recadrées + poses.json
    {pose: {file, head: [x0,y0,x1,y1], hold: [x0,y0,x1,y1] | None}} (coordonnées de l'image recadrée)."""
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    meta = {}
    for f in sorted(os.listdir(raw_dir)):
        name, ext = os.path.splitext(f)
        if ext.lower() != ".png" or name not in POSE_PROMPTS:
            continue
        im = Image.open(os.path.join(raw_dir, f)).convert("RGBA")
        im.putalpha(im.getchannel("A").point(lambda a: 0 if a < 16 else a))
        bb = im.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
        if not bb:
            continue
        im = im.crop(bb)
        head = _white_component_box(im)
        if not head:
            continue
        hold = _hold_box(im) if name.startswith("hold_") else None
        im.save(os.path.join(out_dir, f"{name}.png"), "PNG", optimize=True)
        meta[name] = {"file": f"{name}.png", "head": head, "hold": hold}
    with open(os.path.join(out_dir, "poses.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return meta


def load_poses(pose_dir):
    try:
        with open(os.path.join(pose_dir, "poses.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: dict(v, path=os.path.join(pose_dir, v["file"])) for k, v in meta.items()
            if os.path.isfile(os.path.join(pose_dir, v["file"]))}


POP = (0.86, 0.96, 1.045, 1.06, 1.035, 1.012)  # rebond quand le prof change de pose (1 image chacune)


def _sign_text(im, box, text):
    """Écrit `text` (1 à 2 lignes, noir, gras) centré dans la zone vierge `box` de la pose."""
    from PIL import ImageDraw, ImageFont
    x0, y0, x1, y1 = box
    bw, bh = (x1 - x0) * 0.86, (y1 - y0) * 0.8
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "fonts",
                        "Poppins-900.ttf")
    words = text.replace("/", " /").split()
    options = [[text]]
    for n in (2, 3):  # découpes en 2 ou 3 lignes (écran de téléphone étroit)
        if len(words) >= n:
            k = len(words) / n
            options.append([" ".join(words[round(i * k):round((i + 1) * k)]).replace(" /", "/")
                            for i in range(n)])
    best = None
    for lines in options:
        size = int(bh / len(lines) * 0.9)
        while size > 8:
            f = ImageFont.truetype(path, size)
            wmax = max(f.getbbox(ln)[2] - f.getbbox(ln)[0] for ln in lines)
            if wmax <= bw and size * 1.05 * len(lines) <= bh:
                break
            size -= 2
        if best is None or size > best[0]:
            best = (size, lines)
    size, lines = best
    f = ImageFont.truetype(path, size)
    d = ImageDraw.Draw(im)
    cy = (y0 + y1) / 2
    lh = size * 1.05
    for i, ln in enumerate(lines):
        d.text(((x0 + x1) / 2, cy + (i - (len(lines) - 1) / 2) * lh), ln, font=f, fill=(17, 17, 17), anchor="mm")
    return im


def acting_frames(pose_dir, height, workdir, texts=None):
    """Toutes les images du prof « acteur » à la taille du rendu, sur une toile commune.

    Les poses sont mises à la même échelle (même largeur de tête que la pose « idle », qui fait
    `height` px de haut), pieds sur la même ligne, tête au même endroit ; chaque pose a ses images
    de rebond. texts = {(pose, texte)} à écrire sur les pancartes / écrans.
    → ({clé: chemin}, décalage_x_de_la_toile, hauteur_de_la_toile) ; clés « pose », « pose@k »
    (rebond), « pose|texte » et « pose|texte@k »."""
    import hashlib
    from PIL import Image
    poses = load_poses(pose_dir)
    if not poses:
        return {}, 0, 0
    ref = poses.get("idle") or next(iter(poses.values()))
    rim = Image.open(ref["path"])
    s_ref = height / rim.height
    head_w = (ref["head"][2] - ref["head"][0]) * s_ref
    head_cx = (ref["head"][0] + ref["head"][2]) / 2 * s_ref
    placed = {}
    for name, p in poses.items():
        im = Image.open(p["path"]).convert("RGBA")
        s = head_w / max(1, p["head"][2] - p["head"][0])
        w, h = max(2, round(im.width * s)), max(2, round(im.height * s))
        placed[name] = (im.resize((w, h), Image.LANCZOS), s, (p["head"][0] + p["head"][2]) / 2 * s, p)
    left = max(hc - head_cx for _, _, hc, _ in placed.values())  # toile commune : rien ne dépasse
    left = max(0.0, left)
    right = max(im.width - hc + head_cx for im, _, hc, _ in placed.values())
    W = int(round(left + right)) + 8
    H = int(max(im.height for im, _, _, _ in placed.values()) * 1.07) + 4  # marge pour le rebond
    sig = hashlib.sha1(json.dumps([sorted((k, os.path.getsize(v["path"])) for k, v in poses.items()), height,
                                   sorted(texts or [])]).encode()).hexdigest()[:10]
    d = os.path.join(workdir, f"acting_{sig}")
    os.makedirs(d, exist_ok=True)
    frames = {}

    def emit(key, im, hc):
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        x = int(round(left + head_cx - hc))
        base.alpha_composite(im, (x, H - im.height))
        path = os.path.join(d, key.replace("|", "__").replace("/", "_") + ".png")
        if not os.path.isfile(path):
            base.save(path, "PNG", compress_level=3)
        frames[key] = path
        fx = x + im.width / 2  # rebond ancré aux pieds
        for i, sc in enumerate(POP):
            kpath = os.path.join(d, f"{os.path.basename(path)[:-4]}@{i}.png")
            if not os.path.isfile(kpath):
                sw, sh = max(1, round(im.width * sc)), max(1, round(im.height * sc))
                pim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                pim.alpha_composite(im.resize((sw, sh), Image.BILINEAR),
                                    (int(round(fx - sw / 2)), H - sh))
                pim.save(kpath, "PNG", compress_level=3)
            frames[f"{key}@{i}"] = kpath

    for name, (im, s, hc, p) in placed.items():
        emit(name, im, hc)
    for pose, text in sorted(texts or []):
        if pose not in placed or not placed[pose][3].get("hold") or not text:
            continue
        im, s, hc, p = placed[pose]
        box = [v * s for v in p["hold"]]
        emit(f"{pose}|{text}", _sign_text(im.copy(), box, text), hc)
    return frames, int(round(left)), H


def acting_segments(timeline, total, fps=30):
    """timeline = [(seconde, clé)] (une entrée par changement de pose) → [(clé_image, nb_frames)],
    avec le rebond au début de chaque nouvelle pose."""
    fps = int(fps)
    n = max(1, int(round(total * fps)))
    marks = sorted((max(0, int(round(t * fps))), k) for t, k in timeline or []) or [(0, "idle")]
    if marks[0][0] > 0:
        marks.insert(0, (0, marks[0][1]))
    out = []
    for j, (f0, key) in enumerate(marks):
        f1 = marks[j + 1][0] if j + 1 < len(marks) else n
        if f1 <= f0:
            continue
        pop = len(POP) if (j == 0 or key != marks[j - 1][1]) else 0
        pop = min(pop, f1 - f0)
        for i in range(pop):
            out.append((f"{key}@{i}", 1))
        if f1 - f0 - pop > 0:
            out.append((key, f1 - f0 - pop))
    return out
