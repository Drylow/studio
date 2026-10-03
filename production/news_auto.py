"""Actu sport 100 % automatique (l'utilisateur, 4 oct. : « que ça le fasse tout seul… c'est pas à moi de chercher
des sujets » ; vérification par l'IA choisie, sans Claude).

Tourne sur le PC de l'utilisateur, dans l'agent standalone/pc_agent (il a les clés dans secrets.json, reçues une
fois par `news.py pc-setup`, et lance `tick` chaque minute) :
  1. radar (toutes les 30 min par chaîne) : vidéos du jour des chaînes sources sans revendication (flux RSS, vues),
     titres des chaînes concurrentes (ce qui fait des vues), l'IA en tire les sujets chauds → Discord, avec un lien
     « Faire la vidéo » par sujet (ntfy.sh : le clic publie « go <id> » sur un sujet secret que l'agent écoute) ;
  2. GO (clic, ou Claude par le relais : `news_auto.py go <id>`) → sous-titres (yt-dlp) → moments → plan →
     relecture automatique (noms mal écrits, voix off fidèle aux extraits) → voix → miniature → montage → contrôle
     des planches par l'IA → paquet Discord (« ⚠️ à regarder » si le contrôle trouve un vrai problème).

  python production/news_auto.py radar [--sport mma_en] [--dry-run] [--force]
  python production/news_auto.py tick                 (agent du PC, chaque minute)
  python production/news_auto.py make <id_sujet>      (fait la vidéo d'un sujet proposé, sans attendre le clic)
  python production/news_auto.py go <id_sujet>        (cloud : envoie le GO au PC par le relais)
  python production/news_auto.py status               (cloud : sujets proposés et vidéos en cours, via le relais)
"""
import datetime
import glob
import json
import os
import random
import re
import shutil
import string
import sys
import time
import urllib.parse
import urllib.request

from common import WORK

import news
from services import ai
from services import newsvid as N

AUTO = os.path.join(WORK, "auto")
STATE = os.path.join(AUTO, "state.json")
RADAR_EVERY = 30 * 60          # secondes entre deux recherches de sujets pour une chaîne
HOURS = 36                     # fraîcheur des vidéos sources prises en compte
MIN_SCORE = 6                  # note de l'IA (vues attendues, 1-10) en dessous de laquelle on ne propose pas
MAX_PROPOSALS = 3              # sujets max par chaîne et par passage
NTFY = "https://ntfy.sh"
CTL = "auto-ctl"               # dossier du relais qui sert de boîte aux lettres cloud ↔ PC (GO, état)
COLORS = {"mma_en": 0x12A8E0, "boxing_en": 0xD4A017, "football_en": 0x1DB954}


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


# ── État (sujets proposés, dernières recherches, messages lus) ──────────────

def load_state():
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    for k, v in (("proposals", {}), ("radar", {}), ("considered", {}), ("ntfy_since", ""), ("ctl_done", [])):
        st.setdefault(k, v)
    return st


def save_state(st):
    os.makedirs(AUTO, exist_ok=True)
    now = time.time()
    st["considered"] = {k: t for k, t in st["considered"].items() if now - t < 4 * 86400}
    st["proposals"] = {k: p for k, p in st["proposals"].items() if now - p.get("t", now) < 10 * 86400}
    st["ctl_done"] = st["ctl_done"][-200:]
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(STATE + ".tmp", STATE)


def new_id():
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))


# ── Discord ─────────────────────────────────────────────────────────────────

def discord(content, embeds=None, dry=False):
    if dry:
        print("[Discord]", content)
        for e in embeds or []:
            print("  ", json.dumps(e, ensure_ascii=False)[:1500])
        return
    import requests
    from common import webhook
    r = requests.post(webhook() + "?wait=true", timeout=60,
                      json={"content": content[:1900], "embeds": embeds or [], "allowed_mentions": {"parse": []}})
    r.raise_for_status()


