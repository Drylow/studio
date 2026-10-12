"""Courts formats TikTok / Reels / Shorts (1 min 30 max).

Deux usages :
  - « promo »      : un short PUB tiré d'une longue vidéo — accroche, tension, cliffhanger sans révéler
                     la fin, appel à l'action vers YouTube + écran de fin avec la miniature de la vidéo ;
  - « standalone » : un TikTok autonome, histoire complète (depuis l'accueil, le CSV ou une longue vidéo).
"""
import copy
import shutil
from pathlib import Path

from . import config, events, llm, store
from .util import ffprobe_duration, parse_json, run_cmd, word_count

MAX_SECONDS = 90
ENDCARD_HOLD = 1.3  # silence ajouté après l'appel à l'action : l'écran de fin reste lisible
# réglages appliqués à un projet « short » (vertical, coupes rapides, sous-titres TikTok)
SHORT_OVERRIDES = {
    "script.word_count": 190,
    "visuals.aspect": "9:16",
    "visuals.avg_scene_seconds": 2.8,
    "visuals.min_scene_seconds": 1.2,
    "visuals.max_scene_seconds": 5.0,
    "visuals.captions": True,
    "visuals.caption_style": "tiktok",
    "thumbnail.count": 0,
}
# appel à l'action par langue (modifiable dans le style : shorts.cta_*)
CTA_DEFAULTS = {  # jamais « YouTube » en toutes lettres : TikTok le voit d'un mauvais œil
    "French": {"spoken": "Si tu veux voir la suite, va voir mon réseau sur la plateforme rouge.",
               "line1": "LA SUITE", "line2": "PLATEFORME ROUGE", "line3": "lien en bio"},
    "English": {"spoken": "If you want to see more, check out my channel on the red platform.",
                "line1": "FULL STORY", "line2": "ON THE RED PLATFORM", "line3": "link in bio"},
    "Spanish": {"spoken": "Si quieres ver más, busca mi canal en la plataforma roja.",
                "line1": "LA HISTORIA COMPLETA", "line2": "PLATAFORMA ROJA", "line3": "link en la bio"},
}


def apply_short_settings(p: dict) -> None:
    p["format"] = "short"
    for path, value in SHORT_OVERRIDES.items():
        node = p["settings"]
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value


def cta_for(p: dict) -> dict:
    return _cta(p["settings"].get("language", "English"), p["settings"].get("shorts") or {})


def _cta(lang: str, custom: dict) -> dict:
    base = dict(CTA_DEFAULTS.get(lang, CTA_DEFAULTS["English"]))
    for k in ("spoken", "line1", "line2", "line3"):
        if (custom.get(f"cta_{k}") or "").strip():
            base[k] = custom[f"cta_{k}"].strip()
    return base


async def hold_tail(mp3: Path, seconds: float = ENDCARD_HOLD) -> float:
    """Prolonge la voix d'un short pub par un silence ; renvoie la nouvelle durée."""
    tmp = mp3.with_name("voice_hold.mp3")
    await run_cmd([config.get("FFMPEG"), "-y", "-v", "error", "-i", str(mp3), "-af", f"apad=pad_dur={seconds}",
                   "-c:a", "libmp3lame", "-b:a", "192k", str(tmp)])
    tmp.replace(mp3)
    return ffprobe_duration(mp3)


def script_rules(language: str, seconds: int = 90) -> str:
    seconds = max(30, min(180, int(seconds or 90)))
    return (
        f"FORMAT: vertical short video for TikTok / Reels / Shorts — about {seconds} seconds of narration "
        f"(about {round(seconds * 2.3)} words, never more than {round(seconds * 2.5)}).\n"
        "- The FIRST sentence is the hook: under 12 words, it must make scrolling impossible (a shocking fact, a "
        "question, a stake, an 'imagine'). No greeting, no context before it.\n"
        "- Then fast escalation: short punchy sentences, one idea per sentence, concrete images, a twist.\n"
        "- The story MUST have a real ending (the 'chute'): the situation is resolved on screen, we see the "
        "outcome and its consequence, then a short final punchline that closes the story (irony, reversal, the "
        "price paid). Never stop on the setup of the twist, never end on an open question or a cliffhanger: the "
        "viewer must feel 'it's over, and it landed'.\n"
        "- No 'subscribe', no 'like and share'.\n"
        f"- Written in {language}, natural spoken rhythm."
    )


