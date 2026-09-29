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

Avec le pack FacelessOS (skills/facelessos), le pipeline suit sa méthode :
Research (brief) → Brainstorm (3 hooks notés contre la vidéo de référence et les
dernières vidéos de la chaîne) → Structure (plan + boucles + rotation) → Write
(ancré sur un extrait VERBATIM de la vidéo de référence) → Greenlight (audit A-E
+ scanner d'origine, en boucle jusqu'à une passe propre).

Les sections sont séparées dans le texte final par des lignes « ## Titre » :
elles ne sont PAS lues par la voix off mais servent aux titres à l'écran.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from services import ai
from services import facelessos as FOS

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
    "pov_marry": {
        "name": "POV: You Marry / Fall in Love With… (vie de couple)",
        "desc": "« POV: You Marry a Russian Woman », « POV: You Fall in Love with a Female Yakuza » — une histoire d'amour racontée en « you », de la première rencontre à la dernière scène (façon Oddly Specific Lives).",
        "heading": "a short time-stamp or event label used for structure only, never spoken (e.g. \"3 weeks later\", \"The rooftop\", \"Her mother's verdict\")",
        "structure": """ONE continuous second-person narration ("you"), PRESENT TENSE, chronological. No host, no intro, no "in this video", no spoken chapter titles, no CTA, no outro. The title carries the premise: never restate it, and delay the label itself for a couple of minutes.
- "YOU": an unnamed, ordinary guy, out of his depth, honest; he barely speaks and his lines are short. Give him one or two concrete, ordinary worries early (rent, a job, a broken nose).
- "HER": competent and specific, never a prop. Show who she is through what she does and how others react to her. Later ONE private vulnerability and ONE crisis. She chooses you; you do not rescue her.
- FOLLOW THE CHANNEL'S REFERENCE ANALYSIS (style bible) for the hook shape, beat map, dialogue density and ending. It is the proven model for this format.
- Scenes, not summaries: named real places, a time of day, weather or light, one telling physical detail, then short loaded dialogue that carries the turn.
- Move time inside the narration ("It takes 3 weeks", "Three months in", "Year two is different"), never with headings.
- Plant 2-3 physical motifs early (an object, a ritual, the city, hands) and pay them off; the last line returns to the opening image.
- "Marry" titles reach the proposal or wedding by ~60% and then show married life; "Fall in Love" titles stop at commitment. Danger premises keep real stakes; warm culture premises put the stakes in her family, customs and distance.
- ENDING: a small, quiet two-person scene with 2-4 lines of dialogue, then a last physical image. Never summarize the video.""",
    },
    "business_explained": {
        "name": "How X Actually Makes Money (business expliqué)",
        "desc": "« How Pawn Shops Actually Make Money », « The Economics of Money Laundering » — le vrai modèle économique caché d'un business (façon Marcus Explains).",
        "heading": "short chapter title (2-5 words) — used for structure only",
        "structure": """BUSINESS-MODEL EXPLAINER: one calm narrator explains a money machine to a smart friend. Arc: simple version → hidden levers → the math → twist → origin/famous case → dark side → the piece that ties it together → callback.
- HOOK (no heading, ~7% of the words, done before 1:45): sentence one is EITHER a hard, sourced number that sounds impossible ("A money launderer charges about 8% on every dirty dollar.") OR a real named person in a named place and year. Then within 20 seconds the contradiction ("if that picture were right, this whole business should be dead"), name the common belief and kill it, say the real answer "has almost nothing to do with" the obvious product (matches the "(It's Not X)" title), one scale number as proof, and end with "By the end of this, you'll understand..." + 2-4 open loops, at least one dark or aimed at the viewer ("...and why the person paying for it is almost certainly you"). No greeting, no channel name, no CTA in the hook.
- MASTER ANALOGY: within the first two minutes introduce ONE everyday system that maps the whole business (washing machine, theme-park wristband, vending machine). Call back to it 3+ times, "upgrade" it when new facts arrive, reuse it in the ending.
- SECTIONS in this order (share of the runtime): restatement + master analogy "the simple version" (8%) → core mechanics: 2-3 cost/revenue levers, each with a hard number (14%) → unit math: walk through ONE customer / plate / store / transaction with round numbers ("Say the buffet charges $20."), then scale it up (7%) → short recap + CTA #1 (2%) → the hidden lever(s) most people miss (18%) → the twist: why it's thinner, riskier or weirder than it looks (6%) → origin story or famous case/scandal (7%) → dark side / who really pays: workers, towns, customers, regulators, with numbers, stated flatly, never moralizing (16%) → recap + CTA #2 (2%) → the piece that ties it all together, "here's where it all connects" (8%) → ending (5%).
- Before each big pivot, recap the previous points in ONE list sentence ("Now, if the story ended there, ... But here's the detail everyone missed."). Plant a re-hook every 2-3 minutes ("What comes next is the part that still doesn't make sense.").
- NUMBERS in nearly every paragraph. Name the source inside the sentence (institution, year, sample: "A 2025 study of 88 federal cases..."). Only use figures you are confident are real (company filings, government data, well-known studies, press); round them; if unsure, use a clearly hypothetical worked example instead of inventing a statistic. Turn every percentage into a human unit ("for every $1,000... about $2", "one diner in 20"). Put fines next to revenue ("0.028% of revenue. For a business this size, that's a parking ticket."). Repeat a shocking figure as a fragment: "95%." "Three times."
- STAGING (the video is illustrated scene by scene): write drawable beats — objects, routes, chains of shell companies, a weekday afternoon, a town and its population. Real people get one-line verbatim quotes; otherwise use archetypes ("the grandmother who has soup and a roll"). Put the viewer inside the machine ("Walk into a casino with $50,000 in cash..."). Do not invent named fictional characters.
- RHYTHM: ~14 words per sentence on average; a long explanation followed by a 2-5 word punch. Triplets ("They have methods. They have infrastructure. They have a fee."), "That's not X. That's Y." (max 3 times), sentences opening with And / But / So / Now. Max ~5 rhetorical questions in the whole video, each answered at once. Humor: dry one-liners only, none on criminal topics.
- CTA #1 (~6 min) and CTA #2 (~16-20 min): one sentence each, "If this is already changing how you see X, subscribe, because the next part is where Y." Never ask for likes/subs in the first 5 minutes.
- ENDING: recap every mechanism in one list ("That is the machine."), return to the opening number/person/image, widen it to a general law, land a one-sentence kicker, then "Tell me where you're watching from in the comments, and if this changed how you see X, subscribe." Stop. No "see you next time".""",
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
           "smash that like button", "without further ado", "fascinating", "realm", "intricate",
           "welcome back", "deep dive", "let's break it down", "here's the kicker", "plot twist", "fast forward",
           "little did they know", "studies show", "experts say", "let that sink in", "mind-blowing",
           "at the end of the day", "navigate the complexities", "landscape", "grab your popcorn",
           "little did you know", "whirlwind romance", "two worlds collide", "clash of cultures",
           "love knows no borders", "vibrant culture", "your heart skips a beat", "and the rest is history",
           "happily ever after", "wouldn't have it any other way", "wouldn't change a single thing"],
    "fr": ["plongeons", "plongez", "dans cette vidéo", "accrochez-vous", "sans plus attendre",
           "il est important de noter", "en conclusion", "incontournable", "fascinant", "un véritable voyage",
           "au cœur de", "n'hésitez pas", "que vous soyez", "imaginez un monde où", "la réponse va vous surprendre",
           "restez jusqu'à la fin", "attachez vos ceintures", "force est de constater", "en somme"],
}

