"""Orchestration de 2D Videos : chaîne → script → voix → storyboard → montage.

Chaque étape est un job de fond (services.pov_store.start_job) qui met à jour le
projet sur disque : l'UI n'a qu'à relire le projet pour suivre l'avancement.
"""
import hashlib
import io
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import ai, media, render, tts
from services import pov_script as S
from services import pov_store as store

# ── Styles visuels (issus de l'étude NexLev des chaînes 2D qui percent) ─────

STYLE_PRESETS = {
    "rank_vector": {
        "name": "Cartoon vectoriel sérieux (POVrank / Every Rank)",
        "prompt": "2D vector cartoon illustration, medium-weight clean black outlines, flat colors with simple "
                  "cel-shading (one shadow tone), muted olive / grey / brown palette with a few saturated accents, "
                  "characters with slightly large heads and simple faces (dot eyes, small nose, expressive brows), "
                  "detailed but clean backgrounds, cinematic framing and lighting, serious documentary mood.",
    },
    "ink_stick": {
        "name": "Bonhomme bâton minimal (Ink Explainer)",
        "prompt": "Minimalist 2D vector illustration, thick clean black outlines, flat earth-tone colors (ochre, sand, "
                  "olive, terracotta, muted blue), simple stick-figure characters with a large round white head, dot "
                  "eyes and a small expressive mouth, sparse background with only the essential props, generous empty "
                  "space, educational infographic feel, no gradients, no textures.",
    },
    "finance_cartoon": {
        "name": "Cartoon doux quotidien (finance POV)",
        "prompt": "Clean 2D vector cartoon, thick smooth outlines, flat muted colors with soft cel-shading, friendly "
                  "characters with dot eyes and rounded shapes, modern everyday settings (apartments, offices, stores, "
                  "streets), warm soft lighting, calm and relatable mood.",
    },
    "history_bold": {
        "name": "Cartoon historique coloré (Animated History)",
        "prompt": "Bold 2D cartoon illustration, thick black outlines, vivid saturated colors, caricatured characters "
                  "with big expressive faces, subtle paper texture, historical settings drawn with humor and very clear "
                  "silhouettes, readable at a glance.",
    },
    "dark_graphic": {
        "name": "Roman graphique sombre (survie / histoire)",
        "prompt": "2D illustrated graphic-novel style, confident ink outlines, flat colors with dramatic cel-shading, "
                  "desaturated palette with warm amber candle / fire light accents, expressive characters, gritty "
                  "historical atmosphere, cinematic composition.",
    },
    "muted_cinematic": {
        "name": "2D cinématique désaturé (ancien POV Studio)",
        "prompt": "2D digital cartoon animation, flat shading, clean vector-like lines, desaturated muted tones (greys, "
                  "slate blues, cool neutrals), dramatic cinematic lighting (spotlights, harsh fluorescents, window "
                  "light shafts), melancholic and tense mood, cinematic framing.",
    },
}

DEFAULT_CAPTIONS = {"mode": "karaoke", "font": "Poppins ExtraBold", "size": 64, "color": "#FFFFFF",
                    "highlight": "#FFD60A", "outline": "#000000", "position": "bottom", "uppercase": False}

DEFAULT_MONTAGE = {"pacing": 5.0, "hook_pacing": 3.0, "hook_seconds": 30, "min_scene": 1.6, "max_scene": 9.0,
                   "motion": "auto", "motion_strength": 0.12, "transition": "fade", "transition_dur": 0.3,
                   "captions": DEFAULT_CAPTIONS, "section_titles": True, "music": "", "music_volume": 0.12,
                   "fps": 30, "quality": "fast", "aspect": "16:9", "pause_max": 0.45}

DEFAULT_VOICE = {"provider": "edge", "voice": "", "speed": 1.0, "pitch": 0, "model": "", "instructions": ""}

DEFAULT_VOICE_BY_LANG = {"fr": "fr-FR-RemyMultilingualNeural", "en": "en-US-AndrewMultilingualNeural",
                         "es": "es-ES-AlvaroNeural", "de": "de-DE-ConradNeural", "pt": "pt-BR-AntonioNeural",
                         "it": "it-IT-DiegoNeural"}

