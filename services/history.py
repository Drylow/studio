"""Format Histoire (Drylow Studio) — titre → vidéo documentaire façon « Dose of History ».

Étapes (chacune reprend là où elle s'est arrêtée) :
  script  → narration (services.history_ai.write_script)
  voice   → voix off + timings mot à mot (services.tts)
  plan    → plan visuel : images IA + templates animés calés sur les phrases
  images  → portraits du casting, plans, terrain de bataille, objets d'archive (services.ai)
  render  → musique + bruitages + sous-titres → timeline.json → rendu Remotion (history_engine/)
            → normalisation -14 LUFS.

Données : data/history/<id>/ (project.json, media/ = publicDir du rendu, vidéo finale à la racine).
"""
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import ai, media, tts
from services import align
from services import history_ai as HA
from services import history_geo as GEO
from services import history_sources as SRC
from services import history_audio as HAU
from services import history_channels as HC
from services import history_thumbs as TH
from services import pov_script as S
from services import pov_store as store
from services import runpod_render as RR

APP_DIR = store.APP_DIR
ENGINE_DIR = os.path.join(APP_DIR, "history_engine")

DEFAULT_VOICE = {"provider": "ai33", "voice": "VsVIOTkd9zjLUVaQO9TA", "speed": 0.9}  # « Earl Blackwood » (ElevenLabs via ai33pro), ~150 mots/min
EDGE_VOICE = "en-US-GuyNeural"
DEFAULTS = {"minutes": 3.0, "language": "en", "captions": True, "captions_after_hook": False, "film": 1.0,
            "music_volume": 0.06, "all_templates": False,
            # animations actives par défaut (bataille, graphique, itinéraire : dispo mais coupés)
            "templates": ["statement", "number", "map", "quote", "character", "compare", "archive"],
            "image_style": "paint", "channel": "",
            "cards_per_min": 1.5}
STAGES = ("script", "voice", "plan", "images", "render")
TAIL = 3.0  # secondes après la dernière phrase : la dernière animation se termine, la musique s'éteint


# ── Stockage ────────────────────────────────────────────────────────────────

def data_dir():
    return os.getenv("HISTORY_DATA_DIR") or os.path.join(os.path.dirname(store.data_dir()), "history")


def project_dir(pid):
    return os.path.join(data_dir(), pid)


def media_dir(pid):
    return os.path.join(project_dir(pid), "media")


def _path(pid):
    return os.path.join(project_dir(pid), "project.json")


def get_project(pid):
    if not store.valid_id(pid):
        return None
    return store._read_json(_path(pid))


def save_project(pr):
    pr["updated"] = store.now()
    os.makedirs(project_dir(pr["id"]), exist_ok=True)
    store._write_json(_path(pr["id"]), pr)
    return pr


def update_project(pid, fn):
    with store.lock_for(pid):
        pr = get_project(pid)
        if pr is None:
            raise RuntimeError("Projet introuvable.")
        fn(pr)
        return save_project(pr)


def list_projects():
    out = []
    root = data_dir()
    if os.path.isdir(root):
        for name in os.listdir(root):
            pr = get_project(name)
            if pr:
                out.append(pr)
    return sorted(out, key=lambda p: p.get("created", ""), reverse=True)


def delete_project(pid):
    if store.valid_id(pid):
        shutil.rmtree(project_dir(pid), ignore_errors=True)


def new_project(title, minutes=None, notes="", options=None):
    pr = {"id": store.new_id("hs"), "created": store.now(), "title": (title or "").strip(), "notes": notes or "",
          "minutes": float(minutes or DEFAULTS["minutes"]), "options": dict(DEFAULTS, **(options or {})),
          "voice_settings": dict(DEFAULT_VOICE), "script": None, "voice": None, "plan": None, "render": None}
    os.makedirs(media_dir(pr["id"]), exist_ok=True)
    return save_project(pr)


def stage(pr):
    if pr.get("render"):
        return "done"
    if pr.get("plan") and _missing_assets(pr):
        return "images"
    if pr.get("plan"):
        return "render"
    if pr.get("voice"):
        return "plan"
    if pr.get("script"):
        return "voice"
    return "script"


def summary(pr):
    job = store.running_job(pr["id"]) or store.last_job(pr["id"])
    plan = pr.get("plan") or {}
    segs = plan.get("segments") or []
    return {"id": pr["id"], "title": pr.get("title"), "minutes": pr.get("minutes"), "created": pr.get("created"),
            "stage": stage(pr), "duration": (pr.get("voice") or {}).get("duration"),
            "segments": len(segs), "cards": sum(1 for s in segs if s["type"] not in ("image", "video")),
            "images_missing": len(_missing_assets(pr)) if segs else None,
            "render": pr.get("render"), "thumbnail": pr.get("thumbnail"),
            "channel": (pr.get("options") or {}).get("channel") or "", "job": job.as_dict() if job else None}


# ── 1. Script ───────────────────────────────────────────────────────────────

def job_script(job, pid):
    pr = get_project(pid)
    key = (pr.get("options") or {}).get("channel")
    fos = None
    if HC.channel(key):
        # chaîne History Docs : FacelessOS (recherche, hooks, plan, rédaction, audit greenlight) avec ses skills
        job.update(0.01, "FacelessOS : préparation de la chaîne…")
        fch = HC.fos_channel(key)
        res = S.generate(fch, pr["title"], pr["minutes"], pr.get("notes", ""),
                         progress=lambda p, m, _partial=None: job.update(0.02 + 0.78 * p, m), history=_channel_history(key, pid))
        text, audit = res["script"], None
        try:  # comme les chaînes 2D : 2 tours d'audit greenlight en plus sur le script fini (redites, slop, rythme)
            text, audit = S.audit_script(fch, pr["title"], text, pr["minutes"], rounds=2,
                                         progress=lambda p, m, _partial=None: job.update(0.8 + 0.18 * p, m))
        except Exception as e:  # noqa: BLE001 — l'audit en plus est un bonus : le script du greenlight reste valable
            print(f"[audit] {e}", flush=True)
        sc = script_from_fos(text, pr["title"])
        fos = {"verdict": (res.get("review") or {}).get("verdict"), "rotation": (res.get("outline") or {}).get("rotation"),
               "files_used": (res.get("review") or {}).get("files_used"), "text": text,
               "audit": (audit or {}).get("verdict") if isinstance(audit, dict) else None}
    else:
        job.update(0.05, "Écriture du script (style documentaire)…")
        sc = HA.write_script(pr["title"], pr["minutes"], pr.get("notes", ""), pr["options"].get("language", "en"))

    def save(x):
        x["script"], x["fos"] = sc, fos
        x["voice"] = x["plan"] = x["render"] = None
    update_project(pid, save)
    job.update(1.0, f"Script prêt : {len(HA.narration(sc).split())} mots.")


def script_from_fos(text, title):
    """Texte FacelessOS (hook sans titre, puis « ## chapitre ») → {title, hook, sections} de l'outil."""
    parts = S.parse(text)
    hook = parts[0][1] if parts and not parts[0][0] else ""
    body = parts[1:] if hook else parts
    sections = [{"heading": h or f"Part {i + 1}", "text": re.sub(r"\s+", " ", t).strip()} for i, (h, t) in enumerate(body)]
    if not hook and sections:
        hook = sections.pop(0)["text"]
    return {"title": title, "hook": re.sub(r"\s+", " ", hook).strip(), "sections": sections}


def _channel_history(key, pid):
    """Les dernières vidéos de la chaîne, pour que FacelessOS fasse tourner les angles (rotation)."""
    out = []
    for p in list_projects():
        if p["id"] != pid and (p.get("options") or {}).get("channel") == key and p.get("script"):
            out.append({"title": p["title"], "hook": p["script"].get("hook", ""),
                        "rotation": json.dumps((p.get("fos") or {}).get("rotation") or "")})
    return out[:3]


# ── 2. Voix ─────────────────────────────────────────────────────────────────

def script_timed_words(text, asr):
    """Mots du SCRIPT (orthographe exacte) avec les timings de la voix.

    Alignement de séquence (difflib) entre les tokens du script et les mots entendus par le
    TTS/la transcription ; les mots non retrouvés sont interpolés entre leurs voisins. Évite les
    « Hannibal Barsa » quand la transcription Algrow entend mal un nom."""
    import difflib
    toks = (text or "").split()
    if not toks or not asr:
        return asr
    na = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in toks]
    nb = [re.sub(r"[^a-z0-9]", "", w["w"].lower()) for w in asr]
    times = [None] * len(toks)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=na, b=nb, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (asr[j1 + k]["s"], asr[j1 + k]["e"])
        elif tag == "replace" and j2 > j1:  # bloc de longueurs différentes : on répartit la durée
            s0, e0 = asr[j1]["s"], asr[j2 - 1]["e"]
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = (s0 + (e0 - s0) * k / n, s0 + (e0 - s0) * (k + 1) / n)
    known = [i for i, t in enumerate(times) if t]
    if not known:
        return asr
    out = []
    for i, tok in enumerate(toks):
        t = times[i]
        if not t:
            a = max((k for k in known if k < i), default=None)
            b = min((k for k in known if k > i), default=None)
            if a is None:
                t = (times[b][0], times[b][0])
            elif b is None:
                t = (times[a][1], times[a][1] + 0.25)
            else:
                f = (i - a) / (b - a)
                st = times[a][1] + (times[b][0] - times[a][1]) * f
                t = (st, st + 0.2)
        out.append({"w": tok, "s": round(t[0], 3), "e": round(max(t[1], t[0] + 0.05), 3), "t": i})
    return out


