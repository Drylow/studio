"""Écriture de scripts YouTube « par chaîne » — le cœur de la qualité.

Pipeline (chaque étape a son prompt dédié, pas un seul prompt fourre-tout) :
  1. BIBLE de chaîne : à partir de scripts/transcriptions de référence (tes vidéos
     ou celles d'un concurrent), l'IA extrait un guide de style réutilisable
     (narrateur, rythme, formule de hook, structure, tics à reproduire / éviter).
  2. PLAN : titre + format + durée cible → hook, sections, beats, budget de mots.
  3. RÉDACTION : section par section, avec la fin de la section précédente en
     contexte (continuité, transitions, boucles ouvertes).
  4. RELECTURE : un « script doctor » note le script et liste les problèmes ;
     seules les sections signalées sont réécrites.

Les sections sont séparées dans le texte final par des lignes « ## Titre » :
elles ne sont PAS lues par la voix off mais servent aux titres à l'écran.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from services import ai

LANGS = {
    "fr": "French (natural spoken French from France, like a top French YouTuber — not translated English)",
    "en": "English (natural spoken American English)",
    "es": "Spanish (natural spoken Spanish)",
    "de": "German (natural spoken German)",
    "pt": "Portuguese (natural spoken Brazilian Portuguese)",
    "it": "Italian (natural spoken Italian)",
}

# ── Formats de vidéo (presets) ──────────────────────────────────────────────
# `structure` = consignes pour le plan, `heading` = format des titres de section.
FORMATS = {
    "pov_levels": {
        "name": "Every Rank / Every Level (POV)",
        "desc": "« Your Life as Every Rank in… » — le spectateur EST le perso et grimpe les niveaux (armée, métier, crime, hôpital…).",
        "heading": "Level N: <rank / level name>  (FR: « Niveau N — <nom> »)",
        "structure": """SECOND-PERSON POV ("you"/"tu"), PRESENT TENSE. The viewer IS the protagonist and the SAME person ages and rises through the whole video.
- NO intro fluff. The very first words drop the viewer into Level 1 with age and situation (e.g. "Level one, Private. You are 17 years old. You don't choose this."), OR a 2-3 sentence cold open from a later level then "But it didn't start like this." Pick whatever hooks harder.
- 7 to 10 levels from the lowest to the highest / most extreme rank. Every level clearly ESCALATES (money, power, danger, secrecy, responsibility) and the protagonist is older.
- Each level follows: rank/age & how you got promoted → what your days and missions actually look like (concrete scene, sensory details) → one insider anecdote or hard number (pay, hours, odds, real procedures, slang) → the evaluation / hidden cost / what can go wrong → the promotion or event that pushes you to the next level (one-line hook).
- Serious, grounded, documentary tone. The final level ends with a reflective twist or a callback to Level 1.""",
    },
    "your_life_if": {
        "name": "Your Life If… (POV par âge)",
        "desc": "« POV: You Retired at 35 », « Your Life If You Invested $5 a Day » — même perso suivi à travers les âges, avec chiffres.",
        "heading": "Age N  (or a short milestone like « 30 ans — premier appart »)",
        "structure": """SECOND-PERSON POV, PRESENT TENSE, calm and concrete. The same protagonist is followed through AGE MILESTONES (e.g. 25 → 30 → 40 → 50 → 65).
- HOOK (no heading): an ordinary everyday scene with a precise time, place and amount of money ("It's 6:40 pm and you're standing at a convenience store counter with a five-dollar bill...") that secretly contains the whole premise. End it with a line that makes the stakes obvious.
- Each age section: where you are in life → the key decision or event → the running numbers (balance, income, debt, returns — realistic and internally consistent, compounding done right) → the emotional/social consequence → contrast with the alternative path.
- Include one clear comparison (you vs the friend who chose differently) somewhere in the middle.
- End with the final number, the lesson in one sentence, and a callback to the hook scene. Never give personalized financial advice; stay educational.""",
    },
    "ancient_life": {
        "name": "How Did Ancient Humans… (vie d'avant)",
        "desc": "« What Did Ancient Humans Actually Do All Day? » — contraste avec la vie moderne, preuves, journée reconstituée.",
        "heading": "short chapter title (2-5 words)",
        "structure": """EXPLAINER about how people lived in the past, told directly to the viewer ("you"), punchy and a bit funny.
