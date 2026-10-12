"""Processus de rendu d'un segment vidéo : effet Ken Burns (zoom/pan sous-pixel) + sous-titres.

Lancé par steps/render.py :  python -m app.render_worker job.json
Écrit les images brutes dans ffmpeg (libx264) et affiche "P <frames>" pour la progression.
"""
import json
import math
import subprocess
import sys
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
MARGIN = 1.22  # marge de recadrage disponible pour les mouvements


def load_font(size: int):
    for f in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def motion_window(motion: str, u: float, dur: float, bw: float, bh: float, W: int, H: int, k: float):
    """Retourne la fenêtre (x0, y0, x1, y1) en coordonnées de l'image de base pour u∈[0,1]."""
    zoom_amt = max(0.06, min(0.18, 0.035 * dur)) * k
    if motion in ("zoom_in", "zoom_out"):
        z = 1 + zoom_amt * (u if motion == "zoom_in" else 1 - u)
        vw, vh = W * MARGIN / z, H * MARGIN / z
        cx, cy = bw / 2, bh / 2
    else:
        z = 1 + max(0.1, min(0.16, zoom_amt + 0.04))
        vw, vh = W * MARGIN / z, H * MARGIN / z
        cx, cy = bw / 2, bh / 2
        scale_out = z / MARGIN  # pixels de sortie par pixel de base
        speed = 48 * k          # pixels de sortie par seconde
        if motion in ("pan_left", "pan_right"):
            slack = bw - vw
            travel = min(slack * 0.92, speed * dur / scale_out)
            off = (u - 0.5) * travel
            cx += off if motion == "pan_right" else -off
        else:
            slack = bh - vh
            travel = min(slack * 0.92, speed * dur / scale_out)
            off = (u - 0.5) * travel
            cy += off if motion == "pan_down" else -off
    vw, vh = min(vw, bw), min(vh, bh)
    x0 = max(0.0, min(cx - vw / 2, bw - vw))
    y0 = max(0.0, min(cy - vh / 2, bh - vh))
    return x0, y0, x0 + vw, y0 + vh


def make_base(path: str, W: int, H: int) -> Image.Image:
    img = Image.open(path).convert("RGB")
    s = max(W / img.width, H / img.height) * MARGIN
    size = (max(math.ceil(W * MARGIN), math.ceil(img.width * s)), max(math.ceil(H * MARGIN), math.ceil(img.height * s)))
    return img.resize(size, Image.LANCZOS)


