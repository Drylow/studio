"""Étape 1 · Script — plan puis rédaction partie par partie (façon TubeWriter Pro)."""
import math
import random
import re

from .. import config, events, llm, store, youtube
from ..util import parse_json, word_count

WORDS_PER_PART = 450
# point de départ tiré au hasard pour le « tu » de chaque vidéo (sinon l'IA retombe toujours sur le même profil)
HOMETOWNS = {
    "French": ["Marseille", "Lyon", "Toulouse", "Nantes", "Strasbourg", "Bordeaux", "Rennes", "Montpellier", "Brest",
               "Grenoble", "Dijon", "Perpignan", "Clermont-Ferrand", "Le Havre", "Metz", "Limoges", "Avignon",
               "Bayonne", "Tours", "Nice", "Saint-Étienne", "Rouen", "Amiens", "Poitiers", "Ajaccio",
               "Pointe-à-Pitre", "Liège", "Genève", "Montréal", "Dakar", "Casablanca", "Alger", "Tunis", "Bruxelles"],
    "English": ["Ohio", "Texas", "Glasgow", "Manchester", "Brooklyn", "New Orleans", "Detroit", "Leeds", "Dublin",
                "Atlanta", "Seattle", "Cardiff", "Phoenix", "Belfast", "Chicago", "Liverpool", "Denver", "Bristol",
                "Toronto", "Melbourne", "Nashville", "Birmingham", "Boston", "Miami"],
}
INTRO_ANGLES = ["through your job and what it pays", "through a habit or an object you always carry",
                "through what you want more than anything", "through what you are afraid of losing",
                "through a memory that comes back at the worst moment", "through what other people think of you",
                "through a debt, a promise or a secret", "through your family situation"]


def persona(p: dict) -> str:
    """Un « tu » différent dans chaque vidéo : âge, origine et manière de se présenter tirés au hasard."""
    rnd = random.Random(p["id"])
    lang = p["settings"].get("language", "English")
    town = rnd.choice(HOMETOWNS.get(lang, HOMETOWNS["English"]))
    return (f"PROTAGONIST ('you'): a brand-new person in this video, never the same profile as another video. "
            f"Starting point for this one: about {rnd.randint(17, 64)} years old, from {town} — keep it only if it "
            f"fits the setting (historical or foreign setting: invent an origin that fits instead). Age and hometown "
            f"are optional: introduce who you are {rnd.choice(INTRO_ANGLES)}. Never use the formula "
            f"'you are X years old, you come from Y' (« Tu as X ans, tu viens de Y »). This overrides the channel "
            f"style about stating age and origin.")