- HOOK (no heading): contrast with the viewer's modern life in 2-3 very concrete sentences ("This morning, a machine screamed at you until you woke up..."), then the question the video answers.
- Sections: modern contrast → what archaeology / historians actually found (name the evidence type: bones, tools, cave sites, texts) → a reconstructed day or process step by step → hard numbers (hours, calories, life expectancy, distances) → the surprising twist that flips the assumption.
- Very short sentences, fast pacing, lots of concrete nouns that are easy to illustrate. Light humor, never mocking.
- End with the twist that reframes the viewer's own life.""",
    },
    "survival": {
        "name": "Why You Wouldn't Survive… (immersion)",
        "desc": "« Pourquoi vous ne survivriez pas à… », « How Long You'd Last in… » — un danger par chapitre.",
        "heading": "the danger or the time marker (e.g. « 6h00 — le réveil », « Danger n°3 : l'eau »)",
        "structure": """IMMERSIVE SECOND-PERSON SURVIVAL ("Imagine... you are..." / « Imaginez... vous êtes... »), present tense.
- HOOK (no heading): place the viewer in the setting with vivid sensory detail in 2-3 sentences, then state the stakes (you would not survive long) and why.
- One danger per section, escalating: what you'd face → why your modern body/habits fail → the real historical/scientific detail → how locals actually survived → your survival odds so far (keep a running "survival clock" or score).
- End with the final verdict (how long you'd last) and a sobering or surprising last line.""",
    },
    "every_explained": {
        "name": "Every X Explained / X Years in N Minutes",
        "desc": "« Every Unexplored Place on Earth », « 1500 Years of Russian History in 30 Minutes » — liste ou chronologie compressée.",
        "heading": "item name or era / year range",
        "structure": """FAST-PACED LIST OR COMPRESSED TIMELINE, witty narrator.
- HOOK (no heading): the most shocking item/moment in one line, then the promise of the whole list/timeline.
- Items (or eras) in a satisfying order (escalating weirdness, or chronological). Each: what/where/when in one line → the story or mechanism that makes it remarkable → one hard number → a quick funny or dark aside → snappy transition.
- Keep a steady rhythm: similar length per item, no filler, no repetition of sentence openers.
- End on the strongest item or the modern consequence of the timeline.""",
    },
    "story": {
        "name": "Histoire racontée (documentaire narratif)",
        "desc": "Une histoire vraie racontée comme un thriller, avec suspense et rebondissements.",
        "heading": "evocative chapter title (2-5 words)",
        "structure": """NARRATIVE DOCUMENTARY (third person, past or present tense), told like a thriller.
- HOOK (no heading): start in medias res at the most dramatic moment, then promise the question the video answers.
- Chapters in chronological order with rising tension; each chapter ends on a mini-cliffhanger or reveal.
- Use specific names, dates, places, numbers. Show, don't tell: concrete scenes over summaries.
- Climax, then resolution and a final line that recontextualizes the story.""",
    },
    "ranking": {
        "name": "Classement / Top",
        "desc": "Un top ou une liste classée, du moins au plus impressionnant.",
        "heading": "N. <item name>",
        "structure": """COUNTDOWN / RANKED LIST.
- HOOK (no heading): tease the #1 without revealing it, and why this list will surprise.
- Items from least to most impressive (countdown). Each item: what it is, the story or detail that makes it remarkable, one hard number, and a transition that raises expectations for the next one.
- #1 must pay off the hook. Quick final line.""",
    },
    "custom": {
        "name": "Personnalisé",
        "desc": "Aucune structure imposée : seulement la bible et les règles de la chaîne.",
        "heading": "short section title",
        "structure": "Follow the channel bible and rules exactly. Hook first (no heading), then logical sections.",
    },
}