MACHINE_BANS = ("let's dive / dive into, let's break this down, without further ado, let's unpack, let's jump in, "
                "buckle up, here's the kicker, in today's world / day and age, delve, tapestry, unleash, robust, "
                "game-changer, evolving / digital / modern / competitive landscape")

UNIVERSAL_RULES = """WRITING RULES (non-negotiable — FacelessOS):
- This is a VOICEOVER script: write only what the narrator says out loud. No stage directions, no [brackets], no emojis, no markdown, no bullet points, no scene descriptions.
- Speech, not prose: build every sentence in shapes a narrator actually says. If a VOICE ANCHOR sample is given, it is the reference for sentence shapes: borrow its register, never its content, lines, plot or hooks.
- Write contractions (it's, don't, you're). NEVER use em dashes or en dashes (use a period, a comma, or the word the dash hides). No curly quotes, no ellipsis character.
- Sentence one is a jolt, not homework and not a greeting: no "in this video", no channel name. Open a loop the viewer needs closed.
- Every join between beats reads as "but" or "therefore", never "and then". A rehook or turn every 30-45 seconds, a payoff every 60-90 seconds, and the next question opens within 10 seconds of each payoff.
- Be SPECIFIC: real names, places, times, sensory details. Real-world facts must be accurate and widely documented; never invent statistics or sources. Story details may be invented when the format is a story.
- Vary sentence length (short punches between longer flowing sentences), and never repeat the same fact, phrase or opener without adding something new.
- Never write: {machine}. Also avoid: {banned}.
- Avoid the AI tells: "No X. No Y. No Z." drumbeats, "Most people..." openers, more than one "it's not X, it's Y" per script, empty emphasis words (powerful, game-changing, transformational), guru lines ("Let that sink in", "Here's the truth no one talks about"), staged candor ("Honestly?"), "-ing" padding clauses, significance inflation ("a pivotal moment"), movie-trailer beats ("One X. Then ten. Then..."), wise-narrator verdicts closing paragraphs.
- Write numbers the way they are spoken naturally in the target language (digits are fine for years and big numbers)."""


def lang_label(code):
    return LANGS.get((code or "fr").lower(), f"the language with ISO code '{code}' (natural spoken)")


def _banned(code):
    words = BANNED.get(code, []) + (BANNED["en"] if code != "en" else [])
    return ", ".join(f'"{w}"' for w in words)


def voice_anchor(ch):
    """Extrait parlé VERBATIM de la vidéo de référence (voice anchoring), '' sans référence."""
    return FOS.anchor(ch.get("reference_scripts") or "")


def _channel_block(ch):
    """Contexte de chaîne injecté dans tous les prompts d'écriture."""
    parts = [f"CHANNEL: {ch.get('name') or 'Untitled channel'}"]
    for key, label in (("niche", "Niche"), ("audience", "Target audience"), ("tone", "Narrator & tone"),
                       ("rules", "Channel rules (must follow)"), ("cta", "Call-to-action (one, woven in mid-video, short)")):
        if (ch.get(key) or "").strip():
            parts.append(f"{label}: {ch[key].strip()}")
    if (ch.get("bible") or "").strip():
        parts.append("REFERENCE ANALYSIS / CHANNEL STYLE BIBLE (derived from the reference video of this format — "
                     "follow its hook shape, beat map, rhythm and ending):\n" + ch["bible"].strip())
    anc = voice_anchor(ch)
    if anc:
        parts.append("VOICE ANCHOR — verbatim spoken narration from the channel's reference video. This is the shape "
                     "test reference: every sentence you write must use sentence shapes this narrator uses. Borrow "
                     "the register only; never reuse its plot, lines, images or hooks.\n\"\"\"\n" + anc + "\n\"\"\"")
    elif not (ch.get("bible") or "").strip():
        parts.append("No reference video for this format: stay in the channel's narration theme (tone and rules above).")
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
        + UNIVERSAL_RULES.format(banned=_banned(lang), machine=MACHINE_BANS)
    )


def target_words(ch, minutes):
    wpm = float(ch.get("wpm") or 150)
    return max(80, int(round(float(minutes) * wpm)))


# ── 1. Bible de chaîne ──────────────────────────────────────────────────────

def build_bible(ch, reference_text):
    """Analyse de la vidéo de référence (méthode FacelessOS « competitor transcript analysis »)."""
    lang = (ch.get("language") or "fr").lower()
    st = FOS.text_stats(reference_text)
    prompt = f"""Use the FacelessOS methodology to analyze this transcript from a top-performing video of the format this channel makes. Apply the retention mechanics, hook patterns and structure frameworks. Write a REFERENCE ANALYSIS that another writer will follow for every new script of this channel.

Measured on the transcript: {st['words']} words, {st['sentences']} sentences, {st['avg']} words per sentence on average, {st['short_pct']}% of sentences of 1-4 words, {st['long_pct']}% of 25+ words, {st['dialogue_lines']} quoted dialogue lines.

Write it in {lang_label(lang)}, max ~500 words, as short labeled paragraphs (FORMAT, HOOK, BEAT MAP, VOICE, DIALOGUE, TRANSITIONS, MOTIFS, ENDING, AVOID):
1. HOOK: how sentence one lands, what the first ~45 seconds do (context lean, jolt, turn, promise), the word count, when the premise's label is first said.
2. BEAT MAP: the sections as shares of runtime (0-18%, ...) with what each one does and where the emotional turns are.
3. VOICE: person, tense, sentence rhythm (use the measured numbers), recurring devices (similes, understatement, numbers), 3-4 short verbatim example shapes quoted from the transcript.
4. DIALOGUE, TRANSITIONS and time jumps: how they are handled, with short quoted examples.
5. MOTIFS and CALLBACKS, and how the ending lands.
6. AVOID: what not to copy. The reference teaches style, never content (no plot, lines or hooks reused), and FacelessOS rules win on any conflict: at most 2 antithesis constructions and 1 aphoristic closer per script, no em dashes, no trailer voice.
Output ONLY the analysis text.

REFERENCE TRANSCRIPT:
\"\"\"
{reference_text[:14000]}
\"\"\""""
    return ai.chat(prompt, model=ai.text_model(), reasoning="medium", timeout=300).strip()


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