class Captions:
    def __init__(self, caps: list[dict], W: int, H: int):
        self.caps = caps
        self.W, self.H = W, H
        self.font = load_font(max(28, int(H * (0.052 if W > H else 0.036))))
        self.idx = 0

    @lru_cache(maxsize=64)
    def overlay(self, i: int) -> tuple[Image.Image, tuple[int, int]]:
        text = self.caps[i]["text"]
        W, H, font = self.W, self.H, self.font
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        max_w = W * 0.82
        lines, cur = [], ""
        for word in text.split():
            test = (cur + " " + word).strip()
            if draw.textlength(test, font=font) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        stroke = max(3, font.size // 12)
        lh = int(font.size * 1.22)
        bw = int(max(draw.textlength(l, font=font) for l in lines)) + stroke * 4
        bh = lh * len(lines) + stroke * 4
        im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for n, line in enumerate(lines):
            lw = d.textlength(line, font=font)
            d.text(((bw - lw) / 2, stroke * 2 + n * lh), line, font=font, fill=(255, 255, 255, 255),
                   stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y = int(H * (0.9 if W > H else 0.72)) - bh
        return im, ((W - bw) // 2, y)

    def at(self, t: float):
        caps = self.caps
        while self.idx < len(caps) - 1 and t >= caps[self.idx]["end"]:
            self.idx += 1
        while self.idx > 0 and t < caps[self.idx]["start"]:
            self.idx -= 1
        if caps and caps[self.idx]["start"] <= t < caps[self.idx]["end"]:
            return self.idx
        return None


def _tiktok_box(box, k, fps, t, hook, bw, bh, W, punch):
    """Zoom « punch » au début de chaque scène + secousse de l'accroche, appliqués au cadrage."""
    from app import tiktok_fx as fx
    x0, y0, x1, y1 = box
    z = fx.punch_zoom(k, fps) if punch else 1.0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    vw, vh = (x1 - x0) / z, (y1 - y0) / z
    if hook is not None:
        dx, dy = hook.shake(t)
        s = vw / W
        cx -= dx * s
        cy -= dy * s
    nx0 = max(0.0, min(cx - vw / 2, bw - vw))
    ny0 = max(0.0, min(cy - vh / 2, bh - vh))
    return nx0, ny0, nx0 + vw, ny0 + vh


def main(job_path: str) -> None:
    job = json.load(open(job_path, encoding="utf-8"))
    W, H, fps = job["width"], job["height"], job["fps"]
    strength = float(job.get("strength", 1.0))
    tk = job.get("tiktok")
    tk_caps = tk_hook = tk_end = None
    if tk:
        from app import tiktok_fx as fx
        h = tk.get("hook") or {}
        tk_hook = fx.Hook(h.get("text", ""), h.get("highlight", ""), W, H, float(h.get("duration", 0))) \
            if h.get("text") else None
        ec = tk.get("endcard")
        tk_end = fx.EndCard(float(ec["start"]), ec.get("cta") or {}, ec.get("thumb"), W, H) if ec else None
        tk_caps = fx.TikTokCaptions(tk.get("groups") or [], W, H,
                                    hide_until=float(h.get("duration", 0)) if tk_hook else 0.0,
                                    hide_after=float(ec["start"]) if ec else 1e9)
    caps = Captions(job["captions"], W, H) if job.get("captions") and not tk else None
    def encoder(out: str) -> subprocess.Popen:
        cmd = [job.get("ffmpeg", "ffmpeg"), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", job.get("preset", "veryfast"),
               "-crf", str(job.get("crf", 20)), "-pix_fmt", "yuv420p", "-g", str(fps * 2), "-threads", "2", out]
        return subprocess.Popen(cmd, stdin=subprocess.PIPE)

    if job.get("per_scene"):  # export Resolve : un clip par scène (mouvement intégré, sans texte)
        written = 0
        for sc in job["scenes"]:
            n = sc["frames"]
            if n <= 0:
                continue
            proc = encoder(sc["out"])
            base = make_base(sc["image"], W, H)
            bw, bh = base.size
            for k in range(n):
                u = k / (n - 1) if n > 1 else 0.0
                box = motion_window(sc.get("motion") or "zoom_in", u, n / fps, bw, bh, W, H, strength)                     if sc.get("motion") != "static" else motion_window("zoom_in", 0, n / fps, bw, bh, W, H, 0)
                proc.stdin.write(base.resize((W, H), Image.BILINEAR, box=box).tobytes())
                written += 1
                if written % 24 == 0:
                    print(f"P {written}", flush=True)
            proc.stdin.close()
            if proc.wait() != 0:
                sys.exit(f"ffmpeg failed on {sc['out']}")
        print(f"P {written}", flush=True)
        return
    proc = encoder(job["out"])
    written = 0
    try:
        for sc in job["scenes"]:
            n = sc["frames"]
            if n <= 0:
                continue
            base = make_base(sc["image"], W, H)
            bw, bh = base.size
            dur = n / fps
            motion = sc.get("motion") or "zoom_in"
            for k in range(n):
                u = k / (n - 1) if n > 1 else 0.0
                box = motion_window(motion, u, dur, bw, bh, W, H, strength) if motion != "static" else \
                    motion_window("zoom_in", 0, dur, bw, bh, W, H, 0)
                t = (sc["f0"] + k) / fps
                if tk:
                    box = _tiktok_box(box, k, fps, t, tk_hook, bw, bh, W, tk.get("punch", True))
                frame = base.resize((W, H), Image.BILINEAR, box=box)  # 28 % plus rapide, différence invisible
                if tk:
                    frame = fx.compose(frame, t, tk_caps, tk_hook, tk_end)
                if caps:
                    ci = caps.at((sc["f0"] + k) / fps)
                    if ci is not None:
                        ov, pos = caps.overlay(ci)
                        frame.paste(ov, pos, ov)
                proc.stdin.write(frame.tobytes())
                written += 1
                if written % 24 == 0:
                    print(f"P {written}", flush=True)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    code = proc.wait()
    print(f"P {written}", flush=True)
    if code != 0:
        sys.exit(f"ffmpeg failed ({code})")


if __name__ == "__main__":
    main(sys.argv[1])