BANNED = {
    "en": ["delve", "tapestry", "testament to", "in today's video", "let's dive in", "dive into", "buckle up",
           "game-changer", "unlock", "embark", "journey", "in conclusion", "it's worth noting", "whether you're",
           "imagine a world where", "but here's the thing", "the answer might surprise you", "stay tuned",
           "smash that like button", "without further ado", "fascinating", "realm", "intricate"],
    "fr": ["plongeons", "plongez", "dans cette vidéo", "accrochez-vous", "sans plus attendre",
           "il est important de noter", "en conclusion", "incontournable", "fascinant", "un véritable voyage",
           "au cœur de", "n'hésitez pas", "que vous soyez", "imaginez un monde où", "la réponse va vous surprendre",
           "restez jusqu'à la fin", "attachez vos ceintures", "force est de constater", "en somme"],
}

UNIVERSAL_RULES = """WRITING RULES (non-negotiable):
- This is a VOICEOVER script: write only what the narrator says out loud. No stage directions, no [brackets], no emojis, no markdown, no bullet points, no scene descriptions.
- Spoken rhythm: mostly short and medium sentences, varied length, one idea per sentence. It must sound natural when read by a text-to-speech voice.
- The first sentence must hook within 5 seconds: no greeting, no channel name, no "in this video". Open a loop the viewer needs closed.
- Be SPECIFIC: real names, numbers, procedures, places, sensory details. Vague filler is forbidden. If you state a fact, it must be accurate; never invent statistics — prefer precise but safe phrasing.
- Retention: every 30-60 seconds give a new reveal, twist, or question. End each section with a reason to keep watching.
- Never repeat the same idea, sentence opener, or rhetorical device twice in a row. Max one rhetorical question per section.
- Avoid AI-sounding clichés and these words/phrases: {banned}.
- Write numbers the way they are spoken naturally in the target language (digits are fine for years and big numbers)."""


def lang_label(code):
    return LANGS.get((code or "fr").lower(), f"the language with ISO code '{code}' (natural spoken)")


def _banned(code):
    words = BANNED.get(code, []) + (BANNED["en"] if code != "en" else [])
    return ", ".join(f'"{w}"' for w in words)


def _channel_block(ch):
    """Contexte de chaîne injecté dans tous les prompts d'écriture."""
    parts = [f"CHANNEL: {ch.get('name') or 'Untitled channel'}"]
    for key, label in (("niche", "Niche"), ("audience", "Target audience"), ("tone", "Narrator & tone"),
                       ("rules", "Channel rules (must follow)"), ("cta", "Outro call-to-action (use once, at the very end, short)")):
        if (ch.get(key) or "").strip():
            parts.append(f"{label}: {ch[key].strip()}")
    if (ch.get("bible") or "").strip():
        parts.append("CHANNEL STYLE BIBLE (derived from the channel's best videos — imitate this voice closely):\n"
                     + ch["bible"].strip())
    ref = (ch.get("reference_scripts") or "").strip()
    if ref:
        parts.append("REFERENCE EXCERPT (for voice and rhythm ONLY — never copy its content):\n\"\"\"\n"
                     + ref[:2500] + "\n\"\"\"")
    return "\n\n".join(parts)


def _format(ch):
    return FORMATS.get(ch.get("format") or "pov_levels", FORMATS["pov_levels"])


def _system(ch):
    lang = (ch.get("language") or "fr").lower()
    fmt = _format(ch)
    return (
        "You are an elite scriptwriter for faceless YouTube channels (millions of views, top 1% retention). "
        "You write in " + lang_label(lang) + ".\n\n"
        + _channel_block(ch) + "\n\n"
        "VIDEO FORMAT: " + fmt["name"] + "\n" + fmt["structure"] + "\n\n"
        + UNIVERSAL_RULES.format(banned=_banned(lang))
    )


def target_words(ch, minutes):
    wpm = float(ch.get("wpm") or 150)
    return max(80, int(round(float(minutes) * wpm)))


# ── 1. Bible de chaîne ──────────────────────────────────────────────────────