def outline(ch, title, minutes, notes="", brief=None, hook=None, avoid=None):
    """Plan. Avec FacelessOS : part du brief (STEP 0) et du hook retenu, planifie les boucles,
    les motifs, le grand payoff annoncé 3 fois et les choix de rotation."""
    words = target_words(ch, minutes)
    fmt = _format(ch)
    n_sections = max(3, min(14, round(words / 190)))
    lang = (ch.get("language") or "fr").lower()
    fos = ""
    if brief is not None and FOS.available():
        hook_block = ("APPROVED HOOK (the video opens with it verbatim; plan the sections that follow it):\n<<<\n"
                      + hook + "\n>>>") if hook else ""
        fos = f"""
RESEARCH BRIEF (STEP 0 — build from it, never contradict it):
{brief_text(brief)}
{hook_block}

STRUCTURE REQUIREMENTS (FacelessOS — script-structures, retention-mechanics, outro-psychology):
- 3-act frame: Departure 15-20%, Initiation 60-70%, Return 15-20%, inside the channel's reference beat map.
- Dopamine ladder: the hook opens the main question; each section builds anticipation, closes a loop with a non-obvious payoff and opens the next loop within 10 seconds. No loop left open at the end; no loop closes without the next one opening (until the final payoff).
- The grand payoff is foreshadowed 3 times (the hook, ~30%, ~60%) and lands as the culmination of everything before it.
- Every join between sections reads as BUT or THEREFORE, never AND THEN. Each paragraph delivers new information, progress, an obstacle or an emotional change.
- 2-3 physical motifs planted in the first 20% and paid off; the ending returns to the opening image.
- Ending architecture: the script ends AT the final payoff. No wind-down, no summary, no outro scent.
- The first sentence after the hook pays or escalates, never orients ("To understand why..." is forbidden before a payoff).

VARIETY ROTATION (variety-rotation-skill.md): pick one option per slot and log it. Adapt each pick to this format's narration (second person, present tense for POV); the options are moves, not lines to paste. Do NOT reuse these picks from the channel's last scripts: {avoid or 'none logged yet'}.
{_rotation_banks()}
"""
    prompt = f"""Create the detailed outline of a {minutes}-minute video (≈{words} spoken words in total).

TITLE: {title}
{('EXTRA INSTRUCTIONS FROM THE CREATOR: ' + notes) if notes else ''}
{fos}
Plan about {n_sections} sections after the hook (adapt to the format). Section heading style: {fmt['heading']} — headings in {lang_label(lang)}.
For each section give the beats (the concrete facts, scenes, numbers and twists it will contain — be specific, this is where the research happens), its emotional beat, the loop it closes and the loop it opens, and a word budget. The budgets must add up to ≈{words} words including the hook.

Return JSON:
{{
  "title": "final title",
  "hook": {{"beats": ["..."], "target_words": 60}},
  "sections": [{{"heading": "...", "beats": ["...", "..."], "emotion": "...", "closes": "loop it pays off", "opens": "loop it opens", "exit": "how it hands off to the next section (rotation pick)", "target_words": 180}}],
  "promise": "the one promise the hook makes",
  "payoff": "the grand payoff and where it lands",
  "foreshadow": ["where and how the payoff is foreshadowed"],
  "motifs": ["motif: planted where -> paid off where"],
  "rotation": {{"slot1": "", "slot2": [], "slot4": [], "slot6": [], "slot7": "", "slot8": "", "slot9": ""}},
  "ending": "how the last section lands (callback / final image)"
}}"""
    data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                        model=ai.text_model(), reasoning="medium", timeout=300)
    secs = [s for s in (data.get("sections") or []) if isinstance(s, dict) and s.get("heading")]
    if not secs:
        raise ai.AIError("Le plan renvoyé est vide — relance.")
    hook_d = data.get("hook") if isinstance(data.get("hook"), dict) else {"beats": [], "target_words": 60}
    if hook:
        hook_d["target_words"] = word_count(hook)
    # budgets recalés pour que leur somme = cible (le modèle arrondit souvent large)
    raw = [int(hook_d.get("target_words") or 50)] + [int(x.get("target_words") or 150) for x in secs]
    scale = (words - (raw[0] if hook else 0)) / float((sum(raw[1:]) if hook else sum(raw)) or 1)
    if not hook:
        hook_d["target_words"] = max(25, round(raw[0] * scale))
    for x, r in zip(secs, raw[1:]):
        x["target_words"] = max(30, round(r * scale))
    out = {"title": data.get("title") or title, "hook": hook_d, "sections": secs, "ending": data.get("ending", ""),
           "target_words": words}
    for k in ("promise", "payoff", "foreshadow", "motifs", "rotation"):
        if data.get(k):
            out[k] = data[k]
    return out


