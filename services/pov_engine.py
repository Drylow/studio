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
        "youtube_handle": "@OddlySpecificLives",
        "studio": {"brand": "Oddly Specific Lives", "logo": "OSL", "ref_name": "Female Yakuza",
                   "placeholder": "POV: You Marry a Japanese Woman",
                   "sub": "script FacelessOS (calé sur la vidéo Female Yakuza), voix Algrow, personnages consistants, "
                          "images, musique et montage.",
                   "thumb_prompt": "A beautiful stylized woman matching the premise of \"{title}\", confident knowing "
                                   "smile, iconic outfit of her culture, holding a bouquet of red roses, the most "
                                   "iconic landmark of her country behind her at golden hour."},
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
        # autres formats de la même chaîne : même voix, même style, même narration (choisi d'après le titre)
        "variants": {"pov_life": {
            "niche": "Second-person POV life stories: you live an oddly specific life (a job, a world, a status) "
                     "from the first day to the quiet last scene",
            "rules": "Follow your life chronologically, from the ordinary before to the quiet final scene. Real, "
                     "named places and correct insider details (routines, money, tools, words). Honest and human: "
                     "never glamorize, never mock, never graphic.",
            "bible_note": "derived from the channel's reference video, a POV love story: follow its narration "
                          "register, hook mechanics, rhythm, dialogue density and ending shape; its romance beats "
                          "do not apply",
            "direction": "Show the story like a sitcom: mostly You (and the few recurring people of your life) in the "
                         "everyday places of this life: home, workplace, streets, cars, family dinners, offices. Medium "
                         "and wide shots, characters medium-large, calm or dry understated expressions that sell the "
                         "joke. Put the specific tools, objects, screens and places of this life on screen. Night city "
                         "skylines and warm interiors for emotional beats. Everyone dressed normally: nothing "
                         "suggestive, nothing graphic.",
            "characters": [("You", "the protagonist ('you'), the person in the title: a simple cartoon figure with a "
                                   "large perfectly round plain white head, small black dot eyes; hair, body and outfit "
                                   "follow who the protagonist is in this video; same look in every image")],
            "thumb_style": "Vibrant, detailed comic-book cartoon illustration (NOT stick figures): the video's "
                           "protagonist, three-quarter body, confident knowing expression, dressed normally, holding "
                           "the premise's key prop, with a thick white sticker outline around them; behind them the "
                           "most iconic setting of this life at golden hour or night, with a few small background "
                           "people. Warm saturated colors, clean bold outlines, nothing suggestive, no text.",
        }},
        "variant_default": "pov_life",
        "variant_match": r"(?i)\b(marr(y|ies|ied|iage)|wife|husband|fall(s|ing)?\s+in\s+love|date|dating|"
                         r"girlfriend|boyfriend|bride|wedding|love)\b",
        "thumb_style": "Vibrant, detailed comic-book cartoon illustration (NOT stick figures): one beautiful stylized "
                       "woman of the video's nationality / identity, three-quarter body, confident knowing smile, in an "
                       "iconic outfit of her culture, holding a bouquet of red roses (or the premise's key prop), with a "
                       "thick white sticker outline around her; behind her the most iconic landmark or setting of her "
                       "country / world at golden hour or night, with a few small background people; the country's flag "
                       "as a flat rectangle with a thin black border in the top-left corner (no flag if no country). "
                       "Warm saturated colors, clean bold outlines, no text.",
        "bible": "",
    },
    "oddly_expensive_en": {
        "name": "Oddly Expensive Lives — The Economics of… (EN)", "language": "en", "format": "economics_of",
        "reference_urls": "https://www.youtube.com/watch?v=kY-3P95Ua9Q",
        "youtube_handle": "@OddlyExpensiveLives",
        "studio": {"brand": "Oddly Expensive Lives", "logo": "OEL", "ref_name": "Gray Economy, Never Retiring",
                   "placeholder": "The Economics of a Divorce",
                   "sub": "script FacelessOS façon cours (le prof explique la facture poste par poste), voix Algrow, "
                          "prof animé sur le tableau, images, musique et montage.",
                   "thumb_prompt": "A 3-5 word title about \"{title}\" (like 'THE DIVORCE TRAP'); the teacher "
                                   "at a desk or counter handing over the bill, 1-2 emotional comic characters on "
                                   "the left, the key props in the middle and 4-6 labels with arrows, each a real "
                                   "number from the video."},
        "niche": "The real bill of life's biggest and darkest moments (a divorce, dying, prison, having a kid, an "
                 "ambulance ride), explained by a teacher: every line item, who gets paid, and how people pay less",
        "audience": "US adults 25-54 (plus UK, Canada, Australia) who fear big surprise bills and love 'how it really "
                    "works' money content",
        "tone": "A calm, confident teacher explaining a bill to his class: plain words, contractions, patient, dry "
                "one-line humor about the system, fully serious on death, illness and prison. Never moralizes, "
                "never sells.",
        "rules": "One running tab per video for one typical case, read out after every lesson; the final total is "
                 "the payoff. Only real, rounded figures with the source named in the sentence, otherwise a stated "
                 "estimate or range. General information, never personal financial or legal advice. Three CTAs max: "
                 "~5 min, ~70%, end.",
        "style": "osl_stick", "voice_provider": "algrow", "voice": "rU18Fk3uSDhmg5Xh41o4", "wpm": 158,
        "no_text": True, "voice_speed": 1.0,
        "direction": "SIMPLE, READABLE IMAGES: one clear idea per image that literally shows what the sentence says, "
                     "1-3 characters at most, a few large simple objects, a clean uncluttered background, no small "
                     "details, nothing weird or illogical. "
                     "Alternate between (a) scenes: the white round-headed people living the moment in real, richly "
                     "lit places (a lawyer's office, a courthouse hallway, a hospital corridor, a kitchen table covered "
                     "in envelopes, a funeral home showroom, a prison visiting room, the back of an ambulance) and (b) "
                     "explainer visuals drawn in the same cartoon style: the growing itemized bill on a long paper "
                     "receipt, a price tag, an invoice with one line circled in red, a bar chart, a pie chart of who "
                     "gets the money, a timeline, a calendar, a stack of cash next to a single coin, a map with a "
                     "route, all without any written numbers or words: the editor adds the numbers, labels, "
                     "receipts and charts on top as animations, so keep the upper-left and right side of each image "
                     "calm. Respectful on death, illness and prison: no blood, no gore, no bodies.",
        "default_minutes": 14,
        # rythme posé : le prof prend le temps d'expliquer (scènes de ~8 s, jamais moins de 4,5 s)
        "montage": {"pacing": 8.5, "hook_pacing": 6.0, "hook_seconds": 30, "min_scene": 4.5, "max_scene": 15.0,
                    "motion": "zoom_in", "motion_strength": 0.05, "transition": "fade", "transition_dur": 0.4,
                    "section_titles": False, "captions": {"mode": "none"}, "layout": "board", "pause_max": 0.4,
                    "music": "auto", "music_volume": 0.12, "director": True, "intro": True, "outro": True,
                    "image_qa": True},
        # prof « acteur » : une pose par idée (presets/oddly_expensive_en/poses), choisie par le réalisateur
        "board": dict(board.THEMES["slate"], enabled=True, theme="slate", anim="none", presenter_height=0.5),
        "character": ("People", "every person in every image (spouses, lawyers, nurses, clerks, guards, the viewer) "
                                "is a simple cartoon figure with a large, perfectly round, plain WHITE head (no ears, "
                                "no nose), small solid black dot eyes, simple eyebrows and mouth, thick black outline, "
                                "slim simple body, white mitten hands; roles are shown only by clothes, hair and "
                                "props"),
        # le prof (bas gauche) : rig animé livré dans presets/oddly_expensive_en/presenter/
        "mascot": "the channel's teacher: a simple cartoon man with a large, perfectly round, plain WHITE head (no "
                  "hair, no ears, no nose), small solid black dot eyes under short relaxed black eyebrows, a "
                  "friendly, natural closed-mouth smile; a grey three-piece suit (light grey jacket with notched "
                  "lapels, darker charcoal waistcoat with black buttons, white shirt, black tie), a fan of green "
                  "dollar bills sticking out of the "
                  "breast pocket, grey trousers, black shoes, white mitten hands, thick clean black outlines",
        "thumb_text": True,
        # miniatures façon Marcus Explains (validées sur « The Divorce Trap ») ; presets/oddly_expensive_en/thumb.jpg
        "thumb_rev": 2,
        "thumb_style": "Bright saturated blue blueprint background with faint white technical grid lines and faint "
                       "blueprint sketches. A massive heavy condensed UPPERCASE title of 3-5 words in solid black with "
                       "a thick white outline filling the whole top band edge to edge, with a thick red marker "
                       "underline under it (e.g. 'THE DIVORCE TRAP', 'THE $61,000 DIVORCE'). Detailed comic-book "
                       "cartoon art, thick black outlines, cel shading, expressive faces. On the right, the channel's "
                       "teacher (exactly as in the reference: large round plain white head, grey three-piece suit, "
                       "dollar bills in the breast pocket, white mitten hands) with a calm, friendly, confident "
                       "closed-mouth smile (never a smirk), doing the key action of the story (sliding papers across "
                       "a desk, handing over a bill, ringing up a register). On the left, 1-2 detailed comic "
                       "characters with normal human faces and strong emotions (a glamorous, attractive woman in a "
                       "fitted dress, a sweating shocked man). The key props of the story on a desk or counter in "
                       "the middle. 4-6 short labels in black bold condensed UPPERCASE with a thick white outline, "
                       "each a real number from the video + 1-2 words ('$270/HR LAWYER', '$16,800 2ND RENT'), each "
                       "with a hand-drawn black curved arrow pointing at its prop.",
        "thumb_style_prev": ("Dark midnight-blue slate background with a subtle dot grid, like the channel's board. On "
                             "the right, the channel's teacher (exactly as in the reference image) pointing his stick "
                             "at the hero object with a friendly, natural expression. Center-left, ONE big hero object "
                             "that is the video's bill: a long itemized receipt, a hospital invoice, a price tag or a "
                             "commissary receipt, slightly tilted, with one line circled in red. ONE huge number in "
                             "heavy condensed bold yellow (#FFD447) with a thick black outline (the final total or the "
                             "most absurd line item, e.g. '$310,000', '$0.23/HOUR', '$3,200 FOR 4 MILES'), no other "
                             "words. One small white round-headed character reacting in shock. Clean bold outlines, "
                             "high contrast, readable at small size.",
                             "Dark midnight-blue slate background with a subtle dot grid, like the channel's board. On "
                             "the right, the channel's teacher (exactly as in the reference image) pointing his stick "
                             "at the hero object with a knowing look. Center-left, ONE big hero object that is the "
                             "video's bill: a long itemized receipt, a hospital invoice, a price tag or a commissary "
                             "receipt, slightly tilted, with one line circled in red. ONE huge number in heavy "
                             "condensed bold yellow (#FFD447) with a thick black outline (the final total or the most "
                             "absurd line item, e.g. '$310,000', '$0.23/HOUR', '$3,200 FOR 4 MILES'), no other words. "
                             "One small white round-headed character reacting in shock. Clean bold outlines, high "
                             "contrast, readable at small size."),
        "bible": "",
    },
    "oddly_things_en": {
        "name": "Oddly Specific Things — Your Life as a… (EN)", "language": "en", "format": "object_journey",
        "niche": "Second-person POV journeys of objects: you ARE a stolen phone, a stolen car, a stolen bank card, an "
                 "Amazon return, a donated T-shirt... followed hand to hand through the real hidden economy behind it",
        "audience": "Men and women 16-44 (US, UK, worldwide) who love 'what really happens to...' stories, hidden "
                    "economies and true crime told lightly",
        "tone": "Calm, dry, observant second-person narrator: you are the object. Quiet humor about humans, fully "
                "serious about the people who lose things. Never glamorizes crime.",
        "rules": "Follow the object from its first owner to where it really ends up, in the real order of the real "
                 "supply chain. Real places, methods and prices from research, rounded; typical estimates are said "
                 "as estimates. Never a how-to.",
        "reference_urls": "https://www.youtube.com/watch?v=oFKjAJrLims",
        "youtube_handle": "@OddlySpecificThings",
        "studio": {"brand": "Oddly Specific Things", "logo": "OST", "ref_name": "Mr. Ranks, Crypto Miner",
                   "placeholder": "Your Life as a Stolen Phone",
                   "sub": "script FacelessOS (tu es l'objet, main après main), voix Algrow, objet-personnage "
                          "consistant, cartes « HAND #n », trajets, musique et montage.",
                   "thumb_prompt": "The key moment of \"{title}\": the object (with its tiny worried face) in the "
                                   "hands that take it, on a clean white background, 2 handwritten words, one "
                                   "black arrow."},
        "style": "osl_stick", "voice_provider": "algrow", "voice": "rU18Fk3uSDhmg5Xh41o4", "wpm": 158,
        "no_text": True, "voice_speed": 1.0,
        "direction": "YOU are the object of the title (the narrator): show it in almost every image, big and easy to "
                     "spot, in the hands, pockets, bags, boxes, tables, cars and rooms it passes through, its tiny "
                     "face showing its mood. The people who hold it are the channel's white round-headed figures "
                     "(roles shown by clothes and props: hoodies, gloves, aprons, suits). Real, richly lit places of "
                     "each step (a café terrace at night, a back-room repair shop, a warehouse near an airport, a "
                     "cargo plane hold, a crowded electronics market, a quiet bedroom). Close-ups on hands and on "
                     "the object, then wide shots of the place. Sometimes a simple explainer visual in the same "
                     "style (a map with a route, a stack of cash next to the object, a price tag, a box of identical "
                     "objects). No written words or numbers: the editor adds them as animations. Nothing graphic.",
        "default_minutes": 14,
        "montage": {"pacing": 6.5, "hook_pacing": 5.0, "hook_seconds": 30, "min_scene": 3.5, "max_scene": 11.0,
                    "motion": "zoom_in", "motion_strength": 0.06, "transition": "fade", "transition_dur": 0.4,
                    "section_titles": False, "captions": {"mode": "none"}, "layout": "full", "pause_max": 0.45,
                    "music": "auto", "music_volume": 0.13, "director": True, "image_qa": True,
                    "chapter_cards": True},
        "character": ("You", "the object of the title, who narrates ('you'): drawn as a cartoon object in the same "
                             "bold-outline style, with a tiny simple face on its front or screen (two small solid "
                             "black dot eyes, small eyebrows, a small simple mouth), no arms and no legs; the exact "
                             "same object, color, case and face in every image; its face shows its mood"),
        "object_hero": True,  # le perso « You » est un objet (image de référence sans bras ni jambes)
        # réalisateur du montage : pas de prof, des cartes « HAND #n » posées d'après les titres de partie
        "director": "It is a second-person POV story told by an object (\"you\" = the object of the title) that "
                    "passes from hand to hand. Full-screen illustrations, no presenter. Each new hand already gets "
                    "its own \"HAND #n\" card automatically at the start of its part: never add another animation "
                    "in those first scenes.",
        "fx_types": ["counter", "route", "label", "stamp", "list", "timeline", "split", "bars"],
        "fx_density": "about 30-40% (a story first: most scenes stay clean, animations only for the numbers, "
                      "places and insider words that matter)",
        "fx_rules": "Counters: only a real amount or count said aloud, label = exactly what the narration says "
                    "(\"A DAY\", never \"TODAY\" if it says a day), \"from\" lower than \"to\". Route: only "
                    "when the object itself physically travels between two real named places (never a dot on a "
                    "map, never a person's walk). Label: only a real insider term, tool or place being named "
                    "(FARADAY BAG, LOST MODE, FREE PORT), never a description of the scene (EMPTY TABLE) and "
                    "never a phrase with brackets. Never two animations about the same number in a row.",
        "fx_guide": """ANIMATION TYPES (at most ONE per scene, JSON objects; "at" = the exact word of THIS scene's narration where it
appears, usually the number or the keyword):
- {"type":"counter","to":"$300","from":"$0","label":"WHAT YOU'RE WORTH NOW","at":"300"} : what the object is
  worth, paid or sold for at this hand, or one big number said aloud. The value of the object is the video's thread:
  use it at most hands, label 2-5 words (WHAT YOU'RE WORTH NOW, PAID TO THE THIEF, SOLD FOR, PHONES STOLEN IN 2024).
- {"type":"route","from":"LONDON","to":"HONG KONG","sub":"6,000 MILES BY AIR","at":"Hong Kong"} : the object
  travels from one real place to another (street to shop, city to city, country to country); "sub" = how or how
  far, only if said (optional).
- {"type":"label","text":"FARADAY BAG","at":"bag"} : a new insider term, tool or place being named, 1-3 words.
  At most one label every 30 seconds.
- {"type":"stamp","text":"BLACKLISTED","at":"blacklisted"} : a verdict of 1-2 words (STOLEN, LOCKED, WIPED, SOLD,
  BLACKLISTED, UNLOCKED, SHIPPED...), shown straight at the bottom of the screen. Rare: 3 per video at most, never
  two within 2 minutes.
- {"type":"list","title":"WHAT SHE LOSES","items":[{"text":"Every photo since 2019","at":"photos"}],"at":"first"} :
  3-6 short points (<= 5 words each) spoken in THIS scene, each appearing when its "at" word is spoken.
- {"type":"timeline","title":"YOUR FIRST 24 HOURS","items":[{"label":"9:47 PM","sub":"Snatched"},...],
  "at":"hours"} : steps in time (3-5 steps).
- {"type":"split","left":{"title":"LOCKED","value":"$300","sub":"sold for parts"},"right":{"title":"UNLOCKED",
  "value":"$1,000","sub":"sold whole"},"at":"unlocked"} : two options face to face.
- {"type":"bars","title":"WHO MAKES WHAT","items":[{"label":"Thief","value":300,"display":"£300"},{"label":
  "Buyer in China","value":4000,"display":"£4,000"}],"at":"4,000"} : 2-4 amounts being compared.""",
        "thumb_text": True,
        # miniatures très simples et propres : style 2D de la chaîne, un sujet, beaucoup de blanc, 1-2 mots
        "thumb_style": "Very simple, clean, polished thumbnail in the channel's own 2D cartoon style (smooth clean black "
                       "outlines, soft cel shading, simple characters with a large perfectly round plain WHITE head, "
                       "small black dot eyes, white mitten hands; never gritty, never dark, never realistic). ONE clear "
                       "subject, big, on a flat pure white or soft light-grey background with lots of empty space, or "
                       "one simple, softly lit real setting: the object of the title (drawn as a normal, beautiful "
                       "object, no face) in the hands of the person who takes it, or that person running off with it, "
                       "or the object on its way between two famous places. Soft vivid colors. Text: 1-2 big words "
                       "('GONE FOREVER', 'STOLEN') or a short price change ('£300 → £4,000'), nothing else.",
        "thumb_text_style": "Big clean heavy rounded sans-serif letters, the first word in black and the last word in "
                            "red, no outline, perfectly legible, spelled exactly.",
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
    "oddly_expensive_en": """REFERENCE. Built from Gray Economy's outlier "The Economics of Never Retiring" (140k views on a 2k-sub channel, 13:59, 2,259 words, 161 wpm), a 2D "Economics of X" life-event explainer. It teaches the register, pacing, number handling and beat map. Never reuse its topic, lines or hooks. This channel adds what it lacks: the on-screen teacher, one typical case and the running tab. FacelessOS rules win on any conflict.
HOOK (~80-120 words, 0:00-0:35, no intro). Then vs now or belief vs reality in two lines, one hard statistic with its source, "And here's the strange part.", a reversal of the obvious answer, and a short threat aimed at the viewer ("That plan has a price. Somebody is already calculating it."). Teaching starts immediately after: the first ~90 seconds hold about 260 words and 8 figures.
BEAT MAP (share of runtime). Cold open 3% → how the system got this way, with a numbered frame ("it stood on three legs") 12% → the base bill 10% → the "obvious fix" and its catch 6% → who profits, parties listed one by one 16% → who pays when it breaks 16% → hidden costs nobody puts on the bill 15% → step back to the whole system 12% → verdict and ledger 9% → one soft CTA 1%. In this channel the typical case and the running tab thread through all of it, and the moves that cut the bill sit inside the verdict.
VOICE. Calm, dry, never hyped; the teacher speaks to "you" about 3-4 times a minute. Sentences average ~12 words (median ~10); about a quarter are 6 words or fewer ("The rest is your problem."). Deadpan aphorisms instead of jokes ("A back that holds up fine at 55 is different equipment at 68."). Honest hedges where the data is soft ("roughly", "about", "projections, not prophecies").
NUMBERS. About 7 figures a minute, one every ~9 seconds, mixing dollars, percentages, years and ages. Pattern: figure → source named in the sentence (a federal agency, a named survey or research group) → one plain translation line ("replaces roughly 37%. So it covers about a third of the old paycheck."). Round, then restate simply ("$2,070 a month. Call it 25,000 a year."). Say out loud whether a figure is an average or a median.
TEACHING DEVICES. Define each term inside the sentence the first time ("technically a defined benefit plan, meaning..."). Listed ladders ("Take employers first... Then... Finally..."). A one-line recap about every 2 minutes ("That's the pitch." "That's the buried cost of the plan."). Expectation vs reality pairs ("Ask workers... Ask retirees..."). This channel adds: one typical case introduced early, and the running total read after every lesson.
RE-HOOKS. A section opener every 1.5-2 minutes that pulls the next question forward: "The catch is...", "So who covers the difference?", "The costs that never make the headlines...", "Step back."
ENDING. Concede the upside first (who it works for), then name exactly where the math breaks. Read the ledger: "Who benefits is reasonably clear... Who carries the risk is just as clear." Then the final itemized bill and total, and a three-sentence kicker that calls back to the opening line. One short CTA, then stop.
FACELESSOS LIMITS ON THE REFERENCE'S HABITS. Its "isn't X, it's Y" reversals and aphoristic verdicts are capped: at most 2 antithesis constructions and 1 aphoristic closer per script, never in adjacent paragraphs. No em dashes. Every statistic must be real, widely documented and rounded; anything else becomes a stated estimate or range.""",
    "oddly_things_en": """REFERENCE. Register built from Mr. Ranks' outlier "POV: You're a Crypto Miner Who Starts With One GPU" (263k views on a 26k-sub channel, 28:05, 4,268 words, 152 wpm), a 2D second-person POV story that escalates step by step. It teaches the register, rhythm and pacing. Never reuse its topic, lines or hooks. This channel's twist: "you" are the object in the title, passed from hand to hand. FacelessOS rules win on any conflict.
VOICE. Second person, present tense, plain spoken English. Short sentences: about 8 words on average, one in four is 1-4 words ("You hesitate." "But it's real."), almost none over 25 words. Lists of three concrete nouns ("Wallet address, mining pool, config file."). Exact small times and amounts ("around 11:40 p.m.", "a few dollars"). Dry understatement about humans and what they care about.
HOOK (0:00-0:40, ~100 words). Sentence one is the moment you change hands, with a time, a real place and one physical detail of you (battery, fuel, a crack, a sticker). Two lines on the life you were part of a minute ago. Then the promise in plain numbers: how many hands, how many miles, what you'll be worth at the end. No intro, no title restated.
BEING AN OBJECT. You never move or talk. You perceive: light through fabric, the cold of a car park, the hum of a van, voices that don't know you're listening, your own screen lighting up with a name nobody answers. Feelings come through what you notice, never through stated emotions ("Your screen lights up. Mum. Nobody looks at it."). You know your worth and keep track of it.
HANDS. Every hand opens on a fresh scene (place, time, light, one sound), then the person through one telling habit or tool (they get roles, never names: "the man with the foil", "the woman at the stall by the escalator"), then what they do with you and how this step of the machine works, then the number: what you're worth here. Close each hand on a one-line pull ("He doesn't keep you long.").
NUMBERS. Few, exact, spoken naturally, from the research notes only. Big real facts carry their source lightly inside the sentence ("Police in London later said..."). Every hand states your worth; the final worth is compared with your first price in the ending.
PACING. A small reveal about the hidden machine every 60-90 seconds; a re-hook at every hand-off. Time moves inside the narration ("By Monday", "Six days later", "Somewhere over Russia"), never with headings.
OWNER CUTAWAYS. Two or three short, quiet moments of the first owner's side, told as what you imagine or overhear. Never mock them.
ENDING. The last hand is quiet: someone who doesn't know your story uses you for something ordinary; one trace of the first owner is called back; the last image is physical and still.
AVOID. The reference's tics: "not X, just Y" and "You tell yourself" at most twice each, no fragment drumbeats, at most 2 antithesis constructions and 1 aphoristic closer per script, no em dashes, no CTA, no trailer voice. Never a how-to (no steps to steal, unlock or resell).""",
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


def _bundled_refs(urls_text, ext=".txt"):
    """Transcriptions (ou descriptions) de référence livrées avec l'app (skills/references/<id><ext>)."""
    return "\n\n".join(t for t in (FOS.bundled_reference(v, ext) for v in _video_ids(urls_text)) if t)


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
        "reference_description": _bundled_refs(t.get("reference_urls", ""), ".description.txt"),
        "youtube_handle": t.get("youtube_handle", ""),
        "bible": t.get("bible") or TEMPLATE_BIBLES.get(template or "", ""),
        "wpm": t.get("wpm", 150), "thumb_style": t.get("thumb_style", ""),
        "thumb_text": t.get("thumb_text", True), "thumb_ref": None, "thumb_rev": t.get("thumb_rev", 0),
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
    ch["template"] = template or ""
    ch = apply_channel_update(ch, data)
    _apply_preset_images(ch, template)
    store.save_channel(ch)
    return ch


PRESETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "presets")


