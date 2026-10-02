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
        "brand": "CAGE REPORT", "handle": "",
        "accent": "#E10600", "accent2": "#FFD21F",
        "voice_provider": "algrow", "voice": "jvV8uNVYXJa37GHVtjXf",  # Joe Stokes, présentateur radio US
        "minutes": 18,
        "search": ["UFC news", "Dana White", "UFC interview"],
        "sources": ["@UFC", "@MMAFightingonSBN", "@MMAjunkie", "@arielhelwanishow", "@ChaelSonnen",
                    "@DanielCormier", "@FullSendMMA", "@JREClips", "@FLAGRANTCLIPS", "@MikeBispingOfficial",
                    "@LukeThomas", "@TheSchmo312", "@JAXXONPODCAST", "@BrendanSchaub"],
        "people": "fighters, coaches, managers, promoters and pundits",
    },
    "boxing_en": {
        "name": "Boxing news", "sport": "Boxing", "language": "en",
        "brand": "RING REPORT", "handle": "",
        "accent": "#D4A017", "accent2": "#FFFFFF",
        "voice_provider": "algrow", "voice": "jvV8uNVYXJa37GHVtjXf",
        "minutes": 18,
        "search": ["boxing news", "boxing interview", "boxing press conference"],
        "sources": ["@MatchroomBoxing", "@TopRank", "@IFLTV", "@FightHubTV", "@Seconds_Out", "@DAZNBoxing",
                    "@BoxingSocial", "@QueensberryPromotions"],
        "people": "boxers, trainers, promoters and pundits",
    },
    "football_en": {
        "name": "Football news", "sport": "Football (soccer)", "language": "en",
        "brand": "PITCH REPORT", "handle": "",
        "accent": "#1DB954", "accent2": "#FFFFFF",
        "voice_provider": "algrow", "voice": "jvV8uNVYXJa37GHVtjXf",
        "minutes": 18,
        "search": ["press conference football", "Premier League press conference", "football interview"],
        "sources": ["@SkySportsFootball", "@footballdaily", "@TNTSportsFootball", "@BBCSport", "@ESPNFC",
                    "@TheOverlap", "@RioFerdinandPresents"],
        "people": "players, managers, agents and pundits",
    },
}

NARRATION_STYLE = """THE NARRATOR (copied from the reference channel, Fight Night MMA):
- Every narration block is TWO sentences, 25-45 words, about 11 seconds. Third person, present tense, neutral
  news register. It names the next speaker in full, says what they talk about, and hands over to the clip.
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
    if shutil.which("deno"):
        return []
    if shutil.which("node"):
        return ["--js-runtimes", "node"]
    return []


def video_info(video_id):
    """Titre, chaîne, date de sortie, durée (yt-dlp, sur PC)."""
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-j", "--skip-download", *yt_js_args(),
                        f"https://www.youtube.com/watch?v={video_id}"], capture_output=True, text=True, timeout=180)
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


def save_source(folder, meta, lines):
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
                          "quote": str(m.get("quote") or "").strip(), "heat": int(m.get("heat") or 0)})
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
        rows.append(f"M{k} | {m['speaker'] or 'unknown'}{'' if m['sure'] else ' (not sure)'} | {dur:.0f}s | heat "
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
2. "blocks": the body, {max(10, target * 60 // 55)}-{max(14, target * 60 // 45)} blocks in story order: each is one
   narration block then one moment. A moment can appear in the cold open AND later in full. Group by storyline
   (e.g. 1. the money and the refusal, 2. the other side answers, 3. what comes next). Prefer moments where the
   speaker is sure. Never use a "not sure" speaker's name in the narration (say "the host", "his coach"…).
   Total length ≈ {target} minutes (narration ~11 s per block + clip durations).
3. Narration of each block: follow THE NARRATOR rules below. The narration only introduces what the clip says,
   it never contradicts or exaggerates it.
4. "outro": the last narration block (no clip after it).
5. "titles": 5 options in the channel's style: a SHORT verbatim quote in quotes + CAPS verbs, e.g.
   “YOU GOT HUMILIATED!” Justin Gaethje DESTROYS Ilia Topuria For Demanding Rematch!
   Light clickbait only: the quoted part MUST be said (nearly word for word) in one of the clips you used, and
   the rest must be true. Put the best first. 70-100 characters.
6. "thumb": {{"text": 2-6 words, a real quote from a used clip (caps, may censor swear words like FU**ING),
   "highlight": the 1-2 words to color, "people": [the 2 main people, full names], "moment": id of the clip the
   quote comes from}}.
7. "description" (3 short paragraphs, factual, credits the sources by channel name at the end: "Credits:
   ..."), "tags" (15-25), "pinned_comment" (a question to the viewers).
8. "spelling": a map of caption misspellings → correct spelling for every name seen in the moments
   (e.g. {{"Gachi": "Gaethje", "Tapura": "Topuria"}}).

{NARRATION_STYLE}

Return JSON:
{{"titles": [...], "thumb": {{...}}, "cold_open": [{{"moment": "M3"}}, {{"moment": "M7", "trim": [120, 131]}}],
  "blocks": [{{"narration": "...", "moment": "M2"}}], "outro": "...", "description": "...", "tags": [...],
  "pinned_comment": "...", "spelling": {{...}}}}"""
    plan = ai.chat_json(prompt, model=ai.text_model(), timeout=420)
    return materialize(folder, ch, topic, plan, moms, by_id, log=log)