def _system(p: dict) -> str:
    s = p["settings"]
    lang = s.get("language", "English")
    parts = [
        "You are an elite YouTube scriptwriter for faceless narrated videos. You write ONLY the narration: "
        "the exact words the voiceover artist will read aloud.",
        f"Write in {lang}.",
        "Rules:\n"
        "- Output only narration text. No title, no headings, no labels, no stage directions, no [brackets], "
        "no markdown, no emojis, no scene numbers, no 'Part 1'.\n"
        "- Separate paragraphs with a blank line.\n"
        "- Spoken rhythm: mix short punchy sentences with longer flowing ones. Concrete sensory details, specific "
        "numbers, names, places and dates. Keep the viewer hooked with open loops, foreshadowing, stakes, "
        "surprises and payoffs. No filler, no generic moralizing, never say 'in conclusion'.\n"
        "- Stay historically/factually accurate. Composite or fictional characters are fine, false facts are not.\n"
        "- Write everything so it sounds natural when read aloud by a text-to-speech voice.",
    ]
    if p.get("format") == "short":
        from ..shorts import script_rules
        parts.append(script_rules(lang, (p["settings"].get("shorts") or {}).get("target_seconds") or 90))
    instr = (s["script"].get("instructions") or "").strip()
    if instr:
        parts.append("CHANNEL STYLE INSTRUCTIONS:\n" + instr)
    refs = s["script"].get("references") or []
    if refs:
        ex = []
        for r in refs[:2]:
            words = r.get("text", "").split()
            ex.append(f"--- Reference: {r.get('title', 'untitled')} ---\n" + " ".join(words[:900]))
        parts.append(
            "STYLE REFERENCES — scripts from this channel. Match their voice, point of view, tense, rhythm, "
            "structure and hooks. Never copy their content or sentences.\n\n" + "\n\n".join(ex)
        )
    if p.get("video_context"):
        ctx = " ".join(p["video_context"].split()[:6000])
        parts.append(
            "SOURCE MATERIAL — transcript of a reference video on this topic. Use it for facts, research and "
            "story beats, but write a fully original script with your own wording and structure. Never copy "
            "sentences from it.\n\n" + ctx
        )
    stars = [c for c in p.get("characters", []) if c.get("in_script") and c.get("enabled", True)]
    for c in stars:
        parts.append(f"RECURRING CHARACTER: {c['name']} is the channel's recurring character and MUST appear in "
                     f"this story as a named character (companion, mentor, rival or witness — whatever fits the "
                     f"topic), present in several key moments. {c.get('script_note', '')} Never describe his physical appearance in the "
                     f"narration (no scar, no face details): the images show it, the words only tell what he does "
                     f"and says.".strip())
    parts.append(persona(p))
    if p.get("topic"):
        parts.append("EXTRA CONTEXT / INSTRUCTIONS FOR THIS VIDEO:\n" + p["topic"])
    return "\n\n".join(parts)


def _clean(text: str) -> str:
    text = re.sub(r"^\s*#+\s.*$", "", text, flags=re.M)               # titres markdown
    text = re.sub(r"^\s*(\*\*)?(part|partie|section|scene)\s*\d+.*$", "", text, flags=re.M | re.I)
    text = re.sub(r"^\s*title\s*:.*$", "", text, flags=re.M | re.I)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\[[^\]]{0,80}\]", "", text)                         # [didascalies]
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _models(p: dict) -> tuple[str, str]:
    selected = p["settings"]["script"].get("model")
    if selected:
        return selected, "low" if p["settings"]["script"].get("mode") == "fast" else "medium"
    if p["settings"]["script"].get("mode") == "fast":
        return config.get("FAST_MODEL"), "low"
    return config.get("SCRIPT_MODEL"), "medium"


async def ensure_context(p: dict) -> None:
    if p.get("video_url") and not p.get("video_context"):
        events.log("Récupération de la transcription YouTube…")
        try:
            p["video_context"] = await youtube.transcript(p["video_url"])
            events.log(f"✓ Transcription YouTube : {len(p['video_context'].split())} mots", "ok")
        except Exception as e:  # noqa: BLE001
            p["video_context"] = ""
            p["steps"]["script"]["msg"] = f"Transcription YouTube indisponible ({e}) — on continue sans."
            events.log(f"⚠ Transcription YouTube indisponible ({e}) — on continue sans", "warn")
        store.save_project(p)


async def generate_title(p: dict) -> str:
    s = p["settings"]
    refs = [r.get("title") for r in s["script"].get("references") or [] if r.get("title")]
    hint = ("Existing titles from this channel: " + " | ".join(refs[:6])) if refs else ""
    base = p.get("script") and " ".join(p["script"].split()[:700])
    prompt = (
        f"Write ONE YouTube video title in {s.get('language', 'English')} for a faceless narrated channel. "
        f"{hint}\n"
        + (f"Topic/notes: {p['topic']}\n" if p.get("topic") else "")
        + (f"Script excerpt: {base}\n" if base else "")
        + "The title must be curiosity-driven, clickable, under 70 characters, same format as the channel's titles. "
          "Return only the title, no quotes."
    )
    title = await llm.chat([{"role": "user", "content": prompt}], model=p["settings"]["script"].get("model") or config.get("FAST_MODEL"), effort="low",
                           label="Titre")
    title = title.strip().strip('"').strip("«»").splitlines()[0][:100]
    events.log(f"✓ Titre : {title}", "ok")
    return title


