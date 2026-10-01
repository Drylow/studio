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
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import ai, media, tts
from services import history_ai as HA
from services import history_audio as HAU
from services import pov_store as store

APP_DIR = store.APP_DIR
ENGINE_DIR = os.path.join(APP_DIR, "history_engine")

DEFAULT_VOICE = {"provider": "algrow", "voice": "lfBVYbXnblkOddWFfEIg", "speed": 1.0}  # « Timothy – American Narrator »
EDGE_VOICE = "en-US-GuyNeural"
DEFAULTS = {"minutes": 3.0, "language": "en", "captions": True, "captions_after_hook": True, "film": 1.0,
            "music_volume": 0.16, "all_templates": False,
            # animations actives par défaut (bataille, graphique, comparaison, itinéraire : dispo mais coupés)
            "templates": ["statement", "quote", "character", "archive"],
            "cards_per_min": 1.5}
STAGES = ("script", "voice", "plan", "images", "render")


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
            "render": pr.get("render"), "job": job.as_dict() if job else None}


# ── 1. Script ───────────────────────────────────────────────────────────────

def job_script(job, pid):
    pr = get_project(pid)
    job.update(0.05, "Écriture du script (style documentaire)…")
    sc = HA.write_script(pr["title"], pr["minutes"], pr.get("notes", ""), pr["options"].get("language", "en"))

    def save(x):
        x["script"] = sc
        x["voice"] = x["plan"] = x["render"] = None
    update_project(pid, save)
    job.update(1.0, f"Script prêt : {len(HA.narration(sc).split())} mots.")


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
    provider = vs.get("provider", "algrow")
    voice = vs.get("voice") or (EDGE_VOICE if provider == "edge" else "")
    job.update(0.05, f"Voix off ({provider})…")
    res = tts.synthesize(text, dest, provider=provider, voice=voice, speed=vs.get("speed", 1.0),
                         progress=lambda i, n: job.update(0.05 + 0.85 * i / max(1, n), f"Voix off {min(i + 1, n)}/{n}…"))
    words = script_timed_words(text, res["words"])
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
    end_total = duration + 0.8
    starts = [0.0 if i == 0 else sentences[b["at"]]["start"] for i, b in enumerate(clean)]
    segs = []
    cast = plan.get("cast") or []
    portrait = lambda name: f"images/cast_{HA.slug(name)}.jpg" if name else None  # noqa: E731
    n_img = 0
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
            seg.update(type="image", src=f"images/shot_{n_img:03d}.jpg",
                       motion=b.get("motion") or ("in" if n_img % 2 == 0 else "out"),
                       strength=0.14 if in_hook else 0.07,
                       _prompt=b.get("prompt") or "", _chars=b.get("chars") or [])
            n_img += 1
        elif t == "statement":
            seg["text"] = (b.get("text") or "").upper()
            at = _find_phrase(words, b.get("say") or b.get("text", "").replace("*", ""), start, end)
            seg["reveal"] = round(max(0.0, (at or start) - start), 3)
        elif t == "battle":
            seg.update(title=b.get("title", ""), subtitle=b.get("subtitle", ""), terrain=f"images/terrain_{i:03d}.jpg",
                       _prompt=b.get("terrain_prompt") or "dry open plain with a river", labels=b.get("labels") or [],
                       units=[{k: u[k] for k in ("label", "side", "kind", "x", "y", "to", "move", "w", "h", "trail") if k in u}
                              for u in b.get("units") or [] if "x" in u and "y" in u])
            if isinstance(b.get("line"), dict):
                seg["line"] = b["line"]
        elif t == "character":
            seg.update(name=b.get("name", ""), role=b.get("role", ""), facts=b.get("facts") or [],
                       image=portrait(b.get("portrait") or b.get("name")), _cast=b.get("portrait") or b.get("name"))
        elif t == "compare":
            for side in ("left", "right"):
                s = b.get(side)
                if isinstance(s, dict):
                    seg[side] = {"title": s.get("title", ""), "stats": s.get("stats") or []}
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
                       _prompt=b.get("prompt") or b.get("title", ""))
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
        segs.append(seg)
    _ensure_card_time(segs)
    return segs, cast