def _mid(x):
    m = re.match(r"^\s*M?(\d+)\s*$", str(x or ""))
    return int(m.group(1)) if m else None


def _fix_spelling(text, spelling):
    for wrong, right in (spelling or {}).items():
        if wrong and right and wrong.lower() != right.lower():
            text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.I)
    return text


def clip_spec(src, a, b, spelling, pad_in=0.15, pad_out=0.35):
    """Extrait = lignes a..b de la source → {video, start, end, subs: [{s, e, t}] relatifs au début}."""
    lines = src["lines"]
    start = max(0.0, lines[a]["s"] - pad_in)
    end = lines[b]["e"] + pad_out
    subs = []
    for ln in lines[a:b + 1]:
        s, e = max(0.0, ln["s"] - start), max(0.0, ln["e"] - start)
        subs.append({"s": round(s, 2), "e": round(min(e, end - start), 2), "t": _fix_spelling(ln["t"], spelling)})
    return {"video": src["id"], "start": round(start, 2), "end": round(end, 2),
            "credit": ("@" + src["handle"].lstrip("@")) if src.get("handle") else (src.get("channel") or ""), "channel": src.get("channel") or "",
            "subs": subs}


def materialize(folder, ch, topic, plan, moms, by_id, log=print):
    """Réponse de l'IA → plan.json vérifié (extraits réels, citations vraiment dites)."""
    spelling = plan.get("spelling") or {}

    def moment(ref):
        k = _mid(ref)
        return moms[k] if k is not None and 0 <= k < len(moms) else None

    segs = []
    for c in plan.get("cold_open") or []:
        m = moment(c.get("moment"))
        if not m:
            continue
        a, b = m["a"], m["b"]
        tr = c.get("trim")
        if isinstance(tr, list) and len(tr) == 2:
            try:
                ta, tb = int(tr[0]), int(tr[1])
                if m["a"] <= ta <= tb <= m["b"]:
                    a, b = ta, tb
            except (TypeError, ValueError):
                pass
        segs.append(dict(clip_spec(by_id[m["source"]], a, b, spelling), type="clip", full=True,
                         speaker=m["speaker"] if m["sure"] else ""))
    for blk in plan.get("blocks") or []:
        m = moment(blk.get("moment"))
        nar = re.sub(r"\s+", " ", str(blk.get("narration") or "")).strip()
        if not m:
            log(f"bloc sans extrait ignoré : {nar[:60]}")
            continue
        if nar:
            segs.append({"type": "narration", "text": nar, "next_video": m["source"]})
        segs.append(dict(clip_spec(by_id[m["source"]], m["a"], m["b"], spelling), type="clip", full=False,
                         speaker=m["speaker"] if m["sure"] else ""))
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
           "topic": topic, "voice": {"provider": ch.get("voice_provider", "algrow"), "id": ch["voice"]},
           "titles": titles, "title": titles[0] if titles else "", "thumb": thumb,
           "description": plan.get("description") or "", "tags": plan.get("tags") or [],
           "pinned_comment": plan.get("pinned_comment") or "", "spelling": spelling, "segments": segs}
    est = sum((s["end"] - s["start"]) if s["type"] == "clip" else len(s["text"].split()) / 2.9 for s in segs)
    out["estimated_minutes"] = round(est / 60, 1)
    with open(os.path.join(folder, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"plan : {len(segs)} segments, ~{out['estimated_minutes']} min, {len(titles)} titres")
    return out