# Modèles de chaîne prêts à l'emploi (format + style + voix + rythme), à dupliquer.
TEMPLATES = {
    "every_rank_en": {
        "name": "Every Rank (EN)", "language": "en", "format": "pov_levels",
        "niche": "Your life at every rank / level of a hierarchy (military, jobs, organizations, crime, institutions)",
        "audience": "18-45, curious men and women who love insider details about how systems really work",
        "tone": "Serious, grounded, documentary narrator speaking to 'you'. Dark but factual. Calm authority, no hype.",
        "rules": "Every level must contain one real insider detail (slang, pay, procedure, odds). Keep the same protagonist the whole video.",
        "style": "rank_vector", "voice": "en-US-ChristopherNeural", "wpm": 140,
        "montage": {"pacing": 4.6, "hook_pacing": 3.0, "captions": {"mode": "phrase"}},
        "character": ("You", "the protagonist ('you'): average build, short dark hair, neutral face; same face in every "
                             "image, age and uniform/outfit change with the level"),
    },
    "ancient_life_en": {
        "name": "Ancient Life stick-figure (EN)", "language": "en", "format": "ancient_life",
        "niche": "How ancient / prehistoric humans actually lived (daily life, health, food, work)",
        "audience": "Curious adults 18-54 who like history explained simply and visually",
        "tone": "Direct, punchy, a bit funny, speaks to 'you'. Short sentences.",
        "rules": "Always ground claims in archaeology (name the evidence). Contrast with modern life often.",
        "style": "ink_stick", "voice": "en-US-AndrewMultilingualNeural", "wpm": 155,
        "montage": {"pacing": 2.4, "hook_pacing": 2.0, "motion_strength": 0.08, "captions": {"mode": "karaoke", "uppercase": True}},
        "character": None,
    },
    "your_life_if_fr": {
        "name": "Ta vie si… — finance (FR)", "language": "fr", "format": "your_life_if",
        "niche": "Finances personnelles racontées en POV (épargne, investissement, immobilier, retraite, en France)",
        "audience": "20-40 ans en France qui veulent mieux gérer leur argent",
        "tone": "Narrateur calme et concret qui tutoie le spectateur. Chiffres réalistes pour la France (Livret A, PEA, ETF, SMIC, loyers).",
        "rules": "Jamais de conseil personnalisé. Chiffres cohérents et plausibles. Toujours comparer deux trajectoires.",
        "style": "finance_cartoon", "voice": "fr-FR-RemyMultilingualNeural", "wpm": 145,
        "montage": {"pacing": 5.2, "hook_pacing": 3.5},
        "character": ("Toi", "le protagoniste (« toi ») : silhouette moyenne, cheveux châtains courts, sweat gris ; "
                             "même visage dans toutes les images, il vieillit de 25 à 65 ans"),
    },
    "survie_fr": {
        "name": "Tu ne survivrais pas… (FR)", "language": "fr", "format": "survival",
        "niche": "Immersion historique : pourquoi vous ne survivriez pas à une époque, un métier, un lieu",
        "audience": "Adultes curieux 18-54 ans passionnés d'histoire",
        "tone": "Immersif, vouvoiement (« imaginez… vous êtes… »), détails sensoriels, humour noir léger.",
        "rules": "Un danger par chapitre, basé sur des faits historiques vérifiables. Tenir un « compteur de survie ».",
        "style": "dark_graphic", "voice": "fr-FR-HenriNeural", "wpm": 150,
        "montage": {"pacing": 4.0, "hook_pacing": 3.0},
        "character": ("Vous", "le spectateur projeté dans le passé : homme ordinaire, vêtements modernes au début puis "
                              "habits d'époque, même visage partout"),
    },
    "every_explained_en": {
        "name": "Every X Explained (EN)", "language": "en", "format": "every_explained",
        "niche": "Every X explained: places, eras, phenomena, objects — fast, witty lists",
        "audience": "Broad curious audience 16-44",
        "tone": "Witty, fast, confident narrator with dark humor asides.",
        "rules": "Steady rhythm, one hard number per item.",
        "style": "history_bold", "voice": "en-US-BrianMultilingualNeural", "wpm": 160,
        "montage": {"pacing": 3.8, "hook_pacing": 2.5},
        "character": None,
    },
}


def _merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


# ── Chaînes ─────────────────────────────────────────────────────────────────

def new_channel(data=None, template=None):
    data = data or {}
    t = TEMPLATES.get(template or "", {})
    lang = (data.get("language") or t.get("language") or "fr").lower()
    style_key = t.get("style", "rank_vector")
    ch = {
        "id": store.new_id("ch"), "created": store.now(), "updated": store.now(),
        "name": t.get("name", "Nouvelle chaîne"), "language": lang,
        "format": t.get("format", "pov_levels"), "niche": t.get("niche", ""), "audience": t.get("audience", ""),
        "tone": t.get("tone", ""), "rules": t.get("rules", ""), "cta": "", "reference_scripts": "",
        "reference_urls": "", "bible": "", "wpm": t.get("wpm", 150),
        "style": {"preset": style_key, "prompt": STYLE_PRESETS[style_key]["prompt"], "no_text": True,
                  "ref": None, "characters": []},
        "voice": _merge(DEFAULT_VOICE, {"voice": t.get("voice") or DEFAULT_VOICE_BY_LANG.get(lang, "")}),
        "montage": _merge(DEFAULT_MONTAGE, t.get("montage") or {}),
        "default_minutes": 10,
    }
    if t.get("character"):
        name, desc = t["character"]
        ch["style"]["characters"].append({"id": store.new_id("chr"), "name": name, "description": desc,
                                          "image": None, "always": True})
    ch = apply_channel_update(ch, data)
    store.save_channel(ch)
    return ch


_CH_FIELDS = ("name", "language", "format", "niche", "audience", "tone", "rules", "cta", "reference_scripts",
              "reference_urls", "bible", "wpm", "default_minutes")


def apply_channel_update(ch, data):
    for k in _CH_FIELDS:
        if k in data:
            ch[k] = data[k]
    if isinstance(data.get("style"), dict):
        st = data["style"]
        for k in ("preset", "prompt", "no_text"):
            if k in st:
                ch["style"][k] = st[k]
        if isinstance(st.get("characters"), list):  # nom/description/always (images gérées à part)
            by_id = {c["id"]: c for c in ch["style"]["characters"]}
            new_list = []
            for c in st["characters"]:
                cid = c.get("id")
                base = by_id.get(cid) or {"id": store.new_id("chr"), "image": None}
                base.update({"name": (c.get("name") or "").strip()[:60] or "Perso",
                             "description": (c.get("description") or "").strip()[:800],
                             "always": bool(c.get("always"))})
                new_list.append(base)
            ch["style"]["characters"] = new_list
    if isinstance(data.get("voice"), dict):
        ch["voice"] = _merge(ch.get("voice") or DEFAULT_VOICE, data["voice"])
    if isinstance(data.get("montage"), dict):
        ch["montage"] = _merge(ch.get("montage") or DEFAULT_MONTAGE, data["montage"])
    try:
        ch["wpm"] = max(90, min(220, int(float(ch.get("wpm") or 150))))
    except (TypeError, ValueError):
        ch["wpm"] = 150
    return ch


def channel_ref_path(ch, rel):
    return os.path.join(store.channel_dir(ch["id"]), rel) if rel else None


def save_channel_image(ch, blob, kind, char_id=None):
    """kind = 'style' | 'char'. Stocke en PNG borné (1536 px)."""
    from PIL import Image
    im = Image.open(io.BytesIO(blob))
    im = im.convert("RGB")
    im.thumbnail((1536, 1536))
    os.makedirs(os.path.join(store.channel_dir(ch["id"]), "refs"), exist_ok=True)
    stamp = int(time.time() * 1000)
    if kind == "style":
        rel = f"refs/style_{stamp}.png"
    else:
        rel = f"refs/{char_id}_{stamp}.png"
    im.save(os.path.join(store.channel_dir(ch["id"]), rel), "PNG", optimize=True)
    return rel


