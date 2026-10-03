"""Montage des vidéos d'actu sport (plan.json de services/newsvid.py) — tourne sur le PC, où YouTube
laisse télécharger (le cloud se fait bloquer).

  build(job_dir) :
    1. voix off : narration/nXX.mp3 du dossier (faites dans le cloud), sinon Algrow (ALGROW_API_KEY du .env)
    2. télécharge chaque vidéo source une seule fois (image ≤ 720p et son séparés, yt-dlp)
    3. coupe chaque extrait au bon endroit (calé sur un silence à ±0,7 s), le pose dans le cadre de la chaîne
       avec « Credit: @source » et les sous-titres ; l'ouverture est en plein écran
    4. voix off sur des images muettes de la personne qui va parler (bandeau avec son nom), musique très basse
    5. collage, planches de contrôle (check/), envoi sur Gofile (md5 vérifié) → result.json
    6. supprime TOUT ce qui a été téléchargé et monté (il ne reste que le lien Gofile)
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

from services import media

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(REPO, "static", "fonts")
W, H, FPS = 1920, 1080, 30
BOX = (190, 112, 1540, 866)          # cadre des extraits (x, y, largeur, hauteur) : 16:9, un peu sous le centre
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS)]
AAC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
TENSE = {"name": "News tense", "bpm": 84, "chords": [  # nappe mineure sombre, très basse sous la voix
    ["A3", "C4", "E4", "G4"], ["F3", "A3", "C4", "E4"], ["D3", "F3", "A3", "C4"], ["E3", "G3", "B3", "D4"]]}


def log_to(path):
    def log(*a):
        line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
        print(line, flush=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return log


def _hex(c, default=(225, 6, 0)):
    c = (c or "").lstrip("#")
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def header_duration(path):
    """Durée lue dans l'en-tête (rapide, même pour une vidéo de 3 h)."""
    p = subprocess.run([media.ffmpeg_bin(), "-hide_banner", "-i", path], capture_output=True,
                       creationflags=media._NO_WINDOW)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr.decode("utf-8", "replace"))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


# ── Téléchargement ──────────────────────────────────────────────────────────

def ytdlp_args():
    """yt-dlp ; YTDLP_PROXY (VPS : proxy résidentiel, payé au Go) ne sert qu'à YouTube, jamais à Gofile."""
    from services import newsvid
    proxy = (os.environ.get("YTDLP_PROXY") or "").strip()
    return [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings", "--retries", "5",
            "--fragment-retries", "10", *newsvid.yt_js_args(), *(["--proxy", proxy] if proxy else [])]