def _apply_preset_images(ch, template):
    """Images livrées avec un modèle (presets/<modèle>/style.jpg, thumb.jpg), posées seulement là
    où la chaîne n'a encore rien : elle est prête d'emblée, et tes propres images ne sont jamais écrasées."""
    d = os.path.join(PRESETS_DIR, template or "")
    for kind, name in (("style", "style.jpg"), ("thumb", "thumb.jpg")):
        path = os.path.join(d, name)
        has = (ch.get("style") or {}).get("ref") if kind == "style" else ch.get("thumb_ref")
        if not template or has or not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            rel = save_channel_image(ch, f.read(), kind)
        if kind == "style":
            ch.setdefault("style", {})["ref"] = rel
        else:
            ch["thumb_ref"] = rel
    rig = os.path.join(d, "presenter")  # prof livré avec le modèle (rig animé déjà construit)
    bd = ch.get("board") or {}
    pdir = os.path.join(d, "poses")  # bibliothèque de poses du prof (réalisation du montage)
    if template and not bd.get("poses") and presenter.load_poses(pdir):
        import shutil
        rel_p = f"refs/poses_{int(time.time() * 1000)}"
        shutil.copytree(pdir, os.path.join(store.channel_dir(ch["id"]), rel_p))
        bd = dict(bd, poses=rel_p)
        idle = os.path.join(store.channel_dir(ch["id"]), rel_p, "idle.png")
        if not bd.get("presenter") and os.path.isfile(idle):
            bd = dict(bd, presenter=f"{rel_p}/idle.png", rig=None, anim="none")
        ch["board"] = bd
    man = presenter.load_manifest(rig) if template and uses_board(ch) and not bd.get("presenter") else None
    if man:
        import shutil
        rel_dir = f"refs/rig_{int(time.time() * 1000)}"
        shutil.copytree(rig, os.path.join(store.channel_dir(ch["id"]), rel_dir))
        ch["board"] = dict(bd, presenter=f"{rel_dir}/A.png", rig=rel_dir, anim=man["mode"])


