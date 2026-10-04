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
    cookies = (os.environ.get("YTDLP_COOKIES") or "").strip()  # cookies.txt d'un compte YouTube (VPS bloqué)
    return [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings", "--retries", "5",
            "--fragment-retries", "10", *newsvid.yt_js_args(), *(["--proxy", proxy] if proxy else []),
            *(["--cookies", cookies] if cookies and os.path.isfile(cookies) else [])]


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
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               creationflags=media._NO_WINDOW)
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
        a, b = min(sil, key=lambda x: abs(x[0] - end))[:2]
        e2 = a + max(0.12, min(0.6, (b - a) * 0.7))   # respiration après la dernière phrase, sans mordre la suivante
    if e2 - s2 < 2.0:
        return start, end
    return max(0.0, s2), e2


# Transitions douces entre les passages (l'utilisateur, 4 oct. : « ça coupe net dès que les mecs arrêtent de parler ») :
# chaque morceau entre et sort en fondu court (image + son), le son plus longuement que l'image.
FADE_V_IN, FADE_V_OUT, FADE_A_IN, FADE_A_OUT = 0.2, 0.3, 0.15, 0.45


def vfades(dur):
    return f"fade=t=in:st=0:d={FADE_V_IN},fade=t=out:st={max(0.0, dur - FADE_V_OUT):.3f}:d={FADE_V_OUT}"


def afades(dur):
    return f"afade=t=in:st=0:d={FADE_A_IN},afade=t=out:st={max(0.0, dur - FADE_A_OUT):.3f}:d={FADE_A_OUT}"


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


# ── Textes à l'écran (ASS) ──────────────────────────────────────────────────

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


PROFANITY = re.compile(r"\b(mother|bull|horse|dip)?(fuck|shit|bitch|cunt|pussy|bastard|asshole)", re.I)


def censor(text):
    """Gros mots écrits à l'écran → « F***ING », « S*** » (monétisation) ; « [ __ ] » de YouTube → « **** »."""
    text = re.sub(r"\[\s*_+\s*\]", "****", text)
    return PROFANITY.sub(lambda m: (m.group(1) or "") + m.group(2)[0] + "*" * (len(m.group(2)) - 1), text)


STARTERS = set("what so but and he she they we you it that this like well yeah no because if when why how do did "
               "is are was were it's that's there's look listen honestly man bro now then you're he's she's they're "
               "we're what's let's who where there okay right see sure true not absolutely yes oh".split())
MODALS = {"would", "could", "should", "can", "will", "was", "has", "had"}   # « Gaethje Would do that » : majuscule en trop
SUBJ_VERB = {"he's", "she's", "it's", "that's", "there's", "what's", "you're", "we're", "they're", "i'm"}
FILLER = re.compile(r"^(um+|uh+|uhm|erm|hmm+)[,.]?$", re.I)
NOISE = re.compile(r"^(mhm|mm-?hmm|uh-?huh|hmm+|um+|uh+)[.!?,]*$", re.I)   # sous-titre qui ne dit rien → enlevé
KEEP_DOUBLE = {"had", "that", "is", "very", "so", "no", "bye"}


PUNCT_END = r"[.?!,…:;-][\"”’')]*$"     # « hard." » compte comme une fin de phrase
SENT_END = r"[.?!][\"”’')]*$"
DASH = re.compile(r"^[—–-]+[.,]*$|^--+$")


def _restarts(t):
    """Phrase lâchée en route puis reprise (« he's What is he… », « He's I don't know ») → « he's... What is he… »."""
    words = t.split(" ")
    for i in range(1, len(words)):
        w, prev = words[i], words[i - 1]
        if re.search(PUNCT_END, prev) or not w[:1].isupper():
            continue
        if w.lower() in MODALS:
            words[i] = w.lower()
            continue
        if (w != "I" and w.lower().strip(",.?!") in STARTERS) or \
                (re.match(r"I\b", w) and prev.lower() in SUBJ_VERB):
            words[i - 1] += "..."
    return " ".join(words)


