"""Prof animé en bas à gauche : il fait des gestes de baguette calés sur la voix off.

Animation 2D « pose à pose », comme un vrai dessin animé (pas de rotation d'un morceau
d'image découpé) :

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


def build_pose_rig(base_blob, variants, out_dir):
    """base + {"mid": blob, "point": blob, "tap": blob} → images alignées (+ transitions) et rig.json.

    Une retouche absente ou ratée est remplacée par la pose voisine : le rig reste utilisable."""
    from PIL import Image
    base = _rgba(base_blob)
    base.putalpha(base.getchannel("A").point(lambda a: 0 if a < 16 else a))
    frames = {"A": base}
    for k in ("mid", "point", "tap"):
        if not variants.get(k):
            continue
        v = _align(base, _rgba(variants[k]))
        v.putalpha(v.getchannel("A").point(lambda a: 0 if a < 16 else a))
        frames[k] = Image.composite(v, base, _change_mask(base, v))
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
                "drawn": sorted(k for k in ("mid", "point", "tap") if variants.get(k))}
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
    return timeline(words, total, fps)


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
