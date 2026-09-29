"""API de 2D Videos (POV Studio) — boss-only, tout tourne sur la machine locale.

  GET    /api/pov/config                         état des fournisseurs, formats, styles, modèles
  GET    /api/pov/voices?provider=edge&lang=fr   voix disponibles
  POST   /api/pov/voices/preview                 {provider, voice, speed, text} -> mp3
  GET    /api/pov/music · POST /api/pov/music    bibliothèque de musiques (upload multipart)

  GET/POST          /api/pov/channels            (POST {template?, ...})
  GET/PUT/DELETE    /api/pov/channels/<id>
  POST   /api/pov/channels/<id>/style-image      multipart file | {generate:true, prompt?}  (?kind=thumb :
  DELETE /api/pov/channels/<id>/style-image      référence de style des miniatures)
  POST   /api/pov/channels/<id>/describe-style   multipart files → prompt de style (vision)
  POST   /api/pov/channels/<id>/characters/<cid>/image   multipart file | {generate:true}
  POST   /api/pov/channels/<id>/presenter        multipart file | {generate:true, extra?} | {rebuild:true}
                                                 (+ anim = poses | none) → prof + poses de baguette
  DELETE /api/pov/channels/<id>/presenter
  GET    /api/pov/channels/<id>/board-preview    aperçu JPEG de la mise en page tableau
  POST   /api/pov/channels/<id>/bible            {text?} (sinon reference_scripts)
  POST   /api/pov/channels/<id>/transcripts      {urls}
  POST   /api/pov/channels/<id>/ideas            {hint?}
  GET    /api/pov/channels/<id>/files/<path>

  GET/POST          /api/pov/projects
  GET/PUT/DELETE    /api/pov/projects/<id>
  POST   /api/pov/projects/<id>/cast/<cid>/upload  multipart file (image d'un perso de la vidéo)
  POST   /api/pov/projects/<id>/<action>          script | rewrite | voice | replan | cast | images |
                                                 regen | render | pack | metadata | autopilot | cancel
  POST   /api/pov/projects/<id>/scenes/<i>/upload  multipart file
  GET    /api/pov/projects/<id>/files/<path>
"""
import io
import os
import time

from flask import Blueprint, jsonify, request, send_file, send_from_directory, session

from services import ai, media, tts
from services import pov_engine as E
from services import pov_script as S
from services import pov_store as store

pov_bp = Blueprint("pov", __name__)


@pov_bp.before_request
def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    store.ensure_dirs()
    return None


def _err(msg, code=400):
    return jsonify({"error": str(msg)}), code


def _body():
    return request.get_json(silent=True) or {}


def _upload_bytes(field="file", max_mb=25):
    f = request.files.get(field)
    if not f:
        return None
    data = f.read(max_mb * 1024 * 1024 + 1)
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop gros (max {max_mb} Mo).")
    return data


# ── Config / voix / musique ─────────────────────────────────────────────────

@pov_bp.route("/api/pov/config")
def config():
    return jsonify({
        "ai": {"configured": ai.configured(), "base": ai.base_url(), "text_model": ai.text_model(),
               "fast_model": ai.fast_model(), "image_model": ai.image_model()},
        "tts": tts.provider_status(), "ffmpeg": media.available(),
        "formats": {k: {"name": v["name"], "desc": v["desc"]} for k, v in S.FORMATS.items()},
        "styles": E.STYLE_PRESETS, "board_themes": E.board.THEMES, "templates": {k: {"name": v["name"], "language": v["language"],
                                                    "format": v["format"], "niche": v["niche"]}
                                                for k, v in E.TEMPLATES.items()},
        "languages": list(S.LANGS.keys()), "fonts": ["Poppins ExtraBold", "Poppins Black", "Poppins",
                                                     "Montserrat ExtraBold", "Bangers"],
        "edge_featured": tts.EDGE_FEATURED, "openai_voices": tts.OPENAI_VOICES,
        "defaults": {"montage": E.DEFAULT_MONTAGE, "voice_by_lang": E.DEFAULT_VOICE_BY_LANG},
        "data_dir": store.data_dir(),
    })