def _tidy(t):
    """Sous-titre propre : sans « [laughter] », sans « um/uh » (au milieu d'une phrase → « ... »), sans bégaiement
    (« you you you do it » → « you do it »)."""
    t = re.sub(r"\[[^\]]*\]", " ", t)                       # [laughter], [music]… (les « [ __ ] » sont déjà « **** »)
    words, out, cap = t.split(), [], False
    for k, w in enumerate(words):
        if DASH.match(w) and out and not re.search(PUNCT_END, out[-1]) and k + 1 < len(words) \
                and words[k + 1][:1].islower():
            out[-1] += ","                                 # « The Ultimate Fighter — a very… » → virgule
            continue
        if FILLER.match(w) or DASH.match(w):              # « um », « — » (phrase coupée) → « ... »
            if out and not re.search(PUNCT_END, out[-1]):
                out[-1] += "..."
            elif not out or re.search(SENT_END, out[-1]):
                cap = True                                 # « Uh having parties » → « Having parties »
            continue
        w = re.sub(r"(?<=\w)(?:[—–]|--)+$", "...", w)      # « he thinks— » → « he thinks... »
        if out and w.lower().startswith(out[-1].lower().rstrip(",") + "'") and not re.search(PUNCT_END, out[-1]):
            out[-1] = w                                    # « I I'm », « you you're » → « I'm »
            continue
        if out and w.lower().strip(",.?!") == out[-1].lower().rstrip(".…").strip(",?!") \
                and w.lower().strip(",.?!") not in KEEP_DOUBLE and not re.search(SENT_END, out[-1]):
            out[-1] = re.sub(r"\.\.\.$", "", out[-1])
            if out[-1][:1].isupper() and len(out) == 1 or (len(out) > 1 and re.search(r"[.?!]$", out[-2])):
                w = w[:1].upper() + w[1:]
            out[-1] = w
            continue
        if cap:
            w, cap = w[:1].upper() + w[1:], False
        out.append(w)
    t = " ".join(out)
    while True:   # « He can he can fight » → « He can fight »
        t2 = re.sub(r"\b([A-Za-z']+ [A-Za-z']+(?: [A-Za-z']+)?) (\1)\b", r"\1", t, flags=re.I)
        if t2 == t:
            break
        t = t2
    return re.sub(r"\.\.\.(\.+)", "...", t).strip()


KEEP_CAPS = {"UFC", "MMA", "BMF", "TUF", "USA", "PPV", "KO", "TKO", "GOAT", "I", "OK", "TV", "PFL"}


NAMES = set()   # noms propres de la vidéo (personnes du plan), remplis par build() : « ILIA TOPURIA » → « Ilia Topuria »


def _decaps(subs):
    """Transcription qui crie (« WHEN HIS TIME IS OVER, SOMEONE ») → casse normale ; les noms propres gardent leur
    majuscule (noms du plan, ou mots écrits avec une majuscule au milieu d'une phrase ailleurs dans l'extrait).
    Tout l'extrait d'un bloc : un mot en majuscules en début de ligne n'est pas forcément un début de phrase."""
    known = {n.lower(): n for n in NAMES}
    flat = [(k, w) for k, s in enumerate(subs) for w in s["t"].split()]
    for i, (_, w) in enumerate(flat):
        core = w.strip(".,?!\"'")
        if i and core[:1].isupper() and not core.isupper() and not re.search(r"[.?!]$", flat[i - 1][1]) \
                and core.lower() not in STARTERS:
            known.setdefault(core.lower(), core)
    words = [w for _, w in flat]
    caps = [len(re.sub(r"[^A-Za-z]", "", w)) > 1 and w.isupper() and re.sub(r"[^A-Z]", "", w) not in KEEP_CAPS
            for w in words]
    for i, w in enumerate(words):
        if caps[i] and ((i > 0 and caps[i - 1]) or (i + 1 < len(words) and caps[i + 1])):
            core = re.sub(r"[^A-Za-z']", "", w).lower()
            rep = known.get(core, core)
            if i == 0 or re.search(r"[.?!]$", words[i - 1]):
                rep = rep[:1].upper() + rep[1:]
            words[i] = re.sub(r"[A-Za-z']+", lambda m: rep, w, count=1)
    out = [[] for _ in subs]
    for (k, _), w in zip(flat, words):
        out[k].append(w)
    return [dict(s, t=" ".join(ws)) for s, ws in zip(subs, out)]


