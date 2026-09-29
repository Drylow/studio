"""Tools vidéo — frontends statiques de l'ami, servis DEPUIS le site.

Nouvelle archi (2026-06-13) : l'ami ne fournit plus des services Docker sur
son VPS, mais des frontends 100 % statiques (HTML/CSS/JS) qui tournent dans
le navigateur. Ils sont copiés dans `tool_apps/` à la racine du projet et
servis par Flask DERRIÈRE le mot de passe boss — surtout PAS via /static/
qui est public, car `config.js` contient les clés API.

  /tools/<slug>          → page-cadre Night City (iframe + topbar)
  /toolfiles/<path>      → sert les fichiers de tool_apps/ (boss-only)
  /api/tools/status      → présence des fichiers sur le disque

Les pages chargent `../config.js` (clés API + URL render). Comme tout
l'arbre est monté sous /toolfiles/, les chemins relatifs des apps
(`./assets/…`, `../config.js`) se résolvent tout seuls.

Seul reste à venir côté ami : l'URL de la « render API » (rendu vidéo
final + relais Replicate/HeyGen/Groq), à mettre dans tool_apps/config.js.
Tout ce qui précède le rendu (scripts, voix off, recherche de clips)
fonctionne déjà sans elle.
"""
import os

from flask import Blueprint, abort, jsonify, render_template, send_from_directory

tools_bp = Blueprint("tools", __name__)

# Racine des frontends statiques (hors /static/ → protégé par le gate boss).
TOOLFILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tool_apps")

