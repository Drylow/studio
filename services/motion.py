"""Animations du montage (motion design) dessinées par le code, dans le style des chaînes 2D :
gros contours noirs, ombres franches, papier crème, jaune / rouge en accent.

Chaque animation (« fx ») est une carte posée sur le panneau pendant une scène :

    label     mot clé qui pop, surligné au marqueur jaune
    counter   compteur qui défile jusqu'au chiffre (0 → $61,000)
    receipt   ticket de caisse : la ligne s'imprime, le total défile, cercle rouge autour
    bars      barres qui poussent (comparaison de montants)
    pie       anneau « qui touche l'argent » (parts qui se dessinent)
    list      récap : les points apparaissent un par un, cochés
    split     deux colonnes face à face (règlement / procès) + badge VS
    timeline  frise : la ligne se trace, les étapes apparaissent
    stamp     tampon qui claque (PAID, DENIED, NOT INCLUDED…)

render_fx() dessine les images (30 i/s) de la partie animée puis une image finale tenue et un
fondu de sortie ; la scène les incruste via une liste concat (voir render.render_clip). Chaque fx
renvoie aussi ses bruitages (services/sfx.py) aux bons instants.
"""
import math
import os
import re

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "fonts")

INK = (17, 17, 17)
PAPER = (255, 250, 236)
WHITE = (255, 255, 255)
YELLOW = (255, 212, 71)
RED = (230, 57, 70)
GREEN = (43, 182, 115)
BLUE = (58, 134, 255)
GREY = (120, 128, 140)
PALETTE = [(58, 134, 255), (230, 57, 70), (255, 184, 28), (43, 182, 115), (155, 93, 229), (255, 128, 64)]
SS = 2          # suréchantillonnage des formes (contours lisses)
EXIT = 0.4      # sortie (s) : fondu adouci, calé sur le fondu entre deux images quand la carte part avec sa scène
CENTER_Y = 0.46  # hauteur des cartes centrées dans le panneau (un peu au-dessus du milieu)
TYPES = ("label", "counter", "receipt", "bars", "pie", "list", "split", "timeline", "stamp", "sheet", "route",
         "chapter")
FULL_PANEL = ("sheet",)  # ces fx remplacent l'image de la scène (pas d'image à générer)

_fonts = {}


def font(weight, size):
    """Poppins 700/800/900, Montserrat 800 (tampons)."""
    size = max(8, int(round(size)))
    key = (weight, size)
    if key not in _fonts:
        from PIL import ImageFont
        name = "Montserrat-800.ttf" if weight == "stamp" else f"Poppins-{weight}.ttf"
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    return _fonts[key]


# ── courbes d'animation ──────────────────────────────────────────────────────

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_back(x, s=1.9):
    x = clamp(x)
    x -= 1
    return 1 + x * x * ((s + 1) * x + s)


def seg(t, a, b):
    """Progression 0→1 de t entre a et b."""
    return clamp((t - a) / max(1e-6, b - a))


# ── nombres ───────────────────────────────────────────────────────────────────

_NUM = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")


def parse_number(text):
    """« $61,000 » → ("$", 61000.0, "", 0 décimale, séparateur) ; None si pas de nombre."""
    m = _NUM.search(text or "")
    if not m:
        return None
    raw = m.group(1)
    dec = len(raw.split(".")[1]) if "." in raw else 0
    return text[:m.start()], float(raw.replace(",", "")), text[m.end():], dec, "," in raw or \
        float(raw.replace(",", "")) >= 10000


def fmt_number(prefix, value, suffix, dec, commas):
    s = f"{value:,.{dec}f}" if commas else f"{value:.{dec}f}"
    return f"{prefix}{s}{suffix}"


# ── dessin ────────────────────────────────────────────────────────────────────

