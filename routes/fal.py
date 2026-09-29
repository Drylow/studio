"""Proxy Fal (Nano Banana 2) pour le Thumbnail Creator.

Le navigateur n'a JAMAIS la clé Fal : il appelle nos endpoints, qui relaient
vers fal.ai avec FAL_KEY (.env). Boss-only (sous /api/ → zone boss du gate,
+ revérification explicite du rôle). Utilise urllib (stdlib) → 0 dépendance.

  POST /api/fal/generate   {prompt, image_urls?, aspect_ratio?, resolution?, num_images?}
       -> {request_id, status_url, response_url}   (soumet à la file fal)
  GET  /api/fal/status?status_url=..&response_url=..
       -> {status:"pending"} | {status:"done", images:[{url}], description}

IMPORTANT : on RENVOIE puis RÉUTILISE les `status_url`/`response_url` fournis par
fal à la soumission (au lieu de les reconstruire) — car pour un sous-modèle
(`/edit`) fal place le suivi sur le modèle de base, sans le `/edit`.
"""
import os
import json
import urllib.request
import urllib.error

from flask import Blueprint, jsonify, request, session

fal_bp = Blueprint("fal", __name__)

FAL_BASE     = "https://queue.fal.run"
QUEUE_PREFIX = "https://queue.fal.run/"      # garde-fou anti-SSRF
MODEL_EDIT   = "fal-ai/nano-banana-2/edit"   # avec image(s) de référence
MODEL_T2I    = "fal-ai/nano-banana-2"        # texte -> image (sans référence)
MODEL_VIDEO  = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"  # image -> clip vidéo
MODEL_T2V    = "fal-ai/kling-video/v2.5-turbo/pro/text-to-video"   # texte seul -> clip vidéo


def _key():
    return os.getenv("FAL_KEY", "").strip()


def _fal(method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Key " + _key())
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    if not _key():
        return jsonify({"error": "no_key",
                        "message": "FAL_KEY manquante côté serveur"}), 500
    return None


def _err(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            detail = e.read().decode("utf-8")[:600]
        except Exception:
            detail = str(e)
        return jsonify({"error": "fal_error", "status": e.code, "detail": detail}), 502
    return jsonify({"error": "fal_unreachable", "detail": str(e)}), 502


@fal_bp.route("/api/fal/generate", methods=["POST"])
def generate():
    g = _guard()
    if g:
        return g
    p = request.get_json(silent=True) or {}
    prompt = (p.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "bad_request", "message": "prompt requis"}), 400

    image_urls = p.get("image_urls") or []
    if not isinstance(image_urls, list):
        return jsonify({"error": "bad_request", "message": "image_urls doit être une liste"}), 400
    image_urls = [u for u in image_urls if isinstance(u, str) and u][:14]

    try:
        num_images = int(p.get("num_images", 1))
    except (TypeError, ValueError):
        num_images = 1
    num_images = max(1, min(4, num_images))

    model = MODEL_EDIT if image_urls else MODEL_T2I
    payload = {"prompt": prompt, "num_images": num_images}
    if image_urls:
        payload["image_urls"] = image_urls
    if p.get("aspect_ratio"):
        payload["aspect_ratio"] = p["aspect_ratio"]
    if p.get("resolution"):
        payload["resolution"] = p["resolution"]

    try:
        _, body = _fal("POST", FAL_BASE + "/" + model, payload)
    except Exception as e:
        return _err(e)
    return jsonify({
        "request_id":   body.get("request_id"),
        "status_url":   body.get("status_url"),
        "response_url": body.get("response_url"),
    })


@fal_bp.route("/api/fal/video", methods=["POST"])
def video():
    """Image → clip ou texte → clip (Kling 2.5 Turbo Pro).
    Modes :
      - image_url seule           → image-to-video
      - image_url + tail_image_url → image-to-video start+end frame
      - ni image_url ni tail      → text-to-video (prompt obligatoire)
    Suivi via /api/fal/status (générique).
    """
    g = _guard()
    if g:
        return g
    p = request.get_json(silent=True) or {}
    image_url      = p.get("image_url") or ""
    tail_image_url = p.get("tail_image_url") or ""
    prompt         = (p.get("prompt") or "").strip()
    dur            = str(p.get("duration") or "5")

    has_image = isinstance(image_url, str) and image_url
    has_tail  = isinstance(tail_image_url, str) and tail_image_url

    if not has_image and not prompt:
        return jsonify({"error": "bad_request",
                        "message": "image_url ou prompt requis"}), 400

    payload = {"prompt": prompt or "subtle natural cinematic motion"}
    if dur in ("5", "10"):
        payload["duration"] = dur

    if has_image:
        payload["image_url"] = image_url
        if has_tail:
            payload["tail_image_url"] = tail_image_url
        model = MODEL_VIDEO
    else:
        model = MODEL_T2V

    try:
        _, body = _fal("POST", FAL_BASE + "/" + model, payload)
    except Exception as e:
        return _err(e)
    return jsonify({
        "request_id":   body.get("request_id"),
        "status_url":   body.get("status_url"),
        "response_url": body.get("response_url"),
    })


@fal_bp.route("/api/fal/status", methods=["GET"])
def status():
    g = _guard()
    if g:
        return g
    status_url = request.args.get("status_url", "")
    response_url = request.args.get("response_url", "")
    # Garde-fou : on n'interroge QUE des URLs de la file fal (anti-SSRF).
    if not status_url.startswith(QUEUE_PREFIX) or not response_url.startswith(QUEUE_PREFIX):
        return jsonify({"error": "bad_request"}), 400
    try:
        _, sbody = _fal("GET", status_url)
        state = sbody.get("status")
        if state != "COMPLETED":
            return jsonify({"status": "pending", "fal_status": state,
                            "queue_position": sbody.get("queue_position")})
        _, rbody = _fal("GET", response_url)
        return jsonify({"status": "done",
                        "images": rbody.get("images", []),
                        "video": rbody.get("video"),
                        "description": rbody.get("description", "")})
    except Exception as e:
        return _err(e)