@pov_bp.route("/api/pov/test", methods=["POST"])
def test():
    out = {}
    try:
        out["ai"] = ai.ping()
    except Exception as e:  # noqa: BLE001
        out["ai"] = {"ok": False, "error": str(e)[:300]}
    out["ffmpeg"] = {"ok": media.available()}
    out["tts"] = tts.provider_status()
    return jsonify(out)


_voice_cache = {}


@pov_bp.route("/api/pov/voices")
def voices():
    provider = request.args.get("provider", "edge")
    lang = (request.args.get("lang") or "").lower()
    if provider == "edge":
        try:
            if "all" not in _voice_cache:
                _voice_cache["all"] = tts.edge_voices()
            vs = [v for v in _voice_cache["all"] if not lang or v["locale"].lower().startswith(lang)]
        except Exception as e:  # noqa: BLE001
            return _err(f"Liste Edge indisponible: {e}", 502)
        featured = set(tts.EDGE_FEATURED.get(lang, []))
        vs.sort(key=lambda v: (v["id"] not in featured, v["id"]))
        return jsonify({"voices": vs})
    if provider == "openai":
        return jsonify({"voices": [{"id": v, "name": v} for v in tts.OPENAI_VOICES]})
    if provider in ("algrow", "algrow_stealth"):
        key = f"{provider}:{lang}:{request.args.get('search', '')}"
        try:
            if key not in _voice_cache:
                _voice_cache[key] = tts.algrow_voices(request.args.get("search", ""), lang,
                                                      stealth=provider == "algrow_stealth")
            vs = list(_voice_cache[key])
            cur = request.args.get("current", "")
            if cur and provider == "algrow" and not any(v["id"] == cur for v in vs):
                vs = tts.algrow_voices(cur, "") + vs  # la voix choisie, même hors du top
        except Exception as e:  # noqa: BLE001
            return _err(e, 502)
        return jsonify({"voices": vs})
    return jsonify({"voices": []})


@pov_bp.route("/api/pov/algrow/credits")
def algrow_credits():
    try:
        c = tts.algrow_credits()
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    return jsonify({"elevenlabs": (c.get("tts_characters") or {}).get("remaining"),
                    "stealth": (c.get("stealth_characters") or {}).get("remaining"), "plan": c.get("plan")})


@pov_bp.route("/api/pov/voices/preview", methods=["POST"])
def voice_preview():
    b = _body()
    text = (b.get("text") or "").strip()[:400] or "Voici un aperçu de la voix off de ta prochaine vidéo."
    tmp = os.path.join(store.data_dir(), "preview_%d.mp3" % int(time.time() * 1000))
    try:
        tts.synthesize(text, tmp, provider=b.get("provider", "edge"), voice=b.get("voice", ""),
                       speed=float(b.get("speed") or 1.0), pitch=b.get("pitch") or 0, model=b.get("model", ""),
                       instructions=b.get("instructions", ""))
        with open(tmp, "rb") as f:
            data = f.read()
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return send_file(io.BytesIO(data), mimetype="audio/mpeg")


@pov_bp.route("/api/pov/music", methods=["GET", "POST"])
def music():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(store._AUDIO_EXT):
            return _err("Fichier audio attendu (mp3, m4a, wav…).")
        name = os.path.basename(f.filename).replace("..", "_")
        f.save(os.path.join(store.music_dir(), name))
    return jsonify({"music": store.list_music()})


@pov_bp.route("/api/pov/music/<path:name>")
def music_file(name):
    return send_from_directory(store.music_dir(), os.path.basename(name))


# ── Chaînes ─────────────────────────────────────────────────────────────────

def _channel_or_404(cid):
    ch = store.get_channel(cid)
    if not ch:
        return None, _err("Chaîne introuvable.", 404)
    return ch, None


@pov_bp.route("/api/pov/channels", methods=["GET", "POST"])
def channels():
    if request.method == "POST":
        b = _body()
        ch = E.new_channel(b, template=b.get("template"))
        return jsonify(ch)
    return jsonify({"channels": store.list_channels()})


