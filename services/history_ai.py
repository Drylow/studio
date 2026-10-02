"""Format Histoire : écriture du script et plan visuel (IA texte via services.ai).

1. write_script  : narration documentaire façon « Dose of History » (immersion à la 2e personne,
   date + lieu en ouverture, promesse « rien à voir avec les films », phrases courtes et concrètes).
2. plan_visuals  : à partir des phrases horodatées de la voix off, choisit pour chaque passage
   une image IA (Ken Burns) ou un template animé (carte, bataille, fiche, stats, citation…).
"""
import json
import os
import re

from services import ai

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WPM = 153  # débit mesuré sur la vidéo de référence (5 749 mots / 37 min 41)

TEMPLATES = ("statement", "number", "map", "battle", "character", "compare", "chart", "archive", "route", "quote")


def _reference():
    p = os.path.join(APP_DIR, "presets", "history_doc", "reference_excerpt.txt")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def write_script(title, minutes, notes="", language="en"):
    words = int(round(minutes * WPM))
    hook_words = min(75, max(45, words // 6))
    lang = "English" if language == "en" else "French"
    prompt = f"""You write narration for a faceless YouTube history documentary channel.
Video title: "{title}"
Target length: {words} words (±8%), which is {minutes:g} minutes of voice-over at {WPM} wpm. Language: {lang}.
{('Extra notes from the producer: ' + notes) if notes else ''}

STYLE ANCHOR (copy the voice, rhythm and structure; never the content):
<<<
{_reference()}
>>>

Rules:
- Open with the exact moment: time of day, date, place. Put the viewer inside the scene in second person
  ("you are standing in…"), then state the promise of the title and that the popular version is wrong.
- The hook is the first ~{hook_words} words. It must end on a line that makes stopping impossible.
- Short declarative sentences (average 13 words), concrete numbers, sensory details, real names.
- Everything must be historically accurate and verifiable. When sources disagree, say so ("Polybius says…").
- Open loops early and close them later. No filler, no "in this video", no "delve", no rhetorical question chains.
- 3 to 5 sections after the hook. Each section has a short heading (not read aloud).
- Mention at least: one key person introduced by name and role, the size of the forces with numbers,
  one physical artifact or ancient source, one journey or campaign route, one famous attributed quote,
  one tactical manoeuvre that can be drawn on a map.

Return JSON only:
{{"title": "...", "hook": "hook narration", "sections": [{{"heading": "...", "text": "narration"}}]}}"""
    data = ai.chat_json(prompt, model=ai.text_model(), reasoning="medium", timeout=300)
    hook = (data.get("hook") or "").strip()
    sections = [{"heading": (s.get("heading") or "").strip(), "text": (s.get("text") or "").strip()}
                for s in data.get("sections") or [] if (s.get("text") or "").strip()]
    if not hook or not sections:
        raise ai.AIError("Script incomplet renvoyé par l'IA.")
    return {"title": (data.get("title") or title).strip(), "hook": hook, "sections": sections}


def narration(script):
    return " ".join([script["hook"]] + [s["text"] for s in script["sections"]])


# ── Plan visuel ─────────────────────────────────────────────────────────────

_TPL_DOCS = {
    "statement": ('- statement: {"at","type":"statement","text":"2-5 WORD PUNCHLINE IN CAPS with 1-2 *accent* words",'
                  '"kicker":"optional tiny context line (date, place)","say":"exact words from the sentence that trigger it"}'),
    "number": ('- number: {"at","type":"number","value":47000,"prefix":"","suffix":"","label":"WHAT IT COUNTS (≤5 words)",'
               '"sub":"optional short context","say":"exact words where the number is spoken"} (one striking figure)'),
    "battle": ('- battle: {"at","type":"battle","title":"Manoeuvre name","subtitle":"Place, date","terrain_prompt":"top-down satellite view of …",\n'
               '  "line":{"y":58,"x1":20,"x2":80} (optional front line),\n'
               '  "units":[{"label","side":"a|b","kind":"infantry|cavalry|archers|chariots|elephants|command","x","y","to":[x,y],"move":[f0,f1],"w","h","trail":true}],\n'
               '  "labels":[{"text","x","y","side":"a|b"}]}\n'
               '  x,y are 0-100 screen percentages (keep 8-92, leave the bottom-left 35% x 25% free for the title). side a = protagonist (blue),\n'
               '  side b = enemy (red). 4-9 units. move = [start,end] fractions of the beat. w,h in px (default 54x30, big formations up to 170x60).'),
    "character": '- character: {"at","type":"character","name","role","facts":["≤6 words", "≤6 words", "≤6 words"],"portrait":"cast name"}',
    "compare": ('- compare (duo — portrait left, portrait right): {"at","type":"compare",'
                '"left":{"title":"name or side","subtitle":"role","stats":["≤5 words" x2-3],"portrait":"cast name"},\n'
                '  "right":{"title","subtitle","stats":[...],"portrait":"cast name"}} — two rivals, two leaders, two armies.'),
    "chart": '- chart: {"at","type":"chart","title","subtitle","bars":[{"label","value":number,"side":"a|b|neutral","display":"optional text"}]}',
    "archive": ('- archive: {"at","type":"archive","title":"OBJECT, PLACE, DATE","search":"2-4 word museum search, e.g. Norman helmet / Bayeux Tapestry",'
                '"prompt":"museum photograph of the real artifact (used only if no real image is found)","note":"short caption"}'),
    "map": ('- map (movement map on real geography): {"at","type":"map","title":"short title","subtitle":"dates",'
            '"places":[{"name","lat","lon"}] (real coordinates, 3-6 places, never two towns closer than ~40 km),'
            '"moves":[{"from":"place name","to":"place name","via":["place name"],"side":"a|b","label":"army or leader, max 18 chars"}] '
            '(1-3 moves, in story order; one move per army: put stopovers in "via" instead of chaining moves of the same side),'
            '"battle":"place where they fight, named as the battle is known (e.g. Hastings, not the hamlet next to it) (optional)"}'
            ' — use it whenever armies, fleets or people travel from A to B.'),
    "route": '- route: {"at","type":"route","title":"A to B","subtitle":"campaign name","stops":[{"name","lat","lon"}]} (real coordinates, 3-7 stops)',
    "quote": ('- quote: {"at","type":"quote","text":"the quote exactly as the narrator reads it","author","source":"short attribution, e.g. Livy, Book XXII / attributed","portrait":"cast name or null"}\n'
              '  Start the quote beat on the sentence where the narrator reads the quote.'),
}

_SHOT_GUIDE = """IMAGE PROMPTS — write them like a cinematographer's shot list (this decides the whole look of the video):
- One sentence per shot: SHOT TYPE + LENS, SUBJECT and what they are doing / feeling, KEY PROPS & COSTUME details,
  SETTING with a foreground / background, TIME OF DAY and LIGHT DIRECTION.
  e.g. "Close-up, 85mm: a young Saxon housecarl, mud on his cheek, breath visible in the cold, peering over the rim of his
  round shield at the slope below; spears and banners soft in the background; low dawn sun behind him."
- Vary the coverage like a film: extreme close-up of eyes, close-up, low-angle hero shot, wide establishing landscape,
  aerial view, crowd seen from afar, insert detail (hands, sword hilt, seal, coins, a letter), animals, ships, buildings,
  camp life, weather, aftermath. Never two similar shots in a row; avoid the cliché of two warriors side by side.
- At least HALF of the shots have no named character at all (places, objects, crowds, armies from afar, details).
- At most ONE named cast member per shot; keep the head fully in frame (never crop at the forehead).
- Era-accurate everything (armour, weapons, hairstyles, architecture). No text, no modern objects."""


def _plan_rules(allowed, max_cards):
    docs = "\n".join(_TPL_DOCS[t] for t in TEMPLATES if t in allowed)
    return f"""You are the editor of a history documentary in the visual style of "Dose of History": ultra-realistic
cinematic stills with a slow Ken Burns zoom, cut hard every 12-20 seconds, plus a FEW elegant motion-graphics cards.
You receive the voice-over split into numbered sentences with timestamps. Choose what is on screen for every sentence
by returning ordered BEATS.

A beat starts at sentence index "at" and lasts until the next beat. The first beat has at=0.
Beat types and their fields:
- image: {{"at", "type":"image", "prompt", "chars":[cast names visible], "motion":"in|out|left|right",
  "label":{{"name","role"}} (optional, ONLY the first time a main cast member appears as the subject),
  "stamp":"PLACE, REGION · DATE" (optional, on establishing shots when the story moves to a new place/date; max 3)}}
  motion: in/out for shots of people, left/right only for wide landscapes.
{docs}
ONLY these card types exist: {", ".join(t for t in TEMPLATES if t in allowed)}. Never invent other types.

{_SHOT_GUIDE}

Also return "cast": the recurring people, each with a fixed look used for every image
({{"name","look":"age, face, hair, beard, armour, clothing colours — one sentence"}}).

Pacing rules:
- HOOK (sentences 0..HOOK_END): a new image every sentence (~5 s): faces in close-up and wide establishing shots, no cards.
- After the hook: images last 2-3 sentences (12-20 s). Images are the default.
- AT MOST {max_cards} cards in the whole video, of DIFFERENT types (vary them). A card only when the narration is
  literally about it (two rivals or two armies → compare, a person introduced → character, a striking figure → number,
  a quote read aloud → quote, an artifact or source → archive, a twist or verdict → statement). Never two cards in a row.
"""


def plan_visuals(sentences, duration, hook_end_idx, allowed=None, max_cards=6, require_all=False, first=0, cast=None):
    """first = index global de la 1re phrase (vidéo longue planifiée par morceaux) ; cast = casting déjà fixé."""
    allowed = [t for t in (allowed or TEMPLATES) if t in TEMPLATES]
    lines = "\n".join(f"[{first + i}] ({s['start']:.1f}-{s['end']:.1f}s) {s['text']}" for i, s in enumerate(sentences))
    must = ("Use each of these card types exactly once: " + ", ".join(allowed) + ".") if require_all else ""
    known = ""
    if cast:
        known = ("\nThis is one part of a longer video. The cast is already fixed, reuse these exact names and looks "
                 "(add a new person only if they appear for the first time here): "
                 + json.dumps(cast, ensure_ascii=False) + "\n")
    prompt = (_plan_rules(allowed, max_cards).replace("HOOK_END", str(hook_end_idx))
              .replace("The first beat has at=0.", f"The first beat has at={first}.")
              + f"\nTotal duration: {duration:.1f}s. HOOK_END = sentence {hook_end_idx}. {must}{known}\n\nSentences:\n{lines}\n\n"
              'Return JSON only: {"cast":[...], "beats":[...]}')
    data = ai.chat_json(prompt, model=ai.text_model(), reasoning="high", timeout=400)
    beats = [b for b in data.get("beats") or [] if isinstance(b, dict) and b.get("type")]
    if not beats:
        raise ai.AIError("Plan visuel vide.")
    return {"cast": data.get("cast") or [], "beats": beats}


# ── Variété des plans ───────────────────────────────────────────────────────

def diversify_shots(items, cast, style_name):
    """Monteur image : réécrit la liste de plans pour qu'aucun plan ne ressemble au précédent.

    items = [{"i", "text" (narration du plan), "prompt", "chars"}] → même liste, prompts / persos réécrits."""
    if len(items) < 3:
        return items
    lines = "\n".join(f"[{it['i']}] narration: {it['text'][:220]}\n     current shot: {it['prompt'][:260]}"
                       f"  | chars: {', '.join(it.get('chars') or []) or '-'}" for it in items)
    names = ", ".join(c.get("name", "") for c in cast or []) or "none"
    prompt = f"""You are the picture editor of a history documentary (image style: {style_name}).
Here is the shot list, in order. Rewrite it so the video NEVER feels repetitive, while each shot still illustrates
its narration. Rules:
- Consecutive shots must differ in subject, framing, camera angle and composition. No two shots alike in the whole list.
- At least half of the shots have NO named character: landscapes, aerial views, armies or crowds from afar, ships,
  horses, weapons or objects in close-up, letters and seals, buildings, camps, weather, aftermath, daily life details.
- At most ONE named character per shot (cast: {names}). Never "two warriors side by side looking the same way".
- Vary time of day, light and colour mood across the list.
- Each prompt: one sentence, shot type + lens, subject and action, setting with foreground/background, light.
- Keep chars = the named cast member actually visible (0 or 1 name from the cast).

Shots:
{lines}

Return JSON only: {{"shots": [{{"i": n, "prompt": "...", "chars": ["..."]}}]}} with exactly the same "i" values."""
    try:
        data = ai.chat_json(prompt, model=ai.text_model(), reasoning="medium", timeout=300)
    except Exception:  # noqa: BLE001 — pas de réécriture possible : on garde la liste telle quelle
        return items
    by = {int(x.get("i", -1)): x for x in data.get("shots") or [] if isinstance(x, dict)}
    out = []
    for it in items:
        x = by.get(it["i"])
        if x and (x.get("prompt") or "").strip():
            out.append(dict(it, prompt=x["prompt"].strip(), chars=[c for c in (x.get("chars") or [])][:1]))
        else:
            out.append(dict(it, chars=(it.get("chars") or [])[:1]))
    return out


# ── Style d'image ───────────────────────────────────────────────────────────

STYLE = ("Ultra-realistic cinematic film still from a high-budget historical epic, shot on an ARRI Alexa with a 50mm "
         "anamorphic lens. Natural but dramatic light: low golden sun as backlight and rim light, soft fill on the face, "
         "volumetric haze and dust in the air, real atmospheric depth with the background softly out of focus. Rich warm "
         "colour grade with amber highlights and deep brown shadows, natural skin tones, slightly muted greens and blues. "
         "Crisp detail: skin pores, sweat, dirt, weathered leather, dented metal, coarse wool. Strong composition with "
         "foreground, subject and background layers; the subject's whole head in frame with headroom. Photographic, not "
         "painterly, no CGI look. One single photograph: no collage, no split screen, no panels, no borders. "
         "No text, no logos, no watermark.")
PORTRAIT = ("Ultra-realistic cinematic portrait from a high-budget historical epic, chest-up, looking slightly off camera, "
            "85mm lens, soft warm key light from the side with a gentle rim light, dark smoky background, crisp skin "
            "texture, era-accurate costume. Photographic, not painterly. No text.")
# Styles d'image proposés (le thème des cartes suit : « illustrated » = parchemin, « cinematic » = sombre)
IMAGE_STYLES = {
    "ink": {"name": "Illustré — encre & aquarelle", "theme": "illustrated",
            "shot": ("Hand-drawn historical illustration in ink and watercolour: confident black ink linework with fine "
                     "cross-hatching, muted earthy washes (ochre, burnt sienna, slate blue, faded crimson) on warm off-white "
                     "paper with visible grain, like a premium illustrated history book. Expressive faces, era-accurate "
                     "details, clear composition with depth; whole heads in frame. One single image: no collage, no panels, "
                     "no border, no text, no signature."),
            "portrait": ("Hand-drawn ink and watercolour portrait, chest-up, looking slightly off camera, confident ink "
                         "linework and cross-hatching, muted earthy washes, plain warm paper background. No text.")},
    "bd": {"name": "BD — ligne claire", "theme": "illustrated",
           "shot": ("Graphic-novel illustration in the European ligne-claire tradition: bold clean ink outlines, flat "
                    "cel-shaded colours with dramatic cast shadows, palette of deep teal, ochre, sand and blood red, cinematic "
                    "framing, premium bande dessinée quality. Expressive faces, era-accurate details; whole heads in frame. "
                    "One single image: no panels, no speech bubbles, no border, no text."),
           "portrait": ("Ligne-claire graphic-novel portrait, chest-up, bold clean outlines, flat colours, plain warm "
                        "background. No text.")},
    "paint": {"name": "Peinture d'histoire", "theme": "illustrated",
              "shot": ("Digital painting in the style of 19th-century academic history painting: visible confident brush "
                       "strokes, rich chiaroscuro, warm glazes, atmospheric depth, museum-quality composition. Expressive "
                       "faces, era-accurate details; whole heads in frame. One single image: no frame, no text, no signature."),
              "portrait": ("Academic oil-painting portrait, chest-up, rich chiaroscuro, warm glazes, dark plain background. "
                           "No text.")},
    "cinematic": {"name": "Cinéma — photoréaliste", "theme": "cinematic", "shot": STYLE, "portrait": PORTRAIT},
}
DEFAULT_STYLE = "ink"


def image_style(name):
    return IMAGE_STYLES.get(name or "", IMAGE_STYLES[DEFAULT_STYLE])


ARCHIVE = ("Museum catalogue photograph, neutral grey backdrop, soft studio light, sharp focus, realistic patina, "
           "photographed as a real surviving artifact. No text, no labels.")
TERRAIN = ("Top-down satellite photograph of real terrain, desaturated grey-brown, subtle relief, dry riverbeds, "
           "no roads, no buildings, no text, no labels, evenly lit.")


def pick_archive(candidates, beat):
    """Choisit parmi des images de musée réelles celle qui correspond vraiment à l'objet (ou aucune).

    candidates = [{"title","date","culture","source"}]. Renvoie l'index retenu ou -1."""
    if not candidates:
        return -1
    lines = "\n".join(f"[{i}] {c.get('title','')} — {c.get('date','')} — {c.get('culture','')} ({c.get('source','')})"
                       for i, c in enumerate(candidates))
    prompt = (f"A history documentary needs a real museum image for: \"{beat.get('title','')}\" "
              f"(search: {beat.get('search','')}; narration context: {beat.get('note','')}).\n"
              f"Candidates:\n{lines}\n\nPick the candidate that genuinely shows this object or a very close equivalent "
              "from the same culture and period. If none fits, answer -1. Return JSON only: {\"index\": n}")
    try:
        data = ai.chat_json(prompt, model=ai.fast_model(), timeout=120, tries=2)
        i = int(data.get("index", -1))
        return i if 0 <= i < len(candidates) else -1
    except Exception:  # noqa: BLE001 — pas de vérification possible : on préfère l'image IA
        return -1


def period_brief(title, script_text):
    """L'époque exacte de la vidéo pour les images : sans elle, le modèle d'image mélange les guerres (tuniques
    rouges, shakos napoléoniens, légionnaires, casques de 1940 à Gettysburg). → {"period", "avoid"}."""
    prompt = (f"A history documentary titled \"{title}\" will be illustrated shot by shot. From the narration below, "
              "write the visual period anchor that every image prompt will start with.\n"
              "period: ONE sentence, max 70 words: exact years and place, then how people look: the uniforms of each "
              "side (colours, headgear, weapons), civilian clothes, buildings and vehicles of that time and place.\n"
              "avoid: ONE line listing the look-alike eras an image model tends to confuse with this one (for example "
              "British redcoats, Napoleonic shakos, Roman armour, medieval knights, World War helmets), plus symbols that "
              "did not exist yet (for example a red cross emblem before 1864) and modern objects.\n"
              "Return JSON only: {\"period\": \"...\", \"avoid\": \"...\"}\n\nNARRATION (excerpt):\n"
              + (script_text or "")[:6000])
    data = ai.chat_json(prompt, model=ai.fast_model(), timeout=180, tries=3)
    return {"period": str(data.get("period") or "").strip(), "avoid": str(data.get("avoid") or "").strip()}


SHOT_QA = """You check one illustration for a history documentary. Setting: {period}
What the shot should show: {prompt}
Return JSON only: {{"ok": true or false, "problems": ["short description of each problem"]}}.
ok = false ONLY for clear, visible errors:
- people, uniforms, headgear, flags, weapons, armour, clothes, buildings or vehicles from another era or place than the setting (watch for: {avoid});
- a person with three arms or hands, two heads, or a melted, duplicated face;
- readable words, letters or numbers;
- gore in close-up (exposed organs, severed limbs shown in detail).
Small stylistic liberties are fine."""


def check_shot(path, period, prompt=""):
    """Contrôle en vision d'une image de plan → (ok, [problèmes])."""
    import base64
    import io
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((896, 896))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86)
    q = SHOT_QA.format(period=(period or {}).get("period", ""), avoid=(period or {}).get("avoid", ""),
                       prompt=(prompt or "")[:500])
    content = [{"type": "text", "text": q},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}]
    res = ai.chat_json([{"role": "user", "content": content}], model=ai.text_model(), timeout=240)
    return bool(res.get("ok", True)), [str(x) for x in res.get("problems") or []][:4]


def cast_look(cast, names):
    by = {(c.get("name") or "").lower(): c for c in cast or []}
    out = []
    for n in names or []:
        c = by.get((n or "").lower())
        if c and c.get("look"):
            out.append(f"{c['name']}: {c['look']}")
    return " ".join(out)


def slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:n] or "x"


def dumps(o):
    return json.dumps(o, ensure_ascii=False, indent=1)