def go_link(pid):
    topic = os.environ.get("NEWS_AUTO_TOPIC") or ""
    return f"{NTFY}/{topic}/publish?message=" + urllib.parse.quote(f"go {pid}") if topic else ""


def _age(published):
    try:
        t = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "?"
    h = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600
    return f"{max(1, round(h * 60))} min" if h < 1 else f"{h:.0f} h"


def _views(n):
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{n / 1e3:.0f} k" if n >= 1e3 else str(n)


# ── 1. Radar : les sujets chauds ────────────────────────────────────────────

def rank(ch, vids, trend, recent):
    rows = "\n".join(f"[{i}] {_age(v['published'])} ago, {_views(v.get('views', 0))} views, {v['channel']}: {v['title']}"
                     for i, v in enumerate(vids))
    trows = "\n".join(f"- {_age(v['published'])} ago, {_views(v.get('views', 0))} views, {v['channel']}: {v['title']}"
                      for v in sorted(trend, key=lambda v: -v.get("views", 0))[:40]) or "-"
    done = "\n".join(f"- {p['story']} ({_age_ts(p['t'])} ago)" for p in recent) or "-"
    prompt = f"""You are the editor of "{ch['brand']}", a {ch['sport']} news YouTube channel in the style of Fight Night
MMA: several videos a day, each built from REAL interview clips of the day (podcasts, interviews, press
conferences) linked by a neutral narrator. Goal: pick the stories that will get the MOST VIEWS right now.

USABLE SOURCE VIDEOS (we may use their clips) — [index] age, views, channel: title
{rows}

WHAT THE BIG {ch['sport'].upper()} NEWS CHANNELS ARE POSTING (titles + views: what the audience wants right now; we
never use their clips):
{trows}

STORIES ALREADY PROPOSED RECENTLY (never propose them again, unless there is a clearly NEW development; then the
story line must say what is new):
{done}

Pick up to 4 stories. A story = one headline (feud, callout, fight booked or cancelled, result fallout, injury,
retirement, money/contract, controversy) that has FIRST-HAND material in the usable videos (the person involved
talking, or a strong take from a known fighter/pundit) — enough for a 10-20 minute video (one long podcast or
interview can be enough; a 1-minute clip alone is not). Skip stories with no usable video.
"score" 1-10 = expected views: big names, conflict, freshness, and whether the big news channels are covering it.

Return JSON {{"stories": [{{"story": "the video topic, one line in English",
 "fr": "le sujet en une phrase, en français simple", "why_fr": "pourquoi ça va faire des vues, une phrase en français",
 "people": ["main names"], "videos": [indices of usable videos to use, best first, max 6], "score": 1-10,
 "title_idea": "a YouTube title idea in the channel style (no invented quote)",
 "context": "facts stated in those video titles/descriptions that help the narrator (nothing invented)"}}]}}
best first."""
    return ai.chat_json(prompt, model=ai.text_model(), timeout=300).get("stories") or []


def _age_ts(t):
    h = (time.time() - t) / 3600
    return f"{h:.0f} h" if h >= 1 else f"{max(1, round(h * 60))} min"