def _refresh_from_template(c, template):
    """Complète une chaîne de studio avec ce que le modèle a gagné depuis sa création
    (vidéo de référence, description modèle, handle) sans écraser ce que tu as réglé."""
    t = TEMPLATES[template]
    changed = False
    if not (c.get("reference_scripts") or "").strip() and t.get("reference_urls"):
        # chaîne d'avant la vidéo de référence : on reprend l'écriture actuelle du modèle
        c["reference_urls"] = t["reference_urls"]
        c["reference_scripts"] = _bundled_refs(t["reference_urls"])
        c["bible"] = t.get("bible") or TEMPLATE_BIBLES.get(template, c.get("bible", ""))
        c["tone"], c["rules"] = t.get("tone", c.get("tone", "")), t.get("rules", c.get("rules", ""))
        changed = True
    if not (c.get("reference_description") or "").strip() and t.get("reference_urls"):
        c["reference_description"] = _bundled_refs(t["reference_urls"], ".description.txt")
        changed = changed or bool(c["reference_description"])
    if not c.get("youtube_handle") and t.get("youtube_handle"):
        c["youtube_handle"] = t["youtube_handle"]
        changed = True
    if (c.get("thumb_rev") or 0) < t.get("thumb_rev", 0):
        # nouveau style de miniature du modèle : appliqué, sauf si tu avais écrit le tien
        if not (c.get("thumb_style") or "").strip() or c.get("thumb_style") in t.get("thumb_style_prev", ()):
            c["thumb_style"] = t["thumb_style"]
        c["thumb_rev"] = t["thumb_rev"]
        changed = True
    refs = lambda: ((c.get("style") or {}).get("ref"), c.get("thumb_ref"), (c.get("board") or {}).get("presenter"),
                    (c.get("board") or {}).get("poses"))
    before = refs()
    _apply_preset_images(c, template)
    changed = changed or refs() != before
    if changed:
        store.save_channel(c)
    return c


def studio_channel(template):
    """La chaîne d'un studio simplifié (ex. Oddly Specific Lives) : retrouvée par son modèle, créée sinon."""
    if template not in TEMPLATES:
        raise KeyError(template)
    t = TEMPLATES[template]
    name = t.get("name", "")
    for c in store.list_channels():
        if c.get("template") == template:
            return _refresh_from_template(c, template)
    for c in store.list_channels():  # chaîne créée avant qu'on mémorise le modèle
        if not c.get("template") and c.get("format") == t.get("format") and \
                (c.get("name") == name or (c.get("style") or {}).get("preset") == t.get("style")):
            c["template"] = template
            store.save_channel(c)
            return _refresh_from_template(c, template)
    return new_channel({}, template=template)


def studio_list():
    """[{key, brand, logo}] : les chaînes qui ont un studio simplifié (sélecteur du studio)."""
    return [dict(key=k, brand=t["studio"]["brand"], logo=t["studio"]["logo"])
            for k, t in TEMPLATES.items() if t.get("studio")]


def pick_format(ch, title, wanted=None):
    """Format d'une vidéo de studio : celui demandé, sinon d'après le titre (ex. « Marry » → POV mariage,
    « Inside the Life of… » → POV vie). None = format de la chaîne."""
    t = TEMPLATES.get(ch.get("template") or "", {})
    variants = t.get("variants") or {}
    if wanted in variants:
        return wanted
    if wanted == ch.get("format") or not variants:
        return None
    if re.search(t.get("variant_match") or r"$^", title or ""):
        return None
    return t.get("variant_default")


def studio_formats(ch):
    """[{key, name}] : le format de la chaîne puis ses variantes (choix « Format » du studio)."""
    keys = [ch.get("format")] + list((TEMPLATES.get(ch.get("template") or "", {}).get("variants") or {}))
    return [{"key": k, "name": S.FORMATS[k]["name"]} for k in dict.fromkeys(keys) if k in S.FORMATS]


def project_channel(pr):
    """La chaîne telle que la voit cette vidéo : pr["format"] peut choisir une variante du modèle
    (autre format, même voix/style). La copie n'est jamais enregistrée."""
    ch = store.get_channel(pr["channel_id"])
    fmt = (pr or {}).get("format")
    if not ch or not fmt or fmt == ch.get("format"):
        return ch
    v = ((TEMPLATES.get(ch.get("template") or "", {}).get("variants") or {}).get(fmt)) or {}
    ch = json.loads(json.dumps(ch))
    ch["format"] = fmt
    for k in ("niche", "rules", "tone", "bible_note", "thumb_style"):
        if v.get(k):
            ch[k] = v[k]
    st = ch.setdefault("style", {})
    if v.get("direction"):
        st["direction"] = v["direction"]
    if v.get("characters") is not None:
        old = {_norm_name(c["name"]): c for c in st.get("characters") or []}
        st["characters"] = [{"id": (old.get(_norm_name(n)) or {}).get("id") or store.new_id("chr"), "name": n,
                             "description": d, "image": None, "always": i == 0}
                            for i, (n, d) in enumerate(v["characters"])]
    return ch