def download(video_id, dl_dir, log):
    """Image (≤ 720p, sans son) et son séparés : aucun assemblage, la coupe exacte se fait au montage."""
    os.makedirs(dl_dir, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    got = {}
    for kind, fmt in (("v", "bv*[height<=720][vcodec^=avc1]/bv*[height<=720]/bv*"), ("a", "ba[ext=m4a]/ba")):
        have = [f for f in glob.glob(os.path.join(dl_dir, f"{video_id}.{kind}.*")) if not f.endswith(".part")]
        if have:
            got[kind] = have[0]
            continue
        for k in range(3):
            r = subprocess.run(ytdlp_args() + ["-f", fmt, "-o", f"{video_id}.{kind}.%(ext)s", url], cwd=dl_dir,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            have = [f for f in glob.glob(os.path.join(dl_dir, f"{video_id}.{kind}.*")) if not f.endswith(".part")]
            if have:
                got[kind] = have[0]
                break
            log(f"téléchargement {video_id} ({kind}) essai {k + 1} raté :", (r.stderr or r.stdout)[-300:])
            time.sleep(5 * (k + 1))
    if len(got) < 2:
        return None
    mb = sum(os.path.getsize(p) for p in got.values()) / 1e6
    log(f"téléchargé {video_id} : {mb:.0f} Mo")
    return got


# ── Coupe au silence ────────────────────────────────────────────────────────

def silences(audio, a, b):
    """Silences ([début, fin] en s) entre a et b."""
    a = max(0.0, a)
    p = subprocess.run([media.ffmpeg_bin(), "-hide_banner", "-nostdin", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}",
                        "-i", audio, "-af", "silencedetect=noise=-32dB:d=0.16", "-f", "null", "-"],
                       capture_output=True, creationflags=media._NO_WINDOW)
    err = p.stderr.decode("utf-8", "replace")
    st = [float(x) + a for x in re.findall(r"silence_start: ([\d.]+)", err)]
    en = [float(x) + a for x in re.findall(r"silence_end: ([\d.]+)", err)]
    out = []
    for i, s in enumerate(st):
        out.append((s, en[i] if i < len(en) else b))
    return out


def snap(audio, start, end):
    """Début juste après un silence proche, fin juste au début d'un silence proche (pas de mot coupé)."""
    s2, e2 = start, end
    sil = silences(audio, start - 0.7, start + 0.45)
    if sil:
        s2 = min((x[1] for x in sil), key=lambda v: abs(v - start)) - 0.06
    sil = silences(audio, end - 0.45, end + 0.9)
    if sil:
        e2 = min((x[0] for x in sil), key=lambda v: abs(v - end)) + 0.12
    if e2 - s2 < 2.0:
        return start, end
    return max(0.0, s2), e2


# ── Habillage ───────────────────────────────────────────────────────────────

def make_background(plan, dest, box=True):
    """Fond : noir, nom de la chaîne en motif très discret ; avec box, le cadre des extraits à la couleur de la
    chaîne (sans : fond du logo animé)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    acc = _hex(plan.get("accent"))
    im = Image.new("RGB", (W, H), (10, 10, 12))
    d = ImageDraw.Draw(im)
    brand = (plan.get("brand") or "NEWS").upper()
    f = ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), 46)
    tw = d.textlength(brand, font=f) + 90
    dark = tuple(int(v * 0.11) + 13 for v in acc)  # motif à peine visible
    for row, y in enumerate(range(-20, H + 60, 92)):
        x0 = -((row * 160) % int(tw))
        x = x0
        while x < W:
            d.text((x, y), brand, font=f, fill=dark)
            x += tw
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    im = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), vig)
    if box:
        x, y, w, h = BOX
        glow = Image.new("L", (W, H), 0)
        ImageDraw.Draw(glow).rectangle((x - 14, y - 14, x + w + 14, y + h + 14), fill=170)
        glow = glow.filter(ImageFilter.GaussianBlur(22))
        im = Image.composite(Image.new("RGB", (W, H), acc), im, glow)
        d = ImageDraw.Draw(im)
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), fill=acc)
        d.rectangle((x, y, x + w - 1, y + h - 1), fill=(0, 0, 0))
        _logo(d, brand, acc)
    im.save(dest, "PNG")
    return dest


def _logo(d, brand, acc):
    from PIL import ImageFont
    f = ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), 44)
    tw = d.textlength(brand, font=f)
    x1, y0 = W - 44, 30
    d.rectangle((x1 - tw - 36, y0, x1, y0 + 64), fill=acc)
    d.text((x1 - tw - 18, y0 + 4), brand, font=f, fill=(255, 255, 255))


# ── Transitions : volet penché aux couleurs de la chaîne ────────────────────
# Chaque segment commence couvert par le volet (qui part vers la droite) et finit couvert (le volet arrive
# de la gauche) : collés bout à bout, ça fait un « whip » continu d'un segment au suivant, sans fondu à calculer.

SLANT = 240                       # pente du volet (px)
SW_W = W + 2 * SLANT              # largeur du PNG du volet
SWIPE_OUT, SWIPE_IN = 0.30, 0.24  # sortie au début du segment / arrivée à la fin (s)


def make_swipe(plan, dest):
    from PIL import Image, ImageDraw, ImageFont
    acc = _hex(plan.get("accent"))
    im = Image.new("RGBA", (SW_W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(SLANT, 0), (SW_W, 0), (SW_W - SLANT, H), (0, H)], fill=acc + (255,))
    dark = tuple(int(v * 0.55) for v in acc) + (255,)
    d.polygon([(SLANT, 0), (SLANT + 70, 0), (70, H), (0, H)], fill=dark)                    # bord arrière
    d.polygon([(SW_W - 46, 0), (SW_W, 0), (SW_W - SLANT, H), (SW_W - SLANT - 46, H)], fill=(255, 255, 255, 255))
    brand = (plan.get("brand") or "NEWS").upper()
    f = ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), 190)
    tw = d.textlength(brand, font=f)
    d.text(((SW_W - tw) / 2, H / 2 - 135), brand, font=f, fill=tuple(int(v * 0.78) for v in acc) + (255,))
    im.save(dest, "PNG")
    return dest


def make_shade(dest):
    """Dégradé noir à gauche (sous le titre de la voix off) : lisible même si le b-roll a ses propres textes."""
    from PIL import Image
    a = Image.new("L", (W, 1))
    a.putdata([int(225 * max(0.0, 1 - x / 1250) ** 1.4) for x in range(W)])
    a = a.resize((W, H))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    im.putalpha(a)
    im.save(dest, "PNG")
    return dest


def _swipe_filter(src, sw, dur, out, first=False):
    """[src][sw] → [out] : volet qui sort (début) et qui entre (fin)."""
    def sm(p):
        return f"(({p})*({p})*(3-2*({p})))"
    t0 = dur - SWIPE_IN
    p_out = f"min(1,t/{SWIPE_OUT:.3f})"
    p_in = f"min(1,(t-{t0:.3f})/{SWIPE_IN - 1 / FPS:.3f})"
    x_out = f"{-SLANT}+{W + SLANT}*{sm(p_out)}"
    x_in = f"{-SW_W}+{SW_W - SLANT}*{sm(p_in)}"
    x = f"if(gt(t,{t0:.3f}),{x_in},{W + 10})" if first else \
        f"if(lt(t,{SWIPE_OUT:.3f}),{x_out},if(gt(t,{t0:.3f}),{x_in},{W + 10}))"
    en = f"gt(t,{t0:.3f})" if first else f"lt(t,{SWIPE_OUT:.3f})+gt(t,{t0:.3f})"
    return f"[{src}][{sw}]overlay=x='{x}':y=0:enable='{en}':shortest=1[{out}]"


# ── Textes à l'écran (ASS) ──────────────────────────────────────────────────

STOP = set("the a an and or but to of in on at for with is are was were be been it its it's i i'm i'd i'll you "
           "he she we they him her them his my me our your their that this what who how why when where do does did "
           "not no so if just like get got going gonna have has had will would should could can there here then "
           "than now out up down all one about from by as into over".split())


TAIL = {"CUZ", "COS", "BECAUSE", "AND", "BUT", "SO", "LIKE", "UM", "UH", "THE", "A", "TO", "OF", "THAT", "YOU",
        "I", "IT", "BRO", "MAN", "YEAH", "OR"}


def _c(rgb):
    return "&H00{:02X}{:02X}{:02X}".format(rgb[2], rgb[1], rgb[0])


def _ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _ass_escape(s):
    return (s or "").replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _wrap(text, n):
    """Coupe en lignes de ≤ n caractères (équilibrées) → liste de lignes."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


WEAK = set("believe believes think thinks know knows said say says saying want wants really honestly definitely "
           "actually literally probably something everything anything nothing people thing things guys going "
           "gonna gotta should would could".split())
STRONG = re.compile(r"^(QUIT|CHEAT|ILLEGAL|LIE|LIAR|LYING|RETIR|BEAT|KNOCK|FAKE|EXCUSE|NEVER|DESERVE|SCARED|COWARD|BS|"
                    r"DONE|WALK|BROKE|DESTROY|FINISH|HUMBL|DISRESPECT|JOKE|CLOWN|DUCK|RUN|BELT|CHAMP|KILL|EMBARRASS)")


def _keyword(text):
    """Le mot fort de la citation (coloré) : mot plein (pas « HONESTLY », « BELIEVE »), bonus aux mots qui
    claquent (QUIT, CHEATED, ILLEGAL…), léger avantage à la fin de la phrase."""
    words = re.findall(r"[A-Za-z][A-Za-z'’]+", text)
    best, score = "", -1.0
    for k, w in enumerate(words):
        lw = w.lower()
        if lw in STOP or lw in WEAK or (lw.endswith("ly") and len(lw) > 4) or len(w) < 3:
            continue
        sc = len(w) + 1.0 * k / max(1, len(words)) + (4 if STRONG.match(w.upper()) else 0)
        if sc >= score:
            best, score = w, sc
    return best.upper()


def _styles(acc, acc2, framed):
    x, y, w, h = BOX
    sub_size, margin_v = (46, H - (y + h) + 34) if framed else (54, 70)
    a, a2 = _c(acc), _c(acc2)
    return [
        f"Style: Sub,Montserrat,{sub_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,1,2,"
        f"{x + 40 if framed else 120},{W - x - w + 40 if framed else 120},{margin_v},1",
        "Style: Credit,Montserrat,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,3,10,0,7,"
        "48,48,40,1",
        f"Style: Name,Anton,84,&H00FFFFFF,&H00FFFFFF,{a},&H00000000,0,0,0,0,100,100,1,0,3,18,0,1,0,0,0,1",
        f"Style: Quote,Anton,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,0,0,0,0,100,100,1,0,1,7,3,2,160,160,0,1",
        f"Style: Tag,Montserrat,40,&H00FFFFFF,&H00FFFFFF,{a},&H00000000,1,0,0,0,100,100,2,0,3,12,0,7,0,0,0,1",
        f"Style: Head,Anton,150,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,1,0,1,6,4,7,0,0,0,1",
        f"Style: Pill,Montserrat,46,&H00FFFFFF,&H00FFFFFF,{a},&H00000000,1,0,0,0,100,100,1,0,3,16,0,3,0,0,0,1",
        f"Style: Tick,Montserrat,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,1,0,1,0,0,7,0,0,0,1",
        f"Style: Box,Montserrat,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: Brand,Anton,300,&H00FFFFFF,&H00FFFFFF,{a},&H00000000,0,0,0,0,100,100,6,0,3,40,0,5,0,0,0,1",
        f"Style: Slogan,Montserrat,62,{a2},{a2},&H00000000,&H00000000,1,0,0,0,100,100,8,0,1,3,0,5,0,0,0,1",
    ]


def _write_ass(dest, styles, events):
    with open(dest, "w", encoding="utf-8") as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
                "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
                "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
                "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" +
                "\n".join(events) + "\n")
    return dest