def _wrap_subs(subs, max_chars=78):
    """Lignes de sous-titres auto → phrases lisibles (2 lignes max) ; « ... » quand une phrase est lâchée et reprise."""
    out = []
    for s in _decaps(subs):
        t = _tidy(_restarts(censor(s["t"]).strip()))  # gros mots : « **** » / « F*** »
        if not t or NOISE.match(t):
            continue
        if out and re.search(SENT_END, out[-1]["t"]) and t[:1].islower():
            t = t[:1].upper() + t[1:]                      # « … invincible. » + « having parties » (le « uh » est parti)
        if out and len(out[-1]["t"]) + len(t) + 1 <= max_chars and s["s"] - out[-1]["e"] < 0.4 \
                and not re.search(SENT_END, out[-1]["t"]):
            out[-1] = {"s": out[-1]["s"], "e": s["e"], "t": _tidy(_restarts(out[-1]["t"] + " " + t))}
        else:
            out.append(dict(s, t=t))
    for k in range(len(out) - 1):  # coupure entre deux sous-titres au milieu d'une phrase reprise autrement
        a, b = out[k]["t"], out[k + 1]["t"]
        first = b.split()[0] if b.split() else ""
        if not re.search(PUNCT_END, a) and first[:1].isupper() and first != "I" \
                and first.lower().strip(",.?!") in STARTERS:
            out[k]["t"] = a + "..."
    return out


def _sub_text(t, color=None):
    lines = _wrap(_ass_escape(t), 42)
    if len(lines) > 2:  # 3 lignes : on resserre en 2 lignes un peu plus longues
        lines = _wrap(_ass_escape(t), max(42, (len(t) + 1) // 2 + 6))
    txt = "\\N".join(lines)
    return (f"{{\\c{color}}}" + txt) if color else txt


def clip_ass(dest, subs, framed, credit, speaker, quote, dur, acc, acc2, pill=None, brand=""):
    """Sous-titres (la phrase forte en jaune, rien qui surgit au milieu de l'écran), crédit, nom de qui parle
    pendant sa phrase forte, rappel d'abonnement discret une fois."""
    x, y, w, h = BOX
    ev = []
    q0 = q1 = None
    if quote and quote.get("t") and quote["e"] > quote["s"]:
        q0, q1 = max(0.0, quote["s"] - 0.05), min(dur - 0.2, quote["e"] + 0.2)
    yellow = f"&H{acc2[2]:02X}{acc2[1]:02X}{acc2[0]:02X}&"
    for s in subs or []:
        if s["e"] - s["s"] < 0.15:
            continue
        hot = q0 is not None and s["s"] < q1 - 0.1 and s["e"] > q0 + 0.1
        ev.append(_ev(s["s"], s["e"], "Sub", _sub_text(s["t"], yellow if hot else None), 0))
    if credit:
        ev.append(_ev(0, dur, "Credit", f"Credit: {_ass_escape(credit)}"))
    if brand and not framed:  # plein écran : petit logo en haut à droite (dans le cadre, il est sur le fond)
        ev.append(_ev(0, dur, "Tag", f"{{\\an9\\pos({W - 44},{34})\\fs56\\fnAnton\\b0}}{_ass_escape(brand)}", 2))
    if speaker and q0 is not None and framed:  # le nom PENDANT sa phrase forte : c'est sûrement lui/elle à l'écran
        nx, ny = x + 30, y + 30                    # (plein écran : le crédit le dit déjà, la vidéo a ses propres textes)
        a, b = q0, min(dur - 0.3, max(q1, q0 + 4.0))
        if b - a >= 1.5:
            ev.append(_name_plate(speaker, nx, ny, a, b, top=True))
    pill_at = None
    if pill:
        cands = [min(6.0, max(1.0, dur - 6)), 1.0, dur - 5.0]
        pill_at = next((a for a in cands if 0.5 <= a <= dur - 4.6
                        and (q0 is None or a + 4.5 <= q0 or a >= q1)), None)
    if pill_at is not None:
        a = pill_at
        ev.append(_ev(a, a + 4.5, "Pill", f"{{\\an9\\pos({x + w - 30},{y + 30})\\fad(250,250)}}{_ass_escape(pill)}", 5))
    _write_ass(dest, _styles(acc, acc2, framed), ev)
    return pill_at, (q0, q1)


def make_frame(plan, dest):
    """Cadre des extraits (style Fight Night) : bord + halo à la couleur de la chaîne + logo, centre transparent ;
    posé sur la vidéo elle-même floutée."""
    from PIL import Image, ImageDraw, ImageFilter
    acc = _hex(plan.get("accent"))
    x, y, w, h = BOX
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).rectangle((x - 16, y - 16, x + w + 16, y + h + 16), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(24))
    im = Image.new("RGBA", (W, H), acc + (0,))
    im.putalpha(glow)
    d = ImageDraw.Draw(im)
    d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), fill=acc + (255,))
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=(0, 0, 0, 0))
    _logo(d, (plan.get("brand") or "NEWS").upper(), acc)
    im.save(dest, "PNG")
    return dest


