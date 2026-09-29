"""Worker autonome de Delamain — produit puis publie les vidéos du calendrier
aux dates prévues, SANS intervention.

Sur o2switch (mutualisé) il n'y a pas de démon long. On fonctionne donc en
**machine à états incrémentale** : chaque « tick » fait avancer UNE fiche d'une
seule étape (démarrer un rendu, ou vérifier un rendu → publier). On déclenche
les ticks soit depuis le navigateur (Delamain ouvert), soit par un CRON o2switch
qui appelle l'URL avec un secret.

  POST /api/delamain/worker/tick                  (boss) -> avance une fiche
  GET  /api/delamain/worker/tick?key=<SECRET>     (cron) -> idem, sans session
  GET  /api/delamain/worker/status                (boss) -> compteurs

Cycle d'une fiche (champ status) :
  scheduled  --(date atteinte)-->  rendering(render_job)  --(rendu fini)-->  posted
Seules les chaînes avec autonomy='auto' + connectées YouTube + une franchise
sur la fiche sont traitées. Une fiche sans franchise est ignorée (jamais bloquante).

Secrets .env : LORE_WORKER_URL (rendu) + GOOGLE_* (publication) + WORKER_CRON_SECRET (cron).
"""
import os
import re
import io
import hmac
import json
import time
import base64
import datetime
import threading
import unicodedata
import urllib.parse
import urllib.request
import urllib.error

try:  # Pillow optionnel : sert à borner/normaliser les logos téléchargés.
    from PIL import Image
except Exception:  # pas installé → on garde l'image brute (cf. _download_image)
    Image = None

from flask import Blueprint, jsonify, request, session

from database import (project_list, project_get, group_get, plan_list, plan_get, plan_update,
                      worker_lock_acquire, worker_lock_release,
                      asset_get, asset_set,
                      event_log, event_list, worker_heartbeat, worker_state_get)
from routes.youtube import (_access_token, _opener, _configured as _yt_configured,
                            _resumable_upload)

worker_bp = Blueprint("delamain_worker", __name__)

# Franchises gérées par le tool Lore (doit rester aligné avec routes/lore.py).
# South Park + Family Guy RETIRÉS (choix user 2026-06-30) : la modération de Fal bloque leurs
# persos (enfants/bébés) → pas de miniature auto fiable → on ne les produit plus.
_FR_IDS = {"pokemon", "zelda", "mario", "sonic", "naruto", "onepiece",
           "simpsons", "spongebob", "gravityfalls", "rickandmorty"}
_FR_SERIES = {"simpsons", "spongebob", "gravityfalls", "rickandmorty"}
# Nom affiché de la licence (= texte du logo sous le titre de la miniature).
_FR_NAMES = {"pokemon": "Pokémon", "zelda": "Zelda", "mario": "Mario", "sonic": "Sonic",
             "naruto": "Naruto", "onepiece": "One Piece", "simpsons": "Les Simpson",
             "spongebob": "Bob l'éponge", "gravityfalls": "Gravity Falls",
             "rickandmorty": "Rick et Morty"}

# Verrou : un seul tick à la fois dans ce process (évite que deux appels
# simultanés — boucle navigateur + cron, ou un tick lent encore en cours —
# lancent/publient deux fois la même vidéo).
_TICK_LOCK = threading.Lock()

# Rendu : un échec d'atelier est le plus souvent PASSAGER (file saturée, GPU qui se
# réveille, proxy 5xx). On NE grille pas les essais d'un coup : on RÉESSAYE plus tard
# (toutes les ~10 min) pour laisser le proxy/l'atelier récupérer → le rendu se fait
# tout seul même si personne ne regarde. Chaque retry repart d'un rendu NEUF (le job
# échoué est abandonné). Borné dans le temps : au-delà, la fiche passe « à corriger ».
_MAX_RENDER_TRIES = 12       # ~12 tentatives × 10 min ≈ 2 h de rattrapage auto
_RETRY_DELAY_SEC = 600       # délai entre 2 tentatives (10 min)
# Miniature au moment de PUBLIER : si la génération échoue (Fal injoignable), on NE
# publie PAS sans miniature — on retente au tick suivant. Au-delà de ce seuil on poste
# quand même (mieux vaut la vidéo en ligne sans miniature custom que jamais), avec une
# note « miniature à refaire » → le boss la refait d'un clic (re-roll, push YouTube).
_MAX_THUMB_PUBFAIL = 5


def _cfg(name):
    return os.getenv(name, "").strip()


def _log(level, action, message, entry=None):
    """Écrit une ligne dans le journal du worker (console live + diagnostic). `entry` =
    la fiche concernée (pour relier l'événement à la vidéo/chaîne). Best-effort."""
    pid = entry.get("id") if isinstance(entry, dict) else None
    proj = entry.get("project_id") if isinstance(entry, dict) else None
    event_log(level, action, message, plan_id=pid, project_id=proj)


def _render_tries(notes):
    """Nombre de rendus déjà tentés, lu dans le marqueur de notes (__queued:N /
    __running:N / __retry:N[@heure]). 0 = premier essai."""
    m = re.search(r"__(?:queued|running|retry):(\d+)", notes or "")
    return int(m.group(1)) if m else 0


def _retry_due(notes):
    """Fiche en attente de RE-tentative (marqueur __retry:N@<iso>) : True si l'heure de
    re-tentative est passée (ou s'il n'y a pas d'heure). Sert à ESPACER les retries de
    ~10 min sans démon (on saute la fiche tant que l'heure n'est pas atteinte)."""
    m = re.search(r"__retry:\d+@([0-9T:\-]+)", notes or "")
    if not m:
        return True
    try:
        return _now() >= datetime.datetime.fromisoformat(m.group(1))
    except Exception:
        return True


def _render_transient(err):
    """Échec d'atelier vraisemblablement PASSAGER (→ on retente). Un échec « dur »
    (sujet invalide, etc.) n'est pas retenté pour ne pas gâcher du calcul inutile.
    On y inclut les erreurs de JSON mal formé du LLM d'écriture de script de l'atelier
    (« chatJSON: JSON invalide », « SyntaxError: Expected … in JSON ») : le modèle sort
    parfois un JSON tronqué/invalide — une nouvelle tentative repart proprement et passe."""
    e = (err or "").lower()
    return any(k in e for k in ("503", "502", "504", "500", "timeout", "timed out",
                                "unavailable", "overload", "temporar", "rate limit",
                                "too many", "gateway", "connection", "reset", "proxy",
                                "json", "syntaxerror", "chatjson", "parse", "unexpected",
                                "malformed", "econn", "fetch failed", "socket"))


def _lore_base():
    return _cfg("LORE_WORKER_URL").rstrip("/")


def _lore_headers():
    h = {"Accept": "application/json"}
    tok = _cfg("LORE_WORKER_TOKEN")
    if tok:
        h["x-worker-token"] = tok
    return h


# ── Atelier vidéo de la chaîne (multi-tool) ───────────────────────────────────
# Chaque chaîne a un `video_tool`. Tous les ateliers parlent le MÊME protocole HTTP
# (POST /render -> jobId ; GET /jobs/<id> -> {status,...} ; GET /jobs/<id>/video ->
# le MP4). Seuls changent l'URL, l'en-tête d'auth, et le corps de /render. On ABSTRAIT
# ça ici → le reste du worker (rendu, suivi, publication) est identique pour tous.
#   video_tool = 'lore'              -> atelier Lore (12 franchises, en-tête x-worker-token)
#   video_tool = 'remotion:<niche>'  -> atelier Remotion (aiconvo|chess|war, Bearer token)
_REMOTION_NICHES = {"aiconvo", "chess", "war"}
# Familles d'échecs « game-review » → endpoint POST /render-game (≠ /render des niches).
# video_tool = remotion:chess-<type>[-short]  (type = game|compilation|opening)
_CHESS_GAME_TYPES = {"game", "compilation", "opening"}


def _engine(proj):
    """Décrit l'atelier vidéo de la chaîne : {kind, niche, gametype, short, render_path,
    base, headers, lang}. Défaut = Lore. `lang` = langue de la chaîne ('fr'/'en')."""
    vt = (proj.get("video_tool") or "").strip().lower() if isinstance(proj, dict) else ""
    lang = ((proj.get("lang") or "fr").strip().lower() if isinstance(proj, dict) else "fr")
    if lang not in ("fr", "en"):
        lang = "fr"
    if vt.startswith("remotion"):
        sub = vt.split(":", 1)[1] if ":" in vt else "aiconvo"   # ex: chess, chess-compilation, chess-opening-short
        h = {"Accept": "application/json"}
        tok = _cfg("REMOTION_WORKER_TOKEN")
        if tok:
            h["Authorization"] = "Bearer " + tok      # Remotion : Bearer (≠ Lore)
        base = _cfg("REMOTION_WORKER_URL").rstrip("/")
        # Échecs « game-review » : remotion:chess-<type>[-short] -> POST /render-game.
        if sub.startswith("chess-"):
            rest = sub[len("chess-"):]
            short = rest.endswith("-short")
            gtype = rest[:-6] if short else rest      # retire '-short'
            if gtype not in _CHESS_GAME_TYPES:
                gtype = "compilation"
            if gtype == "game":
                short = False                          # game-review = long 16:9 uniquement
            return {"kind": "remotion", "niche": "chess", "gametype": gtype, "short": short,
                    "render_path": "/render-game", "lang": lang, "base": base, "headers": h}
        # Niche classique (aiconvo|chess|war) -> POST /render.
        niche = sub if sub in _REMOTION_NICHES else "aiconvo"
        return {"kind": "remotion", "niche": niche, "gametype": "", "short": False,
                "render_path": "/render", "lang": lang, "base": base, "headers": h}
    return {"kind": "lore", "niche": "", "gametype": "", "short": False,
            "render_path": "/render", "lang": lang, "base": _lore_base(), "headers": _lore_headers()}


def _engine_configured(eng):
    return bool(eng.get("base"))


def _eng_call(eng, path, method="GET", body=None, timeout=40):
    """Appel HTTP à l'atelier `eng` (même protocole pour Lore et Remotion)."""
    url = eng["base"] + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    h = dict(eng["headers"])
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except ValueError:
            return {"raw": raw}


def _render_body(eng, entry):
    """Construit le corps de POST /render selon l'atelier. Lore : franchise + (durée|100
    faits). Remotion : niche (fixée par la chaîne) + titre + langue (fr=True si la chaîne
    est en français) ; flag `long` pour l'AI Convo si la fiche demande une vidéo longue."""
    title = (entry.get("topic") or entry.get("title") or "").strip()
    if eng["kind"] == "remotion":
        gtype = eng.get("gametype") or ""
        if gtype:   # famille échecs game-review -> POST /render-game (query = le sujet de la fiche)
            body = {"type": gtype, "query": title, "lang": eng.get("lang", "en")}
            if eng.get("short"):
                body["short"] = True
            if gtype == "compilation":
                body["depth"] = "highlight"   # punchy par défaut (review/full = plus lourds)
            return body
        body = {"niche": eng["niche"], "title": title, "fr": (eng.get("lang") == "fr")}
        if eng["niche"] == "aiconvo":
            mins = _entry_minutes(entry)
            if mins >= 7:                  # >= ~7 min → mode long (6 rounds)
                body["long"] = True
        return body
    return None   # Lore : corps construit dans _start_render (logique franchise existante)


def _entry_minutes(entry):
    """Durée demandée (minutes) lue sur la fiche puis dans le titre. 0 si rien."""
    try:
        mins = float(str(entry.get("duration") or "").strip() or 0)
    except ValueError:
        mins = 0
    if mins <= 0:
        mins = _duration_from_text(entry.get("topic") or entry.get("title") or "")
    return mins


def _authorized():
    """Boss en session OU bon secret de cron."""
    if session.get("role") == "boss":
        return True
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    secret = _cfg("WORKER_CRON_SECRET")
    # compare_digest = comparaison à temps constant (anti timing-attack sur le secret).
    return bool(secret and key and hmac.compare_digest(str(key), secret))


def _now():
    return datetime.datetime.now()