def radar(sport, dry=False, force=False):
    """Cherche les sujets chauds d'une chaîne et les propose sur Discord. → liste des sujets proposés."""
    ch = N.channel(sport)
    if not ch.get("sources"):
        return []
    st = load_state()
    st["radar"][sport] = time.time()
    vids = [v for v in N.discover(ch, hours=HOURS, log=log) if not v.get("short")]
    new = [v for v in vids if v["id"] not in st["considered"]]
    if not new and not force:
        log(f"radar {sport} : rien de neuf ({len(vids)} vidéos déjà vues)")
        if not dry:
            save_state(st)
        return []
    trend = N.discover(ch, hours=48, log=log, key="trend")
    recent = [p for p in st["proposals"].values() if p["sport"] == sport and time.time() - p["t"] < 48 * 3600]
    stories = rank(ch, vids, trend, recent)
    used = {v["id"] for p in recent for v in p["videos"]}
    out = []
    for s in stories:
        try:
            score = float(s.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        picked = []
        for i in s.get("videos") or []:
            try:
                v = vids[int(i)]
            except (ValueError, IndexError, TypeError):
                continue
            if v not in picked and not N.claimer(v):
                picked.append(v)
        if score < MIN_SCORE or not picked or not s.get("story"):
            continue
        if all(v["id"] in used for v in picked):       # mêmes vidéos qu'un sujet déjà proposé : pas de doublon
            continue
        p = {"pid": new_id(), "sport": sport, "story": str(s["story"])[:300], "fr": str(s.get("fr") or s["story"])[:300],
             "why_fr": str(s.get("why_fr") or "")[:300], "people": [str(x) for x in s.get("people") or []][:6],
             "videos": picked[:6], "score": score, "title_idea": str(s.get("title_idea") or "")[:200],
             "context": str(s.get("context") or "")[:1500], "t": time.time(), "status": "proposed"}
        out.append(p)
        used |= {v["id"] for v in picked}
        if len(out) >= MAX_PROPOSALS:
            break
    for v in vids:
        st["considered"][v["id"]] = time.time()
    if out:
        embeds = []
        for k, p in enumerate(out, 1):
            src = "\n".join(f"• {v['channel']} — {v['title'][:90]} ({_age(v['published'])}, {_views(v.get('views', 0))} vues)"
                            for v in p["videos"])
            link = go_link(p["pid"])
            go = f"\n\n**[▶️ FAIRE LA VIDÉO]({link})**" if link else f"\n\n(GO : `news_auto.py go {p['pid']}`)"
            embeds.append({"title": f"{k}. {p['fr']}"[:250], "color": COLORS.get(sport, 0x12A8E0),
                           "description": (f"**Pourquoi** : {p['why_fr']}\n**Idée de titre** : {p['title_idea']}\n"
                                           f"**Sources** :\n{src}{go}")[:4000],
                           "footer": {"text": f"sujet {p['pid']} · note {p['score']:.0f}/10"}})
        discord(f"🔎 **{ch['brand']}** — sujets chauds. Clique sur « Faire la vidéo » (une page de texte s'ouvre : "
                f"c'est bon), le lien arrive ici ~40 min après.", embeds, dry=dry)
        for p in out:
            st["proposals"][p["pid"]] = p
    log(f"radar {sport} : {len(vids)} vidéos ({len(new)} nouvelles), {len(stories)} histoires, {len(out)} proposées")
    if not dry:
        save_state(st)
    return out


# ── 2. GO : boîtes aux lettres (ntfy pour le clic, relais pour Claude) ──────

def poll_ntfy(st):
    topic = os.environ.get("NEWS_AUTO_TOPIC") or ""
    if not topic:
        return []
    since = st.get("ntfy_since") or "12h"
    url = f"{NTFY}/{topic}/json?poll=1&since={urllib.parse.quote(since)}"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "drylow-agent"}), timeout=30).read()
    out = []
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("event") != "message":
            continue
        st["ntfy_since"] = ev.get("id") or st["ntfy_since"]
        m = re.fullmatch(r"go\s+([a-z0-9]{4,12})", str(ev.get("message") or "").strip().lower())
        if m:
            out.append((m.group(1), float(ev.get("time") or time.time())))
    return out


def relay(method, path, data=None, timeout=60):
    return news.vps_call(method, path, data=data, timeout=timeout)


def on_agent():
    """Lancé par l'agent du PC (pas un test dans le cloud) : lui seul lit les GO du relais et publie son état."""
    return os.environ.get("NEWS_AUTO_AGENT") == "1" and bool(os.environ.get("NEWS_WORKER_URL"))