def render_clip(seg, files, frame, workdir, dest, accent, log, accent2=(255, 210, 31), pill=None, brand=""):
    """Extrait (exact, calé au silence) → mp4 normalisé, coupes franches, sans bruitage. Ouverture : plein écran,
    léger zoom ; ensuite : dans le cadre, sur la même vidéo floutée."""
    start, end = snap(files["a"], seg["start"], seg["end"])
    shift = seg["start"] - start
    dur = end - start
    subs = [{"s": max(0.0, s["s"] + shift), "e": min(dur, s["e"] + shift), "t": s["t"]} for s in seg["subs"]]
    mutes = []
    if seg.get("full"):  # ouverture : gros mots coupés au son (estimés dans la ligne de sous-titre)
        for x in subs:
            for m in re.finditer(r"\[\s*_+\s*\]|\b(?:mother)?(?:fuck|shit|bitch|cunt)\w*", x["t"], re.I):
                t = x["s"] + (x["e"] - x["s"]) * (m.start() / max(1, len(x["t"])))
                mutes.append((max(0.0, t - 0.3), t + 0.5))
    subs = [s for s in _wrap_subs(subs) if s["e"] > s["s"]]
    if subs and subs[0]["t"][:1].islower():  # la transcription a perdu le début de la phrase (« Do you » …)
        subs[0] = dict(subs[0], t="..." + subs[0]["t"])
    quote = dict(seg["quote"], s=seg["quote"]["s"] + shift, e=seg["quote"]["e"] + shift) if seg.get("quote") else None
    framed = not seg.get("full")
    ass = os.path.join(workdir, os.path.basename(dest) + ".ass")
    clip_ass(ass, subs, framed, seg.get("credit") or "", seg.get("speaker") or "", quote, dur, accent, accent2,
             pill=pill, brand=brand)
    x, y, w, h = BOX
    ins = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", files["v"],
           "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", files["a"]]
    sub = f"subtitles={os.path.basename(ass)}:fontsdir=fonts"
    if framed:
        ins += ["-loop", "1", "-framerate", str(FPS), "-i", frame]
        g = (f"[0:v]fps={FPS},setsar=1,split[s1][s2];"
             f"[s1]scale=480:270:force_original_aspect_ratio=increase,crop=480:270,boxblur=12:2,"
             f"scale={W}:{H},eq=brightness=-0.22:saturation=0.75[bg];"
             f"[s2]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[c];"
             f"[bg][2:v]overlay=0:0:shortest=1[bf];[bf][c]overlay={x}:{y}[b0];[b0]{sub},format=yuv420p,{vfades(dur)}[v];")
    else:
        zw, zh = int(W * 1.04) // 2 * 2, int(H * 1.04) // 2 * 2
        g = (f"[0:v]fps={FPS},scale={zw}:{zh}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
             f"{sub},format=yuv420p,{vfades(dur)}[v];")
    mute = ("volume=0:enable='" + "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in mutes) + "',") if mutes else ""
    g += (f"[1:a]aresample=48000,{mute}loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,{afades(dur)},"
          f"aformat=channel_layouts=stereo[a]")
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


def load_photos(job_dir):
    """photos/photos.json (fait par la miniature : identité vérifiée par le texte de la source) → {nom: [(chemin,
    visage)]} ; seulement les photos nettes, sans texte ni filigrane."""
    import ast
    path = os.path.join(job_dir, "photos", "photos.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for name, items in data.items():
        for it in items:
            p = os.path.join(job_dir, "photos", it.get("file", ""))
            try:
                r = it.get("rate") or {}
                r = ast.literal_eval(r) if isinstance(r, str) else r
            except (ValueError, SyntaxError):
                r = {}
            if os.path.isfile(p) and r.get("face") and r.get("clear", True) and not r.get("watermark") \
                    and not r.get("text") and int(r.get("people") or 1) <= 2:
                out.setdefault(name, []).append((p, r["face"]))
    return out


def photo_still(path, face, dest):
    """Photo → image 3840×2160 cadrée sur le visage (placé à droite du centre, à 35 % de la hauteur) : jamais de
    tête coupée, la gauche reste libre pour le titre."""
    from PIL import Image, ImageOps
    with Image.open(path) as im0:
        im = ImageOps.exif_transpose(im0).convert("RGB")
    iw, ih = im.size
    cx, cy = (face[0] + face[2]) / 2 * iw, (face[1] + face[3]) / 2 * ih
    cw = min(iw, ih * 16 / 9)
    ch = cw * 9 / 16
    x0 = min(max(0, cx - cw * 0.62), iw - cw)
    y0 = min(max(0, cy - ch * 0.35), ih - ch)
    im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((2 * W, 2 * H), Image.LANCZOS).save(dest, quality=92)
    return dest


def narration_ass(dest, seg, dur, plan, acc, acc2):
    """Voix off : titre de l'info (le contexte) + logo ; rien d'autre."""
    ev = []
    brand = (plan.get("brand") or "NEWS").upper()
    ev.append(_ev(0, dur, "Tag", f"{{\\an9\\pos({W - 44},{34})\\fs56\\fnAnton\\b0}}{_ass_escape(brand)}", 2))
    head = seg.get("headline") or ("DROP YOUR THOUGHTS BELOW" if seg.get("outro") else "")
    if head:
        lines = _wrap(_ass_escape(head), 15)[:3]
        y0 = 280 if len(lines) < 3 else 200
        ev.append(_ev(0.25, dur, "Tag", f"{{\\pos(96,{y0})\\fad(250,0)}}"
                                        f"{'THE LATEST' if not seg.get('outro') else 'YOUR TAKE'}", 3))
        ev.append(_ev(0.4, dur, "Head", f"{{\\pos(96,{y0 + 70})\\fad(300,0)}}" + "\\N".join(lines), 3))
    if seg.get("outro") and plan.get("subscribe"):
        ev.append(_ev(1.0, dur, "Pill", f"{{\\an3\\pos({W - 60},{H - 120})\\fad(300,0)}}"
                                        f"{_ass_escape(plan['subscribe'])}", 4))
    return _write_ass(dest, _styles(acc, acc2, False), ev)


def render_narration(seg, audio, files, b0, workdir, dest, music, accent, plan, accent2=(255, 210, 31),
                     shade=None, photo=None):
    """Voix off sur la photo de la personne dont on parle (zoom lent) ou, à défaut, sur des images muettes de sa
    vidéo ; musique dessous ; coupes franches, sans bruitage."""
    dur = media.duration(audio) + 0.35
    ass = narration_ass(os.path.join(workdir, os.path.basename(dest) + ".ass"), seg, dur, plan, accent, accent2)
    n = max(1, int(dur * FPS))
    if photo:
        vin = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", photo]
        pre = f"[0:v]fps={FPS},setsar=1,"
    else:
        vin = ["-ss", f"{b0:.3f}", "-t", f"{dur:.3f}", "-i", files["v"]]
        pre = f"[0:v]fps={FPS},scale={2 * W}:{2 * H}:force_original_aspect_ratio=increase,crop={2 * W}:{2 * H},setsar=1,"
    ins = vin + ["-i", audio, "-stream_loop", "-1", "-i", music,
                 "-loop", "1", "-framerate", str(FPS), "-i", shade or make_shade(os.path.join(workdir, "shade.png"))]
    g = (pre + f"zoompan=z='1+0.05*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
         f"eq=brightness=-0.08:saturation=0.9[bb];[bb][3:v]overlay=0:0:shortest=1,"
         f"subtitles={os.path.basename(ass)}:fontsdir=fonts,format=yuv420p,{vfades(dur)}[v];"
         f"[1:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur=0.35[n];"
         f"[2:a]aresample=48000,volume=0.11,afade=t=in:d=0.4[m];"
         f"[n][m]amix=inputs=2:duration=first:normalize=0,aresample=48000,{afades(dur)}[a]")
    media.run(ins + ["-filter_complex", g, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *X264, *AAC,
                     os.path.basename(dest)], cwd=workdir)
    return dest


def render_sting(plan, workdir, dest, music, accent, accent2=(255, 210, 31), dur=4.5):
    """Logo après la voix off d'intro : nom de la chaîne + slogan, sur la musique, sans bruitage. Reste ~4 s et sort
    en fondu (l'utilisateur, 4 oct. : « il reste une seconde et après ça coupe »)."""
    bg = make_background(plan, os.path.join(workdir, "bg_plain.png"), box=False)
    brand = _ass_escape((plan.get("brand") or "NEWS").upper())
    slogan = _ass_escape(re.sub(r"^SUBSCRIBE FOR\s+", "", (plan.get("subscribe") or "").upper()))
    ev = [_ev(0.1, dur, "Brand", f"{{\\pos({W // 2},{H // 2 - 30})\\fscx115\\fscy115\\fad(200,0)"
                                 f"\\t(0,400,\\fscx100\\fscy100)\\t(400,{int(dur * 1000)},\\fscx106\\fscy106)}}{brand}", 2)]
    if slogan:
        ev.append(_ev(0.5, dur, "Slogan", f"{{\\pos({W // 2},{H // 2 + 260})\\fad(250,0)}}{slogan}", 2))
    ass = _write_ass(os.path.join(workdir, "sting.ass"), _styles(accent, accent2, False), ev)
    g = (f"[0:v]fps={FPS},format=rgb24,subtitles={os.path.basename(ass)}:fontsdir=fonts,format=yuv420p,"
         f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur - 0.6:.3f}:d=0.6[v];"
         f"[1:a]aresample=48000,volume=0.16,afade=t=in:d=0.3,afade=t=out:st={dur - 0.8:.3f}:d=0.8,"
         f"aformat=channel_layouts=stereo[a]")
    media.run(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", bg, "-stream_loop", "-1", "-i", music,
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
                            "https://upload.gofile.io/uploadfile"], capture_output=True, text=True,
                           creationflags=media._NO_WINDOW)
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
    # dossier neuf à chaque montage : des morceaux d'un ancien montage (dossier pas effacé, fichiers bloqués par un
    # processus resté ouvert) ne doivent jamais être repris (3 oct. : la v4 Gaethje contenait des morceaux de la v2)
    shutil.rmtree(os.path.join(work_root, "news_build", name), ignore_errors=True)
    work = os.path.join(work_root, "news_build", f"{name}-{time.strftime('%Y%m%d-%H%M%S')}")
    dl = os.path.join(work, "dl")
    os.makedirs(dl, exist_ok=True)
    log = log_to(os.path.join(job_dir, "build.log"))
    log(f"montage de {name} : {len(plan['segments'])} segments")
    accent = _hex(plan.get("accent"))
    accent2 = _hex(plan.get("accent2"), default=(255, 210, 31))
    shutil.copytree(FONTS, os.path.join(work, "fonts"), dirs_exist_ok=True)
    frame = make_frame(plan, os.path.join(work, "frame.png"))
    shade = make_shade(os.path.join(work, "shade.png"))
    photos = load_photos(job_dir)          # {personne: [(photo, visage)]} : voix off sur la personne dont on parle
    NAMES.clear()
    for nm in [x.get("speaker") or "" for x in plan["segments"]] + list((plan.get("thumb") or {}).get("people") or []) \
            + list((plan.get("spelling") or {}).values()):
        NAMES.update(w for w in str(nm).split() if w[:1].isupper())
    used = {}
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
    vids = list(dict.fromkeys(s["video"] for s in plan["segments"] if s["type"] == "clip"))
    for vid in vids:
        files[vid] = download(vid, dl, log)
    # YouTube bloque parfois quelques minutes (« confirm you're not a bot », 4 oct. : 5 vidéos sur 10 pendant que
    # deux montages téléchargeaient en même temps) : on réessaie après une pause
    for wait in (120, 300):
        miss = [v for v in vids if not files.get(v)]
        if not miss:
            break
        log(f"{len(miss)} vidéo(s) refusée(s) par YouTube : nouvel essai dans {wait // 60} min")
        time.sleep(wait)
        for vid in miss:
            files[vid] = download(vid, dl, log)
    clips = [s for s in plan["segments"] if s["type"] == "clip"]
    lost = [s for s in clips if not files.get(s["video"])]
    for vid in [v for v in vids if not files.get(v)]:
        log(f"!! vidéo {vid} impossible à télécharger : ses extraits et leurs voix off sautent")
    if clips and len(lost) > 0.25 * len(clips):
        raise RuntimeError(f"{len(lost)} extraits sur {len(clips)} impossibles à télécharger (YouTube) : "
                           "vidéo pas montée, à relancer plus tard")
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
            if not seg.get("full") and parts and not any(p.endswith("sting.mp4") for p in parts):
                # sans ouverture en extraits : le logo animé passe entre la voix off d'intro et le 1er extrait
                parts.append(render_sting(plan, work, os.path.join(work, "sting.mp4"), music, accent, accent2))
            if not os.path.isfile(dest):
                render_clip(seg, files[seg["video"]], frame, work, dest, accent, log, accent2=accent2, pill=pill,
                            brand=(plan.get("brand") or "").upper())
        else:
            nxt = next((s for s in segs[i + 1:] if s["type"] == "clip" and files.get(s["video"])), None)
            if nxt is None and seg.get("next_video") is not None:
                continue  # l'extrait annoncé n'existe plus : la voix off saute aussi
            own = next((s for s in segs[i + 1:] if s["type"] == "clip"), None)
            if i > 0 and not seg.get("outro") and own is not None and not files.get(own["video"]):
                continue  # jamais une voix off qui annonce un extrait absent (4 oct. : 8 voix off d'affilée)
            ref = nxt or next((s for s in reversed(segs[:i]) if s["type"] == "clip" and files.get(s["video"])), None)
            if ref is None:
                continue
            if parts and not any(p.endswith("sting.mp4") for p in parts):  # fin de l'ouverture : logo animé
                parts.append(render_sting(plan, work, os.path.join(work, "sting.mp4"), music, accent, accent2))
            seg = dict(seg, lower="" if seg.get("outro") else (nxt or {}).get("speaker", ""))
            # la photo de la 1re personne dont parle la voix off (sinon celle qui va parler) : l'intro « Ilia Topuria is
            # back in the gym » montrait Gaethje (qui parle juste après) sous le titre « TOPURIA RETURNS TO GYM »
            text = seg.get("text") or ""
            hits = [(text.find(n.split()[-1]), n) for n in photos if n.split()[-1] in text]
            who = min(hits)[1] if hits else ((nxt or ref).get("speaker") or "")
            still = None
            if photos.get(who):  # la photo de la personne dont parle la voix off (sinon : images de sa vidéo)
                k = used.get(who, 0)
                used[who] = k + 1
                p, face = photos[who][k % len(photos[who])]
                still = photo_still(p, face, os.path.join(work, f"p{i:03d}.jpg"))
            if not os.path.isfile(dest):
                b0 = broll_window(files[ref["video"]], ref["start"], ref["end"], media.duration(voices[i]) + 0.5)
                render_narration(seg, voices[i], files[ref["video"]], b0, work, dest, music, accent, plan,
                                 accent2=accent2, shade=shade, photo=still)
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