_CH_FIELDS = ("name", "language", "format", "niche", "audience", "tone", "rules", "cta", "reference_scripts",
              "reference_description", "youtube_handle",
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
    return anim if anim in ("none", "stick") else "poses"  # anciens réglages (full…) → poses


def save_presenter(ch, blob, anim="poses"):
    """Enregistre le prof dans refs/rig_<ts>/ (base.png + poses + rig.json).

    anim = « stick » : un seul dessin du prof ; sa baguette est effacée puis redessinée par le code,
           et elle pivote dans son poing, de façon fluide (quelques secondes, aucune IA) ;
           « poses » : l'IA redessine le bras dans 3 autres positions (3 retouches en parallèle,
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
    if anim == "stick" and presenter.build_stick_rig(blob, out_dir):
        return f"{rel_dir}/A.png", rel_dir
    if anim == "poses":
        def edit(k):
            out = None
            for _ in range(2):  # 2e essai si l'IA a redessiné tout le perso au lieu du bras
                try:
                    out = ai.generate_image(presenter.POSE_EDITS[k], width=1024, height=1536, refs=[blob],
                                            quality="high", transparent=True)
                except ai.AIError as e:
                    if getattr(e, "status", None) == 4290:  # quota épuisé : on le dit, pas d'échec silencieux
                        raise
                    return k, None
                if presenter.pose_ok(blob, out):
                    return k, out
            return k, out  # écartée par build_pose_rig : la pose voisine la remplace
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
    ch = project_channel(pr)
    if not ch:
        raise RuntimeError("Chaîne introuvable.")

    def prog(p, msg, partial):
        job.update(0.02 + 0.96 * p, msg)
        if partial:
            store.update_project(pid, lambda x: x.__setitem__("script_draft", partial))

    res = S.generate(ch, pr["title"], pr["minutes"], pr.get("notes") or "", polish=polish, progress=prog,
                     history=channel_history(ch["id"], exclude=pid), rounds=pr.get("fos_rounds"))

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
    ch = project_channel(pr)
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
    ch = project_channel(pr)
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
    ch = project_channel(pr)
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
                         instructions=vs.get("instructions", ""), progress=prog, lang=ch.get("language"))
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
            if i > 0:  # seule dans sa partie et trop courte : rattachée à la scène d'avant
                out[i - 1]["text"] += " " + out[i]["text"]
                out.pop(i)
                continue
            out[i]["text"] += " " + out[i + 1]["text"]
            out.pop(i + 1)
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
    ch = project_channel(pr)
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


def _object_hero(ch):
    """Le narrateur « You » de cette chaîne est un objet (ex. Oddly Specific Things)."""
    return bool(TEMPLATES.get((ch or {}).get("template") or "", {}).get("object_hero"))


def character_ref_image(ch, member):
    """Image de référence d'un perso : en pied, de face, fond uni — dans le style de la chaîne."""
    prompt = (f"Character reference image of \"{member['name']}\": {member.get('description', '')}. "
              "Full body, standing, front view, neutral relaxed pose, arms along the body, calm expression, "
              "centered, plain light grey background, nothing else in the image.")
    if _object_hero(ch) and _norm_name(member.get("name")) == "you":  # le narrateur est un objet
        prompt = (f"Character reference image of \"{member['name']}\": {member.get('description', '')}. "
                  "The object alone, front view, upright, centered, calm neutral face, no arms, no legs, no hands "
                  "holding it, plain light grey background, nothing else in the image.")
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
    ch = project_channel(pr)
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
        return max(1, min(16, int(os.getenv("AI_IMAGE_CONCURRENCY", "12"))))
    except ValueError:
        return 6


IMAGE_QA = """You are the quality checker of a 2D cartoon explainer channel. Look at this generated image for the
scene below and reject it only for REAL, visible mistakes a viewer would notice:
- anatomy errors (extra or missing arms, hands or heads, two heads, fused bodies, broken limbs);
- objects that make no sense or are upside down / facing the wrong way / floating;
- any readable text, letters or numbers (blank papers and screens are fine){no_text}
- the image does not show what the narration says, or it is confusing (too many things, no clear subject).
NARRATION: {text}
PROMPT: {prompt}
Return JSON {{"ok": true|false, "problems": ["short, concrete problem", ...]}}."""


def check_image(path, sc, no_text=True):
    """Contrôle en vision d'une image de scène → (ok, [problèmes])."""
    import base64
    with open(path, "rb") as f:
        blob = _jpeg(f.read(), side=896)
    q = IMAGE_QA.format(text=(sc.get("text") or "")[:400], prompt=(sc.get("prompt") or "")[:500],
                        no_text=";" if no_text else " (ignore this rule: text is allowed on this channel);")
    content = [{"type": "text", "text": q},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(blob).decode()}}]
    res = ai.chat_json([{"role": "user", "content": content}], model=ai.text_model(), timeout=120)
    return bool(res.get("ok", True)), [str(x) for x in res.get("problems") or []][:4]


def _gen_scene(ch, pr, sc):
    """Image d'une scène, contrôlée en vision (chaîne qui l'active) : refaite une fois si elle a une erreur."""
    w, h = dims(pr)
    d = store.project_dir(pr["id"])
    rel = f"images/scene_{sc['i']:04d}_{int(time.time() * 1000) % 10**9}.jpg"
    prompt = sc["prompt"]
    qa = bool((pr.get("montage") or {}).get("image_qa"))
    no_text = (ch.get("style") or {}).get("no_text", True) is not False
    for attempt in range(2 if qa else 1):
        generate_scene_image(ch, prompt, os.path.join(d, rel), scene_chars=sc.get("chars"), width=w, height=h,
                             board_layout=uses_board(pr), cast=cast_list(ch, pr))
        if not qa or attempt == 1:
            break
        try:
            ok, problems = check_image(os.path.join(d, rel), dict(sc, prompt=prompt), no_text)
        except Exception:  # noqa: BLE001  (contrôle indisponible : on garde l'image)
            break
        if ok:
            break
        prompt = sc["prompt"] + " AVOID these mistakes of a previous attempt: " + "; ".join(problems) + "."
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
    ch = project_channel(pr)
    covered = {s["i"] for s in pr["scenes"] if (s.get("fx") or {}).get("type") in _full_panel()}
    if only is not None:
        targets = [s for s in pr["scenes"] if s["i"] in set(only) and s["i"] not in covered]
    else:
        targets = [s for s in pr["scenes"] if not s.get("image") and s["i"] not in covered]
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

# ── Réalisation du montage : poses du prof + animations (motion design) ──────

POSE_HINTS = {
    "idle": "standing relaxed (neutral, rarely)",
    "explain": "open palm presenting to the right (default while explaining)",
    "point": "pointing at the board (when the narration refers to what is on screen)",
    "arms_crossed": "arms crossed, serious (warnings, hard truths)",
    "think": "hand on chin (questions, 'why', 'what if')",
    "shrug": "shrug (uncertainty, 'it depends', ranges)",
    "shocked": "hands on cheeks, mouth open (a shocking number)",
    "money": "counting cash (payments, fees, who gets paid)",
    "facepalm": "facepalm (costly mistakes)",
    "calculator": "looking at a calculator (math, adding up, per hour)",
    "thumbs_down": "thumbs down (bad deal, worst option)",
    "wave": "waving (very first scene and very last scene only)",
    "hold_sign": "holds a blank card: write the key number or 1-3 words on it",
    "hold_phone": "holds a phone facing the viewer: write a short number or 1-3 words on its screen (apps, online, "
                  "bank, bills by text)",
}

FX_GUIDE = """ANIMATION TYPES (at most ONE per scene, JSON objects; "at" = the exact word of THIS scene's narration where it
appears, usually the number or the keyword):
- {"type":"label","text":"THE RETAINER","at":"retainer"} : a new term being defined or a lesson title, 1-3 words.
  Not too many: at most one label every 30 seconds.
- {"type":"counter","to":"$61,000","from":"$0","label":"FINAL BILL","at":"61,000"} : one big number said aloud.
- {"type":"receipt","items":[{"item":"Custody evaluation","amount":"$2,000"}],"total":"$23,200","at":"2,000"} :
  ONLY when the narration adds a line to the running tab or reads the running total; items = only the line(s)
  added in this scene (item <= 4 words), total = the running total stated in the narration.
- {"type":"bars","title":"AVERAGE COST PER PERSON","items":[{"label":"Settled","value":10600,"display":"$10,600"},
  {"label":"Trial","value":20400,"display":"$20,400"}],"at":"20,400"} : 2-4 amounts being compared.
- {"type":"split","left":{"title":"SETTLE","value":"$10,600","sub":"per person"},"right":{"title":"TRIAL",
  "value":"$20,400","sub":"per person"},"at":"trial"} : two options face to face.
- {"type":"pie","title":"WHO GETS PAID","items":[{"label":"Lawyers","value":21200},...],"at":"lawyers"} : a split
  of one sum between 2-6 parties, with the real amounts.
- {"type":"sheet","title":"THE CASE","items":[{"text":"Married couple in Ohio","at":"Ohio"},{"text":"Both in their
  40s","at":"40s"}],"at":"married"} : a FACT SHEET that REPLACES the illustration for the whole scene, with one dash
  line per characteristic, each appearing when its "at" word is spoken. Use it when the narration of THIS scene lists
  3-6 characteristics or facts of a person, a case, a household or a thing (who they are, what they have). Lines
  <= 6 words, faithful to the narration, numbers exactly as spoken. If the enumeration continues in the NEXT scene,
  give that scene a sheet with the SAME title and only its new lines: it extends the same sheet on screen.
- {"type":"list","title":"HOW PEOPLE PAY LESS","items":[{"text":"Settle early","at":"settle"},{"text":"Use
  mediation","at":"mediation"}],"at":"first"} : a recap or a list of 3-6 short points (<= 5 words each) spoken in
  THIS scene, each appearing when its "at" word is spoken.
- {"type":"timeline","title":"A CONTESTED DIVORCE","items":[{"label":"Month 0","sub":"Lawyers hired"},...],
  "at":"months"} : steps or durations in time (3-5 steps).
- {"type":"stamp","text":"NOT INCLUDED","at":"not"} : a verdict of 1-2 words (PAID, DENIED, AVOIDED, NOT
  INCLUDED, SOLD...), shown straight at the bottom of the board. Rare: 3 per video at most, never two within
  2 minutes, only for a real verdict (never a disclaimer like "general info")."""