def poll_ctl(st):
    """GO envoyés par Claude (cloud) : result.json du dossier auto-ctl du relais → {"go": [{"pid", "t"}]}."""
    if not on_agent():
        return []
    r = relay("GET", f"/pc/file?name={CTL}&path=result.json", timeout=30)
    if r.status_code != 200:
        return []
    try:
        cmds = r.json().get("go") or []
    except ValueError:
        return []
    out = []
    for c in cmds:
        key = f"{c.get('pid')}@{c.get('t')}"
        if c.get("pid") and key not in st["ctl_done"]:
            st["ctl_done"].append(key)
            out.append((str(c["pid"]), float(c.get("t") or time.time()) + 3600))   # Claude : pas de garde anti-aperçu
    return out


def ensure_ctl():
    """Crée (une fois) le dossier auto-ctl sur le relais : une « vidéo » déjà finie, jamais proposée au montage."""
    if relay("GET", f"/pc/state?name={CTL}", timeout=30).status_code == 200:
        return
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        data = b'{"noop": true}'
        info = tarfile.TarInfo("job/noop.json")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    relay("PUT", f"/pcjob?name={CTL}", data=buf.getvalue(), timeout=60)
    relay("POST", f"/pc/done?name={CTL}&ok=1", timeout=30)


def publish_status(st, current=None):
    """État lisible par Claude dans le cloud (news_auto.py status) : worker.log du dossier auto-ctl du relais."""
    if not on_agent():
        return
    props = sorted(st["proposals"].values(), key=lambda p: -p["t"])[:30]
    body = {"at": time.time(), "current": current, "radar": st["radar"],
            "proposals": [{k: p.get(k) for k in ("pid", "sport", "fr", "story", "score", "status", "t", "link", "error",
                                                 "job", "warning")} for p in props]}
    try:
        relay("PUT", f"/pc/result?name={CTL}&path=worker.log", data=json.dumps(body, ensure_ascii=False).encode(),
              timeout=30)
    except Exception as e:  # noqa: BLE001
        log("état non envoyé au relais :", str(e)[:120])


# ── 3. La vidéo, de bout en bout ────────────────────────────────────────────

def create_job(p):
    ch = N.channel(p["sport"])
    base = os.path.join(AUTO, "jobs", p["sport"], f"{datetime.date.today():%Y-%m-%d}_{news.slug(p['story'])}")
    d = base if not os.path.isdir(base) else f"{base}-{p['pid']}"
    os.makedirs(d, exist_ok=True)
    ctx = p.get("context") or ""
    ctx += "\nSource videos: " + "; ".join(f"{v['channel']}: {v['title']}" for v in p["videos"])
    with open(os.path.join(d, "job.json"), "w", encoding="utf-8") as f:
        json.dump({"channel": p["sport"], "topic": p["story"], "context": ctx.strip(), "auto": True, "pid": p["pid"],
                   "created": datetime.datetime.utcnow().isoformat(timespec="minutes"), "brand": ch["brand"]},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(d, "pid.txt"), "w", encoding="utf-8") as f:
        f.write(p["pid"])
    return d


def fetch_sources(job, videos):
    capdir = os.path.join(WORK, "news_captions")
    got = 0
    for v in videos:
        if os.path.isfile(os.path.join(job, "sources", f"{v['id']}.json")):
            got += 1
            continue
        info = N.video_info(v["id"]) or {}
        meta = dict(info, id=v["id"], title=info.get("title") or v["title"], channel=info.get("channel") or v["channel"],
                    channel_id=info.get("channel_id") or v.get("channel_id") or "")
        if (info.get("duration") or 999) < 90:
            log(f"{v['id']} : trop court ({info.get('duration')} s), ignoré")
            continue
        lines = []
        for k in range(3):
            lines = N.fetch_captions(v["id"], capdir)
            if lines:
                break
            time.sleep(5 * (k + 1))
        if not lines:
            log(f"{v['id']} : pas de sous-titres")
            continue
        try:
            N.save_source(job, meta, lines)
        except ValueError as e:
            log(f"{v['id']} : {e}")
            continue
        got += 1
        log(f"{v['id']} : {len(lines)} lignes — {meta['title'][:70]}")
        time.sleep(2)
    return got