def describe_style(images):
    """Vision : décrit le style d'1 à 4 captures → prompt de direction artistique."""
    content = [{"type": "text", "text":
                "These are frames from a YouTube channel. Write ONE reusable art-direction prompt (60-110 words, "
                "English) that describes ONLY the visual style so an image model can reproduce it on any subject: "
                "rendering technique, line work, color palette, shading, character design (head/eyes/proportions), "
                "background density, lighting, mood. Do NOT describe the content of these particular frames. "
                "Output only the prompt."}]
    import base64
    for b in images[:4]:
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                                            base64.b64encode(_jpeg(b)).decode()}})
    return ai.chat([{"role": "user", "content": content}], model=ai.text_model(), timeout=180).strip()


def _jpeg(blob, side=1024):
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((side, side))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=88)
    return out.getvalue()


def fetch_transcripts(urls_text, limit=4):
    """Transcriptions YouTube (paquet optionnel youtube-transcript-api)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        raise RuntimeError("Installe youtube-transcript-api (pip) ou colle les scripts à la main.")
    ids = re.findall(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", urls_text or "")
    if not ids:
        ids = re.findall(r"\b([A-Za-z0-9_-]{11})\b", urls_text or "")
    api = YouTubeTranscriptApi()
    out, errors = [], []
    for vid in list(dict.fromkeys(ids))[:limit]:
        try:
            tr = api.fetch(vid, languages=["fr", "en", "es", "de", "pt", "it"])
            text = " ".join(s.text.replace("\n", " ") for s in tr.snippets)
            out.append(f"--- https://youtu.be/{vid} ---\n{text}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{vid}: {type(e).__name__}")
    if not out:
        raise RuntimeError("Aucune transcription récupérée (" + ", ".join(errors or ["lien invalide"]) +
                           "). YouTube bloque parfois : colle le script à la main.")
    return "\n\n".join(out), errors


def _style_parts(ch, scene_chars=None):
    """(préfixe de prompt, liste des images de référence) pour une génération."""
    st = ch.get("style") or {}
    refs, lines = [], []
    style_ref = channel_ref_path(ch, st.get("ref"))
    if style_ref and os.path.isfile(style_ref):
        refs.append(style_ref)
        lines.append(f"Reference image {len(refs)} = ART STYLE reference: copy its rendering, line work, color "
                     "palette and shading exactly. Ignore its content and composition.")
    for c in st.get("characters") or []:
        if scene_chars is not None and c["name"] not in scene_chars and not c.get("always"):
            continue
        p = channel_ref_path(ch, c.get("image"))
        if p and os.path.isfile(p):
            refs.append(p)
            lines.append(f"Reference image {len(refs)} = the character \"{c['name']}\": keep exactly the same face, "
                         "hair, body proportions and colors (outfit and age may change if the scene says so).")
    return lines, refs


def build_image_prompt(ch, scene_prompt, scene_chars=None, allow_text=False, vertical=False):
    st = ch.get("style") or {}
    lines, refs = _style_parts(ch, scene_chars)
    chars_desc = [f"{c['name']}: {c['description']}" for c in st.get("characters") or []
                  if c.get("description") and (scene_chars is None or c["name"] in scene_chars or c.get("always"))]
    parts = lines + ["SCENE: " + scene_prompt.strip()]
    if chars_desc:
        parts.append("CHARACTERS IN THIS IMAGE: " + " | ".join(chars_desc))
    parts.append("ART STYLE: " + (st.get("prompt") or "").strip())
    fmt = ("Tall 9:16 vertical frame, full-bleed illustration, main subject centered, no borders, no frame."
           if vertical else "Wide 16:9 landscape frame, full-bleed illustration, no borders, no frame.")
    if st.get("no_text", True) and not allow_text:
        fmt += " No text, no letters, no words, no captions, no signs with writing, no watermark, no logo."
    parts.append(fmt)
    return "\n".join(p for p in parts if p), refs


_MODERATION = ("safety", "moderation", "policy", "content_policy", "rejected", "not allowed", "violat")


def generate_scene_image(ch, prompt, dest, scene_chars=None, width=1920, height=1080):
    full, refs = build_image_prompt(ch, prompt, scene_chars, vertical=height > width)
    try:
        blob = ai.generate_image(full, width=width, height=height, refs=refs)
    except ai.AIError as e:
        if not any(m in str(e).lower() for m in _MODERATION):
            raise
        safe = ai.chat("Rewrite this image prompt so it passes strict image-safety filters while keeping the same "
                       "scene, meaning and composition (imply violence/danger instead of showing it; no gore, no "
                       "nudity, no real public figures). Output only the prompt.\n\n" + prompt,
                       model=ai.fast_model())
        full, refs = build_image_prompt(ch, safe, scene_chars, vertical=height > width)
        blob = ai.generate_image(full, width=width, height=height, refs=refs)
    ai.fit_cover(blob, width, height, dest)
    return dest


def character_sheet(ch, char):
    prompt = (f"Character reference sheet of \"{char['name']}\": {char.get('description', '')}. "
              "Full-body front view on the left and a 3/4 close-up portrait on the right, neutral pose, plain light "
              "background, clear readable design.")
    full, refs = build_image_prompt(ch, prompt, scene_chars=[])
    full = full.replace("Wide 16:9 landscape frame, full-bleed illustration, no borders, no frame.",
                        "Landscape frame, plain background.")
    blob = ai.generate_image(full, width=1536, height=1024, refs=refs)
    return blob


# ── Projets ─────────────────────────────────────────────────────────────────

def dims(pr):
    return (1080, 1920) if (pr.get("montage") or {}).get("aspect") == "9:16" else (1920, 1080)


def new_project(ch, title, minutes=None, notes=""):
    pr = {
        "id": store.new_id("pr"), "created": store.now(), "updated": store.now(),
        "channel_id": ch["id"], "title": (title or "").strip() or "Nouvelle vidéo",
        "minutes": float(minutes or ch.get("default_minutes") or 10), "notes": notes or "",
        "script": "", "outline": None, "review": None, "script_history": [],
        "voice": None, "scenes": [], "render": None, "metadata": None,
        "voice_settings": json.loads(json.dumps(ch.get("voice") or DEFAULT_VOICE)),
        "montage": json.loads(json.dumps(ch.get("montage") or DEFAULT_MONTAGE)),
    }
    os.makedirs(store.project_dir(pr["id"]), exist_ok=True)
    store.save_project(pr)
    return pr


def project_summary(pr):
    thumb = None
    for sc in pr.get("scenes") or []:
        if sc.get("image"):
            thumb = sc["image"]
            break
    job = store.running_job(pr["id"])
    return {"id": pr["id"], "title": pr.get("title"), "channel_id": pr.get("channel_id"),
            "updated": pr.get("updated"), "created": pr.get("created"),
            "minutes": pr.get("minutes"), "words": S.word_count(S.narration(pr.get("script") or "")),
            "duration": (pr.get("voice") or {}).get("duration"),
            "scenes": len(pr.get("scenes") or []),
            "images": sum(1 for s in pr.get("scenes") or [] if s.get("image")),
            "rendered": bool((pr.get("render") or {}).get("file")), "thumb": thumb,
            "job": job.as_dict() if job else None, "stage": stage(pr)}


def stage(pr):
    if (pr.get("render") or {}).get("file"):
        return "rendered"
    scenes = pr.get("scenes") or []
    if scenes and all(s.get("image") for s in scenes):
        return "storyboard"
    if pr.get("voice"):
        return "voice"
    if (pr.get("script") or "").strip():
        return "script"
    return "idea"


def push_history(pr, label):
    """Sauvegarde la version ACTUELLE avant une modification.

    Les éditions manuelles rapprochées (autosave) ne créent qu'une entrée : on garde
    l'état d'avant la session d'édition, pas une version par frappe."""
    if not (pr.get("script") or "").strip():
        return
    hist = pr.setdefault("script_history", [])
    if hist and hist[-1].get("script") == pr["script"]:
        return
    if label == "édition manuelle" and hist and hist[-1].get("label") == label:
        try:
            last = time.mktime(time.strptime(hist[-1]["at"], "%Y-%m-%dT%H:%M:%S"))
            if time.time() - last < 600:
                return
        except (KeyError, ValueError):
            pass
    hist.append({"at": store.now(), "label": label, "script": pr["script"]})
    del hist[:-20]


