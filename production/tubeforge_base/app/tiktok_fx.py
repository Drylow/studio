"""Habillage TikTok : sous-titres « propres » mot par mot + accroche « grand jeu ».

Utilisé à la fois par le rendu automatique (render_worker) et par l'export DaVinci Resolve (images
PNG transparentes), pour que les deux montages soient identiques.

Style des sous-titres : volontairement sobre pour ne pas « faire IA » — police Montserrat ExtraBold,
casse normale, blanc avec une ombre douce (pas de gros contour), 1 à 3 mots, le mot prononcé passe
en jaune chaud, petite apparition en douceur. L'accroche, elle, met le paquet : gros titre Anton qui
claque, mot-clé surligné, secousse, flash.
"""
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
CAPTION_FONT = FONTS / "Montserrat-VF.ttf"
HOOK_FONT = FONTS / "Anton-Regular.ttf"
WHITE = (255, 255, 255, 255)
YELLOW = (255, 212, 59, 255)


def _font(path: Path, size: int, variation: str | None = None):
    try:
        f = ImageFont.truetype(str(path), size)
        if variation:
            try:
                f.set_variation_by_name(variation)
            except Exception:  # noqa: BLE001
                pass
        return f
    except OSError:
        for alt in ("C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/arialbd.ttf"):
            try:
                return ImageFont.truetype(alt, size)
            except OSError:
                continue
        return ImageFont.load_default(size)


def ease_out(u: float) -> float:
    return 1 - (1 - min(1.0, max(0.0, u))) ** 3


def ease_out_back(u: float, k: float = 1.7) -> float:
    u = min(1.0, max(0.0, u)) - 1
    return 1 + (k + 1) * u ** 3 + k * u ** 2


# ------------------------------------------------------------------ regroupement des mots

def tiktok_groups(words: list[dict], max_words: int = 3, max_chars: int = 18) -> list[dict]:
    """Groupes courts (1 à 3 mots) qui s'arrêtent sur la ponctuation, avec timings par mot."""
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append({"w": w["w"], "s": w["s"], "e": w["e"]})
        text = " ".join(x["w"] for x in cur)
        nxt = words[i + 1] if i + 1 < len(words) else None
        punct = bool(re.search(r"[.!?…,;:—][\"'”’»)]*$", w["w"]))
        too_long = nxt is not None and (len(text) + 1 + len(nxt["w"]) > max_chars or len(cur) >= max_words)
        if punct or too_long or nxt is None:
            groups.append({"start": cur[0]["s"], "end": cur[-1]["e"], "words": cur})
            cur = []
    for a, b in zip(groups, groups[1:]):
        a["end"] = b["start"] if b["start"] - a["end"] < 0.7 else a["end"] + 0.25
    if groups:
        groups[-1]["end"] += 0.4
    return groups


# ------------------------------------------------------------------ sous-titres