def promo_rules(language: str, cta_spoken: str) -> str:
    return (
        "FORMAT: vertical TEASER short (TikTok / Reels / Shorts) whose ONLY goal is to make viewers go watch the "
        "full video on YouTube — HARD LIMIT 75 seconds of narration (about 140-170 words).\n"
        "- The FIRST sentence is the hook: under 12 words, impossible to scroll past.\n"
        "- Then tease the most intense moments and stakes of the story, escalating fast, one idea per sentence.\n"
        "- NEVER reveal how it ends: stop on a cliffhanger at the peak of tension (an open question, a threat, a "
        "decision that has not been made yet).\n"
        f"- The LAST sentence is exactly: \"{cta_spoken}\"\n"
        f"- Written in {language}, natural spoken rhythm, no 'subscribe', no 'like'.\n"
        "- NEVER say or write the word 'YouTube' (TikTok penalizes it): it is only ever 'the red platform'."
    )


async def write_meta(p: dict) -> dict:
    """Titre d'accroche à l'écran (« grand jeu »), légende TikTok et hashtags."""
    lang = p["settings"].get("language", "English")
    first = " ".join((p.get("script") or "").split()[:60])
    promo = (p.get("short") or {}).get("kind") == "promo"
    from . import channels
    used = [h for h in channels.used_hooks(p.get("channel_id")) if h not in (p.get("title"),)][:30]
    avoid = ("\nThese hooks were already used on this account — do NOT reuse them or their structure "
             "(vary the angle, the first word and the rhythm):\n- " + "\n- ".join(used) + "\n") if used else ""
    data = parse_json(await llm.chat([{"role": "user", "content": (
        f"Short vertical video. Title: {p.get('title', '')}\nOpening of the narration: {first}\n{avoid}\n"
        f"Write in {lang}:\n"
        "1) hook_text: the BIG on-screen hook shown during the first 2-3 seconds — 2 to 6 words, uppercase "
        "friendly, punchy, curiosity-driven (can differ from the spoken first line);\n"
        "2) hook_highlight: ONE word of hook_text to highlight in color;\n"
        + ("3) caption: the TikTok post caption (1-2 short lines): a teaser hook + say the full story is on "
           "\"the red platform\" (NEVER write the word YouTube) with the link in bio;\n" if promo else
           "3) caption: the TikTok post caption (1-2 short lines, a hook + a question to drive comments);\n")
        + "4) hashtags: 5 to 8 relevant hashtags (mix broad and niche), without the # sign.\n"
        'Return JSON only: {"hook_text":"","hook_highlight":"","caption":"","hashtags":[]}')}],
        model=config.get("FAST_MODEL"), effort="low", label="Accroche + légende TikTok"))
    meta = {"hook_text": (data.get("hook_text") or "").strip(),
            "hook_highlight": (data.get("hook_highlight") or "").strip(),
            "caption": (data.get("caption") or "").strip(),
            "hashtags": [h.strip().lstrip("#") for h in data.get("hashtags", []) if str(h).strip()]}
    p["short"] = (p.get("short") or {}) | meta
    store.save_project(p)
    events.log(f"✓ Accroche à l'écran : « {meta['hook_text']} »", "ok")
    return meta


