"""Proxy LLM (cliwebproxy, compatible OpenAI) pour Script Writer + Title/Desc.

Le navigateur n'a JAMAIS la clé : il appelle nos endpoints, qui relaient vers
cliwebproxy (`LLM_BASE`/`LLM_KEY` du .env) avec un Bearer. Boss-only (sous /api/
+ revérif du rôle). urllib stdlib → 0 dépendance. Claude uniquement.

  POST /api/llm/stream  {messages, model?, temperature?, max_tokens?}
       -> flux SSE OpenAI (data: {...choices[].delta.content...}) pour l'écriture live
  POST /api/llm        {messages, model?, temperature?, max_tokens?}
       -> {text} (réponse complète, pour Title/Description)
"""
import os
import json
import urllib.request
import urllib.error

from flask import Blueprint, request, session, jsonify, Response, stream_with_context

llm_bp = Blueprint("llm", __name__)

# Modèles Claude autorisés (IDs natifs Anthropic, tels qu'exposés par cliwebproxy
# — vérifié via GET /v1/models : claude-opus-4-8 / claude-sonnet-4-6 dispos).
ALLOWED_MODELS = {"claude-opus-4-8", "claude-sonnet-4-6"}
DEFAULT_MODEL = "claude-opus-4-8"


def _base():
    return os.getenv("LLM_BASE", "").strip().rstrip("/")


def _key():
    return os.getenv("LLM_KEY", "").strip()


def _guard():
    if session.get("role") != "boss":
        return jsonify({"error": "clearance"}), 403
    if not _base() or not _key():
        return jsonify({"error": "no_config", "message": "LLM_BASE/LLM_KEY manquants"}), 500
    return None


def _build_body(p, stream):
    messages = p.get("messages")
    if not isinstance(messages, list) or not messages:
        return None, (jsonify({"error": "bad_request", "message": "messages requis"}), 400)
    model = p.get("model") or DEFAULT_MODEL
    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL
    body = {"model": model, "messages": messages, "stream": stream}
    try:
        if p.get("max_tokens"):
            body["max_tokens"] = int(p["max_tokens"])
    except (TypeError, ValueError):
        pass
    try:
        if p.get("temperature") is not None:
            body["temperature"] = float(p["temperature"])
    except (TypeError, ValueError):
        pass
    return body, None


def _request(body):
    req = urllib.request.Request(_base() + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Authorization", "Bearer " + _key())
    req.add_header("Content-Type", "application/json")
    return req


@llm_bp.route("/api/llm/stream", methods=["POST"])
def stream():
    g = _guard()
    if g:
        return g
    body, err = _build_body(request.get_json(silent=True) or {}, True)
    if err:
        return err
    req = _request(body)

    def gen():
        try:
            with urllib.request.urlopen(req, timeout=180) as up:
                for chunk in up:                 # relaie les lignes SSE OpenAI telles quelles
                    yield chunk
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                detail = str(e)
            yield ("data: " + json.dumps({"error": "upstream", "status": e.code, "detail": detail}) + "\n\n").encode("utf-8")
        except Exception as e:
            yield ("data: " + json.dumps({"error": "upstream", "detail": str(e)}) + "\n\n").encode("utf-8")

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@llm_bp.route("/api/llm", methods=["POST"])
def complete():
    g = _guard()
    if g:
        return g
    body, err = _build_body(request.get_json(silent=True) or {}, False)
    if err:
        return err
    try:
        with urllib.request.urlopen(_request(body), timeout=180) as up:
            data = json.loads(up.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            detail = str(e)
        return jsonify({"error": "upstream", "status": e.code, "detail": detail}), 502
    except Exception as e:
        return jsonify({"error": "upstream", "detail": str(e)}), 502
    text = ""
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass
    return jsonify({"text": text})