def _ev(a, b, style, text, layer=1):
    return f"Dialogue: {layer},{_ass_time(a)},{_ass_time(b)},{style},,0,0,0,,{text}"


def _name_plate(name, x, y, a, b, top=False):
    """Nom de la personne qui parle : glisse depuis la gauche, s'efface (top : ancré en haut à gauche)."""
    an = "\\an7" if top else ""
    return _ev(a, b, "Name", f"{{{an}\\move({x - 900},{y},{x},{y},0,260)\\fad(0,220)}}{_ass_escape(name.upper())}", 3)


def _quote_text(q, acc2):
    t = _ass_escape(q).upper().strip("\"“” ")
    words = t.split()
    while (len(words) > 3 and not re.search(r"[.?!]$", words[-1])  # phrase coupée : « … I CHEATED CUZ »
           and re.sub(r"[^A-Z']", "", words[-1]) in TAIL):
        words.pop()
    t = " ".join(words).rstrip(",;:-")
    n = len(t)
    size, per = (124, 22) if n <= 50 else (104, 27) if n <= 90 else (86, 33)
    kw = _keyword(t)
    lines = []
    for ln in _wrap(t, per):
        if kw:
            colored = f"{{\\c&H{acc2[2]:02X}{acc2[1]:02X}{acc2[0]:02X}&}}{kw}{{\\c&HFFFFFF&}}"
            ln = re.sub(rf"\b{re.escape(kw)}\b", lambda m: colored, ln, count=1)
        lines.append(ln)
    return size, "\\N".join(lines)