def build_bible(ch, reference_text):
    lang = (ch.get("language") or "fr").lower()
    prompt = f"""Analyze these reference scripts/transcripts from a successful YouTube channel and write a reusable STYLE BIBLE that another writer can follow to produce new scripts that feel like the same channel.

Write the bible in {lang_label(lang)}, as concise bullet points (max ~350 words), covering:
1. Narrator persona & point of view (person, tense, attitude, how it addresses the viewer).
2. Hook formula used in the first 15 seconds (describe the pattern + 2 short example hooks in that style, on NEW topics).
3. Structure pattern (sections, how they escalate, typical length of a section).
4. Sentence rhythm & vocabulary level; recurring devices (callbacks, questions, numbers, humor...).
5. Transitions between sections (with 2 examples).
6. How it ends (outro pattern).
7. What to AVOID to stay on-brand.
Output ONLY the bible text.

REFERENCE:
\"\"\"
{reference_text[:12000]}
\"\"\""""
    return ai.chat(prompt, model=ai.text_model(), reasoning="medium").strip()


# ── Idées de vidéos ─────────────────────────────────────────────────────────

def title_ideas(ch, hint="", count=12):
    lang = (ch.get("language") or "fr").lower()
    fmt = _format(ch)
    prompt = f"""{_channel_block(ch)}

VIDEO FORMAT: {fmt['name']} — {fmt['desc']}

Generate {count} video ideas for this channel, in {lang_label(lang)}. {('Focus / constraint: ' + hint) if hint else ''}
Each idea must be a real, clickable YouTube title (curiosity + clarity, max ~70 characters) that fits the format exactly, is specific (not generic), and has strong search or browse potential. Mix safe bets and bold ideas. No clickbait lies.
Return JSON: {{"ideas": [{{"title": "...", "angle": "one sentence: why it will get clicks and what the video covers"}}]}}"""
    data = ai.chat_json(prompt, model=ai.text_model())
    return [i for i in (data.get("ideas") or []) if isinstance(i, dict) and i.get("title")][:count]


# ── Niche bending ───────────────────────────────────────────────────────────

def niche_bend(source, target="", language="fr", count=5, style_keys=None):
    """Transpose un format gagnant vers des niches moins saturées / mieux payées."""
    fmts = "\n".join(f"- {k}: {v['name']} — {v['desc']}" for k, v in FORMATS.items())
    styles = ", ".join(style_keys or [])
    prompt = f"""You are a YouTube niche strategist for faceless 2D-illustrated channels (narration + AI still images, no real animation needed).

WINNING FORMAT / CHANNEL TO BEND (what already works): {source}
{('TARGET DOMAIN WANTED BY THE CREATOR: ' + target) if target else 'No target domain given: propose the best domains yourself.'}
LANGUAGE / MARKET: {lang_label(language)}

"Niche bending" = keep the proven packaging (format, title pattern, pacing, visual style) but apply it to a different topic with less competition and/or higher RPM (finance, law, medicine, careers, business, aviation, tech, real estate, psychology, history of X...). Avoid topics that are already saturated with this exact format.

Available script formats (pick one key): 
{fmts}
Available visual style keys: {styles}

Give {count} concrete channel concepts. Return JSON:
{{"concepts": [{{"name": "channel name", "niche": "one sentence", "audience": "who", "format": "<format key>", "style": "<style key>",
  "tone": "narrator & tone in one sentence", "why": "why it can work: demand, competition, RPM (be honest, say what is uncertain)",
  "rpm": "low | medium | high", "titles": ["5 video titles following the winning title pattern"]}}]}}"""
    data = ai.chat_json(prompt, model=ai.text_model(), reasoning="medium", timeout=240)
    out = []
    for c in data.get("concepts") or []:
        if isinstance(c, dict) and c.get("name"):
            if c.get("format") not in FORMATS:
                c["format"] = "custom"
            out.append(c)
    return out[:count]


# ── 2. Plan ─────────────────────────────────────────────────────────────────