def sentences_from_words(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?][\"'”’)]*$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"text": " ".join(x["w"] for x in s), "start": s[0]["s"], "end": s[-1]["e"], "w0": s[0], "n": len(s)}
            for s in out]


def job_voice(job, pid):
    pr = get_project(pid)
    text = HA.narration(pr["script"])
    vs = pr.get("voice_settings") or DEFAULT_VOICE
    d = media_dir(pid)
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    dest = os.path.join(d, "audio", "voice.mp3")
    provider = vs.get("provider", DEFAULT_VOICE["provider"])
    voice = vs.get("voice") or (EDGE_VOICE if provider == "edge" else "")
    job.update(0.05, f"Voix off ({provider})…")
    res = tts.synthesize(text, dest, provider=provider, voice=voice, speed=vs.get("speed", 1.0),
                         progress=lambda i, n: job.update(0.05 + 0.85 * i / max(1, n), f"Voix off {min(i + 1, n)}/{n}…"))
    # timings mesurés sur l'audio (Whisper) quand c'est possible : sous-titres calés sur toute la vidéo
    job.update(0.92, "Calage des sous-titres sur la voix…")
    heard = align.words_from_audio(dest, pr["options"].get("language", "en")) or res["words"]
    words = script_timed_words(text, heard)
    with open(os.path.join(project_dir(pid), "words.json"), "w", encoding="utf-8") as f:
        json.dump(words, f)
    hook_n = len(pr["script"]["hook"].split())
    hook_end = words[min(hook_n, len(words)) - 1]["e"] if words else 0

    def save(x):
        x["voice"] = {"file": "audio/voice.mp3", "duration": round(res["duration"], 3), "hook_end": round(hook_end, 3),
                      "words": len(words)}
        x["plan"] = x["render"] = None
    update_project(pid, save)
    job.update(1.0, f"Voix prête : {res['duration'] / 60:.1f} min.")


def chapters(pr):
    """Chapitres YouTube (« 00:00 Intro », puis un par partie du script) calés sur la voix."""
    words, sc = load_words(pr["id"]), pr.get("script") or {}
    out, i = ["00:00 Intro"], len((sc.get("hook") or "").split())
    for sec in sc.get("sections") or []:
        if words and i < len(words):
            t = int(words[i]["s"])
            out.append(f"{t // 60:02d}:{t % 60:02d} {sec['heading']}")
        i += len(sec["text"].split())
    return out


def load_words(pid):
    try:
        with open(os.path.join(project_dir(pid), "words.json"), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return []


# ── 3. Plan visuel ──────────────────────────────────────────────────────────

def _geo_to_xy(stops):
    """lat/lon réels → positions 8-92 % sur le plan de la carte (projection simple, ratio conservé)."""
    pts = [(float(s.get("lon", 0)), float(s.get("lat", 0))) for s in stops]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0
    scale = min(76 / w, 48 / (h * 16 / 9)) if w and h else 1
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    out = []
    for s, (lon, lat) in zip(stops, pts):
        out.append({"name": s.get("name", ""), "x": round(48 + (lon - cx) * scale, 2),
                    "y": round(54 - (lat - cy) * scale * 16 / 9, 2),
                    "coords": f"LAT {abs(lat):.2f}° {'N' if lat >= 0 else 'S'} | LNG {abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"})
    return out


def _build_map(seg, b):
    """Carte de mouvements : vraies côtes autour des lieux, flèches A → B dans l'ordre, marqueur de bataille.

    Mise en page « propre » : les déplacements enchaînés d'un même camp ne font qu'une flèche, la flèche
    s'arrête avant la ville, les lieux trop proches sont fusionnés, et chaque étiquette est placée là où
    elle ne touche ni une flèche, ni une autre étiquette, ni le marqueur de bataille, ni le cartouche."""
    pls = []
    for p in b.get("places") or []:
        try:
            pls.append({"name": str(p["name"])[:40], "lat": float(p["lat"]), "lon": float(p["lon"])})
        except (KeyError, TypeError, ValueError):
            continue
    if len(pls) < 2:
        return None
    try:
        geo = GEO.build_map(pls)
    except Exception as e:  # noqa: BLE001 — pas de données géo : la carte devient une phrase choc
        print(f"[map] {e}", flush=True)
        return None
    xy = {k.lower(): v for k, v in geo["xy"].items()}
    bat = str(b.get("battle") or "").lower()
    # 1. trajets (noms → points), puis fusion des trajets enchaînés d'un même camp
    raw = []
    for k, m in enumerate([m for m in b.get("moves") or [] if isinstance(m, dict)][:4]):
        names = [m.get("from")] + list(m.get("via") or []) + [m.get("to")]
        names = [str(x).lower() for x in names if x and str(x).lower() in xy]
        if len(names) < 2:
            continue
        side = m.get("side") if m.get("side") in ("a", "b") else ("a", "b")[k % 2]
        if raw and raw[-1]["side"] == side and raw[-1]["names"][-1] == names[0]:
            raw[-1]["names"] += names[1:]
            continue
        raw.append({"names": names, "side": side, "label": str(m.get("label") or "")[:22]})
    if not raw:
        return None
    # 2. lieux : on garde les plus importants quand deux points se touchent presque
    used = {n for r in raw for n in r["names"]}
    ends = {r["names"][0] for r in raw} | {r["names"][-1] for r in raw}
    rank = lambda n: 3 if n == bat else 2 if n in ends else 1 if n in used else 0  # noqa: E731
    kept = []
    for p in sorted(pls, key=lambda p: -rank(p["name"].lower())):
        x, y = geo["xy"][p["name"]]
        if all(math.hypot(x - k["x"], y - k["y"]) > 46 for k in kept):
            kept.append({"name": p["name"], "x": x, "y": y, "key": p["name"].lower()})
    alias = {}
    named = (str(b.get("title") or "") + " " + str(b.get("subtitle") or "")).lower()
    for p in pls:  # un lieu fusionné pointe vers le lieu gardé le plus proche
        x, y = geo["xy"][p["name"]]
        k = alias[p["name"].lower()] = min(kept, key=lambda k: math.hypot(x - k["x"], y - k["y"]))
        if k["name"].lower() not in named and p["name"].lower() in named:
            k["name"] = p["name"]  # « Battle » absorbé par « Hastings » : on affiche le nom qu'on entend
    n = len(raw)
    moves = []
    for k, r in enumerate(raw):
        pts = []
        for nm in r["names"]:
            pt = [alias[nm]["x"], alias[nm]["y"]]
            if not pts or pts[-1] != pt:
                pts.append(pt)
        if len(pts) < 2:
            continue
        end_key = alias[r["names"][-1]]["key"]
        pts = _trim_end(pts, 50 if end_key == bat else 24)  # la pointe s'arrête avant le point / le marqueur
        st = 0.1 + k * (0.6 / n)
        moves.append({"path": [[round(x, 1), round(y, 1)] for x, y in pts], "side": r["side"], "label": r["label"],
                      "start": round(st, 3), "end": round(st + 0.6 / n * 0.9, 3)})
    if not moves:
        return None
    last = max(mv["end"] for mv in moves)
    bk = alias[bat] if bat in alias else None
    battle = {"x": bk["x"], "y": bk["y"], "at": round(min(0.9, last + 0.03), 3)} if bk else None
    places = [{"name": k["name"], "x": k["x"], "y": k["y"], "kind": "battle" if bk and k is bk else "city",
               **({"at": battle["at"]} if bk and k is bk else {})} for k in kept]
    title = str(b.get("title") or "")[:40]
    focus = [battle["x"], battle["y"]] if battle else moves[-1]["path"][-1]
    _layout_map_labels(places, moves, battle, title, focus)
    seg.update(title=title, subtitle=str(b.get("subtitle") or "")[:40], land=geo["land"],
               rivers=geo["rivers"], places=places, moves=moves, focus=focus, **({"battle": battle} if battle else {}))
    return seg


def _trim_end(pts, dist):
    """Recule la fin du tracé de `dist` px le long du dernier segment."""
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    seg = math.hypot(x1 - x0, y1 - y0)
    if seg <= dist + 8:
        return pts
    t = (seg - dist) / seg
    return pts[:-1] + [[x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]]


def _curve_samples(pts, per=16):
    """Mêmes courbes que le template (Catmull-Rom → Bézier), échantillonnées pour les collisions."""
    out = [tuple(pts[0])]
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        for k in range(1, per + 1):
            t = k / per
            u = 1 - t
            out.append((u ** 3 * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p2[0],
                        u ** 3 * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p2[1]))
    return out


def _layout_map_labels(places, moves, battle, title, focus, zoom=1.1):
    """Place chaque étiquette (lieux puis armées) à l'endroit le plus dégagé parmi plusieurs positions."""
    W, H = 1920, 1080
    arrow = [p for m in moves for p in _curve_samples(m["path"])]
    fx, fy = focus

    def unzoom(b):  # le cartouche et la rose ne zooment pas : on couvre aussi leur emprise en fin de zoom
        return (min(b[0], fx + (b[0] - fx) / zoom), min(b[1], fy + (b[1] - fy) / zoom),
                max(b[2], fx + (b[2] - fx) / zoom), max(b[3], fy + (b[3] - fy) / zoom))

    fixed = [unzoom((40, 40, 130 + 31 * len(title), 190)),  # cartouche titre
             unzoom((1690, 40, 1880, 210))]  # rose des vents
    bottom = fy + (H - 130 - fy) / zoom  # bande des sous-titres
    placed = []

    def hits(box, pad):
        x0, y0, x1, y1 = box
        return sum(1 for (px, py) in arrow if x0 - pad <= px <= x1 + pad and y0 - pad <= py <= y1 + pad)

    def inter(a, b):
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    def score(box, order, own=None):
        x0, y0, x1, y1 = box
        sc = hits(box, 14) * 8 + order * 0.6
        sc += sum(40 for f in fixed + placed if inter(box, f))
        sc += 100 if (x0 < 24 or y0 < 24 or x1 > W - 24 or y1 > bottom) else 0
        if battle:
            cx = min(max(battle["x"], x0), x1)
            cy = min(max(battle["y"], y0), y1)
            sc += 60 if math.hypot(cx - battle["x"], cy - battle["y"]) < 58 else 0
        for p in places:  # ne jamais recouvrir un point de ville
            if p is not own and x0 - 10 <= p["x"] <= x1 + 10 and y0 - 10 <= p["y"] <= y1 + 10:
                sc += 30
        return sc

    def best(cands, w, h, own=None):
        boxes = [(i, (x, y, x + w, y + h)) for i, (x, y) in enumerate(cands)]
        i, box = min(boxes, key=lambda ib: score(ib[1], ib[0], own))
        placed.append(box)
        return box

    for p in sorted(places, key=lambda p: p["kind"] != "battle"):
        big = p["kind"] == "battle"
        w, h = (28 if big else 22) * len(p["name"]) + 18, 44 if big else 38
        r = 62 if big else 14  # le nom de la bataille se pose hors du marqueur
        x, y = p["x"], p["y"]
        cands = [(x + r, y - h / 2), (x - r - w, y - h / 2), (x - w / 2, y - r - h), (x - w / 2, y + r),
                 (x + r * 0.7, y - r * 0.7 - h), (x + r * 0.7, y + r * 0.7), (x - r * 0.7 - w, y - r * 0.7 - h),
                 (x - r * 0.7 - w, y + r * 0.7)]
        box = best(cands, w, h, p)
        p["dx"], p["dy"] = round(box[0] - x, 1), round(box[1] - y, 1)
    for m in moves:
        if not m.get("label"):
            continue
        w, h = 16 * len(m["label"]) + 30, 38
        s = _curve_samples(m["path"])
        cands = []
        for f in (0.3, 0.5, 0.7, 0.15, 0.85):
            i = min(len(s) - 2, max(1, int(f * (len(s) - 1))))
            (ax, ay), (bx, by) = s[i - 1], s[i + 1]
            nx, ny = -(by - ay), bx - ax
            nn = math.hypot(nx, ny) or 1
            nx, ny = nx / nn, ny / nn
            off = 24 + w / 2 * abs(nx) + h / 2 * abs(ny)  # boîte posée à côté du trait, jamais dessus
            for side in (1, -1):
                cx, cy = s[i][0] + side * nx * off, s[i][1] + side * ny * off
                cands.append((cx - w / 2, cy - h / 2))
        box = best(cands, w, h)
        m["labelAt"] = [round((box[0] + box[2]) / 2, 1), round(box[1], 1)]


def _find_phrase(words, phrase, t0, t1):
    """Instant (s) où la phrase est prononcée dans [t0, t1] — révèle la phrase choc au bon mot."""
    toks = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in (phrase or "").split()]
    toks = [t for t in toks if t]
    if not toks:
        return None
    ws = [w for w in words if t0 - 0.05 <= w["s"] <= t1]
    norm = [re.sub(r"[^a-z0-9]", "", w["w"].lower()) for w in ws]
    for i in range(len(ws)):
        if norm[i:i + len(toks)] == toks:
            return ws[i]["s"]
    for i in range(len(ws)):  # repli : premier mot
        if norm[i] == toks[0]:
            return ws[i]["s"]
    return None