def clip_ass(dest, subs, framed, credit, speaker, quote, dur, acc, acc2, pill=None):
    """Sous-titres + crédit + nom de qui parle + citation choc en grand (pop) + rappel d'abonnement."""
    x, y, w, h = BOX
    ev = []
    q0 = q1 = None
    if quote and quote.get("t") and quote["e"] > quote["s"]:
        q0, q1 = max(0.0, quote["s"] - 0.05), min(dur - 0.2, quote["e"] + 0.35)
    for s in subs or []:
        if s["e"] - s["s"] < 0.15:
            continue
        if q0 is not None and s["s"] < q1 and s["e"] > q0:  # la citation remplace le sous-titre normal
            continue
        ev.append(_ev(s["s"], s["e"], "Sub", _ass_escape(s["t"]), 0))
    if credit:
        ev.append(_ev(0, dur, "Credit", f"Credit: {_ass_escape(credit)}"))
    def free(a, b):  # pas en même temps que la citation (même endroit de l'écran)
        return q0 is None or b <= q0 or a >= q1
    if speaker:
        nx, ny = (x + 30, y + 30) if framed else (60, 110)  # en haut à gauche : jamais sur les sous-titres
        win = [(0.35, min(dur - 0.3, 4.6))]
        if q0 is not None:
            win = [(0.35, min(4.6, q0 - 0.05)), (q1 + 0.1, min(dur - 0.3, q1 + 4.0))]
        win = [(a, b) for a, b in win if b - a >= 1.5 and free(a, b)]
        if win:
            ev.append(_name_plate(speaker, nx, ny, *win[0], top=True))
    if q0 is not None:
        size, txt = _quote_text(quote["t"], acc2)
        mv = (H - (y + h) + 70) if framed else 150
        ev.append(_ev(q0, q1, "Quote", f"{{\\fs{size}\\an2\\pos({W // 2},{H - mv})\\fscx135\\fscy135"
                                       f"\\t(0,150,\\fscx100\\fscy100)\\fad(60,160)}}{txt}", 4))
    pill_at = None
    if pill:
        cands = [min(6.0, max(1.0, dur - 6)), 1.0, (q1 or 0) + 0.3, dur - 5.0]
        pill_at = next((a for a in cands if 0.5 <= a <= dur - 4.6 and free(a, a + 4.5)), None)
    if pill_at is not None:
        a = pill_at
        ev.append(_ev(a, a + 4.5, "Pill", f"{{\\an9\\pos({x + w - 30},{y + 30})\\fscx60\\fscy60"
                                          f"\\t(0,180,\\fscx100\\fscy100)\\fad(0,250)}}{_ass_escape(pill)}", 5))
    _write_ass(dest, _styles(acc, acc2, framed), ev)
    return pill_at, (q0, q1)


