"""Actu sport (façon Fight Night MMA) : UN outil pour toutes les chaînes d'actu (MMA, boxe, foot…).

Une vidéo (15-20 min) = les vraies interviews du jour, reliées par une voix off :
  - ouverture (45-75 s) : les phrases les plus fortes, collées à la suite, sans voix off ;
  - puis, en boucle : la voix off présente en 2 phrases qui parle et de quoi, puis son extrait
    (podcast, conférence de presse, interview), affiché dans un cadre aux couleurs de la chaîne
    avec « Credit: @source » et les sous-titres ;
  - fin : un résumé + « drop your thoughts below ».

Étapes (chaque étape écrit un fichier dans le dossier de la vidéo, relancer reprend où ça en était) :
  1. sources    sous-titres horodatés de chaque vidéo source (yt-dlp sur PC, ou transcription NexLev
                enregistrée en JSON) → sources/<id>.json
  2. moments    l'IA relève dans chaque source les passages forts sur le sujet (lignes, qui parle,
                citation exacte) → moments.json
  3. plan       l'IA monte l'histoire (ouverture, ordre des extraits, voix off, titres, description, tags,
                texte de miniature = vraie citation) ; le code vérifie que chaque citation est vraiment
                dite → plan.json
  4. build (PC) télécharge les vidéos, coupe les passages, voix off, montage, Gofile, puis supprime
                tout ce qui a été téléchargé (services/newsvid_render.py)

Règles : clickbait léger seulement (une citation du titre ou de la miniature est toujours dite telle
quelle dans un extrait), jamais un propos prêté à quelqu'un qui ne l'a pas tenu, crédits affichés.
"""
import json
import os
import re
import subprocess
import sys

from services import ai

# ── Chaînes d'actu (même outil, une config par chaîne) ──────────────────────
# brand/handle : affichés sur le fond ; voice : voix Algrow de la voix off ; sources : chaînes YouTube
# où sortent les interviews du jour (pour la recherche automatique sur PC).
CHANNELS = {
    "mma_en": {
        "name": "MMA news (UFC)", "sport": "MMA / UFC", "language": "en",
        "brand": "CAGE DISPATCH", "handle": "", "subscribe": "SUBSCRIBE FOR DAILY MMA NEWS",
        "accent": "#E10600", "accent2": "#FFD21F",
        "voice_provider": "algrow", "voice": "jvV8uNVYXJa37GHVtjXf",  # Joe Stokes, présentateur radio US
        "minutes": 18,
        "thumb_accent": "#40DCF8",  # bleu clair de la bannière @CageDispatch (« DISPATCH ») : mot fort + contour
        "search": ["UFC news", "Dana White", "UFC interview"],
        # chaînes où sortent les interviews (id YouTube : leur flux RSS donne les vidéos du jour, cloud et PC).
        # Seulement des chaînes SANS revendication automatique (voir CLAIMERS) : vérifié le 3 oct. avec NexLev
        # get_content_owner (indépendantes = « IVP » ou sans réseau ; Helwani/Yahoo et Cormier/The Volume sont dans un
        # réseau mais leurs extraits n'ont pas été revendiqués dans la vidéo Gaethje).
        "sources": {"The Ariel Helwani Show": "UCVOdVp54jLrFhRUm4S29HeA", "Chael Sonnen": "UCRlvF4jIeBWqXJDGNXfPyVw",
                    "Daniel Cormier": "UC_1TBgZ5FuGSdRlrrnyJU7w", "FLAGRANT": "UC5PstSsGrRwj2o6asQpC4Rg",
                    "FLAGRANT CLIPS": "UCAjmXPKv1zpYftSDAMeJz8A", "Michael Bisping": "UCDrG2_1TcVkXKXXsD6Kjwig",
                    "Luke Thomas": "UC2EuJ9xTs0XkDZI9YGx7QZA", "Thiccc Boy": "UCiE3q35hojEnPEjjCvnwm5A",
                    "Kolos MMA": "UCwwcynlkf66wcexrsH-azkw", "JRE Clips": "UCnxGkOGNMqQEUMvroOWps6Q",
                    "PowerfulJRE": "UCzQUP1qoWDoEbmsQxvdjxgQ", "Pound 4 Pound with Kamaru & Henry": "UCpVcPOrB9tWcBGe58FYjOmQ",
                    "Submission Radio": "UCNrEHIf8QmKK-cAag4YxIXQ", "DOUBLE COVERAGE PODCAST": "UCf1q6dhccWr6eQEcFFnJSbA"},
        "people": "fighters, coaches, managers, promoters and pundits",
    },
    "boxing_en": {
        "name": "Boxing news", "sport": "Boxing", "language": "en",
        "brand": "RING DISPATCH", "handle": "", "subscribe": "SUBSCRIBE FOR DAILY BOXING NEWS",
        "accent": "#D4A017", "accent2": "#FFFFFF",
        "voice_provider": "algrow", "voice": "jvV8uNVYXJa37GHVtjXf",
        "minutes": 18,
        "search": ["boxing news", "boxing interview", "boxing press conference"],
        "sources": {},  # à remplir (id YouTube) avant de lancer la chaîne : Matchroom, Top Rank, IFL TV, Fight Hub…
        "people": "boxers, trainers, promoters and pundits",
    },
    "football_en": {
        "name": "Football news", "sport": "Football (soccer)", "language": "en",
        "brand": "PITCH DISPATCH", "handle": "", "subscribe": "SUBSCRIBE FOR DAILY FOOTBALL NEWS",
        "accent": "#1DB954", "accent2": "#FFFFFF",
        "voice_provider": "algrow", "voice": "jvV8uNVYXJa37GHVtjXf",
        "minutes": 18,
        "search": ["press conference football", "Premier League press conference", "football interview"],
        "sources": {},  # à remplir (id YouTube) : Sky Sports, TNT Sports, The Overlap, conférences des clubs…
        "people": "players, managers, agents and pundits",
    },
}