@pov_bp.route("/api/pov/nichebend", methods=["POST"])
def nichebend():
    b = _body()
    source = (b.get("source") or "").strip()
    if len(source) < 8:
        return _err("Décris le format ou la chaîne qui marche (ou colle un lien + ce qu'elle fait).")
    try:
        concepts = S.niche_bend(source, (b.get("target") or "").strip(), (b.get("language") or "fr").lower(),
                                style_keys=list(E.STYLE_PRESETS.keys()))
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    return jsonify({"concepts": concepts})


@pov_bp.route("/api/pov/channels/<cid>", methods=["GET", "PUT", "DELETE"])
def channel(cid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    if request.method == "DELETE":
        store.delete_channel(cid)
        return jsonify({"ok": True})
    if request.method == "PUT":
        with store.lock_for(cid):
            ch = E.apply_channel_update(store.get_channel(cid), _body())
            store.save_channel(ch)
    return jsonify(ch)


@pov_bp.route("/api/pov/channels/<cid>/style-image", methods=["POST", "DELETE"])
def style_image(cid):
    """Image de référence : ?kind=style (images de la vidéo, défaut) ou ?kind=thumb (miniatures)."""
    ch, err = _channel_or_404(cid)
    if err:
        return err
    kind = "thumb" if request.args.get("kind") == "thumb" else "style"
    if request.method == "DELETE":
        if kind == "thumb":
            ch["thumb_ref"] = None
        else:
            ch["style"]["ref"] = None
        store.save_channel(ch)
        return jsonify(ch)
    try:
        blob = _upload_bytes()
        if blob is None:
            if kind == "thumb":
                return _err("Importe une de tes miniatures comme référence.")
            b = _body()
            prompt = (b.get("prompt") or "").strip() or \
                "A typical scene of this channel with the main character in a characteristic setting."
            ch_noref = dict(ch, style=dict(ch["style"], ref=None))
            full, refs = E.build_image_prompt(ch_noref, prompt)
            blob = ai.generate_image(full, refs=refs)
        rel = E.save_channel_image(ch, blob, kind)
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    ch = store.get_channel(cid)
    if kind == "thumb":
        ch["thumb_ref"] = rel
    else:
        ch["style"]["ref"] = rel
    store.save_channel(ch)
    return jsonify(ch)


@pov_bp.route("/api/pov/channels/<cid>/describe-style", methods=["POST"])
def describe_style(cid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    blobs = [f.read(15 * 1024 * 1024) for f in request.files.getlist("files")][:4]
    if not blobs and ch["style"].get("ref"):
        with open(E.channel_ref_path(ch, ch["style"]["ref"]), "rb") as f:
            blobs = [f.read()]
    if not blobs:
        return _err("Ajoute 1 à 4 captures d'écran de la chaîne à imiter.")
    try:
        return jsonify({"prompt": E.describe_style(blobs)})
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)


@pov_bp.route("/api/pov/channels/<cid>/characters/<chid>/image", methods=["POST", "DELETE"])
def character_image(cid, chid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    char = next((c for c in ch["style"]["characters"] if c["id"] == chid), None)
    if not char:
        return _err("Personnage introuvable (enregistre la chaîne d'abord).", 404)
    if request.method == "DELETE":
        char["image"] = None
        store.save_channel(ch)
        return jsonify(ch)
    try:
        blob = _upload_bytes()
        if blob is None:
            blob = E.character_sheet(ch, char)
        rel = E.save_channel_image(ch, blob, "char", chid)
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    ch = store.get_channel(cid)
    for c in ch["style"]["characters"]:
        if c["id"] == chid:
            c["image"] = rel
    store.save_channel(ch)
    return jsonify(ch)


@pov_bp.route("/api/pov/channels/<cid>/presenter", methods=["POST", "DELETE"])
def presenter(cid):
    """Génère (ou importe) le prof + son rig animé. ~1 à 2 min : 1 image + 3 retouches en parallèle."""
    ch, err = _channel_or_404(cid)
    if err:
        return err
    if request.method == "DELETE":
        with store.lock_for(cid):
            ch = store.get_channel(cid)
            old = E.board_config(ch)
            ch["board"] = dict(old, presenter=None, rig=None)
            store.save_channel(ch)
        _drop_rig(ch, old)
        return jsonify(ch)
    b = _body()
    anim = (request.form.get("anim") or b.get("anim") or E.board_config(ch).get("anim") or "poses")
    anim = "none" if anim == "none" else "poses"
    try:
        blob = _upload_bytes()
        if blob is not None:
            rel, rig = E.save_presenter(ch, blob, anim=anim)
        elif b.get("rebuild"):  # même prof, autre type d'animation
            rel, rig = E.rebuild_presenter(ch, anim)
        else:
            rel, rig = E.presenter_image(ch, b.get("extra") or "", anim=anim)
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    with store.lock_for(cid):
        ch = store.get_channel(cid)
        old = E.board_config(ch)
        ch["board"] = dict(old, presenter=rel, rig=rig, anim=anim)
        store.save_channel(ch)
    _drop_rig(ch, old, keep=rel)
    return jsonify(ch)


def _drop_rig(ch, old, keep=None):
    """Supprime l'ancien présentateur (image seule ou dossier du rig)."""
    import shutil
    for key in ("rig", "presenter"):
        rel = old.get(key)
        if not rel or (keep and keep.startswith(rel.rstrip("/") + "/")) or rel == keep:
            continue
        path = E.channel_ref_path(ch, rel)
        base = os.path.join(store.channel_dir(ch["id"]), "refs")
        if not path or not os.path.abspath(path).startswith(os.path.abspath(base)):
            continue
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


@pov_bp.route("/api/pov/channels/<cid>/board-preview")
def board_preview(cid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    dest = os.path.join(store.channel_dir(cid), "board_preview.jpg")
    try:
        E.board_preview(ch, dest)
    except Exception as e:  # noqa: BLE001
        return _err(e, 500)
    return send_file(dest, mimetype="image/jpeg", max_age=0)


@pov_bp.route("/api/pov/channels/<cid>/transcripts", methods=["POST"])
def transcripts(cid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    urls = (_body().get("urls") or "").strip()
    try:
        text, errors = E.fetch_transcripts(urls)
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    ch = store.get_channel(cid)
    ch["reference_urls"] = urls
    ch["reference_scripts"] = text
    store.save_channel(ch)
    return jsonify({"channel": ch, "errors": errors})


@pov_bp.route("/api/pov/channels/<cid>/bible", methods=["POST"])
def bible(cid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    text = (_body().get("text") or ch.get("reference_scripts") or "").strip()
    if len(text.split()) < 80:
        return _err("Colle au moins un script / une transcription de référence (80 mots minimum).")
    try:
        bib = S.build_bible(ch, text)
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)
    ch = store.get_channel(cid)
    ch["bible"] = bib
    store.save_channel(ch)
    return jsonify(ch)


@pov_bp.route("/api/pov/channels/<cid>/ideas", methods=["POST"])
def ideas(cid):
    ch, err = _channel_or_404(cid)
    if err:
        return err
    try:
        return jsonify({"ideas": S.title_ideas(ch, (_body().get("hint") or "").strip())})
    except Exception as e:  # noqa: BLE001
        return _err(e, 502)


@pov_bp.route("/api/pov/channels/<cid>/files/<path:rel>")
def channel_file(cid, rel):
    if not store.valid_id(cid):
        return _err("id", 404)
    return send_from_directory(store.channel_dir(cid), rel, max_age=86400)


# ── Projets ─────────────────────────────────────────────────────────────────

def _full(pr):
    job = store.running_job(pr["id"]) or store.last_job(pr["id"])
    out = dict(pr)
    # l'historique complet est lourd : l'UI n'a besoin que des libellés (restauration par index)
    out["script_history"] = [{"at": h.get("at"), "label": h.get("label"),
                              "words": S.word_count(h.get("script") or "")} for h in pr.get("script_history") or []]
    out["job"] = job.as_dict() if job else None
    out["stage"] = E.stage(pr)
    out["voice_outdated"] = bool(pr.get("voice")) and E.voice_outdated(pr)
    out["words_count"] = S.word_count(S.narration(pr.get("script") or ""))
    ch = store.get_channel(pr.get("channel_id")) or {}
    out["channel_cast"] = [{"name": c["name"], "description": c.get("description", ""), "image": c.get("image")}
                           for c in (ch.get("style") or {}).get("characters") or []]
    return out


@pov_bp.route("/api/pov/projects", methods=["GET", "POST"])
def projects():
    if request.method == "POST":
        b = _body()
        ch = store.get_channel(b.get("channel_id") or "")
        if not ch:
            return _err("Choisis une chaîne.")
        pr = E.new_project(ch, b.get("title"), b.get("minutes"), b.get("notes", ""))
        if (b.get("script") or "").strip():
            pr["script"] = b["script"].strip() + "\n"
            store.save_project(pr)
        return jsonify(_full(pr))
    return jsonify({"projects": [E.project_summary(p) for p in store.list_projects()]})


_PR_FIELDS = ("title", "minutes", "notes", "script", "title_locked")


@pov_bp.route("/api/pov/projects/<pid>", methods=["GET", "PUT", "DELETE"])
def project(pid):
    pr = store.get_project(pid)
    if not pr:
        return _err("Projet introuvable.", 404)
    if request.method == "DELETE":
        store.cancel_job(pid)
        store.delete_project(pid)
        return jsonify({"ok": True})
    if request.method == "PUT":
        b = _body()
        removed = []

        def upd(x):
            if "script" in b and b["script"] != x.get("script"):
                E.push_history(x, "édition manuelle")
            for k in _PR_FIELDS:
                if k in b:
                    x[k] = b[k]
            if isinstance(b.get("voice_settings"), dict):
                x["voice_settings"] = E._merge(x.get("voice_settings") or E.DEFAULT_VOICE, b["voice_settings"])
            if isinstance(b.get("montage"), dict):
                x["montage"] = E._merge(x.get("montage") or E.DEFAULT_MONTAGE, b["montage"])
            if isinstance(b.get("scenes"), list):  # prompt / mouvement / persos édités à la main
                by_i = {s["i"]: s for s in x.get("scenes") or []}
                for s in b["scenes"]:
                    t = by_i.get(s.get("i"))
                    if t:
                        for k in ("prompt", "motion"):
                            if k in s:
                                t[k] = s[k]
                        if isinstance(s.get("chars"), list):
                            t["chars"] = [str(c)[:40] for c in s["chars"]][:8]
            if isinstance(b.get("cast"), list):  # casting édité (noms, alias, descriptions, ajouts, retraits)
                old = {c["id"]: c for c in x.get("cast") or []}
                new = []
                for c in b["cast"][:12]:
                    base = old.get(c.get("id")) or {"id": store.new_id("cst"), "image": None}
                    base.update({"name": (c.get("name") or "").strip()[:40] or "Perso",
                                 "aliases": [str(a).strip()[:40] for a in (c.get("aliases") or []) if str(a).strip()][:6],
                                 "role": (c.get("role") or "").strip()[:120],
                                 "description": (c.get("description") or "").strip()[:600]})
                    new.append(base)
                keep = {c["id"] for c in new}
                removed.extend(c.get("image") for c in old.values() if c["id"] not in keep and c.get("image"))
                x["cast"] = new
            if "restore" in b:
                hist = x.get("script_history") or []
                i = int(b["restore"])
                if 0 <= i < len(hist):
                    snap = hist[i]["script"]  # lu AVANT push_history (qui peut décaler les index)
                    E.push_history(x, "avant restauration")
                    x["script"] = snap
        pr = store.update_project(pid, upd)
        for rel in removed:  # images des persos retirés
            try:
                os.remove(os.path.join(store.project_dir(pid), rel))
            except OSError:
                pass
    return jsonify(_full(pr))


_ACTIONS = {
    "script": lambda pid, b: (lambda j: E.job_script(j, pid, polish=b.get("polish", True))),
    "rewrite": lambda pid, b: (lambda j: E.job_rewrite(j, pid, (b.get("instruction") or "").strip())),
    "voice": lambda pid, b: (lambda j: E.job_voice(j, pid)),
    "replan": lambda pid, b: (lambda j: E.job_replan(j, pid)),
    "cast": lambda pid, b: (lambda j: E.job_cast(j, pid, redetect=bool(b.get("redetect")), only=b.get("only"))),
    "images": lambda pid, b: (lambda j: E.job_images(j, pid, only=b.get("only"),
                                                      first_only=bool(b.get("first_only")))),
    "regen": lambda pid, b: (lambda j: E.job_regen(j, pid, int(b.get("i", -1)), b.get("prompt"))),
    "render": lambda pid, b: (lambda j: E.job_render(j, pid)),
    "audit": lambda pid, b: (lambda j: E.job_audit(j, pid, rounds=int(b.get("rounds") or 2))),
    "pack": lambda pid, b: (lambda j: E.job_pack(j, pid, motion=b.get("motion", "none"))),
    "metadata": lambda pid, b: (lambda j: E.job_metadata(j, pid)),
    "thumbnails": lambda pid, b: (lambda j: E.job_thumbnails(j, pid, (b.get("idea") or "").strip(),
                                                              b.get("count", 2))),
    "autopilot": lambda pid, b: (lambda j: E.job_autopilot(j, pid, render_video=b.get("render", True))),
}


@pov_bp.route("/api/pov/projects/<pid>/<action>", methods=["POST"])
def project_action(pid, action):
    pr = store.get_project(pid)
    if not pr:
        return _err("Projet introuvable.", 404)
    if action == "cancel":
        j = store.cancel_job(pid)
        return jsonify({"cancelled": bool(j)})
    if action not in _ACTIONS:
        return _err("Action inconnue.", 404)
    b = _body()
    if action == "rewrite" and not (b.get("instruction") or "").strip():
        return _err("Consigne vide.")
    if action in ("script", "rewrite", "audit", "cast", "images", "regen", "autopilot", "metadata", "thumbnails") \
            and not ai.configured():
        return _err("Proxy IA non configuré (AI_BASE_URL / AI_API_KEY dans le .env).", 503)
    if action in ("voice", "render", "pack", "autopilot") and not media.available():
        return _err("ffmpeg introuvable (pip install imageio-ffmpeg).", 503)
    try:
        job = store.start_job(pid, action, _ACTIONS[action](pid, b))
    except RuntimeError as e:
        return _err(e, 409)
    return jsonify({"job": job.as_dict()})


@pov_bp.route("/api/pov/projects/<pid>/cast/<cid>/upload", methods=["POST"])
def cast_upload(pid, cid):
    """Image d'un perso de la vidéo importée à la main (remplace la référence générée)."""
    pr = store.get_project(pid)
    if not pr:
        return _err("Projet introuvable.", 404)
    if not any(c["id"] == cid for c in pr.get("cast") or []):
        return _err("Personnage introuvable.", 404)
    try:
        blob = _upload_bytes()
        if not blob:
            return _err("Aucun fichier.")
        E.set_cast_image(pid, cid, E._save_cast_image(pid, cid, blob))
    except Exception as e:  # noqa: BLE001
        return _err(e)
    return jsonify(_full(store.get_project(pid)))


@pov_bp.route("/api/pov/projects/<pid>/scenes/<int:i>/upload", methods=["POST"])
def scene_upload(pid, i):
    pr = store.get_project(pid)
    if not pr:
        return _err("Projet introuvable.", 404)
    try:
        blob = _upload_bytes()
        if not blob:
            return _err("Aucun fichier.")
        w, h = E.dims(pr)
        rel = f"images/scene_{i:04d}_up{int(time.time()) % 10**6}.jpg"
        ai.fit_cover(blob, w, h, os.path.join(store.project_dir(pid), rel))
    except Exception as e:  # noqa: BLE001
        return _err(e)

    def upd(x):
        for s in x["scenes"]:
            if s["i"] == i:
                s.update({"image": rel, "status": "done", "error": None})
        x["render"] = None
    return jsonify(_full(store.update_project(pid, upd)))


@pov_bp.route("/api/pov/projects/<pid>/files/<path:rel>")
def project_file(pid, rel):
    if not store.valid_id(pid):
        return _err("id", 404)
    as_dl = request.args.get("dl") == "1"
    return send_from_directory(store.project_dir(pid), rel, as_attachment=as_dl, max_age=3600)