def _parse(post_at):
    """post_at 'AAAA-MM-JJ HH:MM' (ou 'AAAA-MM-JJ') -> datetime naïf, ou None."""
    s = (post_at or "").strip()
    if not s:
        return None
    for fmt, ln in (("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.datetime.strptime(s[:ln], fmt)
        except ValueError:
            continue
    return None


def _due(post_at):
    """post_at <= maintenant ? (pas de date = dû)."""
    dt = _parse(post_at)
    return True if dt is None else dt <= _now()


def _rfc3339_future(post_at):
    """Si post_at est dans le FUTUR -> chaîne RFC3339 UTC pour publishAt YouTube
    (publication programmée). Sinon None -> publication publique immédiate."""
    dt = _parse(post_at)
    if dt is None:
        return None
    aware = dt.astimezone()  # interprété en heure locale du serveur
    if aware <= datetime.datetime.now().astimezone():
        return None
    return aware.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Génération métadonnées + miniature côté studio (basées sur la chaîne) ─────

def _channel_videos(proj, n=6):
    """Titres + descriptions + miniatures des n dernières vidéos de la chaîne."""
    try:
        access = _access_token(proj["yt_refresh_token"], proj.get("proxy", ""))
        op = _opener(proj.get("proxy", ""))
        r1 = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true")
        r1.add_header("Authorization", "Bearer " + access)
        with op.open(r1, timeout=20) as rr:
            d1 = json.loads(rr.read().decode("utf-8"))
        uploads = d1["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        r2 = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults="
            + str(n) + "&playlistId=" + uploads)
        r2.add_header("Authorization", "Bearer " + access)
        with op.open(r2, timeout=20) as rr:
            d2 = json.loads(rr.read().decode("utf-8"))
        out = []
        for it in d2.get("items", []):
            sn = it.get("snippet", {})
            th = sn.get("thumbnails", {}) or {}
            # 16:9 PLEINE résolution d'abord (maxres) puis medium (16:9) ; 'high'
            # est du 4:3 → donnerait des bandes noires en réf. On évite.
            thumb = ((th.get("maxres") or {}).get("url")
                     or (th.get("medium") or {}).get("url")
                     or (th.get("high") or {}).get("url") or "")
            out.append({"title": sn.get("title", ""),
                        "description": (sn.get("description", "") or "")[:500],
                        "thumb": thumb})
        return out
    except Exception:
        return []


def _llm(prompt, max_tokens=900):
    base = _cfg("LLM_BASE").rstrip("/"); key = _cfg("LLM_KEY")
    if not base or not key:
        return ""
    body = {"model": "claude-sonnet-4-6", "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(base + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"]


def _llm_vision(prompt, image_url, max_tokens=240):
    """Comme _llm mais avec une IMAGE en entrée (le proxy cliwebproxy supporte la
    vision). Sert à analyser le STYLE d'une miniature de réf."""
    base = _cfg("LLM_BASE").rstrip("/"); key = _cfg("LLM_KEY")
    if not base or not key or not image_url:
        return ""
    body = {"model": "claude-sonnet-4-6", "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}]}]}
    req = urllib.request.Request(base + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"]


def _analyze_style(ref_url):
    """Vision : décrit le STYLE d'une miniature de la chaîne (pour la RECRÉER de zéro
    avec un autre sujet, cas « pas de réf du même thème »). Ne décrit PAS le perso
    (il sera remplacé). Renvoie un paragraphe anglais prêt à mettre dans un prompt."""
    if not ref_url:
        return ""
    prompt = ("Analyse cette miniature YouTube. Décris en ANGLAIS, en UN seul paragraphe continu, "
              "tout ce qu'il faut pour recréer son STYLE EXACT avec un sujet différent : le style "
              "graphique, le fond, le TEXTE exact du gros titre + son style typographique (couleur, "
              "contour, ombre, position — à garder identique), le style et la position du logo, la "
              "mise en page, la palette, les éléments décoratifs, l'ambiance. NE décris PAS le "
              "personnage spécifique (il sera remplacé). Commence directement par la description.")
    try:
        return (_llm_vision(prompt, ref_url) or "").strip()
    except Exception:
        return ""


def _channel_brief(entry):
    """Consignes du boss qui doivent guider la PRODUCTION AUTO de cette fiche :
    instructions communes du PROJET (delamain_groups.instructions, héritées) PUIS
    instructions propres de la CHAÎNE (delamain_projects.description). Concaténées.
    → injectées dans la génération des titres/descriptions ET des miniatures pour que
    Delamain respecte le ton/format/style demandés. '' si rien (comportement inchangé)."""
    pid = entry.get("project_id")
    if not pid:
        return ""
    try:
        proj = project_get(pid)
    except Exception:
        proj = None
    if not proj:
        return ""
    parts = []
    gid = proj.get("group_id")
    if gid:
        try:
            g = group_get(gid)
            if g and (g.get("instructions") or "").strip():
                parts.append(g["instructions"].strip())
        except Exception:
            pass
    chan = (proj.get("description") or "").strip()
    if chan:
        parts.append(chan)
    return "\n\n".join(parts)[:1500]


def _gen_metadata(entry, vids):
    """Titre + description + tags calqués sur les vidéos existantes de la chaîne."""
    examples = "\n".join("- " + v["title"] + "\n  " + v["description"][:200] for v in vids[:4])
    subject = entry.get("topic") or entry.get("title") or ""
    try:
        mins = float(str(entry.get("duration") or "").strip() or 0)
    except ValueError:
        mins = 0
    dur_note = ("\n\nIMPORTANT : cette vidéo dure ~" + str(int(mins)) + " minute(s), ce n'est PAS une liste de 100 faits. "
                "N'écris PAS « 100 anecdotes » / « 100 faits » dans le titre : adapte le titre à une vidéo courte de ~"
                + str(int(mins)) + " min sur le sujet.") if mins > 0 else ""
    brief = _channel_brief(entry)
    brief_note = (("\n\nCONSIGNES DU PROPRIÉTAIRE DE LA CHAÎNE (à respecter en priorité, "
                   "elles priment sur l'imitation des exemples) :\n" + brief) if brief else "")
    prompt = ("Tu écris les métadonnées YouTube d'une NOUVELLE vidéo, dans le style EXACT de la chaîne.\n"
              "Vidéos déjà publiées (titres + descriptions) à imiter :\n" + (examples or "(aucune)") +
              brief_note +
              "\n\nNouvelle vidéo — sujet : " + subject + dur_note +
              "\n\nRéponds en JSON STRICT, rien d'autre : "
              '{"title":"...","description":"...","tags":["t1","t2"]}. '
              "Titre ≤100 caractères, même ton/format que les titres ci-dessus. "
              "Description : accroche + résumé + 3-5 hashtags. 10-15 tags pertinents.")
    try:
        txt = _llm(prompt)
    except Exception:
        return
    m = re.search(r"\{[\s\S]*\}", txt or "")
    if not m:
        return
    try:
        data = json.loads(m.group(0))
    except Exception:
        return
    upd = {}
    if data.get("title"):
        upd["title"] = str(data["title"])[:100]
    if data.get("description"):
        upd["description"] = str(data["description"])
    tags = data.get("tags")
    if tags:
        upd["tags"] = ",".join(tags) if isinstance(tags, list) else str(tags)
    if upd:
        plan_update(entry["id"], upd)


def _thumb_subject(entry):
    """Sujet PRÉCIS pour le personnage de la miniature, extrait du topic
    (« 1h de Secrets sur Pikachu pour s'endormir » -> « Pikachu »). Évite que le
    modèle mette un perso générique (ex. Ronflex quand on dit juste « Pokémon »)."""
    t = (entry.get("topic") or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s*pour s'endormir.*$", "", t, flags=re.I).strip()
    t = re.sub(r"\s*(expliquée?s?|qu'on ne t'a jamais dites?)\s*$", "", t, flags=re.I).strip()
    m = (re.search(r"\bsur\s+(.+)$", t, flags=re.I)
         or re.search(r"\bdes?\s+(.+)$", t, flags=re.I)
         or re.search(r"\bdu\s+(.+)$", t, flags=re.I)
         or re.search(r"\bd'(.+)$", t, flags=re.I))
    if m:
        t = m.group(1).strip()
    t = re.sub(r"^(les|le|la|l')\s+", "", t, flags=re.I).strip()
    return t[:40]


def _norm(s):
    """minuscule + sans accents (repli de secours sans LLM)."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return s.lower()


def _subject_for_thumb(entry):
    """Sujet/personnage à dessiner sur la miniature. UNIVERSEL : c'est Claude qui
    lit le titre (n'importe quel format, n'importe quel thème, n'importe quelle
    langue) et renvoie le sujet en quelques mots. Repli regex si le LLM est indispo."""
    topic = (entry.get("topic") or entry.get("title") or "").strip()
    if not topic:
        return "this video"
    prompt = ("Titre d'une vidéo YouTube : « " + topic + " ».\n"
              "Donne UNIQUEMENT le sujet ou personnage principal à représenter sur la "
              "miniature, en 1 à 4 mots, sans phrase ni ponctuation autour "
              "(ex. « Pikachu », « Ted Bundy », « la Tour Eiffel », « Bitcoin »).")
    try:
        ans = (_llm(prompt, max_tokens=20) or "").strip()
        ans = ans.splitlines()[0].strip().strip('".«»·-–—').strip()
    except Exception:
        ans = ""
    return (ans[:50] or _thumb_subject(entry) or topic[:50])


def _pick_reference(vids, entry):
    """Choisit la miniature de RÉFÉRENCE. UNIVERSEL : Claude regarde les titres des
    anciennes vidéos de la chaîne et désigne celle du MÊME univers/thème que la
    nouvelle. Renvoie (url, matched) : matched=True si on a trouvé une réf du MÊME
    thème (son logo est déjà le bon → on ne change QUE le perso) ; matched=False si
    on retombe sur la plus récente (autre thème : il faudra REFAIRE le logo, sinon
    on colle un logo qui ne correspond pas — ex. Luffy sous un logo Pokémon).
    Pas de liste de licences codée → marche pour n'importe quelle chaîne."""
    cands = [v for v in (vids or []) if v.get("thumb")]
    if not cands:
        return ("", False)
    topic = (entry.get("topic") or entry.get("title") or "").strip()
    listing = "\n".join("[%d] %s" % (i, (v.get("title") or "")[:90]) for i, v in enumerate(cands))
    prompt = ("Nouvelle vidéo : « " + topic + " ».\n\n"
              "Anciennes vidéos de la chaîne :\n" + listing + "\n\n"
              "Laquelle porte sur EXACTEMENT le même univers / licence / série / thème que la "
              "nouvelle (donc la même identité visuelle et le même logo) ? Réponds UNIQUEMENT "
              "par le numéro entre crochets, ou « none » si aucune ne correspond vraiment.")
    try:
        ans = (_llm(prompt, max_tokens=8) or "").strip().lower()
        if "none" not in ans:
            m = re.search(r"\d+", ans)
            if m and 0 <= int(m.group(0)) < len(cands):
                return (cands[int(m.group(0))]["thumb"], True)
    except Exception:
        pass
    # Repli sans LLM : un mot « fort » du sujet présent dans un ancien titre = match.
    subj = _norm(_thumb_subject(entry))
    for w in [w for w in subj.split() if len(w) >= 4]:
        for v in cands:
            if w in _norm(v.get("title", "")):
                return (v["thumb"], True)
    # Aucun thème ne colle → on garde la plus récente POUR LE STYLE seulement.
    return (cands[0]["thumb"], False)


def _brand_for_thumb(entry):
    """Nom de licence/série/marque à afficher comme logo (cas « pas de réf du même
    thème » : on doit refaire le logo). Claude le déduit du titre ; « » si aucune
    licence pertinente (sujet réel/généraliste → on enlèvera juste le logo)."""
    topic = (entry.get("topic") or entry.get("title") or "").strip()
    if not topic:
        return ""
    prompt = ("Vidéo : « " + topic + " ». Quel nom de licence / série / univers / marque "
              "doit apparaître comme LOGO sur la miniature ? Réponds en 1 à 3 mots "
              "(ex. « One Piece », « Pokémon », « Marvel »), ou « none » si le sujet n'a "
              "pas de licence claire (personne réelle, sujet généraliste).")
    try:
        ans = (_llm(prompt, max_tokens=12) or "").strip().splitlines()[0].strip().strip('".«»').strip()
    except Exception:
        ans = ""
    if ans.lower() in ("none", "aucune", "aucun", ""):
        return ""
    return ans[:30]


def _serp_images(query, n=6):
    """Recherche Google Images via SerpAPI → liste de résultats {original, ...}."""
    key = _cfg("SERPAPI_KEY")
    if not key:
        return []
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
        {"engine": "google_images", "q": query, "api_key": key})
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            d = json.loads(r.read().decode("utf-8"))
        return (d.get("images_results") or [])[:n]
    except Exception:
        return []


def _is_logo(url, brand):
    """Vision : cette image est-elle VRAIMENT le logo-titre de <brand> ? (filtre le
    junk que la recherche peut renvoyer : persos, photos, symboles seuls, fan-arts)."""
    prompt = ("Réponds OUI ou NON. Cette image est-elle le LOGO officiel (le titre stylisé) de "
              "la licence « " + brand + " » ? OUI seulement si c'est clairement le logo-titre, "
              "pas un personnage, pas une photo, pas un coloriage, pas un symbole/icône seul.")
    try:
        return "oui" in (_llm_vision(prompt, url, max_tokens=5) or "").lower()
    except Exception:
        return False


def _download_image(url, max_px=512, max_bytes=3000000):
    """Télécharge une image et renvoie (bytes, content_type) exploitable (png/jpeg/webp).
    Avec Pillow : borne à max_px + convertit en PNG (transparence gardée). Sans Pillow :
    garde le brut si format raster courant et pas trop gros. None si inexploitable.
    Cap à 3 Mo (et non 700 Ko) : sans Pillow, un cap trop bas rejetait de vrais logos
    officiels un peu lourds → on retombait sur le repli qui gardait le logo de la réf
    (ex. logo One Piece resté sur une miniature Naruto). 3 Mo en base64 passe à Fal."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except Exception:
        return None
    if "svg" in ct:
        return None
    if Image is not None:
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGBA")
            if max(im.size) > max_px:
                im.thumbnail((max_px, max_px))
            buf = io.BytesIO(); im.save(buf, "PNG")
            return buf.getvalue(), "image/png"
        except Exception:
            pass
    if ct in ("image/png", "image/jpeg", "image/jpg", "image/webp") and len(raw) <= max_bytes:
        return raw, ("image/jpeg" if ct == "image/jpg" else ct)
    return None


def _find_real_logo(brand):
    """Vrai logo officiel de <brand>, STOCKÉ dans NOTRE base (asset_cache). 1 seule
    recherche SerpAPI + vérif vision par licence, puis on garde l'IMAGE chez nous →
    réutilisable pour toutes les chaînes, plus JAMAIS de crédit Serp pour ce logo.
    Renvoie une data URI prête pour Fal, ou '' si rien de fiable (→ logo redessiné).
    Base extensible (kind='logo' ; on pourra ajouter 'character' etc. plus tard)."""
    brand = (brand or "").strip()
    if not brand:
        return ""
    key = brand.lower()
    # 1) Déjà dans NOTRE base → aucune recherche, on ressort l'image stockée.
    img, ct = asset_get("logo", key)
    if img:
        return "data:" + (ct or "image/png") + ";base64," + base64.b64encode(img).decode()
    # 2) Sinon : SerpAPI + vérif vision + on télécharge et on STOCKE l'image chez nous.
    if not _cfg("SERPAPI_KEY"):
        return ""
    for im in _serp_images(brand + " logo png transparent", 6):
        u = im.get("original")
        if not (u and _is_logo(u, brand)):
            continue
        got = _download_image(u)
        if not got:
            continue
        raw, ct = got
        asset_set("logo", key, u, raw, ct)
        return "data:" + ct + ";base64," + base64.b64encode(raw).decode()
    return ""


# Cache mémoire des logos embarqués (lus une fois depuis le disque).
_BUNDLED_LOGO_CACHE = {}


def _bundled_logo(fr_id):
    """Logo officiel EMBARQUÉ dans le dépôt (logos/<id>.png), pour les 12 franchises
    gérées. → TOUJOURS disponible, AUCUN téléchargement côté serveur (les CDN de logos
    bloquent souvent l'IP d'un serveur mutualisé → le DL échouait en prod et on gardait
    le mauvais logo de la réf, ex. logo One Piece sur une miniature Naruto). Renvoie une
    data URI PNG prête pour Fal, ou '' si pas de fichier. Prioritaire sur SerpAPI."""
    fr_id = (fr_id or "").strip().lower()
    if not fr_id:
        return ""
    if fr_id in _BUNDLED_LOGO_CACHE:
        return _BUNDLED_LOGO_CACHE[fr_id]
    # logos/ est à la racine de l'app (worker.py est dans routes/).
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "logos", fr_id + ".png")
    out = ""
    try:
        with open(path, "rb") as f:
            out = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        out = ""
    _BUNDLED_LOGO_CACHE[fr_id] = out
    return out


# Drapeau posé par _fal_image quand le DERNIER appel a été REFUSÉ par la modération de Fal
# (HTTP 422 « flagged by a content checker ») — ≠ panne. Lu par _gen_thumbnail pour basculer
# sur un modèle de repli (FLUX) qui n'a pas le filtre strict de Nano Banana (Gemini).
_LAST_FAL_FLAGGED = False


def _fal_image(model, payload, key):
    """Soumet un job Fal, attend la fin, renvoie l'URL image ou '' si échec. Pose
    `_LAST_FAL_FLAGGED=True` si l'échec est un REFUS de modération (422) et non une panne."""
    global _LAST_FAL_FLAGGED
    _LAST_FAL_FLAGGED = False
    try:
        req = urllib.request.Request("https://queue.fal.run/" + model,
                                     data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Authorization", "Key " + key)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as r:
            sub = json.loads(r.read().decode("utf-8"))
        surl, rurl = sub.get("status_url"), sub.get("response_url")
        if not (surl and rurl):
            return ""
        for _ in range(40):
            time.sleep(3)
            sreq = urllib.request.Request(surl); sreq.add_header("Authorization", "Key " + key)
            with urllib.request.urlopen(sreq, timeout=30) as r:
                if json.loads(r.read().decode("utf-8")).get("status") == "COMPLETED":
                    break
        rreq = urllib.request.Request(rurl); rreq.add_header("Authorization", "Key " + key)
        with urllib.request.urlopen(rreq, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
        imgs = res.get("images") or []
        return (imgs[0].get("url") or "") if imgs else ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace").lower()
        except Exception:
            body = ""
        if e.code == 422 or any(k in body for k in
                                ("content checker", "flagged", "content polic", "nsfw", "safety")):
            _LAST_FAL_FLAGGED = True
        return ""
    except Exception:
        return ""


# Le DERNIER appel a-t-il dû basculer sur le modèle de repli ? (pour le journal)
_LAST_FAL_FALLBACK = False


def _to_16x9_datauri(url):
    """Recadre une image au format 16:9 (1280×720) et renvoie une data URI JPEG. Sert à
    normaliser la sortie de gpt-image-1 (qui ne sort qu'en 3:2) au format de la chaîne.
    Sans effet (renvoie '') si l'image est déjà ~16:9 (cas Nano Banana/FLUX) ou si échec :
    l'appelant garde alors l'URL d'origine. La data URI marche pour la publication YouTube
    (urllib gère data:) ET l'affichage <img> dans Delamain."""
    if Image is None or not url or url.startswith("data:"):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = im.size
        target = 16 / 9
        if abs((w / h) - target) < 0.03:
            return ""   # déjà ~16:9 → rien à faire
        if (w / h) > target:                 # trop large → on rogne les côtés
            nw = int(round(h * target)); x = (w - nw) // 2
            im = im.crop((x, 0, x + nw, h))
        else:                                # trop haut (cas gpt 3:2) → on rogne haut/bas
            nh = int(round(w / target)); y = (h - nh) // 2
            im = im.crop((0, y, w, y + nh))
        im = im.resize((1280, 720), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _fal_image_safe(model, payload, key, logo_brand=""):
    """Comme _fal_image, MAIS si Nano Banana REFUSE par modération (persos type enfants —
    South Park, Family Guy…), bascule AUTOMATIQUEMENT sur un autre modèle SANS ce filtre :
      1) **gpt-image-1** (edit) : accepte ces persos ET reproduit fidèlement le PIXEL ART de
         la chaîne (perso pixel + « POUR S'ENDORMIR » + bon logo). Vérifié en vrai. Sort en
         3:2 → l'appelant recadre en 16:9 (_to_16x9_datauri).
      2) sinon **FLUX Kontext** (1 image) : garde le texte/le style mais perso plus lisse.
    → ces franchises se génèrent toutes seules comme les autres, sans intervention.
    `logo_brand` (cas réf d'une AUTRE licence, sans image-logo) : on dicte le bon logo en texte."""
    global _LAST_FAL_FALLBACK
    _LAST_FAL_FALLBACK = False
    url = _fal_image(model, payload, key)
    if url or not _LAST_FAL_FLAGGED:
        return url
    _LAST_FAL_FALLBACK = True
    imgs = payload.get("image_urls") or []
    prompt = payload.get("prompt", "")
    if logo_brand:
        prompt += (" The franchise logo must read \"" + logo_brand + "\": replace any other "
                   "franchise logo with a clean \"" + logo_brand + "\" logo in the same spot.")
    if imgs:
        u = _fal_image("fal-ai/gpt-image-1/edit-image",
                       {"prompt": prompt, "image_urls": [imgs[0]], "image_size": "1536x1024"}, key)
        if u:
            return u
        return _fal_image("fal-ai/flux-pro/kontext", {"prompt": prompt, "image_url": imgs[0]}, key)
    u = _fal_image("fal-ai/gpt-image-1", {"prompt": prompt, "image_size": "1536x1024"}, key)
    return u or _fal_image("fal-ai/flux/dev",
                           {"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1}, key)


def _thumb_issues(gen_url, brand="", topic="", ref_url="", brief="", headline=""):
    """CONTRÔLE QUALITÉ vision de TOUTE la miniature générée. Si une RÉF de la chaîne est
    fournie, COMPARE le style/format à cette réf. Renvoie '' si rien à corriger, sinon UNE
    phrase décrivant les défauts (texte mal orthographié — ex. « DORMIRE » —, mauvais logo,
    style qui ne colle pas à la réf, artefacts). Renvoie **None** si le contrôle n'a PAS pu
    s'exécuter (vision indispo/erreur) → l'appelant NE doit PAS confondre ça avec « OK » et ne
    pose jamais une miniature non vérifiée. UNIVERSEL : aucune langue ni licence codée en dur
    (brand + sujet déduits par Claude en amont) → marche pour toute chaîne/thème.

    `brief` = consignes du propriétaire (dont la RÈGLE de texte de la miniature). Sans ça, le QA
    ne vérifiait QUE l'orthographe → une miniature au texte BIEN orthographié mais NON CONFORME
    (ex. « 100 ANECDOTES SUR ZELDA » alors que la règle dit « seulement POUR S'ENDORMIR »)
    passait pour « OK ». Avec le brief, le QA signale ce texte en trop → boucle de correction."""
    if not gen_url:
        return ""
    ctx = (" Sujet de la vidéo : « " + topic[:90] + " ».") if topic else ""
    if headline:
        ctx += (" RÈGLE ABSOLUE : le GROS titre de la miniature doit être EXACTEMENT « " + headline +
                " » et RIEN d'autre. S'il y a le MOINDRE autre texte écrit sur l'image en plus de ce "
                "titre et du logo (un nombre, « 100 anecdotes », un autre mot/phrase, un titre en plus), "
                "c'est un DÉFAUT à signaler, MÊME parfaitement orthographié. Le logo-image de la licence "
                "est autorisé (ce n'est pas du texte en trop).")
    if brief:
        ctx += (" RÈGLE du propriétaire pour le TEXTE de la miniature (lis la partie qui concerne la "
                "MINIATURE) : « " + brief[:600] + " ». Le gros titre doit respecter cette règle À LA "
                "LETTRE : tout texte EN TROP dans la zone de titre (autre phrase, nombre, ou nom de "
                "licence ÉCRIT en texte — le LOGO image de la licence, lui, reste autorisé) est un "
                "DÉFAUT à signaler, MÊME s'il est bien orthographié.")
    logo_q = ((" - le logo de licence est bien celui de « " + brand + " » (pas une autre licence) ;")
              if brand else "")
    base = _cfg("LLM_BASE").rstrip("/"); lkey = _cfg("LLM_KEY")
    if not base or not lkey:
        return None   # pas de vision configurée → IMPOSSIBLE de vérifier (≠ « tout est OK »)
    if ref_url:
        intro = ("Image 1 = une miniature qu'on vient de GÉNÉRER. Image 2 = une miniature de RÉFÉRENCE "
                 "de la MÊME chaîne YouTube (le style et le format à respecter)." + ctx + " Vérifie l'image 1 : "
                 "- garde-t-elle le MÊME style graphique, la même mise en page et le même format que la réf ?"
                 + logo_q + " - tout le texte est-il correctement orthographié dans sa langue (aucune lettre "
                 "en trop/manquante, aucun mot inventé/charabia) ? - aucun artefact grossier ? "
                 "Si TOUT est parfait, réponds EXACTEMENT « OK ». Sinon, en UNE phrase, dis ce qui ne va pas.")
        content = [{"type": "text", "text": intro},
                   {"type": "image_url", "image_url": {"url": gen_url}},
                   {"type": "image_url", "image_url": {"url": ref_url}}]
    else:
        intro = ("Contrôle qualité de cette miniature YouTube." + ctx + " Vérifie : - tout le texte est-il "
                 "correctement orthographié dans sa langue (aucune lettre en trop/manquante, aucun mot "
                 "inventé/charabia) ?" + logo_q + " - aucun artefact grossier ? Si TOUT est parfait, réponds "
                 "EXACTEMENT « OK ». Sinon, en UNE phrase, dis ce qui ne va pas et comment le corriger.")
        content = [{"type": "text", "text": intro},
                   {"type": "image_url", "image_url": {"url": gen_url}}]
    body = {"model": "claude-sonnet-4-6", "max_tokens": 120, "messages": [{"role": "user", "content": content}]}
    # On RÉESSAIE l'appel vision sur erreur passagère (proxy en rate-limit 429, timeout…)
    # avant d'abandonner : un échec du contrôle ne doit JAMAIS être pris pour « OK ».
    for _try in range(3):
        try:
            req = urllib.request.Request(base + "/chat/completions",
                                         data=json.dumps(body).encode("utf-8"), method="POST")
            req.add_header("Authorization", "Bearer " + lkey)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=90) as r:
                ans = json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
            return "" if ans[:2].upper() == "OK" else ans
        except Exception:
            time.sleep(2)
    return None   # n'a PAS pu vérifier après plusieurs essais → l'appelant ne fait pas confiance


def _compose_prompt(ref_url, subject, topic, brand="", matched=False, has_logo=False, brief=""):
    """UNIVERSEL : Claude REGARDE la miniature de réf de la chaîne (vision) et RÉDIGE
    lui-même la consigne d'édition d'image, dans le STYLE EXACT de cette chaîne (ambiance,
    pose, mise en page, headline, palette, place du logo). → plus AUCUNE hypothèse codée
    (« sleepy », « français », « franchise »…) : marche pour n'importe quelle chaîne/thème.
    Renvoie la consigne (anglais, pour Fal) ou '' si échec (→ l'appelant a un repli codé)."""
    if not ref_url or not subject:
        return ""
    base = _cfg("LLM_BASE").rstrip("/"); lkey = _cfg("LLM_KEY")
    if not base or not lkey:
        return ""
    if matched:
        if brief:
            # Le brief du boss peut prescrire un texte fixe (ex. "POUR S'ENDORMIR") — il prime
            # sur le texte de la réf. On garde le logo de la réf (sûr), MAIS on ERASE le vieux
            # titre de la réf (sinon le modèle le recopie : « 100 ANECDOTES SUR ZELDA ») et on
            # ne garde que le headline demandé par le propriétaire.
            logo_rule = ("Keep the franchise logo EXACTLY as in the reference (same position, "
                         "size and style). The reference shows OLD title text — you MUST erase ALL "
                         "of that old title text completely. Write ONLY the headline required by the "
                         "channel owner's instructions below (and nothing else): no extra words, no "
                         "number, no franchise name spelled out in the title area.")
        else:
            logo_rule = ("Keep the title text AND the franchise logo EXACTLY as in the reference "
                         "(change no text and no logo) — only the main character changes.")
    elif has_logo:
        logo_rule = ('A second image is provided: the official "' + brand + '" logo. Put THAT logo '
                     "(from image 2) where the reference's franchise logo sits, same spot and size, "
                     "and remove every trace of the reference's original franchise.")
    elif brand:
        logo_rule = ('Replace the reference\'s franchise logo with a clean logo whose text reads only "'
                     + brand + '".')
    else:
        logo_rule = "Remove the franchise logo; keep only the headline text."
    ask = ("Voici une miniature de RÉFÉRENCE d'une chaîne YouTube (le style EXACT à respecter). On veut "
           "une NOUVELLE miniature pour la MÊME chaîne. Sujet à représenter : « " + subject + " »"
           + ((" (vidéo : « " + topic + " »)") if topic else "") + ". Analyse la réf : style graphique, "
           "mise en page, le gros texte/headline fixe, la palette, l'AMBIANCE et la pose typiques du "
           "personnage, l'emplacement du logo. Puis RÉDIGE UNE seule consigne d'édition d'image, EN "
           "ANGLAIS, pour un modèle d'image, qui : garde le style, la mise en page, la palette et le "
           "headline EXACTEMENT comme la réf ; remplace le personnage principal par « " + subject + " » "
           "représenté dans la MÊME ambiance/pose que le perso de la réf ; " + logo_rule + " rend une "
           "image 16:9 plein cadre, sans bordure ni bande noire."
           " IMPORTANT : la consigne ne doit JAMAIS faire écrire le titre de la vidéo ni aucun mot/chiffre "
           "supplémentaire sur l'image — le gros texte reste EXACTEMENT celui de la réf, rien d'autre."
           + (("\nConsignes du propriétaire de la chaîne — applique CELLES qui concernent la miniature "
               "(style, couleurs, expression, texte/headline, ce qu'il faut montrer ou éviter), ignore "
               "le reste : « " + brief + " ».") if brief else "")
           + " Réponds UNIQUEMENT par la consigne d'édition en anglais, rien d'autre.")
    content = [{"type": "text", "text": ask}, {"type": "image_url", "image_url": {"url": ref_url}}]
    body = {"model": "claude-sonnet-4-6", "max_tokens": 320, "messages": [{"role": "user", "content": content}]}
    try:
        req = urllib.request.Request(base + "/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Authorization", "Bearer " + lkey)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
        return out if len(out) > 20 else ""
    except Exception:
        return ""


def _set_thumb_progress(entry_id, val):
    """Écrit l'avancement de la miniature (colonne thumb_progress) — lu en live par
    le frontend (polling) pour afficher « 🎬 NN% ». Écriture courte (transaction brève)
    → visible par les autres requêtes/process pendant que la génération tourne."""
    try:
        plan_update(entry_id, {"thumb_progress": str(val)})
    except Exception:
        pass


# Cache (durée du process) du GROS titre fixe d'une chaîne, par project_id.
_HEADLINE_CACHE = {}


def _canonical_headline(vids, project_id=None):
    """GROS titre IDENTIQUE qui revient sur (presque) toutes les miniatures de la chaîne
    (ex. « POUR S'ENDORMIR »). C'est LE texte autorisé sur la miniature → sert à RECADRER
    le QA : tout autre texte (un nombre, « 100 anecdotes », un titre en plus) = DÉFAUT, même
    bien orthographié. Sans ça, le QA ne comparait qu'à UNE réf qui pouvait être pourrie →
    il laissait passer. Vision sur plusieurs miniatures (le commun = le vrai titre, les
    pollutions varient donc ne sont PAS communes). '' si indétectable. Mis en cache."""
    if project_id is not None and project_id in _HEADLINE_CACHE:
        return _HEADLINE_CACHE[project_id]
    thumbs = [v["thumb"] for v in (vids or []) if v.get("thumb")][:5]
    base = _cfg("LLM_BASE").rstrip("/"); lkey = _cfg("LLM_KEY")
    if len(thumbs) < 2 or not base or not lkey:
        return ""
    content = [{"type": "text", "text":
                "Voici plusieurs miniatures de la MÊME chaîne YouTube. Quel est le GROS titre qui "
                "apparaît IDENTIQUE (mot pour mot) sur TOUTES ? Réponds UNIQUEMENT par ce texte exact, "
                "rien d'autre, ou « aucun » s'il n'y a pas de gros titre commun à toutes."}]
    for t in thumbs:
        content.append({"type": "image_url", "image_url": {"url": t}})
    body = {"model": "claude-sonnet-4-6", "max_tokens": 30,
            "messages": [{"role": "user", "content": content}]}
    try:
        req = urllib.request.Request(base + "/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Authorization", "Bearer " + lkey)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=90) as r:
            ans = json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
        ans = ans.splitlines()[0].strip().strip('".«»').strip()
    except Exception:
        return ""
    if ans.lower() in ("aucun", "none", ""):
        ans = ""
    if project_id is not None:
        _HEADLINE_CACHE[project_id] = ans
    return ans


def _gen_thumbnail(entry, vids, franchise=""):
    """Miniature via Fal (Nano Banana). Renvoie True si une miniature a bien été
    posée (thumbnail_url mis à jour), False sinon (Fal injoignable). Écrit aussi
    l'avancement (%) dans thumb_progress au fil des étapes pour l'affichage live.

    LA CLÉ, c'est bien choisir la RÉFÉRENCE :
    on prend une ancienne miniature de la chaîne du MÊME thème/licence (son logo
    est déjà le bon) → le modèle n'a plus qu'à remplacer le PERSONNAGE, ce qu'il
    fait très bien. Avant on prenait la dernière vidéo (souvent une autre
    licence) → il devait réécrire un logo stylisé = impossible (« POKÉMON
    L'ÉPONGE »). Prompt simple et universel : « change juste le perso, ne touche à
    aucun texte ni logo ». Vérifié en vrai avec FAL sur la chaîne @LeGrandRecap."""
    key = _cfg("FAL_KEY")
    if not key:
        return False
    _set_thumb_progress(entry["id"], 5)
    subject = _subject_for_thumb(entry)
    # NB : on n'injecte PAS les consignes de la chaîne (brief) dans la miniature. Elles
    # contiennent le format du TITRE (« 100 anecdotes sur X pour s'endormir ») et le modèle
    # d'image les RECOPIAIT sur la miniature (régression). La miniature COPIE la réf de la
    # chaîne (texte + logo) et ne change QUE le personnage — l'approche qui marchait. Le brief
    # ne pilote que le TITRE/desc (cf. _gen_metadata).
    ref, matched = _pick_reference(vids, entry)
    # Trace de diagnostic (visible dans le journal) : combien de vidéos de la chaîne on a
    # regardées, et quelle réf on copie. Si matched=False, c'est qu'AUCUNE vidéo de la même
    # licence n'a été trouvée parmi les candidats → on tombe dans l'adaptation (moins fiable) ;
    # le fix = regarder PLUS de vidéos (n=50) pour toujours retrouver la bonne licence.
    _log("ok", "thumb_ref",
         "Miniature : %d vidéos chaîne vues, réf %s (%s)"
         % (len(vids or []), ("même licence ✓" if matched else "AUCUNE même licence → adaptation"),
            (ref[:120] if ref else "aucune")),
         entry)
    topic = (entry.get("topic") or entry.get("title") or "").strip()[:120]
    fr_id = (franchise or entry.get("franchise") or "").strip().lower()
    # Nom de licence pour l'auto-validation du logo : les 12 gérées (fiable) SINON déduit
    # par Claude → UNIVERSEL (marche pour une chaîne/thème totalement différent).
    brand_check = _FR_NAMES.get(fr_id) or _brand_for_thumb(entry)
    # GROS titre fixe de la chaîne (ex. « POUR S'ENDORMIR ») : on l'IMPOSE au modèle ET on le
    # fait CONTRÔLER par le QA → plus aucun texte en trop (« 100 anecdotes ») MÊME si la réf
    # copiée est elle-même polluée. C'est ça la vraie « double-vérif » qui manquait.
    headline = _canonical_headline(vids, entry.get("project_id"))
    head_clause = ((" The big headline text must read EXACTLY \"" + headline + "\" and nothing else — "
                    "keep ONLY that as the large title; do NOT add any other text, number, extra line "
                    "or the video title anywhere on the image.") if headline else "")
    _log("ok", "thumb_head",
         "Titre fixe imposé à la miniature : « " + (headline or "(aucun détecté)") + " »", entry)
    # Description du PERSO à dessiner. Si le sujet est GÉNÉRIQUE (= juste le nom de la licence,
    # ex. « Pokémon », sans perso précis dans le titre), on exige un perso DIFFÉRENT de celui de
    # la réf — sinon le modèle garde le perso existant et reproduit la même miniature.
    fr_name = _FR_NAMES.get(fr_id) or ""
    _generic_subj = bool(subject) and (_norm(subject) in (_norm(fr_name), _norm(fr_id))
                                       or _norm(subject) in ("", "this video"))
    char_desc = (("a well-known " + (fr_name or brand_check or "") + " character that is CLEARLY "
                  "DIFFERENT from the one currently in the image — never keep the same character")
                 if _generic_subj else
                 (subject + " (it must be CLEARLY DIFFERENT from the character currently shown)"))
    logo_url = ""                            # logo officiel fourni en image 2 si on doit le remplacer
    if ref:
        # RÈGLE SIMPLE (exigée par le boss) : on prend la FORME d'une miniature existante de la
        # chaîne et on ne change QUE 2 choses — le PERSO et le LOGO. Le gros texte
        # « POUR S'ENDORMIR », la mise en page, le fond, le nuage et le style restent IDENTIQUES.
        # On ne « reconstruit » plus rien à partir de zéro (c'est ça qui mangeait le texte).
        use_edit = True
        if matched:
            # Même licence → le logo est déjà le bon : on ne touche QUE le personnage.
            ref_imgs = [ref]
            prompt = ("Edit this thumbnail. Keep EVERYTHING exactly as it is — art style, layout, "
                      "background, cloud, the franchise logo, and ALL text (especially the big "
                      "headline) — do NOT add, remove or change any text or the logo. Change ONLY ONE "
                      "thing: replace the sleeping character with " + char_desc + ", sleeping in the same "
                      "pose, same spot and the same art style. "
                      "Full 16:9 image, edge to edge, no borders, no black bars." + head_clause)
        else:
            # Autre licence → on remplace le logo par le VRAI logo (embarqué pour les 12 ; sinon
            # SerpAPI) et on change le perso. RIEN d'autre ne bouge (surtout pas le texte).
            logo_url = _bundled_logo(fr_id) or (_find_real_logo(brand_check) if brand_check else "")
            if logo_url:
                ref_imgs = [ref, logo_url]
                prompt = ("Image 1 is a thumbnail to edit. Image 2 is a logo. Keep image 1 EXACTLY as "
                          "it is — art style, layout, background, cloud, and ALL its text (especially "
                          "the big headline) — do NOT add, remove or change any text. Change ONLY TWO "
                          "things: (1) replace the sleeping character with " + char_desc + " (same "
                          "sleeping pose, same spot, same art style); (2) replace the franchise logo "
                          "with the logo from image 2, same spot and similar size, keeping its real "
                          "colors. Touch nothing else. Full 16:9 image, edge to edge, no borders." + head_clause)
            else:
                # Pas de logo dispo → on garde celui de la réf et on change juste le perso
                # (mieux qu'un logo redessiné qui part en charabia).
                ref_imgs = [ref]
                prompt = ("Edit this thumbnail. Keep EVERYTHING exactly as it is — art style, layout, "
                          "background, cloud, logo and ALL text (especially the big headline) — do NOT "
                          "add, remove or change any text or logo. Change ONLY the sleeping character: "
                          "replace it with " + char_desc + ", same pose, same spot, same art style. "
                          "Full 16:9 image, edge to edge, no borders, no black bars." + head_clause)
    else:
        # Aucune réf du tout (chaîne sans AUCUNE miniature) → génération simple de zéro.
        use_edit = False
        ref_imgs = []
        logo_clause = ('The franchise logo must read "' + brand_check + '". ' if brand_check else "")
        prompt = ("A 16:9 YouTube thumbnail featuring " + subject + ". "
                  + logo_clause + "Bold readable title, clean background, no borders." + head_clause)
    model = "fal-ai/nano-banana-2/edit" if use_edit else "fal-ai/nano-banana-2"
    payload = {"prompt": prompt, "num_images": 1, "aspect_ratio": "16:9"}
    if use_edit:
        payload["image_urls"] = ref_imgs
    _set_thumb_progress(entry["id"], 15)   # prompt prêt → on attaque la génération
    # AUTO-QA + AUTO-CORRECTION : on génère, puis la vision analyse TOUTE la miniature
    # (orthographe du texte — ex. « DORMIRE » —, bon logo de licence, artefacts). Si un
    # défaut est repéré, on RE-PROMPTE pour ÉDITER l'image et corriger précisément ce
    # défaut (jusqu'à 4 essais). → Delamain ne publie jamais une miniature fautive sans
    # intervention manuelle. (Le titre est ce qui résiste le plus aux modèles d'image,
    # mais l'itération guidée par la vision converge.)
    # % indicatif par étape (génération Fal puis contrôle qualité vision).
    _GEN_PCT = (25, 50, 70, 85)
    _QA_PCT = (45, 65, 80, 92)
    best = last_url = ""
    issues = ""            # défaut PRÉCIS repéré par le QA (à corriger par édition)
    verified = ""          # image CONFIRMÉE propre par le contrôle qualité vision
    qa_ran = False         # le QA vision a-t-il pu s'exécuter au moins une fois ?
    for attempt in range(4):
        _set_thumb_progress(entry["id"], _GEN_PCT[attempt])
        if attempt == 0 or not issues:
            # 1er essai, OU pas de défaut précis à corriger (QA indispo au tour précédent)
            # → on (re)génère de zéro plutôt que d'« éditer » dans le vide.
            # logo_brand : si la réf est d'une AUTRE licence (matched=False), FLUX doit refaire
            # le bon logo en texte (il ne reçoit pas l'image-logo en 1-image). Si matched, le logo
            # de la réf est déjà bon → on n'y touche pas.
            url = _fal_image_safe(model, payload, key,
                                  logo_brand=(brand_check if (ref and not matched) else ""))
        else:
            # Édite l'image précédente pour corriger UNIQUEMENT les défauts repérés.
            imgs = [last_url] + ([logo_url] if logo_url else [])
            logo_fix = (('The franchise logo must be the official "' + brand_check + '" logo'
                         + (' shown in image 2' if logo_url else '') + ' — replace any wrong logo. ')
                        if brand_check else "")
            fixp = ("Edit this thumbnail to FIX ONLY these problems: " + issues + ". "
                    "Rewrite any misspelled or garbled text as correct, properly-spelled words "
                    "in the SAME language as the original text. "
                    "If the problem is UNWANTED or EXTRA title text (extra words, a number, or a "
                    "franchise name written in the title area), DELETE those words ENTIRELY so they "
                    "are completely gone — do NOT just shrink or move them — and keep only the title "
                    "text that the instructions allow; repaint the freed space to match the background. "
                    + logo_fix +
                    "Keep the art style, character, layout, background and colors identical. "
                    "Full 16:9 image, edge to edge, no borders, no black bars.")
            url = _fal_image_safe("fal-ai/nano-banana-2/edit",
                                  {"prompt": fixp, "num_images": 1, "aspect_ratio": "16:9",
                                   "image_urls": imgs}, key)
        used_fallback = _LAST_FAL_FALLBACK
        if used_fallback:
            _log("ok", "thumb_fallback",
                 "Nano Banana a refusé (modération) → bascule sur le modèle de repli (gpt-image-1) "
                 "pour cette miniature", entry)
        if not url:
            continue
        best = last_url = url
        _set_thumb_progress(entry["id"], _QA_PCT[attempt])
        # QA : compare AUSSI à la réf de la chaîne (style/format) quand il y en a une (le logo est
        # vérifié contre <brand>, jamais contre le logo de la réf). Sur le modèle de repli (gpt,
        # 3:2 avant recadrage), on NE passe PAS la réf → pas de faux positif sur le format.
        chk = _thumb_issues(url, brand_check, topic, ("" if used_fallback else ref), headline=headline)
        if chk is None:
            # Le contrôle n'a PAS pu tourner (vision indispo) → on ne fait AUCUNE confiance
            # à cette image. Pas de défaut précis → on régénère de zéro au tour suivant.
            issues = ""
            continue
        qa_ran = True
        issues = chk
        if issues == "":          # confirmé propre par la vision
            verified = url
            break
    # On ne pose QUE ce qui a été VÉRIFIÉ propre. Sinon, si le QA a au moins tourné mais
    # voit encore un défaut mineur après 4 essais, on garde la meilleure (mieux qu'un blocage).
    # Si le QA n'a JAMAIS pu vérifier (panne vision) → on NE pose RIEN : return False →
    # réessai au tick suivant (et au pire _ensure_assets_ready bascule après 5 échecs sur la
    # miniature auto YouTube — JAMAIS sur une image non contrôlée).
    final = verified or (best if qa_ran else "")
    if final:
        # gpt-image-1 (repli SP/FG) sort en 3:2 → on recadre au format 16:9 de la chaîne (data URI).
        # Sans effet si l'image est déjà 16:9 (Nano Banana / FLUX) → on garde l'URL telle quelle.
        fixed = _to_16x9_datauri(final)
        if fixed:
            final = fixed
        # thumbnail_url AVANT de vider la progress → un poll voit toujours soit « en cours »,
        # soit « fini avec image », jamais un trou.
        plan_update(entry["id"], {"thumbnail_url": final, "thumb_progress": ""})
        return True
    return False


# ── Étapes ───────────────────────────────────────────────────────────────────

def _resolve_franchise(entry):
    """Franchise de la fiche, ou déduite du sujet par le LLM si absente.
    Renvoie un id valide, ou '' si aucune des 12 franchises gérées ne colle.
    Mémorise le résultat sur la fiche pour ne pas reclasser à chaque tick."""
    fr = (entry.get("franchise") or "").strip().lower()
    if fr in _FR_IDS:
        return fr
    subject = (entry.get("topic") or entry.get("title") or "").strip()
    if not subject:
        return ""
    prompt = ("Classe ce sujet de vidéo YouTube dans UNE seule franchise parmi cette liste "
              "(réponds UNIQUEMENT par l'identifiant exact, ou 'none' si aucune ne colle) :\n"
              + ", ".join(sorted(_FR_IDS)) + "\n\nSujet : " + subject)
    try:
        ans = re.sub(r"[^a-z]", "", (_llm(prompt, max_tokens=12) or "").strip().lower())
    except Exception:
        return ""
    if ans in _FR_IDS:
        plan_update(entry["id"], {"franchise": ans})
        return ans
    return ""


def _duration_from_text(text):
    """Minutes demandées détectées dans un titre : '1h30'→90, '2h'→120, '2 heures'→120,
    '45 min'→45. 0 si rien (→ l'atelier prend le mode 'liste de 100 faits' ≈ 1h).
    Sert à RESPECTER la durée écrite dans le sujet (« 1h30 de Secrets… »)."""
    t = (text or "").lower()
    m = re.search(r"(?<!\d)(\d{1,2})h(\d{1,2})?(?!\d)", t)          # 2h, 2h30, 1h
    if m:
        h = int(m.group(1)); mm = int(m.group(2) or 0)
        if 1 <= h <= 12 and mm < 60:
            return h * 60 + mm
    m = re.search(r"(?<!\d)(\d{1,2})\s*heures?\b", t)               # 2 heures
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(1)) * 60
    m = re.search(r"(?<!\d)(\d{1,3})\s*(?:min|minutes?|mn)\b", t)   # 45 min
    if m and 5 <= int(m.group(1)) <= 600:
        return int(m.group(1))
    return 0


def _start_render(proj, entry):
    """scheduled -> rendering : on ne fait QUE lancer le rendu ici (appel LÉGER,
    quelques secondes). Titre/desc + miniature sont préparés ENSUITE, pendant que
    la vidéo se rend (cf. _prepare_assets), pour que ce tick reste RAPIDE → la
    fiche passe à 🎬 tout de suite et la boucle navigateur ne se fige jamais
    (avant, ce tick durait 2-4 min — LLM + Fal — et donnait l'impression d'être
    bloqué, obligeant à relancer à la main). Si l'atelier est INJOIGNABLE, l'appel
    /render échoue ici et on n'a rien gaspillé (ni Fal ni LLM)."""
    eng = _engine(proj)
    subject = (entry.get("topic") or entry.get("title") or "").strip()
    # FILET ANTI-GÂCHIS : si la fiche porte DÉJÀ un job de rendu (ex. on a cliqué ▶
    # sur une vidéo en cours, ou le statut a été remis à 'scheduled'), on NE relance
    # PAS un rendu neuf — on REPREND le job existant. Sinon on abandonne une vidéo
    # déjà rendue (et on repaie un rendu). On ne lance un rendu neuf que si le job a
    # disparu (404) ou a échoué.
    existing = (entry.get("render_job") or "").strip()
    if existing:
        try:
            st = _eng_call(eng, "/jobs/" + urllib.parse.quote(existing), timeout=20)
            s = st.get("status")
            if s and s != "failed":
                tries = _render_tries(entry.get("notes"))
                base = "__queued" if s == "queued" else "__running"
                plan_update(entry["id"], {"status": "rendering",
                                          "notes": base + ((":" + str(tries)) if tries else "")})
                # 'done' : la reprise repasse en 'rendering' → le prochain tick voit
                # 'done' et publie (chemin de publication normal, miniature comprise).
                return {"action": "render_resumed", "id": entry["id"],
                        "job": existing, "status": s}
        except urllib.error.HTTPError as e:
            if e.code != 404:   # 404 = job perdu → on enchaîne sur un rendu neuf
                raise
        except Exception:
            pass   # atelier injoignable : on tente quand même un rendu neuf ci-dessous
    if not _engine_configured(eng):
        return {"action": "render_start_failed", "id": entry["id"],
                "detail": "atelier « " + eng["kind"] + " » non configuré (.env)"}
    if eng["kind"] == "remotion":
        # Remotion : la niche est fixée par la chaîne (video_tool=remotion:<niche>), pas
        # de franchise à deviner. Le titre = le sujet de la fiche.
        body = _render_body(eng, entry)
    else:
        # Lore : on déduit la franchise du sujet (ou on écarte la fiche proprement).
        fr = _resolve_franchise(entry)
        if not fr:
            plan_update(entry["id"], {"status": "failed",
                                      "notes": "aucune franchise gérée ne correspond à ce sujet"})
            _log("warn", "no_franchise", "Sujet écarté (aucun univers géré ne correspond) : « "
                 + subject + " »", entry)
            return {"action": "no_franchise", "id": entry["id"], "topic": subject}
        body = {"title": subject, "franchise": fr, "lang": eng.get("lang", "fr")}
        # Durée demandée → mode 'durée cible' ; sinon défaut 'liste de 100 faits'.
        mins = _entry_minutes(entry)
        if mins > 0:
            body["duration"] = mins
            body["mpb"] = 0.6
        else:
            body["facts"] = 100
            body["spf"] = 35
        if fr in _FR_SERIES:
            body["clip"] = True
    data = _eng_call(eng, eng.get("render_path", "/render"), method="POST", body=body, timeout=30)
    job = data.get("jobId") or data.get("id")
    if not job:
        # Atelier injoignable / refus : on NE génère RIEN (pas de gâchis), on réessaiera.
        return {"action": "render_start_failed", "id": entry["id"], "detail": data}
    tries = _render_tries(entry.get("notes"))   # conserve le compteur de relances auto
    mark = "__queued" + ((":" + str(tries)) if tries else "")
    plan_update(entry["id"], {"status": "rendering", "render_job": str(job), "notes": mark})
    _tag = eng.get("gametype") or eng["niche"]
    via = (eng["kind"] + (":" + _tag if _tag else "") + (" short" if eng.get("short") else ""))
    _log("ok", "render_started", "Rendu lancé (" + via + ") : « " + subject + " »"
         + ((" (tentative " + str(tries + 1) + ")") if tries else ""), entry)
    return {"action": "render_started", "id": entry["id"], "job": job, "title": subject}


def _prepare_assets(proj, entry):
    """Pendant le rendu : prépare titre/desc PUIS miniature, UNE chose par appel
    (chaque tick reste borné → la boucle défile sans à-coups). Renvoie ce qui a
    été fait ('metadata'/'thumbnail') ou None si tout est déjà prêt.
    Filet de sécurité : à la publication, _publish a de toute façon des valeurs de
    repli (titre = sujet, pas de miniature custom) si rien n'a encore été généré."""
    if not (entry.get("title") or "").strip():
        _gen_metadata(entry, _channel_videos(proj, 50))
        return "metadata"
    if not (entry.get("thumbnail_url") or "").strip():
        fr = (entry.get("franchise") or "").strip().lower()
        _gen_thumbnail(entry, _channel_videos(proj, 50), fr)
        return "thumbnail"
    return None


def _pubfail_count(prog):
    """Compteur d'échecs de génération de miniature AU MOMENT DE PUBLIER
    (marqueur thumb_progress 'pubfail:N'). 0 si absent."""
    m = re.search(r"pubfail:(\d+)", str(prog or ""))
    return int(m.group(1)) if m else 0


def _ensure_assets_ready(proj, entry):
    """DOUBLE CHECK avant publication : garantit que titre/description ET miniature
    sont prêts. Génère ce qui manque — les DEUX si besoin, dans le MÊME appel. (Avant,
    on n'en préparait qu'UN par tick : si le rendu finissait avant le tick « miniature »,
    la vidéo partait SANS miniature. C'est le bug qu'on corrige ici.)

    Renvoie (ready, entry_frais) :
      ready=True  → publication autorisée (miniature présente — ou, en dernier recours
                    après {_MAX_THUMB_PUBFAIL} échecs si Fal reste injoignable, on poste
                    quand même et on marque thumb_progress='redo' pour la refaire d'un clic,
                    plutôt que de bloquer la file indéfiniment).
      ready=False → miniature pas encore prête (Fal vient d'échouer) → NE PAS publier ce
                    tick ; on retentera tout seul au tick suivant (~1 min)."""
    if not (entry.get("title") or "").strip():
        try:
            _gen_metadata(entry, _channel_videos(proj, 50))
        except Exception:
            pass
        entry = plan_get(entry["id"]) or entry
    if (entry.get("thumbnail_url") or "").strip():
        return True, entry
    fails = _pubfail_count(entry.get("thumb_progress"))
    try:
        ok = _gen_thumbnail(entry, _channel_videos(proj, 50),
                            (entry.get("franchise") or "").strip().lower())
    except Exception:
        ok = False
    entry = plan_get(entry["id"]) or entry
    if ok and (entry.get("thumbnail_url") or "").strip():
        return True, entry
    fails += 1
    if fails >= _MAX_THUMB_PUBFAIL:
        # Fal injoignable depuis trop longtemps : on publie SANS miniature custom (la
        # vidéo en ligne vaut mieux qu'une vidéo bloquée) et on signale 'redo' → le boss
        # la refait d'un clic (re-roll, qui pousse aussi la miniature sur YouTube).
        _set_thumb_progress(entry["id"], "redo")
        return True, plan_get(entry["id"]) or entry
    _set_thumb_progress(entry["id"], "pubfail:" + str(fails))
    return False, entry


def _supervise_release(proj, entry):
    """SUPERVISION CLAUDE du contenu, juste avant publication. Claude relit titre +
    description par rapport au sujet : titre cohérent, dans la bonne langue, accrocheur,
    sans charabia ni erreur ? S'il détecte un souci, on REGÉNÈRE le titre/desc UNE fois
    (auto-correction), puis on publie quand même. → JAMAIS bloquant (fail-open total :
    si l'IA est indisponible OU si après correction c'est encore imparfait, on poste —
    un titre perfectible vaut mieux qu'une chaîne figée 3 mois). Renvoie la fiche fraîche."""
    title = (entry.get("title") or "").strip()
    topic = (entry.get("topic") or "").strip()
    if not title or not topic:
        return entry
    prompt = ("Tu supervises la publication d'une vidéo YouTube. Sujet : « " + topic + " ». "
              "Titre proposé : « " + title + " ». "
              "Le titre est-il un vrai titre de vidéo, cohérent avec le sujet, dans la même "
              "langue que le sujet, accrocheur, SANS faute grossière ni charabia ni texte "
              "tronqué ? Réponds EXACTEMENT « OK » si c'est bon à publier, sinon réponds en "
              "UNE phrase ce qui cloche.")
    try:
        verdict = (_llm(prompt, max_tokens=80) or "").strip()
    except Exception:
        return entry   # superviseur indisponible → on ne bloque pas
    if not verdict or verdict[:2].upper() == "OK":
        _log("ok", "supervision", "Contrôle Claude avant publication : OK — « " + title + " »", entry)
        return entry
    # Claude a repéré un souci → on regénère titre/desc UNE fois puis on publie.
    _log("warn", "supervision", "Claude a repéré un souci sur le titre (" + verdict[:160]
         + ") → régénération", entry)
    try:
        _gen_metadata(entry, _channel_videos(proj, 50))
    except Exception:
        pass
    return plan_get(entry["id"]) or entry


def _release_check(proj, entry, job_status):
    """GO/NO-GO déterministe avant mise en ligne (garanties dures, sans LLM → fiables
    même si le superviseur est down). Renvoie (ok, raison, fatal) :
      ok=False, fatal=False → on ne publie pas MAINTENANT, on retentera (anomalie passagère) ;
      ok=False, fatal=True  → inutile de retenter (doublon) → la fiche est écartée proprement.
    Tout est fail-open quand l'info manque (jamais de blocage sur une donnée absente)."""
    title = (entry.get("title") or "").strip()
    if not title:
        return False, "titre manquant", False
    if not (entry.get("thumbnail_url") or "").strip():
        # 'redo' = _ensure_assets_ready a VOLONTAIREMENT renoncé à la miniature après
        # _MAX_THUMB_PUBFAIL échecs Fal (fail-open choisi : « ne jamais bloquer » → on
        # publie quand même avec la miniature auto YouTube, le marqueur 'redo' survit à
        # la publi → le boss la refait d'un clic). Tout autre état = minia pas encore
        # prête → on bloque et on retentera au tick suivant.
        if (entry.get("thumb_progress") or "").strip() != "redo":
            return False, "miniature manquante", False
    # Vidéo réellement produite : si l'atelier annonce une durée, elle doit être plausible.
    for k in ("duration", "seconds", "length"):
        v = job_status.get(k)
        try:
            if v is not None and float(v) > 0 and float(v) < 5:
                return False, "vidéo anormalement courte (" + str(v) + ")", False
        except (TypeError, ValueError):
            pass
    # Anti-doublon : même sujet DÉJÀ publié sur cette chaîne → ne pas re-poster.
    topic = (entry.get("topic") or title).strip().lower()
    if topic:
        for it in plan_list(proj["id"]):
            if (it.get("id") != entry.get("id") and it.get("status") == "posted"
                    and (it.get("topic") or it.get("title") or "").strip().lower() == topic):
                return False, "doublon — déjà publiée sur la chaîne", True
    return True, "", False


def _finalize_and_publish(proj, entry, job_status):
    """Chemin de publication UNIQUE partagé par les 3 déclencheurs (tick auto, priorité
    'rendu fini', bouton Publier). Enchaîne : double check des assets → supervision Claude
    du contenu → go/no-go déterministe → publication. Renvoie toujours un dict d'action."""
    ready, entry = _ensure_assets_ready(proj, entry)
    if not ready:
        _log("warn", "thumb_pending", "Miniature pas prête (atelier image indispo) — réessai auto", entry)
        return {"action": "thumb_pending", "id": entry["id"]}
    entry = _supervise_release(proj, entry)
    ok, reason, fatal = _release_check(proj, entry, job_status)
    if not ok:
        if fatal:
            plan_update(entry["id"], {"status": "failed", "notes": "non publiée : " + reason})
            _log("error", "duplicate", "Publication annulée : " + reason, entry)
            return {"action": "skipped_duplicate", "id": entry["id"], "reason": reason}
        _log("warn", "release_blocked", "Publication retardée : " + reason + " (réessai auto)", entry)
        return {"action": "release_blocked", "id": entry["id"], "reason": reason}
    return _publish(proj, entry, job_status)


def _publish(proj, entry, job_status):
    """rendering(done) -> posted : télécharge le MP4 du worker et le poste sur YouTube."""
    job = (entry.get("render_job") or "").strip()
    title = (entry.get("title") or job_status.get("title") or entry.get("topic") or "Vidéo")[:100]
    desc = entry.get("description") or job_status.get("description") or ""
    tags_src = entry.get("tags") or job_status.get("tags") or []
    if isinstance(tags_src, str):
        tags = [t.strip() for t in tags_src.split(",") if t.strip()][:30]
    else:
        tags = [str(t).strip() for t in tags_src if str(t).strip()][:30]
    thumb_url = (entry.get("thumbnail_url") or job_status.get("thumb")
                 or job_status.get("thumbnail") or job_status.get("thumb_url") or "")
    proxy = proj.get("proxy", "")

    access = _access_token(proj["yt_refresh_token"], proxy)
    if not access:
        return {"action": "publish_failed", "id": entry["id"], "detail": "auth google"}

    # Programmation native YouTube : si la date est future → upload PRIVÉ + publishAt
    # (YouTube rend la vidéo publique tout seul à la date). Sinon → public direct.
    pub_at = _rfc3339_future(entry.get("post_at"))
    status_obj = ({"privacyStatus": "private", "publishAt": pub_at}
                  if pub_at else {"privacyStatus": "public"})
    # OBLIGATOIRE : déclare la vidéo « PAS faite pour les enfants » à chaque upload
    # (sinon YouTube laisse la question sans réponse et bride la vidéo). = « Non ».
    status_obj["selfDeclaredMadeForKids"] = False
    meta = {"snippet": {"title": title, "description": desc, "tags": tags},
            "status": status_obj}
    # Récupère le MP4 sur l'atelier de CETTE chaîne (Lore ou Remotion, même endpoint
    # /jobs/<id>/video) et l'envoie à YouTube EN FLUX, sans jamais charger la vidéo entière
    # en RAM (1h ≈ plusieurs Go → sinon upload bloqué à 0% sur le mutualisé).
    eng = _engine(proj)
    src = urllib.request.Request(
        eng["base"] + "/jobs/" + urllib.parse.quote(job) + "/video", method="GET", headers=eng["headers"])
    op = _opener(proxy)
    res = _resumable_upload(op, access, meta, src)
    vid = res.get("id") or ""
    yurl = "https://www.youtube.com/watch?v=" + vid

    # Miniature (best-effort).
    if vid and thumb_url:
        try:
            with urllib.request.urlopen(thumb_url, timeout=60) as tr:
                tb = tr.read()
                tct = tr.headers.get("Content-Type", "image/jpeg")
            treq = urllib.request.Request(
                "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + vid,
                data=tb, method="POST")
            treq.add_header("Authorization", "Bearer " + access)
            treq.add_header("Content-Type", tct)
            with op.open(treq, timeout=120):
                pass
        except Exception:
            pass

    # Lore worker : une fois le MP4 uploadé sur YouTube, on libère l'entrée côté atelier
    # (le doc Lore Maxxing le recommande ; auto-purge 7 j sinon). Best-effort, lore seulement
    # (l'atelier Remotion n'expose pas DELETE).
    if vid and eng["kind"] == "lore":
        try:
            _eng_call(eng, "/jobs/" + urllib.parse.quote(job), method="DELETE", timeout=20)
        except Exception:
            pass

    # 'posted' = pris en charge (publié OU programmé sur YouTube → plus à produire).
    note = ("programmée pour " + (entry.get("post_at") or "")) if pub_at else "publiée"
    plan_update(entry["id"], {"status": "posted", "video_url": yurl, "notes": note})
    if pub_at:
        _log("ok", "scheduled", "Programmée le " + (entry.get("post_at") or "") + " : « "
             + title + " » " + yurl, entry)
    else:
        _log("ok", "published", "Publiée : « " + title + " » " + yurl, entry)
    return {"action": ("scheduled" if pub_at else "published"),
            "id": entry["id"], "url": yurl, "title": title, "when": entry.get("post_at") or ""}


# ── Sélection + tick ──────────────────────────────────────────────────────────

def _auto_projects():
    out = {}
    for p in project_list():
        # On n'auto-produit qu'une chaîne dont : l'autonomie = auto, YouTube est connecté,
        # et l'ATELIER de sa niche est configuré (Lore par défaut, ou Remotion:<niche>).
        if (p.get("autonomy") or "auto") != "auto" or not p.get("yt_refresh_token"):
            continue
        vtool = (p.get("video_tool") or "").strip().lower() or "lore"
        if vtool == "none":
            continue   # chaîne en production manuelle → jamais auto
        eng = _engine(p)
        if eng["kind"] in ("lore", "remotion") and _engine_configured(eng):
            out[p["id"]] = p
    return out


def _pick(projs):
    """La prochaine fiche à faire avancer — UNE CHAÎNE À LA FOIS.

    Règles :
      1) S'il y a un rendu en cours, on le finit d'abord (= 1 seul rendu global).
      2) Sinon on reste sur une chaîne DÉJÀ ENTAMÉE (qui a déjà des vidéos
         posted/programmées) tant qu'il lui reste des fiches → on la termine
         AVANT de passer à une autre chaîne.
      3) Aucune chaîne entamée → on démarre celle dont la prochaine date est la
         plus proche. La date ne sert qu'à choisir l'ORDRE des chaînes, pas à
         entrelacer les chaînes entre elles.
    Franchise obligatoire (sinon fiche ignorée).
    """
    all_mine = [it for it in plan_list() if it.get("project_id") in projs]
    # Toute fiche programmée/en rendu est éligible. La franchise n'est plus
    # exigée ici : si elle manque, _start_render la déduit du sujet (ou écarte
    # la fiche proprement). Une fiche manuelle produit donc elle aussi.
    elig = [it for it in all_mine if it.get("status") in ("scheduled", "rendering")]
    if not elig:
        return None
    # 1) un rendu en cours → on le finit (sa chaîne est l'active).
    rendering = sorted([it for it in elig if it["status"] == "rendering"],
                       key=lambda it: it.get("post_at") or "")
    if rendering:
        return rendering[0]
    # 2/3) sélection de la chaîne active, puis sa fiche la plus proche. On ÉCARTE les
    # fiches qui attendent leur prochaine re-tentative (retry espacé de ~10 min) tant
    # que l'heure n'est pas atteinte → elles redeviennent éligibles d'elles-mêmes.
    scheduled = [it for it in elig if it["status"] == "scheduled" and _retry_due(it.get("notes"))]
    by_proj = {}
    for it in scheduled:
        by_proj.setdefault(it["project_id"], []).append(it)
    started = {it["project_id"] for it in all_mine if it.get("status") == "posted"}
    in_progress = [pid for pid in by_proj if pid in started]
    pool = in_progress or list(by_proj.keys())   # chaînes entamées d'abord
    chan_min = lambda pid: min((it.get("post_at") or "9999") for it in by_proj[pid])
    active = sorted(pool, key=chan_min)[0]
    return sorted(by_proj[active], key=lambda it: it.get("post_at") or "")[0]


def _publish_finished_first(projs):
    """PRIORITÉ ABSOLUE : si un rendu est DÉJÀ fini (prêt à publier), on le publie
    TOUT DE SUITE, sans attendre qu'un autre rendu en cours se termine. Sinon une
    vidéo prête à être envoyée reste coincée derrière un rendu de 30-60 min (cas
    vécu : la vidéo finie attendait derrière une autre encore en rendu). Publier
    n'interrompt PAS le rendu en cours (il tourne sur l'atelier, indépendamment).
    On regarde toutes les fiches qui portent un job (rendering OU scheduled), et on
    publie la PREMIÈRE dont le job est 'done'. Renvoie le résultat _publish, ou None."""
    for it in plan_list():
        if it.get("project_id") not in projs:
            continue
        if it.get("status") not in ("rendering", "scheduled"):
            continue
        job = (it.get("render_job") or "").strip()
        if not job:
            continue
        p = projs[it["project_id"]]
        try:
            st = _eng_call(_engine(p), "/jobs/" + urllib.parse.quote(job), timeout=20)
        except Exception:
            continue   # job injoignable/perdu → _pick + _start_render s'en occupent
        if st.get("status") == "done":
            _log_suggestions(st, it)   # Remotion : idées d'animations (chess/war) → journal
            # Chemin unique : double check assets + supervision Claude + go/no-go + publi.
            return _finalize_and_publish(p, it, st)
    return None


def _log_suggestions(job_status, entry):
    """Remotion renvoie parfois `suggestions` = idées de NOUVELLES animations/designs
    (surtout chess/war). On les pose dans le journal → le studio garde un backlog visible
    d'améliorations à pousser sur le VPS. Sans effet pour Lore (pas de suggestions)."""
    sugg = job_status.get("suggestions") or []
    if isinstance(sugg, list) and sugg:
        items = " · ".join(str(s).strip() for s in sugg[:4] if str(s).strip())
        if items:
            _log("info", "suggestions", "💡 Idées d'animations proposées : " + items, entry)


@worker_bp.route("/api/delamain/worker/tick", methods=["GET", "POST"])
def tick():
    if not _authorized():
        return jsonify({"error": "clearance"}), 403
    if not (_lore_base() or _cfg("REMOTION_WORKER_URL")):
        return jsonify({"action": "skip", "reason": "no_engine_configured"})
    if not _yt_configured():
        return jsonify({"action": "skip", "reason": "youtube_not_configured"})

    # Un seul tick à la fois, MÊME entre process (o2switch/Passenger peut en
    # lancer plusieurs) : verrou mémoire (rapide, même process) PUIS verrou DB
    # global. Sans le verrou DB, 2 process pourraient lancer 2 rendus / publier
    # 2 fois la même vidéo. Avec, le comportement reste strictement séquentiel.
    if not _TICK_LOCK.acquire(blocking=False):
        return jsonify({"action": "busy"})
    if not worker_lock_acquire():
        _TICK_LOCK.release()
        return jsonify({"action": "busy"})
    try:
        worker_heartbeat("tick")   # battement de cœur : « le worker vient de tourner »
        projs = _auto_projects()
        if not projs:
            return jsonify({"action": "idle", "reason": "aucune chaîne auto connectée"})
        # AVANT TOUT : publier un rendu déjà fini (ne pas le faire attendre derrière
        # un rendu en cours). Si une vidéo prête a été publiée, on s'arrête là.
        done_pub = _publish_finished_first(projs)
        if done_pub is not None:
            return jsonify(done_pub)
        entry = _pick(projs)
        if not entry:
            return jsonify({"action": "idle", "reason": "rien à produire"})

        proj = projs[entry["project_id"]]   # la fiche est publiée sur SA chaîne
        try:
            if entry["status"] == "scheduled":
                return jsonify(_start_render(proj, entry))
            # rendering : on vérifie le job de CETTE fiche sur SON atelier (Lore/Remotion)
            st = _eng_call(_engine(proj), "/jobs/"
                           + urllib.parse.quote((entry.get("render_job") or "")), timeout=30)
            s = st.get("status")
            if s == "done":
                _log_suggestions(st, entry)   # Remotion : idées d'animations → journal
                # Chemin unique : double check assets + supervision Claude + go/no-go + publi.
                # Si la miniature échoue, on ne publie PAS ce tick (réessai auto).
                return jsonify(_finalize_and_publish(proj, entry, st))
            if s == "failed":
                err = str(st.get("error", ""))[:200]
                tries = _render_tries(entry.get("notes"))
                if _render_transient(err) and tries + 1 < _MAX_RENDER_TRIES:
                    # Panne passagère (proxy, 5xx, atelier saturé…) → on NE grille pas
                    # tout d'un coup : on replanifie un rendu NEUF ~10 min plus tard (le
                    # proxy a le temps de récupérer). Repris tout seul par le cron même
                    # si personne ne regarde ; au bout de ~2 h sans succès → « à corriger ».
                    nxt = (_now() + datetime.timedelta(seconds=_RETRY_DELAY_SEC)).isoformat(timespec="seconds")
                    plan_update(entry["id"], {"status": "scheduled", "render_job": "",
                                              "notes": "__retry:" + str(tries + 1) + "@" + nxt})
                    _log("warn", "render_retry", "Rendu raté (panne passagère : " + (err or "?")[:120]
                         + ") → nouvelle tentative auto vers " + nxt[11:16], entry)
                    return jsonify({"action": "render_retry", "id": entry["id"],
                                    "try": tries + 1, "next": nxt})
                suffix = (" (après " + str(tries + 1) + " tentatives sur ~2 h)") if tries else ""
                plan_update(entry["id"], {"status": "failed",
                                          "notes": "rendu échoué" + suffix + " : " + err})
                _log("error", "render_failed", "Rendu échoué" + suffix + " : " + (err or "?")[:160]
                     + " — intervention requise", entry)
                return jsonify({"action": "render_failed", "id": entry["id"]})
            # Reflète l'état réel (file d'attente vs rendu) sans spammer la DB :
            # on n'écrit QUE si ça change. Le passage à "running" remet updated_at
            # = vrai début du rendu (→ % estimé correct).
            tries = _render_tries(entry.get("notes"))
            base = "__queued" if s == "queued" else "__running"
            marker = base + ((":" + str(tries)) if tries else "")
            if (entry.get("notes") or "") != marker:
                plan_update(entry["id"], {"notes": marker})
                entry["notes"] = marker
            # Le rendu tourne : on en profite pour préparer titre/desc puis
            # miniature (UNE chose par tick → reste rapide). Prêts pour la publi.
            did = _prepare_assets(proj, entry)
            return jsonify({"action": "rendering", "id": entry["id"], "status": s, "prep": did})
        except urllib.error.HTTPError as e:
            # Job introuvable sur l'atelier (404) = rendu perdu/expiré → on NE
            # bloque PAS toute la file (sinon _pick renvoie toujours cette fiche
            # en premier et plus rien n'avance) : on la repasse en 'scheduled'
            # pour relancer un rendu propre au prochain tick (auto-récupération).
            if e.code == 404:
                plan_update(entry["id"], {"status": "scheduled", "render_job": "",
                                          "notes": "rendu perdu sur l'atelier, relance auto"})
                _log("warn", "requeue", "Rendu introuvable sur l'atelier (404) → relance auto", entry)
                return jsonify({"action": "requeue", "id": entry["id"]})
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                detail = str(e)
            return jsonify({"action": "error", "id": entry["id"], "status": e.code, "detail": detail}), 502
        except Exception as e:  # noqa: BLE001
            return jsonify({"action": "error", "id": entry["id"], "detail": str(e)}), 502
    finally:
        worker_lock_release()
        _TICK_LOCK.release()


@worker_bp.route("/api/delamain/worker/status", methods=["GET"])
def status():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    projs = _auto_projects()
    items = [it for it in plan_list() if it.get("project_id") in projs]
    def n(*st):
        return sum(1 for it in items if it.get("status") in st)
    return jsonify({
        "configured": bool((_lore_base() or _cfg("REMOTION_WORKER_URL")) and _yt_configured()),
        "auto_channels": len(projs),
        "rendering": n("rendering"),
        "due": sum(1 for it in items if it.get("status") == "scheduled"
                   and (it.get("franchise") or "").strip() and _due(it.get("post_at"))),
        "scheduled": n("scheduled"),
        "posted": n("posted"),
        "failed": n("failed"),
    })


@worker_bp.route("/api/delamain/worker/events", methods=["GET"])
def events():
    """Console live : journal du worker (événements d'id > since) + battement de cœur
    (dernier tick). Lecture seule, sans verrou. `health` = état du heartbeat pour le
    dead-man's switch : 'ok' si tick récent, 'stale' si silence prolongé alors qu'il y a
    des vidéos dues (= le worker ne tourne plus → cron à vérifier), 'idle' sinon."""
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    since = request.args.get("since", default=0, type=int)
    evs = event_list(since, 200)
    state = worker_state_get()
    # Y a-t-il du travail dû mais pas pris en charge ? (sert à juger un silence du worker)
    projs = _auto_projects()
    items = [it for it in plan_list() if it.get("project_id") in projs]
    due = sum(1 for it in items if it.get("status") in ("scheduled", "rendering"))
    age = None
    last = (state or {}).get("last_tick") or ""
    if last:
        try:
            age = (datetime.datetime.utcnow()
                   - datetime.datetime.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds()
        except Exception:
            age = None
    if age is None:
        health = "idle"
    elif age > 300 and due > 0:
        health = "stale"      # >5 min sans tick alors qu'il reste à produire → anormal
    else:
        health = "ok"
    return jsonify({"events": evs, "state": state, "age_sec": age,
                    "health": health, "due": due})


def _set_youtube_thumbnail(proj, vid, thumb_url):
    """Pose la miniature `thumb_url` sur la vidéo YouTube `vid` (déjà en ligne /
    programmée). Utilise l'OAuth + le proxy de la chaîne. Renvoie True si OK."""
    access = _access_token(proj.get("yt_refresh_token", ""), proj.get("proxy", ""))
    if not access:
        return False
    op = _opener(proj.get("proxy", ""))
    with urllib.request.urlopen(thumb_url, timeout=60) as tr:
        tb = tr.read()
        tct = tr.headers.get("Content-Type", "image/jpeg")
    treq = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + vid,
        data=tb, method="POST")
    treq.add_header("Authorization", "Bearer " + access)
    treq.add_header("Content-Type", tct)
    with op.open(treq, timeout=120):
        pass
    return True


def _reroll_worker(plan_id):
    """Régénère la miniature EN FOND (re-roll). Tourne dans un thread : la requête a
    déjà répondu « started », donc plus AUCUN timeout HTTP même si Fal met 1-3 min (le
    re-roll synchrone expirait → « erreur génération » côté navigateur). Écrit
    l'avancement (thumb_progress) en continu pour l'affichage live, et pousse la nouvelle
    miniature sur YouTube si la vidéo est déjà en ligne. LIBÈRE les verrous à la fin
    (ils ont été pris par la requête appelante) — finally garanti même en cas d'erreur."""
    try:
        entry = plan_get(plan_id)
        proj = project_get(entry.get("project_id")) if entry else None
        if not entry or not proj:
            _set_thumb_progress(plan_id, "error")
            return
        try:
            ok = _gen_thumbnail(entry, _channel_videos(proj, 50))
        except Exception:
            ok = False
        entry = plan_get(plan_id) or entry
        new_thumb = (entry.get("thumbnail_url") or "").strip()
        if not (ok and new_thumb):
            _set_thumb_progress(plan_id, "error")   # Fal injoignable → l'UI le dira
            return
        # Vidéo déjà sur YouTube ? (video_url contient ?v=ID) → on y pousse la nouvelle.
        m = re.search(r"[?&]v=([\w-]+)", entry.get("video_url") or "")
        if m and proj.get("yt_refresh_token"):
            try:
                if not _set_youtube_thumbnail(proj, m.group(1), new_thumb):
                    _set_thumb_progress(plan_id, "pushfail")
            except Exception:
                _set_thumb_progress(plan_id, "pushfail")
        # Succès : thumb_progress a déjà été remis à '' par _gen_thumbnail (= fini).
    finally:
        worker_lock_release()
        _TICK_LOCK.release()


@worker_bp.route("/api/delamain/worker/rethumb/<int:plan_id>", methods=["POST"])
def rethumb(plan_id):
    """Re-roll : régénère la miniature d'une fiche, EN FOND. Répond tout de suite
    (« started ») puis génère dans un thread → le frontend suit le % via /thumbstatus et
    ne subit aucun timeout. Si la vidéo est DÉJÀ en ligne, la nouvelle miniature est
    aussi poussée sur YouTube (thumbnails.set). Marche AUSSI pendant un rendu."""
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    entry = plan_get(plan_id)
    if not entry:
        return jsonify({"error": "introuvable"}), 404
    proj = project_get(entry.get("project_id"))
    if not proj:
        return jsonify({"error": "chaine introuvable"}), 404
    # Verrou : un tick simultané prépare lui aussi la miniature (s'il la voit vide) → sans
    # verrou il pourrait écraser celle qu'on régénère ici. Le thread de fond GARDE le
    # verrou pendant toute la génération et le libère à la fin (TTL 10 min = filet anti-
    # blocage si le process meurt). Si un tick/upload tient déjà le verrou → réessayer.
    if not _TICK_LOCK.acquire(blocking=False):
        return jsonify({"action": "busy"})
    if not worker_lock_acquire():
        _TICK_LOCK.release()
        return jsonify({"action": "busy"})
    # Marque « en cours » AVANT de répondre : le 1er poll voit déjà un %, jamais un faux
    # « terminé » (anti-race au démarrage). Le thread prend le relais (5 %, 15 %, …).
    _set_thumb_progress(plan_id, 1)
    try:
        threading.Thread(target=_reroll_worker, args=(plan_id,), daemon=True).start()
    except Exception as e:  # noqa: BLE001 — échec rarissime de spawn : on relâche tout
        _set_thumb_progress(plan_id, "error")
        worker_lock_release()
        _TICK_LOCK.release()
        return jsonify({"action": "failed", "detail": str(e)[:200]}), 502
    return jsonify({"action": "started", "id": plan_id})


@worker_bp.route("/api/delamain/worker/thumbstatus/<int:plan_id>", methods=["GET"])
def thumbstatus(plan_id):
    """Avancement live de la miniature (suivi du re-roll). Lecture SEULE, SANS verrou →
    répond même pendant que la génération tourne (thread/process). Renvoie le % en cours
    ('1'..'100'), ou un état terminal : '' (fini, voir thumbnail_url), 'error' (échec
    génération), 'pushfail' (refaite mais MAJ YouTube ratée), 'redo' (postée sans minia)."""
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    it = plan_get(plan_id)
    if not it:
        return jsonify({"error": "introuvable"}), 404
    return jsonify({"progress": (it.get("thumb_progress") or ""),
                    "thumbnail_url": (it.get("thumbnail_url") or "")})


@worker_bp.route("/api/delamain/worker/publish/<int:plan_id>", methods=["GET", "POST"])
def publish_now(plan_id):
    """Publie MAINTENANT le rendu DÉJÀ FINI de CETTE fiche précise, directement, sans
    file d'attente ni nouveau rendu. Renvoie en clair ce qui se passe (publiée / pas
    encore finie / rendu perdu / erreur YouTube exacte) → on ne devine plus. Boss-only.
    Sert de bouton « Publier maintenant » + de diagnostic d'upload."""
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    if not _yt_configured():
        return jsonify({"action": "not_configured"}), 400
    entry = plan_get(plan_id)
    if not entry:
        return jsonify({"action": "not_found"}), 404
    proj = project_get(entry.get("project_id"))
    if not proj or not proj.get("yt_refresh_token"):
        return jsonify({"action": "no_channel",
                        "detail": "chaîne non connectée à YouTube"}), 400
    eng = _engine(proj)
    if not _engine_configured(eng):
        return jsonify({"action": "not_configured",
                        "detail": "atelier « " + eng["kind"] + " » non configuré"}), 400
    job = (entry.get("render_job") or "").strip()
    if not job:
        # Aucun rendu lié → rien à republier (il faut (re)lancer un rendu).
        return jsonify({"action": "no_job",
                        "detail": "aucun rendu lié à cette fiche"})
    # Verrou : pas deux uploads/ticks en même temps (cron + bouton).
    if not _TICK_LOCK.acquire(blocking=False):
        return jsonify({"action": "busy"})
    if not worker_lock_acquire():
        _TICK_LOCK.release()
        return jsonify({"action": "busy"})
    try:
        try:
            st = _eng_call(eng, "/jobs/" + urllib.parse.quote(job), timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return jsonify({"action": "job_lost",
                                "detail": "le rendu n'existe plus sur l'atelier"})
            raise
        s = st.get("status")
        if s == "failed":
            return jsonify({"action": "render_failed",
                            "detail": str(st.get("error", ""))[:200]})
        if s != "done":
            return jsonify({"action": "still_rendering", "status": s})
        # Rendu fini → chemin unique : double check assets + supervision Claude + go/no-go.
        # Si la miniature ne peut pas être générée, on NE publie pas sans (réessai auto).
        return jsonify(_finalize_and_publish(proj, entry, st))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            detail = str(e)
        return jsonify({"action": "upload_error", "status": e.code, "detail": detail}), 502
    except Exception as e:  # noqa: BLE001
        return jsonify({"action": "upload_error", "detail": str(e)[:300]}), 502
    finally:
        worker_lock_release()
        _TICK_LOCK.release()


@worker_bp.route("/api/delamain/worker/ytstatus/<int:plan_id>", methods=["GET", "POST"])
def ytstatus(plan_id):
    """DIAGNOSTIC : interroge YouTube sur l'état RÉEL de la vidéo publiée de cette fiche
    (uploadStatus, processing, taille du fichier reçu par YouTube). → on sait enfin si
    YouTube a bien les octets ou si l'upload a vraiment échoué, au lieu de deviner.
    Accepte la session boss OU ?key=CRON_SECRET (pour diagnostic externe)."""
    if not _authorized():
        return jsonify({"error": "clearance"}), 403
    entry = plan_get(plan_id)
    if not entry:
        return jsonify({"action": "not_found"}), 404
    proj = project_get(entry.get("project_id"))
    if not proj or not proj.get("yt_refresh_token"):
        return jsonify({"action": "no_channel"}), 400
    m = re.search(r"[?&]v=([\w-]+)", entry.get("video_url") or "")
    if not m:
        return jsonify({"action": "no_video_id", "status": entry.get("status")})
    vid = m.group(1)
    proxy = proj.get("proxy", "")
    access = _access_token(proj["yt_refresh_token"], proxy)
    if not access:
        return jsonify({"action": "auth_failed"}), 502
    url = ("https://www.googleapis.com/youtube/v3/videos"
           "?part=status,processingDetails,fileDetails&id=" + vid)
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + access)
    op = _opener(proxy)
    try:
        with op.open(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            detail = str(e)
        return jsonify({"action": "yt_error", "status": e.code, "detail": detail}), 502
    items = data.get("items") or []
    if not items:
        return jsonify({"action": "not_on_youtube", "video_id": vid,
                        "detail": "vidéo absente côté YouTube (supprimée ?)"})
    info = items[0]
    st = info.get("status") or {}
    proc = info.get("processingDetails") or {}
    fd = info.get("fileDetails") or {}
    fsize = fd.get("fileSize")
    return jsonify({
        "action": "ok", "video_id": vid,
        "uploadStatus": st.get("uploadStatus"),
        "failureReason": st.get("failureReason"),
        "rejectionReason": st.get("rejectionReason"),
        "privacyStatus": st.get("privacyStatus"),
        "processingStatus": proc.get("processingStatus"),
        "fileSize": fsize,
        "fileSizeMo": (round(int(fsize) / 1048576, 1) if (fsize and str(fsize).isdigit()) else None),
        "durationMs": fd.get("durationMs"),
    })