NARRATION_STYLE = """THE NARRATOR (copied from the reference channel, Fight Night MMA):
- Every narration block is TWO sentences (25-45 words, about 11 s), or THREE when a verified fact from the news
  context adds real value (a record, a date, a number, what happened in the fight): that added context is what
  makes the video more than a compilation (YouTube monetization). Third person, present tense, neutral news
  register. It names the next speaker in full, says what they talk about, and hands over to the clip.
- Sentence 1: a connector + full name + a reporting verb + the topic. Connectors rotate (never twice in a row):
  "Meanwhile,", "On the other side,", "At the same time,", "Beyond that,", "Adding to that,", "Taking that
  further,", "On a similar note,", "From X's side,", "However,", "That's when", "Then,". Reporting verbs rotate:
  questions, points toward, highlights, weighs in on, fires back at, lays out, puts X forward, admits, reveals,
  doubles down on, keeps X in the conversation.
- Sentence 2 ("He…"/"She…") gives the angle the clip will prove, with one concrete detail (a number, a name,
  a date) when the clip has one.
- NEVER quote the clip in the narration, never give the narrator's own opinion, never invent a fact. Facts in
  the narration must come from the clips or from the provided news context.
- First narration block (right after the cold open): restate the premise in one sentence and ask the question
  the video answers ("So what makes Gaethje turn down a payday this big?").
- Last block (outro): recap both sides in one sentence, one stakes line ("What happens next could reshape the
  division."), then "So, drop your thoughts below." Nothing else."""


def channel(key):
    if key not in CHANNELS:
        raise KeyError(f"Chaîne d'actu inconnue : {key} (connues : {', '.join(CHANNELS)})")
    return dict(CHANNELS[key], key=key)


# ── 0. Les vidéos du jour (flux RSS des chaînes sources : marche dans le cloud comme sur PC) ──

def feed(channel_id):
    """15 dernières vidéos d'une chaîne : [{id, title, channel, published (ISO), description}]."""
    import urllib.request
    import xml.etree.ElementTree as ET
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(raw)
    name = root.findtext("a:title", default="", namespaces=ns)
    out = []
    for e in root.findall("a:entry", ns):
        out.append({"id": e.findtext("yt:videoId", namespaces=ns), "title": e.findtext("a:title", namespaces=ns),
                    "channel": name, "published": e.findtext("a:published", namespaces=ns),
                    "description": (e.findtext("m:group/m:description", default="", namespaces=ns) or "")[:300]})
    return out


def discover(ch, hours=48, log=print):
    """Vidéos sorties dans les `hours` dernières heures sur les chaînes sources, les plus récentes d'abord."""
    import datetime
    from concurrent.futures import ThreadPoolExecutor
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)

    def one(cid):
        try:
            return feed(cid)
        except Exception as e:  # noqa: BLE001
            log(f"flux {cid} : {str(e)[:80]}")
            return []
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = [v for vs in ex.map(one, (ch.get("sources") or {}).values()) for v in vs]
    fresh = [v for v in rows if v["published"] and
             datetime.datetime.fromisoformat(v["published"].replace("Z", "+00:00")) >= since]
    fresh.sort(key=lambda v: v["published"], reverse=True)
    return fresh


def stories(ch, videos):
    """L'IA regroupe les vidéos du jour en histoires et les classe (gros noms, conflit, nouveauté)."""
    rows = "\n".join(f"{i}. [{v['published'][:16]}] {v['channel']}: {v['title']}" for i, v in enumerate(videos))
    prompt = f"""You are the editor of a {ch['sport']} news YouTube channel copied from Fight Night MMA (it posts 4-5
videos a day about the biggest names: feuds, callouts, money, rematches, retirements, controversies).
Here are the videos published in the last hours by the main {ch['sport']} channels:
{rows}

Group them into STORIES (one story = one feud or headline, e.g. "Gaethje refuses the Topuria rematch"). Rank the
stories by how many views a Fight Night style video would get (big names, conflict, money, fresh quotes). For each
story: "story" (one line), "people" (main names), "videos" (indices of the videos that contain first-hand
interviews or statements for it; skip pure reaction or compilation videos), "why" (one line).
Return JSON {{"stories": [...]}} best first, max 8."""
    return ai.chat_json(prompt, model=ai.text_model(), timeout=240).get("stories") or []