def _outline_text(ol):
    lines = [f"TITLE: {ol['title']}", "HOOK: " + " | ".join(ol["hook"].get("beats") or [])]
    for i, s in enumerate(ol["sections"], 1):
        lines.append(f"{i}. {s['heading']} ({s.get('target_words', '?')} words): " + " | ".join(s.get("beats") or []))
    if ol.get("ending"):
        lines.append("ENDING: " + ol["ending"])
    for k, lab in (("promise", "PROMISE"), ("payoff", "GRAND PAYOFF"), ("foreshadow", "FORESHADOW"), ("motifs", "MOTIFS")):
        v = ol.get(k)
        if v:
            lines.append(f"{lab}: " + (" | ".join(map(str, v)) if isinstance(v, list) else str(v)))
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
        extra = "".join(f" {lab}: {s[k]}." for k, lab in (("emotion", "Emotional beat"), ("closes", "Loop it pays off"),
                                                              ("opens", "Loop it opens"), ("exit", "Hand-off"))
                        if s.get(k))
        what = (f"section {idx + 1}/{len(ol['sections'])} \"{s['heading']}\". Beats: " + " | ".join(s.get("beats") or [])
                + "." + extra
                + f" LENGTH: {int(n * 0.9)}-{int(n * 1.1)} words (hard limit — pick the strongest beats if they don't all fit)."
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


# ── FacelessOS : Research → Brainstorm → Greenlight ────────────────────────

FORMAT_NOTES = """HOW FACELESSOS APPLIES TO THIS TOOL (read before any check):
- Output mode = clean TTS prose (Vidrush-like): every word is spoken by an AI voice over AI images. Lines starting with "## " are structure labels, never spoken: ignore them in every check. There are no [VISUAL] cues and there must be no brackets, timestamps or stage directions in the spoken copy.
- Story formats (POV stories, "your life if", fiction) run in FacelessOS Fiction Mode: invented story events, people and in-story numbers ("It takes 3 weeks", "28 years old") are fiction and are NOT D5 findings. D5 and the verify-or-cut rule apply to real-world claims only (customs, history, places, laws, statistics): each must be accurate and widely documented, otherwise cut or soften it. A real-world statistic that is not common knowledge is a finding.
- Checks written for documentaries are graded by their intent: C4 (perspective shift) = the viewer's picture of the premise at the end differs from the one they arrived with; E1 "specific sourcing" and "original research" = correct, specific real-world detail beyond the obvious clichés; E1 "human review" scores 0 until the creator edits the script. A check that genuinely cannot apply is N/A, never a failure.
- The channel's own rules win on channel conventions: if the channel says "no CTA", a missing CTA is not a finding (the ending architecture still applies: end at the final payoff).
- The reference video is the voice anchor for D1/D4 and the comparison hook for A4 (quote its opening). Shapes it uses pass the shape test, EXCEPT where FacelessOS caps them (D7 thresholds, machine bans, em dashes).
- Length: the spoken word count must stay within ±20% of the target."""


def brief_text(brief):
    if not brief:
        return "(no brief)"
    lines = [f"TOPIC: {brief.get('topic', '')}", f"ANGLE: {brief.get('angle', '')}", "PROOF BANK:"]
    for it in brief.get("proof_bank") or []:
        if isinstance(it, dict):
            lines.append(f"→ {it.get('item', '')} ({it.get('basis', '')})")
        else:
            lines.append(f"→ {it}")
    lines += [f"HOOK DIRECTION: {brief.get('hook_direction', '')}", f"STRUCTURE HINT: {brief.get('structure_hint', '')}"]
    return "\n".join(lines)


def _rotation_banks():
    txt = FOS.skill("variety-rotation-skill.md")
    keep = [FOS.section("variety-rotation-skill.md", "Rotation Guardrails")]
    for h in ("SLOT 1:", "SLOT 2:", "SLOT 4:", "SLOT 6:", "SLOT 7:", "SLOT 8:", "SLOT 9:", "CROSS-SCRIPT RULES"):
        keep.append(FOS.section("variety-rotation-skill.md", h))
    return "\n\n".join(k for k in keep if k) if txt else ""


def research_brief(ch, title, minutes, notes=""):
    """STEP 0 (research-and-ideation-skill.md) : le brief à 5 champs, sans navigation web."""
    parts = [FOS.section("research-and-ideation-skill.md", "Angle mining", 2),
             FOS.section("research-and-ideation-skill.md", "The verify-or-cut rule", 3),
             FOS.section("research-and-ideation-skill.md", "The output contract", 2)]
    prompt = f"""Run the FacelessOS research front-end for this video and produce the five-field brief. The skill text is below; run it from the open file.

VIDEO TITLE: {title}  ({minutes} minutes)
{('CREATOR NOTES: ' + notes) if notes else ''}

CONSTRAINTS OF THIS TOOL: there is no web browsing here. The PROOF BANK may only hold facts you are certain are accurate and widely documented; give the kind of source that documents each one (e.g. "standard Filipino wedding custom, covered by the Philippine National Commission for Culture and the Arts"). Never guess a number or a source: an uncertain item is cut, not softened into a guess. For story formats (POV stories), the PROOF BANK holds the real-world specifics the story will stand on (customs, rituals, foods, words, places, laws, history of the setting), 6-10 items, and the ANGLE is the story's non-obvious take on the premise (write the default sentence first, run all four frames, keep the winner).

SKILL (research-and-ideation-skill.md):
{chr(10).join(p for p in parts if p)}

Return JSON:
{{"default_sentence": "...", "frames": {{"contrarian": "...", "hidden_cost": "...", "untold_story": "...", "mechanism_reveal": "..."}},
  "topic": "...", "angle": "winning frame + the take", "proof_bank": [{{"item": "...", "basis": "kind of source that documents it"}}],
  "hook_direction": "which item or story moment leads + the tension it plants", "structure_hint": "..."}}"""
    data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                        model=ai.text_model(), reasoning="medium", timeout=300)
    if not data.get("angle"):
        raise ai.AIError("Brief de recherche vide — relance.")
    return data


def _reference_opening(ch, words=110):
    anc = voice_anchor(ch)
    if not anc:
        return ""
    return " ".join(anc.split("[...]")[0].split()[:words])


def hook_options(ch, title, minutes, brief, history=None):
    """Brainstorm : 3 hooks sur 3 ouvertures différentes, notés contre la référence (A4) et
    contre les dernières vidéos de la chaîne (diff de bibliothèque) → le meilleur."""
    total = target_words(ch, minutes)
    n = max(60, min(130, round(total * 0.06)))
    past = [h for h in (history or []) if h.get("hook")]
    past_txt = "\n".join(f'- "{h["title"]}": "{h["hook"]}"' + (f' (rotation: {h["rotation"]})' if h.get("rotation") else "")
                         for h in past[:3]) or "- (no previous scripts on this channel)"
    ref = _reference_opening(ch)
    skills = "\n\n".join(x for x in (
        FOS.section("faceless-scripts-os-master.md", "CRITICAL: Conversational Flow"),
        FOS.section("REAL-FACELESS-HOOK-SWIPE.md", "How to use these in v5"),
        FOS.section("REAL-FACELESS-HOOK-SWIPE.md", "THE 4 HOOK MISTAKES"),
        FOS.section("greenlight-audit-skill.md", "Group A - Hook"),
        FOS.section("variety-rotation-skill.md", "SLOT 9:"),
        FOS.section("voice-anchoring-skill.md", "The four written-not-spoken tells")) if x)
    prompt = f"""STEP 2 of FacelessOS: write 3 different hooks for this video, grade them, keep the best. Run from the skill text below.

VIDEO TITLE: {title}
RESEARCH BRIEF:
{brief_text(brief)}

HOOK LENGTH: {n - 15}-{n + 10} words each (the whole cold open up to its button line).
COMPARISON HOOK FOR A4 (the proven winner of this format, verbatim — beat it on its own merits, never copy it):
<<<
{ref or '(no reference video: grade against the swipe files)'}
>>>
CHANNEL-LIBRARY DIFF (variety-rotation guardrail 2): the new hook must open on a DIFFERENT move and a DIFFERENT through-concept than these recent hooks, not just different wording:
{past_txt}

Rules: each option uses a different opening move and a different hook turn (Slot 9). Sentence one is a jolt that already contains the video's best tension. Speech, not trailer voice: every sentence must be a shape the VOICE ANCHOR narrator uses. No em dashes.

SKILLS:
{skills}

Return JSON:
{{"options": [{{"move": "opening move in a few words", "slot9": "e.g. 9C", "text": "the full hook"}}],
  "grades": [{{"option": 0, "scroll_stop": "yes/no + why", "sayable": "yes/no + why", "beats_reference": "yes/no + why", "differs_from_library": "yes/no"}}],
  "winner": 0, "why": "one sentence"}}"""
    data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                        model=ai.text_model(), reasoning="high", timeout=360)
    opts = [o for o in (data.get("options") or []) if isinstance(o, dict) and (o.get("text") or "").strip()]
    if not opts:
        raise ai.AIError("Aucun hook proposé — relance.")
    w = data.get("winner")
    w = w if isinstance(w, int) and 0 <= w < len(opts) else 0
    for o in opts:
        o["text"] = FOS.mech_fix(_clean(o["text"]))
    return {"options": opts, "grades": data.get("grades") or [], "winner": w, "why": data.get("why", ""),
            "hook": opts[w]["text"], "slot9": opts[w].get("slot9", ""), "move": opts[w].get("move", "")}