def material_minutes(job):
    """Durée totale des moments forts trouvés (minutes) : règle la longueur de la vidéo."""
    with open(os.path.join(job, "moments.json"), "r", encoding="utf-8") as f:
        moms = json.load(f)
    by_id = {s["id"]: s["lines"] for s in N.sources(job)}
    sec = 0.0
    for m in moms:
        ln = by_id.get(m["source"])
        if ln and 0 <= m["a"] <= m["b"] < len(ln):
            sec += max(0.0, ln[m["b"]]["e"] - ln[m["a"]]["s"])
    return sec / 60, len(moms)


def review(job):
    """Relecture automatique (ce que Claude faisait à la main) : noms mal écrits dans les sous-titres, voix off
    fidèle à son extrait (bonne personne, rien d'inventé), puis bandeaux refaits."""
    path = os.path.join(job, "plan.json")
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    j = news.job_meta(job)
    ch = N.channel(j["channel"])
    segs = plan["segments"]
    # 1) noms : toutes les suites de mots en majuscule des sous-titres
    caps = {}
    for s in segs:
        if s["type"] == "clip":
            txt = " ".join(x["t"] for x in s["subs"])
            for m in re.finditer(r"\b[A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*)*", txt):
                caps[m.group(0)] = caps.get(m.group(0), 0) + 1
    known = sorted({s.get("speaker") for s in segs if s.get("speaker")} | set((plan.get("thumb") or {}).get("people") or []))
    prompt = (f"These capitalized words come from auto-generated YouTube captions of {ch['sport']} interviews about: "
              f"{j['topic']}. Captions misspell names phonetically (e.g. 'Sukian' or 'Sarukan' for Tsarukyan, 'Gatei' "
              f"or 'Gai' for Gaethje, 'Tapora' for Topuria). Known people in the video: {', '.join(known) or '-'}.\n"
              "Return JSON {\"fix\": {\"wrong\": \"right\"}} ONLY for misspelled names of real people, teams, events or "
              "places you are sure about. Never change a correct name or a normal English word. Keep the same number "
              "of words when a full name is split (\"Arman Sukian\": \"Arman Tsarukyan\").\n" +
              "\n".join(f"- {k} ({n}x)" for k, n in sorted(caps.items(), key=lambda kv: -kv[1])[:300]))
    fix = {}
    try:
        fix = {str(a): str(b) for a, b in (ai.chat_json(prompt, model=ai.text_model(), timeout=240).get("fix") or {}).items()
               if a and b and a != b and len(a) > 1}
    except Exception as e:  # noqa: BLE001
        log("relecture des noms impossible :", str(e)[:120])
    if fix:
        sp = dict(plan.get("spelling") or {}, **fix)
        plan["spelling"] = sp
        for s in segs:
            if s["type"] == "clip":
                for x, t in zip(s["subs"], N._fix_spelling_lines([x["t"] for x in s["subs"]], sp)):
                    x["t"] = t
                if s.get("quote"):
                    s["quote"]["t"] = N._fix_spelling_lines([s["quote"]["t"]], sp)[0]
        log(f"relecture : {len(fix)} noms corrigés ({', '.join(f'{a}→{b}' for a, b in list(fix.items())[:12])})")
    # 2) chaque voix off face à l'extrait qui suit
    rows = []
    for i, s in enumerate(segs):
        if s["type"] != "narration" or s.get("outro"):
            continue
        nxt = next((x for x in segs[i + 1:] if x["type"] == "clip"), None)
        clip = " ".join(x["t"] for x in nxt["subs"])[:1200] if nxt else ""
        rows.append(f"[{i}] NARRATION: {s['text']}\n    NEXT CLIP (speaker: {(nxt or {}).get('speaker') or '?'}, "
                    f"channel: {(nxt or {}).get('channel') or '?'}): {clip}")
    prompt = (f"Fact-check a {ch['sport']} news video before it is published. Each narration introduces the clip that "
              "follows. A narration is WRONG if it names the wrong speaker, says the clip contains something it does "
              "not, invents a fact (number, date, result) not in the clip or in this context, or exaggerates. "
              f"Context: {j.get('context') or '-'}\nVideo title: {plan.get('title')}\n\n" + "\n".join(rows) +
              "\n\nRewrite ONLY the wrong narrations (same style: 2-3 neutral sentences, third person, present tense, "
              "same length, names the speaker in full). Also say if the video title is false or misleading and give a "
              "corrected one keeping its quoted part only if that quote is said in a clip. Return JSON "
              '{"fixes": [{"i": index, "text": "new narration"}], "title_ok": true/false, "title": "corrected title"}')
    changed = 0
    try:
        res = ai.chat_json(prompt, model=ai.text_model(), timeout=300)
        for fx in res.get("fixes") or []:
            try:
                i = int(fx.get("i"))
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(segs) and segs[i]["type"] == "narration" and str(fx.get("text") or "").strip():
                segs[i]["text"] = str(fx["text"]).strip()
                segs[i].pop("headline", None)
                changed += 1
        if res.get("title_ok") is False and str(res.get("title") or "").strip():
            plan["title"] = str(res["title"]).strip()
            plan["titles"] = [plan["title"]] + [t for t in plan.get("titles") or [] if t != plan["title"]]
            log("relecture : titre corrigé →", plan["title"])
    except Exception as e:  # noqa: BLE001
        log("relecture des voix off impossible :", str(e)[:120])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    if changed:
        log(f"relecture : {changed} voix off réécrites")
        N.headlines(job, log=log)
        for f in glob.glob(os.path.join(job, "narration", "n*.mp3")):   # voix à refaire en entier (même ton)
            os.remove(f)


