"""Chaînes du format Histoire (dans la lignée de Dose of History) et leur fiche FacelessOS.

Une chaîne = concept, ton, règles, vidéo de référence (voix), durée, style d'image et idées de vidéos.
fos_channel(key) la présente au moteur FacelessOS de services/pov_script.py (format « history_doc »)."""
import json
import os

from services import pov_script as S
from services.pov_store import APP_DIR

PRESETS = os.path.join(APP_DIR, "presets", "history_channels")
REFERENCES = os.path.join(APP_DIR, "skills", "references")

_COMMON_RULES = (
    "Real history only: every fact, number, date and quote comes from the research notes or is common, well-documented "
    "knowledge; contested figures are given as a range with who claims them. Name sources inside the sentence (a "
    "memoir, a letter, an army report, a later testimony). Never invent a named character or a quote. Brutal facts are "
    "stated plainly, never relished or glorified. Respect every people involved, especially Indigenous nations and "
    "civilians, and cite their own accounts. No modern politics.")

CHANNELS = {
    "survivors_account": {
        "name": "The Survivor's Account",
        "handle": "@SurvivorsAccount",
        "tagline": "History, told by the people who lived through it.",
        "niche": ("Famous battles, sieges and disasters told through ONE real eyewitness account (often a teenager or a "
                  "survivor): Gettysburg, Pompeii, Agincourt, the fall of Constantinople, the Titanic, Isandlwana..."),
        "audience": "Men 25-65, US and UK first, who love military history, last stands and 'what it was really like'.",
        "tone": ("Grave, vivid, intimate. The narrator walks beside the witness: we see what they saw, at their height, "
                 "with their age and their fear, then step back to explain what was really happening."),
        "rules": (_COMMON_RULES + " EVERY video is built around one real, named eyewitness whose account survives (a "
                  "memoir, letters, a diary, a recorded testimony). The hook names the witness, their age and where "
                  "they stood. Quote the witness verbatim 5-10 times, short lines read aloud and introduced as theirs "
                  "('She later wrote: ...'): these become on-screen quote cards. Alternate the witness's view with the "
                  "wider picture (forces, tactics, numbers). The ending says what became of the witness and how their "
                  "words reached us."),
        "reference": "EDGm3821yE8",
        "minutes": 38,
        "image_style": "paint",
        "title_formulas": [
            "What a [age]-Year-Old [witness] Saw at [event] Was Too Brutal for Textbooks",
            "The [age]-Year-Old Who [did/watched X] — [His/Her] [letters/diary] Still Exist",
            "The [role] Who Survived [event]'s Final [N] Days",
            "What a [witness] Saw at [event] Was Left Out of [side] History",
        ],
    },
    "frontier_blood": {
        "name": "Frontier Blood",
        "handle": "@FrontierBlood",
        "tagline": "The American frontier, without the Hollywood.",
        "niche": ("The American frontier and the wars of the West, 1820-1890: the Alamo, Comanche and Lakota wars, "
                  "Texas Rangers, Adobe Walls, Fetterman, the Wagon Box Fight, Little Bighorn and beyond."),
        "audience": "Men 25-65, mostly US, who love Western and frontier history told straight.",
        "tone": ("Grave, vivid, plain-spoken. The frontier as it was: distances, hunger, weather, weapons, fear, on every "
                 "side, never the movie version."),
        "rules": (_COMMON_RULES + " Give every side its own sources: army reports and soldiers' letters, and the "
                  "accounts of Comanche, Lakota, Cheyenne, Kiowa or Tejano participants. Explain the weapons and why "
                  "they mattered (ranges, reload times). Pay off the title formula ('They didn't just...', 'more "
                  "terrifying than you think', 'N vs M') with specifics."),
        "reference": "EDGm3821yE8",
        "minutes": 38,
        "image_style": "paint",
        "title_formulas": [
            "They Didn't Just [lose/kill X] — The [Final N Minutes / Truth] Nobody Talks About",
            "[Event] Was More Terrifying Than You Think",
            "How [N] [men] Held Off [M] [enemy] at [place]",
            "The Secret Weapon [N] [men] Used Against [M] [enemy] | [Battle]",
        ],
    },
}


def channel(key):
    return CHANNELS.get(key)


def ideas(key):
    """Idées de vidéos de la chaîne (titre, texte de miniature, scène, côté du texte, image de base)."""
    path = os.path.join(PRESETS, key, "ideas.json")
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError):
        return []
    for it in items:
        img = os.path.join(PRESETS, key, "ideas", it["id"] + ".jpg")
        it["image"] = img if os.path.isfile(img) else None
    return items


def idea_for(key, title):
    t = (title or "").strip().lower()
    return next((i for i in ideas(key) if i["title"].strip().lower() == t), None)


def reference_text(key):
    ref = (CHANNELS.get(key) or {}).get("reference")
    try:
        with open(os.path.join(REFERENCES, f"{ref}.txt"), encoding="utf-8") as f:
            return f.read()
    except (OSError, TypeError):
        return ""


def bible(key):
    """Analyse FacelessOS de la vidéo de référence, faite une fois puis gardée dans presets/history_channels/."""
    path = os.path.join(PRESETS, key, "bible.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    ref = reference_text(key)
    if not ref:
        return ""
    text = S.build_bible(dict(_base(key), bible="", reference_scripts=""), ref)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return text


def _base(key):
    c = CHANNELS[key]
    return {"name": c["name"], "language": "en", "format": "history_doc", "niche": c["niche"],
            "audience": c["audience"], "tone": c["tone"], "rules": c["rules"], "cta": "", "wpm": 150}


def fos_channel(key, wpm=None):
    """La chaîne telle que FacelessOS l'attend (pov_script) : contexte, bible et voix de référence."""
    ch = _base(key)
    ch.update(bible=bible(key), reference_scripts=reference_text(key),
              bible_note="derived from the reference video of this format (Dose of History) — follow its hook shape, "
                         "beat map, rhythm and ending; never its topic, lines or hooks")
    if wpm:
        ch["wpm"] = wpm
    return ch