async def shorts_from_long(p_long: dict, count: int = 2, mode: str = "auto", kind: str = "promo",
                           channel: dict | None = None) -> list[dict]:
    """Tire des shorts d'une longue vidéo TubeForge (nouveaux projets). kind = "promo" ou "standalone"."""
    src_dir = store.project_dir(p_long["id"])
    thumb_rel = store.thumbnail_path(p_long)
    return await _make_shorts({
        "title": p_long.get("title", ""), "script": p_long.get("script") or "",
        "language": p_long["settings"].get("language", "English"), "style_id": p_long["style_id"],
        "settings": p_long["settings"], "parent_id": p_long["id"], "log_to": p_long,
        "thumb": (src_dir / thumb_rel) if thumb_rel and (src_dir / thumb_rel).exists() else None,
        "characters": [(c, src_dir) for c in p_long.get("characters", [])],
    }, count, mode, kind, channel)


async def shorts_from_url(url: str, count: int = 2, mode: str = "auto", kind: str = "promo",
                          channel: dict | None = None) -> list[dict]:
    """Clipping d'une vidéo YouTube déjà en ligne : transcription + miniature -> shorts."""
    from . import youtube
    events.log(f"Lecture de la vidéo YouTube {url}…", "step")
    info = await youtube.info(url)
    script = await youtube.transcript(url)
    tmp = config.DATA / "previews" / f"yt_{youtube.video_id(url)}.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    has_thumb = await youtube.thumbnail(url, tmp)
    style_id = (channel or {}).get("style_id") or store.list_styles()[0]["id"]
    style = store.get_style(style_id) or store.list_styles()[0]
    settings = {k: copy.deepcopy(style[k]) for k in ("script", "voice", "visuals", "thumbnail", "shorts")}
    settings["language"] = style.get("language", "English")
    events.log(f"✓ « {info['title']} » ({word_count(script)} mots de transcription)", "ok")
    return await _make_shorts({
        "title": info["title"], "script": script, "language": None, "style_id": style["id"], "settings": settings,
        "parent_id": None, "source_url": url, "thumb": tmp if has_thumb else None, "characters": [],
    }, count, mode, kind, channel)