def check_sheets(job):
    """Contrôle des planches (une image / 10 s) par l'IA : seulement les vrais problèmes."""
    import base64
    import io
    from PIL import Image
    blocking, minor = [], []
    for p in sorted(glob.glob(os.path.join(job, "check", "sheet_*.jpg"))):
        im = Image.open(p).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        prompt = ("This is a contact sheet (one frame every 10 seconds, time at the bottom right of each frame) of an "
                  "automatically edited sports news video: interview clips in a colored frame with subtitles, and "
                  "narrator parts on a photo with a short headline. Report only REAL problems a viewer would notice: "
                  "black or blank frames (outside the very first and last seconds), broken or glitched images, "
                  "garbled/unreadable or overlapping text, text cut off at the edges, subtitles in a foreign language, "
                  "an obviously wrong or unrelated image, a headline that makes no sense. A fade (darker frame) between "
                  "parts is normal. Return JSON {\"blocking\": [\"time: problem\"], \"minor\": [\"time: problem\"]} "
                  "(blocking = the video should not be posted as is).")
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                                        base64.b64encode(buf.getvalue()).decode()}}]
        try:
            r = ai.chat_json([{"role": "user", "content": content}], model=ai.text_model(), timeout=240)
        except Exception as e:  # noqa: BLE001
            minor.append(f"{os.path.basename(p)} : contrôle impossible ({str(e)[:60]})")
            continue
        blocking += [f"{os.path.basename(p)[6:8]} — {x}" for x in r.get("blocking") or []]
        minor += [f"{os.path.basename(p)[6:8]} — {x}" for x in r.get("minor") or []]
    return blocking, minor