# couverture alternative quand un plan du hook dure trop : on découpe en plusieurs plans (~5 s), comme la référence
_COVERAGE = ("", "Same moment, tighter: extreme close-up of the main subject's face and eyes.",
             "Same moment from further back: wide shot showing the surroundings and the scale.",
             "Same moment, low-angle close-up of the main subject.",
             "Same moment, insert detail: hands, weapons, equipment.")


def _split_hook_shot(seg, hook_end, max_len=7.5, target=5.5):
    if seg["type"] != "image" or seg["start"] >= hook_end or seg["end"] - seg["start"] <= max_len:
        return [seg]
    n = min(len(_COVERAGE), int(-(-(seg["end"] - seg["start"]) // target)))
    step = (seg["end"] - seg["start"]) / n
    base = seg["src"][:-4]
    out = []
    for k in range(n):
        piece = dict(seg, start=round(seg["start"] + k * step, 3), end=round(seg["start"] + (k + 1) * step, 3),
                     src=seg["src"] if k == 0 else f"{base}_{k}.jpg", motion=("in", "out")[k % 2],
                     _prompt=(seg.get("_prompt", "") + " " + _COVERAGE[k]).strip())
        if k:
            piece.pop("label", None)
            piece.pop("stamp", None)
        out.append(piece)
    return out


def _norm_tok(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())


def _quote_times(words, text, t0, t1):
    """Instant (s, relatif au segment) où chaque mot de la citation est prononcé, ou None.

    Recherche séquentielle tolérante (mots sautés / ponctuation) ; il faut retrouver au moins 60 %
    des mots, les autres sont interpolés."""
    toks = [_norm_tok(w) for w in re.sub(r"^[\"“”«»\s]+|[\"“”«»\s]+$", "", text or "").split()]
    toks = [t for t in toks if t] if toks else []
    if not toks:
        return None
    ws = [w for w in words if t0 - 0.3 <= w["s"] <= t1 + 0.3]
    norm = [_norm_tok(w["w"]) for w in ws]
    best = None
    for s0 in range(len(ws)):
        if norm[s0] != toks[0]:
            continue
        found, j = [], s0
        for tk in toks:
            k = next((k for k in range(j, min(j + 4, len(ws))) if norm[k] == tk), None)
            found.append(None if k is None else ws[k]["s"])
            if k is not None:
                j = k + 1
        hits = sum(1 for f in found if f is not None)
        if best is None or hits > best[0]:
            best = (hits, found)
    if not best or best[0] < 0.6 * len(toks):
        return None
    found = best[1]
    known = [(i, f) for i, f in enumerate(found) if f is not None]
    out = []
    for i, f in enumerate(found):
        if f is None:
            a = max((k for k in known if k[0] < i), default=known[0], key=lambda k: k[0])
            b = min((k for k in known if k[0] > i), default=known[-1], key=lambda k: k[0])
            f = a[1] if a[0] == b[0] else a[1] + (b[1] - a[1]) * (i - a[0]) / (b[0] - a[0])
        out.append(round(max(0.0, f - t0), 3))
    return out


def build_segments(plan, sentences, words, duration, hook_end, allowed=None, max_cards=None):
    beats = sorted(plan["beats"], key=lambda b: int(b.get("at", 0) or 0))
    seen, clean = set(), []
    for b in beats:
        at = max(0, min(len(sentences) - 1, int(b.get("at", 0) or 0)))
        if at in seen:
            continue
        seen.add(at)
        b["at"] = at
        clean.append(b)
    if clean and clean[0]["at"] != 0:
        clean[0]["at"] = 0
    end_total = duration + TAIL
    starts = [0.0 if i == 0 else sentences[b["at"]]["start"] for i, b in enumerate(clean)]
    segs = []
    cast = plan.get("cast") or []
    portrait = lambda name: f"images/cast_{HA.slug(name)}.jpg" if name else None  # noqa: E731
    n_img = 0
    labelled, n_stamps, n_char = set(), 0, 0
    allowed = set(allowed or HA.TEMPLATES)
    n_cards = 0
    for i, b in enumerate(clean):
        start = starts[i]
        end = starts[i + 1] if i + 1 < len(clean) else end_total
        if end - start < 1.6 and segs:  # trop court : le précédent continue
            segs[-1]["end"] = end
            continue
        t = b["type"]
        if t != "image":
            # type coupé, ou budget d'animations dépassé (les citations restent) → image du passage
            over = max_cards is not None and n_cards >= max_cards and t != "quote"
            if t not in allowed or over or t not in HA.TEMPLATES:
                said = " ".join(x["text"] for x in sentences if start - 0.05 <= x["start"] < end)
                b = {"type": "image", "prompt": b.get("prompt") or f"A believable scene showing: {said}",
                     "chars": b.get("chars") or ([b["portrait"]] if b.get("portrait") else [])}
                t = "image"
            else:
                n_cards += 1
        seg = {"start": round(start, 3), "end": round(end, 3), "type": t}
        if t == "image":
            in_hook = start < hook_end
            motion = b.get("motion") if b.get("motion") in ("in", "out", "left", "right") else None
            if motion in ("left", "right") and b.get("chars"):
                motion = None  # pas de pan sur un personnage : zoom ancré sur les visages
            seg.update(type="image", src=f"images/shot_{n_img:03d}.jpg",
                       motion=motion or ("in" if n_img % 2 == 0 else "out"),
                       strength=0.12 if in_hook else 0.07,
                       _prompt=b.get("prompt") or "", _chars=b.get("chars") or [])
            lab = b.get("label")
            if isinstance(lab, dict) and lab.get("name") and lab["name"].lower() not in labelled:
                labelled.add(lab["name"].lower())
                seg["label"] = {"name": lab["name"][:40], "role": (lab.get("role") or "")[:50]}
            if b.get("stamp") and n_stamps < 3:
                seg["stamp"] = str(b["stamp"]).upper()[:60]
                n_stamps += 1
            n_img += 1
        elif t == "statement":
            seg["text"] = (b.get("text") or "").upper()
            at = _find_phrase(words, b.get("say") or b.get("text", "").replace("*", ""), start, end)
            seg["reveal"] = round(max(0.0, (at or start) - start), 3)
            if b.get("kicker"):
                seg["kicker"] = str(b["kicker"])[:50]
        elif t == "number":
            try:
                value = float(str(b.get("value", 0)).replace(",", ""))
            except ValueError:
                value = 0
            seg.update(value=int(value) if value == int(value) else value, prefix=b.get("prefix") or "",
                       suffix=b.get("suffix") or "", label=(b.get("label") or "")[:40], sub=(b.get("sub") or "")[:80])
            at = _find_phrase(words, b.get("say") or "", start, end)
            seg["reveal"] = round(max(0.0, (at or start) - start), 3)
            if not value:
                seg = {"start": seg["start"], "end": seg["end"], "type": "statement", "text": seg["label"].upper(), "reveal": 0}
        elif t == "battle":
            seg.update(title=b.get("title", ""), subtitle=b.get("subtitle", ""), terrain=f"images/terrain_{i:03d}.jpg",
                       _prompt=b.get("terrain_prompt") or "dry open plain with a river", labels=b.get("labels") or [],
                       units=[{k: u[k] for k in ("label", "side", "kind", "x", "y", "to", "move", "w", "h", "trail") if k in u}
                              for u in b.get("units") or [] if "x" in u and "y" in u])
            if isinstance(b.get("line"), dict):
                seg["line"] = b["line"]
        elif t == "character":
            seg.update(name=b.get("name", ""), role=b.get("role", ""), facts=b.get("facts") or [],
                       image=portrait(b.get("portrait") or b.get("name")), _cast=b.get("portrait") or b.get("name"),
                       variant=("right", "left", "full")[n_char % 3])
            n_char += 1
        elif t == "compare":
            for side in ("left", "right"):
                s = b.get(side)
                if isinstance(s, dict):
                    seg[side] = {"title": s.get("title", ""), "subtitle": s.get("subtitle", ""), "stats": s.get("stats") or []}
                    if s.get("portrait"):
                        seg[side]["image"] = portrait(s["portrait"])
                        seg[side]["_cast"] = s["portrait"]
            if "left" not in seg:
                seg.update(type="statement", text=(b.get("title") or "THE NUMBERS").upper(), reveal=0)
        elif t == "chart":
            seg.update(title=b.get("title", ""), subtitle=b.get("subtitle", ""),
                       bars=[{"label": x.get("label", ""), "value": float(x.get("value") or 0), "side": x.get("side", "neutral"),
                              **({"display": x["display"]} if x.get("display") else {})} for x in b.get("bars") or []])
        elif t == "archive":
            seg.update(title=b.get("title", ""), note=b.get("note", ""), image=f"images/archive_{i:03d}.jpg",
                       tilt=(-0.6, 0.7)[i % 2], _prompt=b.get("prompt") or b.get("title", ""),
                       _search=b.get("search") or b.get("title", ""))
        elif t == "map":
            seg = _build_map(seg, b) or {"start": seg["start"], "end": seg["end"], "type": "statement",
                                          "text": (b.get("title") or "").upper(), "reveal": 0}
        elif t == "route":
            stops = [s for s in b.get("stops") or [] if "lat" in s and "lon" in s]
            seg.update(title=b.get("title", ""), subtitle=b.get("subtitle", ""), stops=_geo_to_xy(stops) if len(stops) >= 2 else [])
            if len(seg["stops"]) < 2:
                seg.update(type="statement", text=(b.get("title") or "").upper(), reveal=0)
        elif t == "quote":
            seg.update(text=b.get("text", ""), author=b.get("author", ""), source=b.get("source", ""))
            times = _quote_times(words, seg["text"], start, end)
            if times:
                seg["words"] = times
            if b.get("portrait"):
                seg.update(image=portrait(b["portrait"]), _cast=b["portrait"])
        segs.extend(_split_hook_shot(seg, hook_end))
    _ensure_card_time(segs)
    return segs, cast


# durée minimale de chaque carte (s), comme la référence (10-20 s par carte) : l'animation se termine,
# puis la carte TIENT pendant que la narration continue. Phrase choc : 5 s après son apparition ;
# citation : 4,5 s après le dernier mot prononcé.
CARD_MIN = {"statement": 6.0, "number": 7.0, "map": 13.0, "character": 11.0, "compare": 13.0, "chart": 11.0, "archive": 9.0, "route": 12.0,
            "battle": 15.0, "quote": 9.0}
MIN_IMAGE = 3.0


def _card_need(s):
    want = CARD_MIN.get(s["type"], 0)
    if s["type"] in ("statement", "number"):
        want = max(want, s.get("reveal", 0) + 5.0)
    if s["type"] == "quote" and s.get("words"):
        want = max(want, s["words"][-1] + 4.5)
    return want - (s["end"] - s["start"])


def _ensure_card_time(segs):
    """Allonge les cartes trop courtes sur les images qui suivent (une image trop réduite est absorbée,
    la carte reste alors à l'écran pendant ce passage), puis si besoin sur l'image d'avant."""
    i = 0
    while i < len(segs):
        s = segs[i]
        if s["type"] in CARD_MIN:
            need = _card_need(s)
            while need > 0 and i + 1 < len(segs) and segs[i + 1]["type"] == "image":
                nxt = segs[i + 1]
                room = (nxt["end"] - nxt["start"]) - MIN_IMAGE
                if room >= need:
                    nxt["start"] = round(nxt["start"] + need, 3)
                    s["end"] = round(s["end"] + need, 3)
                    need = 0
                else:  # image trop courte pour céder ce temps : la carte la recouvre entièrement
                    s["end"] = nxt["end"]
                    segs.pop(i + 1)
                    need = _card_need(s)
            prv = segs[i - 1] if i > 0 else None
            if need > 0 and prv and prv["type"] == "image":
                take = min(need, max(0.0, (prv["end"] - prv["start"]) - MIN_IMAGE))
                prv["end"] = round(prv["end"] - take, 3)
                s["start"] = round(s["start"] - take, 3)
                if s["type"] in ("statement", "number"):
                    s["reveal"] = round(s.get("reveal", 0) + take, 3)
                if s.get("words"):
                    s["words"] = [round(t + take, 3) for t in s["words"]]
        i += 1


def rebuild_segments(pid):
    """Recalcule le montage depuis le plan déjà écrit (aucun appel IA) : timings, durées, mots."""
    pr = get_project(pid)
    words = load_words(pid)
    sents = sentences_from_words(words)
    opts = dict(DEFAULTS, **(pr.get("options") or {}))
    duration = pr["voice"]["duration"]
    max_cards = max(2, int(round(duration / 60 * float(opts["cards_per_min"]))))
    plan = pr["plan"]
    segs, cast = build_segments({"beats": plan["beats"], "cast": plan.get("cast") or []}, sents, words, duration,
                                pr["voice"].get("hook_end") or 0, allowed=opts["templates"], max_cards=max_cards)

    def save(x):
        x["plan"]["segments"] = segs
        x["render"] = None
    return update_project(pid, save)


def _diversify(segs, sents, cast, style):
    imgs = [s for s in segs if s["type"] == "image"]
    items = []
    for k, s in enumerate(imgs):
        mid = (s["start"] + s["end"]) / 2
        said = " ".join(x["text"] for x in sents if x["start"] < s["end"] and x["end"] > s["start"]) or \
            " ".join(x["text"] for x in sents if x["start"] <= mid <= x["end"])
        items.append({"i": k, "text": said, "prompt": s.get("_prompt", ""), "chars": s.get("_chars") or []})
    name = HA.image_style(style)["name"]
    chunks = [items[k:k + 45] for k in range(0, len(items), 45)]  # vidéo longue : le monteur image travaille par lots
    with ThreadPoolExecutor(max_workers=4) as ex:
        done = list(ex.map(lambda c: HA.diversify_shots(c, cast, name), chunks))
    for s, it in zip(imgs, [it for c in done for it in c]):
        s["_prompt"], s["_chars"] = it["prompt"], it["chars"]
    _vary_gaze(imgs)


FACE_CAMERA = " The person faces the camera, eyes looking straight at the viewer."


def _vary_gaze(imgs):
    """Un plan à personnage sur deux regarde la caméra : sinon tout le monde finit de profil, à gauche ou à droite."""
    k = 0
    for s in imgs:
        p = s.get("_prompt") or ""
        if not s.get("_chars") or FACE_CAMERA in p:
            continue
        if k % 2 == 0 and not any(w in p.lower() for w in ("camera", "viewer", "lens")):
            s["_prompt"] = p.rstrip() + FACE_CAMERA
        k += 1


PLAN_CHUNK = 90  # phrases par appel au-delà desquelles on planifie par morceaux (vidéos longues)


def _plan_all(job, sents, duration, hook_idx, allowed, max_cards, require_all=False):
    """Plan visuel ; une vidéo longue est planifiée par morceaux (le 1er fixe le casting, les autres en parallèle)."""
    rows = [{"text": s["text"], "start": s["start"], "end": s["end"]} for s in sents]
    if len(rows) <= PLAN_CHUNK * 1.3:
        return HA.plan_visuals(rows, duration, hook_idx, allowed=allowed, max_cards=max_cards, require_all=require_all)
    n = -(-len(rows) // PLAN_CHUNK)
    size = -(-len(rows) // n)
    bounds = [(k * size, min(len(rows), (k + 1) * size)) for k in range(n)]

    def cards_for(a, b):
        return max(1, int(round(max_cards * (rows[b - 1]["end"] - rows[a]["start"]) / max(1.0, duration))))

    def retry(fn, *a, **kw):  # une partie qui tombe sur une coupure réseau réessaie seule (pas tout le plan)
        for t in range(3):
            try:
                return fn(*a, **kw)
            except Exception as e:  # noqa: BLE001
                if t == 2:
                    raise
                print(f"[plan] partie à refaire : {str(e)[:120]}", flush=True)
                time.sleep(30 * (t + 1))

    a, b = bounds[0]
    job.update(0.12, f"Plan visuel : partie 1/{n}…")
    head = retry(HA.plan_visuals, rows[a:b], duration, hook_idx, allowed=allowed, max_cards=cards_for(a, b))
    cast = head["cast"]
    parts = {0: head}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(retry, HA.plan_visuals, rows[a:b], duration, -1, allowed, cards_for(a, b), False, a, cast): k
                for k, (a, b) in enumerate(bounds) if k}
        for fut in as_completed(futs):
            parts[futs[fut]] = fut.result()
            job.update(0.12 + 0.5 * len(parts) / n, f"Plan visuel : {len(parts)}/{n} parties…")
    beats, names = [], {c.get("name") for c in cast}
    for k in range(n):
        lo, hi = bounds[k]
        part = [x for x in parts[k]["beats"] if lo <= int(x.get("at", lo) or 0) < hi] or parts[k]["beats"][:1]
        if part and int(part[0].get("at", 0) or 0) != lo:
            part[0]["at"] = lo
        beats += part
        for c in parts[k]["cast"]:
            if c.get("name") not in names:
                cast.append(c)
                names.add(c.get("name"))
    return {"cast": cast, "beats": beats}


def job_plan(job, pid):
    pr = get_project(pid)
    words = load_words(pid)
    sents = sentences_from_words(words)
    duration = pr["voice"]["duration"]
    hook_end = pr["voice"].get("hook_end") or 20
    hook_idx = max([i for i, s in enumerate(sents) if s["end"] <= hook_end + 0.2] or [0])
    job.update(0.1, "Plan visuel : images, cartes, fiches et animations…")
    opts = dict(DEFAULTS, **(pr.get("options") or {}))
    allowed = opts["templates"]
    max_cards = max(2, int(round(duration / 60 * float(opts["cards_per_min"]))))
    plan = _plan_all(job, sents, duration, hook_idx, allowed, max_cards, opts.get("all_templates", False))
    segs, cast = build_segments(plan, sents, words, duration, hook_end, allowed=allowed, max_cards=max_cards)
    job.update(0.7, "Monteur image : variété des plans…")
    _diversify(segs, sents, cast, opts.get("image_style"))

    def save(x):
        x["plan"] = {"cast": cast, "segments": segs, "beats": plan["beats"]}
        x["render"] = None
    update_project(pid, save)
    kinds = {}
    for s in segs:
        kinds[s["type"]] = kinds.get(s["type"], 0) + 1
    job.update(1.0, "Plan prêt : " + ", ".join(f"{v} {k}" for k, v in kinds.items()))


# ── 4. Images ───────────────────────────────────────────────────────────────

def _asset_requests(pr):
    """[(chemin relatif, kind, prompt, refs_cast)] de toutes les images nécessaires."""
    plan = pr.get("plan") or {}
    cast = plan.get("cast") or []
    reqs, wanted_cast = [], set()
    for s in plan.get("segments") or []:
        if s["type"] == "image":
            reqs.append((s["src"], "shot", s.get("_prompt", ""), s.get("_chars") or []))
            wanted_cast.update(s.get("_chars") or [])
        elif s["type"] == "battle":
            reqs.append((s["terrain"], "terrain", s.get("_prompt", ""), []))
        elif s["type"] == "archive":
            reqs.append((s["image"], "archive", s.get("_prompt", ""), [], {"search": s.get("_search", ""),
                                                                          "title": s.get("title", ""), "note": s.get("note", "")}))
        for side in (s, s.get("left") or {}, s.get("right") or {}):
            if side.get("_cast"):
                wanted_cast.add(side["_cast"])
    by = {(c.get("name") or "").lower(): c for c in cast}
    portraits = []
    for name in sorted(wanted_cast):
        c = by.get((name or "").lower(), {"name": name, "look": ""})
        portraits.append((f"images/cast_{HA.slug(name)}.jpg", "portrait", c.get("look", ""), [c.get("name") or name]))
    return portraits, reqs


def _missing_assets(pr):
    portraits, reqs = _asset_requests(pr)
    d = media_dir(pr["id"])
    return [r for r in portraits + reqs if not os.path.isfile(os.path.join(d, r[0]))]


def _era(pr):
    """Ancre d'époque à mettre en tête de chaque image (calculée une fois, gardée dans le projet)."""
    per = pr.get("period") or {}
    if not per.get("period"):
        return ""
    return (f"Setting: {per['period']} Every uniform, weapon, flag, garment, building and vehicle belongs to this "
            f"exact time and place; nothing from other eras ({per.get('avoid', '')}).")


REALISM = ("Documentary realism: everything at its true real-world size, real physics, the real architecture and "
           "landscape of this place; nothing oversized, surreal or symbolic.")


def _gen(pr, rel, kind, prompt, chars, info=None):
    d = media_dir(pr["id"])
    cast = (pr.get("plan") or {}).get("cast") or []
    style = HA.image_style((pr.get("options") or {}).get("image_style"))
    chars = (chars or [])[:1]  # un seul personnage de référence par plan : fini les duos répétés
    look = HA.cast_look(cast, chars)
    era = _era(pr)
    if kind == "portrait":
        full = (f"{style['portrait']} {chars[0] if chars else ''}: {prompt} {era} Facing the viewer, eyes toward the "
                f"camera, not in profile.").strip()
        blob = ai.generate_image(full, width=1024, height=1536, quality="high")
        w, h = 900, 1200
    elif kind == "terrain":
        blob = ai.generate_image(f"{HA.TERRAIN} {prompt}")
        w, h = 1920, 1080
    elif kind == "archive":
        real = SRC.find_real_image(info or {"title": prompt}, HA.pick_archive)
        if real:  # vraie image de musée : on la garde entière (pas de recadrage), avec son crédit
            blob, credit = real
            _save_contained(blob, os.path.join(d, rel))
            _set_archive_credit(pr["id"], rel, credit)
            return
        blob = ai.generate_image(f"{HA.ARCHIVE} {prompt} {era}")
        _set_archive_credit(pr["id"], rel, "Reconstruction (AI)")
        w, h = 1920, 1080
    else:
        refs = [os.path.join(d, f"images/cast_{HA.slug(n)}.jpg") for n in chars]
        refs = [r for r in refs if os.path.isfile(r)]
        avoid = ""
        dest = os.path.join(d, rel)
        for attempt in range(2):  # contrôle en vision (époque, bras en trop, texte) : refaite une fois si ratée
            text = f"{era} {prompt}. {('Character: ' + look) if look else ''} {REALISM} {style['shot']}{avoid}".strip()
            if refs:
                text += " Keep this character's face, hair and outfit identical to the reference portrait, drawn in the same style."
            try:
                blob = ai.generate_image(text, refs=refs or None, quality="high")
            except ai.AIError as e:  # refus du filtre de sécurité (blessés, chirurgie…) : suggérer au lieu de montrer
                if not any(m in str(e).lower() for m in ("safety", "moderation", "policy", "rejected", "violat")):
                    raise
                prompt = ai.chat("Rewrite this image prompt for a history documentary so it passes strict image-safety "
                                 "filters while keeping the same moment, place and composition: imply the violence or "
                                 "the wounds (covered stretchers, tools, faces, aftermath from afar) instead of showing "
                                 "them; no blood, no gore, no bodies in close-up. Output only the prompt.\n\n" + prompt,
                                 model=ai.fast_model())
                text = f"{era} {prompt}. {('Character: ' + look) if look else ''} {REALISM} {style['shot']}{avoid}".strip()
                blob = ai.generate_image(text, refs=refs or None, quality="high")
            _fit_cover(blob, 1920, 1080, dest, anchor_y=0.22)
            if attempt or not era:
                break
            try:
                ok, problems = HA.check_shot(dest, pr.get("period"), prompt)
            except Exception:  # noqa: BLE001 — contrôle indisponible : on garde l'image
                break
            if ok:
                break
            print(f"[qa] {rel} : {'; '.join(problems)[:200]}", flush=True)
            avoid = " AVOID these mistakes of a previous attempt: " + "; ".join(problems) + "."
        _grade(dest)
        return
    dest = os.path.join(d, rel)
    _fit_cover(blob, w, h, dest, anchor_y=0.22 if kind == "portrait" else 0.5)
    if kind == "portrait":
        _grade(dest)


def _balance_gaze(job, pid):
    """Les plans copient le regard du portrait de référence : tout le monde finit par regarder du même côté.
    On mesure le sens du regard de chaque plan (vision, gardé dans `_facing`) et on retourne en miroir celui qui
    regarde du même côté que le plan à personnage précédent : les regards alternent. Les vraies archives et les
    animations ne sont jamais retournées."""
    from PIL import Image, ImageOps
    pr = get_project(pid)
    d = media_dir(pid)
    shots = [s for s in pr["plan"]["segments"] if s["type"] == "image" and s.get("src")]
    todo = [s for s in shots if not s.get("_facing")]
    if todo:
        job.update(0.99, f"Sens des regards : {len(todo)} plan(s)…")
        with ThreadPoolExecutor(max_workers=8) as ex:
            found = dict(zip([s["src"] for s in todo], ex.map(
                lambda s: _safe(lambda: HA.shot_facing(os.path.join(d, s["src"])), "none"), todo)))
    else:
        found = {}
    last, flips = None, []
    for s in shots:
        f = s.get("_facing") or found.get(s["src"], "none")
        if f in ("left", "right"):
            if f == last and not s.get("_flipped"):
                flips.append(s["src"])
                f = "left" if f == "right" else "right"
            last = f
        found[s["src"]] = f
    for src in flips:
        path = os.path.join(d, src)
        ImageOps.mirror(Image.open(path)).save(path, quality=92)

    def save(x):
        for s in x["plan"]["segments"]:
            if s.get("src") in found:
                s["_facing"] = found[s["src"]]
            if s.get("src") in flips:
                s["_flipped"] = True
    update_project(pid, save)
    return len(flips)


def _safe(fn, default):
    try:
        return fn()
    except Exception:  # noqa: BLE001 — contrôle indisponible : on laisse le plan tel quel
        return default


def _fit_cover(blob, width, height, dest, anchor_y=0.5):
    """Recadre au format exact (cover). anchor_y < 0.5 rogne surtout le bas : les têtes restent dans le cadre."""
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    sw, sh = im.size
    scale = max(width / sw, height / sh)
    nw, nh = max(width, round(sw * scale)), max(height, round(sh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - width) // 2, int((nh - height) * max(0.0, min(1.0, anchor_y)))
    im = im.crop((left, top, left + width, top + height))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, "JPEG", quality=92, optimize=True)


def _save_contained(blob, dest, max_side=1800):
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((max_side, max_side))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, "JPEG", quality=92)


def _set_archive_credit(pid, rel, credit):
    def upd(x):
        for s in (x.get("plan") or {}).get("segments") or []:
            if s.get("type") == "archive" and s.get("image") == rel:
                s["credit"] = credit
    update_project(pid, upd)


def _grade(path):
    """Étalonnage commun à tous les plans : couleurs un peu éteintes, contraste doux (look photo de tournage)."""
    try:
        from PIL import Image, ImageEnhance
        im = Image.open(path).convert("RGB")
        im = ImageEnhance.Color(im).enhance(0.95)
        im.save(path, quality=92)
    except Exception:  # noqa: BLE001 — l'image brute reste utilisable
        pass


def job_images(job, pid):
    pr = get_project(pid)
    os.makedirs(os.path.join(media_dir(pid), "images"), exist_ok=True)
    if not (pr.get("period") or {}).get("period"):
        job.update(0.01, "Époque exacte pour les images…")
        per = HA.period_brief(pr["title"], HA.narration(pr["script"]))
        update_project(pid, lambda x: x.__setitem__("period", per))
        pr = get_project(pid)
    portraits, reqs = _asset_requests(pr)
    d = media_dir(pid)
    todo_p = [r for r in portraits if not os.path.isfile(os.path.join(d, r[0]))]
    todo = [r for r in reqs if not os.path.isfile(os.path.join(d, r[0]))]
    total = len(todo_p) + len(todo)
    if not total:
        _balance_gaze(job, pid)
        job.update(1.0, "Toutes les images sont prêtes.")
        return
    workers = max(1, int(os.getenv("AI_IMAGE_CONCURRENCY") or 6))
    done = 0
    errors = []

    def run(batch, label):
        nonlocal done
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_gen, pr, *r): r for r in batch}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except ai.AIError as e:
                    if getattr(e, "status", 0) == 4290:  # quota : on garde ce qui est fait, reprise plus tard
                        for f in futs:
                            f.cancel()
                        raise
                    errors.append(f"{futs[fut][0]} : {e}")
                done += 1
                job.update(0.02 + 0.96 * done / total, f"{label} {done}/{total}")
    # portraits d'abord : ils servent de référence pour garder les mêmes visages
    run(todo_p, "Portraits du casting")
    run(todo, "Images")
    if errors:
        raise RuntimeError(f"{len(errors)} image(s) en échec (relance pour les refaire) : {errors[0][:200]}")
    flipped = _balance_gaze(job, pid)
    job.update(1.0, f"{total} image(s) générée(s), {flipped} retournée(s) pour varier les regards.")


# ── 5. Rendu ────────────────────────────────────────────────────────────────

def captions_from_words(words, max_words=5, max_chars=28):
    out, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x["w"] for x in cur)
        if len(cur) >= max_words or len(text) >= max_chars or re.search(r"[.!?,;:]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    caps = []
    for i, c in enumerate(out):
        end = out[i + 1][0]["s"] if i + 1 < len(out) else c[-1]["e"] + 0.4
        caps.append({"text": " ".join(x["w"] for x in c), "start": round(c[0]["s"], 3),
                     "end": round(min(end, c[-1]["e"] + 0.6), 3)})
    return caps


def _public(seg):
    """Segment sans les champs internes (_prompt, _cast…)."""
    out = {k: v for k, v in seg.items() if not k.startswith("_")}
    for side in ("left", "right"):
        if isinstance(out.get(side), dict):
            out[side] = {k: v for k, v in out[side].items() if not k.startswith("_")}
    return out


def build_timeline(pr):
    pid = pr["id"]
    d = media_dir(pid)
    words = load_words(pid)
    opts = pr.get("options") or DEFAULTS
    duration = pr["voice"]["duration"] + TAIL
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    bed = os.path.join(d, "audio", "music.mp3")
    if not os.path.isfile(bed) or media.duration(bed) < duration - 0.5:
        HAU.music_bed(bed, duration + 2)
    sfx = HAU.ensure_sfx(os.path.join(d, "audio", "sfx"))
    rel = lambda p: os.path.relpath(p, d).replace("\\", "/")  # noqa: E731
    cues = []
    for s in pr["plan"]["segments"]:
        if s["type"] in ("statement", "number"):
            cues.append({"src": rel(sfx["boom"]), "at": round(s["start"] + s.get("reveal", 0), 3), "volume": 0.55})
        elif s["type"] in ("battle", "map", "character", "compare", "chart", "archive", "route", "quote"):
            cues.append({"src": rel(sfx["whoosh"]), "at": s["start"], "volume": 0.3})
            if s["type"] == "map":
                dur = s["end"] - s["start"]
                for mv in s.get("moves") or []:
                    cues.append({"src": rel(sfx["whoosh"]), "at": round(s["start"] + mv["start"] * dur, 3), "volume": 0.25})
                if s.get("battle"):
                    cues.append({"src": rel(sfx["boom"]), "at": round(s["start"] + s["battle"]["at"] * dur, 3), "volume": 0.5})
            if s["type"] == "battle":
                dur = s["end"] - s["start"]
                for u in s.get("units") or []:
                    if u.get("to"):
                        cues.append({"src": rel(sfx["tick"]), "at": round(s["start"] + (u.get("move") or [0.25])[0] * dur, 3),
                                     "volume": 0.45})
    hook_end = pr["voice"].get("hook_end") or 0
    return {
        "duration": round(duration, 3), "fps": 30, "width": 1920, "height": 1080,
        "voice": pr["voice"]["file"], "music": "audio/music.mp3",
        "musicVolume": float(opts.get("music_volume", DEFAULTS["music_volume"])),
        "sfx": cues, "film": float(opts.get("film", 1.0)),
        "captions": captions_from_words(words) if opts.get("captions", True) else [],
        "captionsFrom": hook_end if opts.get("captions_after_hook", True) else 0,
        "captionsMute": [[s["start"], s["end"]] for s in pr["plan"]["segments"] if s["type"] == "quote"],
        "captionsBand": [[s["start"], s["end"]] for s in pr["plan"]["segments"] if s["type"] in ("image", "video")],
        "theme": HA.image_style(opts.get("image_style")).get("theme", "cinematic"),
        "segments": _with_tail([_public(s) for s in pr["plan"]["segments"]], duration),
    }


def _with_tail(segs, duration):
    """La dernière carte / image tient jusqu'au bout (marge après la voix)."""
    if segs:
        segs[-1]["end"] = round(max(segs[-1]["end"], duration), 3)
    return segs


def engine_ready():
    """(ok, message) : Node + dépendances du moteur Remotion."""
    node = shutil.which("node")
    if not node:
        return False, "Node.js introuvable : installe Node 18+ (nodejs.org) pour le rendu Remotion."
    if not os.path.isdir(os.path.join(ENGINE_DIR, "node_modules", "remotion")):
        npm = shutil.which("npm")
        if not npm:
            return False, "npm introuvable (fourni avec Node.js)."
        r = subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=ENGINE_DIR, capture_output=True, text=True)
        if r.returncode != 0:
            return False, "npm install a échoué : " + (r.stderr or r.stdout)[-400:]
    return True, node