# durée minimale lisible de chaque carte (s) ; une citation dure au moins jusqu'à son dernier mot + 3 s
CARD_MIN = {"statement": 4.0, "character": 7.0, "compare": 9.0, "chart": 8.0, "archive": 6.5, "route": 9.0,
            "battle": 11.0, "quote": 7.0}


def _ensure_card_time(segs):
    """Allonge les cartes trop courtes en prenant le temps sur l'image voisine (après, sinon avant)."""
    for i, s in enumerate(segs):
        if s["type"] not in CARD_MIN:
            continue
        want = CARD_MIN[s["type"]]
        if s["type"] == "quote" and s.get("words"):
            want = max(want, s["words"][-1] + 3.0)
        need = want - (s["end"] - s["start"])
        if need <= 0:
            continue
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        if nxt and nxt["type"] == "image":
            take = min(need, max(0.0, (nxt["end"] - nxt["start"]) - 3.0))
            nxt["start"] = round(nxt["start"] + take, 3)
            s["end"] = round(s["end"] + take, 3)
            need -= take
        prv = segs[i - 1] if i > 0 else None
        if need > 0 and prv and prv["type"] == "image":
            take = min(need, max(0.0, (prv["end"] - prv["start"]) - 3.0))
            prv["end"] = round(prv["end"] - take, 3)
            s["start"] = round(s["start"] - take, 3)
            if s["type"] == "statement":
                s["reveal"] = round(s.get("reveal", 0) + take, 3)
            if s.get("words"):
                s["words"] = [round(t + take, 3) for t in s["words"]]


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
    plan = HA.plan_visuals([{"text": s["text"], "start": s["start"], "end": s["end"]} for s in sents], duration, hook_idx,
                           allowed=allowed, max_cards=max_cards, require_all=opts.get("all_templates", False))
    segs, cast = build_segments(plan, sents, words, duration, hook_end, allowed=allowed, max_cards=max_cards)

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
            reqs.append((s["image"], "archive", s.get("_prompt", ""), []))
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


def _gen(pr, rel, kind, prompt, chars):
    d = media_dir(pr["id"])
    cast = (pr.get("plan") or {}).get("cast") or []
    look = HA.cast_look(cast, chars)
    if kind == "portrait":
        full = f"{HA.PORTRAIT} {chars[0] if chars else ''}: {prompt}".strip()
        blob = ai.generate_image(full, width=1024, height=1536)
        w, h = 900, 1200
    elif kind == "terrain":
        blob = ai.generate_image(f"{HA.TERRAIN} {prompt}")
        w, h = 1920, 1080
    elif kind == "archive":
        blob = ai.generate_image(f"{HA.ARCHIVE} {prompt}")
        w, h = 1920, 1080
    else:
        refs = [os.path.join(d, f"images/cast_{HA.slug(n)}.jpg") for n in chars]
        refs = [r for r in refs if os.path.isfile(r)]
        text = f"{prompt}. {('Characters: ' + look) if look else ''} {HA.STYLE}"
        if refs:
            text += " Keep each character's face, hair and outfit identical to the reference portraits."
        blob = ai.generate_image(text, refs=refs or None)
        w, h = 1920, 1080
    dest = os.path.join(d, rel)
    ai.fit_cover(blob, w, h, dest, anchor_y=0.22 if kind in ("shot", "portrait") else 0.5)
    if kind in ("shot", "portrait"):
        _grade(dest)


def _grade(path):
    """Étalonnage commun à tous les plans : couleurs un peu éteintes, contraste doux (look photo de tournage)."""
    try:
        from PIL import Image, ImageEnhance
        im = Image.open(path).convert("RGB")
        im = ImageEnhance.Color(im).enhance(0.88)
        im = ImageEnhance.Contrast(im).enhance(0.96)
        im.save(path, quality=92)
    except Exception:  # noqa: BLE001 — l'image brute reste utilisable
        pass