class TikTokCaptions:
    def __init__(self, groups: list[dict], W: int, H: int, hide_until: float = 0.0, hide_after: float = 1e9):
        self.groups = groups
        self.W, self.H = W, H
        self.hide_until = hide_until
        self.hide_after = hide_after
        self.font = _font(CAPTION_FONT, int(W * 0.084), "ExtraBold")
        self.idx = 0

    def _layout(self, words: list[str]) -> list[list[int]]:
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines, cur = [], []
        for i, w in enumerate(words):
            test = " ".join(words[j] for j in cur + [i])
            if cur and d.textlength(test, font=self.font) > self.W * 0.78:
                lines.append(cur)
                cur = [i]
            else:
                cur.append(i)
        if cur:
            lines.append(cur)
        return lines

    @lru_cache(maxsize=256)
    def render(self, gi: int, active: int) -> Image.Image:
        """Image RGBA (taille du texte + marges) du groupe gi avec le mot `active` en couleur."""
        words = [w["w"] for w in self.groups[gi]["words"]]
        f = self.font
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines = self._layout(words)
        space = d.textlength(" ", font=f)
        lh = int(f.size * 1.18)
        widths = [sum(d.textlength(words[i], font=f) for i in ln) + space * (len(ln) - 1) for ln in lines]
        pad = int(f.size * 0.45)
        bw, bh = int(max(widths)) + pad * 2, lh * len(lines) + pad * 2
        text_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        dt = ImageDraw.Draw(text_layer)
        for li, ln in enumerate(lines):
            x = (bw - widths[li]) / 2
            y = pad + li * lh
            for i in ln:
                dt.text((x, y), words[i], font=f, fill=YELLOW if i == active else WHITE,
                        stroke_width=max(2, f.size // 28), stroke_fill=(0, 0, 0, 150))
                x += d.textlength(words[i], font=f) + space
        # ombre douce décalée : le texte semble posé sur l'image, pas collé par-dessus
        alpha = text_layer.getchannel("A")
        shadow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        shadow.putalpha(alpha.point(lambda a: int(a * 0.72)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(3, f.size // 11)))
        out = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        out.alpha_composite(shadow, (0, max(2, f.size // 16)))
        out.alpha_composite(text_layer)
        return out

    def state_at(self, t: float) -> tuple[int, int, float] | None:
        """(groupe, mot actif, temps depuis l'apparition du groupe) ou None."""
        if t < self.hide_until or t >= self.hide_after or not self.groups:
            return None
        g = self.groups
        while self.idx < len(g) - 1 and t >= g[self.idx]["end"]:
            self.idx += 1
        while self.idx > 0 and t < g[self.idx]["start"]:
            self.idx -= 1
        cur = g[self.idx]
        if not (cur["start"] <= t < cur["end"]):
            return None
        active = 0
        for i, w in enumerate(cur["words"]):
            if t >= w["s"] - 0.02:
                active = i
        return self.idx, active, t - max(cur["start"], self.hide_until)

    def position(self, img: Image.Image) -> tuple[int, int]:
        return (self.W - img.width) // 2, int(self.H * 0.64) - img.height // 2

    def overlay(self, t: float):
        st = self.state_at(t)
        if st is None:
            return None
        gi, active, since = st
        img = self.render(gi, active)
        u = since / 0.14  # apparition douce : 88 % -> 100 % en 0,14 s
        if u < 1:
            sc = 0.88 + 0.12 * ease_out(u)
            img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BILINEAR)
            a = img.getchannel("A").point(lambda v: int(v * min(1.0, 0.35 + u)))
            img.putalpha(a)
        return img, self.position(img)


# ------------------------------------------------------------------ accroche

class Hook:
    """Gros titre d'ouverture : claque (zoom arrière rapide), secousse, flash, mot-clé surligné."""

    def __init__(self, text: str, highlight: str, W: int, H: int, duration: float):
        self.text = (text or "").upper().strip()
        self.highlight = (highlight or "").upper().strip(" .,!?")
        self.W, self.H, self.duration = W, H, duration
        self.font = _font(HOOK_FONT, int(W * 0.135))
        self._base = self._build() if self.text else None

    def _build(self) -> Image.Image:
        f = self.font
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words = self.text.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if cur and d.textlength(test, font=f) > self.W * 0.86:
                lines.append(cur)
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(cur)
        space = d.textlength(" ", font=f)
        lh = int(f.size * 1.08)
        widths = [sum(d.textlength(w, font=f) for w in ln) + space * (len(ln) - 1) for ln in lines]
        pad = int(f.size * 0.4)
        bw, bh = int(max(widths)) + pad * 2, lh * len(lines) + pad * 2
        layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        stroke = max(4, f.size // 14)
        for li, ln in enumerate(lines):
            x = (bw - widths[li]) / 2
            y = pad + li * lh
            for w in ln:
                ww = d.textlength(w, font=f)
                hl = self.highlight and w.strip(" .,!?:;").upper() == self.highlight
                if hl:  # mot-clé sur bandeau jaune, légèrement incliné façon marqueur
                    box = Image.new("RGBA", (int(ww + stroke * 4), int(f.size * 1.12)), YELLOW)
                    box = box.rotate(-2.5, expand=True, resample=Image.BICUBIC)
                    layer.alpha_composite(box, (int(x - stroke * 2), int(y - f.size * 0.02)))
                    dl.text((x, y), w, font=f, fill=(15, 15, 15, 255))
                else:
                    dl.text((x, y), w, font=f, fill=WHITE, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                x += ww + space
        alpha = layer.getchannel("A")
        shadow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        shadow.putalpha(alpha.point(lambda a: int(a * 0.8)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(f.size // 9))
        out = Image.new("RGBA", (bw, bh + f.size // 8), (0, 0, 0, 0))
        out.alpha_composite(shadow, (0, f.size // 9))
        out.alpha_composite(layer)
        return out

    def shake(self, t: float) -> tuple[int, int]:
        """Décalage de secousse (aussi appliqué à l'image de fond)."""
        if not self.text or t < 0.08 or t > 0.6:
            return 0, 0
        amp = 16 * (1 - (t - 0.08) / 0.52)
        return int(amp * math.sin(t * 97)), int(amp * math.cos(t * 83))

    def flash(self, t: float) -> float:
        return max(0.0, 0.55 * (1 - t / 0.12)) if self.text else 0.0

    def overlay(self, t: float):
        if not self._base or t >= self.duration:
            return None
        if t < 0.22:
            sc = 1.55 - 0.55 * ease_out_back(t / 0.22, 1.3)
            alpha = min(1.0, t / 0.06)
        elif t > self.duration - 0.25:
            u = (t - (self.duration - 0.25)) / 0.25
            sc, alpha = 1 - 0.12 * u, 1 - u
        else:
            sc, alpha = 1.0 + 0.02 * math.sin((t - 0.22) * 3), 1.0
        img = self._base
        if abs(sc - 1) > 0.003:
            img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BILINEAR)
        if alpha < 0.999:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
        dx, dy = self.shake(t)
        return img, ((self.W - img.width) // 2 + dx, int(self.H * 0.31) - img.height // 2 + dy)


def punch_zoom(k: int, fps: int) -> float:
    """Petit zoom au début de chaque scène (1,07 -> 1,00 en 5 images) : dynamise les coupes."""
    frames = max(3, int(fps * 0.2))
    if k >= frames:
        return 1.0
    return 1 + 0.07 * (1 - ease_out(k / frames))


def compose(frame: Image.Image, t: float, caps: "TikTokCaptions | None", hook: "Hook | None",
            endcard: "EndCard | None" = None) -> Image.Image:
    """Applique accroche + flash + sous-titres (+ écran de fin) sur une image RGB."""
    if endcard is not None and endcard.active(t):
        ov = endcard.overlay(t)
        if ov is not None:
            frame.paste(ov[0], ov[1], ov[0])
        return frame
    if hook is not None:
        h = hook.overlay(t)
        if h is not None:
            img, pos = h
            frame.paste(img, pos, img)
        fl = hook.flash(t)
        if fl > 0:
            frame = Image.blend(frame, Image.new("RGB", frame.size, (255, 255, 255)), fl)
    if caps is not None:
        c = caps.overlay(t)
        if c is not None:
            img, pos = c
            frame.paste(img, pos, img)
    return frame


# ------------------------------------------------------------------ écran de fin (short pub → YouTube)

YT_RED = (255, 0, 51, 255)


class EndCard:
    """Dernières secondes d'un short pub : miniature de la vidéo YouTube + « VIDÉO COMPLÈTE SUR YOUTUBE »."""

    def __init__(self, start: float, cta: dict, thumb: str | None, W: int, H: int):
        self.start, self.W, self.H = start, W, H
        self.cta = cta or {}
        self.layer = self._build(thumb)
        self.arrow = self._arrow()

    def _text(self, text: str, font, fill, stroke=0) -> Image.Image:
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        box = d.textbbox((0, 0), text, font=font, stroke_width=stroke)
        img = Image.new("RGBA", (box[2] - box[0] + 8, box[3] - box[1] + 8), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((4 - box[0], 4 - box[1]), text, font=font, fill=fill, stroke_width=stroke,
                                 stroke_fill=(0, 0, 0, 255))
        return img

    def _build(self, thumb: str | None) -> Image.Image:
        W, H = self.W, self.H
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        # voile sombre en dégradé pour la lisibilité
        grad = Image.new("L", (1, H))
        for y in range(H):
            grad.putpixel((0, y), int(70 + 130 * (y / H)))
        layer.paste(Image.new("RGBA", (W, H), (8, 8, 12, 255)), (0, 0), grad.resize((W, H)))
        big = _font(HOOK_FONT, int(W * 0.12))
        t1 = self._text(self.cta.get("line1", "FULL VIDEO"), big, WHITE, stroke=max(4, big.size // 14))
        layer.alpha_composite(t1, ((W - t1.width) // 2, int(H * 0.13)))
        y_card = int(H * 0.25)
        card_h = 0
        if thumb:
            try:
                im = Image.open(thumb).convert("RGB")
                cw = int(W * 0.8)
                ch = int(cw * im.height / im.width)
                im = im.resize((cw, ch), Image.LANCZOS)
                border = max(6, W // 160)
                card = Image.new("RGBA", (cw + border * 2, ch + border * 2), WHITE)
                card.paste(im, (border, border))
                mask = Image.new("L", card.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=W // 30, fill=255)
                card.putalpha(mask)
                card = card.rotate(-3, expand=True, resample=Image.BICUBIC)
                shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
                shadow.putalpha(card.getchannel("A").point(lambda a: int(a * 0.6)))
                shadow = shadow.filter(ImageFilter.GaussianBlur(W // 60))
                x = (W - card.width) // 2
                layer.alpha_composite(shadow, (x + W // 90, y_card + W // 70))
                layer.alpha_composite(card, (x, y_card))
                # bouton « lecture » YouTube au centre de la miniature
                pb_w = int(cw * 0.2)
                pb = Image.new("RGBA", (pb_w, int(pb_w * 0.7)), (0, 0, 0, 0))
                dp = ImageDraw.Draw(pb)
                dp.rounded_rectangle((0, 0, pb.width - 1, pb.height - 1), radius=pb.height // 4, fill=YT_RED)
                tw = pb.height * 0.42
                cx, cy = pb.width / 2, pb.height / 2
                dp.polygon([(cx - tw * 0.45, cy - tw * 0.55), (cx - tw * 0.45, cy + tw * 0.55), (cx + tw * 0.6, cy)], fill=WHITE)
                layer.alpha_composite(pb, ((W - pb.width) // 2, y_card + card.height // 2 - pb.height // 2))
                card_h = card.height
            except Exception:  # noqa: BLE001 — pas de miniature : l'écran de fin reste valable
                card_h = 0
        y = y_card + (card_h or int(H * 0.2)) + int(H * 0.035)
        f2 = _font(HOOK_FONT, int(W * 0.1))
        t2 = self._text(self.cta.get("line2", "ON YOUTUBE"), f2, WHITE)
        pad = int(W * 0.03)
        box = Image.new("RGBA", (t2.width + pad * 2, t2.height + pad), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, box.height - 1), radius=box.height // 4, fill=YT_RED)
        box.alpha_composite(t2, (pad, pad // 2))
        layer.alpha_composite(box, ((W - box.width) // 2, y))
        self.y_bio = y + box.height + int(H * 0.03)
        f3 = _font(CAPTION_FONT, int(W * 0.062), "ExtraBold")
        t3 = self._text(self.cta.get("line3", "link in bio"), f3, WHITE)
        layer.alpha_composite(t3, ((W - t3.width) // 2, self.y_bio))
        self.y_arrow = self.y_bio + t3.height + int(H * 0.012)
        return layer

    def _arrow(self) -> Image.Image:
        s = int(self.W * 0.07)
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(img).polygon([(s * 0.1, s * 0.25), (s * 0.9, s * 0.25), (s * 0.5, s * 0.85)], fill=YELLOW)
        return img

    def active(self, t: float) -> bool:
        return t >= self.start

    def overlay(self, t: float):
        if t < self.start:
            return None
        u = min(1.0, (t - self.start) / 0.35)
        dy = int((1 - ease_out(u)) * self.H * 0.06)
        frame = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        frame.alpha_composite(self.layer, (0, 0))
        bob = int(math.sin((t - self.start) * 7) * self.W * 0.012)
        frame.alpha_composite(self.arrow, ((self.W - self.arrow.width) // 2, self.y_arrow + bob))
        if u < 1:
            frame.putalpha(frame.getchannel("A").point(lambda a: int(a * ease_out(u))))
        if dy:
            shifted = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            shifted.alpha_composite(frame, (0, dy))
            frame = shifted
        return frame, (0, 0)