class Pad:
    """Toile suréchantillonnée : on dessine en coordonnées « 1x », tout est multiplié par SS."""

    def __init__(self, w, h):
        from PIL import Image, ImageDraw
        self.w, self.h = int(w), int(h)
        self.im = Image.new("RGBA", (self.w * SS, self.h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def box(self, xy, fill, outline=INK, width=5, radius=22, shadow=10, shadow_fill=INK):
        x0, y0, x1, y1 = [v * SS for v in xy]
        if shadow:
            s = shadow * SS
            self.d.rounded_rectangle((x0 + s, y0 + s, x1 + s, y1 + s), radius * SS, fill=shadow_fill)
        self.d.rounded_rectangle((x0, y0, x1, y1), radius * SS, fill=fill,
                                 outline=outline if width else None, width=int(width * SS))

    def rect(self, xy, fill):
        self.d.rectangle([v * SS for v in xy], fill=fill)

    def line(self, pts, fill, width):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=int(round(width * SS)), joint="curve")

    def ellipse(self, xy, fill=None, outline=None, width=0):
        self.d.ellipse([v * SS for v in xy], fill=fill, outline=outline, width=int(round(width * SS)))

    def arc(self, xy, start, end, fill, width):
        self.d.arc([v * SS for v in xy], start, end, fill=fill, width=int(round(width * SS)))

    def pie(self, xy, start, end, fill):
        self.d.pieslice([v * SS for v in xy], start, end, fill=fill)

    def text(self, xy, s, weight, size, fill=INK, anchor="la", stroke=0, stroke_fill=WHITE):
        self.d.text((xy[0] * SS, xy[1] * SS), s, font=font(weight, size * SS), fill=fill, anchor=anchor,
                    stroke_width=int(round(stroke * SS)), stroke_fill=stroke_fill)

    def tw(self, s, weight, size):
        b = font(weight, size * SS).getbbox(s)
        return (b[2] - b[0]) / SS

    def image(self):
        from PIL import Image
        return self.im.resize((self.w, self.h), Image.LANCZOS)


def fit_size(s, weight, size, max_w, min_size=14):
    """Taille de police pour que `s` tienne dans max_w."""
    while size > min_size:
        b = font(weight, size).getbbox(s)
        if b[2] - b[0] <= max_w:
            return size
        size -= 2
    return min_size


def wrap(s, weight, size, max_w, max_lines=2):
    words, lines, cur = (s or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        b = font(weight, size).getbbox(t)
        if b[2] - b[0] <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def transform(im, scale=1.0, alpha=1.0, dx=0, dy=0, rot=0.0, pivot=None):
    """Mise à l'échelle / rotation / décalage / transparence d'une image dans une toile de même taille."""
    from PIL import Image
    if scale == 1.0 and alpha >= 1.0 and not dx and not dy and not rot:
        return im
    w, h = im.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    src = im
    if rot:
        src = src.rotate(rot, resample=Image.BICUBIC, center=pivot)
    if scale != 1.0 and scale > 0.01:
        cx, cy = pivot or (w / 2, h / 2)
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        src = src.resize((sw, sh), Image.BILINEAR)
        ox, oy = round(cx - cx * scale + dx), round(cy - cy * scale + dy)
    elif scale <= 0.01:
        return out
    else:
        ox, oy = round(dx), round(dy)
    out.alpha_composite(src, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))
    if alpha < 1.0:
        a = out.getchannel("A").point(lambda v: int(v * clamp(alpha)))
        out.putalpha(a)
    return out


# ── les fx ────────────────────────────────────────────────────────────────────

# rythme posé : chaque type se déroule plus ou moins lentement (1 = vitesse de base)
SLOW = {"label": 1.2, "counter": 1.5, "receipt": 1.6, "bars": 1.9, "pie": 1.6, "list": 2.1, "split": 1.8,
        "timeline": 1.9, "stamp": 1.0, "title": 1.0, "sheet": 1.0, "intro": 1.0, "outro": 1.0, "route": 1.5,
        "chapter": 1.2}


class Fx:
    """Base : taille de la toile, position sur l'image, fin de l'animation, bruitages."""
    anim_end = 0.5

    def __init__(self, spec, geo, state=None):
        self.spec, self.geo = spec, geo
        self.state = state if state is not None else {}  # partagé d'un fx à l'autre (ticket, fiche)
        self.k = geo["k"]
        self.sfx = []
        self.slow = SLOW.get((spec or {}).get("type"), 1.0)
        self.times = [float(x) for x in (spec or {}).get("_times") or []]  # items calés sur la voix (s)
        if self.times:
            self.slow = 1.0
        self.setup()

    def setup(self):
        pass

    def frame(self, t):
        raise NotImplementedError

    # temps « réel » (ralenti selon le type)
    def at(self, t):
        return self.frame(t / self.slow)

    @property
    def length(self):
        return self.anim_end * self.slow

    @property
    def sounds(self):
        return [(t * self.slow, n, g) for t, n, g in self.sfx]


def _panel(geo):
    return geo["panel"]


class Label(Fx):
    anim_end = 0.45

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.txt = (self.spec.get("text") or "").upper()[:40]
        self.size = fit_size(self.txt, 900, 84 * k, pw * 0.6)
        tw = font(900, self.size).getbbox(self.txt)
        self.tw, self.th = tw[2] - tw[0], self.size * 1.05
        self.padx, self.pady = 26 * k, 14 * k
        self.w = int(self.tw + 2 * self.padx + 40 * k)
        self.h = int(self.th + 2 * self.pady + 36 * k)
        self.x, self.y = int(px + 36 * k), int(py + 34 * k)
        self.sfx = [(0.0, "pop", 0.8)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        bw = self.tw + 2 * self.padx
        grow = ease_out(seg(t, 0.05, 0.3))
        x0, y0 = 6 * k, 6 * k
        mw = max(8 * k, bw * grow)
        p.box((x0, y0, x0 + mw, y0 + self.th + 2 * self.pady), YELLOW, width=5 * k, radius=10 * k, shadow=8 * k)
        txt = Pad(self.w, self.h)  # le texte n'apparaît que sur la partie déjà surlignée
        txt.text((x0 + self.padx, y0 + self.pady + self.th * 0.46), self.txt, 900, self.size, anchor="lm")
        from PIL import Image, ImageDraw
        mask = Image.new("L", txt.im.size, 0)
        ImageDraw.Draw(mask).rectangle((0, 0, int((x0 + mw) * SS), txt.im.size[1]), fill=255)
        p.im.paste(txt.im, (0, 0), Image.composite(txt.im.getchannel("A"), Image.new("L", mask.size, 0), mask))
        im = p.image()
        s = 0.72 + 0.28 * ease_back(seg(t, 0.0, 0.3))
        return transform(im, scale=s, alpha=seg(t, 0, 0.08), pivot=(x0, y0 + self.th / 2))


class Counter(Fx):
    anim_end = 1.55

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.to = parse_number(self.spec.get("to") or "") or ("", 0.0, "", 0, False)
        fr = parse_number(self.spec.get("from") or "")
        self.start = fr[1] if fr else 0.0
        self.label = (self.spec.get("label") or "").upper()[:48]
        self.w, self.h = int(800 * k), int(380 * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * CENTER_Y - self.h / 2)
        final = fmt_number(*self.to)
        self.size = fit_size(final, 900, 150 * k, self.w - 110 * k)
        ticks = [(0.25 + i * 0.07, "tick", 0.5) for i in range(int((1.35 - 0.25) / 0.07))]
        self.sfx = [(0.0, "pop", 0.7)] + ticks + [(1.4, "ding", 0.7)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 22 * k
        p.box((m, m, self.w - m - 10 * k, self.h - m - 10 * k), WHITE, width=5 * k, radius=26 * k, shadow=10 * k)
        pre, val, suf, dec, commas = self.to
        v = self.start + (val - self.start) * ease_out(seg(t, 0.25, 1.35))
        s = fmt_number(pre, v, suf, dec, commas)
        cx = (self.w - 10 * k) / 2
        p.text((cx, self.h * 0.43), s, 900, self.size, fill=RED if t >= 1.35 else INK, anchor="mm")
        if self.label:
            ls = fit_size(self.label, 800, 40 * k, self.w - 120 * k)
            p.text((cx, self.h * 0.72), self.label, 800, ls, fill=GREY, anchor="mm")
        im = p.image()
        return transform(im, scale=0.6 + 0.4 * ease_back(seg(t, 0, 0.3)), alpha=seg(t, 0, 0.1))


def _amount(s):
    n = parse_number(s or "")
    return n[1] if n else None


def recap_filter(old, asked, old_total, total):
    """Lignes vraiment nouvelles d'un ticket : un récapitulatif (« les soins, 38 688 $ ; l'hospice, 0 $… »)
    ne rajoute pas une ligne dont le montant est déjà sur le ticket, sauf si le total annoncé augmente
    exactement de ce montant (deux postes différents au même prix)."""
    seen = [_amount(a) for _, a in old]
    ot, tt = _amount(old_total), _amount(total)
    out = []
    for item, amount in asked:
        v = _amount(amount)
        if v is not None and v in seen and not (v and ot is not None and tt is not None and abs(ot + v - tt) < 0.5):
            continue
        out.append((item, amount))
        seen.append(v)
        if ot is not None and v is not None:
            ot += v
    return out


class Receipt(Fx):
    """Ticket de caisse : garde les lignes des tickets précédents (state["receipt"])."""

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        st = self.state.setdefault("receipt", {"items": [], "total": None})
        self.old = list(st["items"])
        self.old_total = st["total"]
        self.total = str(self.spec.get("total") or "")
        asked = [(str(i.get("item") or "")[:30], str(i.get("amount") or "")) for i in self.spec.get("items") or []
                 if isinstance(i, dict)]
        self.new = recap_filter(self.old, asked, self.old_total, self.total)
        if asked and not self.new and self.old_total:  # simple récapitulatif : le total reste celui du ticket
            self.total = self.old_total
        st["items"] = self.old + self.new
        st["total"] = self.total or st["total"]
        rows = (self.old + self.new)[-6:]
        self.n_old = max(0, len(rows) - len(self.new))
        self.rows = rows
        self.more = len(self.old + self.new) > 6
        self.w = int(640 * k)
        self.row_h = 62 * k
        self.head = 124 * k
        self.foot = 132 * k
        self.h = int(self.head + self.row_h * (len(rows) + (0.7 if self.more else 0)) + self.foot + 60 * k)
        self.x = int(px + pw - self.w - 34 * k)
        self.y = int(py + 30 * k)
        self.type_start, self.type_per = 0.45, 0.45
        self.roll_start = self.type_start + self.type_per * len(self.new) + 0.1
        self.roll_end = self.roll_start + 0.7
        self.circle_end = self.roll_end + 0.45
        self.anim_end = self.circle_end + 0.05
        sfx = [(0.0, "whoosh", 0.7)]
        for j in range(len(self.new)):
            t0 = self.type_start + j * self.type_per
            sfx += [(t0 + i * 0.045, "type", 0.55) for i in range(7)]
        sfx += [(self.roll_start + i * 0.06, "tick", 0.35) for i in range(10)]
        sfx.append((self.roll_end, "kaching", 0.8))
        self.sfx = sfx

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 8 * k
        x0, x1 = m, self.w - 18 * k
        y1 = self.h - 22 * k
        # papier + bord inférieur en dents de scie
        teeth = 14
        tw_ = (x1 - x0) / teeth
        body = [(x0, m), (x1, m), (x1, y1)]
        for i in range(teeth):
            body += [(x1 - tw_ * (i + 0.5), y1 + 14 * k), (x1 - tw_ * (i + 1), y1)]
        sh = [(x + 10 * k, y + 10 * k) for x, y in body]
        p.d.polygon([(x * SS, y * SS) for x, y in sh], fill=INK)
        p.d.polygon([(x * SS, y * SS) for x, y in body], fill=PAPER, outline=INK, width=int(4 * k * SS))
        cx = (x0 + x1) / 2
        p.text((cx, m + 54 * k), "RUNNING TAB", 900, 48 * k, anchor="mm")
        dash_y = m + self.head - 18 * k

        def dashes(y):
            x = x0 + 22 * k
            while x < x1 - 22 * k:
                p.line([(x, y), (min(x + 14 * k, x1 - 22 * k), y)], INK, 3 * k)
                x += 24 * k
        dashes(dash_y)
        y = dash_y + 18 * k
        if self.more:
            p.text((x0 + 26 * k, y + self.row_h * 0.35), "…", 800, 28 * k, fill=GREY, anchor="lm")
            y += self.row_h * 0.7
        for j, (item, amount) in enumerate(self.rows):
            new_j = j - self.n_old
            if new_j >= 0:
                t0 = self.type_start + new_j * self.type_per
                if t < t0:
                    break
                prog = seg(t, t0, t0 + self.type_per * 0.9)
                if prog < 1:
                    hl = 1.0
                else:
                    hl = 1 - seg(t, self.roll_end, self.roll_end + 0.6)
                if hl > 0:
                    col = tuple(int(255 - (255 - c) * hl) for c in YELLOW)
                    p.rect((x0 + 14 * k, y + 4 * k, x1 - 14 * k, y + self.row_h - 4 * k), col + (255,))
                n = int(round(len(item) * prog))
                s_item = item[:n]
                s_amt = amount if prog >= 1 else ""
            else:
                s_item, s_amt = item, amount
            isz = fit_size(item, 700, 36 * k, (x1 - x0) * 0.6)
            p.text((x0 + 26 * k, y + self.row_h / 2), s_item, 700, isz, anchor="lm")
            if s_amt:
                p.text((x1 - 26 * k, y + self.row_h / 2), s_amt, 800, 36 * k, anchor="rm")
            y += self.row_h
        ty = m + self.head + self.row_h * (len(self.rows) + (0.7 if self.more else 0)) + 6 * k
        dashes(ty)
        p.text((x0 + 26 * k, ty + 58 * k), "TOTAL", 900, 50 * k, anchor="lm")
        tot = parse_number(self.total)
        if tot:
            old = parse_number(self.old_total or "")
            v0 = old[1] if old else 0.0
            v = v0 + (tot[1] - v0) * ease_out(seg(t, self.roll_start, self.roll_end))
            s_tot = fmt_number(tot[0], v, tot[2], tot[3], tot[4])
        else:
            s_tot = self.total
        tsz = fit_size(fmt_number(*tot) if tot else s_tot, 900, 56 * k, (x1 - x0) * 0.55)
        tx = x1 - 26 * k
        p.text((tx, ty + 58 * k), s_tot, 900, tsz, fill=RED if t >= self.roll_end else INK, anchor="rm")
        cp = seg(t, self.roll_end, self.circle_end)
        if cp > 0:  # cercle rouge tracé à la main autour du total
            tw_ = p.tw(s_tot, 900, tsz)
            cxx, cyy = tx - tw_ / 2, ty + 58 * k
            rx, ry = tw_ / 2 + 24 * k, 42 * k
            pts = []
            steps = 48
            for i in range(int(steps * cp * 1.08) + 1):
                a = -2.2 + 2 * math.pi * 1.08 * i / steps
                wob = 1 + 0.04 * math.sin(3 * a)
                pts.append((cxx + rx * wob * math.cos(a), cyy + ry * wob * math.sin(a)))
            if len(pts) > 1:
                p.line(pts, RED, 6 * k)
        im = p.image()
        slide = (1 - ease_out(seg(t, 0, 0.35))) * (self.w + 60 * k)
        return transform(im, dx=slide, alpha=seg(t, 0, 0.1))


class Bars(Fx):
    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        items = [i for i in self.spec.get("items") or [] if isinstance(i, dict)][:4]
        self.items = []
        for i in items:
            v = i.get("value")
            try:
                v = float(v)
            except (TypeError, ValueError):
                pn = parse_number(str(i.get("display") or ""))
                v = pn[1] if pn else 0.0
            self.items.append((str(i.get("label") or "")[:34], v, str(i.get("display") or "")))
        self.title = (self.spec.get("title") or "").upper()[:44]
        self.w, self.h = int(940 * k), int(640 * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * CENTER_Y - self.h / 2)
        n = max(1, len(self.items))
        self.anim_end = 0.35 + 0.18 * n + 0.55
        self.sfx = [(0.0, "pop", 0.6)] + [(0.35 + 0.18 * j + 0.5, "pop", 0.5) for j in range(n)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 16 * k
        p.box((m, m, self.w - 26 * k, self.h - 26 * k), WHITE, width=5 * k, radius=26 * k, shadow=10 * k)
        if self.title:
            p.text(((self.w - 10 * k) / 2, 70 * k), self.title, 900,
                   fit_size(self.title, 900, 44 * k, self.w - 120 * k), anchor="mm")
        n = max(1, len(self.items))
        vmax = max([v for _, v, _ in self.items] + [1e-9])
        base_y = self.h - 132 * k
        top_y = 170 * k
        area_w = self.w - 140 * k
        slot = area_w / n
        bw = min(150 * k, slot * 0.56)
        big = max(range(n), key=lambda j: self.items[j][1]) if self.items else 0
        p.line([(50 * k, base_y), (self.w - 60 * k, base_y)], INK, 5 * k)
        for j, (label, v, disp) in enumerate(self.items):
            cx = 70 * k + slot * (j + 0.5)
            g = ease_out(seg(t, 0.35 + 0.18 * j, 0.35 + 0.18 * j + 0.5))
            hgt = (base_y - top_y - 40 * k) * (v / vmax) * g
            col = RED if j == big and n > 1 else BLUE
            if hgt > 2:
                p.box((cx - bw / 2, base_y - hgt, cx + bw / 2, base_y), col, width=4 * k, radius=8 * k, shadow=0)
            if g >= 1 and disp:
                a = seg(t, 0.35 + 0.18 * j + 0.5, 0.35 + 0.18 * j + 0.7)
                if a > 0:
                    p.text((cx, base_y - hgt - 30 * k), disp, 900,
                           fit_size(disp, 900, 42 * k, slot * 0.95), anchor="mm")
            lines = wrap(label, 800, 30 * k, slot * 0.94)
            for li, ln in enumerate(lines):
                p.text((cx, base_y + 34 * k + li * 34 * k), ln, 800, 30 * k, fill=GREY, anchor="mm")
        im = p.image()
        return transform(im, scale=0.7 + 0.3 * ease_back(seg(t, 0, 0.3)), alpha=seg(t, 0, 0.1))


class Pie(Fx):
    anim_end = 1.5

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        items = [i for i in self.spec.get("items") or [] if isinstance(i, dict)][:6]
        vals = []
        for i in items:
            try:
                vals.append((str(i.get("label") or "")[:26], max(0.0, float(i.get("value")))))
            except (TypeError, ValueError):
                pn = parse_number(str(i.get("value") or ""))
                vals.append((str(i.get("label") or "")[:26], pn[1] if pn else 1.0))
        tot = sum(v for _, v in vals) or 1.0
        self.items = [(l, v / tot) for l, v in vals]
        self.title = (self.spec.get("title") or "").upper()[:40]
        self.w, self.h = int(940 * k), int(580 * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * CENTER_Y - self.h / 2)
        self.sfx = [(0.0, "whoosh", 0.5)] + [(0.3 + 0.9 * sum(v for _, v in self.items[:j]), "pop", 0.4)
                                              for j in range(len(self.items))]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 16 * k
        p.box((m, m, self.w - 26 * k, self.h - 26 * k), WHITE, width=5 * k, radius=26 * k, shadow=10 * k)
        if self.title:
            p.text(((self.w - 10 * k) / 2, 66 * k), self.title, 900,
                   fit_size(self.title, 900, 42 * k, self.w - 120 * k), anchor="mm")
        cx, cy, r = 250 * k, 310 * k, 180 * k
        sweep = 360 * ease_in_out(seg(t, 0.3, 1.2))
        a0 = -90.0
        p.ellipse((cx - r - 3 * k, cy - r - 3 * k, cx + r + 3 * k, cy + r + 3 * k), fill=INK)
        p.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(235, 235, 235))
        for j, (label, frac) in enumerate(self.items):
            a1 = a0 + 360 * frac
            end = min(a1, -90 + sweep)
            if end > a0:
                p.pie((cx - r, cy - r, cx + r, cy + r), a0, end, PALETTE[j % len(PALETTE)] + (255,))
            a0 = a1
        ri = r * 0.52
        p.ellipse((cx - ri - 3 * k, cy - ri - 3 * k, cx + ri + 3 * k, cy + ri + 3 * k), fill=INK)
        p.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=WHITE)
        ly = 160 * k
        step = min(70 * k, (self.h - 210 * k) / max(1, len(self.items)))
        acc = 0.0
        for j, (label, frac) in enumerate(self.items):
            vis = seg(t, 0.3 + 0.9 * acc, 0.3 + 0.9 * acc + 0.15)
            acc += frac
            if vis <= 0:
                continue
            y = ly + j * step
            p.box((480 * k, y - 16 * k, 512 * k, y + 16 * k), PALETTE[j % len(PALETTE)], width=3 * k,
                  radius=6 * k, shadow=0)
            p.text((530 * k, y), label, 800, fit_size(label, 800, 34 * k, 250 * k), anchor="lm")
            p.text((self.w - 60 * k, y), f"{round(frac * 100)}%", 900, 36 * k, anchor="rm")
        im = p.image()
        return transform(im, scale=0.7 + 0.3 * ease_back(seg(t, 0, 0.3)), alpha=seg(t, 0, 0.1))


class ListFx(Fx):
    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.title = (self.spec.get("title") or "").upper()[:40]
        self.items = [str(i.get("text") if isinstance(i, dict) else i)[:60] for i in self.spec.get("items") or []
                      if str(i.get("text") if isinstance(i, dict) else i).strip()][:6]
        self.w = int(900 * k)
        self.row = 80 * k
        self.h = int(140 * k + self.row * len(self.items) + 40 * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * CENTER_Y - self.h / 2)
        self.step = 0.32
        if len(self.times) != len(self.items):
            self.times = [0.3 + self.step * j for j in range(len(self.items))]
        self.anim_end = (self.times[-1] if self.times else 0.3) + 0.45
        self.sfx = [(0.0, "pop", 0.6)] + [(t, "pop", 0.45) for t in self.times]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 16 * k
        p.box((m, m, self.w - 26 * k, self.h - 26 * k), WHITE, width=5 * k, radius=26 * k, shadow=10 * k)
        if self.title:
            p.text((60 * k, 76 * k), self.title, 900, fit_size(self.title, 900, 44 * k, self.w - 140 * k),
                   anchor="lm")
        for j, it in enumerate(self.items):
            a = seg(t, self.times[j], self.times[j] + 0.3)
            if a <= 0:
                continue
            y = 140 * k + self.row * j + self.row / 2
            dx = (1 - ease_out(a)) * -40 * k
            r = 24 * k * (0.6 + 0.4 * ease_back(a))
            cx = 78 * k + dx
            p.ellipse((cx - r, y - r, cx + r, y + r), fill=GREEN, outline=INK, width=3 * k)
            p.line([(cx - 9 * k, y + 1 * k), (cx - 2 * k, y + 8 * k), (cx + 10 * k, y - 8 * k)], WHITE, 5 * k)
            p.text((122 * k + dx, y), it, 800, fit_size(it, 800, 40 * k, self.w - 190 * k), anchor="lm")
        im = p.image()
        return transform(im, scale=0.75 + 0.25 * ease_back(seg(t, 0, 0.3)), alpha=seg(t, 0, 0.1))


class Split(Fx):
    anim_end = 1.15

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.l = self.spec.get("left") or {}
        self.r = self.spec.get("right") or {}
        self.w, self.h = int(980 * k), int(400 * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * CENTER_Y - self.h / 2)
        self.sfx = [(0.0, "pop", 0.6), (0.35, "pop", 0.6), (0.7, "stamp", 0.45)]

    def _col(self, p, x0, x1, data, a, col):
        k = self.k
        if a <= 0:
            return
        y0, y1 = 30 * k, self.h - 40 * k
        s = 0.7 + 0.3 * ease_back(a)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hw, hh = (x1 - x0) / 2 * s, (y1 - y0) / 2 * s
        p.box((cx - hw, cy - hh, cx + hw, cy + hh), WHITE, width=5 * k, radius=24 * k, shadow=10 * k)
        p.rect((cx - hw + 5 * k, cy - hh + 5 * k, cx + hw - 5 * k, cy - hh + 70 * k * s), col + (255,))
        title = str(data.get("title") or "").upper()[:26]
        val = str(data.get("value") or "")[:18]
        sub = str(data.get("sub") or "")[:40]
        p.text((cx, cy - hh + 38 * k * s), title, 900, fit_size(title, 900, 30 * k * s, hw * 1.7), fill=WHITE,
               anchor="mm")
        p.text((cx, cy + 10 * k * s), val, 900, fit_size(val, 900, 66 * k * s, hw * 1.8), anchor="mm")
        if sub:
            p.text((cx, cy + 80 * k * s), sub, 700, fit_size(sub, 700, 24 * k * s, hw * 1.8), fill=GREY,
                   anchor="mm")

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        mid = self.w / 2
        self._col(p, 20 * k, mid - 60 * k, self.l, seg(t, 0, 0.3), BLUE)
        self._col(p, mid + 50 * k, self.w - 30 * k, self.r, seg(t, 0.35, 0.65), RED)
        a = seg(t, 0.7, 0.95)
        if a > 0:
            r = 56 * k * (0.5 + 0.5 * ease_back(a))
            cy = self.h / 2 - 5 * k
            p.ellipse((mid - r + 6 * k, cy - r + 6 * k, mid + r + 6 * k, cy + r + 6 * k), fill=INK)
            p.ellipse((mid - r, cy - r, mid + r, cy + r), fill=YELLOW, outline=INK, width=5 * k)
            p.text((mid, cy), "VS", 900, 44 * k * (r / (56 * k)), anchor="mm")
        return p.image()


class Timeline(Fx):
    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.items = [i for i in self.spec.get("items") or [] if isinstance(i, dict)][:5]
        self.title = (self.spec.get("title") or "").upper()[:44]
        self.w, self.h = int(1240 * k), int(400 * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * 0.5 - self.h / 2)
        n = max(1, len(self.items))
        self.draw_end = 0.3 + 0.35 * n
        self.anim_end = self.draw_end + 0.3
        self.sfx = [(0.0, "pop", 0.5)] + [(0.3 + 0.35 * (j + 0.5), "tick", 0.8) for j in range(n)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 16 * k
        p.box((m, m, self.w - 26 * k, self.h - 26 * k), WHITE, width=5 * k, radius=26 * k, shadow=10 * k)
        if self.title:
            p.text(((self.w - 10 * k) / 2, 64 * k), self.title, 900,
                   fit_size(self.title, 900, 42 * k, self.w - 120 * k), anchor="mm")
        n = max(1, len(self.items))
        x0, x1, y = 80 * k, self.w - 100 * k, 212 * k
        prog = seg(t, 0.3, self.draw_end)
        xe = x0 + (x1 - x0) * prog
        p.line([(x0, y), (xe, y)], INK, 7 * k)
        if prog >= 1:
            p.d.polygon([((x1 + 8 * k) * SS, (y - 16 * k) * SS), ((x1 + 34 * k) * SS, y * SS),
                         ((x1 + 8 * k) * SS, (y + 16 * k) * SS)], fill=INK)
        slot = (x1 - x0) / n
        for j, it in enumerate(self.items):
            cx = x0 + slot * (j + 0.5)
            a = seg(t, 0.3 + 0.35 * (j + 0.5), 0.3 + 0.35 * (j + 0.5) + 0.2)
            if a <= 0:
                continue
            r = 16 * k * (0.5 + 0.5 * ease_back(a))
            p.ellipse((cx - r, y - r, cx + r, y + r), fill=YELLOW, outline=INK, width=4 * k)
            lab = str(it.get("label") or "")[:22]
            sub = str(it.get("sub") or "")[:30]
            p.text((cx, y - 48 * k), lab, 900, fit_size(lab, 900, 36 * k, slot * 0.95), anchor="mm")
            if sub:
                for li, ln in enumerate(wrap(sub, 700, 28 * k, slot * 0.92)):
                    p.text((cx, y + 50 * k + li * 32 * k), ln, 700, 28 * k, fill=GREY, anchor="mm")
        im = p.image()
        return transform(im, scale=0.8 + 0.2 * ease_back(seg(t, 0, 0.3)), alpha=seg(t, 0, 0.1))


class Stamp(Fx):
    """Tampon bien droit, en bas au centre du panneau (il ne cache pas les visages de l'image)."""
    anim_end = 0.4

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.txt = (self.spec.get("text") or "PAID").upper()[:18]
        self.size = fit_size(self.txt, "stamp", 84 * k, pw * 0.4)
        tw = font("stamp", self.size).getbbox(self.txt)
        self.tw = tw[2] - tw[0]
        bw, bh = self.tw + 70 * k, self.size * 1.5
        self.w, self.h = int(bw * 1.45), int(bh * 1.6)  # marge pour l'arrivée (le tampon part plus grand)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * 0.83 - self.h / 2)
        self.sfx = [(0.14, "stamp", 0.9)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        cx, cy = self.w / 2, self.h / 2
        bw, bh = self.tw + 70 * k, self.size * 1.5
        red = RED + (235,)
        p.d.rounded_rectangle([(cx - bw / 2) * SS, (cy - bh / 2) * SS, (cx + bw / 2) * SS, (cy + bh / 2) * SS],
                              14 * k * SS, fill=(255, 250, 240, 225))
        p.d.rounded_rectangle([(cx - bw / 2) * SS, (cy - bh / 2) * SS, (cx + bw / 2) * SS, (cy + bh / 2) * SS],
                              14 * k * SS, outline=red, width=int(9 * k * SS))
        p.d.rounded_rectangle([(cx - bw / 2 + 14 * k) * SS, (cy - bh / 2 + 14 * k) * SS,
                               (cx + bw / 2 - 14 * k) * SS, (cy + bh / 2 - 14 * k) * SS],
                              8 * k * SS, outline=red, width=int(3 * k * SS))
        p.text((cx, cy + 4 * k), self.txt, "stamp", self.size, fill=red, anchor="mm")
        im = p.image()
        s = 1.4 - 0.4 * ease_out(seg(t, 0, 0.15))
        return transform(im, scale=s, alpha=seg(t, 0, 0.1) * 0.95)


class Title(Fx):
    """Écran titre de l'intro : bandeau papier, nom de la chaîne, titre qui claque, trait rouge."""
    anim_end = 1.9

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.kicker = (self.spec.get("kicker") or "").upper()[:40]
        self.pre = (self.spec.get("pre") or "").upper()[:40]
        self.main = (self.spec.get("main") or "").upper()[:34]
        self.w, self.h = int(pw * 0.78), int(430 * k)
        self.x = int(px + pw * 0.56 - self.w / 2)
        self.y = int(py + ph * 0.46 - self.h / 2)
        self.msize = fit_size(self.main, 900, 150 * k, self.w - 140 * k)
        self.psize = fit_size(self.pre, 900, 58 * k, self.w - 200 * k) if self.pre else 0
        self.sfx = [(0.0, "whoosh", 0.8), (0.75, "stamp", 0.9), (1.55, "kaching", 0.6)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 16 * k
        a = ease_out(seg(t, 0, 0.35))
        p.box((m, m + 40 * k, self.w - 26 * k, self.h - 26 * k), PAPER, width=6 * k, radius=28 * k, shadow=12 * k)
        if self.kicker:
            kw = p.tw(self.kicker, 900, 30 * k) + 44 * k
            p.box((56 * k, 18 * k, 56 * k + kw, 76 * k), YELLOW, width=5 * k, radius=10 * k, shadow=6 * k)
            p.text((56 * k + kw / 2, 47 * k), self.kicker, 900, 30 * k, anchor="mm")
        cx = (self.w - 10 * k) / 2
        y_pre = 150 * k
        if self.pre:
            n = int(round(len(self.pre) * seg(t, 0.3, 0.7)))
            p.text((cx, y_pre), self.pre[:n], 900, self.psize, fill=GREY, anchor="mm")
        y_main = 270 * k if self.pre else 225 * k
        sm = seg(t, 0.72, 0.9)
        if sm > 0:
            p.text((cx, y_main), self.main, 900, self.msize, fill=YELLOW, anchor="mm", stroke=7 * k,
                   stroke_fill=INK)
        u = ease_out(seg(t, 1.1, 1.5))
        if u > 0:
            tw_ = p.tw(self.main, 900, self.msize)
            x0 = cx - tw_ / 2
            p.line([(x0, y_main + self.msize * 0.62), (x0 + tw_ * u, y_main + self.msize * 0.58)], RED, 12 * k)
        im = p.image()
        if 0 < sm < 1:  # le titre claque : léger zoom sur toute la carte
            im = transform(im, scale=1 + 0.05 * (1 - ease_out(sm)))
        return transform(im, dx=(1 - a) * -self.w * 0.3, alpha=seg(t, 0, 0.12))


class Intro(Fx):
    """Intro plein écran (≈5 s) : fond du tableau, billets qui tombent, ticket de caisse qui s'imprime
    avec les lignes de la facture de la vidéo (montants cachés), tampon de la chaîne, titre qui
    claque, puis tout s'envole. Aucune image de la vidéo derrière."""
    anim_end = 5.4
    exit = False  # reste opaque jusqu'au bout : le fondu vers la première scène fait la transition

    def setup(self):
        import random
        k = self.k
        self.x, self.y = 0, 0
        self.w, self.h = int(self.geo["W"]), int(self.geo["H"])
        self.kicker = (self.spec.get("kicker") or "").upper()[:40]
        self.pre = (self.spec.get("pre") or "").upper()[:40]
        self.main = (self.spec.get("main") or "").upper()[:34]
        self.items = [str(i).upper()[:20] for i in self.spec.get("items") or []][:4] or ["THE BILL"]
        self.bg = self.spec.get("bg") or {}
        self.msize = fit_size(self.main, 900, 170 * k, self.w * 0.44)
        self.psize = fit_size(self.pre, 900, 66 * k, self.w * 0.42) if self.pre else 0
        rnd = random.Random(7)
        self.bills = [(rnd.uniform(0, self.w), rnd.uniform(-self.h, 0), rnd.uniform(0.6, 1.2) * k,
                       rnd.uniform(-40, 40), rnd.uniform(-90, 90), rnd.uniform(0.18, 0.32)) for _ in range(22)]
        self._base = None
        self.sfx = [(0.0, "whoosh", 0.7)] + [(0.7 + 0.28 * j + 0.05 * i, "type", 0.45) for j in range(len(self.items))
                                             for i in range(4)] + \
                   [(1.95, "stamp", 0.9), (2.55, "stamp", 0.7), (3.3, "kaching", 0.7), (4.85, "whoosh", 0.8)]

    def _background(self):
        from PIL import Image, ImageDraw
        if self._base is None:
            bgc = tuple(self.bg.get("rgb") or (30, 37, 48))
            dot = tuple(self.bg.get("dot") or (44, 53, 66))
            im = Image.new("RGBA", (self.w, self.h), bgc + (255,))
            d = ImageDraw.Draw(im)
            step = int(40 * self.k)
            for yy in range(step // 2, self.h, step):
                for xx in range(step // 2, self.w, step):
                    d.ellipse((xx - 2, yy - 2, xx + 2, yy + 2), fill=dot + (255,))
            self._base = im
        return self._base.copy()

    def frame(self, t):
        from PIL import Image
        k = self.k
        out = self._background()
        # billets qui tombent (derrière tout)
        bills = Pad(self.w, self.h)
        for bx, by, sc, rot, spin, speed in self.bills:
            y = by + t * self.h * speed * 1.4
            if y > self.h + 60 * k:
                continue
            a = math.radians(rot + spin * t)
            bw, bh = 120 * sc, 56 * sc
            pts = [(-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2)]
            pts = [(bx + px_ * math.cos(a) - py_ * math.sin(a), y + px_ * math.sin(a) + py_ * math.cos(a))
                   for px_, py_ in pts]
            bills.d.polygon([(x_ * SS, y_ * SS) for x_, y_ in pts], fill=(120, 185, 120, 170),
                            outline=(20, 60, 30, 210), width=int(3 * SS))
            inner = [(x_ * 0.78 + bx * 0.22, y_ * 0.7 + y * 0.3) for x_, y_ in pts]  # cadre intérieur du billet
            bills.d.polygon([(x_ * SS, y_ * SS) for x_, y_ in inner], outline=(30, 90, 45, 190), width=int(2 * SS))
            r = 12 * sc
            bills.d.ellipse(((bx - r) * SS, (y - r) * SS, (bx + r) * SS, (y + r) * SS), fill=(70, 140, 80, 200),
                            outline=(20, 60, 30, 210), width=int(2 * SS))
        out.alpha_composite(bills.image())
        p = Pad(self.w, self.h)
        # ticket de caisse (à droite) qui descend puis s'imprime
        rw, rx = 560 * k, self.w * 0.64
        drop = ease_out(seg(t, 0.1, 0.6))
        ry = -700 * k + drop * (170 * k + 700 * k)
        rows = len(self.items)
        rh = 170 * k + rows * 70 * k + 150 * k
        body = [(rx, ry), (rx + rw, ry), (rx + rw, ry + rh)]
        teeth = 14
        tw_ = rw / teeth
        for i in range(teeth):
            body += [(rx + rw - tw_ * (i + 0.5), ry + rh + 16 * k), (rx + rw - tw_ * (i + 1), ry + rh)]
        p.d.polygon([((x_ + 12 * k) * SS, (y_ + 12 * k) * SS) for x_, y_ in body], fill=INK)
        p.d.polygon([(x_ * SS, y_ * SS) for x_, y_ in body], fill=PAPER, outline=INK, width=int(5 * k * SS))
        p.text((rx + rw / 2, ry + 62 * k), "THE BILL", 900, 52 * k, anchor="mm")
        yy = ry + 128 * k
        for j, it in enumerate(self.items):
            a = seg(t, 0.7 + 0.28 * j, 0.95 + 0.28 * j)
            if a > 0:
                n = int(round(len(it) * a))
                p.text((rx + 34 * k, yy + 35 * k), it[:n], 800, fit_size(it, 800, 36 * k, rw * 0.6), anchor="lm")
                if a >= 1:
                    p.text((rx + rw - 34 * k, yy + 35 * k), "$???", 900, 36 * k, fill=GREY, anchor="rm")
            yy += 70 * k
        p.line([(rx + 30 * k, yy + 12 * k), (rx + rw - 30 * k, yy + 12 * k)], INK, 4 * k)
        if t >= 1.9:
            blink = RED if int((t - 1.9) * 3) % 2 == 0 else INK
            p.text((rx + 34 * k, yy + 70 * k), "TOTAL", 900, 52 * k, anchor="lm")
            p.text((rx + rw - 34 * k, yy + 70 * k), "$???", 900, 58 * k, fill=blink, anchor="rm")
        # nom de la chaîne en tampon, puis titre
        cx = self.w * 0.405  # à droite du prof (en bas à gauche), à gauche du ticket
        if self.kicker and t >= 1.8:
            a = seg(t, 1.8, 1.98)
            kw = p.tw(self.kicker, 900, 44 * k) + 60 * k
            sc = 1.6 - 0.6 * ease_out(a)
            x0, y0 = cx - kw * sc / 2, self.h * 0.17 - 40 * k * sc
            p.box((x0, y0, x0 + kw * sc, y0 + 80 * k * sc), YELLOW, width=6 * k, radius=12 * k, shadow=8 * k)
            p.text((cx, y0 + 40 * k * sc), self.kicker, 900, 44 * k * sc, anchor="mm")
        if self.pre:
            n = int(round(len(self.pre) * seg(t, 2.1, 2.45)))
            p.text((cx, self.h * 0.31), self.pre[:n], 900, self.psize, fill=WHITE, anchor="mm")
        if t >= 2.5:
            a = seg(t, 2.5, 2.7)
            sc = 1.5 - 0.5 * ease_out(a)
            p.text((cx, self.h * 0.44), self.main, 900, self.msize * sc, fill=YELLOW, anchor="mm", stroke=9 * k * sc,
                   stroke_fill=INK)
            u = ease_out(seg(t, 2.9, 3.3))
            if u > 0:
                tw_ = p.tw(self.main, 900, self.msize)
                p.line([(cx - tw_ / 2, self.h * 0.44 + self.msize * 0.62),
                        (cx - tw_ / 2 + tw_ * u, self.h * 0.44 + self.msize * 0.58)], RED, 14 * k)
        im = p.image()
        out.alpha_composite(im)
        e = seg(t, 4.8, 5.4)  # sortie : tout grossit et s'efface vers la première scène
        if e > 0:
            fg = transform(im, scale=1 + 0.25 * ease_in_out(e), alpha=1 - e)
            out = self._background()
            out.alpha_composite(bills.image())
            out.alpha_composite(fg)
        return out


class Sheet(Fx):
    """Fiche à tirets qui REMPLACE l'image de la scène : titre surligné, puis une ligne « — … »
    qui apparaît au moment où la voix la dit (spec["_times"], en secondes depuis le début du fx)."""
    FULL = True

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.x, self.y, self.w, self.h = int(px), int(py), int(pw), int(ph)
        self.title = (self.spec.get("title") or "").upper()[:40]
        items = []
        for it in self.spec.get("items") or []:
            txt = it.get("text") if isinstance(it, dict) else it
            if str(txt or "").strip():
                items.append(str(txt).strip()[:46])
        n = max(1, len(items))
        if len(self.times) != len(items):
            self.times = [0.6 + 0.9 * j for j in range(n)]
        # suite de la fiche de la scène d'avant (même titre) : ses lignes restent, les nouvelles s'ajoutent
        st = self.state.get("sheet") or {}
        self.cont = bool(self.spec.get("_cont")) and st.get("title") == self.title
        carry = list(st.get("items") or []) if self.cont else []
        cap = 8  # lignes visibles au maximum (la police s'adapte)
        self.state["sheet"] = {"title": self.title, "items": (carry + items)[-cap:]}
        keep = max(0, min(len(carry), cap - len(items)))
        self.items = (carry[-keep:] if keep else []) + items[:cap]
        self.times = [-1.0] * keep + [max(0.2 if self.cont else 0.45, t) for t in self.times][:cap]
        self.exit = not self.spec.get("_hold")  # la fiche continue à la scène suivante : pas de fondu
        rows = max(len(self.items), int(self.spec.get("_rows") or 0), 1)  # même hauteur sur toute la fiche
        self.row = min(110 * k, (self.h - 230 * k) / min(8, rows))
        self.size = min(60 * k, self.row * 0.56)
        self.anim_end = (self.times[-1] if self.times else 0.6) + 0.45
        self.sfx = ([] if self.cont else [(0.0, "whoosh", 0.5)]) + [(t, "pop", 0.5) for t in self.times if t >= 0]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        wipe = 1.0 if self.cont else ease_out(seg(t, 0, 0.4))
        p.box((0, 0, self.w, self.h), PAPER, width=6 * k, radius=16 * k, shadow=0)
        for j in range(len(self.items)):  # lignes de cahier, discrètes
            y = 210 * k + self.row * (j + 1)
            p.line([(290 * k, y), (self.w - 70 * k, y)], (214, 224, 238), 3 * k)
        if self.title:
            ts = fit_size(self.title, 900, 64 * k, self.w * 0.7)
            tw_ = p.tw(self.title, 900, ts)
            p.box((70 * k, 58 * k, 70 * k + tw_ + 56 * k, 58 * k + ts * 1.5), YELLOW, width=5 * k, radius=10 * k,
                  shadow=7 * k)
            p.text((98 * k, 58 * k + ts * 0.75), self.title, 900, ts, anchor="lm")
        y0 = 210 * k
        for j, it in enumerate(self.items):
            a = seg(t, self.times[j], self.times[j] + 0.35)
            if a <= 0:
                continue
            y = y0 + self.row * (j + 0.5)
            dx = (1 - ease_out(a)) * -50 * k
            # lignes décalées à droite : le prof (en bas à gauche) pointe la fiche sans cacher le texte
            sz = fit_size(it, 800, self.size, self.w - 460 * k)
            p.text((300 * k + dx, y), "—", 900, sz * 1.05, fill=RED, anchor="lm")
            p.text((374 * k + dx, y), it, 800, sz, anchor="lm")
        im = p.image()
        if wipe < 1:  # la fiche glisse du haut par-dessus l'image
            im = transform(im, dy=-(1 - wipe) * self.h * 0.35, alpha=seg(t, 0, 0.18))
        return im


class Outro(Intro):
    """Outro simple (≈7 s) : fond du tableau, nom de la chaîne en tampon, « THANKS FOR WATCHING »,
    « SEE YOU ON THE NEXT BILL », bouton SUBSCRIBE cliqué. La moitié droite reste calme (écrans de fin)."""
    anim_end = 2.9
    exit = False

    def setup(self):
        k = self.k
        self.x, self.y = 0, 0
        self.w, self.h = int(self.geo["W"]), int(self.geo["H"])
        self.kicker = (self.spec.get("kicker") or "").upper()[:40]
        self.line1 = (self.spec.get("line1") or "THANKS FOR WATCHING").upper()[:30]
        self.line2 = (self.spec.get("line2") or "SEE YOU ON THE NEXT BILL").upper()[:34]
        self.bg = self.spec.get("bg") or {}
        self.s1 = fit_size(self.line1, 900, 96 * k, self.w * 0.42)
        self.s2 = fit_size(self.line2, 900, 58 * k, self.w * 0.42)
        self._base = None
        self.sfx = [(0.0, "whoosh", 0.6), (0.25, "stamp", 0.7), (0.6, "pop", 0.6), (1.05, "pop", 0.6),
                    (1.45, "pop", 0.7), (2.25, "tick", 1.0), (2.35, "ding", 0.8)]

    def frame(self, t):
        k = self.k
        out = self._background()
        p = Pad(self.w, self.h)
        cx = self.w * 0.39
        if self.kicker:
            a = seg(t, 0.2, 0.36)
            if a > 0:
                kw = p.tw(self.kicker, 900, 40 * k) + 56 * k
                sc = 1.5 - 0.5 * ease_out(a)
                x0, y0 = cx - kw * sc / 2, self.h * 0.2 - 36 * k * sc
                p.box((x0, y0, x0 + kw * sc, y0 + 72 * k * sc), YELLOW, width=6 * k, radius=12 * k, shadow=8 * k)
                p.text((cx, y0 + 36 * k * sc), self.kicker, 900, 40 * k * sc, anchor="mm")
        a1 = seg(t, 0.55, 0.85)
        if a1 > 0:
            p.text((cx, self.h * 0.35), self.line1, 900, self.s1 * (0.8 + 0.2 * ease_back(a1)), fill=WHITE,
                   anchor="mm", stroke=6 * k, stroke_fill=INK)
        a2 = seg(t, 1.0, 1.3)
        if a2 > 0:
            p.text((cx, self.h * 0.46), self.line2, 900, self.s2 * (0.8 + 0.2 * ease_back(a2)), fill=YELLOW,
                   anchor="mm", stroke=5 * k, stroke_fill=INK)
        a3 = seg(t, 1.4, 1.7)
        if a3 > 0:  # bouton S'abonner, cliqué
            done = t >= 2.3
            label = "SUBSCRIBED" if done else "SUBSCRIBE"
            bw, bh = 470 * k, 110 * k
            sc = (0.6 + 0.4 * ease_back(a3)) * (0.94 if 2.2 <= t < 2.32 else 1.0)
            x0, y0 = cx - bw * sc / 2, self.h * 0.6 - bh * sc / 2
            p.box((x0, y0, x0 + bw * sc, y0 + bh * sc), (120, 128, 140) if done else RED, width=6 * k,
                  radius=22 * k, shadow=9 * k)
            ls = fit_size(label, 900, 50 * k * sc, bw * sc * (0.7 if done else 0.86))
            tx = cx - (24 * k if done else 0)
            p.text((tx, y0 + bh * sc / 2), label, 900, ls, fill=WHITE, anchor="mm")
            if done:  # coche dessinée (la police n'a pas le symbole)
                lx = tx + p.tw(label, 900, ls) / 2 + 22 * k
                ly = y0 + bh * sc / 2
                p.line([(lx, ly), (lx + 14 * k, ly + 14 * k), (lx + 40 * k, ly - 16 * k)], WHITE, 9 * k)
            c = seg(t, 1.8, 2.25)  # le curseur arrive puis clique
            if c > 0:
                mx = cx + bw * 0.62 - (bw * 0.35) * ease_out(c)
                my = self.h * 0.6 + bh * 0.9 - (bh * 0.55) * ease_out(c)
                arrow = [(mx, my), (mx, my + 56 * k), (mx + 15 * k, my + 42 * k), (mx + 27 * k, my + 66 * k),
                         (mx + 37 * k, my + 61 * k), (mx + 25 * k, my + 38 * k), (mx + 44 * k, my + 38 * k)]
                p.d.polygon([(x_ * SS, y_ * SS) for x_, y_ in arrow], fill=WHITE, outline=INK, width=int(4 * k * SS))
        out.alpha_composite(p.image())
        return out


class Chapter(Fx):
    """Carte de partie, en haut à gauche, façon jeu : pastille jaune « 3 » + « HAND » + « THE FENCE »
    (posée d'après le titre de partie « Hand 3: The fence »)."""
    anim_end = 0.75

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        kick = (self.spec.get("kicker") or "").upper().strip()
        m = re.match(r"^(.*?)\s*#?\s*(\d+)$", kick)
        self.word, self.num = (m.group(1).strip(), m.group(2)) if m else (kick, "")
        self.title = (self.spec.get("title") or "").upper()[:32]
        self.d = 150 * k  # pastille
        self.size = fit_size(self.title, 900, 60 * k, pw * 0.42)
        self.ksize = 30 * k
        tw = max(font(900, self.size).getbbox(self.title)[2], font(800, self.ksize).getbbox(self.word)[2])
        self.w = int(self.d + tw + 110 * k)
        self.h = int(self.d + 40 * k)
        self.x, self.y = int(px + 34 * k), int(py + 30 * k)
        self.sfx = [(0.0, "whoosh", 0.5), (0.22, "pop", 0.8)]

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        r = self.d / 2
        cy = 16 * k + r
        bx0 = 16 * k + r * 0.6
        grow = ease_out(seg(t, 0.1, 0.45))
        bx1 = bx0 + (self.w - 30 * k - bx0) * grow
        if grow > 0:  # bandeau blanc qui se déroule derrière la pastille
            p.box((bx0, cy - r * 0.8, bx1, cy + r * 0.8), WHITE, width=5 * k, radius=r * 0.5, shadow=8 * k)
            tx = 16 * k + self.d + 24 * k
            n = int(round(len(self.title) * seg(t, 0.3, 0.65)))
            if self.word:
                p.text((tx, cy - 22 * k), self.word, 800, self.ksize, fill=GREY, anchor="ls")
                p.text((tx, cy + 4 * k), self.title[:n], 900, self.size, anchor="lt")
            else:
                p.text((tx, cy), self.title[:n], 900, self.size, anchor="lm")
        a = ease_back(seg(t, 0.0, 0.3))
        rr = r * max(0.01, a)
        cx = 16 * k + r
        p.ellipse((cx - rr + 6 * k, cy - rr + 6 * k, cx + rr + 6 * k, cy + rr + 6 * k), fill=INK)
        p.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=YELLOW, outline=INK, width=6 * k)
        if self.num and a > 0.5:
            p.text((cx, cy + 2 * k), "#" + self.num if len(self.num) < 2 else self.num, 900,
                   fit_size("#" + self.num, 900, 70 * k * a, rr * 1.45), anchor="mm")
        im = p.image()
        return transform(im, dx=-(1 - ease_out(seg(t, 0, 0.3))) * 60 * k, alpha=seg(t, 0, 0.08))


class Route(Fx):
    """Trajet : deux points (départ, arrivée), une ligne pointillée en arc qui se trace avec un petit
    avion au bout, l'arrivée qui claque ; « sub » = comment ou combien (facultatif)."""
    anim_end = 1.5

    def setup(self):
        k = self.k
        px, py, pw, ph = _panel(self.geo)
        self.a = (self.spec.get("from") or "").upper()[:24]
        self.b = (self.spec.get("to") or "").upper()[:24]
        self.sub = (self.spec.get("sub") or "").upper()[:40]
        self.w, self.h = int(1120 * k), int((440 if self.sub else 380) * k)
        self.x = int(px + pw * 0.5 - self.w / 2)
        self.y = int(py + ph * CENTER_Y - self.h / 2)
        self.p0 = (190 * k, 250 * k)
        self.p1 = (self.w - 200 * k, 250 * k)
        self.ctl = ((self.p0[0] + self.p1[0]) / 2, 40 * k)
        # chaque nom a sa moitié de carte (noms longs : « CENTRAL NEW JERSEY », « PENNSYLVANIA »)
        self.lsize = min(fit_size(self.a, 900, 46 * k, 470 * k), fit_size(self.b, 900, 46 * k, 470 * k))
        self.sfx = [(0.0, "pop", 0.6), (0.3, "whoosh", 0.7), (1.2, "ding", 0.7)]

    def _pt(self, u):
        (x0, y0), (cx, cy), (x1, y1) = self.p0, self.ctl, self.p1
        return ((1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u * u * x1,
                (1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u * u * y1)

    def _pin(self, p, xy, s, fill):
        k = self.k
        x, y = xy
        r = 20 * k * s
        if r <= 0:
            return
        p.ellipse((x - r + 4 * k, y - r + 4 * k, x + r + 4 * k, y + r + 4 * k), fill=INK)
        p.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=INK, width=5 * k)

    def frame(self, t):
        k = self.k
        p = Pad(self.w, self.h)
        m = 16 * k
        p.box((m, m, self.w - 26 * k, self.h - 26 * k), WHITE, width=5 * k, radius=26 * k, shadow=10 * k)
        u = ease_in_out(seg(t, 0.3, 1.2))
        n = 40
        for j in range(n):  # pointillés jusqu'à la tête de la ligne
            a0, a1 = j / n, (j + 0.55) / n
            if a0 >= u:
                break
            p.line([self._pt(a0), self._pt(min(a1, u))], INK, 6 * k)
        self._pin(p, self.p0, ease_back(seg(t, 0.0, 0.25)), BLUE)
        arrive = seg(t, 1.2, 1.45)
        if arrive > 0:
            self._pin(p, self.p1, ease_back(arrive), RED)
        elif u > 0:  # petit avion (triangle) au bout de la ligne
            hx, hy = self._pt(u)
            bx, by = self._pt(max(0.0, u - 0.02))
            ang = math.atan2(hy - by, hx - bx)
            pts = [(hx + math.cos(ang) * 26 * k, hy + math.sin(ang) * 26 * k),
                   (hx + math.cos(ang + 2.5) * 18 * k, hy + math.sin(ang + 2.5) * 18 * k),
                   (hx + math.cos(ang - 2.5) * 18 * k, hy + math.sin(ang - 2.5) * 18 * k)]
            p.d.polygon([(x_ * SS, y_ * SS) for x_, y_ in pts], fill=YELLOW, outline=INK, width=int(4 * k * SS))
        ly = self.p0[1] + 62 * k
        lo, hi = m + 30 * k, self.w - 56 * k

        def cx(x, s):  # nom centré sous son point, mais jamais coupé par le bord de la carte
            half = p.tw(s, 900, self.lsize) / 2
            return min(max(x, lo + half), hi - half)
        p.text((cx(self.p0[0], self.a), ly), self.a, 900, self.lsize, anchor="mm")
        if arrive > 0:
            p.text((cx(self.p1[0], self.b), ly), self.b, 900, self.lsize, fill=RED, anchor="mm")
        if self.sub and t >= 1.2:
            p.text(((self.w - 10 * k) / 2, ly + 66 * k), self.sub, 800,
                   fit_size(self.sub, 800, 34 * k, self.w - 160 * k), fill=GREY, anchor="mm")
        im = p.image()
        return transform(im, scale=0.8 + 0.2 * ease_back(seg(t, 0, 0.3)), alpha=seg(t, 0, 0.1))


CLASSES = {"outro": Outro, "sheet": Sheet, "intro": Intro, "title": Title, "label": Label, "counter": Counter, "receipt": Receipt, "bars": Bars, "pie": Pie, "list": ListFx,
           "split": Split, "timeline": Timeline, "stamp": Stamp, "route": Route, "chapter": Chapter}


def make(spec, geo, state=None):
    cls = CLASSES.get((spec or {}).get("type"))
    return cls(spec, geo, state) if cls else None


def render_fx(fx, duration, out_dir, fps=30, exit_dur=EXIT):
    """Images d'un fx pour `duration` secondes → [(chemin, durée)] (animation, image tenue, sortie).

    La sortie (fondu adouci + léger recul) occupe les `exit_dur` dernières secondes ; tout est dans
    une toile de taille fixe (fx.w × fx.h), posée en (fx.x, fx.y) sur l'image."""
    os.makedirs(out_dir, exist_ok=True)
    fps = int(fps)
    duration = max(0.5, float(duration))
    tail = max(0.1, float(exit_dur)) if getattr(fx, "exit", True) else 0.0
    anim = min(fx.length, duration - tail)
    n_anim = max(1, int(math.ceil(anim * fps)))
    seq = []
    last = None
    for i in range(n_anim):
        im = fx.at(i / fps)
        path = os.path.join(out_dir, f"a{i:04d}.png")
        im.save(path, "PNG", compress_level=1)
        seq.append((path, 1 / fps))
        last = im
    final = fx.at(max(fx.length, anim))
    fpath = os.path.join(out_dir, "hold.png")
    final.save(fpath, "PNG", compress_level=1)
    hold = duration - n_anim / fps - tail
    if hold > 0:
        seq.append((fpath, hold))
    else:
        final = last
    if not tail:
        return seq
    n_exit = max(1, int(round(tail * fps)))
    for i in range(n_exit):
        a = 1 - ease_in_out((i + 1) / n_exit)  # la dernière image est vide : rien ne reste après la fin
        path = os.path.join(out_dir, f"x{i:02d}.png")
        transform(final, scale=1 - 0.05 * (1 - a), alpha=a).save(path, "PNG", compress_level=1)
        seq.append((path, 1 / fps))
    return seq


def blank(out_dir, w, h):
    from PIL import Image
    path = os.path.join(out_dir, "blank.png")
    if not os.path.isfile(path):
        Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0)).save(path, "PNG")
    return path


def write_track(seq, offset, blank_path, dest, skip=0.0):
    """Liste concat : transparent pendant `offset` s, puis les images du fx à partir de `skip` s
    (suite d'un fx commencé dans la scène d'avant, qui reste à l'écran pendant le changement d'image)."""
    def q(pth):
        return "file '" + os.path.relpath(pth, os.path.dirname(dest)).replace("\\", "/").replace("'", "'\\''") + "'"
    lines = ["ffconcat version 1.0"]
    if offset > 0:
        lines += [q(blank_path), f"duration {offset:.6f}"]
    if skip > 0:
        out, t = [], 0.0
        for path, dur in seq:
            if t + dur > skip + 1e-6:
                out.append((path, min(dur, t + dur - skip)))
            t += dur
        seq = out
    for path, dur in seq:
        lines += [q(path), f"duration {dur:.6f}"]
    lines.append(q(seq[-1][0] if seq else blank_path))
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return dest