# ── Sous-titres des sources ─────────────────────────────────────────────────

def _ts(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def lines_from_nexlev(data):
    """Transcription NexLev ({"transcript": [{startMs, endMs, text}]}) → lignes [{s, e, t, turn}].
    La fin d'une ligne = début de la suivante (les sous-titres auto se chevauchent) ; « >> » = changement
    de personne qui parle."""
    raw = data.get("transcript") if isinstance(data, dict) else data
    out = []
    for x in raw or []:
        t = re.sub(r"\s+", " ", str(x.get("text") or "")).strip()
        if not t:
            continue
        turn = t.startswith(">>")
        t = t.lstrip("> ").strip()
        out.append({"s": int(x.get("startMs") or 0) / 1000.0, "e": int(x.get("endMs") or 0) / 1000.0, "t": t,
                    "turn": turn})
    return _fix_ends(out)


def lines_from_json3(data):
    """Sous-titres YouTube json3 (yt-dlp --sub-format json3) → lignes [{s, e, t, turn}]."""
    out = []
    for ev in data.get("events") or []:
        segs = ev.get("segs")
        if not segs:
            continue
        t = re.sub(r"\s+", " ", "".join(s.get("utf8", "") for s in segs)).strip()
        if not t:
            continue
        turn = t.startswith(">>")
        t = t.lstrip("> ").strip()
        if t:
            s = int(ev.get("tStartMs") or 0) / 1000.0
            out.append({"s": s, "e": s + int(ev.get("dDurationMs") or 0) / 1000.0, "t": t, "turn": turn})
    return _fix_ends(out)


def _fix_ends(lines):
    lines.sort(key=lambda x: x["s"])
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["s"] if i + 1 < len(lines) else ln["e"]
        ln["e"] = round(max(ln["s"] + 0.3, min(ln["e"], nxt) if nxt > ln["s"] else ln["e"]), 3)
    return lines


def fetch_captions(video_id, dest_dir):
    """Sous-titres anglais d'une vidéo via yt-dlp (sur PC ; le cloud se fait bloquer par YouTube)."""
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, video_id)
    cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-subs", "--write-auto-subs",
           "--sub-langs", "en.*,en", "--sub-format", "json3", "-o", out, *yt_js_args(),
           f"https://www.youtube.com/watch?v={video_id}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    for f in sorted(os.listdir(dest_dir)):
        if f.startswith(video_id) and f.endswith(".json3"):
            with open(os.path.join(dest_dir, f), "r", encoding="utf-8") as fh:
                return lines_from_json3(json.load(fh))
    return []


def yt_js_args():
    """yt-dlp a besoin d'un moteur JavaScript pour YouTube : deno (par défaut) ou node."""
    import shutil
    local = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "deno",
                         "deno.exe" if os.name == "nt" else "deno")
    if os.path.isfile(local):  # dans le PATH (deno est le moteur par défaut de yt-dlp) : pas de « C:\\ » à passer
        d = os.path.dirname(local)
        if d not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        return []
    if shutil.which("deno"):
        return []
    if shutil.which("node"):
        return ["--js-runtimes", "node"]
    return []


def video_info(video_id):
    """Titre, chaîne, date de sortie, durée (yt-dlp, sur PC)."""
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-j", "--skip-download", *yt_js_args(),
                        f"https://www.youtube.com/watch?v={video_id}"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {}
    return {"id": video_id, "title": d.get("title"), "channel": d.get("channel"),
            "handle": d.get("uploader_id") or "", "date": d.get("upload_date"), "duration": d.get("duration")}


def load_source(path):
    """Fichier source (sources/<id>.json) : {"id", "title", "channel", "handle", "date", "lines": [...]}."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Chaînes qui revendiquent (Content ID) les extraits repris : interdites comme sources. One Night with Steiny a
# revendiqué 6 passages de la vidéo Gaethje (3 oct., « Shots Studios Affiliate ») ; même réseau = même risque.
# Avant d'ajouter une nouvelle chaîne source : NexLev get_content_owner(channel_id) → dans un réseau (MCN, média) =
# risque, à tester sur un seul extrait ; « IVP » ou rien = indépendant, sans Content ID.
CLAIMERS = {
    "UCdd7HZYwU1YOE2lILZ5P2VQ": "One Night with Steiny (Shots Studios : revendication du 3 oct.)",
    "UCTvuMRhyrTVgbEdLyymZq8g": "FULL SEND MMA (Shots Studios)",
    "UCvgfXK4nTYKudb0rFR6noLA": "UFC (réseau UFC)",
    "UC4f1JueVgo5t9HSmobCRPug": "MMA Fighting (Vox Media)",
    "UCk9lx4sKRQCDTyXFaouk_vQ": "Mighty / Demetrious Johnson (Whistle Sports)",
}
CLAIMER_NAMES = {"one night with steiny", "full send mma", "full send podcast", "ufc", "mmafightingonsbn",
                 "mma fighting", "mighty", "nelk", "nelk boys"}


def claimer(meta):
    """Raison du refus si la source vient d'une chaîne qui revendique, sinon ''."""
    cid = meta.get("channel_id") or meta.get("channelId") or ""
    if cid in CLAIMERS:
        return CLAIMERS[cid]
    name = (meta.get("channel") or "").strip().lower()
    return f"{meta.get('channel')} (chaîne qui revendique)" if name in CLAIMER_NAMES else ""