def _remotion(job, project_media, out_path, p0, p1, extra=()):
    ok, node = engine_ready()
    if not ok:
        raise RuntimeError(node)
    cmd = [node, os.path.join(ENGINE_DIR, "render.mjs"), "--project", project_media] + (
        ["--out", out_path] if out_path else []) + list(extra)
    conc = os.getenv("REMOTION_CONCURRENCY")
    if conc:
        cmd += ["--concurrency", conc]
    proc = subprocess.Popen(cmd, cwd=ENGINE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace")
    tail = []
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("stage") == "bundle":
                job.update(p0, "Préparation du moteur d'animation…")
            elif ev.get("stage") == "render":
                part = f" (morceau {ev['chunk']}/{ev['chunks']})" if ev.get("chunks") else ""
                job.update(p0 + (p1 - p0) * float(ev.get("progress") or 0),
                           f"Rendu {ev.get('renderedFrames', 0)}/{ev.get('total', '?')} images{part}")
            elif ev.get("stage") == "audio":
                job.update(p1, "Rendu du son…")
            if job.cancelled():
                proc.kill()
                raise store.JobCancelled("Annulé.")
        tail = (proc.stderr.read() or "").strip().splitlines()[-6:]
    finally:
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Rendu Remotion en échec :\n" + "\n".join(tail))


CHUNK_FRAMES = 900  # 30 s par morceau : un redémarrage de la machine ne perd que quelques minutes de rendu


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def job_render(job, pid):
    pr = get_project(pid)
    missing = _missing_assets(pr)
    if missing:
        raise RuntimeError(f"{len(missing)} image(s) manquante(s) : lance d'abord les images.")
    d = media_dir(pid)
    # rendu par morceaux (render.mjs --chunk-dir) : après un redémarrage, on reprend au morceau suivant. Les
    # morceaux ne servent que pour la même timeline (même plan, même voix, mêmes options).
    chunks = os.path.join(project_dir(pid), "chunks")
    sig = hashlib.sha1(json.dumps([pr.get("plan"), pr.get("voice"), pr.get("options")], sort_keys=True,
                                  default=str).encode("utf-8")).hexdigest()
    saved = os.path.join(chunks, "timeline.json")
    if _read(os.path.join(chunks, "sig.txt")) == sig and os.path.isfile(saved):
        job.update(0.02, "Reprise du rendu…")
        with open(saved, encoding="utf-8") as f:
            tl = json.load(f)
    else:
        shutil.rmtree(chunks, ignore_errors=True)
        job.update(0.02, "Musique, bruitages et sous-titres…")
        tl = build_timeline(pr)
        os.makedirs(chunks)
        with open(saved, "w", encoding="utf-8") as f:
            json.dump(tl, f, ensure_ascii=False)
        with open(os.path.join(chunks, "sig.txt"), "w") as f:
            f.write(sig)
        with open(os.path.join(chunks, "frames.txt"), "w") as f:
            f.write(str(CHUNK_FRAMES))
    with open(os.path.join(d, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False)
    size = _read(os.path.join(chunks, "frames.txt")) or "2700"  # un rendu commencé garde sa taille de morceau
    # rendu local (gratuit, du dernier morceau au premier) ET, si RUNPOD_API_KEY, une machine RunPod en même temps
    # (du premier au dernier) : ils se rejoignent au milieu ; la machine est supprimée dès que tout est rendu
    done = threading.Event()
    helper = None
    if RR.available():
        def remote():
            try:
                RR.render(job, d, chunks, int(size), math.ceil(tl["duration"] * tl["fps"]), 0.05, 0.94,
                          stop=done.is_set)
            except Exception as e:  # noqa: BLE001 — sans RunPod, le rendu local fait tout
                print(f"[runpod] {e}", flush=True)
        helper = threading.Thread(target=remote, daemon=True)
        helper.start()
    for f in os.listdir(chunks):  # marques d'un rendu interrompu
        if f.startswith("claim_"):
            os.remove(os.path.join(chunks, f))
    try:
        if helper:  # 1er passage : le local laisse à RunPod les morceaux qu'il a pris, puis attend qu'il ait fini
            _remotion(job, d, None, 0.05, 0.94, ["--chunk-dir", chunks, "--chunk-frames", size, "--reverse",
                                                 "--skip-claimed", "--no-audio"])
            helper.join(timeout=1800)
    finally:
        done.set()
        if helper:
            helper.join(timeout=300)
    # ce qui manque encore (machine RunPod perdue…) + le son
    _remotion(job, d, None, 0.05, 0.94, ["--chunk-dir", chunks, "--chunk-frames", size, "--reverse"])
    job.update(0.95, "Assemblage et mixage final (-14 LUFS)…")
    parts = sorted(f for f in os.listdir(chunks) if re.fullmatch(r"part_\d{3}\.mp4", f))
    with open(os.path.join(chunks, "parts.txt"), "w", encoding="utf-8") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    name = f"{HA.slug(pr['title'], 60)}_{int(time.time()) % 1000000}.mp4"
    media.run(["-f", "concat", "-safe", "0", "-i", os.path.join(chunks, "parts.txt"), "-i", os.path.join(chunks, "audio.wav"),
               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac",
               "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", os.path.join(project_dir(pid), name)])
    shutil.rmtree(chunks, ignore_errors=True)
    old = (pr.get("render") or {}).get("file")

    def save(x):
        x["render"] = {"file": name, "duration": tl["duration"], "at": store.now()}
    update_project(pid, save)
    if old and old != name:
        try:
            os.remove(os.path.join(project_dir(pid), old))
        except OSError:
            pass
    job.update(1.0, "Vidéo prête ✔")


class _Sub:
    """Sous-progression d'une étape dans la barre globale."""

    def __init__(self, job, a, b, label):
        self.job, self.a, self.b, self.label = job, a, b, label

    def update(self, p=None, msg=None):
        self.job.update(None if p is None else self.a + (self.b - self.a) * p, f"[{self.label}] {msg}" if msg else None)

    def cancelled(self):
        return self.job.cancelled()


THUMB_LOOK = ("YouTube thumbnail painting in the style of the top history documentary channels: one dramatic scene, "
              "vivid saturated colours, strong contrast, fire glow, drifting smoke and a dramatic sky; {subject}; the "
              "action of the story behind. Keep the {corner} corner of the frame calmer (sky or smoke) for a title "
              "added later. Era-accurate. No text, no letters.")
CAMEO_LOOK = ("Head-and-shoulders portrait of {who}, as an authentic period portrait from that era (a 19th-century "
              "engraving or black-and-white photograph for modern times; an engraved portrait or marble bust for "
              "antiquity), facing the viewer, plain light background, nothing else. No text.")


def thumb_concepts(pr, n=3):
    """n idées de miniature façon Dose of History : scène, personnage face caméra, 2-4 mots (mot fort en rouge),
    médaillon facultatif d'un acteur clé. Les guillemets sont réservés aux vrais mots du témoin."""
    script = HA.narration(pr["script"])[:9000]
    data = ai.chat_json(
        f'Design {n} different YouTube thumbnails for the history documentary "{pr["title"]}". Study of the most '
        'viewed thumbnails of the niche (Dose of History): one dramatic painted scene, a person big in the '
        'foreground looking straight at the viewer, fire, smoke, flags; ONE short line of text of 2-4 words in '
        'white with the strongest word in red (e.g. BRUTAL FATE, CHILLING DISCOVERY, "I SAW CUSTER DIE"); '
        'sometimes a black-and-white period portrait of a key person in an oval cameo.\n'
        'Rules for the text: an emotional hook, never a description or a detail of the plot. Best: 2-3 words. '
        'Patterns that work: BRUTAL FATE, CHILLING DISCOVERY, WORSE THAN DEATH, SHE SAW EVERYTHING, 28 VS 700, '
        'NO ONE SURVIVED, HIDDEN TRUTH; one strong word in red (BRUTAL, CHILLING, HORRIFYING, TRUTH, EVERYTHING, a '
        'number). It adds to the title without repeating it. Put it in quotes ONLY when it is the witness\'s real '
        'words from the script, copied exactly and very short (2-4 words); never invent a quote. All 3 texts differ.\n'
        'Rules for the image: a true moment of the story, era-accurate, no gore in close-up; the person in the '
        'foreground is the witness or the hero of the story. The cameo, used in at most 2 of the 3, is the MOST '
        'famous real person of the story (the leader, the enemy commander, the famous name in the title), never a '
        'minor figure.\n'
        'Return JSON only: {"concepts": [{"text": "2-4 WORDS", "red": ["WORD"], "quotes": false, '
        '"corner": "top-left|top-right|bottom-left|bottom-right", "subject": "who stands big in the foreground '
        '(age, look, clothes, expression) and on which side", "scene": "one sentence: the moment and the place behind", '
        '"cameo": "real person + look, or empty"}]}\n\nSCRIPT (excerpt):\n' + script,
        model=ai.text_model(), timeout=240)
    out = []
    for c in (data.get("concepts") or [])[:n]:
        if isinstance(c, dict) and c.get("text") and c.get("scene"):
            corner = c.get("corner") if c.get("corner") in ("top-left", "top-right", "bottom-left", "bottom-right") \
                else "top-right"
            out.append({"text": str(c["text"]).strip().strip('"“”'), "red": [str(x) for x in c.get("red") or []][:2],
                        "quotes": bool(c.get("quotes")), "corner": corner, "subject": str(c.get("subject") or ""),
                        "scene": str(c["scene"]), "cameo": str(c.get("cameo") or "").strip()})
    if not out:
        raise ai.AIError("Miniature : aucune idée.")
    return out


def job_thumbnail(job, pid, n=3):
    """Miniatures (n variantes au choix) : peinture saturée + personnage face caméra + 2-4 mots posés par le code
    (blanc, mot fort en rouge) + médaillon noir et blanc facultatif. La 1re est la miniature par défaut."""
    pr = get_project(pid)
    style = HA.image_style((pr.get("options") or {}).get("image_style"))
    if not pr.get("period") and pr.get("script"):
        per = HA.period_brief(pr["title"], HA.narration(pr["script"]))
        update_project(pid, lambda x: x.__setitem__("period", per))
        pr = get_project(pid)
    era = _era(pr)
    job.update(0.05, "Miniatures : idées…")
    concepts = (pr.get("thumb") or {}).get("concepts") or thumb_concepts(pr, n)
    update_project(pid, lambda x: x.__setitem__("thumb", {"concepts": concepts}))
    d = project_dir(pid)

    def make(k_c):
        k, c = k_c
        corner = c["corner"].replace("-", " ")
        blob = ai.generate_image(f"{era} {c['scene']} {THUMB_LOOK.format(subject=c['subject'], corner=corner)} "
                                 f"{style['shot']}", width=1920, height=1080, quality="high")
        base = os.path.join(d, f"thumbnail_base_{k}.jpg")
        ai.fit_cover(blob, 1280, 720, base)
        cameo = None
        if c.get("cameo"):
            try:
                cameo = os.path.join(d, f"thumbnail_cameo_{k}.jpg")
                ai.fit_cover(ai.generate_image(CAMEO_LOOK.format(who=c["cameo"]), width=1024, height=1536,
                                               quality="high"), 768, 1024, cameo)
            except Exception as e:  # noqa: BLE001 — sans médaillon, la miniature reste bonne
                print(f"[thumbnail] médaillon : {e}", flush=True)
                cameo = None
        side = "left" if c["corner"].endswith("left") else "right"
        rel = f"thumbnail_{k}.jpg"
        TH.compose_doh(base, c["text"], c["red"], c["corner"], cameo=cameo, cameo_side=side, quotes=c["quotes"],
                       dest=os.path.join(d, rel))
        return rel

    made = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, fut in enumerate([ex.submit(make, (k + 1, c)) for k, c in enumerate(concepts)]):
            try:
                made.append(fut.result())
            except Exception as e:  # noqa: BLE001
                print(f"[thumbnail] variante {i + 1} : {e}", flush=True)
            job.update(0.1 + 0.9 * (i + 1) / len(concepts), f"Miniatures {len(made)}/{len(concepts)}")
    if not made:
        raise ai.AIError("Miniatures : aucune image.")

    def save(x):
        x["thumbnail"], x["thumb_options"] = made[0], made
    update_project(pid, save)
    job.update(1.0, f"{len(made)} miniature(s) prête(s).")


def job_autopilot(job, pid):
    steps = [("script", job_script, 0.0, 0.12, "1/5 Script"), ("voice", job_voice, 0.12, 0.22, "2/5 Voix"),
             ("plan", job_plan, 0.22, 0.3, "3/5 Plan visuel"), ("images", job_images, 0.3, 0.7, "4/5 Images"),
             ("render", job_render, 0.7, 1.0, "5/5 Montage")]
    for key, fn, a, b, label in steps:
        pr = get_project(pid)
        cur = stage(pr)
        if cur == "done":
            break
        if STAGES.index(key) < STAGES.index(cur):
            continue
        fn(_Sub(job, a, b, label), pid)
    if not get_project(pid).get("thumbnail"):
        try:
            job_thumbnail(_Sub(job, 0.99, 1.0, "Miniature"), pid)
        except Exception as e:  # noqa: BLE001 — la vidéo est faite : une miniature ratée se refait à part
            print(f"[thumbnail] {e}", flush=True)
    job.update(1.0, "Vidéo terminée ✔")


JOBS = {"script": job_script, "voice": job_voice, "plan": job_plan, "images": job_images, "render": job_render,
        "thumbnail": job_thumbnail, "autopilot": job_autopilot}


def invalidate_from(pid, step):
    """Refaire une étape efface les suivantes (le rendu dépend du plan, le plan de la voix…)."""
    def upd(x):
        if step in ("script",):
            x["script"] = None
        if step in ("script", "voice"):
            x["voice"] = None
        if step in ("script", "voice", "plan"):
            x["plan"] = None
        x["render"] = None
    update_project(pid, upd)