def job_images(job, pid):
    pr = get_project(pid)
    os.makedirs(os.path.join(media_dir(pid), "images"), exist_ok=True)
    portraits, reqs = _asset_requests(pr)
    d = media_dir(pid)
    todo_p = [r for r in portraits if not os.path.isfile(os.path.join(d, r[0]))]
    todo = [r for r in reqs if not os.path.isfile(os.path.join(d, r[0]))]
    total = len(todo_p) + len(todo)
    if not total:
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
    job.update(1.0, f"{total} image(s) générée(s).")


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
    duration = pr["voice"]["duration"] + 0.8
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    bed = os.path.join(d, "audio", "music.mp3")
    if not os.path.isfile(bed) or media.duration(bed) < duration - 0.5:
        HAU.music_bed(bed, duration + 2)
    sfx = HAU.ensure_sfx(os.path.join(d, "audio", "sfx"))
    rel = lambda p: os.path.relpath(p, d).replace("\\", "/")  # noqa: E731
    cues = []
    for s in pr["plan"]["segments"]:
        if s["type"] == "statement":
            cues.append({"src": rel(sfx["boom"]), "at": round(s["start"] + s.get("reveal", 0), 3), "volume": 0.55})
        elif s["type"] in ("battle", "character", "compare", "chart", "archive", "route", "quote"):
            cues.append({"src": rel(sfx["whoosh"]), "at": s["start"], "volume": 0.3})
            if s["type"] == "battle":
                dur = s["end"] - s["start"]
                for u in s.get("units") or []:
                    if u.get("to"):
                        cues.append({"src": rel(sfx["tick"]), "at": round(s["start"] + (u.get("move") or [0.25])[0] * dur, 3),
                                     "volume": 0.45})
    hook_end = pr["voice"].get("hook_end") or 0
    return {
        "duration": round(duration, 3), "fps": 30, "width": 1920, "height": 1080,
        "voice": pr["voice"]["file"], "music": "audio/music.mp3", "musicVolume": float(opts.get("music_volume", 0.16)),
        "sfx": cues, "film": float(opts.get("film", 1.0)),
        "captions": captions_from_words(words) if opts.get("captions", True) else [],
        "captionsFrom": hook_end if opts.get("captions_after_hook", True) else 0,
        "captionsMute": [[s["start"], s["end"]] for s in pr["plan"]["segments"] if s["type"] == "quote"],
        "segments": [_public(s) for s in pr["plan"]["segments"]],
    }


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


def _remotion(job, project_media, out_path, p0, p1):
    ok, node = engine_ready()
    if not ok:
        raise RuntimeError(node)
    cmd = [node, os.path.join(ENGINE_DIR, "render.mjs"), "--project", project_media, "--out", out_path]
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
                job.update(p0 + (p1 - p0) * float(ev.get("progress") or 0),
                           f"Rendu {ev.get('renderedFrames', 0)}/{ev.get('total', '?')} images")
            if job.cancelled():
                proc.kill()
                raise store.JobCancelled("Annulé.")
        tail = (proc.stderr.read() or "").strip().splitlines()[-6:]
    finally:
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Rendu Remotion en échec :\n" + "\n".join(tail))


def job_render(job, pid):
    pr = get_project(pid)
    missing = _missing_assets(pr)
    if missing:
        raise RuntimeError(f"{len(missing)} image(s) manquante(s) : lance d'abord les images.")
    job.update(0.02, "Musique, bruitages et sous-titres…")
    tl = build_timeline(pr)
    d = media_dir(pid)
    with open(os.path.join(d, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False)
    raw = os.path.join(project_dir(pid), "render_raw.mp4")
    _remotion(job, d, raw, 0.05, 0.94)
    job.update(0.95, "Mixage final (-14 LUFS)…")
    name = f"{HA.slug(pr['title'], 60)}_{int(time.time()) % 1000000}.mp4"
    media.run(["-i", raw, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", os.path.join(project_dir(pid), name)])
    os.remove(raw)
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
    job.update(1.0, "Vidéo terminée ✔")


JOBS = {"script": job_script, "voice": job_voice, "plan": job_plan, "images": job_images, "render": job_render,
        "autopilot": job_autopilot}


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