def _norm_tok(w):
    return re.sub(r"[^0-9a-z.]", "", (w or "").lower()).strip(".")


def _nums(text):
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


def _fx_numbers(fx):
    vals = []

    def walk(v):
        if isinstance(v, dict):
            for kk, vv in v.items():
                if kk != "at":
                    walk(vv)
        elif isinstance(v, list):
            for vv in v:
                walk(vv)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            vals.append(str(int(v)) if float(v).is_integer() else str(v))
        elif isinstance(v, str):
            vals.extend(_nums(v))
    walk(fx)
    return vals


def plan_montage(ch, pr, words, poses, log=None):
    """Le réalisateur (IA) : pour chaque scène, la pose du prof (+ texte de sa pancarte) et au plus
    une animation calée sur un mot. Chiffres vérifiés contre la narration (sinon l'animation saute).
    → {index_scène: {"pose", "sign", "fx"}}"""
    scenes = pr.get("scenes") or []
    narration = " ".join(s.get("text") or "" for s in scenes)
    allowed = _nums(narration) | _nums(S.narration(pr.get("script") or "")) | {"0"}  # 0 : départ d'un compteur
    pose_lines = "\n".join(f"- {k}: {v}" for k, v in POSE_HINTS.items() if k in poses)
    t = TEMPLATES.get(ch.get("template") or "", {})
    types = set(t.get("fx_types") or _motion_types())
    brief = t.get("director") or ("It is a teacher-style explainer: a cartoon teacher in a grey suit stands at the "
                                  "bottom-left of the screen next to a board that shows one illustration per scene.")
    density = t.get("fx_density") or "about 55-65%"
    pose_block = f"""TEACHER POSES (pick one per scene):
{pose_lines}
Rules for poses: match what the sentence does; keep the same pose for 2-3 consecutive scenes while the idea
continues, then change (never the same pose for more than 4 scenes in a row); use hold_sign / hold_phone about once
every 8-12 scenes, with "sign" = the key number or 1-3 words of that scene, UPPERCASE, max 14 characters (e.g.
"$270/HR", "77%", "12-18 MONTHS"). "wave" only for the very first scene of the video and the very last one.
""" if len(poses) > 1 else 'No presenter on screen: always return "pose": "idle" and "sign": "".\n'
    out, total_so_far, last_pose = {}, "", "wave"
    heads = {x.get("section"): x.get("heading") or "" for x in scenes if x.get("first")}
    chunk = 25  # réponses courtes : les très longues se font couper par le proxy
    for c0 in range(0, len(scenes), chunk):
        part = scenes[c0:c0 + chunk]
        rows = "\n".join(f'{s["i"]} [{s["start"]:.1f}-{s["end"]:.1f}s]{" ## " + s["heading"] if s.get("first") and s.get("heading") else ""}: {s.get("text") or ""}'
                         for s in part)
        prompt = f"""You are the video editor and motion designer of the faceless YouTube channel "{ch.get('name', '')}"
({ch.get('niche', '')}). The video is "{pr.get('title', '')}". {brief}
Your job: make it lively and clear, like a top channel, WITHOUT clutter.

{pose_block}
{t.get("fx_guide") or FX_GUIDE}
Clarity: text on screen must make sense on its own for a viewer outside the US. Never leave jargon or a vague
phrase alone on a sheet, list or label: add a 2-4 word gloss (e.g. "One 401(k) (retirement savings)", "3 fights: kids,
house, retirement", "QDRO (court order to split retirement)").
{t.get("fx_rules") or ""}
Density: {density} of scenes get an animation; never the same type in 3 consecutive animated scenes (receipt
excepted when the tab really changes); leave some scenes clean. Every number you write MUST appear exactly in the
narration (same digits); never compute new numbers, never invent sources. Text is English, short, UPPERCASE for
titles.
{('The running tab so far reads: ' + total_so_far) if total_so_far else ''}
Previous scene pose: {last_pose}.

SCENES (index [time]: narration):
{rows}

Return JSON: {{"scenes": [{{"i": <index>, "pose": "<pose>", "sign": "", "fx": null or {{...}}}}]}} with one entry
per scene above, in order."""
        try:
            res = ai.chat_json(prompt, model=ai.text_model())
        except ai.AIError as e:  # un paquet raté : ces scènes gardent un montage simple
            if log:
                log(f"scènes {c0}-{c0 + len(part) - 1} sans réalisation ({str(e)[:80]})")
            continue
        for e in res.get("scenes") or []:
            try:
                i = int(e.get("i"))
            except (TypeError, ValueError):
                continue
            pose = e.get("pose") if e.get("pose") in poses else "explain" if "explain" in poses else "idle"
            sign = str(e.get("sign") or "").upper().strip()[:16]
            if pose.startswith("hold_") and (not sign or not _nums(sign) <= allowed):
                pose, sign = "explain" if "explain" in poses else "idle", ""
            if not pose.startswith("hold_"):
                sign = ""
            fx = e.get("fx") if isinstance(e.get("fx"), dict) else None
            pose, sign, fx = _dedupe(pose, sign, fx, poses)
            ahead = 10 if fx and fx.get("type") == "timeline" else 3
            ctx = " ".join(x.get("text") or "" for x in scenes if i - 2 <= x["i"] <= i + ahead) + " " + \
                heads.get((scenes[i] if 0 <= i < len(scenes) else {}).get("section"), "")  # + titre de sa partie
            if fx and fx.get("type") == "counter" and str(fx.get("from") or "").strip() == str(fx.get("to") or "").strip():
                fx = None  # un compteur qui ne compte rien
            if fx and (fx.get("type") not in types or not set(_fx_numbers(fx)) <= allowed
                       or not _grounded(fx, ctx)):
                if log:
                    log(f"animation écartée (scène {i}) : {json.dumps(fx)[:120]}")
                fx = None
            if fx and fx.get("type") == "receipt" and fx.get("total"):
                total_so_far = str(fx["total"])
            out[i] = {"pose": pose, "sign": sign, "fx": fx}
            last_pose = pose
    return out


_STOP = {"the", "and", "for", "with", "that", "this", "your", "you", "from", "into", "what", "when", "who", "how",
         "per", "one", "two", "not", "are", "was", "his", "her", "its", "our", "their", "they", "them", "then"}


def _fx_words(fx):
    """Mots porteurs de sens écrits par une animation (titres, étiquettes, lignes)."""
    parts = []
    t = fx.get("type")
    if t in ("label", "stamp"):
        parts.append(fx.get("text") or "")
    elif t in ("list", "sheet"):
        parts += [fx.get("title") or ""] + [str(x.get("text") if isinstance(x, dict) else x)
                                            for x in fx.get("items") or []]
    elif t == "timeline":
        parts += [str((x or {}).get("sub") or "") for x in fx.get("items") or [] if isinstance(x, dict)]
    elif t == "receipt":
        parts += [str((x or {}).get("item") or "") for x in fx.get("items") or [] if isinstance(x, dict)]
    return [w for w in re.findall(r"[a-z]+", " ".join(parts).lower()) if len(w) > 2 and w not in _STOP]


def _grounded(fx, context):
    """Vrai si au moins la moitié des mots de l'animation sont dits autour de la scène (un mot peut
    être au singulier / pluriel, ou sa racine)."""
    words = _fx_words(fx)
    if not words:
        return True
    ctx = set(re.findall(r"[a-z]+", (context or "").lower()))
    stems = {w[:5] for w in ctx if len(w) > 4}
    hit = sum(1 for w in words if w in ctx or w.rstrip("s") in ctx or (len(w) > 4 and w[:5] in stems)
              or any(c.startswith(w) for c in ctx))  # pay → paying
    return hit * 2 >= len(words)


def _dedupe(pose, sign, fx, poses):
    """Pancarte et animation qui montrent la même chose : la pancarte reste si l'animation n'était
    qu'un chiffre ou un mot (compteur, étiquette, tampon), sinon l'animation reste."""
    if not (sign and fx and (_nums(sign) & set(_fx_numbers(fx)) or sign.lower() in json.dumps(fx).lower())):
        return pose, sign, fx
    if fx.get("type") in ("counter", "label", "stamp"):
        return pose, sign, None
    return ("point" if "point" in poses else "explain"), "", fx


NOTE_GAP = 25.0   # petites notes (étiquette, tampon) : au moins 25 s entre deux, sinon ça fait notification
STAMP_GAP = 120.0  # un tampon au plus toutes les 2 min…
STAMP_MAX = 3      # … et 3 par vidéo


def thin_notes(scenes):
    """Pas trop de petites notes à l'écran : une étiquette ou un tampon trop proche du précédent
    saute (la scène reste propre). → indices (dans `scenes`) des animations gardées."""
    keep, last_note, last_stamp, stamps = set(), -1e9, -1e9, 0
    for k, s in enumerate(scenes):
        f = s.get("fx")
        if not f:
            continue
        t = float(f.get("t", s.get("start") or 0.0))
        if f.get("type") in ("label", "stamp"):
            if t - last_note < NOTE_GAP:
                continue
            if f.get("type") == "stamp":
                if t - last_stamp < STAMP_GAP or stamps >= STAMP_MAX:
                    continue
                last_stamp, stamps = t, stamps + 1
            last_note = t
        keep.add(k)
    return keep


def _motion_types():
    from services import motion
    return motion.TYPES


def _fx_time(scene, fx, words):
    """Instant (s) du mot « at » dans la scène, sinon juste après le début de la scène."""
    at = _norm_tok((fx or {}).get("at"))
    t0, t1 = float(scene["start"]), float(scene["end"])
    if at:
        for w in words:
            if t0 - 0.05 <= float(w.get("s", 0)) <= t1 + 0.05:
                tok = _norm_tok(w.get("w"))
                if tok and (tok == at or (len(at) > 2 and (at in tok or tok in at))):
                    return max(t0, float(w["s"]) - 0.1)
    return t0 + min(0.4, (t1 - t0) * 0.2)


def _item_times(scene, fx, words):
    """Instants (s) où chaque ligne d'une fiche / liste est dite (mot « at » de la ligne), dans l'ordre."""
    items = [x for x in (fx or {}).get("items") or []]
    if not items or not any(isinstance(x, dict) and x.get("at") for x in items):
        return None
    t0, t1 = float(scene["start"]), float(scene["end"])
    pool = [w for w in words if t0 - 0.05 <= float(w.get("s", 0)) <= t1 + 0.05]
    out, pos, last = [], 0, t0 + 0.4
    for x in items:
        at = _norm_tok(x.get("at") if isinstance(x, dict) else "")
        found = None
        for j in range(pos, len(pool)):
            tok = _norm_tok(pool[j].get("w"))
            if at and tok and (tok == at or (len(at) > 2 and (at in tok or tok in at))):
                found = j
                break
        if found is not None:
            pos = found + 1
            last = max(last, float(pool[found]["s"]) - 0.1)
        else:
            last = last + 0.8
        out.append(round(min(last, t1 - 0.3), 3))
    return out