def save_source(folder, meta, lines):
    why = claimer(meta)
    if why:
        raise ValueError(f"source refusée, revendication Content ID : {why}")
    os.makedirs(os.path.join(folder, "sources"), exist_ok=True)
    src = dict(meta, lines=lines)
    with open(os.path.join(folder, "sources", f"{meta['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(src, f, ensure_ascii=False, indent=1)
    return src


def sources(folder):
    d = os.path.join(folder, "sources")
    if not os.path.isdir(d):
        return []
    return [load_source(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(".json")]


# ── 2. Moments forts de chaque source ───────────────────────────────────────

WINDOW = 140  # lignes par passage envoyé à l'IA (~7 min de parole)


def _numbered(lines, a, b):
    return "\n".join(f"[{i}] {_ts(lines[i]['s'])} {'>> ' if lines[i].get('turn') else ''}{lines[i]['t']}"
                     for i in range(a, min(b, len(lines))))


def find_moments(src, topic, ch, log=print):
    """Passages forts d'une source sur le sujet → [{"source", "a", "b", "speaker", "sure", "summary",
    "quote", "heat"}] (a, b = indices de lignes, b inclus)."""
    lines = src["lines"]
    found = []
    for a in range(0, len(lines), WINDOW - 10):
        b = min(len(lines), a + WINDOW)
        prompt = f"""You are the researcher of a {ch['sport']} news YouTube channel. Today's video is about:
TOPIC: {topic}

Below is part of an auto-generated transcript (YouTube captions, names often misspelled; ">>" marks a change of
speaker) of this video:
SOURCE: "{src.get('title', '')}" on the channel {src.get('channel', '')} (published {src.get('date', '?')})

Find every passage where someone says something strong, newsworthy or controversial about the TOPIC (a claim, a
callout, a reveal, a prediction, an insult, a number, an offer, a refusal). Each passage must be a COMPLETE
thought: start at the beginning of a sentence (or of a question that the answer needs) and end at the end of a
sentence. 12 to 70 seconds long. Skip small talk, ads, intros and anything off-topic.

For each passage give:
- "a", "b": first and last line numbers (inclusive);
- "speaker": who is talking (full real name), deduced from the source and the context; "sure": true only if you
  are certain (the host introduces them, it is their own channel/show, they speak in the first person about
  their own fight…). If several people talk, name the main one;
- "quoting": if the person talking is READING or QUOTING someone else's words (a social media post, a
  statement, another interview), the name of the person being quoted, else "". The speaker stays the person
  actually talking: never present read-out words as spoken by the quoted person;
- "replay": true if this passage is a clip from ANOTHER show replayed inside this video (a reaction video playing
  a podcast clip), false if it is this channel's own footage;
- "summary": one neutral sentence;
- "quote": the single most clickable sentence of the passage, VERBATIM from the lines (fix only obvious caption
  misspellings of names);
- "heat": 1-10 (10 = a headline everyone will click).

Return JSON {{"moments": [...]}} (empty list if nothing relevant).

TRANSCRIPT:
{_numbered(lines, a, b)}"""
        try:
            res = ai.chat_json(prompt, model=ai.text_model(), timeout=300)
        except ai.AIError as e:
            log(f"moments {src['id']} [{a}-{b}] : {str(e)[:100]}")
            continue
        for m in res.get("moments") or []:
            try:
                ma, mb = int(m["a"]), int(m["b"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (0 <= ma <= mb < len(lines)):
                continue
            found.append({"source": src["id"], "a": ma, "b": mb, "speaker": str(m.get("speaker") or "").strip(),
                          "sure": bool(m.get("sure")), "summary": str(m.get("summary") or "").strip(),
                          "quote": str(m.get("quote") or "").strip(), "heat": int(m.get("heat") or 0),
                          "quoting": str(m.get("quoting") or "").strip(), "replay": bool(m.get("replay"))})
        if b >= len(lines):
            break
    # passages en double (fenêtres qui se chevauchent) : on garde le plus chaud
    found.sort(key=lambda m: (m["a"], -m["heat"]))
    out = []
    for m in found:
        if out and m["a"] <= out[-1]["b"]:
            if m["heat"] > out[-1]["heat"]:
                out[-1] = m
            continue
        out.append(m)
    return out


# ── Citations : toujours vraiment dites ─────────────────────────────────────

def _words(s):
    return re.findall(r"[a-z0-9$%']+", (s or "").lower().replace("’", "'"))


def quote_in(lines, a, b, quote, min_ratio=0.8):
    """Vrai si `quote` est dit (dans l'ordre) entre les lignes a et b ; les noms mal transcrits et les
    mots censurés (« f*** ») sont tolérés à hauteur de 20 % des mots."""
    q = [w for w in _words(quote) if w]
    if not q:
        return False
    hay = _words(" ".join(ln["t"] for ln in lines[max(0, a):b + 1]))
    if not hay:
        return False
    best = 0
    for i in range(len(hay)):  # meilleur alignement mot à mot depuis chaque départ
        k, hit = i, 0
        for w in q:
            for j in range(k, min(len(hay), k + 4)):
                if hay[j] == w or (len(w) > 4 and hay[j][:4] == w[:4]):
                    hit, k = hit + 1, j + 1
                    break
        best = max(best, hit)
        if best == len(q):
            break
    return best >= max(1, round(len(q) * min_ratio))


# ── 3. Plan de la vidéo ─────────────────────────────────────────────────────

def _moment_rows(moms, by_id):
    rows = []
    for k, m in enumerate(moms):
        src = by_id[m["source"]]
        dur = src["lines"][m["b"]]["e"] - src["lines"][m["a"]]["s"]
        flags = (f" (reading {m['quoting']}'s words)" if m.get("quoting") else "") + \
            (" (REPLAYED from another show: avoid)" if m.get("replay") else "")
        rows.append(f"M{k} | {m['speaker'] or 'unknown'}{'' if m['sure'] else ' (not sure)'}{flags} | {dur:.0f}s | heat "
                    f"{m['heat']} | source: {src.get('channel', '')} \"{src.get('title', '')[:70]}\" "
                    f"({src.get('date', '?')}) | {m['summary']} | quote: \"{m['quote']}\"")
    return "\n".join(rows)


def make_plan(folder, ch, topic, context="", log=print):
    """moments.json + sources → plan.json (ouverture, blocs voix off + extrait, titres, miniature…)."""
    with open(os.path.join(folder, "moments.json"), "r", encoding="utf-8") as f:
        moms = json.load(f)
    by_id = {s["id"]: s for s in sources(folder)}
    moms = [m for m in moms if m["source"] in by_id]
    target = int(ch.get("minutes") or 18)
    prompt = f"""You are the showrunner of the {ch['sport']} news YouTube channel "{ch['brand']}". Format copied from
Fight Night MMA (13.9K subs, 8.9M views, 4-5 videos a day): ~80% real interview clips of the day, 20% a neutral
narrator who links them. Build today's video.

TOPIC: {topic}
NEWS CONTEXT (verified, use for narration facts): {context or '-'}

AVAILABLE MOMENTS (from real interviews published in the last days; durations are approximate):
{_moment_rows(moms, by_id)}

BUILD:
1. "cold_open": 3-5 moments (ids), the hottest lines first, together 45-80 seconds. No narration in the cold open.
   You may trim a long moment for the cold open with "trim": [first_line, last_line] (absolute line numbers
   inside that moment's a-b range).
2. CLIP LENGTH: every clip 15-50 seconds (YouTube monetization: short clips + narration, never long re-uploads).
   For a longer moment, keep its best part with "trim": [first_line, last_line] (absolute line numbers inside
   that moment's a-b range, starting and ending on a full sentence).
3. "blocks": the body, {max(10, target * 60 // 55)}-{max(14, target * 60 // 45)} blocks in story order: each is one
   narration block then one moment. A moment can appear in the cold open AND later in full. Group by storyline
   (e.g. 1. the money and the refusal, 2. the other side answers, 3. what comes next). Prefer moments where the
   speaker is sure. Never use a "not sure" speaker's name in the narration (say "the host", "his coach"…).
   Never use a moment marked REPLAYED when the original show is among the sources. For a moment where someone
   reads another person's words, the narration says who reads them ("On Flagrant, the hosts read Topuria's post").
   Total length ≈ {target} minutes (narration ~11 s per block + clip durations).
4. Narration of each block: follow THE NARRATOR rules below. The narration only introduces what the clip says,
   it never contradicts or exaggerates it.
5. "outro": the last narration block (no clip after it).
6. "titles": 5 options in the channel's style: a SHORT verbatim quote in quotes + CAPS verbs, e.g.
   “YOU GOT HUMILIATED!” Justin Gaethje DESTROYS Ilia Topuria For Demanding Rematch!
   Light clickbait only: the quoted part MUST be said (nearly word for word) in one of the clips you used, and
   the rest must be true. Put the best first. 70-100 characters.
7. "thumb": {{"text": 2-6 words, a real quote from a used clip (caps, may censor swear words like FU**ING),
   "highlight": the 1-2 words to color, "people": [the 2 main people, full names], "moment": id of the clip the
   quote comes from}}.
8. "description" (3 short paragraphs, factual, credits the sources by channel name at the end: "Credits:
   ..."), "tags" (15-25), "pinned_comment" (a question to the viewers).
9. "spelling": a map of caption misspellings → correct spelling for every name seen in the moments
   (e.g. {{"Gachi": "Gaethje", "Tapura": "Topuria"}}).

{NARRATION_STYLE}

Return JSON:
{{"titles": [...], "thumb": {{...}}, "cold_open": [{{"moment": "M3"}}, {{"moment": "M7", "trim": [120, 131]}}],
  "blocks": [{{"narration": "...", "moment": "M2"}}, {{"narration": "...", "moment": "M5", "trim": [40, 52]}}], "outro": "...", "description": "...", "tags": [...],
  "pinned_comment": "...", "spelling": {{...}}}}"""
    plan = ai.chat_json(prompt, model=ai.text_model(), timeout=420)
    with open(os.path.join(folder, "plan_raw.json"), "w", encoding="utf-8") as f:  # pour remonter le plan sans l'IA
        json.dump(plan, f, ensure_ascii=False, indent=1)
    return materialize(folder, ch, topic, plan, moms, by_id, log=log)


def _mid(x):
    m = re.match(r"^\s*M?(\d+)\s*$", str(x or ""))
    return int(m.group(1)) if m else None


def _fix_spelling(text, spelling):
    for wrong, right in (spelling or {}).items():
        if wrong and right and wrong.lower() != right.lower():
            text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.I)
    return text


_SENT_END = re.compile(r"[.?!][\"”’')\]]*$")
# Prononciation de la voix off (Algrow lit mal certains noms : « Gaethje » = GAY-chee) : orthographe phonétique
# envoyée à la voix SEULEMENT (sous-titres, titres et bandeaux gardent la vraie orthographe). Un nom = un mot.
PRONOUNCE = {"Gaethje": "Gay-chee", "Cormier": "Kor-mee-ay", "Tsarukyan": "Tsa-roo-kee-an",
             "Oliveira": "Oli-vay-ra"}


def speakable(text):
    for k, v in PRONOUNCE.items():
        text = re.sub(rf"\b{k}\b", v, text)
    return text


MAX_CLIP = 60.0   # un extrait ne dure jamais plus (monétisation : extraits courts + voix off)
TEASER = 40.0     # ouverture (comme Fight Night : 15-40 s) : un échange complet, compréhensible seul


def _pieces(lines, a, b):
    """Lignes a..b → morceaux de phrase horodatés : une ligne est coupée à chaque fin de phrase, l'instant
    de la coupure est estimé au prorata des caractères (le PC recale ensuite sur le silence le plus proche)."""
    out = []
    for i in range(max(0, a), min(len(lines), b + 1)):
        ln = lines[i]
        t = ln["t"]
        dur = max(0.1, ln["e"] - ln["s"])
        pos = 0
        for p in re.split(r"(?<=[.?!])\s+(?=[A-Z0-9\"“'])", t):
            k0 = t.find(p, pos)
            k1 = k0 + len(p)
            pos = k1
            out.append({"s": ln["s"] + dur * k0 / max(1, len(t)), "e": ln["s"] + dur * k1 / max(1, len(t)),
                        "t": p, "end": bool(_SENT_END.search(p)), "line": i})
    return out


def _quote_piece(pieces, quote):
    """(premier, dernier) morceau de la citation (alignement mot à mot qui démarre sur son 1er mot), ou None."""
    q = _words(quote)
    if not q:
        return None
    words = [(w, k) for k, p in enumerate(pieces) for w in _words(p["t"])]

    def same(a, b):
        return a == b or (len(b) > 4 and a[:4] == b[:4])
    best, span = 0, None
    for i in range(len(words)):
        if not same(words[i][0], q[0]):
            continue
        k, hit, last = i, 0, i
        for w in q:
            for j in range(k, min(len(words), k + 4)):
                if same(words[j][0], w):
                    hit, k, last = hit + 1, j + 1, j
                    break
        if hit > best:
            best, span = hit, (words[i][1], words[last][1])
    return span if best >= max(1, round(len(q) * 0.6)) else None


def _window(pieces, first, last, max_len, anchor=None):
    """Plus longue suite de phrases entières ≤ max_len qui contient toute la citation `anchor` = (début, fin)."""
    starts = [k for k in range(first, last + 1) if k == first or pieces[k - 1]["end"]]
    ends = [k for k in range(first, last + 1) if pieces[k]["end"]] or [last]
    a0, a1 = anchor if anchor else (None, None)
    best = None
    for s in starts:
        if a0 is not None and s > a0:
            break
        for e in ends:
            if e < s or (a1 is not None and e < a1):
                continue
            dur = pieces[e]["e"] - pieces[s]["s"]
            if dur > max_len:
                break
            if best is None or dur > best[2]:
                best = (s, e, dur)
    if best is None:  # aucune phrase entière ne tient : la citation seule, coupée à max_len
        s = a0 if a0 is not None else first
        e = s
        while e + 1 <= last and pieces[e + 1]["e"] - pieces[s]["s"] <= max_len:
            e += 1
        return s, e
    return best[0], best[1]


def clip_spec(src, a, b, spelling, quote=None, max_len=MAX_CLIP, pad_in=0.15, pad_out=0.35):
    """Extrait = lignes a..b de la source, recalé sur des phrases entières (jamais « nothing illegal in the »),
    au plus max_len secondes autour de la citation → {video, start, end, subs: [{s, e, t}] relatifs au début}."""
    lines = src["lines"]
    pcs = _pieces(lines, a, min(len(lines) - 1, b + 14))  # de quoi finir la phrase, ou la réponse à une question
    in_ab = [k for k, p in enumerate(pcs) if p["line"] <= b]
    first = 0
    if a > 0 and not _SENT_END.search(lines[a - 1]["t"]):  # la 1re ligne commence au milieu d'une phrase
        nxt = [k for k in range(1, len(pcs)) if pcs[k - 1]["end"] and pcs[k]["line"] <= a + 1]
        first = nxt[0] if nxt else 0
    last = in_ab[-1] if in_ab else len(pcs) - 1
    while last + 1 < len(pcs) and not pcs[last]["end"] and pcs[last + 1]["line"] <= b + 2:
        last += 1  # finir la phrase commencée
    anchor = _quote_piece(pcs[first:last + 1], quote) if quote else None
    if anchor:
        anchor = (first + anchor[0], first + anchor[1])
    s, e = _window(pcs, first, last, max_len, anchor)
    # un échange complet (l'utilisateur, 3 oct. : « ça coupe avant qu'il réponde ») : jamais finir sur une question,
    # on garde au moins ~6 s de réponse, en phrases entières
    lim = max_len + 20

    def fits(k):
        return k < len(pcs) and pcs[k]["e"] - pcs[s]["s"] <= lim
    if pcs[e]["t"].rstrip().endswith("?"):
        q_end = pcs[e]["e"]
        while fits(e + 1) and (pcs[e]["t"].rstrip().endswith("?") or not pcs[e]["end"] or pcs[e]["e"] - q_end < 6):
            e += 1
    start = max(0.0, pcs[s]["s"] - pad_in)
    end = pcs[e]["e"] + pad_out
    subs = [{"s": round(max(0.0, p["s"] - start), 2), "e": round(min(p["e"] - start, end - start), 2),
             "t": _fix_spelling(p["t"], spelling)} for p in pcs[s:e + 1]]
    out = {"video": src["id"], "start": round(start, 2), "end": round(end, 2),
           "credit": ("@" + src["handle"].lstrip("@")) if src.get("handle") else (src.get("channel") or ""),
           "channel": src.get("channel") or "", "subs": subs}
    if anchor and s <= anchor[0] and anchor[1] <= e:  # la phrase choc : affichée en grand au montage
        out["quote"] = {"t": _fix_spelling(quote, spelling), "s": round(max(0.0, pcs[anchor[0]]["s"] - start), 2),
                        "e": round(min(pcs[anchor[1]]["e"] - start, end - start), 2)}
    return out


def headlines(folder, log=print):
    """Titre court (bandeau à l'écran) pour chaque voix off + le fil d'actu du bas : seulement ce que la voix off
    dit (pas de nouveau fait). Écrit dans plan.json (seg["headline"], plan["ticker"])."""
    path = os.path.join(folder, "plan.json")
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    nar = [(i, s["text"]) for i, s in enumerate(plan["segments"]) if s["type"] == "narration" and not s.get("outro")]
    if not nar:
        return plan
    prompt = ("You write on-screen headlines for a sports news video. For each voice-over below, write ONE headline "
              "in ALL CAPS, 2 to 6 words, punchy but strictly true to that voice-over (no fact it does not say, no "
              "invented quote). Use surnames (e.g. GAETHJE, TOPURIA). Then write 'ticker': 4 to 8 short ALL CAPS "
              "news lines (3 to 8 words each) summarising the whole video for a scrolling news ticker, same rule.\n"
              'Answer JSON: {"headlines": [{"i": <index>, "h": "..."}], "ticker": ["..."]}\n\n' +
              "\n".join(f"[{i}] {t}" for i, t in nar))
    res = ai.chat_json(prompt, model=ai.text_model(), timeout=240)
    got = {int(h["i"]): str(h["h"]).strip().upper() for h in res.get("headlines") or [] if str(h.get("i", "")).isdigit()}
    for i, _ in nar:
        if got.get(i):
            plan["segments"][i]["headline"] = got[i][:48]
    plan["ticker"] = [str(t).strip().upper()[:70] for t in res.get("ticker") or [] if str(t).strip()][:8]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    log(f"bandeaux : {len(got)} titres, fil d'actu {len(plan['ticker'])} lignes")
    return plan


def materialize(folder, ch, topic, plan, moms, by_id, log=print):
    """Réponse de l'IA → plan.json vérifié (extraits réels, citations vraiment dites)."""
    spelling = plan.get("spelling") or {}

    def moment(ref):
        k = _mid(ref)
        return moms[k] if k is not None and 0 <= k < len(moms) else None

    def span(m, tr):
        a, b = m["a"], m["b"]
        if isinstance(tr, list) and len(tr) == 2:
            try:
                ta, tb = int(tr[0]), int(tr[1])
                if m["a"] <= ta <= tb <= m["b"]:
                    a, b = ta, tb
            except (TypeError, ValueError):
                pass
        return a, b

    segs = []
    # plus d'ouverture en extraits (l'utilisateur, 3 oct. : « au tout début, je veux l'intro avec la voix off et la
    # photo ») : la vidéo commence par la 1re voix off ; une chaîne peut la remettre avec "cold_open": True
    for c in (plan.get("cold_open") or []) if ch.get("cold_open") else []:
        m = moment(c.get("moment"))
        if not m:
            continue
        a, b = span(m, c.get("trim"))
        segs.append(dict(clip_spec(by_id[m["source"]], a, b, spelling, quote=m.get("quote"), max_len=TEASER),
                         type="clip", full=True,
                         speaker=m["speaker"] if m["sure"] else ""))
    for blk in plan.get("blocks") or []:
        m = moment(blk.get("moment"))
        nar = re.sub(r"\s+", " ", str(blk.get("narration") or "")).strip()
        if not m:
            log(f"bloc sans extrait ignoré : {nar[:60]}")
            continue
        if nar:
            segs.append({"type": "narration", "text": nar, "next_video": m["source"]})
        a, b = span(m, blk.get("trim"))
        segs.append(dict(clip_spec(by_id[m["source"]], a, b, spelling, quote=m.get("quote")), type="clip", full=False,
                         speaker=m["speaker"] if m["sure"] else ""))
    # l'ouverture ne rejoue pas un passage du corps (sinon le spectateur l'entend deux fois)
    body = [x for x in segs if x["type"] == "clip" and not x.get("full")]
    for c in [x for x in segs if x.get("full")]:
        if any(b["video"] == c["video"] and b["start"] < c["end"] and c["start"] < b["end"] for b in body):
            log(f"ouverture : {c['video']} {c['start']}-{c['end']} recoupe un extrait du corps → retiré")
            segs.remove(c)
    if plan.get("outro"):
        segs.append({"type": "narration", "text": re.sub(r"\s+", " ", plan["outro"]).strip(), "next_video": None,
                     "outro": True})
    # titres et miniature : la citation doit être dite dans un extrait utilisé
    used = [s for s in segs if s["type"] == "clip"]

    def said(q):
        q = re.sub(r"[“”\"]", "", q or "")
        q = re.sub(r"\*+", "", q)
        for s in used:
            src = by_id[s["video"]]
            idx = [i for i, ln in enumerate(src["lines"]) if s["start"] - 0.5 <= ln["s"] <= s["end"]]
            if idx and quote_in(src["lines"], idx[0], idx[-1], q, 0.75):
                return True
        return False

    titles = []
    for t in plan.get("titles") or []:
        qs = re.findall(r"[“\"]([^”\"]{3,80})[”\"]", t)
        if qs and not all(said(q) for q in qs):
            log(f"titre écarté (citation jamais dite) : {t}")
            continue
        titles.append(t.strip())
    thumb = dict(plan.get("thumb") or {})
    if thumb.get("text") and not said(thumb["text"]):
        log(f"texte de miniature jamais dit : {thumb.get('text')} → à refaire")
        thumb["checked"] = False
    else:
        thumb["checked"] = True
    out = {"channel": ch["key"], "brand": ch["brand"], "accent": ch["accent"], "accent2": ch.get("accent2"),
           "subscribe": ch.get("subscribe") or "SUBSCRIBE FOR DAILY NEWS",
           "topic": topic, "voice": {"provider": ch.get("voice_provider", "algrow"), "id": ch["voice"]},
           "titles": titles, "title": titles[0] if titles else "", "thumb": thumb,
           "description": plan.get("description") or "", "tags": plan.get("tags") or [],
           "pinned_comment": plan.get("pinned_comment") or "", "spelling": spelling, "segments": segs}
    est = sum((s["end"] - s["start"]) if s["type"] == "clip" else len(s["text"].split()) / 2.9 for s in segs)
    out["estimated_minutes"] = round(est / 60, 1)
    try:  # refaire le plan sans l'IA garde les bandeaux déjà écrits (même voix off → même titre)
        with open(os.path.join(folder, "plan.json"), "r", encoding="utf-8") as f:
            old = json.load(f)
        heads = {x["text"]: x["headline"] for x in old.get("segments", []) if x.get("headline")}
        for x in segs:
            if x["type"] == "narration" and heads.get(x["text"]):
                x["headline"] = heads[x["text"]]
        if old.get("ticker"):
            out["ticker"] = old["ticker"]
    except (OSError, ValueError):
        pass
    with open(os.path.join(folder, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"plan : {len(segs)} segments, ~{out['estimated_minutes']} min, {len(titles)} titres")
    return out
