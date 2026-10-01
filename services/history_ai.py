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

TEMPLATES = ("statement", "battle", "character", "compare", "chart", "archive", "route", "quote")


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
    "statement": '- statement: {"at","type":"statement","text":"2-5 WORD PUNCHLINE IN CAPS with 1-2 *accent* words","say":"exact words from the sentence that trigger it"}',
    "battle": ('- battle: {"at","type":"battle","title":"Manoeuvre name","subtitle":"Place, date","terrain_prompt":"top-down satellite view of …",\n'
               '  "line":{"y":58,"x1":20,"x2":80} (optional front line),\n'
               '  "units":[{"label","side":"a|b","kind":"infantry|cavalry|archers|chariots|elephants|command","x","y","to":[x,y],"move":[f0,f1],"w","h","trail":true}],\n'
               '  "labels":[{"text","x","y","side":"a|b"}]}\n'
               '  x,y are 0-100 screen percentages (keep 8-92, leave the bottom-left 35% x 25% free for the title). side a = protagonist (blue),\n'
               '  side b = enemy (red). 4-9 units. move = [start,end] fractions of the beat. w,h in px (default 54x30, big formations up to 170x60).'),
    "character": '- character: {"at","type":"character","name","role","facts":["≤6 words", "≤6 words"],"portrait":"cast name"}',
    "compare": ('- compare: {"at","type":"compare","left":{"title","stats":["≤5 words" x3],"portrait":"cast name or null"},\n'
                '  "right":{"title","stats":[...],"portrait":"cast name or null"}}'),
    "chart": '- chart: {"at","type":"chart","title","subtitle","bars":[{"label","value":number,"side":"a|b|neutral","display":"optional text"}]}',
    "archive": '- archive: {"at","type":"archive","title":"OBJECT, PLACE, DATE","prompt":"museum photograph of a real artifact …","note":"short caption"}',
    "route": '- route: {"at","type":"route","title":"A to B","subtitle":"campaign name","stops":[{"name","lat","lon"}]} (real coordinates, 3-7 stops)',
    "quote": ('- quote: {"at","type":"quote","text":"the quote exactly as the narrator reads it","author","source":"short attribution, e.g. Livy, Book XXII / attributed","portrait":"cast name or null"}\n'
              '  Start the quote beat on the sentence where the narrator reads the quote.'),
}


def _plan_rules(allowed, max_cards):
    docs = "\n".join(_TPL_DOCS[t] for t in TEMPLATES if t in allowed)
    return f"""You are the editor of a history documentary in the visual style of "Dose of History": realistic
photographic stills (like production stills from a historical drama) with a slow Ken Burns zoom, cut hard every
12-20 seconds, plus a FEW elegant motion-graphics cards. You receive the voice-over split into numbered sentences
with timestamps. Choose what is on screen for every sentence by returning ordered BEATS.

A beat starts at sentence index "at" and lasts until the next beat. The first beat has at=0.
Beat types and their fields:
- image: {{"at", "type":"image", "prompt", "chars":[cast names visible], "motion":"in|out|left|right|up|down"}}
  prompt = one concrete, believable shot: framing (close-up / medium / wide), subject, action, era-accurate costume,
  setting, time of day, natural light. One clear subject; when a person is the subject their whole face is visible.
  Never text, never modern objects. Avoid words like epic, dramatic, cinematic, glowing.
{docs}
ONLY these card types exist: {", ".join(t for t in TEMPLATES if t in allowed)}. Never invent other types.

Also return "cast": the recurring people, each with a fixed look used for every image
({{"name","look":"age, face, hair, beard, armour, clothing colours — one sentence"}}).

Pacing rules:
- HOOK (sentences 0..HOOK_END): a new image every sentence (~5 s): close-ups of faces and calm wide establishing shots, no cards.
- After the hook: images last 2-3 sentences (12-20 s). Images are the default.
- AT MOST {max_cards} cards in the whole video. A card only when the narration is literally about it
  (a person introduced → character, a journey → route, a quote read aloud → quote, an artifact or source → archive,
  a twist or verdict → statement). Never two cards in a row.
"""


def plan_visuals(sentences, duration, hook_end_idx, allowed=None, max_cards=6, require_all=False):
    allowed = [t for t in (allowed or TEMPLATES) if t in TEMPLATES]
    lines = "\n".join(f"[{i}] ({s['start']:.1f}-{s['end']:.1f}s) {s['text']}" for i, s in enumerate(sentences))
    must = ("Use each of these card types exactly once: " + ", ".join(allowed) + ".") if require_all else ""
    prompt = (_plan_rules(allowed, max_cards).replace("HOOK_END", str(hook_end_idx))
              + f"\nTotal duration: {duration:.1f}s. HOOK_END = sentence {hook_end_idx}. {must}\n\nSentences:\n{lines}\n\n"
              'Return JSON only: {"cast":[...], "beats":[...]}')
    data = ai.chat_json(prompt, model=ai.text_model(), reasoning="high", timeout=400)
    beats = [b for b in data.get("beats") or [] if isinstance(b, dict) and b.get("type")]
    if not beats:
        raise ai.AIError("Plan visuel vide.")
    return {"cast": data.get("cast") or [], "beats": beats}


# ── Style d'image ───────────────────────────────────────────────────────────

STYLE = ("A realistic photograph that looks like a production still from a big-budget historical drama such as HBO's Rome "
         "or Gladiator. Warm, hazy natural daylight with fine dust in the air, restrained earthy colours (sand, ochre, "
         "bronze, faded red), realistic skin texture, authentic weathered costumes and armour, an uncluttered composition "
         "with one clear subject, eye-level camera, 35mm lens, gentle depth of field. When a person is the subject their "
         "whole face is visible. Not a painting, not concept art, not an illustration, not HDR, no orange-teal grade, "
         "no oversaturated colours, no movie-poster look. No text, no captions, no watermark, no modern objects.")
PORTRAIT = ("A realistic photographic portrait from a historical drama production, chest-up, looking slightly off camera, "
            "soft warm window light, plain dark background, natural skin texture, restrained colours. Not a painting. No text.")
ARCHIVE = ("Museum catalogue photograph, neutral grey backdrop, soft studio light, sharp focus, realistic patina, "
           "photographed as a real surviving artifact. No text, no labels.")
TERRAIN = ("Top-down satellite photograph of real terrain, desaturated grey-brown, subtle relief, dry riverbeds, "
           "no roads, no buildings, no text, no labels, evenly lit.")


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
