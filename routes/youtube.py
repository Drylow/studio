"""Connexion YouTube (OAuth 2.0) par projet — pour que Delamain publie sur la chaîne.

Chaque projet (= chaîne) se connecte via le flux OAuth Google. On stocke le
REFRESH TOKEN en base (boss-only) ; l'access token est régénéré à la volée.

  GET  /api/youtube/status?project_id=X   -> {connected, channel_title, channel_id}
  GET  /api/youtube/connect?project_id=X   -> redirige vers l'écran de consentement Google
  GET  /api/youtube/callback               -> Google renvoie ici ; on échange le code
  POST /api/youtube/disconnect             {project_id}
  POST /api/youtube/upload                 {project_id, video_url, title, description, tags, privacy}

Secrets attendus dans .env :
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, et OAUTH_REDIRECT_BASE (ex: https://edgerunners.fr)

urllib stdlib → 0 dépendance. Boss-only.
"""
import os
import json
import tempfile
import urllib.parse
import urllib.request
import urllib.error

from flask import Blueprint, jsonify, request, session, redirect

from database import project_get, project_set_youtube, project_disconnect_youtube

youtube_bp = Blueprint("youtube", __name__)

AUTH_URI  = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def _cfg(name):
    return os.getenv(name, "").strip()


def _redirect_uri():
    base = _cfg("OAUTH_REDIRECT_BASE").rstrip("/")
    if not base:
        # Repli dev : reconstruit depuis la requête courante.
        base = request.host_url.rstrip("/")
    return base + "/api/youtube/callback"


def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    return None


def _opener(proxy=""):
    """Opener urllib qui route via le proxy de la chaîne si fourni (isolation d'IP).
    Accepte http://user:pass@ip:port. Sans proxy → trafic depuis l'IP du serveur."""
    proxy = (proxy or "").strip()
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener()


def _configured():
    return bool(_cfg("GOOGLE_CLIENT_ID") and _cfg("GOOGLE_CLIENT_SECRET"))


# ── Statut de connexion ───────────────────────────────────────────────────────

@youtube_bp.route("/api/youtube/status", methods=["GET"])
def status():
    g = _guard()
    if g:
        return g
    pid = request.args.get("project_id", type=int)
    proj = project_get(pid) if pid else None
    if not proj:
        return jsonify({"error": "not_found"}), 404
    return jsonify({
        "configured": _configured(),
        "connected": bool(proj.get("yt_refresh_token")),
        "channel_title": proj.get("yt_channel_title", ""),
        "channel_id": proj.get("yt_channel_id", ""),
    })


# ── Démarrage du flux OAuth ───────────────────────────────────────────────────

@youtube_bp.route("/api/youtube/connect", methods=["GET"])
def connect():
    g = _guard()
    if g:
        return g
    if not _configured():
        return jsonify({"error": "no_config",
                        "message": "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET manquants dans .env"}), 500
    pid = request.args.get("project_id", type=int)
    if not pid or not project_get(pid):
        return jsonify({"error": "bad_project"}), 400
    # On transporte l'id du projet dans `state` pour le retrouver au callback.
    params = {
        "client_id": _cfg("GOOGLE_CLIENT_ID"),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",      # pour obtenir un refresh_token
        # select_account = force l'écran de choix de compte (indispensable si plusieurs
        # comptes Google sont connectés, sinon Google prend authuser=0 et renvoie 403).
        # consent = force un refresh_token à chaque connexion.
        "prompt": "select_account consent",
        "state": str(pid),
    }
    # Empêche le navigateur de mettre en cache cette redirection 302 (sinon il
    # réutilise une ancienne version sans select_account → Google prend le compte
    # par défaut en silence et renvoie 403).
    resp = redirect(AUTH_URI + "?" + urllib.parse.urlencode(params))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


# ── Retour de Google ──────────────────────────────────────────────────────────