def _audit_skills(half):
    """Texte des skills lu par l'audit (« run from the open file, never from memory »).
    half = "structure" (groupes A, B, C, E) ou "voice" (groupe D)."""
    g = "greenlight-audit-skill.md"
    head = FOS.skill(g).split("## Group A - Hook")[0].strip()
    if half == "structure":
        blocks = [(g + " — rules", head), (g + " — Group A", FOS.section(g, "Group A - Hook")),
                  (g + " — Group B", FOS.section(g, "Group B - Retention")), (g + " — Group C", FOS.section(g, "Group C - Red-Tape")),
                  (g + " — Group E", FOS.section(g, "Group E - Authenticity")),
                  ("retention-mechanics-skill.md", FOS.skill("retention-mechanics-skill.md")),
                  ("faceless-scripts-os-master.md — STEP 4: Transitions & Rehooks",
                   FOS.section("faceless-scripts-os-master.md", "STEP 4: Transitions")),
                  ("outro-psychology-skill.md — The Ending Architecture",
                   FOS.section("outro-psychology-skill.md", "The Ending Architecture"))]
    else:
        blocks = [(g + " — rules", head), (g + " — Group D", FOS.section(g, "Group D - Voice + Anti-slop")),
                  ("humanizer-skill.md", FOS.skill("humanizer-skill.md")),
                  ("voice-anchoring-skill.md", FOS.skill("voice-anchoring-skill.md")),
                  ("faceless-scripts-os-master.md — ANTI-AI SLOP CHECKLIST",
                   FOS.section("faceless-scripts-os-master.md", "ANTI-AI SLOP CHECKLIST"))]
    return "\n\n".join(f"===== {name} =====\n{txt}" for name, txt in blocks if txt)


def _numbered(parts):
    return "\n\n".join(f"[{i}] {h or 'HOOK'}\n{t}" for i, (h, t) in enumerate(parts))


_FIX_SPEC = ('"fixes": [{"n": 1, "check": "e.g. D7", "part": 0, "quote": "exact verbatim text from that part", '
             '"problem": "what fails and which pass condition", "fix": "precise instruction: register translation, never de-clawing"}]')
_HALF_SPEC = {
    "structure": """{"verdict": "PASS" | "FIX-THEN-PASS" | "HOLD",
  "hold_reason": "only for HOLD: the structural problem editing cannot patch",
  "A": {"sentence_one": "verbatim", "hook_words": 0, "turn": "But / However / equivalent", "a4": "graded against the quoted reference opening: won / lost / BLOCKED", "result": "clean or finding"},
  "B": {"loop_ledger": ["question: opens [part] closes [part]"], "result": "clean or finding"},
  "C": {"result": "clean or finding"},
  "promise_map": "hook promises X -> paid in part N",
  "E": {"score": "x/7", "missing": "signals scored 0", "red_flags": 0},
  """ + _FIX_SPEC + "}",
    "voice": """{"verdict": "PASS" | "FIX-THEN-PASS",
  "D": {"anchor": "whose transcript", "shapes_quoted": ["verbatim anchor shape", "..."], "matched_line": "script line = anchor shape", "result": "clean or finding"},
  "D5": ["each real-world number or claim = its basis, or 'no real-world numbers'"],
  "D7": {"antithesis": ["\\"instance\\" (part N)"], "aphorisms": ["\\"instance\\" (part N)"], "floor": FLOOR, "result": "N antithesis, M aphoristic closers; threshold ok or finding"},
  """ + _FIX_SPEC + "}",
}