def outline(ch, title, minutes, notes=""):
    words = target_words(ch, minutes)
    fmt = _format(ch)
    n_sections = max(3, min(14, round(words / 190)))
    lang = (ch.get("language") or "fr").lower()
    prompt = f"""Create the detailed outline of a {minutes}-minute video (≈{words} spoken words in total).

TITLE: {title}
{('EXTRA INSTRUCTIONS FROM THE CREATOR: ' + notes) if notes else ''}

Plan about {n_sections} sections after the hook (adapt to the format). Section heading style: {fmt['heading']} — headings in {lang_label(lang)}.
For each section give the beats (the concrete facts, scenes, numbers and twists it will contain — be specific, this is where the research happens) and a word budget. The budgets must add up to ≈{words} words including the hook.

Return JSON:
{{
  "title": "final title",
  "hook": {{"beats": ["..."], "target_words": 60}},
  "sections": [{{"heading": "...", "beats": ["...", "..."], "target_words": 180}}],
  "ending": "how the last section lands (callback / twist)"
}}"""
    data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                        model=ai.text_model(), reasoning="medium", timeout=300)
    secs = [s for s in (data.get("sections") or []) if isinstance(s, dict) and s.get("heading")]
    if not secs:
        raise ai.AIError("Le plan renvoyé est vide — relance.")
    hook = data.get("hook") if isinstance(data.get("hook"), dict) else {"beats": [], "target_words": 60}
    # budgets recalés pour que leur somme = cible (le modèle arrondit souvent large)
    raw = [int(hook.get("target_words") or 50)] + [int(x.get("target_words") or 150) for x in secs]
    scale = words / float(sum(raw) or 1)
    hook["target_words"] = max(25, round(raw[0] * scale))
    for x, r in zip(secs, raw[1:]):
        x["target_words"] = max(30, round(r * scale))
    return {"title": data.get("title") or title, "hook": hook, "sections": secs, "ending": data.get("ending", ""),
            "target_words": words}


def _outline_text(ol):
    lines = [f"TITLE: {ol['title']}", "HOOK: " + " | ".join(ol["hook"].get("beats") or [])]
    for i, s in enumerate(ol["sections"], 1):
        lines.append(f"{i}. {s['heading']} ({s.get('target_words', '?')} words): " + " | ".join(s.get("beats") or []))
    if ol.get("ending"):
        lines.append("ENDING: " + ol["ending"])
    return "\n".join(lines)


# ── 3. Rédaction ────────────────────────────────────────────────────────────

def _clean(text):
    t = (text or "").strip()
    t = re.sub(r"^```\w*|```$", "", t).strip()
    lines = []
    for ln in t.splitlines():
        s = ln.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("#"):
            continue  # le modèle ne doit pas réécrire le titre de section
        s = re.sub(r"^\*\*(.+)\*\*$", r"\1", s)
        s = re.sub(r"\[[^\]]{0,60}\]", "", s).strip()
        if s:
            lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def write_section(ch, ol, idx, previous_tail):
    """idx = -1 pour le hook, sinon index de section."""
    if idx < 0:
        n = int(ol["hook"].get("target_words") or 60)
        what = ("the HOOK / cold open (no heading). Beats: " + " | ".join(ol["hook"].get("beats") or [])
                + f". LENGTH: {int(n * 0.9)}-{int(n * 1.1)} words (hard limit).")
    else:
        s = ol["sections"][idx]
        last = idx == len(ol["sections"]) - 1
        n = int(s.get("target_words") or 180)
        what = (f"section {idx + 1}/{len(ol['sections'])} \"{s['heading']}\". Beats: " + " | ".join(s.get("beats") or [])
                + f". LENGTH: {int(n * 0.9)}-{int(n * 1.1)} words (hard limit — pick the strongest beats if they don't all fit)."
                + (" This is the LAST section: land the ending (" + (ol.get("ending") or "strong final line") + ")."
                   if last else " End with a one-line hook into the next section."))
    if previous_tail:
        context = ("END OF THE PREVIOUS PART (continue seamlessly, do not repeat it):\n<<<\n"
                   + previous_tail + "\n>>>")
    else:
        context = "This is the very beginning of the video."
    prompt = (f"FULL OUTLINE (for context):\n{_outline_text(ol)}\n\n{context}\n\n"
              f"Now write ONLY {what}\nDo not write the heading. Output only the narration text.")
    text = ai.chat([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                   model=ai.text_model(), reasoning="medium", timeout=300)
    return _clean(text)


# ── 4. Relecture ────────────────────────────────────────────────────────────

def review(ch, title, parts):
    """parts = [(heading, text)] (heading '' pour le hook). Renvoie {score, issues}."""
    numbered = "\n\n".join(f"[{i}] {h or 'HOOK'}\n{t}" for i, (h, t) in enumerate(parts))
    prompt = f"""You are a ruthless YouTube script doctor. Review this script for the video "{title}".
Check: hook strength in the first 5 seconds, retention (reveals/open loops), specificity (no vague filler), accuracy red flags, repetition, AI clichés, spoken naturalness for TTS, on-brand voice (channel bible), escalation, ending payoff, and the forbidden phrases.

Return JSON: {{"score": 1-10, "issues": [{{"part": <index>, "problem": "...", "fix": "precise rewrite instruction"}}]}}
Only list real, important issues (max 6). If a part is good, don't list it.

SCRIPT:
{numbered}"""
    data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                        model=ai.text_model(), reasoning="medium", timeout=300)
    issues = [i for i in (data.get("issues") or []) if isinstance(i, dict) and isinstance(i.get("part"), int)]
    return {"score": data.get("score"), "issues": issues}


