"""API du format Histoire (/api/history/*) — boss uniquement, comme 2D Videos.

Titre + durée → script documentaire → voix → plan visuel → images IA → rendu Remotion
(history_engine/). Tout tourne côté serveur : l'onglet peut être fermé pendant une vidéo.
"""
import os
import shutil

from flask import Blueprint, jsonify, request, send_from_directory, session

from services import ai, media, tts
from services import history as H
from services import history_ai as HA
from services import history_channels as HC
from services import pov_store as store

history_bp = Blueprint("history", __name__)

VOICES = [
    {"provider": "ai33", "voice": "VsVIOTkd9zjLUVaQO9TA", "speed": 0.9, "name": "Earl — conteur US grave (ElevenLabs via ai33pro)"},
    {"provider": "ai33", "voice": "VMCgCMbBs53ElBxVD4VB", "speed": 0.9, "name": "Steven — documentaire grave (ElevenLabs via ai33pro)"},
    {"provider": "ai33", "voice": "t0eCaS57KWbQQc1wRkah", "speed": 0.9, "name": "Russ — narrateur US profond (ElevenLabs via ai33pro)"},
    {"provider": "ai33", "voice": "JBFqnCBsd6RMkjVDRZzb", "speed": 0.9, "name": "George — conteur britannique (ElevenLabs via ai33pro)"},
    {"provider": "algrow", "voice": "lfBVYbXnblkOddWFfEIg", "name": "Timothy — narrateur US grave (Algrow)"},
    {"provider": "algrow", "voice": "642gSURPsKb4OdCDpkPc", "name": "Elliott — narrateur britannique (Algrow)"},
    {"provider": "algrow", "voice": "vLZJLcQMJCqxjrHGEVDO", "name": "Connery — documentaire profond (Algrow)"},
    {"provider": "edge", "voice": "en-US-GuyNeural", "name": "Guy — Edge TTS (gratuit)"},
    {"provider": "edge", "voice": "en-GB-RyanNeural", "name": "Ryan — Edge TTS britannique (gratuit)"},
]


@history_bp.before_request
def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    os.makedirs(H.data_dir(), exist_ok=True)
    return None


def _err(msg, code=400):
    return jsonify({"error": str(msg)}), code


def _full(pr):
    out = H.summary(pr)
    out.update({"notes": pr.get("notes", ""), "options": pr.get("options"), "voice_settings": pr.get("voice_settings"),
                "script": pr.get("script"), "voice": pr.get("voice")})
    plan = pr.get("plan") or {}
    out["plan"] = {"cast": plan.get("cast") or [],
                   "segments": [{k: v for k, v in s.items() if k in ("type", "start", "end", "src", "image", "terrain", "text",
                                                                      "title", "name", "_prompt")}
                                for s in plan.get("segments") or []]}
    return out


@history_bp.route("/api/history/config")
def config():
    node = shutil.which("node")
    engine_deps = os.path.isdir(os.path.join(H.ENGINE_DIR, "node_modules", "remotion"))
    return jsonify({"ai": ai.configured(), "tts": tts.provider_status(), "ffmpeg": media.available(),
                    "node": bool(node), "engine_deps": engine_deps, "voices": VOICES, "defaults": H.DEFAULTS,
                    "styles": [{"key": k, "name": v["name"]} for k, v in HA.IMAGE_STYLES.items()],
                    "channels": [{"key": k, "name": c["name"], "handle": c["handle"], "minutes": c["minutes"],
                                  "image_style": c["image_style"], "ideas": [i["title"] for i in HC.ideas(k)]}
                                 for k, c in HC.CHANNELS.items()],
                    "wpm": 153, "data_dir": H.data_dir()})


@history_bp.route("/api/history/projects", methods=["GET", "POST"])
def projects():
    if request.method == "GET":
        return jsonify({"projects": [H.summary(p) for p in H.list_projects()]})
    b = request.get_json(silent=True) or {}
    title = (b.get("title") or "").strip()
    if len(title) < 4:
        return _err("Écris le titre de la vidéo.")
    if not ai.configured():
        return _err("Proxy IA non configuré (AI_BASE_URL / AI_API_KEY dans le .env).", 503)
    if not media.available():
        return _err("ffmpeg introuvable (pip install imageio-ffmpeg).", 503)
    minutes = max(1.0, min(60.0, float(b.get("minutes") or H.DEFAULTS["minutes"])))
    opts = {k: b["options"][k] for k in H.DEFAULTS if isinstance(b.get("options"), dict) and k in b["options"]}
    pr = H.new_project(title, minutes, (b.get("notes") or "").strip(), opts)
    v = b.get("voice") or {}
    if v.get("provider") in tts.PROVIDERS:
        known = next((x for x in VOICES if x["provider"] == v["provider"] and x["voice"] == v.get("voice")), {})
        pr["voice_settings"] = {"provider": v["provider"], "voice": v.get("voice", ""),
                                "speed": float(v.get("speed") or known.get("speed") or 1.0)}
        H.save_project(pr)
    store.start_job(pr["id"], "autopilot", lambda j: H.job_autopilot(j, pr["id"]))
    return jsonify(H.summary(H.get_project(pr["id"])))


@history_bp.route("/api/history/projects/<pid>", methods=["GET", "DELETE"])
def project(pid):
    pr = H.get_project(pid)
    if not pr:
        return _err("Projet introuvable.", 404)
    if request.method == "DELETE":
        store.cancel_job(pid)
        H.delete_project(pid)
        return jsonify({"ok": True})
    return jsonify(_full(pr))


@history_bp.route("/api/history/projects/<pid>/<action>", methods=["POST"])
def action(pid, action):
    pr = H.get_project(pid)
    if not pr:
        return _err("Projet introuvable.", 404)
    b = request.get_json(silent=True) or {}
    if action == "cancel":
        return jsonify({"cancelled": bool(store.cancel_job(pid))})
    if action == "redo":  # refaire une étape (et les suivantes), puis enchaîner jusqu'à la vidéo
        step = b.get("step")
        if step not in H.STAGES:
            return _err("Étape inconnue.")
        if step == "images":
            shutil.rmtree(os.path.join(H.media_dir(pid), "images"), ignore_errors=True)
        H.invalidate_from(pid, step)
        action = "autopilot"
    if action == "regen":  # refaire une seule image du plan
        rel = (b.get("file") or "").replace("\\", "/")
        if not rel.startswith("images/") or ".." in rel:
            return _err("Image invalide.")
        try:
            os.remove(os.path.join(H.media_dir(pid), rel))
        except OSError:
            pass
        H.update_project(pid, lambda x: x.update(render=None))
        action = "autopilot"
    if action not in H.JOBS:
        return _err("Action inconnue.", 404)
    try:
        job = store.start_job(pid, action, lambda j: H.JOBS[action](j, pid))
    except RuntimeError as e:
        return _err(e, 409)
    return jsonify({"job": job.as_dict()})


@history_bp.route("/api/history/projects/<pid>/files/<path:rel>")
def files(pid, rel):
    if not store.valid_id(pid):
        return _err("id", 404)
    return send_from_directory(H.project_dir(pid), rel, as_attachment=request.args.get("dl") == "1", max_age=0)