def _wrap_subs(subs, max_chars=42):
    """Lignes de sous-titres auto (souvent coupées au milieu) → phrases courtes lisibles."""
    out = []
    for s in subs:
        t = re.sub(r"\[\s*_+\s*\]", "****", s["t"]).strip()  # gros mot censuré par YouTube : « [ __ ] »
        if not t:
            continue
        if out and len(out[-1]["t"]) + len(t) + 1 <= max_chars and s["s"] - out[-1]["e"] < 0.4 \
                and not re.search(r"[.?!]$", out[-1]["t"]):
            out[-1] = {"s": out[-1]["s"], "e": s["e"], "t": out[-1]["t"] + " " + t}
        else:
            out.append(dict(s, t=t))
    return out


def sfx_track(events, dur, dest):
    from services import sfx
    return sfx.build_track(events, dur + 0.5, dest)


# ── Segments ────────────────────────────────────────────────────────────────

def render_clip(seg, files, bg, workdir, dest, accent, log, accent2=(255, 210, 31), swipe=None, first=False,
                pill=None):
    """Extrait (exact, calé au silence) → mp4 normalisé. Plein écran pour l'ouverture, sinon dans le cadre.
    Montage : volet de transition, nom de qui parle, citation choc en grand + zoom, rappel d'abonnement."""
    start, end = snap(files["a"], seg["start"], seg["end"])
    shift = seg["start"] - start
    dur = end - start
    subs = [{"s": max(0.0, s["s"] + shift), "e": min(dur, s["e"] + shift), "t": s["t"]} for s in seg["subs"]]
    subs = [s for s in _wrap_subs(subs) if s["e"] > s["s"]]
    quote = dict(seg["quote"], s=seg["quote"]["s"] + shift, e=seg["quote"]["e"] + shift) if seg.get("quote") else None
    framed = not seg.get("full")
    ass = os.path.join(workdir, os.path.basename(dest) + ".ass")
    pill_at, (q0, q1) = clip_ass(ass, subs, framed, seg.get("credit") or "", seg.get("speaker") or "", quote, dur,
                           accent, accent2, pill=pill)
    sfx = [(0.0, "whoosh", 0.55)] if not first else []
    if q0 is not None:
        sfx.append((q0, "hit", 0.75))
    if pill_at is not None:
        sfx.append((pill_at, "pop", 0.5))
    sfx_wav = sfx_track(sfx, dur, os.path.join(workdir, os.path.basename(dest) + ".sfx.wav"))
    x, y, w, h = BOX
    ins = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", files["v"],
           "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", files["a"], "-i", sfx_wav]
    sub = f"subtitles={os.path.basename(ass)}:fontsdir=fonts"
    zoom = f":enable='between(t,{q0:.3f},{q1:.3f})'" if q0 is not None else None
    cw, ch = (w, h) if framed else (W, H)
    if framed:
        ins += ["-loop", "1", "-framerate", str(FPS), "-i", bg]
        g = (f"[0:v]fps={FPS},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
             f"setsar=1[c];")
        base = f"[3:v][c1]overlay={x}:{y}:shortest=1[b0];"
        zx, zy = x, y
    else:
        g = f"[0:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[c];"
        base = "[c1]null[b0];"
        zx, zy = 0, 0
    if zoom:  # « punch-in » pendant la citation choc
        zw, zh = int(cw * 1.09) // 2 * 2, int(ch * 1.09) // 2 * 2
        g += f"[c]split[c1][cz0];[cz0]scale={zw}:{zh},crop={cw}:{ch}[cz];" + base
        g += f"[b0][cz]overlay={zx}:{zy}{zoom}[b1];[b1]{sub}[b2];"
    else:
        g += "[c]null[c1];" + base + f"[b0]{sub}[b2];"
    sw_idx = 4 if framed else 3
    ins += ["-loop", "1", "-framerate", str(FPS), "-i", swipe]
    g += _swipe_filter("b2", f"{sw_idx}:v", dur, "b3", first=first) + ";[b3]format=yuv420p[v];"
    g += ("[1:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[ca];"
          "[2:a]aresample=48000,aformat=channel_layouts=stereo[fx];"
          "[ca][fx]amix=inputs=2:duration=first:normalize=0,aresample=48000[a]")
    media.run(ins + ["-filter_complex", g, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *X264, *AAC,
                     os.path.basename(dest)], cwd=workdir)
    return dest


def broll_window(files, near_start, near_end, dur):
    """Images muettes de la personne qui va parler : un passage de la même vidéo, hors de l'extrait."""
    total = header_duration(files["v"]) or (near_end + dur + 60)
    if near_start - 20 - dur >= 0:
        return near_start - 20 - dur
    if near_end + 15 + dur <= total:
        return near_end + 15
    return max(0.0, min(total - dur, near_end + 1))