def run(job):
    """Une vidéo auto, étape par étape (relancer reprend où ça en était)."""
    j = news.job_meta(job)
    ch = N.channel(j["channel"])
    st = load_state()
    p = st["proposals"].get(j.get("pid") or "") or {}
    if not N.sources(job):
        if fetch_sources(job, p.get("videos") or []) == 0:
            raise RuntimeError("aucune source utilisable (pas de sous-titres ou chaîne qui revendique)")
    if not os.path.isfile(os.path.join(job, "moments.json")):
        news.cmd_moments(job)
    mins, n = material_minutes(job)
    log(f"matière : {n} moments, {mins:.1f} min")
    if n < 4 or mins < 4:
        raise RuntimeError(f"pas assez de matière ({n} moments, {mins:.1f} min) pour une vidéo")
    if not os.path.isfile(os.path.join(job, "plan.json")):
        target = max(8, min(int(ch.get("minutes") or 18), round(mins * 1.1)))
        N.make_plan(job, dict(ch, minutes=target), j["topic"], context=j.get("context", ""), log=log)
        N.headlines(job, log=log)
    if not os.path.isfile(os.path.join(job, "review_done")):
        review(job)
        open(os.path.join(job, "review_done"), "w").close()
    news.cmd_voice(job)
    if not os.path.isfile(os.path.join(job, "thumb.jpg")):
        try:
            from services import newsvid_thumb as T
            out = T.make(job, log=log)
            if out:
                shutil.copy(out[0], os.path.join(job, "thumb.jpg"))
        except Exception as e:  # noqa: BLE001  (la vidéo part quand même, sans miniature)
            log("miniature impossible :", str(e)[:200])
    if not os.path.isfile(os.path.join(job, "result.json")):
        news.cmd_build(job)
    with open(os.path.join(job, "result.json"), "r", encoding="utf-8") as f:
        res = json.load(f)
    if not res.get("link"):
        raise RuntimeError("montage fini mais envoi Gofile raté")
    blocking, minor = check_sheets(job)
    if (res.get("minutes") or 0) < 5:
        blocking.append(f"vidéo trop courte ({res.get('minutes')} min)")
    if blocking:
        note = "⚠️ **À REGARDER avant de poster** (contrôle auto) :\n" + "\n".join(f"• {b}" for b in blocking[:8])
    else:
        note = "🤖 faite et vérifiée toute seule"
    if not os.path.isfile(os.path.join(job, "discord_done")):
        news.cmd_send(job, tag="⚠️ auto, à regarder" if blocking else "✅ auto, à poster", note=note)
    return dict(res, warning="; ".join(blocking)[:300] if blocking else "")


def make(pid):
    st = load_state()
    p = st["proposals"].get(pid)
    if not p:
        raise SystemExit(f"sujet inconnu : {pid}")
    ch = N.channel(p["sport"])
    p.update(status="running", started=time.time(), attempts=p.get("attempts", 0) + 1)
    job = p.get("job") if p.get("job") and os.path.isdir(p["job"]) else create_job(p)
    p["job"] = job
    save_state(st)
    publish_status(st, current=pid)
    if p["attempts"] == 1:
        discord(f"▶️ **{ch['brand']}** — c'est parti : {p['fr']}\nLe lien arrive ici dans ~40 min.")
    try:
        res = run(job)
        upd = {"status": "done", "link": res.get("link"), "warning": res.get("warning"), "done": time.time()}
    except Exception as e:  # noqa: BLE001
        log(f"{pid} : ERREUR {e}")
        upd = {"status": "failed", "error": str(e)[:300]}
        discord(f"❌ **{ch['brand']}** — vidéo auto ratée : {p['fr']}\nRaison : {str(e)[:300]}")
    st = load_state()
    st["proposals"].setdefault(pid, p).update(upd)
    save_state(st)
    publish_status(st)
    return upd


