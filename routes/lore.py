"""Pont vers le tool vidéo « Lore » (rendu via worker distant).

Le rendu de la vidéo ENTIÈRE (scénario → voix → visuels → Remotion/ffmpeg →
MP4 + miniature + métadonnées) tourne sur un GPU RunPod. Le site NE rend PAS :
il appelle une petite API HTTP toujours-up (`worker/server.mjs`, fournie avec
le tool) qui orchestre le pod. Ce module est juste un RELAIS boss-only entre le
studio et cette API, pour ne jamais exposer le token worker au navigateur.

  GET  /api/lore/status                 -> {configured, franchises}
  POST /api/lore/render                 {title, franchise, ...} -> {jobId, status}
  GET  /api/lore/jobs/<job_id>          -> {status, mp4?, ...}
  GET  /api/lore/jobs/<job_id>/video    -> streame le MP4 fini

Secrets attendus dans .env :
  LORE_WORKER_URL    ex: https://lore.kanye.studio   (où tourne worker/server.mjs)
  LORE_WORKER_TOKEN  (optionnel) = WORKER_TOKEN côté worker, envoyé en x-worker-token

urllib stdlib → 0 dépendance. Boss-only.
"""
import os
import json
import urllib.parse
import urllib.request
import urllib.error

from flask import Blueprint, jsonify, request, session, Response, stream_with_context

lore_bp = Blueprint("lore", __name__)

# Univers gérés par le tool (cf. README Lore Maxxing). "series" = footage d'ambiance.
FRANCHISES = [
    {"id": "pokemon",     "name": "Pokémon",        "kind": "game"},
    {"id": "zelda",       "name": "Zelda",          "kind": "game"},
    {"id": "mario",       "name": "Mario",          "kind": "game"},
    {"id": "sonic",       "name": "Sonic",          "kind": "game"},
    {"id": "naruto",      "name": "Naruto",         "kind": "game"},
    {"id": "onepiece",    "name": "One Piece",      "kind": "game"},
    {"id": "simpsons",    "name": "Les Simpson",    "kind": "series"},
    {"id": "spongebob",   "name": "Bob l'éponge",   "kind": "series"},
    {"id": "gravityfalls","name": "Gravity Falls",  "kind": "series"},
    {"id": "rickandmorty","name": "Rick et Morty",  "kind": "series"},
]
_FRANCHISE_IDS = {f["id"] for f in FRANCHISES}


def _cfg(name):
    return os.getenv(name, "").strip()


def _base():
    return _cfg("LORE_WORKER_URL").rstrip("/")


def _configured():
    return bool(_base())


def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    return None


def _headers(json_body=False):
    h = {"Accept": "application/json"}
    tok = _cfg("LORE_WORKER_TOKEN")
    if tok:
        h["x-worker-token"] = tok
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _call(path, method="GET", body=None, timeout=60):
    """Appelle l'API worker. Renvoie (status_code, parsed_json_or_text)."""
    url = _base() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=_headers(json_body=body is not None))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"error": raw or e.reason}
    except Exception as e:  # noqa: BLE001 — réseau/timeout : message lisible côté UI
        return 502, {"error": "worker_unreachable", "detail": str(e)}


# ── Statut ─────────────────────────────────────────────────────────────────

@lore_bp.route("/api/lore/status", methods=["GET"])
def status():
    g = _guard()
    if g:
        return g
    return jsonify({"configured": _configured(), "franchises": FRANCHISES})


# ── Lancer un rendu ──────────────────────────────────────────────────────────

@lore_bp.route("/api/lore/render", methods=["POST"])
def render():
    g = _guard()
    if g:
        return g
    if not _configured():
        return jsonify({"error": "not_configured",
                        "detail": "LORE_WORKER_URL absent du .env — l'API worker n'est pas branchée."}), 503
    p = request.get_json(silent=True) or {}
    title = (p.get("title") or "").strip()
    franchise = (p.get("franchise") or "").strip().lower()
    if not title:
        return jsonify({"error": "title requis"}), 400
    if franchise not in _FRANCHISE_IDS:
        return jsonify({"error": "franchise inconnue", "detail": franchise}), 400

    # On ne transmet au worker que des paramètres connus/sains.
    body = {"title": title, "franchise": franchise,
            "lang": (p.get("lang") or "fr").strip().lower()}
    # Soit faits+secondes/fait, soit durée cible+min/beat.
    if p.get("duration"):
        body["duration"] = p["duration"]
        body["mpb"] = p.get("mpb", 0.6)
    else:
        body["facts"] = p.get("facts", 100)
        body["spf"] = p.get("spf", 35)
    if p.get("clip"):
        body["clip"] = True

    code, data = _call("/render", method="POST", body=body, timeout=30)
    return jsonify(data), (200 if code < 400 else code)


# ── Suivi d'un job ────────────────────────────────────────────────────────────

@lore_bp.route("/api/lore/jobs/<job_id>", methods=["GET"])
def job(job_id):
    g = _guard()
    if g:
        return g
    if not _configured():
        return jsonify({"error": "not_configured"}), 503
    code, data = _call("/jobs/" + urllib.parse.quote(job_id), timeout=30)
    return jsonify(data), (200 if code < 400 else code)


# ── Annuler un job (best-effort) ──────────────────────────────────────────────

@lore_bp.route("/api/lore/jobs/<job_id>", methods=["DELETE"])
def job_cancel(job_id):
    """Demande l'annulation d'un rendu au worker (best-effort).

    Le worker actuel n'expose PAS encore de route d'annulation (404) → on renvoie
    cancelled:false sans erreur. Si l'ami ajoute `DELETE /jobs/:id` côté worker,
    ça l'utilisera automatiquement (dé-file un job en attente / stoppe un rendu)."""
    g = _guard()
    if g:
        return g
    if not _configured():
        return jsonify({"cancelled": False, "reason": "not_configured"})
    code, data = _call("/jobs/" + urllib.parse.quote(job_id), method="DELETE", timeout=20)
    return jsonify({"cancelled": code < 400, "code": code, "worker": data})


# ── Récupérer le MP4 fini (streamé à travers Flask, token jamais exposé) ──────

@lore_bp.route("/api/lore/jobs/<job_id>/video", methods=["GET"])
def job_video(job_id):
    g = _guard()
    if g:
        return g
    if not _configured():
        return jsonify({"error": "not_configured"}), 503
    url = _base() + "/jobs/" + urllib.parse.quote(job_id) + "/video"
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        upstream = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        return jsonify({"error": "video_indisponible", "detail": e.reason}), e.code
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": "worker_unreachable", "detail": str(e)}), 502

    ctype = upstream.headers.get("Content-Type", "video/mp4")

    def _gen():
        try:
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    resp = Response(stream_with_context(_gen()), content_type=ctype)
    clen = upstream.headers.get("Content-Length")
    if clen:
        resp.headers["Content-Length"] = clen
    resp.headers["Content-Disposition"] = f'inline; filename="{job_id}.mp4"'
    return resp