# ── Registre des tools ────────────────────────────────────────────────────
# Pour ajouter/retirer un tool : une entrée ici. La page d'entrée est un
# chemin relatif dans tool_apps/. Sidebar, cartes d'accueil et iframe suivent.
TOOLS = {
    "explainer": {
        "slug": "explainer",
        "category": "youtube",
        "name": "EXPLAINER FORGE",
        "short": "Explainer Forge",
        "tag": "// GRID",
        "desc": "Un sujet → une vidéo explicative complète : chapitres, scripts, "
                "pictogrammes, voix off, montage. Queue et bibliothèque intégrées.",
        "entry": "explainer/index.html",
        "theme": "explainer",
        "needs_render": True,
        "accent": "violet",
        "icon": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
                '<rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 17.5h7M17.5 14v7"/>',
    },
    "pov-studio": {
        "slug": "pov-studio",
        "category": "youtube",
        "name": "POV STUDIO 2D",
        "short": "POV Studio 2D",
        "tag": "// POV",
        "desc": "Script POV par niveaux → voix off ElevenLabs, images IA par scène, "
                "montage auto. Inclut Niche Bending (analyse de chaînes virales).",
        "entry": "pov-studio/index.html",
        "theme": "dark",
        "needs_render": True,
        "accent": "pink",
        "icon": '<path d="M4 5h16v11H4z"/><path d="M8 21h8M12 16v5"/><circle cx="9" cy="10" r="1.6"/>'
                '<path d="M13 12l2.5-3 2.5 3"/>',
    },
    "delamain": {
        "slug": "delamain",
        "category": "agent",
        "name": "DELAMAIN",
        "short": "Delamain",
        "tag": "// CORE",
        "desc": "L'intelligence opérationnelle du studio. Concierge IA (Claude) à la "
                "Delamain : te conseille, planifie tes vidéos, et — bientôt — pilote "
                "directement les outils du studio.",
        "entry": "delamain/index.html",
        "theme": "dark",
        "needs_render": False,
        "accent": "cyan",
        "icon": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2"/>'
                '<path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
    },
    "voiceover": {
        "slug": "voiceover",
        "category": "youtube",
        "name": "VOICEOVER STUDIO",
        "short": "Voiceover Studio",
        "tag": "// VOX",
        "desc": "Générateur de voix off ElevenLabs autonome — 100 % navigateur, "
                "aucun serveur requis. Fonctionne dès que la clé ElevenLabs est posée.",
        "entry": "voiceover/index.html",
        "theme": "dark",
        "needs_render": False,
        "accent": "cyan",
        "icon": '<path d="M12 3v18M8 7v10M16 7v10M4 10v4M20 10v4"/>',
    },
    "stock-footage": {
        "slug": "stock-footage",
        "category": "youtube",
        "name": "NINEVEH",
        "short": "Nineveh",
        "tag": "// STOCK",
        "desc": "Script de narration → documentaire en stock footage (Pexels/Pixabay) : "
                "TTS, découpage en scènes, éditeur de clips, render final.",
        "entry": "stock-footage/index.html",
        "theme": "shadcn",
        "needs_render": True,
        "accent": "cyan",
        "icon": '<path d="M3 6l4-2 5 2 5-2 4 2v12l-4 2-5-2-5 2-4-2z"/><path d="M12 6v12M7 4v12M17 4v12"/>',
    },
    "heygen": {
        "slug": "heygen",
        "category": "youtube",
        "name": "AVATAR DECK",
        "short": "Avatar Deck",
        "tag": "// HEYGEN",
        "desc": "Pipeline avatar HeyGen : transcription Whisper, plan B-roll par LLM, "
                "assets auto, render. Dashboard + studio fournis par l'outil.",
        "entry": "heygen/index.html",
        "theme": "dark",
        "needs_render": True,
        "accent": "gold",
        "icon": '<circle cx="12" cy="8" r="4"/><path d="M5 21c0-3.5 3-6 7-6s7 2.5 7 6"/>'
                '<path d="M19 3l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
    },
    "lore": {
        "slug": "lore",
        "category": "youtube",
        "name": "LORE",
        "short": "Lore",
        "tag": "// LORE",
        "desc": "Génère la vidéo ENTIÈRE « X faits / lore pour s'endormir » (Pokémon, Zelda, "
                "Mario, séries…) : narration, visuels, montage, miniature + SEO. Rendu sur "
                "le worker distant. Aussi piloté automatiquement par Delamain.",
        "entry": "lore/index.html",
        "theme": "dark",
        "needs_render": True,
        "accent": "cyan",
        "icon": '<path d="M3 5h13l5 5v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/>'
                '<path d="M9 11.5l4 2.3-4 2.3z" fill="currentColor" stroke="none"/><path d="M16 5v5h5"/>',
    },
    "thumbnail-creator": {
        "slug": "thumbnail-creator",
        "category": "youtube",
        "name": "THUMBNAIL CREATOR",
        "short": "Thumbnail Creator",
        "tag": "// THUMB",
        "desc": "Crée des miniatures YouTube : pars d'un lien vidéo (récupère sa "
                "miniature) ou d'une image de référence, ajoute un prompt → "
                "Nano Banana 2 (Fal) génère la miniature.",
        "entry": "thumbnail-creator/index.html",
        "theme": "dark",
        "needs_render": False,
        "accent": "pink",
        "icon": '<rect x="3" y="4" width="18" height="14" rx="2"/><circle cx="8.5" cy="9.5" r="1.6"/>'
                '<path d="M21 15l-5-4-4 3-2-1.5L3 17"/>',
    },
    "script-writer": {
        "slug": "script-writer",
        "category": "youtube",
        "name": "SCRIPT WRITER",
        "short": "Script Writer",
        "tag": "// SCRIPT",
        "desc": "Donne un thème et une durée de voix off → Claude écrit ton script "
                "en direct (streaming), avec compteur de mots et jauge en temps réel.",
        "entry": "script-writer/index.html",
        "theme": "dark",
        "needs_render": False,
        "accent": "violet",
        "icon": '<path d="M4 4h11l5 5v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/>'
                '<path d="M14 4v5h5M8 13h8M8 17h6"/>',
    },
    "title-description": {
        "slug": "title-description",
        "category": "youtube",
        "name": "TITLE & DESCRIPTION",
        "short": "Title & Desc",
        "tag": "// SEO",
        "desc": "À partir d'un script ou d'un thème : titres optimisés CTR, description "
                "SEO (chapitres, CTA, hashtags) et tags — par Claude.",
        "entry": "title-description/index.html",
        "theme": "dark",
        "needs_render": False,
        "accent": "cyan",
        "icon": '<path d="M3 7l4-3h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H7l-4-3z"/>'
                '<path d="M8 9h9M8 12h9M8 15h6"/>',
    },
    "image-forge": {
        "slug": "image-forge",
        "category": "youtube",
        "name": "IMAGE FORGE",
        "short": "Image Forge",
        "tag": "// IMG",
        "desc": "Génère n'importe quel visuel (b-roll, bannière, poster, mème, avatar) "
                "en haute qualité avec Nano Banana 2 (Fal) — prompt + images de "
                "référence optionnelles, formats variés, jusqu'à 4 images.",
        "entry": "image-forge/index.html",
        "theme": "dark",
        "needs_render": False,
        "accent": "violet",
        "icon": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/>'
                '<path d="M21 16l-5-5L5 21"/>',
    },
    "video-forge": {
        "slug": "video-forge",
        "category": "youtube",
        "name": "VIDEO FORGE",
        "short": "Video Forge",
        "tag": "// VID",
        "desc": "Anime une image fixe (miniature, visuel, photo) en clip vidéo avec "
                "Kling 2.5 (Fal) — idéal pour intros, transitions et Shorts. 5 ou 10 s.",
        "entry": "video-forge/index.html",
        "theme": "dark",
        "needs_render": True,
        "accent": "pink",
        "icon": '<rect x="2.5" y="5" width="19" height="14" rx="3"/>'
                '<path d="M10 9.2l5 2.8-5 2.8z" fill="currentColor" stroke="none"/>',
    },
}