def _audit_half(ch, half, title, parts, brief, ol, target, words, sc):
    ref = _reference_opening(ch)
    groups = "Groups A, B, C and E (Group D runs in a separate pass)" if half == "structure" else \
             "Group D, checks D1 to D7 (Groups A, B, C and E run in a separate pass)"
    system = (_system(ch) + "\n\n" + FORMAT_NOTES +
              "\n\nYou are now running the FacelessOS v5 GREENLIGHT AUDIT on a finished draft. The skill files are below. "
              "Run every check from this open text, never from memory.\n\n" + _audit_skills(half))
    extra = (f"A4 COMPARISON HOOK (reference video opening, verbatim): {ref or 'none: A4 = BLOCKED unless the swipe files serve'}\n"
             f"PLAN PROMISE / PAYOFF: {(ol or {}).get('promise', '')} / {(ol or {}).get('payoff', '')}\n"
             f"RESEARCH BRIEF:\n{brief_text(brief) if brief else '(none)'}") if half == "structure" else (
             "SCANNER REPORT (trailer-voice-scan.py, run on this draft — D3: fix every HARD-BAN and mechanical hit on "
             "sight; judge the shape flags by D1 against the anchor; the D7 ledger must list at least the floor):\n"
             + FOS.scan_report(sc))
    prompt = f"""Run {groups} of the greenlight audit on the script below. Collect EVERY finding of these groups in this one run: the loop only converges when a run lists all of them, and a finding skipped now costs a whole extra pass. Evidence bar: every finding QUOTES the exact offending text, copied verbatim from ONE part of the script, and names the check it fails; if you cannot quote failing text, there is no finding. Never manufacture a failure the text does not support, and never rubber-stamp: the fields below are the mandatory artifacts (write each ledger by re-reading the script in this pass, then count).

VIDEO TITLE: {title}
TARGET: {target} spoken words (script has {words}; ±20% allowed).
{extra}

SCRIPT (parts numbered [0], [1]...; "HOOK" and headings are labels, not spoken):
{_numbered(parts)}

Return ONLY JSON:
{_HALF_SPEC[half].replace("FLOOR", str(len(sc["floor"])))}
The verdict is PASS only when "fixes" is empty. Number fixes from 1."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    try:
        return ai.chat_json(msgs, model=ai.text_model(), reasoning="high", timeout=600, tries=1)
    except ai.AIError:  # trop long pour le proxy : même audit, raisonnement plus court
        return ai.chat_json(msgs, model=ai.text_model(), reasoning="medium", timeout=600)


def greenlight(ch, title, parts, brief=None, ol=None, minutes=None):
    """Greenlight audit (groupes A-E + scanner d'origine) → verdict structuré.
    Deux passes parallèles (structure A/B/C/E, voix D) pour rester sous les délais du proxy."""
    sc = FOS.scan(parts)
    words = sum(word_count(t) for _, t in parts)
    target = (ol or {}).get("target_words") or (target_words(ch, minutes) if minutes else words)
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {h: ex.submit(_audit_half, ch, h, title, parts, brief, ol, target, words, sc) for h in ("structure", "voice")}
        halves = {h: f.result() for h, f in futs.items()}
    data = {}
    for h in ("structure", "voice"):
        for k, v in halves[h].items():
            if k not in ("fixes", "verdict"):
                data[k] = v
    hold = halves["structure"].get("verdict") == "HOLD"
    fixes = []
    for f in (halves["structure"].get("fixes") or []) + (halves["voice"].get("fixes") or []):
        if not isinstance(f, dict):
            continue
        try:
            i = int(f.get("part"))
        except (TypeError, ValueError):
            continue
        q = (f.get("quote") or "").strip().strip('"')
        if not (0 <= i < len(parts)) or not q:
            continue
        # règle de preuve : la citation doit exister dans la partie (sinon pas de finding)
        if _norm_q(q) not in _norm_q(parts[i][1]):
            hit = [j for j, (_, t) in enumerate(parts) if _norm_q(q) in _norm_q(t)]
            if not hit:
                continue
            i = hit[0]
        f["part"] = i
        f["n"] = len(fixes) + 1
        fixes.append(f)
    # le scanner est une machine : un HARD-BAN restant est toujours un fix
    for i, (_, t) in enumerate(parts):
        for name in FOS.hard_ban_hits(t):
            if not any(x["part"] == i and "HARD" in (x.get("check") or "").upper() for x in fixes):
                fixes.append({"n": len(fixes) + 1, "check": "D3 HARD-BAN", "part": i, "quote": "", "problem": name,
                              "fix": "Remove the machine-banned phrase; say the thing plainly in the anchor's register."})
    data["fixes"] = fixes
    data["verdict"] = "HOLD" if hold else ("PASS" if not fixes else "FIX-THEN-PASS")
    data["scan"] = {k: len(v) for k, v in sc.items()}
    data["words"] = words
    return data


def _norm_q(t):
    return re.sub(r"\s+", " ", (t or "").replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def apply_fixes(ch, title, parts, fixes, budgets=None):
    """Applique les fixes numérotés : retouches chirurgicales (le reste reste mot pour mot),
    réécriture complète de la partie seulement si un fix est structurel."""
    by_part = {}
    for f in fixes:
        by_part.setdefault(f["part"], []).append(f)
    out = list(parts)

    def fix_one(idx, items):
        heading, text = parts[idx]
        n = word_count(text)
        before = parts[idx - 1][1][-400:] if idx > 0 else ""
        after = parts[idx + 1][1][:250] if idx + 1 < len(parts) else ""
        listing = "\n".join(f"Fix {f.get('n', k + 1)} ({f.get('check', '')}): quote «{f.get('quote', '')}» — "
                            f"{f.get('problem', '')} → {f.get('fix', '')}" for k, f in enumerate(items))
        prompt = f"""Apply these greenlight fixes to PART [{idx}] ({heading or 'HOOK'}) of the script for "{title}".
{listing}

Rules (voice-anchoring fix direction): register translation, never de-clawing. The jolt, the proof and the planted tension survive; only the delivery changes. If a fix makes the line weaker, the fix is wrong. Change ONLY what the fixes require: every other sentence stays word for word. No em dashes, contractions on, shapes from the VOICE ANCHOR. Keep the part at {int(n * 0.9)}-{int(n * 1.1)} words.
Prefer local edits. Return JSON: {{"edits": [{{"old": "exact verbatim substring of the part", "new": "replacement"}}], "rewrite": null}}
Only if a fix is structural (a flat stretch that needs a new loop, a missing payoff, a promise the part must now pay), return "rewrite": "<the full rewritten part>" instead.

BEFORE: \"\"\"{before}\"\"\"
PART [{idx}]: \"\"\"{text}\"\"\"
AFTER: \"\"\"{after}\"\"\""""
        data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                            model=ai.text_model(), reasoning="medium", timeout=300)
        new = text
        rw = data.get("rewrite")
        if isinstance(rw, str) and word_count(rw) >= 0.6 * n:
            new = _clean(rw)
        else:
            for e in data.get("edits") or []:
                if not isinstance(e, dict) or not e.get("old"):
                    continue
                old, rep = e["old"], e.get("new") or ""
                if old in new:
                    new = new.replace(old, rep, 1)
                else:  # tolérance sur les espaces / guillemets
                    m = re.search(re.escape(_norm_q(old)).replace(r"\ ", r"\s+"), new, flags=re.I)
                    if m:
                        new = new[:m.start()] + rep + new[m.end():]
        return FOS.mech_fix(new)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {idx: ex.submit(fix_one, idx, items) for idx, items in by_part.items()}
        for idx, fut in futs.items():
            try:
                new = fut.result()
                if word_count(new) >= 0.5 * word_count(parts[idx][1]):
                    out[idx] = (parts[idx][0], new)
            except Exception:  # un fix raté ne bloque pas les autres ; l'audit suivant le reverra
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


def generate(ch, title, minutes, notes="", polish=True, progress=None, history=None, rounds=None):
    """Script complet. progress(pct, message, partial_script_or_None).

    history = dernières vidéos de la chaîne [{title, hook, rotation}] (diff de bibliothèque FacelessOS)."""
    def step(p, m, partial=None):
        if progress:
            progress(p, m, partial)

    if polish and FOS.available():
        return _generate_fos(ch, title, minutes, notes, step, history or [], rounds)
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