def narration_ass(dest, seg, dur, plan, acc, acc2):
    """Voix off : titre de l'info (glisse), nom de qui va parler, fil d'actu qui défile en bas, logo."""
    ev = []
    brand = (plan.get("brand") or "NEWS").upper()
    ev.append(_ev(0, dur, "Tag", f"{{\\an9\\pos({W - 44},{34})\\fs56\\fnAnton\\b0}}{_ass_escape(brand)}", 2))
    head = seg.get("headline") or ("DROP YOUR THOUGHTS BELOW" if seg.get("outro") else "")
    if head:
        lines = _wrap(_ass_escape(head), 15)[:3]
        y0 = 280 if len(lines) < 3 else 200
        ev.append(_ev(0.25, dur, "Tag", f"{{\\move(-500,{y0},96,{y0},0,220)}}"
                                        f"{'THE LATEST' if not seg.get('outro') else 'YOUR TAKE'}", 3))
        ev.append(_ev(0.4, dur, "Head", f"{{\\move(-1400,{y0 + 70},96,{y0 + 70},0,320)}}" + "\\N".join(lines), 3))
    lower = seg.get("lower") or ""
    if lower:
        ev.append(_name_plate(lower, 96, H - 120, 0.6, dur))
    if seg.get("outro") and plan.get("subscribe"):
        ev.append(_ev(1.0, dur, "Pill", f"{{\\an3\\pos({W - 60},{H - 140})\\fscx60\\fscy60"
                                        f"\\t(0,180,\\fscx100\\fscy100)}}{_ass_escape(plan['subscribe'])}", 4))
    tick = [t for t in plan.get("ticker") or [] if t]
    if tick:  # bandeau noir + étiquette + texte qui défile (180 px/s)
        yb = H - 76
        ev.append(_ev(0, dur, "Box", f"{{\\p1\\pos(0,{yb})\\c&H000000&\\alpha&H30&}}m 0 0 l {W} 0 l {W} 76 l 0 76{{\\p0}}", 1))
        txt = "   •   ".join(_ass_escape(t) for t in tick)
        txt = (txt + "   •   ") * 3
        x0, x1 = int(W * 0.35), int(W * 0.35 - 180 * dur)
        ev.append(_ev(0, dur, "Tick", f"{{\\clip(260,{yb},{W},{H})\\move({x0},{yb + 15},{x1},{yb + 15})}}{txt}", 2))
        ev.append(_ev(0, dur, "Tag", f"{{\\pos(26,{yb + 14})\\fs38}}LATEST", 3))
    return _write_ass(dest, _styles(acc, acc2, False), ev)


def render_narration(seg, audio, files, b0, workdir, dest, music, accent, plan, accent2=(255, 210, 31),
                     swipe=None, shade=None):
    dur = media.duration(audio) + 0.35
    ass = narration_ass(os.path.join(workdir, os.path.basename(dest) + ".ass"), seg, dur, plan, accent, accent2)
    sfx_wav = sfx_track([(0.0, "whoosh", 0.55)], dur, os.path.join(workdir, os.path.basename(dest) + ".sfx.wav"))
    n = max(1, int(dur * FPS))
    ins = ["-ss", f"{b0:.3f}", "-t", f"{dur:.3f}", "-i", files["v"], "-i", audio,
           "-stream_loop", "-1", "-i", music, "-i", sfx_wav, "-loop", "1", "-framerate", str(FPS), "-i", swipe,
           "-loop", "1", "-framerate", str(FPS), "-i", shade or make_shade(os.path.join(workdir, "shade.png"))]
    # b-roll : zoom lent (calculé sur une image 2× plus grande : pas de tremblement), assombri
    g = (f"[0:v]fps={FPS},scale={2 * W}:{2 * H}:force_original_aspect_ratio=increase,crop={2 * W}:{2 * H},setsar=1,"
         f"zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
         f"eq=brightness=-0.10:saturation=0.8[bb];[bb][5:v]overlay=0:0:shortest=1,"
         f"subtitles={os.path.basename(ass)}:fontsdir=fonts[b2];"
         + _swipe_filter("b2", "4:v", dur, "b3") + ";[b3]format=yuv420p[v];"
         f"[1:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur=0.35[n];"
         f"[2:a]aresample=48000,volume=0.11,afade=t=in:d=0.4[m];"
         f"[3:a]aresample=48000,aformat=channel_layouts=stereo[fx];"
         f"[n][m][fx]amix=inputs=3:duration=first:normalize=0,aresample=48000[a]")
    media.run(ins + ["-filter_complex", g, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *X264, *AAC,
                     os.path.basename(dest)], cwd=workdir)
    return dest