def fx_timing(scene, fx, words):
    """fx + « t » (instant d'apparition) et « item_t » (lignes) — une fiche démarre avec sa scène."""
    if not fx:
        return None
    full = fx.get("type") in _full_panel()
    out = dict(fx, t=round(float(scene["start"]) if full else _fx_time(scene, fx, words), 3))
    it = _item_times(scene, fx, words)
    if it:
        out["item_t"] = it
    return out


def _full_panel():
    from services import motion
    return motion.FULL_PANEL


_CHAPTER = re.compile(r"^\s*([A-Za-z]+)\s*#?\s*(\d+)\s*[:.\-\u2013\u2014]\s*(.+?)\s*$")


def chapter_card(scene):
    """Carte de partie d'après le titre de la partie (« Hand 3: The fence » → HAND #3 / THE FENCE),
    sur la première scène de la partie ; None sinon."""
    m = _CHAPTER.match(scene.get("heading") or "") if scene.get("first") else None
    if not m:
        return None
    return {"type": "chapter", "kicker": f"{m.group(1).upper()} #{m.group(2)}", "title": m.group(3).upper()[:32]}


def montage_enabled(pr):
    return bool((pr.get("montage") or {}).get("director"))


def channel_poses(ch):
    """Dossier (absolu) de la bibliothèque de poses du prof de la chaîne, ou None."""
    rel = board_config(ch).get("poses")
    d = channel_ref_path(ch, rel) if rel else None
    return d if d and presenter.load_poses(d) else None


def job_montage(job, pid):
    """Plan de montage : poses du prof + animations, enregistré scène par scène."""
    pr = store.get_project(pid)
    ch = project_channel(pr)
    pd = channel_poses(ch)
    poses = presenter.load_poses(pd) if pd else {}
    if not poses:
        poses = {"idle": {}}
    job.update(0.05, "Réalisation du montage (poses, animations)…")
    plan = plan_montage(ch, pr, load_words(pid), poses, log=lambda m: job.update(None, m))
    words = load_words(pid)

    cards = bool((pr.get("montage") or {}).get("chapter_cards"))

    def save(x):
        for s in x.get("scenes") or []:
            e = plan.get(s["i"])
            card = chapter_card(s) if cards else None
            if not e and not card:
                continue
            if e:
                s["pose"], s["sign"] = e["pose"], e["sign"]
                s["fx"] = fx_timing(s, e.get("fx"), words)
            if card:  # la carte de partie passe avant l'animation du réalisateur
                s["fx"] = fx_timing(s, card, words)
            if s["fx"] and s["fx"]["type"] in _full_panel():
                s["status"] = "done"  # la fiche remplace l'image : rien à générer
        sc = x.get("scenes") or []
        for k, f in check_receipts(sc, allowed_numbers(x)).items():
            sc[k]["fx"] = f
        keep = thin_notes(sc)
        for k, s in enumerate(sc):
            if s.get("fx") and k not in keep:
                s["fx"] = None
        x["montage_plan"] = {"at": store.now(), "n_fx": sum(1 for s in sc if s.get("fx"))}
    store.update_project(pid, save)
    n = sum(1 for s in store.get_project(pid).get("scenes") or [] if s.get("fx"))
    job.update(1.0, f"Montage réalisé : {n} animations, {len(plan)} poses.")


def _acting(pr, ch, layout, workdir, w, h, lead=0.0, scenes=None, extra=None):
    """Prof « acteur » : une pose par scène (plan de montage), avec rebond ; None si pas de poses.
    lead = durée de l'intro (le prof salue pendant l'intro, les scènes sont décalées d'autant)."""
    pd = channel_poses(ch)
    scenes = (pr.get("scenes") or []) if scenes is None else scenes
    if not pd or not layout or not (any(s.get("pose") for s in scenes) or extra):
        return None
    bd = board_config(ch)
    g = board.geometry(bd, w, h)
    keys, texts = [], set()
    for s in scenes:
        pose = s.get("pose") or "explain"
        key = f"{pose}|{s['sign']}" if s.get("sign") and pose.startswith("hold_") else pose
        if s.get("sign") and pose.startswith("hold_"):
            texts.add((pose, s["sign"]))
        keys.append((float(s["start"]) + lead, key))
    if lead > 0:
        keys.insert(0, (0.0, "wave"))
    keys += list(extra or [])
    frames, left, H = presenter.acting_frames(pd, g["presenter_h"], workdir, texts)
    if not frames:
        return None
    keys = [(t, k if k in frames else (k.split("|")[0] if k.split("|")[0] in frames else "idle")) for t, k in keys]
    timeline = [keys[0]] + [keys[j] for j in range(1, len(keys)) if keys[j][1] != keys[j - 1][1]]
    idle = frames.get("idle") or frames.get(keys[0][1])
    layout = dict(layout, presenter=idle, rig=frames, rig_mode="acting", acting=timeline,
                  pres_x=max(0, g["presenter_x"] - left), pres_y=g["presenter_bottom"] - H, bob=False)
    sounds = [(t + 0.02, "pop", 0.22) for t, _ in timeline[1:]]
    return layout, sounds


INTRO_SECONDS = 5.5
OUTRO_SECONDS = 7.0


def outro_spec(pr, ch):
    bd = board_config(ch)
    t = title_spec(pr, ch)
    return {"type": "outro", "kicker": t["kicker"], "line1": "Thanks for watching", "line2": "See you on the next bill",
            "bg": {"rgb": _hex_rgb(bd.get("bg_color"), [30, 37, 48]), "dot": _hex_rgb(bd.get("line_color"), [44, 53, 66])}}


def _hex_rgb(h, default):
    h = (h or "").lstrip("#")
    try:
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)] if len(h) == 6 else default
    except ValueError:
        return default


_TOTAL_ITEM = re.compile(r"(?i)^\s*(running |sub|grand |new |final )?total\b")


def _signed_amount(a):
    from services import motion
    v = motion._amount(a)
    return -v if v is not None and re.match(r"^\s*[^\d]*[-\u2212\u2013]", str(a or "")) else v


def allowed_numbers(pr):
    """Chiffres dits dans la vidéo (narration des scènes + script) : seuls ceux-là peuvent s'afficher."""
    return _nums(" ".join(x.get("text") or "" for x in pr.get("scenes") or [])) | \
        _nums(S.narration(pr.get("script") or "")) | {"0"}


def check_receipts(scenes, allowed=None):
    """Garde le ticket de caisse juste, dans l'ordre des scènes : une ligne « Running total » n'est pas une
    ligne de la facture, un total qui ne colle pas aux lignes est recalculé (s'il est dit dans la vidéo),
    sinon le ticket saute (comparaison à part, ex. le même trajet au tarif Medicare).
    → {indice dans scenes: fx corrigé, ou None = à retirer}, seulement pour les tickets qui changent."""
    from services import motion
    out, rows, total = {}, [], None
    for k, sc in enumerate(scenes):
        fx = sc.get("fx") or {}
        if fx.get("type") != "receipt":
            continue
        items = [x for x in fx.get("items") or [] if isinstance(x, dict) and x.get("item")
                 and not _TOTAL_ITEM.match(str(x.get("item")))]
        asked = [(str(x.get("item")), str(x.get("amount") or "")) for x in items]
        new = motion.recap_filter(rows, asked, total, str(fx.get("total") or ""))
        tv, pv = motion._amount(fx.get("total")), motion._amount(total)
        fixed = dict(fx, items=items)
        if new and pv is not None and tv is not None:
            exp = pv + sum(_signed_amount(a) or 0 for _, a in new)
            if abs(exp - tv) >= 0.5:
                if allowed is not None and str(int(round(exp))) not in allowed:
                    out[k] = None
                    continue
                pre = (motion.parse_number(str(fx.get("total"))) or ("$",))[0]
                fixed["total"] = motion.fmt_number(pre, exp, "", 0, True)
        elif not new and pv is not None and tv is not None and abs(pv - tv) >= 0.5:
            fixed["total"] = total  # un récapitulatif relit le ticket tel qu'il est
        if fixed != fx:
            out[k] = fixed
        rows += new
        total = fixed.get("total") or total
    return out


def intro_items(pr, limit=4):
    """Lignes de la facture annoncées dans l'intro (montants cachés) : les « Add X, $Y » du script,
    sinon les lignes des tickets du montage."""
    names = []
    for raw in re.findall(r"\b[Aa]dd (?:the |an? )?([A-Za-z][^,.$:]{2,48}?),?\s*\$[\d,]+", pr.get("script") or ""):
        n = re.split(r"\s+(?:for|of|on|at|to|in)\s+", raw.strip())[0]
        if len(n) > 20:
            n = " ".join(n.split()[-2:])
        names.append(n.upper())
    if not names:  # lignes des tickets, sans les récapitulatifs (même règle que le ticket à l'écran)
        from services import motion
        rows, total = [], None
        sc = pr.get("scenes") or []
        fixes = check_receipts(sc, allowed_numbers(pr))
        for k, s in enumerate(sc):
            fx = fixes.get(k, s.get("fx")) if k in fixes else (s.get("fx") or {})
            fx = fx or {}
            if fx.get("type") != "receipt":
                continue
            asked = [(str(it.get("item") or ""), str(it.get("amount") or "")) for it in fx.get("items") or []
                     if isinstance(it, dict) and it.get("item")]
            new = motion.recap_filter(rows, asked, total, str(fx.get("total") or ""))
            rows += new
            if new or not asked:  # un simple récapitulatif garde le total du ticket
                total = str(fx.get("total") or "") or total
        names = [n.upper()[:20] for n, _ in rows]
    return list(dict.fromkeys(names))[:limit] or ["THE BILL"]


def intro_spec(pr, ch):
    bd = board_config(ch)
    return dict(title_spec(pr, ch), type="intro", items=intro_items(pr),
                bg={"rgb": _hex_rgb(bd.get("bg_color"), [30, 37, 48]), "dot": _hex_rgb(bd.get("line_color"), [44, 53, 66])})


def _intro_bg(ch, workdir, w, h):
    """Image unie (couleur du fond) sous l'intro : aucune image de la vidéo n'y apparaît."""
    from PIL import Image
    path = os.path.join(workdir, "intro_bg.png")
    rgb = tuple(_hex_rgb(board_config(ch).get("bg_color"), [30, 37, 48]))
    if not os.path.isfile(path):
        os.makedirs(workdir, exist_ok=True)
        Image.new("RGB", (w, h), rgb).save(path)
    return path