CHUNK_WORDS = 950  # sections écrites par blocs consécutifs (FacelessOS : jamais plus de 3 500 mots d'un coup)


def _chunks(ol):
    """Sections consécutives réparties en blocs équilibrés d'au plus ~CHUNK_WORDS mots."""
    secs = ol["sections"]
    total = sum(int(x.get("target_words") or 180) for x in secs)
    k = max(1, min(len(secs), -(-total // CHUNK_WORDS)))
    size = -(-len(secs) // k)
    return [list(range(i, min(i + size, len(secs)))) for i in range(0, len(secs), size)]


def write_sections(ch, ol, idxs, previous_tail):
    """Plusieurs sections consécutives en une seule génération, dans l'ordre, à la suite du texte déjà écrit
    (même voix d'un bout à l'autre, et 3 à 4 fois moins d'allers-retours avec l'IA)."""
    if len(idxs) == 1:
        return [write_section(ch, ol, idxs[0], previous_tail)]
    last = len(ol["sections"]) - 1
    specs = []
    for i in idxs:
        sec = ol["sections"][i]
        n = int(sec.get("target_words") or 180)
        extra = "".join(f" {lab}: {sec[k]}." for k, lab in (("emotion", "Emotional beat"), ("closes", "Loop it pays off"),
                                                            ("opens", "Loop it opens"), ("exit", "Hand-off")) if sec.get(k))
        role = (" This is the LAST section of the video: land the ending (" + (ol.get("ending") or "strong final line")
                + ").") if i == last else (" End with a one-line hook into the next section." if i == idxs[-1] else "")
        specs.append(f"## {sec['heading']}\nBeats: " + " | ".join(sec.get("beats") or []) + "." + extra
                     + f" LENGTH: {int(n * 0.9)}-{int(n * 1.1)} words (hard limit).{role}")
    context = ("END OF THE PREVIOUS PART (continue seamlessly, do not repeat it):\n<<<\n" + previous_tail + "\n>>>"
               if previous_tail else "This is the very beginning of the video.")
    prompt = (f"FULL OUTLINE (for context):\n{_outline_text(ol)}\n\n{context}\n\n"
              f"Now write these {len(idxs)} consecutive sections, in this order, as one continuous voiceover. Start "
              "each one with its heading line exactly as written below (the line beginning with \"## \"), then its "
              "narration only. Respect each length.\n\n" + "\n\n".join(specs))
    raw = ai.chat([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                  model=ai.text_model(), reasoning="medium", timeout=420)
    texts = [t for t in (_clean(b) for b in re.split(r"(?m)^[ \t]*#{1,3}[ \t]+.*$", raw or "")) if t]
    if len(texts) != len(idxs) or any(word_count(t) < 0.4 * int(ol["sections"][i].get("target_words") or 180)
                                      for t, i in zip(texts, idxs)):
        # découpage inattendu : on repasse section par section plutôt que de mal répartir le texte
        out, tail = [], previous_tail
        for i in idxs:
            out.append(write_section(ch, ol, i, tail))
            tail = out[-1][-600:]
        return out
    return texts


def _write_all(ch, ol, hook, step, p0, p1):
    parts = [("", hook)] if hook else []
    tail = hook[-600:] if hook else ""
    idx_groups = _chunks(ol)
    if not hook:
        idx_groups = [[-1]] + idx_groups
    for k, idxs in enumerate(idx_groups):
        names = ", ".join("le hook" if i < 0 else f"{i + 1}" for i in idxs)
        step(p0 + (p1 - p0) * k / max(1, len(idx_groups)),
             f"[Write] Écriture des sections {names} / {len(ol['sections'])}…", compose(parts) if parts else None)
        if idxs == [-1]:
            texts = [write_section(ch, ol, -1, tail)]
        else:
            texts = write_sections(ch, ol, idxs, tail)
        for i, text in zip(idxs, texts):
            parts.append(("" if i < 0 else ol["sections"][i]["heading"], FOS.mech_fix(text)))
        tail = parts[-1][1][-600:]
    return parts


def _generate_fos(ch, title, minutes, notes, step, history, rounds=None):
    """Research → Brainstorm → Structure → Write → Greenlight (boucle jusqu'à une passe propre)."""
    max_rounds = int(rounds or os.getenv("FOS_MAX_ROUNDS") or 3)
    step(0.02, "[Research] Brief : angle, faits réels, direction du hook…")
    brief = research_brief(ch, title, minutes, notes)
    step(0.08, "[Brainstorm] 3 hooks, notés contre la vidéo de référence…")
    hk = hook_options(ch, title, minutes, brief, history)
    avoid = "; ".join(f"{h['title']}: {h['rotation']}" for h in history[:3] if h.get("rotation")) or ""
    step(0.15, "[Structure] Plan, boucles, motifs et rotation…", compose([("", hk["hook"])]))
    ol = outline(ch, title, minutes, notes, brief=brief, hook=hk["hook"], avoid=avoid)
    ol.setdefault("rotation", {})
    if isinstance(ol["rotation"], dict) and hk.get("slot9"):
        ol["rotation"]["slot9"] = hk["slot9"]
    parts = _write_all(ch, ol, hk["hook"], step, 0.20, 0.62)
    budgets = [word_count(hk["hook"])] + [int(x.get("target_words") or 180) for x in ol["sections"]]
    if abs(sum(word_count(t) for _, t in parts) - sum(budgets)) > 0.15 * sum(budgets):
        step(0.63, "[Write] Ajustement de la longueur…", compose(parts))
        parts = [(h, FOS.mech_fix(t)) for h, t in fit_length(ch, parts, budgets)]

    parts, final, runs, verdict = greenlight_loop(ch, ol["title"], parts, brief, ol, minutes, max_rounds, step, 0.65, 0.98)
    if final == "HOLD":
        # HOLD : problème de structure → retour au plan (une fois), puis audit complet depuis le début
        step(0.7, "[Greenlight] HOLD → retour au plan : " + (verdict.get("hold_reason") or "")[:90], compose(parts))
        ol = outline(ch, title, minutes, (notes + "\n" if notes else "") + "The previous draft was put on HOLD by the "
                     "greenlight audit: " + (verdict.get("hold_reason") or "") + " Fix this at the outline level.",
                     brief=brief, hook=hk["hook"], avoid=avoid)
        parts = _write_all(ch, ol, hk["hook"], step, 0.72, 0.85)
        parts, final, more, verdict = greenlight_loop(ch, ol["title"], parts, brief, ol, minutes, max_rounds, step,
                                                      0.86, 0.98)
        runs += [dict(r, round=len(runs) + r["round"]) for r in more]
    script = compose(parts)
    report = {"engine": "facelessos", "verdict": final, "rounds": runs, "block": verdict,
              "brief": brief, "hooks": {k2: hk[k2] for k2 in ("options", "grades", "winner", "why")},
              "files_used": FOS.files_used(),
              # compatibilité avec l'ancien panneau « Relecture IA »
              "score": None, "issues": [{"part": f["part"], "problem": f"{f.get('check', '')}: {f.get('problem', '')}",
                                          "fix": f.get("fix", "")} for r in runs for f in r.get("fixes") or []]}
    step(1.0, f"Script prêt — verdict FacelessOS : {final}.", script)
    return {"title": ol["title"], "outline": ol, "script": script, "review": report,
            "words": word_count(narration(script))}


def greenlight_loop(ch, title, parts, brief=None, ol=None, minutes=None, rounds=3, step=None, p0=0.0, p1=1.0):
    """Boucle de convergence : audit complet → fixes → audit complet… jusqu'à PASS (ou `rounds` passes)."""
    def st(p, m, partial=None):
        if step:
            step(p, m, partial)
    runs, verdict = [], {}
    for k in range(1, rounds + 1):
        p = p0 + (p1 - p0) * (k - 1) / rounds
        st(p, f"[Greenlight] Audit FacelessOS, passe {k} (groupes A-E + scanner)…", compose(parts))
        try:
            verdict = greenlight(ch, title, parts, brief, ol, minutes)
        except Exception as e:
            runs.append({"round": k, "verdict": "ERROR", "error": str(e)[:300], "fixes": []})
            break
        runs.append({"round": k, "verdict": verdict["verdict"], "fixes": verdict["fixes"], "scan": verdict.get("scan"),
                     "words": verdict.get("words"), "hold_reason": verdict.get("hold_reason", "")})
        if verdict["verdict"] in ("PASS", "HOLD") or not verdict["fixes"]:
            break
        st(p + 0.5 * (p1 - p0) / rounds, f"[Greenlight] {len(verdict['fixes'])} fix(es) à appliquer…", compose(parts))
        parts = apply_fixes(ch, title, parts, verdict["fixes"])
    # la passe qui applique des fixes ne s'accorde jamais le PASS : il vient de la passe suivante
    return parts, (runs[-1]["verdict"] if runs else "ERROR"), runs, verdict


def audit_script(ch, title, script_text, minutes=None, rounds=2, progress=None):
    """Greenlight sur un script existant (collé à la main, réécrit sur consigne…)."""
    parts = [(h, FOS.mech_fix(t)) for h, t in parse(script_text)]
    if not parts:
        raise ai.AIError("Script vide.")
    parts, final, runs, verdict = greenlight_loop(ch, title, parts, minutes=minutes, rounds=rounds, step=progress)
    report = {"engine": "facelessos", "verdict": final, "rounds": runs, "block": verdict,
              "files_used": FOS.files_used(), "score": None,
              "issues": [{"part": f["part"], "problem": f"{f.get('check', '')}: {f.get('problem', '')}",
                          "fix": f.get("fix", "")} for r in runs for f in r.get("fixes") or []]}
    return compose(parts), report


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


def _fit_tags(tags, limit=500):
    """Tags dédoublonnés qui tiennent dans le champ YouTube (500 caractères, virgules comprises)."""
    out, seen = [], set()
    for t in tags or []:
        t = re.sub(r"\s+", " ", str(t).replace(",", " ")).strip().lstrip("#")
        if t and t.lower() not in seen and len(", ".join(out + [t])) <= limit:
            out.append(t)
            seen.add(t.lower())
    return out


def package(ch, pr):
    """Kit de mise en ligne (packaging-skill.md) : titre + idées, description, tags, commentaire épinglé,
    dans la voix de la chaîne et calé sur la description de la vidéo de référence."""
    lang = (ch.get("language") or "fr").lower()
    title = pr.get("title") or ""
    script = narration(pr.get("script") or "")
    brief = ((pr.get("review") or {}).get("brief")) or {}
    skills = "\n\n".join(x for x in (
        FOS.section("packaging-skill.md", "The upload kit", 2), FOS.section("packaging-skill.md", "Rules", 2),
        FOS.skill("title-formulas-skill.md"),
        FOS.section("humanizer-skill.md", "Machine tier")) if x)
    desc_anchor = (ch.get("reference_description") or "").strip()
    handle = (ch.get("youtube_handle") or "").strip()
    prompt = f"""Run the FacelessOS packaging step (skill text below, run it from the open file) on this finished video and return the upload kit as JSON. Language: {lang_label(lang)}.

VIDEO TITLE (chosen by the creator, keep it as option 1 exactly): {title}
BRIEF: TOPIC = {brief.get('topic', title)} | ANGLE = {brief.get('angle', '')}
{('WRITTEN-SURFACE ANCHOR — a real published description from this channel. Match its shape, length, line breaks, casing, emoji density, CTA lines and hashtag style:' + chr(10) + '<<<' + chr(10) + desc_anchor + chr(10) + '>>>') if desc_anchor else ''}
{('Channel handle for a subscribe link (only if the anchor convention uses links): ' + handle) if handle else ''}

Rules for this tool: nothing invented (every claim, name and tag traces to the script); zero slop vocabulary; no em dashes; the description never pastes the hook verbatim and puts the strongest line first (first ~125 characters show before "more"); tags 15-25, comma-free phrases; the pinned comment makes ONE move (a question that drives replies, in the channel's voice), never "thanks for watching". The two extra title options come from two different framework families in title-formulas-skill.md and keep the channel's "POV: ..." pattern when it fits.

SKILLS:
{skills}

FINISHED SCRIPT:
{script[:9000]}

Return JSON: {{"titles": ["{title}", "option 2", "option 3"], "why": "one line on the ranking", "description": "the full description, ready to paste, with line breaks and hashtags", "tags": ["..."], "pinned_comment": "..."}}"""
    data = ai.chat_json([{"role": "system", "content": _system(ch)}, {"role": "user", "content": prompt}],
                        model=ai.text_model(), reasoning="medium", timeout=300)
    titles = [t.strip() for t in data.get("titles") or [] if isinstance(t, str) and t.strip()]
    if title and (not titles or titles[0] != title):
        titles = [title] + [t for t in titles if t != title]
    desc = FOS.mech_fix((data.get("description") or "").strip()).replace(", \n", "\n")
    return {"titles": titles[:3], "why": data.get("why", ""), "description": desc,
            "tags": _fit_tags(data.get("tags")), "pinned_comment": FOS.mech_fix((data.get("pinned_comment") or "").strip()),
            "engine": "facelessos", "at": None}


def dumps(o):
    return json.dumps(o, ensure_ascii=False)