async def _make_shorts(src: dict, count: int, mode: str, kind: str, channel: dict | None) -> list[dict]:
    from . import channels as chans
    lang = (channel or {}).get("language") or src["language"] or "English"
    script = src["script"]
    if word_count(script) < 150:
        raise ValueError("Le script de la vidéo est trop court pour en tirer des shorts")
    custom = dict(src["settings"].get("shorts") or {})
    for k in ("spoken", "line1", "line2", "line3"):
        if channel and (channel["cta"].get(k) or "").strip():
            custom[f"cta_{k}"] = channel["cta"][k]
    cta = _cta(lang, custom)
    label = "shorts pub" if kind == "promo" else "TikToks autonomes"
    log_to = src.get("log_to")
    events.log(f"Recherche des {count} meilleurs passages pour des {label}…", "step", log_to)
    translate = (f"\n- The source may be in another language: write every short directly in {lang} "
                 "(natural, idiomatic adaptation, never a literal translation).")
    if kind == "promo":
        ask = (f"Write {count} different TEASER shorts that advertise this video, each built around a different "
               "gripping angle or moment of the story.\n" + promo_rules(lang, cta["spoken"]) + translate)
    else:
        ask = (f"Pick the {count} most gripping, self-contained moments and turn each into a standalone vertical "
               "short.\n" + script_rules(lang)
               + "\n- Keep the original sentences and voice as much as possible (light edits only so it stands "
                 "alone).\n- Each short must be understandable without having seen the long video." + translate)
    used = chans.used_hooks((channel or {}).get("id"))
    if used:
        ask += ("\n- These titles/hooks were already posted on this account, find NEW angles:\n  - "
                + "\n  - ".join(used[:25]))
    data = parse_json(await llm.chat([{"role": "user", "content": (
        f"Here is the narration of a long YouTube video titled \"{src['title']}\".\n\n{script}\n\n"
        + ask + '\nReturn JSON only: {"shorts":[{"title":"short title for TikTok","script":"the full narration"}]}')}],
        model=config.get("SCRIPT_MODEL"), effort="low", label=f"Écriture des {label}"))
    items = (data.get("shorts") if isinstance(data, dict) else data) or []
    created = []
    for it in items[:count]:
        text = (it.get("script") or "").strip()
        if not text:
            continue
        p = store.create_project(it.get("title") or src["title"] or "Short", src["style_id"],
                                 mode=mode, custom_script=text, characters=[])
        p["settings"] = copy.deepcopy(src["settings"])
        p["settings"]["language"] = lang
        apply_short_settings(p)
        if channel:
            chans.apply(p, channel)
        if src.get("parent_id"):
            p["parent_id"] = src["parent_id"]
        if src.get("source_url"):
            p["source_url"] = src["source_url"]
        pdir = store.project_dir(p["id"])
        p["short"] = {"kind": kind, "parent_title": src["title"]}
        if kind == "promo":
            p["short"]["cta"] = cta
            if src.get("thumb"):  # miniature de la vidéo YouTube pour l'écran de fin
                shutil.copy2(src["thumb"], pdir / "endcard_thumb.png")
                p["short"]["endcard_thumb"] = "endcard_thumb.png"
        # mêmes personnages (avec leurs fiches) que la longue vidéo
        for c, cdir in src["characters"]:
            c = copy.deepcopy(c)
            if c.get("image") and (cdir / c["image"]).exists():
                (pdir / "characters").mkdir(exist_ok=True)
                shutil.copy2(cdir / c["image"], pdir / c["image"])
            p["characters"].append(c)
        store.save_project(p)
        created.append(p)
        events.log(f"✓ {'Short pub' if kind == 'promo' else 'TikTok'} créé : « {p['title']} » "
                   f"({word_count(text)} mots{', ' + channel['name'] if channel else ''})", "ok", log_to)
    if not created:
        raise RuntimeError("Aucun short n'a pu être tiré de cette vidéo")
    if channel:
        from . import planner
        planner.assign(channel)
    return created


async def ideas(ch: dict, n: int = 30, theme: str = "") -> list[dict]:
    """Idées de TikToks pour une chaîne (titres + angle), sans redites avec ce qui existe déjà."""
    from . import channels
    style = store.get_style(ch["style_id"]) or store.list_styles()[0]
    refs = [r.get("title") for r in style["script"].get("references", []) if r.get("title")]
    used = channels.used_hooks(ch["id"], 80)
    data = parse_json(await llm.chat([{"role": "user", "content": (
        f"You plan the content of the TikTok account « {ch['name']} » (faceless 2D animated story videos, "
        f"vertical, 60-90 s, written in {ch['language']}).\n"
        f"Channel style: {style['script'].get('instructions', '')[:600]}\n"
        f"Example titles of the channel's long videos: {'; '.join(refs) or 'none'}\n"
        + (f"Theme for this batch: {theme}\n" if theme else "")
        + ("Already made (do NOT repeat or paraphrase):\n- " + "\n- ".join(used) + "\n" if used else "")
        + f"\nGive {n} NEW video ideas with strong viral potential: varied eras, places and roles, each with a "
          "concrete gripping situation (stakes, danger, a twist). Titles in the channel language, in the "
          "channel's title format (e.g. 'POV: ...' / 'POV : Tu es ...'), max 70 characters. "
          "context = one line in English: the angle and 2-3 concrete facts to include.\n"
          'Return JSON only: {"ideas":[{"title":"","context":""}]}')}],
        model=config.get("SCRIPT_MODEL"), effort="low", label=f"Idées TikTok ({ch['name']})"))
    out = []
    for it in (data.get("ideas") if isinstance(data, dict) else data) or []:
        t = (it.get("title") or "").strip()
        if t and t not in used:
            out.append({"title": t, "context": (it.get("context") or "").strip()})
    return out[:n]
