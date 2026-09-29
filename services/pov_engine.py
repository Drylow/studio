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

from services import ai, board, media, presenter, render, tts
from services import facelessos as FOS
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
    "board_cartoon": {
        "name": "Cartoon explainer business (Marcus Explains)",
        "prompt": "Clean modern 2D cartoon illustration in the style of a popular YouTube business-explainer channel: "
                  "bold smooth black outlines (thicker around characters), flat colors with one soft cel-shading tone, "
                  "bright natural palette, simple rounded character bodies with white four-finger mitten hands and "
                  "expressive minimal faces, real-world backgrounds (stores, offices, streets, factories) drawn simpler "
                  "and lighter with slightly desaturated colors so the characters and key props pop, clear readable "
                  "props, crisp vector look, generous breathing room, no photorealism, no painterly texture, no heavy "
                  "gradients.",
    },
    "osl_stick": {
        "name": "Bonhommes blancs POV (Oddly Specific Lives)",
        "prompt": "2D digital cartoon illustration with clean bold black outlines and soft cel shading. Simple stick-figure-"
                  "like characters: a large perfectly round plain WHITE head (no nose, no ears), small solid black dot "
                  "eyes, tiny simple eyebrows and a small simple mouth; women have the same white round head with long "
                  "straight black hair or a black bun; slim simple bodies in plain solid-colored long-sleeve sweaters or "
                  "simple outfits (green, blue, red, purple, yellow, black) with dark trousers, white mitten hands. "
                  "Detailed, cozy, richly lit realistic backgrounds (living rooms, kitchens, restaurants, city skylines "
                  "at night, streets, parks, courtrooms) with depth, warm lamps, golden hour or neon atmosphere, "
                  "cinematic composition, characters medium-large in the frame, calm understated facial expressions. "
                  "Background people and crowds are the same white round-head figures — never realistic humans.",
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
                   "fps": 30, "quality": "fast", "aspect": "16:9", "pause_max": 0.45,
                   "layout": "full"}  # "board" = fond quadrillé + panneau + présentateur (16:9)

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
    "oddly_specific_en": {
        "name": "Oddly Specific Lives — POV mariage (EN)", "language": "en", "format": "pov_marry",
        "niche": "Second-person POV life stories: you marry / fall in love with a woman from a specific culture or with "
                 "an oddly specific life (Russian, Latina, Indian, British, female Yakuza, serial killer...)",
        "audience": "Men 18-45 (US, UK, India, worldwide) who love relationship stories, culture shock and dark humor",
        "tone": "Calm, intimate second-person narrator ('you'), present tense, literary but always sayable: sensory "
                "detail, everyday similes, dry understatement, short loaded dialogue. Never mean-spirited.",
        "rules": "Follow the relationship chronologically, from the first meeting to the quiet final scene. Real, named "
                 "places and correct cultural details (food, family, customs, words). Stereotypes are affectionate, "
                 "never insulting.",
        "reference_urls": "https://www.youtube.com/watch?v=130HkA6TN8c",
        "style": "osl_stick", "voice_provider": "algrow", "voice": "rU18Fk3uSDhmg5Xh41o4", "wpm": 158,
        "no_text": True, "voice_speed": 1.0,
        "direction": "Show the story like a sitcom: mostly You and Her (and her family / friends) in everyday places — "
                     "apartments, kitchens, restaurants, her parents' home, streets and landmarks of her country, "
                     "wedding venues, hospitals, parks. Medium and wide shots, characters medium-large, calm or dry "
                     "understated expressions that sell the joke. Put the cultural details on screen (food, clothes, "
                     "architecture, objects, customs). Night city skylines and warm interiors for emotional beats.",
        "default_minutes": 14,
        "montage": {"pacing": 6.0, "hook_pacing": 6.0, "hook_seconds": 0, "min_scene": 3.0, "max_scene": 11.0,
                    "motion": "zoom_in", "motion_strength": 0.08, "transition": "fade", "transition_dur": 0.4,
                    "section_titles": False, "captions": {"mode": "none"}, "layout": "full",
                    "music": "auto", "music_volume": 0.14},
        "character": ("You", "the protagonist ('you'): a simple cartoon man with a large perfectly round plain white head, "
                             "small black dot eyes, no hair; slim body; plain colored sweater or outfit that fits the "
                             "scene; same look in every image"),
        "characters_extra": [("Her", "the woman he loves: same white round head and dot eyes, long straight black hair "
                                     "(or a bun), clothes that fit her culture and the scene; same look in every image")],
        "thumb_text": False,
        "thumb_style": "Vibrant, detailed comic-book cartoon illustration (NOT stick figures): one beautiful stylized "
                       "woman of the video's nationality / identity, three-quarter body, confident knowing smile, in an "
                       "iconic outfit of her culture, holding a bouquet of red roses (or the premise's key prop), with a "
                       "thick white sticker outline around her; behind her the most iconic landmark or setting of her "
                       "country / world at golden hour or night, with a few small background people; the country's flag "
                       "as a flat rectangle with a thin black border in the top-left corner (no flag if no country). "
                       "Warm saturated colors, clean bold outlines, no text.",
        "bible": "",
    },
    "business_en": {
        "name": "Business Explained — tableau + prof (EN)", "language": "en", "format": "business_explained",
        "niche": "How businesses really make money: hidden business models, margins, markups and the dark side "
                 "(pawn shops, buffets, dollar stores, casinos, money laundering...)",
        "audience": "US/UK men and women 18-44 who love insider economics, side-hustle and 'how it really works' content",
        "tone": "One calm, confident narrator explaining a machine to a smart friend. Conversational (contractions), "
                "dry one-line humor, colder and fully serious on criminal topics. Never moralizes.",
        "rules": "Every claim is concrete and sourced in the sentence (institution, year, sample). Only real figures, "
                 "rounded; otherwise a clearly hypothetical worked example. One master analogy per video, called back "
                 "3+ times. Three CTAs max: ~6 min, ~16-20 min, end ('Tell me where you're watching from').",
        "style": "board_cartoon", "voice": "en-US-AndrewMultilingualNeural", "wpm": 165, "no_text": False,
        "voice_speed": 1.08, "default_minutes": 24,
        "montage": {"pacing": 6.0, "hook_pacing": 4.5, "hook_seconds": 30, "min_scene": 2.5, "max_scene": 10.0,
                    "motion": "auto", "motion_strength": 0.05, "transition": "cut", "section_titles": False,
                    "captions": {"mode": "none"}, "layout": "board", "pause_max": 0.35},
        "board": dict(board.THEMES["slate"], enabled=True, theme="slate", anim="poses"),
        "character": ("People", "every person in every image (workers, customers, bosses, criminals, the viewer) "
                                "is a simple cartoon figure with a large, perfectly round, plain WHITE head (no hair, "
                                "no ears, no nose), small solid black dot eyes, simple black line eyebrows and mouth, "
                                "thick black outline, slim simple body, white mitten hands; roles are shown only by "
                                "clothes and props"),
        "mascot": "the channel's presenter: a simple cartoon man with a large, perfectly round, plain WHITE head (no "
                  "hair, no ears, no nose), small solid black dot eyes, simple black eyebrows and a small confident "
                  "closed smile, thick black outline; slim body in a dark charcoal-grey suit, white shirt, burgundy tie, "
                  "black shoes, white mitten hands",
        "direction": "Alternate between (a) character scenes: the white round-headed characters acting out the exact moment "
                     "in a real place (store, back office, street, bank) and (b) explainer visuals drawn in the same "
                     "cartoon style: a 3-box flowchart with arrows, a simple bar chart or timeline, a stack of cash "
                     "next to a tiny coin, a building cut-away, a map with arrows, money flowing through a pipe, a "
                     "receipt or price tag close-up. Whenever the narration states a key number or concept, put it on "
                     "screen as ONE bold label (e.g. '8¢ PER $1', 'THE 25% RULE', '$42.7 BILLION').",
        "thumb_style": "Dark midnight-blue slate background with a subtle dot grid and a few faint white chalk doodles "
                       "of the setting; a huge heavy black condensed UPPERCASE title of 3-4 words with a thick white outline "
                       "across the top, underlined by a thick red marker stroke; the channel presenter (white round head, "
                       "charcoal suit, burgundy tie) center-right with a smug, knowing grin doing the business's key action; 1-2 white "
                       "round-headed characters on the left reacting (shocked, worried or greedy); the key props of the "
                       "business in the middle; 4-6 short black labels with white outline and curved black arrows "
                       "pointing at props, each a number + 1-3 words ('$100K DAILY CASH FLOW', '3% SERVICE CHARGE').",
        "bible": "",
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


# Bibles de style prêtes à l'emploi (tirées de l'analyse des transcriptions des chaînes de référence).
TEMPLATE_BIBLES = {
    "oddly_specific_en": """REFERENCE. Built from the channel's own outlier "POV: You Fall in Love with a Female Yakuza" (117k views, 10:58, 1,759 words, 160 wpm). It teaches the register, pacing and beat map. Never reuse its plot, lines, images or hooks. FacelessOS rules win on any conflict.
FORMAT. One continuous second-person narration, present tense, chronological. No host, no intro, no "in this video", no spoken chapter titles, no CTA, no outro. The title carries the premise: never restate it. Delay the label itself (the reference names her world only after ~2:45).
HOOK (first ~110 words, 0:00-0:45). Sentence one puts you and her in the same frame with a jolt ("The first time you see her, you're on your knees, not by choice."). Then one specific place and one wry detail, one sensory paragraph (weather, light, sound), your ordinary worry (rent, a broken nose), the turn ("Then the alley goes quiet."), her entrance shown through its effect on others, her first short line of dialogue, her exit. Button the scene with a one-line irony ("You tell yourself you won't look for her. You look for her.").
BEAT MAP (share of runtime). First meeting in media res 0-18% → you go looking, learning who she really is through specific facts 18-30% → second meeting: a long dialogue scene where she states the stakes, one small detail makes you fall 30-47% → one-sentence thesis of what this love is 47-50% → accumulating moments in named places, first touch 50-65% → her world intrudes: absence, an injury or crisis, the thing gets named in dialogue 65-75% → "Loving her is..." montage of her specific habits, and what you accept 75-88% → reflection that calls back the first scene, then a final quiet two-person scene and a last image 88-100%.
VOICE. Calm, intimate, literary but always sayable. ~11 words per sentence (median 9); about one sentence in five is 1-4 words; a long flowing sentence (25+ words) every few lines. Everyday similes ("the way you'd look at a minor inconvenience, a traffic jam, a slow elevator"; "the way you'd choose your steps on ice"). Dry understatement ("running would be undignified"; "It takes 3 weeks, which is embarrassing in retrospect"). Story-scale numbers, few and exact (3 weeks, 28 years old, three organizations, exactly 3 seconds).
DIALOGUE. ~24 short quoted lines in 11 minutes, all subtext. She speaks in precise, loaded sentences. You say almost nothing ("I understand." "I know." "Nothing. Just you."). Dialogue carries the key turns: the warning, the "why", the naming.
TIME. Move time inside the narration, never with headings: "It takes 3 weeks", "on a Tuesday night", "Three months in", "for two weeks she's unreachable".
PLACE. Real, named, drawable places and textures (Shinjuku alley, basement bar in Kabukicho, rooftop above a ramen shop, laundry lines and satellite dishes). The city is a character that closes scenes ("Below you, Tokyo breathes.").
MOTIFS. Plant 2-3 physical motifs early (rain, hands, the city at night) and pay them off; the last line returns to one of them ("Her hand finds yours in the dark. She doesn't let go. Neither do you.").
FACELESSOS LIMITS ON THE REFERENCE'S HABITS. Its "Not X, but Y" reframes and verdict lines are the part not to copy: at most 2 antithesis constructions and 1 aphoristic closer per script, never in adjacent paragraphs. Short fragment runs only as a dialogue beat or a real count. No em dashes.
OTHER PREMISES. Same register for warm culture premises (Korean, Filipina, Russian...): her world = her family, city and customs; the stakes are cultural (the family's verdict, a ritual you must get right, distance, faith), not violence. "Marry" titles must reach the proposal or wedding by ~60% and then show married life; "Fall in Love" titles stop at commitment.
CULTURE. 6-10 correct, widely documented specifics (ceremony names, dishes, kinship words, places), each shown in a scene with context; one country unless the title is a broad label. Humor aims at your ignorance or at the size of their love, never at her intelligence, morals, accent, looks, skin, religion, poverty or immigration status. Negative stereotypes only in the mouths of clueless outsiders, disproved within 60 seconds. Rituals and faith are shown as beautiful. In crime premises never tie the criminality to her ethnicity.""",
    "business_en": """VOICE. One calm narrator explaining a machine to a smart friend. No greeting, channel name, "in this video" or sponsor. Contractions and plain words. Colder on criminal topics: fewer contractions, no jokes. ~180 spoken words per minute.
HOOK (first 250-350 words, done by 1:45). Sentence one is either a hard, sourced number that sounds impossible, or a real named person in a named place and year. State the paradox ("if that picture were right, this whole business should be dead"). Name the popular belief and kill it. Say the real answer "has almost nothing to do with" the obvious product. End with "By the end of this, you'll understand..." plus 2-4 open loops, at least one dark or aimed at the viewer.
MASTER ANALOGY. Within the first two minutes, ONE everyday system (washing machine, ride wristband, vending machine) that maps the whole business. Call back to it 3+ times, "upgrade" it when facts arrive, reuse it in the close.
STRUCTURE. Simple version → hidden lever → math → twist → origin or case → dark side → the piece that ties it together → callback. Before each pivot, recap the previous points in one list sentence: "Now, if the story ended there..."
NUMBERS. A specific figure in nearly every paragraph. Name the source inside the sentence: institution, year, sample size. Turn every percentage into a human unit ("for every $1,000... about $2", "1 in 500", "one diner in 20"). Walk through one customer, one plate or one store with round numbers ("Say the buffet charges $20."). Set fines against revenue ("0.028% of revenue... a parking ticket"). Repeat a shocking figure as a fragment: "95%." "Three times."
STAGING. Drawable beats: objects, routes, company chains, a weekday, a town and its population. Real named people with one-line verbatim quotes; otherwise archetypes ("the grandmother who has soup and a roll"). Put the viewer in the scene: "Walk into a casino with $50,000 in cash..."
RHYTHM. ~14 words per sentence. A long explanation followed by a 2-5 word punch. "That's not X. That's Y.", triplets ("They have methods. They have infrastructure. They have a fee."), sentences opening with And, But, So or Now. Five rhetorical questions at most, each answered at once. Dry one-line humor.
RE-HOOKS. Every 2-3 minutes plant a loop ("What comes next is the part that still doesn't make sense."). CTAs at ~6:00 and between 16:00 and 20:00: "If [this changed how you see X], subscribe, because [the next part is where Y]."
DARK SIDE. 15-25% on who pays: workers, towns, customers, regulators, all with numbers. State it flatly. Never moralize.
ENDING. Recap every mechanism in one list ("That is the machine."), return to the opening image or person, widen it to a general law, land a one-sentence kicker. Then: "Tell me where you're watching from in the comments, and if this changed how you see [X], subscribe." Stop.""",
}

def _video_ids(text):
    ids = re.findall(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", text or "")
    return list(dict.fromkeys(ids or re.findall(r"\b([A-Za-z0-9_-]{11})\b", text or "")))


def _bundled_refs(urls_text):
    """Transcriptions de référence livrées avec l'app (skills/references/<id>.txt)."""
    return "\n\n".join(t for t in (FOS.bundled_reference(v) for v in _video_ids(urls_text)) if t)


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
        "tone": t.get("tone", ""), "rules": t.get("rules", ""), "cta": "",
        "reference_urls": t.get("reference_urls", ""), "reference_scripts": _bundled_refs(t.get("reference_urls", "")),
        "bible": t.get("bible") or TEMPLATE_BIBLES.get(template or "", ""),
        "wpm": t.get("wpm", 150), "thumb_style": t.get("thumb_style", ""),
        "thumb_text": t.get("thumb_text", True), "thumb_ref": None,
        "style": {"preset": style_key, "prompt": STYLE_PRESETS[style_key]["prompt"],
                  "no_text": t.get("no_text", True), "direction": t.get("direction", ""),
                  "ref": None, "characters": []},
        "voice": _merge(DEFAULT_VOICE, {"provider": t.get("voice_provider", "edge"),
                                        "voice": t.get("voice") or DEFAULT_VOICE_BY_LANG.get(lang, ""),
                                        "speed": t.get("voice_speed", 1.0)}),
        "montage": _merge(DEFAULT_MONTAGE, t.get("montage") or {}),
        "board": _merge(board.DEFAULT_BOARD, dict(t.get("board") or {}, mascot=t.get("mascot", ""))),
        "default_minutes": t.get("default_minutes", 10),
    }
    if t.get("character"):
        name, desc = t["character"]
        ch["style"]["characters"].append({"id": store.new_id("chr"), "name": name, "description": desc,
                                          "image": None, "always": True})
    for name, desc in t.get("characters_extra") or []:
        ch["style"]["characters"].append({"id": store.new_id("chr"), "name": name, "description": desc,
                                          "image": None, "always": False})
    ch = apply_channel_update(ch, data)
    store.save_channel(ch)
    return ch


_CH_FIELDS = ("name", "language", "format", "niche", "audience", "tone", "rules", "cta", "reference_scripts",
              "reference_urls", "bible", "wpm", "default_minutes", "thumb_style", "thumb_text")
_BOARD_FIELDS = ("theme", "bg_color", "line_color", "major_color", "pattern", "cell", "major_every", "paper",
                 "panel_width", "border", "border_color", "radius", "shadow", "shadow_color", "shadow_offset",
                 "presenter_height", "presenter_x", "bob", "animate", "anim", "mascot", "presenter_outline",
                 "outline_color", "spot", "spot_color")


def apply_channel_update(ch, data):
    for k in _CH_FIELDS:
        if k in data:
            ch[k] = data[k]
    if isinstance(data.get("style"), dict):
        st = data["style"]
        for k in ("preset", "prompt", "no_text", "direction"):
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
    if isinstance(data.get("board"), dict):  # le PNG du présentateur se gère via son endpoint
        bd = ch.get("board") or dict(board.DEFAULT_BOARD)
        for k in _BOARD_FIELDS:
            if k in data["board"]:
                bd[k] = data["board"][k]
        ch["board"] = bd
    try:
        ch["wpm"] = max(90, min(220, int(float(ch.get("wpm") or 150))))
    except (TypeError, ValueError):
        ch["wpm"] = 150
    return ch


def channel_ref_path(ch, rel):
    return os.path.join(store.channel_dir(ch["id"]), rel) if rel else None


def save_channel_image(ch, blob, kind, char_id=None):
    """kind = 'style' | 'thumb' | 'char'. Stocke en PNG borné (1536 px)."""
    from PIL import Image
    im = Image.open(io.BytesIO(blob))
    im = im.convert("RGB")
    im.thumbnail((1536, 1536))
    os.makedirs(os.path.join(store.channel_dir(ch["id"]), "refs"), exist_ok=True)
    stamp = int(time.time() * 1000)
    if kind in ("style", "thumb"):
        rel = f"refs/{kind}_{stamp}.png"
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
    """Transcriptions YouTube (youtube-transcript-api). Si YouTube bloque, prend la transcription
    livrée avec l'app quand elle existe (skills/references/<id>.txt)."""
    ids = _video_ids(urls_text)[:limit]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
    except Exception:
        api = None
    out, errors = [], []
    for vid in ids:
        bundled = FOS.bundled_reference(vid)
        try:
            if api is None:
                raise RuntimeError("youtube-transcript-api absent")
            tr = api.fetch(vid, languages=["fr", "en", "es", "de", "pt", "it"])
            text = " ".join(s.text.replace("\n", " ") for s in tr.snippets)
            # une transcription livrée (ponctuée, en paragraphes) vaut mieux que les sous-titres auto
            out.append(bundled or f"--- https://youtu.be/{vid} ---\n{text}")
        except Exception as e:  # noqa: BLE001
            if bundled:
                out.append(bundled)
            else:
                errors.append(f"{vid}: {type(e).__name__}")
    if not out:
        raise RuntimeError("Aucune transcription récupérée (" + ", ".join(errors or ["lien invalide"]) +
                           "). YouTube bloque parfois : colle le script à la main.")
    return "\n\n".join(out), errors


def _norm_name(n):
    return re.sub(r"\s+", " ", (n or "").strip().lower())


def cast_list(ch, pr=None):
    """Personnages de la vidéo : [{id, name, aliases, description, path, always, source}].

    = persos récurrents de la chaîne + casting du projet (détecté dans le script, façon TubeGen).
    Un perso du projet qui porte le nom d'un perso de la chaîne le remplace pour cette vidéo
    (ex. « You » avec une tenue propre à la vidéo)."""
    out = {}
    for c in (ch.get("style") or {}).get("characters") or []:
        out[_norm_name(c["name"])] = {"id": c.get("id"), "name": c["name"], "aliases": [],
                                      "description": c.get("description") or "",
                                      "path": channel_ref_path(ch, c.get("image")), "always": bool(c.get("always")),
                                      "source": "channel"}
    for c in (pr or {}).get("cast") or []:
        key = _norm_name(c.get("name"))
        if not key:
            continue
        base = out.get(key) or {}
        img = os.path.join(store.project_dir(pr["id"]), c["image"]) if c.get("image") else None
        out[key] = {"id": c.get("id"), "name": c["name"], "aliases": c.get("aliases") or [],
                    "description": c.get("description") or base.get("description", ""),
                    "path": img if img and os.path.isfile(img) else base.get("path"),
                    "always": base.get("always", False), "source": "video"}
    return list(out.values())


def _in_scene(cast, scene_chars):
    """Persos présents : ceux nommés par la scène (nom ou alias) ; sans info, les persos « toujours là »."""
    if scene_chars is None:
        return [c for c in cast if c.get("always")]
    names = {_norm_name(n) for n in scene_chars}
    return [c for c in cast if _norm_name(c["name"]) in names or any(_norm_name(a) in names for a in c["aliases"])]


MAX_CHAR_REFS = 4


def _style_parts(ch, scene_chars=None, cast=None):
    """(lignes de prompt, images de référence) : style de la chaîne + persos présents dans la scène."""
    st = ch.get("style") or {}
    refs, lines = [], []
    style_ref = channel_ref_path(ch, st.get("ref"))
    if style_ref and os.path.isfile(style_ref):
        refs.append(style_ref)
        lines.append(f"Reference image {len(refs)} = ART STYLE reference: copy its rendering, line work, color "
                     "palette and shading exactly. Ignore its content, characters and composition.")
    present = _in_scene(cast if cast is not None else cast_list(ch), scene_chars)
    for c in present[:MAX_CHAR_REFS]:
        if c.get("path") and os.path.isfile(c["path"]):
            refs.append(c["path"])
            lines.append(f"Reference image {len(refs)} = the character \"{c['name']}\": draw this character with "
                         "EXACTLY the same head, face, hair, body proportions, colors and outfit (only change the "
                         "outfit or age if the scene explicitly says so). Same design in every image.")
    return lines, refs


def uses_board(ch_or_pr):
    """Mise en page tableau active (réglage « montage.layout » de la chaîne ou du projet)."""
    return ((ch_or_pr or {}).get("montage") or {}).get("layout") == "board"


def build_image_prompt(ch, scene_prompt, scene_chars=None, allow_text=False, vertical=False, board_layout=False,
                       cast=None):
    st = ch.get("style") or {}
    cast = cast if cast is not None else cast_list(ch)
    lines, refs = _style_parts(ch, scene_chars, cast)
    chars_desc = [f"{c['name']}: {c['description']}" for c in _in_scene(cast, scene_chars) if c.get("description")]
    parts = lines + ["SCENE: " + scene_prompt.strip()]
    if chars_desc:
        parts.append("CHARACTERS IN THIS IMAGE: " + " | ".join(chars_desc))
    parts.append("ART STYLE: " + (st.get("prompt") or "").strip())
    parts.append("EVERY person in the image — including background people, crowds, waiters, customers, passers-by, "
                 "people on screens or in photos — is drawn in exactly the same character design as the main "
                 "characters (same head shape, face style and proportions). Never draw a realistic or differently "
                 "styled human.")
    fmt = ("Tall 9:16 vertical frame, full-bleed illustration, main subject centered, no borders, no frame."
           if vertical else "Wide 16:9 landscape frame, full-bleed illustration, no borders, no frame.")
    if st.get("no_text", True) and not allow_text:
        fmt += " No text, no letters, no words, no captions, no signs with writing, no watermark, no logo."
    elif not allow_text:
        fmt += (" Text: ONLY the short label(s) quoted in the scene description, big, bold, uppercase and spelled "
                "exactly; no other writing, no small unreadable text, no watermark, no logo.")
    if board_layout and not vertical:
        fmt += (" Keep the bottom-left corner of the image calm and free of important details (a presenter "
                "character is overlaid there).")
    parts.append(fmt)
    return "\n".join(p for p in parts if p), refs


_MODERATION = ("safety", "moderation", "policy", "content_policy", "rejected", "not allowed", "violat")


def generate_scene_image(ch, prompt, dest, scene_chars=None, width=1920, height=1080, board_layout=False,
                         cast=None):
    full, refs = build_image_prompt(ch, prompt, scene_chars, vertical=height > width, board_layout=board_layout,
                                    cast=cast)
    try:
        blob = ai.generate_image(full, width=width, height=height, refs=refs)
    except ai.AIError as e:
        if not any(m in str(e).lower() for m in _MODERATION):
            raise
        safe = ai.chat("Rewrite this image prompt so it passes strict image-safety filters while keeping the same "
                       "scene, meaning and composition (imply violence/danger instead of showing it; no gore, no "
                       "nudity, no real public figures). Output only the prompt.\n\n" + prompt,
                       model=ai.fast_model())
        full, refs = build_image_prompt(ch, safe, scene_chars, vertical=height > width, board_layout=board_layout,
                                        cast=cast)
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


def presenter_image(ch, extra="", anim=None):
    """Présentateur (prof en bas à gauche) : image de base détourée + son animation."""
    bd = ch.get("board") or {}
    mascot = (bd.get("mascot") or "").strip()
    if not mascot:
        always = [c for c in (ch.get("style") or {}).get("characters") or [] if c.get("always")]
        mascot = always[0]["description"] if always else "a friendly simple cartoon teacher"
    prompt = (presenter.PRESENTER_POSE + f"\nCHARACTER DESIGN: {mascot}."
              + (f"\n{extra.strip()}" if extra.strip() else "")
              + "\nART STYLE: " + ((ch.get("style") or {}).get("prompt") or ""))
    blob = ai.generate_image(prompt, width=1024, height=1536, quality="high", transparent=True)
    return save_presenter(ch, blob, anim=anim or bd.get("anim") or "poses")


def _pad_portrait(blob):
    """Image importée → toile 2:3 transparente, pieds en bas (format attendu par l'animation)."""
    from PIL import Image
    im = Image.open(io.BytesIO(board.cutout(blob))).convert("RGBA")
    W, H = 1024, 1536
    s = min((W - 40) / im.width, (H - 30) / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((W - im.width) // 2, H - 15 - im.height))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def _anim_mode(anim):
    return "none" if anim == "none" else "poses"  # anciens réglages (stick / full) → poses


def save_presenter(ch, blob, anim="poses"):
    """Enregistre le prof dans refs/rig_<ts>/ (base.png + poses + rig.json).

    anim = « poses » : l'IA redessine le bras dans 3 autres positions (3 retouches en parallèle,
           ~1 min), recollées au pixel près → gestes de baguette en animation 2D pose à pose ;
           « none » : image fixe.
    Renvoie (image_de_repos_rel, dossier_rig_rel | None)."""
    from PIL import Image
    im = Image.open(io.BytesIO(blob))
    lo = im.convert("RGBA").getchannel("A").getextrema()[0]
    if lo > 250 or im.size != (1024, 1536):  # import : détourage + mise au format
        blob = _pad_portrait(blob)
    rel_dir = f"refs/rig_{int(time.time() * 1000)}"
    out_dir = os.path.join(store.channel_dir(ch["id"]), rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "base.png"), "wb") as f:
        f.write(blob)
    try:
        return _build_anim(out_dir, rel_dir, blob, _anim_mode(anim))
    except Exception:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)  # pas de dossier orphelin si l'IA échoue
        raise


def _build_anim(out_dir, rel_dir, blob, anim):
    if anim == "poses":
        def edit(k):
            try:
                return k, ai.generate_image(presenter.POSE_EDITS[k], width=1024, height=1536, refs=[blob],
                                            quality="high", transparent=True)
            except ai.AIError as e:
                if getattr(e, "status", None) == 4290:  # quota épuisé : on le dit, pas d'échec silencieux
                    raise
                return k, None
        with ThreadPoolExecutor(max_workers=3) as ex:
            variants = dict(ex.map(edit, list(presenter.POSE_EDITS)))
        if any(variants.values()):
            presenter.build_pose_rig(blob, variants, out_dir)
            return f"{rel_dir}/A.png", rel_dir
    from PIL import Image  # animation désactivée (ou toutes les retouches ont échoué) : image fixe
    Image.open(io.BytesIO(board.cutout(blob))).save(os.path.join(out_dir, "static.png"))
    return f"{rel_dir}/static.png", None


def rebuild_presenter(ch, anim):
    """Change le type d'animation sans redessiner le prof (repart de base.png, nouveau dossier :
    l'ancien reste valable tant que le nouveau n'est pas prêt)."""
    bd = board_config(ch)
    rel_dir = bd.get("rig") or os.path.dirname(bd.get("presenter") or "")
    out_dir = channel_ref_path(ch, rel_dir) if rel_dir else None
    base = os.path.join(out_dir, "base.png") if out_dir else None
    if not base or not os.path.isfile(base):
        raise RuntimeError("Image de base du prof introuvable : génère ou importe-le à nouveau.")
    with open(base, "rb") as f:
        blob = f.read()
    return save_presenter(ch, blob, anim=_anim_mode(anim))


def rig_paths(ch):
    """(images {clé: chemin absolu}, mode) du prof animé, ou ({}, None)."""
    bd = board_config(ch)
    if not bd.get("rig") or not bd.get("animate", True) or bd.get("anim") == "none":
        return {}, None
    man = presenter.load_manifest(channel_ref_path(ch, bd["rig"]))
    return (man["frames"], man["mode"]) if man else ({}, None)


def board_config(ch):
    return _merge(board.DEFAULT_BOARD, (ch or {}).get("board") or {})


def board_preview(ch, dest):
    """Aperçu de la mise en page (fond + image de style ou 1re image dispo + présentateur)."""
    bd = board_config(ch)
    scene = channel_ref_path(ch, (ch.get("style") or {}).get("ref"))
    blank = None
    if not scene or not os.path.isfile(scene):
        from PIL import Image
        blank = scene = dest + ".blank.png"
        Image.new("RGB", (1920, 1080), (238, 236, 230)).save(scene)
    pres = channel_ref_path(ch, bd.get("presenter"))
    tmp = dest + f".{os.getpid()}.{int(time.time() * 1000)}.jpg"
    try:
        board.compose_still(bd, scene, pres, tmp, 1920, 1080)
        os.replace(tmp, dest)
    finally:
        if blank and os.path.isfile(blank):
            os.remove(blank)
    return dest


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

def channel_history(cid, exclude=None, limit=3):
    """Dernières vidéos écrites de la chaîne : ouverture + rotation (diff de bibliothèque FacelessOS)."""
    out = []
    for p in store.list_projects():
        if p.get("channel_id") != cid or p.get("id") == exclude:
            continue
        text = S.narration(p.get("script") or "")
        if text:
            out.append({"title": p.get("title") or "", "hook": " ".join(text.split()[:90]),
                        "rotation": (p.get("outline") or {}).get("rotation") or ""})
    return out[:limit]  # list_projects() est déjà trié du plus récent au plus ancien


def job_script(job, pid, polish=True):
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    if not ch:
        raise RuntimeError("Chaîne introuvable.")

    def prog(p, msg, partial):
        job.update(0.02 + 0.96 * p, msg)
        if partial:
            store.update_project(pid, lambda x: x.__setitem__("script_draft", partial))

    res = S.generate(ch, pr["title"], pr["minutes"], pr.get("notes") or "", polish=polish, progress=prog,
                     history=channel_history(ch["id"], exclude=pid))

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


def job_audit(job, pid, rounds=2):
    """Audit FacelessOS (greenlight en boucle) du script actuel du projet."""
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    if not (pr.get("script") or "").strip():
        raise RuntimeError("Pas de script à auditer.")
    if not FOS.available():
        raise RuntimeError("Pack FacelessOS introuvable (dossier skills/facelessos).")

    def prog(p, msg, partial):
        job.update(0.02 + 0.96 * p, msg)
    script, report = S.audit_script(ch, pr["title"], pr["script"], pr.get("minutes"), rounds=rounds, progress=prog)

    def save(x):
        push_history(x, "avant audit FacelessOS")
        x["script"] = script
        x["review"] = report
    store.update_project(pid, save)
    job.update(1.0, f"Audit FacelessOS : {report['verdict']}.")


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
    roster = "\n".join(f"- {c['name']}" + (f" (also called: {', '.join(c['aliases'])})" if c["aliases"] else "")
                       + f": {c.get('description', '')}" for c in cast_list(ch, pr)) or "- (no recurring character)"
    heads = [h for h, _ in S.parse(pr.get("script") or "") if h]
    lines = []
    for sc in scenes:
        prev = all_scenes[sc["i"] - 1]["text"] if sc["i"] > 0 else ""
        lines.append(f"#{sc['i']} [section: {sc.get('heading') or 'hook'}] (prev: \"{prev[-120:]}\") "
                     f"NARRATION: \"{sc['text']}\"")
    st = ch.get("style") or {}
    direction = (st.get("direction") or "").strip()
    direction = f"- CHANNEL ART DIRECTION: {direction}\n" if direction else ""
    if st.get("no_text", True):
        text_rule = "No text or letters in the image."
    else:
        text_rule = ("Text: at most ONE short label per image (2-5 words, UPPERCASE, written in quotes in the prompt, "
                     f"in {S.lang_label(ch.get('language', 'en')).split(' (')[0]}) on a white callout box with a thick "
                     "black border, a sign or a tag — use it for the key number or concept of the narration. No "
                     "other writing.")
    if uses_board(pr):
        text_rule += " Keep the bottom-left corner calm (a presenter is overlaid there)."
    prompt = f"""You are the art director of a faceless 2D YouTube channel. For each scene below, write the image prompt of the illustration shown while this narration is spoken.

VIDEO: {pr['title']}
CHAPTERS: {' | '.join(heads) if heads else '-'}
ART STYLE (added automatically, do not repeat it): {(ch.get('style') or {}).get('prompt', '')[:400]}
CAST OF THIS VIDEO (their look is locked by reference images — in the prompt, refer to them ONLY by their exact name, do not re-describe their face, hair or default outfit; only mention an outfit or age change when the narration implies it):
{roster}

RULES:
{direction}- Show the exact moment/idea the narration describes, literally and concretely: subject + action + setting + key props. One clear focal point, readable in 1 second.
- If the narration talks to "you"/"tu"/"vous" and a protagonist character exists, show that character doing it.
- "chars" must list EVERY cast member visible in the image, by exact name (aliases → the cast name). Other people (crowds, waiters, strangers) are not cast: describe them briefly in the prompt instead, always as the same kind of cartoon figures as the cast (never "realistic people").
- Vary the camera across consecutive scenes (wide establishing, medium, close-up on hands/face/object, over-the-shoulder, top-down, low angle). Never the same framing twice in a row.
- Stay historically / technically accurate (uniforms, tools, places, era).
- For violence, death or danger: imply it (shadows, aftermath, expressions), never gore. No real celebrities.
- {text_rule} 25-60 words per prompt, English.

SCENES:
{chr(10).join(lines)}

Return JSON: {{"prompts": [{{"i": <scene number>, "prompt": "...", "chars": ["exact cast names visible, or empty"]}}]}}"""
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


# ── Casting de la vidéo (persos consistants, façon TubeGen) ─────────────────

MAX_CAST = 7


def detect_cast(ch, pr):
    """Lit le script → persos récurrents avec un look FIXE pour toute la vidéo."""
    st = ch.get("style") or {}
    known = "\n".join(f"- {c['name']}: {c.get('description', '')}" for c in st.get("characters") or []) or "- none"
    script = S.narration(pr.get("script") or "")
    prompt = f"""You are the character designer of a faceless 2D YouTube channel. Read this video script and define the CAST: the recurring or visually important characters who will appear in several illustrations (max {MAX_CAST}). Ignore one-off extras and crowds.

VIDEO: {pr.get('title', '')}
CHANNEL ART STYLE (every character must follow its character design rules): {(st.get('prompt') or '')[:700]}
CHANNEL RECURRING CHARACTERS (already defined): 
{known}

For each cast member give:
- "name": a short unique label used for every scene (e.g. "Her", "Her Father", "Grandma", "Min-jun"). ALWAYS include every channel character who appears in this video (e.g. the protagonist "You"), under their exact channel name, with a video-specific default outfit — so they get a locked look too.
- "aliases": how the narration refers to them (e.g. ["your wife", "Ji-woo", "she"] — no pronouns alone).
- "role": one line.
- "description": a precise, FIXED visual description for the whole video, following the channel's character design (for white round-head stick figures: head is always the same, so identity = hairstyle and hair color, age cues, body type, and a signature default outfit with exact colors, plus 1 accessory). 30-60 words, English, no personality traits.

Return JSON: {{"cast": [{{"name": "...", "aliases": ["..."], "role": "...", "description": "..."}}]}}

SCRIPT:
\"\"\"
{script[:14000]}
\"\"\"
"""
    data = ai.chat_json(prompt, model=ai.text_model(), timeout=240)
    out, seen = [], set()
    for c in data.get("cast") or []:
        if not isinstance(c, dict) or not (c.get("name") or "").strip():
            continue
        key = _norm_name(c["name"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": store.new_id("cst"), "name": c["name"].strip()[:40],
                    "aliases": [str(a).strip()[:40] for a in (c.get("aliases") or []) if str(a).strip()][:6],
                    "role": (c.get("role") or "").strip()[:120],
                    "description": (c.get("description") or "").strip()[:600], "image": None})
    return out[:MAX_CAST]


def character_ref_image(ch, member):
    """Image de référence d'un perso : en pied, de face, fond uni — dans le style de la chaîne."""
    prompt = (f"Character reference image of \"{member['name']}\": {member.get('description', '')}. "
              "Full body, standing, front view, neutral relaxed pose, arms along the body, calm expression, "
              "centered, plain light grey background, nothing else in the image.")
    st = ch.get("style") or {}
    refs, lines = [], []
    style_ref = channel_ref_path(ch, st.get("ref"))
    if style_ref and os.path.isfile(style_ref):
        refs.append(style_ref)
        lines.append("Reference image 1 = ART STYLE reference: copy its rendering, line work, character design "
                     "rules, colors and shading exactly. Ignore its content.")
    full = "\n".join(lines + [prompt, "ART STYLE: " + (st.get("prompt") or ""),
                              "Tall portrait frame. No text, no letters, no watermark."])
    return ai.generate_image(full, width=1024, height=1536, refs=refs)


def _save_cast_image(pid, cid, blob):
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((1024, 1536))
    rel = f"cast/{cid}_{int(time.time() * 1000) % 10**9}.png"
    path = os.path.join(store.project_dir(pid), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "PNG", optimize=True)
    return rel


def set_cast_image(pid, cid, rel):
    old = []

    def f(x):
        for c in x.get("cast") or []:
            if c["id"] == cid:
                if c.get("image") and c["image"] != rel:
                    old.append(c["image"])
                c["image"] = rel
    store.update_project(pid, f)
    for r in old:
        try:
            os.remove(os.path.join(store.project_dir(pid), r))
        except OSError:
            pass


def job_cast(job, pid, redetect=False, only=None, p0=0.0, p1=1.0):
    """Casting : détection des persos dans le script (si besoin) + une image de référence par perso."""
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    if not (pr.get("script") or "").strip():
        raise RuntimeError("Écris le script d'abord : les persos sont tirés du script.")
    if redetect or pr.get("cast") is None:
        job.update(p0, "Détection des personnages dans le script…")
        found = detect_cast(ch, pr)
        prev = {_norm_name(c["name"]): c for c in pr.get("cast") or []}
        for c in found:  # garde les images déjà validées d'un perso du même nom
            if _norm_name(c["name"]) in prev and prev[_norm_name(c["name"])].get("image"):
                c["id"] = prev[_norm_name(c["name"])]["id"]
                c["image"] = prev[_norm_name(c["name"])]["image"]
        store.update_project(pid, lambda x: x.__setitem__("cast", found))
        pr = store.get_project(pid)
    todo = [c for c in pr.get("cast") or [] if (only and c["id"] in only) or (not only and not c.get("image"))]
    if not todo:
        job.update(p1, f"{len(pr.get('cast') or [])} personnage(s) prêts.")
        return
    done = 0
    job.update(p0 + (p1 - p0) * 0.15, f"Images de référence des personnages 0/{len(todo)}…")
    ex = ThreadPoolExecutor(max_workers=min(len(todo), _image_workers()))
    try:
        futs = {ex.submit(character_ref_image, ch, c): c for c in todo}
        for fut in as_completed(futs):
            c = futs[fut]
            set_cast_image(pid, c["id"], _save_cast_image(pid, c["id"], fut.result()))
            done += 1
            job.update(p0 + (p1 - p0) * (0.15 + 0.85 * done / len(todo)),
                       f"Images de référence des personnages {done}/{len(todo)}")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


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
    generate_scene_image(ch, sc["prompt"], os.path.join(d, rel), scene_chars=sc.get("chars"), width=w, height=h,
                         board_layout=uses_board(pr), cast=cast_list(ch, pr))
    return rel


def job_images(job, pid, only=None, first_only=False):
    """Génère les images manquantes (ou `only` = liste d'indices à (re)faire)."""
    job.update(0.01, "Préparation du storyboard…")
    pr = store.get_project(pid)
    if not pr.get("scenes"):
        raise RuntimeError("Aucune scène : génère la voix off d'abord.")
    pr = store.get_project(pid)
    if pr.get("cast") is None and any(not (s.get("prompt") or "").strip() for s in pr["scenes"]):
        job_cast(job, pid, p0=0.01, p1=0.06)  # persos consistants AVANT d'écrire les prompts
    ensure_prompts(job, pid, 0.06, 0.12)
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
    quota = None
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
            except ai.AIError as e:
                if getattr(e, "status", None) == 4290:  # quota épuisé : on s'arrête net, message clair
                    for f in futs:
                        f.cancel()
                    quota = e
                    break
                failed += 1
                mark(s["i"], status="error", error=str(e)[:300])
            except Exception as e:  # noqa: BLE001
                failed += 1
                mark(s["i"], status="error", error=str(e)[:300])
            job.update(0.12 + 0.88 * (done + failed) / total,
                       f"Images {done}/{total}" + (f" · {failed} en échec" if failed else ""))
    except store.JobCancelled:
        _reset_queued(pid)
        raise
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    if quota:
        _reset_queued(pid)
        store.update_project(pid, lambda x: x.__setitem__("render", None) if done else None)
        raise RuntimeError(f"{done} image(s) faite(s) avant l'arrêt. {quota}")
    for rel in old_files:  # anciennes versions remplacées
        try:
            os.remove(os.path.join(store.project_dir(pid), rel))
        except OSError:
            pass
    store.update_project(pid, lambda x: x.__setitem__("render", None))
    if failed:
        raise RuntimeError(f"{failed} image(s) en échec — clique « Relancer les échecs ».")
    job.update(1.0, f"{done} image(s) prêtes.")


def _reset_queued(pid):
    def reset(x):  # les scènes jamais lancées repassent « en attente »
        for sc in x["scenes"]:
            if sc.get("status") == "queued":
                sc["status"] = "done" if sc.get("image") else "pending"
    store.update_project(pid, reset)


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
    music = pick_music(pr, m.get("music"))
    layout = _layout_for(pr, os.path.join(d, "render"), w, h)
    out_name = f"{render.safe_name(pr.get('title'))}_{int(time.time()) % 1000000}.mp4"
    try:
        res = render.render_video(
            os.path.join(d, "render"), scenes, os.path.join(d, pr["voice"]["file"]), os.path.join(d, out_name),
            width=w, height=h, fps=int(m.get("fps") or 30), motion=m.get("motion", "auto"),
            motion_strength=float(m.get("motion_strength") or 0.12), transition=m.get("transition", "fade"),
            transition_dur=float(m.get("transition_dur") or 0.3), words=load_words(pid),
            captions=m.get("captions") or {"mode": "none"}, overlays=overlays, music_path=music,
            music_volume=float(m.get("music_volume") or 0.12), quality=m.get("quality", "fast"), layout=layout,
            progress=lambda p, msg: job.update(p * 0.98, msg), cancelled=job.cancelled)
    except render.Cancelled:
        raise store.JobCancelled("Annulé.")
    old = (pr.get("render") or {}).get("file")

    def save(x):
        x["render"] = {"file": out_name, "v": int(time.time()), "duration": res["duration"], "at": store.now()}
    store.update_project(pid, save)
    _remove_quiet(d, old if old != out_name else None)
    job.update(1.0, "Vidéo exportée.")


def pick_music(pr, choice):
    """Musique de fond : un fichier précis, ou « auto » = une piste de la bibliothèque par vidéo
    (toujours la même pour un projet donné). Bibliothèque vide → pistes libres générées."""
    if not choice:
        return None
    if choice != "auto":
        return store.music_path(choice)
    tracks = store.list_music()
    if not tracks:
        from services import music
        music.ensure_defaults(store.music_dir())
        tracks = store.list_music()
    if not tracks:
        return None
    k = int(hashlib.sha1(pr["id"].encode()).hexdigest(), 16) % len(tracks)
    return store.music_path(tracks[k])


def _layout_for(pr, workdir, w, h, with_presenter=True):
    """Mise en page tableau pour le rendu (None = plein écran)."""
    if not uses_board(pr) or h > w:
        return None
    ch = store.get_channel(pr["channel_id"]) or {}
    bd = board_config(ch)
    os.makedirs(workdir, exist_ok=True)
    rig, mode = rig_paths(ch) if ch else ({}, None)
    return render.prepare_layout(workdir, bd, channel_ref_path(ch, bd.get("presenter")) if ch else None, w, h,
                                 with_presenter=with_presenter, rig=rig, rig_mode=mode or "full")


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
    layout = _layout_for(pr, os.path.join(d, "render"), w, h)
    extras = {}
    if layout:  # éléments séparés, pour qui veut refaire la mise en page lui-même
        extras["mise_en_page/fond_quadrille.png"] = layout["bg"]
        if layout.get("presenter"):
            extras["mise_en_page/presentateur.png"] = layout["presenter"]
    return render.export_pack(os.path.join(d, "render"), scenes, os.path.join(d, pr["voice"]["file"]),
                             os.path.join(d, name), width=w, height=h, fps=int(m.get("fps") or 30),
                             motion=motion or "none", motion_strength=float(m.get("motion_strength") or 0.1),
                             words=load_words(pid), script_text=pr.get("script") or "", title=pr.get("title", ""),
                             layout=layout, extras=extras,
                             progress=lambda p, msg: job.update(p * 0.99, msg), cancelled=job.cancelled)


def job_thumbnails(job, pid, idea="", count=2):
    """Miniatures YouTube (style + perso de la chaîne, gros texte court)."""
    pr = store.get_project(pid)
    ch = store.get_channel(pr["channel_id"])
    count = max(1, min(4, int(count or 2)))
    job.update(0.05, "Concepts de miniatures…")
    chars = [c["name"] for c in (ch.get("style") or {}).get("characters") or []]
    bd = board_config(ch)
    mascot = channel_ref_path(ch, bd.get("presenter"))
    mascot = mascot if mascot and os.path.isfile(mascot) else None
    if mascot:
        chars.append("Mascot")
    thumb_style = (ch.get("thumb_style") or "").strip()
    with_text = ch.get("thumb_text", True) is not False
    thumb_ref = channel_ref_path(ch, ch.get("thumb_ref"))
    thumb_ref = thumb_ref if thumb_ref and os.path.isfile(thumb_ref) else None
    text_rule = (f"and 2-4 words of huge bold text (in the video's language: {S.lang_label(ch.get('language', 'fr'))})"
                 + (" (the title text of the style above)" if thumb_style else " placed away from the subject")
                 if with_text else "and NO text at all (the image alone must create the curiosity)")
    concept = ai.chat_json(f"""You design YouTube thumbnails for an animated 2D illustration channel ({ch.get('niche', '')}).
{('CHANNEL THUMBNAIL STYLE (follow it exactly, it is proven): ' + thumb_style) if thumb_style else 'Characters have clear, expressive faces.'}
Video title: {pr['title']}
Script excerpt: {S.narration(pr.get('script') or '')[:1200]}
Recurring characters: {', '.join(chars) or 'none'}
{('Creator idea: ' + idea) if idea else ''}

Create {count} DIFFERENT thumbnail concepts that maximize CTR: one strong focal subject with a big readable emotion, high contrast, a visual curiosity gap that does NOT repeat the title word for word, {text_rule}.
Return JSON: {{"thumbs": [{{"text": "{'SHORT TEXT' if with_text else ''}", "prompt": "40-70 words: composition, subject, expression, props, background, colors{', where the text goes' if with_text else ''}", "chars": ["character names visible"]}}]}}""", model=ai.text_model())
    items = (concept.get("thumbs") or [])[:count]
    if not items:
        raise RuntimeError("Aucun concept de miniature renvoyé.")
    d = store.project_dir(pid)
    done, results = 0, []

    def one(it):
        prompt = f"YouTube thumbnail. {it.get('prompt', '')}"
        if with_text and it.get("text"):
            prompt += (f" Huge bold clean sans-serif text reading exactly \"{it.get('text', '')}\" with a thick dark "
                       "outline, perfectly legible, spelled correctly.")
        prompt += " Bright, saturated, high contrast, readable at small size."
        if thumb_style:
            prompt += " THUMBNAIL STYLE: " + thumb_style
        if thumb_style or thumb_ref:
            # style de miniature propre à la chaîne (différent du style des images de la vidéo)
            refs = [thumb_ref] if thumb_ref else []
            full = (("Reference image 1 = THUMBNAIL STYLE reference: copy its art style, rendering, outlines, "
                     "composition and color treatment exactly; the subject and setting are new, as described.\n")
                    if thumb_ref else "") + prompt
            if not with_text:
                full += " No text, no letters, no words (a flag is fine)."
        else:
            full, refs = build_image_prompt(ch, prompt, scene_chars=it.get("chars") or [], allow_text=with_text)
        if mascot and "Mascot" in (it.get("chars") or []):
            refs = refs + [mascot]
            full = (f"Reference image {len(refs)} = the channel MASCOT: same head, face, colors and outfit "
                    "(expression and pose change as described).\n" + full)
        blob = ai.generate_image(full, width=1920, height=1080, refs=refs, quality="high")
        rel = f"thumbs/thumb_{int(time.time() * 1000) % 10**9}.jpg"
        ai.fit_cover(blob, 1280, 720, os.path.join(d, rel), quality=90)
        return {"file": rel, "text": it.get("text", "") if with_text else "", "prompt": it.get("prompt", ""),
                "at": store.now()}

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