def render_sting(plan, workdir, dest, music, accent, accent2=(255, 210, 31), swipe=None, dur=2.6):
    """Logo animé entre l'ouverture et la première voix off : nom de la chaîne qui claque + slogan."""
    bg = make_background(plan, os.path.join(workdir, "bg_plain.png"), box=False)
    brand = _ass_escape((plan.get("brand") or "NEWS").upper())
    slogan = _ass_escape(re.sub(r"^SUBSCRIBE FOR\s+", "", (plan.get("subscribe") or "").upper()))
    ev = [_ev(0.15, dur, "Brand", f"{{\\pos({W // 2},{H // 2 - 30})\\fscx170\\fscy170\\blur12"
                                  f"\\t(0,230,\\fscx100\\fscy100\\blur0)}}{brand}", 2)]
    if slogan:
        ev.append(_ev(0.55, dur, "Slogan", f"{{\\pos({W // 2},{H // 2 + 260})\\fad(200,0)}}{slogan}", 2))
    ass = _write_ass(os.path.join(workdir, "sting.ass"), _styles(accent, accent2, False), ev)
    sfx_wav = sfx_track([(0.0, "whoosh", 0.55), (0.15, "hit", 0.9)], dur, os.path.join(workdir, "sting.sfx.wav"))
    g = (f"[0:v]fps={FPS},format=rgb24,subtitles={os.path.basename(ass)}:fontsdir=fonts[b2];"
         + _swipe_filter("b2", "3:v", dur, "b3") + ";[b3]format=yuv420p[v];"
         f"[1:a]aresample=48000,volume=0.16,afade=t=in:d=0.3[m];[2:a]aresample=48000,aformat=channel_layouts=stereo[fx];"
         f"[m][fx]amix=inputs=2:duration=first:normalize=0,aresample=48000[a]")
    media.run(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", bg, "-stream_loop", "-1", "-i", music,
               "-i", sfx_wav, "-loop", "1", "-framerate", str(FPS), "-i", swipe,
               "-filter_complex", g, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *X264, *AAC,
               os.path.basename(dest)], cwd=workdir)
    return dest


def tts(seg_text, dest, plan):
    from services import tts as T
    v = plan.get("voice") or {}
    T.synthesize(seg_text, dest, provider=v.get("provider") or "algrow", voice=v.get("id") or "", lang="en")
    return dest


# ── Contrôle ────────────────────────────────────────────────────────────────