def title_spec(pr, ch):
    """Écran titre de l'intro : « THE ECONOMICS OF » en petit, la suite en énorme."""
    title = (pr.get("title") or "").strip()
    m = re.match(r"(?i)^(the economics of|how|why|inside the life of|the real cost of)\s+(.+)$", title)
    pre, main = (m.group(1), m.group(2)) if m else ("", title)
    brand = ((TEMPLATES.get(ch.get("template") or "", {}).get("studio") or {}).get("brand")
             or (ch.get("name") or "").split(" — ")[0])
    return {"type": "title", "kicker": brand, "pre": pre, "main": main}


def ensure_intro_image(pid, ch, w, h):
    """Image d'ouverture de l'intro (une image IA qui résume le sujet, sans texte), créée une fois."""
    pr = store.get_project(pid)
    d = store.project_dir(pid)
    rel = (pr.get("intro") or {}).get("image")
    if rel and os.path.isfile(os.path.join(d, rel)):
        return os.path.join(d, rel)
    prompt = (f"Wide, inviting establishing shot that sums up the topic \"{pr.get('title', '')}\" at a glance: the "
              "typical people of this story and the most iconic objects of the topic together in one clear, "
              "well-lit scene, warm cinematic light, calm open space in the center of the frame.")
    rel = f"images/intro_{int(time.time())}.jpg"
    os.makedirs(os.path.join(d, "images"), exist_ok=True)
    generate_scene_image(ch, prompt, os.path.join(d, rel), width=w, height=h, board_layout=uses_board(pr))

    def save(x):
        x["intro"] = {"image": rel, "prompt": prompt}
    store.update_project(pid, save)
    return os.path.join(d, rel)


def render_inputs(pid, workdir, until=None):
    """Tout ce qu'il faut au montage : scènes (+ intro), voix (décalée par l'intro), mots, animations,
    bruitages, mise en page du prof. until = secondes de narration à garder (extrait de test)."""
    pr = store.get_project(pid)
    d = store.project_dir(pid)
    m = pr.get("montage") or DEFAULT_MONTAGE
    w, h = dims(pr)
    ch = project_channel(pr)
    scenes_src = [s for s in pr["scenes"] if until is None or s["start"] < until]
    t_end = scenes_src[-1]["end"] if until is not None and scenes_src else None
    lead = INTRO_SECONDS if (m.get("intro") and montage_enabled(pr)) else 0.0
    tail = OUTRO_SECONDS if (m.get("outro") and montage_enabled(pr) and t_end is None) else 0.0
    voice = os.path.join(d, pr["voice"]["file"])
    voice_end = lead + (t_end if t_end is not None else media.duration(voice))
    if lead or t_end or tail:
        os.makedirs(workdir, exist_ok=True)
        cut = os.path.join(workdir, f"voice_{int(lead * 1000)}_{int((t_end or 0) * 1000)}_{int(tail * 1000)}.mp3")
        if not os.path.isfile(cut) or os.path.getmtime(cut) < os.path.getmtime(voice):
            af = ([f"adelay={int(lead * 1000)}:all=1"] if lead else []) + ([f"apad=pad_dur={tail:.3f}"] if tail else [])
            media.run(["-y", "-i", voice] + (["-t", f"{t_end:.3f}"] if t_end else []) +
                      (["-af", ",".join(af)] if af else []) + ["-c:a", "libmp3lame", "-q:a", "2", cut])
        voice = cut
    scenes, prev_img = [], None
    for s in scenes_src:  # une fiche plein panneau cache l'image : on garde celle de la scène d'avant
        img = os.path.join(d, s["image"]) if s.get("image") else None
        if (s.get("fx") or {}).get("type") in _full_panel() or not img:
            img = prev_img or img or _intro_bg(ch, workdir, w, h)
        scenes.append({"image": img, "start": s["start"] + lead, "motion": "none"
                       if (s.get("fx") or {}).get("type") in _full_panel() else s.get("motion"), "index": s["i"]})
        prev_img = img
    words = [dict(x, s=x["s"] + lead, e=x["e"] + lead) for x in load_words(pid) if t_end is None or x["s"] < t_end]
    overlays = []
    if m.get("section_titles", True):
        for s in scenes_src:
            if s.get("first") and s.get("heading"):
                a = s["start"] + lead
                overlays.append({"start": a + 0.15, "end": min(s["end"] + lead, a + 2.6) if
                                 s["end"] - s["start"] > 1.2 else a + 2.2, "text": s["heading"]})
    layout = _layout_for(pr, workdir, w, h)
    fx, sounds = None, []
    if montage_enabled(pr):
        off = 1 if lead else 0
        keep = thin_notes(scenes_src)  # aussi pour les plans faits avant cette règle
        fixes = check_receipts(pr["scenes"], allowed_numbers(pr))  # idem : tickets justes
        plan = [fixes[k] if k in fixes else s.get("fx") for k, s in enumerate(scenes_src)]
        fx = [{"scene": k + off, "t": f.get("t", s["start"]) + lead,
               "items_t": [t + lead for t in f.get("item_t") or []],
               "spec": {a: b for a, b in f.items() if a not in ("t", "item_t")}}
              for k, (s, f) in enumerate(zip(scenes_src, plan)) if f and k in keep]
        if lead:  # intro plein écran dessinée par le code (aucune image de la vidéo derrière)
            scenes.insert(0, {"image": _intro_bg(ch, workdir, w, h), "start": 0.0, "motion": "none", "index": -1})
            fx.insert(0, {"scene": 0, "t": 0.0, "spec": intro_spec(pr, ch)})
        if tail:  # outro simple après la dernière phrase
            scenes.append({"image": _intro_bg(ch, workdir, w, h), "start": voice_end, "motion": "none", "index": -2})
            fx.append({"scene": len(scenes) - 1, "t": voice_end, "spec": outro_spec(pr, ch)})
        acted = _acting(pr, ch, layout, workdir, w, h, lead=lead, scenes=scenes_src,
                        extra=[(voice_end, "wave")] if tail else None)
        if acted:
            layout, sounds = acted
        sounds += [(float(s["start"]) + lead + 0.05, "whoosh", 0.3) for s in scenes_src[1:]
                   if s.get("first") and s.get("heading")]
    return {"scenes": scenes, "voice": voice, "words": words, "overlays": overlays, "layout": layout, "fx": fx,
            "sounds": sounds, "w": w, "h": h, "m": m, "music": pick_music(pr, m.get("music"))}


def outro_preview(pid, workdir, out):
    """Aperçu de l'outro seule (image du prof, musique, bruitages)."""
    pr = store.get_project(pid)
    ch = project_channel(pr)
    m = pr.get("montage") or DEFAULT_MONTAGE
    w, h = dims(pr)
    os.makedirs(workdir, exist_ok=True)
    silent = os.path.join(workdir, "silence.mp3")
    media.run(["-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{OUTRO_SECONDS:.2f}", "-c:a",
               "libmp3lame", "-q:a", "4", silent])
    layout = _layout_for(pr, workdir, w, h)
    acted = _acting(pr, ch, layout, workdir, w, h, scenes=[], extra=[(0.0, "wave")])
    if acted:
        layout = acted[0]
    render.render_video(workdir, [{"image": _intro_bg(ch, workdir, w, h), "start": 0.0, "motion": "none"}], silent,
                        out, width=w, height=h, fps=30, motion="none", transition="cut", words=[],
                        captions={"mode": "none"}, music_path=pick_music(pr, m.get("music")),
                        music_volume=float(m.get("music_volume") or 0.12), layout=layout,
                        fx=[{"scene": 0, "t": 0.0, "spec": outro_spec(pr, ch)}], tail=0.0)
    return out


def job_render(job, pid):
    pr = store.get_project(pid)
    if not pr.get("voice"):
        raise RuntimeError("Pas de voix off.")
    missing = [s["i"] for s in pr["scenes"] if not s.get("image")
               and (s.get("fx") or {}).get("type") not in _full_panel()]
    if missing:
        raise RuntimeError(f"{len(missing)} scène(s) sans image.")
    d = store.project_dir(pid)
    x = render_inputs(pid, os.path.join(d, "render"))
    m = x["m"]
    out_name = f"{render.safe_name(pr.get('title'))}_{int(time.time()) % 1000000}.mp4"
    try:
        res = render.render_video(
            os.path.join(d, "render"), x["scenes"], x["voice"], os.path.join(d, out_name),
            width=x["w"], height=x["h"], fps=int(m.get("fps") or 30), motion=m.get("motion", "auto"),
            motion_strength=float(m.get("motion_strength") or 0.12), transition=m.get("transition", "fade"),
            transition_dur=float(m.get("transition_dur") or 0.3), words=x["words"],
            captions=m.get("captions") or {"mode": "none"}, overlays=x["overlays"], music_path=x["music"],
            music_volume=float(m.get("music_volume") or 0.12), quality=m.get("quality", "fast"),
            layout=x["layout"], progress=lambda p, msg: job.update(p * 0.98, msg), cancelled=job.cancelled,
            fx=x["fx"], sfx_events=x["sounds"] or None)
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
    ch = project_channel(pr) or {}
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
    ch = project_channel(pr)
    count = max(1, min(4, int(count or 2)))
    job.update(0.05, "Concepts de miniatures…")
    chars = [c["name"] for c in (ch.get("style") or {}).get("characters") or []]
    mascot = _channel_mascot(ch)
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
            look = TEMPLATES.get(ch.get("template") or "", {}).get("thumb_text_style") or (
                "Huge bold clean sans-serif text with a thick dark outline, perfectly legible, spelled correctly.")
            prompt += f" Text reading exactly \"{it.get('text', '')}\". {look}"
        prompt += " Bright, saturated, high contrast, readable at small size."
        if thumb_style:
            prompt += " THUMBNAIL STYLE: " + thumb_style
        if thumb_style or thumb_ref:
            # style de miniature propre à la chaîne (différent du style des images de la vidéo)
            refs = [thumb_ref] if thumb_ref else []
            full = (("Reference image 1 = THUMBNAIL STYLE reference: copy its art style, rendering, outlines, "
                     "composition and color treatment exactly; the subject and setting are new, as described.\n")
                    if thumb_ref else "") + prompt
            art = channel_ref_path(ch, (ch.get("style") or {}).get("ref"))
            if not thumb_ref and art and os.path.isfile(art):  # pas encore de miniature modèle : le style des images
                refs = [art]
                full = ("Reference image 1 = ART STYLE reference: copy its rendering, line work and character "
                        "design exactly; ignore its content.\n") + prompt
            if not with_text:
                full += " No text, no letters, no words (a flag is fine)."
        else:
            full, refs = build_image_prompt(ch, prompt, scene_chars=it.get("chars") or [], allow_text=with_text)
        if mascot and ("Mascot" in (it.get("chars") or []) or _thumb_has_teacher(thumb_style)):
            refs = refs + [mascot]
            full = (f"Reference image {len(refs)} = the channel MASCOT: same head, face, colors and outfit "
                    "(expression and pose change as described).\n" + full)
        blob = ai.generate_image(full, width=1920, height=1080, refs=refs, quality="high")
        rel = f"thumbs/thumb_{int(time.time() * 1000) % 10**9}.jpg"
        ai.fit_cover(blob, 1280, 720, os.path.join(d, rel), quality=90)
        return {"file": rel, "text": it.get("text", "") if with_text else "", "prompt": it.get("prompt", ""),
                "at": store.now(), "gen": {"prompt": full, "refs": list(refs)}}

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