@youtube_bp.route("/api/youtube/callback", methods=["GET"])
def callback():
    # Le gate global exige déjà boss ; pas de revérif stricte ici (Google n'envoie pas nos cookies si SameSite=Lax → on tolère).
    err = request.args.get("error")
    if err:
        return _close_popup("Connexion refusée : " + err)
    code = request.args.get("code", "")
    pid = request.args.get("state", type=int)
    if not code or not pid or not project_get(pid):
        return _close_popup("Paramètres invalides.")
    # Échange code -> tokens
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": _cfg("GOOGLE_CLIENT_ID"),
        "client_secret": _cfg("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": _redirect_uri(),
        "grant_type": "authorization_code",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(TOKEN_URI, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return _close_popup("Échec de l'échange OAuth : " + str(e))
    refresh = tok.get("refresh_token", "")
    access = tok.get("access_token", "")
    if not refresh:
        return _close_popup("Aucun refresh_token reçu (révoque l'accès dans ton compte Google puis réessaie).")
    # Récupère le nom de la chaîne pour l'afficher
    title, ch_id = _fetch_channel(access)
    project_set_youtube(pid, refresh, title, ch_id)
    return _close_popup("Chaîne connectée : " + (title or "OK"), ok=True)


def _fetch_channel(access_token):
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            method="GET")
        req.add_header("Authorization", "Bearer " + access_token)
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
        it = (d.get("items") or [{}])[0]
        return (it.get("snippet", {}).get("title", ""), it.get("id", ""))
    except Exception:
        return ("", "")


def _close_popup(msg, ok=False):
    color = "#39e6a4" if ok else "#ff4f6d"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>YouTube</title>
<style>body{{background:#03030a;color:{color};font-family:'JetBrains Mono',monospace;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;padding:20px}}</style>
</head><body><div><p>{msg}</p><p style="color:#6b7a99;font-size:12px">Vous pouvez fermer cette fenêtre.</p></div>
<script>try{{window.opener&&window.opener.postMessage({{yt:"{'ok' if ok else 'err'}"}}, "*");}}catch(e){{}}
setTimeout(()=>window.close(),1500);</script></body></html>"""
    return html


# ── Liste des vidéos de la chaîne (via OAuth, scope youtube.readonly) ─────────

@youtube_bp.route("/api/youtube/videos", methods=["GET"])
def videos():
    g = _guard()
    if g:
        return g
    pid = request.args.get("project_id", type=int)
    proj = project_get(pid) if pid else None
    if not proj:
        return jsonify({"error": "not_found"}), 404
    if not proj.get("yt_refresh_token"):
        return jsonify({"videos": [], "connected": False})
    n = request.args.get("n", default=12, type=int)
    proxy = proj.get("proxy", "")
    try:
        access = _access_token(proj["yt_refresh_token"], proxy)
        if not access:
            return jsonify({"error": "auth"}), 502
        op = _opener(proxy)
        # 1) playlist "uploads" de la chaîne authentifiée
        r1 = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true", method="GET")
        r1.add_header("Authorization", "Bearer " + access)
        with op.open(r1, timeout=20) as rr:
            d1 = json.loads(rr.read().decode("utf-8"))
        items = d1.get("items") or []
        if not items:
            return jsonify({"videos": [], "connected": True})
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        # 2) éléments de la playlist (les plus récents d'abord)
        r2 = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults="
            + str(min(50, max(1, n))) + "&playlistId=" + uploads, method="GET")
        r2.add_header("Authorization", "Bearer " + access)
        with op.open(r2, timeout=20) as rr:
            d2 = json.loads(rr.read().decode("utf-8"))
        vids = []
        for it in d2.get("items", []):
            sn = it.get("snippet", {})
            vids.append({
                "id": sn.get("resourceId", {}).get("videoId", ""),
                "title": sn.get("title", ""),
                "description": (sn.get("description", "") or "")[:600],
                "thumb": (sn.get("thumbnails", {}).get("medium", {}) or {}).get("url", ""),
                "date": (sn.get("publishedAt", "") or "")[:10],
            })
        return jsonify({"videos": vids, "connected": True})
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            detail = str(e)
        return jsonify({"error": "youtube_error", "status": e.code, "detail": detail}), 502
    except Exception as e:
        return jsonify({"error": "fetch_failed", "detail": str(e)}), 502


# ── Déconnexion ───────────────────────────────────────────────────────────────

@youtube_bp.route("/api/youtube/disconnect", methods=["POST"])
def disconnect():
    g = _guard()
    if g:
        return g
    p = request.get_json(silent=True) or {}
    pid = p.get("project_id")
    if not pid or not project_get(pid):
        return jsonify({"error": "bad_project"}), 400
    project_disconnect_youtube(pid)
    return jsonify({"ok": True})


# ── Rafraîchissement d'access token (utilitaire interne) ──────────────────────

def _access_token(refresh_token, proxy=""):
    data = urllib.parse.urlencode({
        "refresh_token": refresh_token,
        "client_id": _cfg("GOOGLE_CLIENT_ID"),
        "client_secret": _cfg("GOOGLE_CLIENT_SECRET"),
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URI, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with _opener(proxy).open(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("access_token", "")


# ── Publication (videos.insert) ───────────────────────────────────────────────
# Note : nécessite un fichier vidéo monté (étape montage à venir). Le endpoint est
# prêt ; il prend une URL de vidéo, la télécharge et l'envoie en upload résumable.

def _resumable_upload(op, access, meta, src_req):
    """Upload résumable d'une vidéo vers YouTube SANS la charger entièrement en RAM.
    Une vidéo d'1h pèse des centaines de Mo à plusieurs Go ; faire `bytes = resp.read()`
    (tout en mémoire) faisait planter l'hébergement mutualisé et laissait des uploads
    BLOQUÉS À 0% sur YouTube. Ici : on STREAME le MP4 source vers un fichier temporaire,
    puis on l'envoie à YouTube en flux (Content-Length fixé → http.client lit le fichier
    par blocs = mémoire quasi constante). Renvoie le dict de réponse YouTube ('id' dedans).
    Lève en cas d'échec (l'appelant gère le repli)."""
    fd, tmp = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        total = 0
        with urllib.request.urlopen(src_req, timeout=900) as vr, open(tmp, "wb") as f:
            while True:
                buf = vr.read(1024 * 1024)   # 1 Mo à la fois
                if not buf:
                    break
                f.write(buf)
                total += len(buf)
        if total <= 0:
            raise RuntimeError("vidéo source vide (0 octet)")
        # 1) initialisation de la session résumable (crée la vidéo + renvoie l'URL d'upload).
        init = urllib.request.Request(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            data=json.dumps(meta).encode("utf-8"), method="POST")
        init.add_header("Authorization", "Bearer " + access)
        init.add_header("Content-Type", "application/json; charset=UTF-8")
        init.add_header("X-Upload-Content-Type", "video/*")
        init.add_header("X-Upload-Content-Length", str(total))   # YouTube sait la taille → barre de progression réelle
        with op.open(init, timeout=60) as ir:
            upload_url = ir.headers.get("Location")
        if not upload_url:
            raise RuntimeError("pas d'URL d'upload renvoyée par YouTube")
        # 2) envoi des octets EN FLUX depuis le fichier (Content-Length manuel → pas de
        # transfer-encoding chunked, que YouTube refuse ; http.client envoie par blocs).
        with open(tmp, "rb") as f:
            put = urllib.request.Request(upload_url, data=f, method="PUT")
            put.add_header("Content-Type", "video/*")
            put.add_header("Content-Length", str(total))
            with op.open(put, timeout=3600) as pr:   # gros fichiers : timeout large
                return json.loads(pr.read().decode("utf-8"))
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

@youtube_bp.route("/api/youtube/upload", methods=["POST"])
def upload():
    g = _guard()
    if g:
        return g
    if not _configured():
        return jsonify({"error": "no_config"}), 500
    p = request.get_json(silent=True) or {}
    pid = p.get("project_id")
    proj = project_get(pid) if pid else None
    if not proj or not proj.get("yt_refresh_token"):
        return jsonify({"error": "not_connected",
                        "message": "Cette chaîne n'est pas connectée à YouTube."}), 400
    # Source vidéo : soit une URL directe (video_url), soit un job du tool Lore
    # (lore_job) → on récupère le MP4 sur le worker avec le token (côté serveur).
    video_url = (p.get("video_url") or "").strip()
    lore_job = (str(p.get("lore_job") or "")).strip()
    if lore_job:
        lbase = os.getenv("LORE_WORKER_URL", "").strip().rstrip("/")
        if not lbase:
            return jsonify({"error": "lore_not_configured",
                            "message": "Le service de rendu (worker) n'est pas branché : impossible de récupérer la vidéo."}), 503
        src_req = urllib.request.Request(
            lbase + "/jobs/" + urllib.parse.quote(lore_job) + "/video", method="GET")
        ltok = os.getenv("LORE_WORKER_TOKEN", "").strip()
        if ltok:
            src_req.add_header("x-worker-token", ltok)
    elif video_url:
        src_req = urllib.request.Request(video_url, method="GET")
    else:
        return jsonify({"error": "no_video",
                        "message": "Aucune vidéo à publier : fournis video_url ou lore_job."}), 400

    # tags : accepte une liste OU une chaîne séparée par des virgules
    tags_in = p.get("tags") or ""
    if isinstance(tags_in, list):
        tags = [str(t).strip() for t in tags_in if str(t).strip()][:30]
    else:
        tags = [t.strip() for t in str(tags_in).split(",") if t.strip()][:30]

    proxy = proj.get("proxy", "")   # publication via le proxy de la chaîne si défini
    try:
        access = _access_token(proj["yt_refresh_token"], proxy)
        if not access:
            return jsonify({"error": "auth", "message": "Impossible de rafraîchir l'accès Google."}), 502
        meta = {
            "snippet": {
                "title": (p.get("title") or "Vidéo")[:100],
                "description": p.get("description") or "",
                "tags": tags,
            },
            # selfDeclaredMadeForKids=False = « Non, pas fait pour les enfants »,
            # déclaré à CHAQUE upload (sinon YouTube laisse la question en suspens).
            "status": {"privacyStatus": p.get("privacy") or "private",
                       "selfDeclaredMadeForKids": False},
        }
        # Upload résumable EN FLUX (jamais toute la vidéo en RAM → cf. _resumable_upload).
        op = _opener(proxy)
        res = _resumable_upload(op, access, meta, src_req)
        video_id = res.get("id") or ""

        # Miniature (générée par le tool vidéo) — best-effort, n'échoue pas l'upload.
        thumb_url = (p.get("thumb_url") or "").strip()
        thumb_set = False
        if video_id and thumb_url:
            try:
                with urllib.request.urlopen(thumb_url, timeout=60) as tr:
                    thumb_bytes = tr.read()
                    tctype = tr.headers.get("Content-Type", "image/jpeg")
                treq = urllib.request.Request(
                    "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + video_id,
                    data=thumb_bytes, method="POST")
                treq.add_header("Authorization", "Bearer " + access)
                treq.add_header("Content-Type", tctype)
                with op.open(treq, timeout=120):
                    thumb_set = True
            except Exception:
                thumb_set = False

        return jsonify({"ok": True, "video_id": video_id, "thumb_set": thumb_set,
                        "url": "https://www.youtube.com/watch?v=" + video_id})
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:600]
        except Exception:
            detail = str(e)
        return jsonify({"error": "youtube_error", "status": e.code, "detail": detail}), 502
    except Exception as e:
        return jsonify({"error": "upload_failed", "detail": str(e)}), 502