def check_sheets(video, out_dir, every=10, cols=6, rows=5):
    """Une image toutes les `every` s, en planches 6×5 (une planche = 5 min) → check/sheet_XX.jpg."""
    from PIL import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "_frames")
    os.makedirs(tmp, exist_ok=True)
    media.run(["-i", video, "-vf", f"fps=1/{every},scale=384:216", "-q:v", "4", os.path.join(tmp, "f%04d.jpg")])
    frames = sorted(glob.glob(os.path.join(tmp, "f*.jpg")))
    per = cols * rows
    for k in range(0, len(frames), per):
        sheet = Image.new("RGB", (cols * 384, rows * 216), (0, 0, 0))
        d = ImageDraw.Draw(sheet)
        for i, fp in enumerate(frames[k:k + per]):
            x, y = (i % cols) * 384, (i // cols) * 216
            with Image.open(fp) as im:  # fermé tout de suite : Windows refuse d'effacer un fichier ouvert
                sheet.paste(im, (x, y))
            t = (k + i) * every
            # heure en bas à droite : le crédit de la source (en haut à gauche) reste visible à la relecture
            d.rectangle((x + 384 - 50, y + 216 - 20, x + 384, y + 216), fill=(0, 0, 0))
            d.text((x + 384 - 46, y + 216 - 16), f"{t // 60}:{t % 60:02d}", fill=(255, 255, 0))
        sheet.save(os.path.join(out_dir, f"sheet_{k // per + 1:02d}.jpg"), quality=80)
    shutil.rmtree(tmp, ignore_errors=True)


def gofile(path, log):
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
    md5 = md5.hexdigest()
    for k in range(5):
        r = subprocess.run(["curl", "-sS", "--noproxy", "*", "--max-time", "3600", "-F", f"file=@{path}",
                            "https://upload.gofile.io/uploadfile"], capture_output=True, text=True)
        try:
            data = json.loads(r.stdout).get("data") or {}
            if data.get("downloadPage") and data.get("md5", md5) == md5:
                return data["downloadPage"], md5
            log("gofile : réponse inattendue", r.stdout[:200])
        except ValueError:
            log("gofile : erreur", (r.stderr or r.stdout)[:200])
        time.sleep(20 * (k + 1))
    return None, md5


# ── Tout le montage ─────────────────────────────────────────────────────────

def build(job_dir, work_root, upload=True, keep=False):
    job_dir = os.path.abspath(job_dir)
    name = os.path.basename(job_dir.rstrip("/\\"))
    with open(os.path.join(job_dir, "plan.json"), "r", encoding="utf-8") as f:
        plan = json.load(f)
    work = os.path.join(work_root, "news_build", name)
    dl = os.path.join(work, "dl")
    os.makedirs(dl, exist_ok=True)
    log = log_to(os.path.join(job_dir, "build.log"))
    log(f"montage de {name} : {len(plan['segments'])} segments")
    accent = _hex(plan.get("accent"))
    accent2 = _hex(plan.get("accent2"), default=(255, 210, 31))
    shutil.copytree(FONTS, os.path.join(work, "fonts"), dirs_exist_ok=True)
    bg = make_background(plan, os.path.join(work, "bg.png"))
    swipe = make_swipe(plan, os.path.join(work, "swipe.png"))
    shade = make_shade(os.path.join(work, "shade.png"))
    music = os.path.join(work, "music.mp3")
    if not os.path.isfile(music):
        from services import music as M
        M.generate("news_tense", music, minutes=3, track=TENSE)
    # 1) voix off
    nar_dir = os.path.join(job_dir, "narration")
    voices = {}
    for i, seg in enumerate(plan["segments"]):
        if seg["type"] != "narration":
            continue
        mine = os.path.join(nar_dir, f"n{i:03d}.mp3")
        if not os.path.isfile(mine):
            mine = os.path.join(work, f"n{i:03d}.mp3")
            if not os.path.isfile(mine):
                log(f"voix off {i}…")
                tts(seg["text"], mine, plan)
        voices[i] = mine
    # 2) téléchargements
    files = {}
    for vid in dict.fromkeys(s["video"] for s in plan["segments"] if s["type"] == "clip"):
        files[vid] = download(vid, dl, log)
        if not files[vid]:
            log(f"!! vidéo {vid} impossible à télécharger : ses extraits sautent")
    # 3) segments (+ logo animé après l'ouverture, rappel d'abonnement sur le 2e extrait encadré)
    parts = []
    segs = plan["segments"]
    framed_seen = 0
    for i, seg in enumerate(segs):
        dest = os.path.join(work, f"s{i:03d}.mp4")
        if seg["type"] == "clip":
            if not files.get(seg["video"]):
                continue
            pill = None
            if not seg.get("full"):
                framed_seen += 1
                if framed_seen == 2:
                    pill = plan.get("subscribe")
            if not os.path.isfile(dest):
                render_clip(seg, files[seg["video"]], bg, work, dest, accent, log, accent2=accent2, swipe=swipe,
                            first=not parts, pill=pill)
        else:
            nxt = next((s for s in segs[i + 1:] if s["type"] == "clip" and files.get(s["video"])), None)
            if nxt is None and seg.get("next_video") is not None:
                continue  # l'extrait annoncé n'existe plus : la voix off saute aussi
            ref = nxt or next((s for s in reversed(segs[:i]) if s["type"] == "clip" and files.get(s["video"])), None)
            if ref is None:
                continue
            if parts and not any(p.endswith("sting.mp4") for p in parts):  # fin de l'ouverture : logo animé
                parts.append(render_sting(plan, work, os.path.join(work, "sting.mp4"), music, accent, accent2,
                                          swipe=swipe))
            seg = dict(seg, lower="" if seg.get("outro") else (nxt or {}).get("speaker", ""))
            if not os.path.isfile(dest):
                b0 = broll_window(files[ref["video"]], ref["start"], ref["end"], media.duration(voices[i]) + 0.5)
                render_narration(seg, voices[i], files[ref["video"]], b0, work, dest, music, accent, plan,
                                 accent2=accent2, swipe=swipe, shade=shade)
        parts.append(dest)
        log(f"segment {i + 1}/{len(segs)} prêt")
    # 4) collage
    lst = os.path.join(work, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        f.write("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
    out = os.path.join(work_root, "news_out", f"{name}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    media.run(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "-movflags", "+faststart",
               os.path.abspath(out)], cwd=work)
    total = header_duration(out)
    log(f"vidéo : {out} ({total / 60:.1f} min, {os.path.getsize(out) / 1e6:.0f} Mo)")
    check_sheets(out, os.path.join(job_dir, "check"))
    result = {"file": os.path.basename(out), "minutes": round(total / 60, 2), "size": os.path.getsize(out),
              "at": time.strftime("%Y-%m-%d %H:%M"), "segments": len(parts)}
    if upload:
        link, md5 = gofile(out, log)
        result.update(link=link, md5=md5)
        log("gofile :", link)
    with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    if not keep:  # rien ne reste sur le PC : téléchargements, segments, et la vidéo si elle est sur Gofile
        shutil.rmtree(work, ignore_errors=True)
        if result.get("link"):
            os.remove(out)
        log("nettoyé : téléchargements et fichiers de montage supprimés")
    return result