def _thumb_has_teacher(thumb_style):
    """Le style de miniature de la chaîne met son prof / sa mascotte à l'image (ex. Oddly Expensive Lives)."""
    return bool(re.search(r"(?i)\b(teacher|presenter|mascot)\b", thumb_style or ""))


def _channel_mascot(ch):
    path = channel_ref_path(ch, board_config(ch).get("presenter"))
    return path if path and os.path.isfile(path) else None


def save_png(blob, path, side=1536):
    """Image importée → PNG borné (refuse tout ce que Pillow ne sait pas lire)."""
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((side, side))
    im.save(path, "PNG")
    return path


def youtube_thumbnail(url_or_id):
    """Miniature d'une vidéo YouTube (maxres, sinon hq) → bytes, None si introuvable."""
    ids = _video_ids(url_or_id)
    if not ids:
        return None
    import urllib.request
    for q in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            req = urllib.request.Request(f"https://img.youtube.com/vi/{ids[0]}/{q}.jpg",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                blob = r.read()
            if len(blob) > 3000:  # YouTube renvoie une vignette grise de ~1 Ko quand la taille n'existe pas
                return blob
        except Exception:  # noqa: BLE001
            continue
    return None


def job_thumbs_custom(job, pid, prompt, count=2, ref_files=None, channel_style=True):
    """Miniatures « à la manière de » : 1re référence = la miniature à imiter (lien YouTube ou image),
    les suivantes = images d'appoint (perso, objet, style) ; 1 à 4 variantes en parallèle."""
    pr = store.get_project(pid)
    ch = project_channel(pr)
    count = max(1, min(4, int(count or 1)))
    refs = [p for p in (ref_files or []) if p and os.path.isfile(p)][:4]
    thumb_style = (ch.get("thumb_style") or "").strip()
    if channel_style and not refs:
        tr = channel_ref_path(ch, ch.get("thumb_ref"))
        if tr and os.path.isfile(tr):
            refs = [tr]
    with_text = ch.get("thumb_text", True) is not False
    head = []
    if refs:
        head.append("Reference image 1 = THE THUMBNAIL TO MODEL: reproduce its composition, framing, art style, "
                    "rendering, outlines, colors and overall look as closely as possible, with the new content "
                    "described below.")
        for i in range(2, len(refs) + 1):
            head.append(f"Reference image {i} = an extra reference from the creator (a character, object, place "
                        "or style detail): use it as the prompt describes.")
    full = "\n".join(head) + ("\n" if head else "") + (
        f"YouTube thumbnail, 16:9, for the video \"{pr.get('title', '')}\". {prompt.strip()} "
        "Bright, saturated, high contrast, readable at small size.")
    if channel_style and thumb_style:
        full += " CHANNEL THUMBNAIL STYLE: " + thumb_style
    mascot = _channel_mascot(ch) if channel_style and _thumb_has_teacher(thumb_style) else None
    if mascot and len(refs) < 4:
        refs = refs + [mascot]
        full = (f"Reference image {len(refs)} = the channel's TEACHER: same head, face, colors and outfit "
                "(expression and pose change as described).\n" + full)
    if not with_text and "text" not in prompt.lower():
        full += " No text, no letters, no words (a flag is fine)."
    d = store.project_dir(pid)
    os.makedirs(os.path.join(d, "thumbs"), exist_ok=True)
    job.update(0.05, f"Génération de {count} miniature(s)…")
    results, done = [], 0

    def one(k):
        blob = ai.generate_image(full, width=1920, height=1080, refs=refs, quality="high")
        rel = f"thumbs/thumb_{int(time.time() * 1000) % 10**9}_{k}.jpg"
        ai.fit_cover(blob, 1280, 720, os.path.join(d, rel), quality=92)
        return {"file": rel, "text": "", "prompt": prompt.strip(), "at": store.now(), "custom": True,
                "gen": {"prompt": full, "refs": [os.path.relpath(r, d) if r.startswith(d) else r for r in refs]}}

    errors = []
    with ThreadPoolExecutor(max_workers=count) as ex:
        for fut in as_completed([ex.submit(one, k) for k in range(count)]):
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:160])
            done += 1
            job.update(0.05 + 0.95 * done / count, f"Miniatures {done}/{count}")
    if not results:
        raise RuntimeError("Aucune miniature générée : " + (errors[0] if errors else "erreur inconnue"))

    def save(x):
        x["thumbnails"] = (results + (x.get("thumbnails") or []))[:12]
    store.update_project(pid, save)
    job.update(1.0, f"{len(results)} miniature(s) prête(s).")


def job_thumb_regen(job, pid, file):
    """Regénère UNE miniature avec le même prompt et les mêmes références ; elle garde sa place."""
    pr = store.get_project(pid)
    ch = project_channel(pr)
    thumbs = pr.get("thumbnails") or []
    old = next((t for t in thumbs if t.get("file") == file), None)
    if not old:
        raise RuntimeError("Miniature introuvable.")
    d = store.project_dir(pid)
    gen = old.get("gen") or {}
    full = gen.get("prompt")
    refs = [r if os.path.isabs(r) else os.path.join(d, r) for r in gen.get("refs") or []]
    refs = [r for r in refs if os.path.isfile(r)]
    if not full:  # miniature d'avant la mémorisation : on repart de son prompt + style de la chaîne
        tr = channel_ref_path(ch, ch.get("thumb_ref"))
        refs = [tr] if tr and os.path.isfile(tr) else []
        full = ((("Reference image 1 = THE THUMBNAIL TO MODEL: copy its art style, rendering, outlines, composition "
                  "and colors; new content as described.\n") if refs else "")
                + f"YouTube thumbnail, 16:9. {old.get('prompt', '')} " + (ch.get("thumb_style") or ""))
    job.update(0.1, "Nouvelle version de la miniature…")
    blob = ai.generate_image(full, width=1920, height=1080, refs=refs, quality="high")
    rel = f"thumbs/thumb_{int(time.time() * 1000) % 10**9}_r.jpg"
    ai.fit_cover(blob, 1280, 720, os.path.join(d, rel), quality=92)

    def save(x):
        for t in x.get("thumbnails") or []:
            if t.get("file") == file:
                t["file"], t["at"] = rel, store.now()
                t["gen"] = {"prompt": full, "refs": [os.path.relpath(r, d) if r.startswith(d) else r for r in refs]}
    store.update_project(pid, save)
    try:
        os.remove(os.path.join(d, file))
    except OSError:
        pass
    job.update(1.0, "Miniature regénérée.")


def delete_thumb(pid, file):
    d = store.project_dir(pid)

    def save(x):
        x["thumbnails"] = [t for t in x.get("thumbnails") or [] if t.get("file") != file]
    store.update_project(pid, save)
    path = os.path.normpath(os.path.join(d, file))
    if path.startswith(os.path.join(d, "thumbs")) and os.path.isfile(path):
        os.remove(path)


def studio_summary(pr):
    """Résumé d'un projet pour le studio simplifié : état, progression, vidéo, miniatures."""
    out = project_summary(pr)
    job = store.running_job(pr["id"]) or store.last_job(pr["id"])
    out["job"] = job.as_dict() if job else None
    rd = pr.get("render") or {}
    out["render"] = {"file": rd.get("file"), "duration": rd.get("duration"), "v": rd.get("v")} if rd.get("file") else None
    out["thumbnails"] = [{"file": t.get("file"), "at": t.get("at")} for t in pr.get("thumbnails") or [] if t.get("file")]
    rv = pr.get("review") or {}
    out["verdict"] = rv.get("verdict") if rv.get("engine") == "facelessos" else None
    out["format"] = pr.get("format")
    md = pr.get("metadata") or {}
    out["metadata"] = {k: md.get(k) for k in ("titles", "description", "tags", "pinned_comment", "at")} if md else None
    return out


def chapters(pr):
    m = pr.get("montage") or DEFAULT_MONTAGE
    lead = INTRO_SECONDS if (m.get("intro") and montage_enabled(pr)) else 0.0  # la voix démarre après l'intro
    out = []
    for s in pr.get("scenes") or []:
        if s.get("first"):
            t = int(s["start"] + (lead if out else 0))
            out.append(f"{t // 60:02d}:{t % 60:02d} {s.get('heading') or ('Intro' if not out else '')}".strip())
    if out and not out[0].startswith("00:00"):
        out.insert(0, "00:00 Intro")
    return out


def job_metadata(job, pid):
    pr = store.get_project(pid)
    ch = project_channel(pr)
    job.update(0.2, "Titre, description, tags et commentaire épinglé…")
    if FOS.available():
        meta = S.package(ch, pr)
        meta["at"] = store.now()
    else:
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
    need_voice, need_cast = voice_outdated(pr), pr.get("cast") is None
    if need_voice and need_cast:
        # voix et casting en même temps : indépendants (la voix fait les scènes, le casting les persos)
        with ThreadPoolExecutor(max_workers=2) as ex:
            fv = ex.submit(job_voice, _Sub(job, 0.25, 0.35, "2/4 Voix"), pid)
            fc = ex.submit(job_cast, _Sub(job, 0.25, 0.35, "2/4 Personnages"), pid)
            fv.result()
            fc.result()
    elif need_voice:
        job_voice(_Sub(job, 0.25, 0.35, "2/4 Voix"), pid)
    pr = store.get_project(pid)
    if montage_enabled(pr) and not pr.get("montage_plan"):
        try:  # poses du prof + animations, AVANT les images (une fiche remplace l'image de sa scène)
            job_montage(_Sub(job, 0.35, 0.4, "3/4 Réalisation"), pid)
        except Exception as e:  # noqa: BLE001
            job.update(None, f"Réalisation du montage impossible ({str(e)[:80]}) : montage simple.")
    job_images(_Sub(job, 0.4, 0.85, "3/4 Images"), pid)
    if render_video:
        job_render(_Sub(job, 0.85, 0.98, "4/4 Montage"), pid)
        try:  # titre + description prêts à copier ; jamais bloquant pour la vidéo
            job_metadata(_Sub(job, 0.98, 1.0, "4/4 Publication"), pid)
        except Exception as e:  # noqa: BLE001
            job.update(None, f"Vidéo prête (titre/description à regénérer : {str(e)[:80]})")
    job.update(1.0, "Vidéo terminée ✔")