def voice_signature(pr):
    raw = json.dumps([S.narration(pr.get("script") or ""), pr.get("voice_settings"),
                      (pr.get("montage") or {}).get("pause_max")], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def voice_outdated(pr):
    v = pr.get("voice")
    return not v or v.get("sig") != voice_signature(pr)


# ── Jobs : script ───────────────────────────────────────────────────────────

def job_script(job, pid, polish=True):
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    if not ch:
        raise RuntimeError("Chaîne introuvable.")

    def prog(p, msg, partial):
        job.update(0.02 + 0.96 * p, msg)
        if partial:
            store.update_project(pid, lambda x: x.__setitem__("script_draft", partial))

    res = S.generate(ch, pr["title"], pr["minutes"], pr.get("notes") or "", polish=polish, progress=prog)

    def save(x):
        push_history(x, "avant régénération")
        x["script"] = res["script"]
        x["outline"] = res["outline"]
        x["review"] = res["review"]
        x.pop("script_draft", None)
        if res.get("title") and not x.get("title_locked"):
            x["title"] = res["title"]
    store.update_project(pid, save)
    job.update(1.0, f"Script prêt : {res['words']} mots (≈{res['words'] / max(1, ch.get('wpm', 150)):.1f} min).")


def job_rewrite(job, pid, instruction):
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    job.update(0.1, "Réécriture du script…")
    new = S.rewrite_selection(ch, pr.get("script") or "", instruction)
    if S.word_count(new) < 20:
        raise RuntimeError("Réécriture vide — réessaie.")

    def save(x):
        push_history(x, "avant réécriture : " + instruction[:60])
        x["script"] = new
    store.update_project(pid, save)
    job.update(1.0, "Script réécrit.")


# ── Jobs : voix ─────────────────────────────────────────────────────────────

def tighten_pauses(src, words, max_pause, dest):
    """Raccourcit les silences trop longs (> max_pause) et recale les timings.

    Découpe à l'ÉCHANTILLON près (WAV) — un filtre ffmpeg sur du MP3 coupe par
    trames de ~26 ms et ferait dériver sous-titres et coupes au fil de la vidéo."""
    import wave
    if not words or not max_pause or max_pause <= 0:
        return None
    sr = 44100
    wav_in, wav_out = dest + ".in.wav", dest + ".out.wav"
    media.run(["-i", src, "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", wav_in])
    try:
        with wave.open(wav_in, "rb") as wi:
            n_total = wi.getnframes()
            params = wi.getparams()
            cuts = []  # (début, fin) en échantillons, à supprimer
            lead = words[0]["s"]
            if lead > 0.25:
                cuts.append((0, int(round((lead - 0.2) * sr))))
            for x, y in zip(words, words[1:]):
                if y["s"] - x["e"] > max_pause:
                    c0 = int(round((x["e"] + max_pause / 2) * sr))
                    c1 = int(round((y["s"] - max_pause / 2) * sr))
                    if c1 > c0 and (not cuts or c0 >= cuts[-1][1]):
                        cuts.append((c0, min(c1, n_total)))
            if not cuts:
                return None
            with wave.open(wav_out, "wb") as wo:
                wo.setparams(params)
                pos = 0
                for c0, c1 in cuts + [(n_total, n_total)]:
                    if c0 > pos:
                        wi.setpos(pos)
                        wo.writeframes(wi.readframes(c0 - pos))
                    pos = max(pos, c1)
        media.run(["-i", wav_out, "-c:a", "libmp3lame", "-b:a", "192k", dest])
    finally:
        for f in (wav_in, wav_out):
            try:
                os.remove(f)
            except OSError:
                pass

    def remap(sec):
        x = sec * sr
        removed = 0
        for c0, c1 in cuts:
            if x >= c1:
                removed += c1 - c0
            elif x > c0:
                return (c0 - removed) / sr
        return (x - removed) / sr
    return [{"w": w["w"], "s": round(remap(w["s"]), 3), "e": round(remap(w["e"]), 3), "t": w.get("t", 0)}
            for w in words]


def job_voice(job, pid):
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    text = S.narration(pr.get("script") or "")
    if S.word_count(text) < 5:
        raise RuntimeError("Le script est vide.")
    vs = pr.get("voice_settings") or DEFAULT_VOICE
    d = store.project_dir(pid)
    raw = os.path.join(d, "voice_raw.mp3")
    job.update(0.02, "Synthèse de la voix off…")

    def prog(i, n):
        job.update(0.02 + 0.8 * i / max(1, n), f"Voix off {min(i + 1, n)}/{n}…")
    provider = vs.get("provider", "edge")
    voice = vs.get("voice") or (DEFAULT_VOICE_BY_LANG.get(ch.get("language", "fr"), "") if provider == "edge" else "")
    res = tts.synthesize(text, raw, provider=provider, voice=voice,
                         speed=vs.get("speed", 1.0), pitch=vs.get("pitch", 0), model=vs.get("model", ""),
                         instructions=vs.get("instructions", ""), progress=prog)
    words = res["words"]
    stamp = int(time.time())
    vname = f"voice_{stamp}.mp3"  # nom versionné : sous Windows on ne peut pas écraser un fichier en lecture
    final = os.path.join(d, vname)
    pause = float((pr.get("montage") or {}).get("pause_max") or 0)
    job.update(0.85, "Nettoyage des silences…")
    tight = tighten_pauses(raw, words, pause, final) if pause > 0 else None
    if tight:
        words = tight
    else:
        os.replace(raw, final)
    if os.path.exists(raw):
        os.remove(raw)
    duration = media.duration(final)
    with open(os.path.join(d, "words.json"), "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    sections = section_ranges(pr.get("script") or "")  # le script RÉELLEMENT lu (pas une version éditée après)
    with open(os.path.join(d, "sections.json"), "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False)
    sig = voice_signature(pr)

    old_voice = (pr.get("voice") or {}).get("file")

    def save(x):
        x["voice"] = {"file": vname, "v": stamp, "duration": round(duration, 3),
                      "words": len(words), "sig": sig}
        x["render"] = None
        _replan(x, words, duration, sections)
    store.update_project(pid, save)
    _remove_quiet(d, old_voice if old_voice != vname else None)
    # calibration du débit réel de la voix de la chaîne (sert à viser la bonne durée)
    n = S.word_count(text)
    if n > 120 and duration > 20:
        measured = n / (duration / 60.0)
        ch = store.get_channel(pr["channel_id"])
        if ch:
            ch["wpm"] = int(round(0.5 * float(ch.get("wpm") or measured) + 0.5 * measured))
            store.save_channel(ch)
    job.update(1.0, f"Voix off prête : {duration / 60:.1f} min.")


def _remove_quiet(folder, rel):
    """Supprime un ancien fichier ; ignoré s'il est encore ouvert (lecteur du navigateur sous Windows)."""
    if not rel:
        return
    try:
        os.remove(os.path.join(folder, rel))
    except OSError:
        pass


def load_words(pid):
    p = os.path.join(store.project_dir(pid), "words.json")
    if not os.path.isfile(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Découpage en scènes ─────────────────────────────────────────────────────

def section_ranges(script_text):
    """[(heading, token_start, token_end)] sur le texte de narration normalisé."""
    out, t = [], 0
    for h, txt in S.parse(script_text):
        n = len(re.sub(r"\s+", " ", txt).strip().split())
        out.append((h, t, t + n))
        t += n
    return out


def plan_scenes(words, total, sections, m):
    pacing = float(m.get("pacing") or 5)
    hook_pacing = float(m.get("hook_pacing") or pacing)
    hook_s = float(m.get("hook_seconds") or 0)
    mn = float(m.get("min_scene") or 1.5)
    mx = max(mn + 0.5, float(m.get("max_scene") or 9))

    def sec_of(t_idx):
        for i, (_, a, b) in enumerate(sections):
            if a <= t_idx < b:
                return i
        return len(sections) - 1 if sections else 0

    # 1) unités = phrases (coupées aux fins de phrase ET aux changements de section)
    units, cur = [], []
    for w in words:
        if cur and sec_of(w.get("t", 0)) != sec_of(cur[-1].get("t", 0)):
            units.append(cur)
            cur = []
        cur.append(w)
        if w["w"][-1:] in ".!?…":
            units.append(cur)
            cur = []
    if cur:
        units.append(cur)

    def target_at(t):
        return hook_pacing if t < hook_s else pacing

    # 2) phrases trop longues pour le rythme → coupées (virgules de préférence)
    fine = []
    for u in units:
        dur = u[-1]["e"] - u[0]["s"]
        tgt = target_at(u[0]["s"])
        limit = min(mx, max(tgt * 1.6, mn * 2))
        if dur <= limit or len(u) < 4:
            fine.append(u)
            continue
        parts = max(2, round(dur / tgt))
        per = dur / parts
        piece, start = [], u[0]["s"]
        for i, w in enumerate(u):
            piece.append(w)
            left = len(u) - i - 1
            long_enough = (w["e"] - start) >= per * (0.75 if w["w"][-1:] in ",;:" else 1.0)
            if long_enough and left >= 2:
                fine.append(piece)
                piece = []
                start = w["e"]
        if piece:
            if fine and len(piece) < 2:
                fine[-1].extend(piece)
            else:
                fine.append(piece)

    # 3) regroupement glouton vers la cible, sans traverser une section
    scenes, grp = [], []
    for u in fine:
        if grp:
            same_sec = sec_of(u[0].get("t", 0)) == sec_of(grp[0][0].get("t", 0))
            span = u[-1]["e"] - grp[0][0]["s"]
            if same_sec and span <= target_at(grp[0][0]["s"]) * 1.15:
                grp.append(u)
                continue
            scenes.append(grp)
        grp = [u]
    if grp:
        scenes.append(grp)

    out = []
    for g in scenes:
        ws = [w for u in g for w in u]
        out.append({"start": ws[0]["s"], "text": " ".join(w["w"] for w in ws), "section": sec_of(ws[0].get("t", 0))})
    if not out:
        return []
    out[0]["start"] = 0.0
    # 4) fusion des scènes trop courtes (dans la même section)
    i = 0
    while i < len(out):
        end = out[i + 1]["start"] if i + 1 < len(out) else total
        if end - out[i]["start"] < mn and len(out) > 1:
            if i + 1 < len(out) and out[i + 1]["section"] == out[i]["section"]:
                out[i]["text"] += " " + out[i + 1]["text"]
                out.pop(i + 1)
                continue
            if i > 0 and out[i - 1]["section"] == out[i]["section"]:
                out[i - 1]["text"] += " " + out[i]["text"]
                out.pop(i)
                continue
        i += 1
    for i, sc in enumerate(out):
        sc["end"] = out[i + 1]["start"] if i + 1 < len(out) else total
        sc["start"] = round(sc["start"], 3)
        sc["end"] = round(sc["end"], 3)
        sc["heading"] = sections[sc["section"]][0] if sections else ""
        sc["first"] = i == 0 or out[i - 1]["section"] != sc["section"]
    return out


def load_sections(pid):
    p = os.path.join(store.project_dir(pid), "sections.json")
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return [tuple(x) for x in json.load(f)]


def _replan(pr, words, duration, sections=None):
    """Recalcule les scènes après une nouvelle voix. Garde image+prompt des scènes au texte identique."""
    old = {(_norm(s.get("text"))): s for s in pr.get("scenes") or []}
    if sections is None:
        sections = load_sections(pr["id"]) or section_ranges(pr.get("script") or "")
    new = plan_scenes(words, duration, sections, pr.get("montage") or DEFAULT_MONTAGE)
    scenes = []
    for i, sc in enumerate(new):
        prev = old.get(_norm(sc["text"]))
        scenes.append({"i": i, "start": sc["start"], "end": sc["end"], "text": sc["text"],
                       "section": sc["section"], "heading": sc["heading"], "first": sc["first"],
                       "prompt": (prev or {}).get("prompt", ""), "chars": (prev or {}).get("chars"),
                       "image": (prev or {}).get("image"), "motion": (prev or {}).get("motion"),
                       "status": "done" if (prev or {}).get("image") else "pending", "error": None})
    pr["scenes"] = scenes


def _norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def job_replan(job, pid):
    pr = store.get_project(pid)
    if not pr.get("voice"):
        raise RuntimeError("Génère la voix off d'abord.")
    words = load_words(pid)
    store.update_project(pid, lambda x: _replan(x, words, x["voice"]["duration"]))
    job.update(1.0, "Scènes recalculées.")


# ── Prompts d'images ────────────────────────────────────────────────────────

def _prompt_batch(ch, pr, scenes, all_scenes):
    chars = (ch.get("style") or {}).get("characters") or []
    roster = "\n".join(f"- {c['name']}: {c.get('description', '')}" for c in chars) or "- (no recurring character)"
    heads = [h for h, _ in S.parse(pr.get("script") or "") if h]
    lines = []
    for sc in scenes:
        prev = all_scenes[sc["i"] - 1]["text"] if sc["i"] > 0 else ""
        lines.append(f"#{sc['i']} [section: {sc.get('heading') or 'hook'}] (prev: \"{prev[-120:]}\") "
                     f"NARRATION: \"{sc['text']}\"")
    prompt = f"""You are the art director of a faceless 2D YouTube channel. For each scene below, write the image prompt of the illustration shown while this narration is spoken.

VIDEO: {pr['title']}
CHAPTERS: {' | '.join(heads) if heads else '-'}
ART STYLE (added automatically, do not repeat it): {(ch.get('style') or {}).get('prompt', '')[:400]}
RECURRING CHARACTERS (use their exact name when they appear; mention age/outfit/rank if the narration implies it):
{roster}

RULES:
- Show the exact moment/idea the narration describes, literally and concretely: subject + action + setting + key props. One clear focal point, readable in 1 second.
- If the narration talks to "you"/"tu"/"vous" and a protagonist character exists, show that character doing it.
- Vary the camera across consecutive scenes (wide establishing, medium, close-up on hands/face/object, over-the-shoulder, top-down, low angle). Never the same framing twice in a row.
- Stay historically / technically accurate (uniforms, tools, places, era).
- For violence, death or danger: imply it (shadows, aftermath, expressions), never gore. No real celebrities.
- No text or letters in the image. 25-60 words per prompt, English.

SCENES:
{chr(10).join(lines)}

Return JSON: {{"prompts": [{{"i": <scene number>, "prompt": "...", "chars": ["names of recurring characters visible, or empty"]}}]}}"""
    data = ai.chat_json(prompt, model=ai.fast_model(), timeout=240)
    out = {}
    for p in data.get("prompts") or []:
        try:
            out[int(p.get("i"))] = (str(p.get("prompt") or "").strip(), [str(c) for c in (p.get("chars") or [])])
        except (TypeError, ValueError):
            continue
    return out


def ensure_prompts(job, pid, p0=0.0, p1=0.2):
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    todo = [s for s in pr["scenes"] if not (s.get("prompt") or "").strip()]
    if not todo:
        return
    batches = [todo[i:i + 12] for i in range(0, len(todo), 12)]
    done = 0
    results = {}
    ex = ThreadPoolExecutor(max_workers=4)
    try:
        futs = [ex.submit(_prompt_batch, ch, pr, b, pr["scenes"]) for b in batches]
        for fut in as_completed(futs):
            results.update(fut.result())
            done += 1
            job.update(p0 + (p1 - p0) * done / len(batches), f"Prompts d'images {done}/{len(batches)}…")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    def save(x):
        for s in x["scenes"]:
            if not (s.get("prompt") or "").strip():
                prm, chars = results.get(s["i"], ("", []))
                s["prompt"] = prm or f"Illustration of: {s['text'][:200]}"
                s["chars"] = chars
    store.update_project(pid, save)


# ── Images ──────────────────────────────────────────────────────────────────

def _image_workers():
    try:
        return max(1, min(16, int(os.getenv("AI_IMAGE_CONCURRENCY", "6"))))
    except ValueError:
        return 6


def _gen_scene(ch, pr, sc):
    w, h = dims(pr)
    d = store.project_dir(pr["id"])
    rel = f"images/scene_{sc['i']:04d}_{int(time.time() * 1000) % 10**9}.jpg"
    generate_scene_image(ch, sc["prompt"], os.path.join(d, rel), scene_chars=sc.get("chars"), width=w, height=h)
    return rel


def job_images(job, pid, only=None, first_only=False):
    """Génère les images manquantes (ou `only` = liste d'indices à (re)faire)."""
    job.update(0.01, "Préparation du storyboard…")
    pr = store.get_project(pid)
    if not pr.get("scenes"):
        raise RuntimeError("Aucune scène : génère la voix off d'abord.")
    ensure_prompts(job, pid, 0.01, 0.12)
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    if only is not None:
        targets = [s for s in pr["scenes"] if s["i"] in set(only)]
    else:
        targets = [s for s in pr["scenes"] if not s.get("image")]
    if first_only:
        targets = targets[:1]
    if not targets:
        job.update(1.0, "Toutes les images sont déjà prêtes.")
        return
    total, done, failed = len(targets), 0, 0
    old_files = []

    def mark(i, **kw):
        def f(x):
            for s in x["scenes"]:
                if s["i"] == i:
                    if kw.get("image") and s.get("image"):
                        old_files.append(s["image"])
                    s.update(kw)
        store.update_project(pid, f)

    for s in targets:
        mark(s["i"], status="queued", error=None)
    job.update(0.12, f"Génération de {total} image(s)…")
    ex = ThreadPoolExecutor(max_workers=_image_workers())
    try:
        futs = {ex.submit(_gen_scene, ch, pr, s): s for s in targets}
        for fut in as_completed(futs):
            s = futs[fut]
            try:
                rel = fut.result()
                mark(s["i"], image=rel, status="done", error=None)
                done += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                mark(s["i"], status="error", error=str(e)[:300])
            job.update(0.12 + 0.88 * (done + failed) / total,
                       f"Images {done}/{total}" + (f" · {failed} en échec" if failed else ""))
    except store.JobCancelled:
        def reset(x):  # les scènes jamais lancées repassent « en attente »
            for sc in x["scenes"]:
                if sc.get("status") == "queued":
                    sc["status"] = "done" if sc.get("image") else "pending"
        store.update_project(pid, reset)
        raise
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    for rel in old_files:  # anciennes versions remplacées
        try:
            os.remove(os.path.join(store.project_dir(pid), rel))
        except OSError:
            pass
    store.update_project(pid, lambda x: x.__setitem__("render", None))
    if failed:
        raise RuntimeError(f"{failed} image(s) en échec — clique « Relancer les échecs ».")
    job.update(1.0, f"{done} image(s) prêtes.")


def job_regen(job, pid, idx, prompt=None):
    if prompt is not None:
        def f(x):
            for s in x["scenes"]:
                if s["i"] == idx:
                    s["prompt"] = prompt.strip()
        store.update_project(pid, f)
    job_images(job, pid, only=[idx])


# ── Montage ─────────────────────────────────────────────────────────────────

def job_render(job, pid):
    pr = store.get_project(pid)
    if not pr.get("voice"):
        raise RuntimeError("Pas de voix off.")
    missing = [s["i"] for s in pr["scenes"] if not s.get("image")]
    if missing:
        raise RuntimeError(f"{len(missing)} scène(s) sans image.")
    d = store.project_dir(pid)
    m = pr.get("montage") or DEFAULT_MONTAGE
    w, h = dims(pr)
    scenes = [{"image": os.path.join(d, s["image"]), "start": s["start"], "motion": s.get("motion"),
               "index": s["i"]} for s in pr["scenes"]]
    overlays = []
    if m.get("section_titles", True):
        for s in pr["scenes"]:
            if s.get("first") and s.get("heading"):
                overlays.append({"start": s["start"] + 0.15, "end": min(s["end"], s["start"] + 2.6) if
                                 s["end"] - s["start"] > 1.2 else s["start"] + 2.2, "text": s["heading"]})
    music = store.music_path(m.get("music")) if m.get("music") else None
    out_name = f"{render.safe_name(pr.get('title'))}_{int(time.time()) % 1000000}.mp4"
    try:
        res = render.render_video(
            os.path.join(d, "render"), scenes, os.path.join(d, pr["voice"]["file"]), os.path.join(d, out_name),
            width=w, height=h, fps=int(m.get("fps") or 30), motion=m.get("motion", "auto"),
            motion_strength=float(m.get("motion_strength") or 0.12), transition=m.get("transition", "fade"),
            transition_dur=float(m.get("transition_dur") or 0.3), words=load_words(pid),
            captions=m.get("captions") or {"mode": "none"}, overlays=overlays, music_path=music,
            music_volume=float(m.get("music_volume") or 0.12), quality=m.get("quality", "fast"),
            progress=lambda p, msg: job.update(p * 0.98, msg), cancelled=job.cancelled)
    except render.Cancelled:
        raise store.JobCancelled("Annulé.")
    old = (pr.get("render") or {}).get("file")

    def save(x):
        x["render"] = {"file": out_name, "v": int(time.time()), "duration": res["duration"], "at": store.now()}
    store.update_project(pid, save)
    _remove_quiet(d, old if old != out_name else None)
    job.update(1.0, "Vidéo exportée.")


def job_pack(job, pid, motion="none"):
    """Pack montage : 1 clip MP4 par image, calé sur la voix off (+ voix, SRT, timestamps)."""
    pr = store.get_project(pid)
    if not pr.get("voice"):
        raise RuntimeError("Pas de voix off.")
    missing = [s["i"] for s in pr["scenes"] if not s.get("image")]
    if missing:
        raise RuntimeError(f"{len(missing)} scène(s) sans image.")
    d = store.project_dir(pid)
    m = pr.get("montage") or DEFAULT_MONTAGE
    w, h = dims(pr)
    scenes = [{"image": os.path.join(d, s["image"]), "start": s["start"], "text": s["text"]} for s in pr["scenes"]]
    name = f"{render.safe_name(pr.get('title'))}_pack_montage_{int(time.time()) % 1000000}.zip"
    try:
        res = _pack_call(d, scenes, pr, w, h, m, motion, pid, job, name)
    except render.Cancelled:
        raise store.JobCancelled("Annulé.")
    old = (pr.get("pack") or {}).get("file")

    def save(x):
        x["pack"] = {"file": name, "v": int(time.time()), "clips": res["clips"], "motion": motion,
                     "at": store.now()}
    store.update_project(pid, save)
    _remove_quiet(d, old if old != name else None)
    job.update(1.0, f"Pack montage prêt : {res['clips']} clips.")


def _pack_call(d, scenes, pr, w, h, m, motion, pid, job, name):
    return render.export_pack(os.path.join(d, "render"), scenes, os.path.join(d, pr["voice"]["file"]),
                             os.path.join(d, name), width=w, height=h, fps=int(m.get("fps") or 30),
                             motion=motion or "none", motion_strength=float(m.get("motion_strength") or 0.1),
                             words=load_words(pid), script_text=pr.get("script") or "", title=pr.get("title", ""),
                             progress=lambda p, msg: job.update(p * 0.99, msg), cancelled=job.cancelled)


def job_thumbnails(job, pid, idea="", count=2):
    """Miniatures YouTube (style + perso de la chaîne, gros texte court)."""
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    count = max(1, min(4, int(count or 2)))
    job.update(0.05, "Concepts de miniatures…")
    chars = [c["name"] for c in (ch.get("style") or {}).get("characters") or []]
    concept = ai.chat_json(f"""You design YouTube thumbnails for an animated 2D illustration channel ({ch.get('niche', '')}). Characters have clear, expressive faces.
Video title: {pr['title']}
Script excerpt: {S.narration(pr.get('script') or '')[:1200]}
Recurring characters: {', '.join(chars) or 'none'}
{('Creator idea: ' + idea) if idea else ''}

Create {count} DIFFERENT thumbnail concepts that maximize CTR: one strong focal subject with a big readable emotion, high contrast, simple background, a visual curiosity gap that does NOT repeat the title, and 2-4 words of huge bold text (in the video's language: {S.lang_label(ch.get('language', 'fr'))}) placed away from the subject.
Return JSON: {{"thumbs": [{{"text": "SHORT TEXT", "prompt": "40-70 words: composition, subject, expression, props, background, colors, where the text goes", "chars": ["character names visible"]}}]}}""", model=ai.text_model())
    items = (concept.get("thumbs") or [])[:count]
    if not items:
        raise RuntimeError("Aucun concept de miniature renvoyé.")
    d = store.project_dir(pid)
    done, results = 0, []

    def one(it):
        prompt = (f"YouTube thumbnail. {it.get('prompt', '')} Huge bold clean sans-serif text reading exactly "
                  f"\"{it.get('text', '')}\" with a thick dark outline, perfectly legible, spelled correctly. "
                  "Bright, saturated, high contrast, readable at small size.")
        full, refs = build_image_prompt(ch, prompt, scene_chars=it.get("chars") or [], allow_text=True)
        blob = ai.generate_image(full, width=1920, height=1080, refs=refs, quality="high")
        rel = f"thumbs/thumb_{int(time.time() * 1000) % 10**9}.jpg"
        ai.fit_cover(blob, 1280, 720, os.path.join(d, rel), quality=90)
        return {"file": rel, "text": it.get("text", ""), "prompt": it.get("prompt", ""), "at": store.now()}

    with ThreadPoolExecutor(max_workers=count) as ex:
        for fut in as_completed([ex.submit(one, it) for it in items]):
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001
                job.update(None, f"Une miniature a échoué : {str(e)[:120]}")
            done += 1
            job.update(0.1 + 0.9 * done / len(items), f"Miniatures {done}/{len(items)}")
    if not results:
        raise RuntimeError("Toutes les miniatures ont échoué.")

    def save(x):
        x["thumbnails"] = (results + (x.get("thumbnails") or []))[:8]
    store.update_project(pid, save)
    job.update(1.0, f"{len(results)} miniature(s) prête(s).")


def chapters(pr):
    out = []
    for s in pr.get("scenes") or []:
        if s.get("first"):
            t = int(s["start"])
            out.append(f"{t // 60:02d}:{t % 60:02d} {s.get('heading') or ('Intro' if not out else '')}".strip())
    if out and not out[0].startswith("00:00"):
        out.insert(0, "00:00 Intro")
    return out


def job_metadata(job, pid):
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    job.update(0.2, "Titres, description et tags…")
    meta = S.metadata(ch, pr["title"], pr.get("script") or "")
    meta["chapters"] = chapters(pr)
    store.update_project(pid, lambda x: x.__setitem__("metadata", meta))
    job.update(1.0, "Métadonnées prêtes.")


# ── Autopilot ───────────────────────────────────────────────────────────────

class _Sub:
    """Vue d'un job sur une plage de progression (étapes de l'autopilot)."""

    def __init__(self, job, a, b, label):
        self.job, self.a, self.b, self.label = job, a, b, label

    def update(self, progress=None, message=None):
        p = None if progress is None else self.a + (self.b - self.a) * progress
        self.job.update(p, f"[{self.label}] {message}" if message else None)

    def cancelled(self):
        return self.job.cancelled()


def job_autopilot(job, pid, render_video=True):
    pr = store.get_project(pid)
    if not (pr.get("script") or "").strip():
        job_script(_Sub(job, 0.0, 0.25, "1/4 Script"), pid)
    pr = store.get_project(pid)
    if voice_outdated(pr):
        job_voice(_Sub(job, 0.25, 0.35, "2/4 Voix"), pid)
    job_images(_Sub(job, 0.35, 0.85, "3/4 Images"), pid)
    if render_video:
        job_render(_Sub(job, 0.85, 1.0, "4/4 Montage"), pid)
    job.update(1.0, "Vidéo terminée ✔")