def tick():
    """Agent du PC, chaque minute : GO reçus → vidéo (une à la fois) ; sinon radar si c'est l'heure."""
    st = load_state()
    gos = []
    for src in (poll_ntfy, poll_ctl):
        try:
            gos += src(st)
        except Exception as e:  # noqa: BLE001
            log(f"{src.__name__} :", str(e)[:150])
    for pid, t in gos:
        p = st["proposals"].get(pid)
        if not p:
            log(f"GO {pid} : sujet inconnu")
            continue
        if t - p["t"] < 20:              # clic « fantôme » (aperçu du lien par Discord juste après l'envoi)
            log(f"GO {pid} ignoré (trop tôt après la proposition)")
            continue
        if p["status"] in ("proposed", "failed"):
            p.update(status="queued", queued=time.time(), attempts=0 if p["status"] == "failed" else p.get("attempts", 0))
            log(f"GO {pid} : {p['story']}")
    save_state(st)
    # une vidéo coupée en route (PC éteint) reprend, deux essais max
    todo = [p for p in st["proposals"].values() if p["status"] == "running" and p.get("attempts", 0) < 2] + \
        sorted([p for p in st["proposals"].values() if p["status"] == "queued"], key=lambda p: p.get("queued", 0))
    if todo:
        make(todo[0]["pid"])
        return
    for p in st["proposals"].values():
        if p["status"] == "running":     # deux essais ratés
            p.update(status="failed", error="coupée deux fois")
    for sport in N.CHANNELS:
        if N.CHANNELS[sport].get("sources") and time.time() - st["radar"].get(sport, 0) >= RADAR_EVERY:
            try:
                radar(sport)
            except Exception as e:  # noqa: BLE001
                log(f"radar {sport} :", str(e)[:200])
            st = load_state()
    if time.time() - st.get("status_at", 0) > 300:
        st["status_at"] = time.time()
        save_state(st)
        publish_status(st)
    prune()


def prune():
    """Dossiers de vidéos auto de plus de 7 jours : effacés (rien d'utile, tout est sur Gofile et Discord)."""
    for d in glob.glob(os.path.join(AUTO, "jobs", "*", "*")):
        try:
            if time.time() - os.path.getmtime(d) > 7 * 86400:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
    capdir = os.path.join(WORK, "news_captions")
    for f in glob.glob(os.path.join(capdir, "*")):
        try:
            if time.time() - os.path.getmtime(f) > 2 * 86400:
                os.remove(f)
        except OSError:
            pass


# ── Cloud : piloter le PC par le relais ─────────────────────────────────────

def cmd_go(pid):
    ensure_ctl()
    r = relay("GET", f"/pc/file?name={CTL}&path=result.json", timeout=30)
    cur = r.json() if r.status_code == 200 else {}
    cur.setdefault("go", []).append({"pid": pid, "t": time.time()})
    cur["go"] = cur["go"][-50:]
    r = relay("PUT", f"/pc/result?name={CTL}&path=result.json", data=json.dumps(cur).encode(), timeout=30)
    print("GO envoyé au PC" if r.status_code == 200 else f"relais : {r.status_code} {r.text[:200]}")


def cmd_status():
    r = relay("GET", f"/pc/file?name={CTL}&path=worker.log", timeout=30)
    if r.status_code != 200:
        raise SystemExit("pas encore d'état (le PC n'a pas encore tourné en mode auto)")
    s = r.json()
    print(f"état du PC il y a {_age_ts(s['at'])} ; en cours : {s.get('current') or '-'}")
    for sport, t in (s.get("radar") or {}).items():
        print(f"  radar {sport} : il y a {_age_ts(t)}")
    for p in s.get("proposals") or []:
        print(f"  [{p['pid']}] {p['status']:9} {p['sport']:12} note {p.get('score')}  {p.get('fr') or p.get('story')}"
              + (f"\n      {p['link']}" if p.get("link") else "") + (f"\n      ! {p['error']}" if p.get("error") else ""))


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c, rest = argv[0], argv[1:]
    flags = [a for a in rest if a.startswith("--")]
    args = [a for a in rest if not a.startswith("--")]
    if c == "radar":
        sports = [rest[rest.index("--sport") + 1]] if "--sport" in rest else \
            [k for k, v in N.CHANNELS.items() if v.get("sources")]
        for s in sports:
            radar(s, dry="--dry-run" in flags, force="--force" in flags)
    elif c == "tick":
        tick()
    elif c == "make":
        print(json.dumps(make(args[0]), ensure_ascii=False, indent=1))
    elif c == "go":
        cmd_go(args[0])
    elif c == "status":
        cmd_status()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    main(sys.argv[1:])