# ── Catégories ─────────────────────────────────────────────────────────────
# Regroupement des outils pour la navigation à 2 niveaux : l'accueil affiche
# ces catégories ; cliquer ouvre /category/<slug> qui liste les outils dont le
# champ "category" correspond. Pour déplacer un outil : changer son "category".
CATEGORIES = {
    "agent": {
        "slug": "agent",
        "name": "DELAMAIN",
        "desc": "L'intelligence opérationnelle du studio — ton concierge IA qui te "
                "conseille, planifie et pilotera bientôt toute la production.",
        "accent": "cyan",
        "icon": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2"/>'
                '<path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
    },
    "youtube": {
        "slug": "youtube",
        "name": "YOUTUBE",
        "desc": "Ton arsenal complet pour produire des vidéos YouTube : scripts, "
                "vidéos explicatives, POV, documentaires, avatars, recherche de niche "
                "et miniatures.",
        "accent": "pink",
        "icon": '<rect x="2.5" y="5" width="19" height="14" rx="4"/>'
                '<path d="M10 9.2l5 2.8-5 2.8z" fill="currentColor" stroke="none"/>',
    },
}


def _tools_in(cat_slug):
    return [t for t in TOOLS.values() if t.get("category") == cat_slug]


@tools_bp.app_context_processor
def _inject_tools():
    # Tous les templates connaissent la liste des outils ET les catégories
    # (avec leurs outils) pour la nav à 2 niveaux.
    cats = []
    for slug, cat in CATEGORIES.items():
        tools = _tools_in(slug)
        if tools:
            c = dict(cat)
            c["tools"] = tools
            cats.append(c)
    return {"nav_tools": list(TOOLS.values()), "nav_categories": cats}


@tools_bp.route("/category/<slug>")
def category_page(slug):
    cat = CATEGORIES.get(slug)
    if cat is None:
        abort(404)
    return render_template(
        "category.html",
        category=cat,
        cat_tools=_tools_in(slug),
        active_page="cat-" + slug,
    )


@tools_bp.route("/tools/<slug>")
def tool_page(slug):
    tool = TOOLS.get(slug)
    if tool is None:
        abort(404)
    installed = os.path.isfile(os.path.join(TOOLFILES_DIR, tool["entry"]))
    return render_template(
        "tool_frame.html",
        tool=tool,
        installed=installed,
        iframe_src=("/toolfiles/" + tool["entry"]) if installed else "",
        active_page="tool-" + slug,
    )


@tools_bp.route("/toolfiles/<path:relpath>")
def tool_file(relpath):
    # Boss-only : /toolfiles est dans BOSS_ONLY_PREFIXES (app.py), donc le
    # gate a déjà refusé les guests avant d'arriver ici. send_from_directory
    # bloque tout débordement hors de TOOLFILES_DIR (path traversal).
    return send_from_directory(TOOLFILES_DIR, relpath)


@tools_bp.route("/api/tools/status")
def tools_status():
    # Plus de ping réseau : les tools sont des fichiers locaux. On vérifie
    # juste qu'ils sont bien installés sur le disque.
    out = {}
    for slug, tool in TOOLS.items():
        installed = os.path.isfile(os.path.join(TOOLFILES_DIR, tool["entry"]))
        out[slug] = {"installed": installed, "needs_render": tool["needs_render"]}
    return jsonify({"tools": out})