def _live(p: dict, prefix: str):
    """Affiche le texte en cours d'écriture dans l'éditeur (p["script_draft"])."""
    buf: list[str] = []

    def on_delta(piece: str) -> None:
        buf.append(piece)
        p["script_draft"] = (prefix + "\n\n" if prefix else "") + "".join(buf)
        store.save_throttled(p)
    return on_delta


async def generate(p: dict, progress=None) -> str:
    """Écrit le script complet et l'enregistre dans le projet.

    Reprenable : le plan et chaque partie terminée sont gardés dans p["script_job"] ; après un
    redémarrage, l'écriture reprend à la partie suivante."""
    if progress and p.get("video_url") and not p.get("video_context"):
        progress(0, 1, "Récupération de la transcription YouTube…")
    await ensure_context(p)
    if not p.get("title"):
        if progress:
            progress(0, 1, "Génération du titre…")
        p["title"] = await generate_title(p)
        p["title_auto"] = True
        store.save_project(p)
    target = int(p["settings"]["script"].get("word_count") or 1500)
    lang = p["settings"].get("language", "English")
    model, effort = _models(p)
    system = _system(p)
    n_parts = max(1, math.ceil(target / WORDS_PER_PART))
    events.log(f"Script : {target} mots visés en {lang}, {n_parts} partie(s), modèle {model}")
    p["script_draft"] = ""

    if n_parts == 1:
        if progress:
            progress(0, 1, "Rédaction du script…")
        text = await llm.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": f"Video title: {p['title']}\nWrite the full narration script, about "
                                        f"{target} words. Start with a strong hook in the very first sentence."},
        ], model=model, effort=effort, label="Rédaction du script", on_delta=_live(p, ""))
        text = _clean(text)
    else:
        job = p.get("script_job") or {}
        if job.get("title") != p["title"] or job.get("target") != target or job.get("lang") != lang:
            job = {"title": p["title"], "target": target, "lang": lang, "parts": None, "written": []}
        if job.get("written"):
            events.log(f"↻ Reprise de l'écriture : {len(job['written'])} partie(s) déjà écrite(s)", "step")
        if not job.get("parts"):
            if progress:
                progress(0, n_parts + 1, "Plan du script… (le modèle réfléchit, ~1-2 min)")
            outline_raw = await llm.chat([
                {"role": "system", "content": system},
                {"role": "user", "content":
                    f"Video title: {p['title']}\nTarget length: {target} words of narration.\n"
                    f"Plan the script as exactly {n_parts} consecutive parts that flow as one continuous story. "
                    "The first part opens with an irresistible hook; the arc escalates; the last part delivers the "
                    "emotional/narrative payoff. Return JSON only: "
                    '{"parts":[{"beats":"what happens in this part, key facts and moments, 2-4 sentences",'
                    '"words":<integer>}]} — the words must sum to about ' + str(target) + "."},
            ], model=model, effort=effort, label="Plan du script")
            try:
                job["parts"] = parse_json(outline_raw)["parts"]
            except Exception:  # noqa: BLE001
                job["parts"] = [{"beats": f"Part {i + 1} of the story", "words": target // n_parts}
                                for i in range(n_parts)]
            p["script_job"] = job
            store.save_project(p)
            for i, x in enumerate(job["parts"]):
                events.log(f"   Plan {i + 1}. {str(x.get('beats', ''))[:150]}")
        parts = job["parts"]
        total_budget = sum(int(x.get("words") or 0) for x in parts) or target
        outline_txt = "\n".join(f"{i + 1}. {x.get('beats', '')}" for i, x in enumerate(parts))
        written: list[str] = job["written"]
        for i, part in enumerate(parts):
            if i < len(written):
                continue
            budget = max(120, round(int(part.get("words") or target / len(parts)) * target / total_budget))
            if progress:
                progress(i + 1, len(parts) + 1, f"Rédaction partie {i + 1}/{len(parts)}…")
            so_far = "\n\n".join(written)
            tail = " ".join(so_far.split()[-1400:])
            pos = ("This is the FIRST part: open with a powerful hook in the very first sentence, no greeting, "
                   "no channel intro." if i == 0 else
                   "This is the FINAL part: land the ending with a strong emotional payoff and a memorable last "
                   "line." if i == len(parts) - 1 else "Continue seamlessly from the exact last sentence.")
            msg = (f"Video title: {p['title']}\n\nFULL OUTLINE:\n{outline_txt}\n\n"
                   + (f"SCRIPT WRITTEN SO FAR (last words):\n{tail}\n\n" if tail else "")
                   + f"Now write part {i + 1} of {len(parts)}: {part.get('beats', '')}\n"
                   f"Length: about {budget} words (this matters). {pos}\n"
                   "Output only the narration of this part.")
            text_part = _clean(await llm.chat([{"role": "system", "content": system},
                                               {"role": "user", "content": msg}], model=model, effort=effort,
                                              label=f"Partie {i + 1}/{len(parts)}", on_delta=_live(p, so_far)))
            if word_count(text_part) < budget * 0.7:
                events.log(f"⚠ Partie {i + 1} trop courte ({word_count(text_part)}/{budget} mots) — réécriture", "warn")
                text_part = _clean(await llm.chat([
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"{msg}\n\nYour previous draft was too short "
                                                f"({word_count(text_part)} words). Rewrite it at about {budget} "
                                                f"words with more concrete detail:\n\n{text_part}"},
                ], model=model, effort=effort, label=f"Partie {i + 1} (allongée)", on_delta=_live(p, so_far)))
            written.append(text_part)
            p["script_job"] = job
            store.save_project(p)
            events.log(f"✓ Partie {i + 1}/{len(parts)} : {word_count(text_part)} mots "
                       f"(total {word_count(chr(10).join(written))}/{target})", "ok")
        text = "\n\n".join(written)
    p["script"] = text
    p.pop("script_draft", None)
    p.pop("script_job", None)
    store.add_history(p, "generate", text)
    store.save_project(p)
    events.log(f"✓ Script terminé : {word_count(text)} mots (≈ {round(word_count(text) / 160)} min de voix)", "ok")
    return text