def rewrite_part(ch, title, parts, idx, fixes, budget=None):
    heading, text = parts[idx]
    budget = int(budget or len(text.split()))
    before = parts[idx - 1][1][-500:] if idx > 0 else ""
    after = parts[idx + 1][1][:300] if idx + 1 < len(parts) else ""
    prompt = f"""Rewrite this part of the script for "{title}" ({heading or 'HOOK'}), applying these fixes:
- """ + "\n- ".join(fixes) + f"""

Keep the same role in the story. LENGTH: {int(budget * 0.9)}-{int(budget * 1.1)} words (hard limit) — if a fix adds material, cut weaker details elsewhere. It must still connect with the text before and after.
BEFORE: \"\"\"{before}\"\"\"
PART TO REWRITE: \"\"\"{text}\"\"\"
AFTER: \"\"\"{after}\"\"\"

Output only the rewritten narration text."""
    return _clean(ai.chat([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                          model=ai.text_model(), reasoning="medium", timeout=300))


def fit_part(ch, heading, text, budget):
    """Condense / étoffe une partie pour tenir son budget de mots."""
    n = len(text.split())
    verb = "Condense" if n > budget else "Expand (with concrete, accurate details — no filler)"
    prompt = (f"{verb} this part of a voiceover script to {int(budget * 0.93)}-{int(budget * 1.07)} words "
              f"(currently {n}). Keep the voice, the strongest facts, the first sentence's hook and the last "
              f"sentence's transition. Output only the narration text.\n\nPART ({heading or 'HOOK'}):\n{text}")
    return _clean(ai.chat([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                          model=ai.text_model(), reasoning="low", timeout=240))


def fit_length(ch, parts, budgets, tolerance=0.15):
    """Si le total s'écarte de >15 % de la cible, recale les parties les plus hors budget."""
    total, target = sum(len(t.split()) for _, t in parts), sum(budgets)
    if not target or abs(total - target) <= tolerance * target:
        return parts
    idxs = [i for i, (_, t) in enumerate(parts)
            if budgets[i] and abs(len(t.split()) - budgets[i]) > max(12, 0.15 * budgets[i])]
    out = list(parts)
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {i: ex.submit(fit_part, ch, parts[i][0], parts[i][1], budgets[i]) for i in idxs}
        for i, fut in futs.items():
            try:
                new = fut.result()
                if len(new.split()) >= 0.5 * budgets[i]:
                    out[i] = (parts[i][0], new)
            except Exception:
                pass
    return out


# ── Pipeline complet ────────────────────────────────────────────────────────

def compose(parts):
    """[(heading, text)] → texte éditable avec lignes « ## heading »."""
    out = []
    for h, t in parts:
        if h:
            out.append("## " + h)
        out.append(t.strip())
        out.append("")
    return "\n".join(out).strip() + "\n"


def parse(script_text):
    """Texte éditable → [(heading, text)]. Les lignes « ## » sont des titres de section."""
    parts, heading, buf = [], "", []
    for ln in (script_text or "").splitlines():
        s = ln.strip()
        if s.startswith("## ") or (s.startswith("#") and len(s) > 1 and not s.startswith("#hashtag")):
            if any(x.strip() for x in buf) or heading:
                parts.append((heading, "\n".join(buf).strip()))
            heading, buf = s.lstrip("#").strip(), []
        else:
            buf.append(ln)
    if any(x.strip() for x in buf) or heading:
        parts.append((heading, "\n".join(buf).strip()))
    return [(h, t) for h, t in parts if t]


def narration(script_text):
    return re.sub(r"\s+", " ", " ".join(t for _, t in parse(script_text))).strip()


def word_count(text):
    return len((text or "").split())


def generate(ch, title, minutes, notes="", polish=True, progress=None):
    """Script complet. progress(pct, message, partial_script_or_None)."""
    def step(p, m, partial=None):
        if progress:
            progress(p, m, partial)

    step(0.03, "Plan de la vidéo (hook, sections, beats)…")
    ol = outline(ch, title, minutes, notes)
    total = len(ol["sections"]) + 1
    budgets = [int(ol["hook"].get("target_words") or 60)] + [int(x.get("target_words") or 180) for x in ol["sections"]]
    parts = []
    tail = ""
    for i in range(-1, len(ol["sections"])):
        label = "le hook" if i < 0 else f"la section {i + 1}/{len(ol['sections'])} — {ol['sections'][i]['heading']}"
        step(0.10 + 0.65 * (i + 1) / total, f"Écriture de {label}…", compose(parts) if parts else None)
        text = write_section(ch, ol, i, tail)
        parts.append(("" if i < 0 else ol["sections"][i]["heading"], text))
        tail = text[-600:]
    step(0.78, "Relecture par le script doctor…", compose(parts))
    report = {"score": None, "issues": []}
    if polish:
        try:
            report = review(ch, ol["title"], parts)
            by_part = {}
            for iss in report["issues"]:
                if 0 <= iss["part"] < len(parts):
                    by_part.setdefault(iss["part"], []).append(f"{iss.get('problem', '')} → {iss.get('fix', '')}")
            if by_part:
                step(0.85, f"Réécriture de {len(by_part)} partie(s) signalée(s)…", compose(parts))
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {idx: ex.submit(rewrite_part, ch, ol["title"], list(parts), idx, fixes, budgets[idx])
                            for idx, fixes in by_part.items()}
                    for idx, fut in futs.items():
                        try:
                            new = fut.result()
                            if word_count(new) > 0.5 * word_count(parts[idx][1]):
                                parts[idx] = (parts[idx][0], new)
                        except Exception:
                            pass
        except Exception as e:  # la relecture est un bonus : jamais bloquante
            report = {"score": None, "issues": [], "error": str(e)}
    total_words = sum(len(t.split()) for _, t in parts)
    if abs(total_words - sum(budgets)) > 0.15 * sum(budgets):
        step(0.93, f"Ajustement de la longueur ({total_words} → ~{sum(budgets)} mots)…", compose(parts))
        parts = fit_length(ch, parts, budgets)
    script = compose(parts)
    step(1.0, "Script prêt.", script)
    return {"title": ol["title"], "outline": ol, "script": script, "review": report,
            "words": word_count(narration(script))}


def rewrite_selection(ch, script_text, instruction):
    """Réécrit tout le script selon une consigne libre (« plus drôle », « raccourcis le niveau 3 »...)."""
    prompt = f"""Here is a full voiceover script (lines starting with "## " are section headings — keep that format and keep headings unless asked otherwise).
Apply this instruction from the creator: {instruction}
Return the COMPLETE updated script in the same format, nothing else.

SCRIPT:
{script_text}"""
    out = ai.chat([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                  model=ai.text_model(), reasoning="medium", timeout=400)
    out = re.sub(r"^```\w*|```$", "", out.strip()).strip()
    return out + "\n"


def metadata(ch, title, script_text):
    """Titre, description SEO, tags — pour la publication."""
    lang = (ch.get("language") or "fr").lower()
    prompt = f"""Write YouTube publishing metadata in {lang_label(lang)} for this video.
Working title: {title}
Return JSON: {{"titles": ["5 alternative high-CTR titles, max 70 chars"], "description": "SEO description: 2-line hook, 1 paragraph summary, chapters are NOT needed, 3-5 hashtags at the end", "tags": ["15 tags"]}}

SCRIPT (excerpt):
{narration(script_text)[:5000]}"""
    return ai.chat_json([{"role": "system", "content": _channel_block(ch)}, {"role": "user", "content": prompt}],
                        model=ai.fast_model())


def dumps(o):
    return json.dumps(o, ensure_ascii=False)