async def rewrite_selection(p: dict, start: int, end: int, action: str, instruction: str = "") -> str:
    script = p["script"]
    sel = script[start:end]
    if not sel.strip():
        raise ValueError("Sélection vide")
    n = word_count(sel)
    how = {
        "regenerate": "Rewrite it with fresh wording but the same meaning and roughly the same length.",
        "adjust": f"Apply this instruction: {instruction}",
        "shorten": f"Shorten it to about {max(5, int(n * 0.75))} words, keeping the key information.",
        "lengthen": f"Lengthen it to about {n + min(500, max(30, n))} words with more vivid, concrete detail.",
    }.get(action, f"Apply this instruction: {instruction}")
    before = script[max(0, start - 1500):start]
    after = script[end:end + 800]
    out = await llm.chat([
        {"role": "system", "content": _system(p)},
        {"role": "user", "content": f"Here is a passage of the script, with surrounding context.\n\n"
                                    f"CONTEXT BEFORE:\n{before}\n\nPASSAGE TO CHANGE:\n{sel}\n\n"
                                    f"CONTEXT AFTER:\n{after}\n\n{how}\n"
                                    "It must flow seamlessly with the context. Return only the new passage."},
    ], model=p["settings"]["script"].get("model") or config.get("SCRIPT_MODEL"), effort="low", label=f"Sélection ({action})")
    out = _clean(out)
    p["script"] = script[:start] + out + script[end:]
    store.add_history(p, f"selection:{action}", p["script"])
    store.save_project(p)
    return p["script"]
