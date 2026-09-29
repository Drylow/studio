"""Client IA unique (texte + images) — API compatible OpenAI.

Tout passe par un proxy OpenAI-compatible (CLIProxyAPI : comptes Codex mutualisés),
configuré dans le .env — la clé ne quitte JAMAIS le serveur :

  AI_BASE_URL          ex: https://cliproxy.kanye.studio/v1
  AI_API_KEY           clé du proxy
  AI_TEXT_MODEL        modèle d'écriture (scripts)          défaut: gpt-5.5
  AI_FAST_MODEL        modèle rapide (prompts d'images...)   défaut: gpt-5.5
  AI_IMAGE_MODEL       modèle image                          défaut: gpt-image-2

Repli : si AI_BASE_URL/AI_API_KEY sont vides on réutilise LLM_BASE/LLM_KEY
(proxy déjà utilisé par Script Writer / Title & Desc).

urllib stdlib (comme le reste du projet) + Pillow pour normaliser les images.
"""
import base64
import io
import json
import os
import random
import time
import urllib.error
import urllib.request
import uuid

try:
    from PIL import Image
except Exception:  # Pillow requis pour le recadrage — erreur claire à l'usage
    Image = None


class AIError(Exception):
    """Erreur lisible (affichée telle quelle dans l'UI)."""


# ── Configuration ───────────────────────────────────────────────────────────

def _env(name, default=""):
    return (os.getenv(name) or default).strip()


def base_url():
    return (_env("AI_BASE_URL") or _env("LLM_BASE")).rstrip("/")


def api_key():
    return _env("AI_API_KEY") or _env("LLM_KEY")


def text_model():
    return _env("AI_TEXT_MODEL", "gpt-5.5")


def fast_model():
    return _env("AI_FAST_MODEL", "gpt-5.5")


def image_model():
    return _env("AI_IMAGE_MODEL", "gpt-image-2")


def text_fallback():
    """Modèle texte de secours quand les comptes du modèle principal sont à court de quota
    (ex. comptes Codex en pause → Gemini). Vide = pas de secours."""
    return _env("AI_TEXT_FALLBACK", "gemini-3-flash")


_cooldown = {}  # modèle → timestamp de fin de pause (quota épuisé), pour basculer sans attendre


def configured():
    return bool(base_url() and api_key())


def _require():
    if not configured():
        raise AIError("Proxy IA non configuré : renseigne AI_BASE_URL et AI_API_KEY dans le .env.")


# ── HTTP bas niveau ─────────────────────────────────────────────────────────

_TRANSIENT = (408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524)


def _post(path, body=None, *, data=None, content_type="application/json", timeout=180):
    """POST vers le proxy. Renvoie (content_type, bytes). Lève AIError."""
    _require()
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base_url() + path, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + api_key())
    req.add_header("Content-Type", content_type)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = r.headers.get("Content-Type", ""), r.read()
        _log(path, "ok", t0)
        return out
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            detail = str(e)
        _log(path, e.code, t0)
        quota = _quota_wait(e.code, detail, e.headers)
        if quota:  # tous les comptes sont en pause : inutile de réessayer
            try:
                info = json.loads(detail).get("error") or {}
                if info.get("model") and info.get("reset_seconds"):
                    _cooldown[info["model"]] = time.time() + float(info["reset_seconds"])
            except (ValueError, AttributeError, TypeError):
                pass
            err = AIError(quota)
            err.status = 4290
            raise err
        err = AIError(f"IA {e.code}: {detail}")
        err.status = e.code
        raise err
    except Exception as e:  # réseau / timeout
        _log(path, "réseau", t0)
        err = AIError(f"IA injoignable: {e}")
        err.status = 0
        raise err


def _quota_wait(code, detail, headers=None):
    """Quota épuisé côté proxy (CLIProxyAPI : « model_cooldown ») → message lisible, sinon None.

    Un 429 passager (rafale) reste retenté normalement ; seul un blocage de plus de 2 min
    (limite d'utilisation des comptes atteinte) est remonté tel quel à l'utilisateur."""
    if code != 429:
        return None
    secs = None
    try:
        e = json.loads(detail).get("error") or {}
        secs = e.get("reset_seconds")
        if secs is None and e.get("code") != "model_cooldown" and "usage_limit" not in json.dumps(e):
            return None
    except (ValueError, AttributeError):
        if "usage_limit" not in (detail or "") and "cooldown" not in (detail or ""):
            return None
    if secs is None and headers is not None:
        try:
            secs = int(headers.get("Retry-After") or 0) or None
        except (TypeError, ValueError):
            secs = None
    if secs is not None and float(secs) < 120:
        return None
    if secs:
        h, m = divmod(int(float(secs)) // 60, 60)
        when = time.strftime("%H:%M", time.localtime(time.time() + float(secs)))
        wait = (f"{h} h {m:02d}" if h else f"{m} min") + f" (vers {when})"
    else:
        wait = "un moment"
    return ("Quota IA épuisé : tous les comptes du proxy ont atteint leur limite d'utilisation. "
            f"Réessaie dans {wait}. Ce qui est déjà fait est conservé.")


def _log(path, status, t0):
    """Trace console (serveur) : repère vite un proxy lent ou des comptes saturés."""
    dt = time.time() - t0
    if status != "ok" or dt > 45:
        print(f"[ia] {path} → {status} en {dt:.0f}s", flush=True)


def _with_retries(fn, tries=4, base_delay=3.0):
    last = None
    for attempt in range(tries):
        try:
            return fn()
        except AIError as e:
            last = e
            status = getattr(e, "status", 0)
            if status and status not in _TRANSIENT:
                raise
            if attempt < tries - 1:
                time.sleep(base_delay * (2 ** attempt) + random.random())
    raise last


# ── Texte ───────────────────────────────────────────────────────────────────

def chat(messages, *, model=None, temperature=None, json_mode=False,
         max_tokens=None, reasoning=None, timeout=240, tries=4):
    """Complétion chat. `messages` = liste OpenAI ou simple str (message user)."""
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    model = model or text_model()
    fb = text_fallback()
    if fb and fb != model and _cooldown.get(model, 0) > time.time():
        model = fb  # modèle principal en pause : secours direct (pas 90 s d'attente du proxy)
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens:
        body["max_tokens"] = int(max_tokens)
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if reasoning:
        body["reasoning_effort"] = reasoning

    def once():
        _, raw = _post("/chat/completions", body, timeout=timeout)
        try:
            data = json.loads(raw.decode("utf-8"))
            text = data["choices"][0]["message"]["content"] or ""
        except Exception:
            raise AIError("Réponse IA illisible: " + raw[:200].decode("utf-8", "replace"))
        if not text.strip():
            err = AIError("Réponse IA vide.")
            err.status = 502  # retentable
            raise err
        return text

    try:
        return _with_retries(once, tries=tries)
    except AIError as e:
        if getattr(e, "status", None) != 4290 or not fb or body["model"] == fb:
            raise
        _log("/chat/completions", f"quota {body['model']} épuisé → secours {fb}", time.time())
        body["model"] = fb
        body.pop("reasoning_effort", None)
        return _with_retries(once, tries=tries)


def extract_json(text):
    """Extraction JSON tolérante (fences markdown, texte autour)."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        a, b = raw.find(open_c), raw.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(raw[a:b + 1])
            except ValueError:
                continue
    raise AIError("JSON attendu, réponse illisible: " + raw[:160])


def chat_json(messages, *, model=None, temperature=None, reasoning=None, tries=3, timeout=240):
    """chat() + parsing JSON, avec nouvelle tentative si le JSON est cassé."""
    last = None
    for _ in range(tries):
        try:
            return extract_json(chat(messages, model=model, temperature=temperature,
                                     json_mode=True, reasoning=reasoning, timeout=timeout))
        except AIError as e:
            last = e
            if getattr(e, "status", None) not in (None, 502) and "JSON" not in str(e):
                raise
    raise last


# ── Images ──────────────────────────────────────────────────────────────────

def _multipart(fields, files):
    """Encode un multipart/form-data. files = [(field, filename, bytes, mime)]."""
    boundary = "----drylow" + uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode())
        out.write(str(v).encode("utf-8"))
        out.write(b"\r\n")
    for field, filename, blob, mime in files:
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
                  f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
        out.write(blob)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), "multipart/form-data; boundary=" + boundary


def _decode_image_response(ctype, raw):
    """Le proxy renvoie soit l'image brute (image/png), soit du JSON b64/url."""
    if ctype.startswith("image/") or raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:3] == b"\xff\xd8\xff":
        return raw
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise AIError("Réponse image illisible.")
    item = (data.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=120) as r:
            return r.read()
    raise AIError("Aucune image dans la réponse: " + raw[:200].decode("utf-8", "replace"))


def _size_for(width, height):
    if width == height:
        return "1024x1024"
    return "1536x1024" if width > height else "1024x1536"


def generate_image(prompt, *, width=1920, height=1080, refs=None, model=None,
                   quality="medium", timeout=300, tries=4, transparent=False):
    """Génère une image et la renvoie en octets (PNG/JPEG bruts du fournisseur).

    refs = liste de chemins/octets d'images de référence (style, perso...) →
    endpoint /images/edits (cohérence du style). Sinon /images/generations.
    transparent = fond transparent (PNG RGBA), pour le présentateur détouré.
    """
    model = model or image_model()
    size = _size_for(width, height)
    ref_blobs = []
    for r in refs or []:
        if isinstance(r, (bytes, bytearray)):
            ref_blobs.append(bytes(r))
        elif r and os.path.isfile(r):
            with open(r, "rb") as f:
                ref_blobs.append(f.read())

    fields = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": 1}
    if transparent:
        fields.update({"background": "transparent", "output_format": "png"})

    def once():
        if ref_blobs:
            files = [("image[]", f"ref_{i}.png", _to_png(b), "image/png")
                     for i, b in enumerate(ref_blobs[:8])]
            data, ctype = _multipart(fields, files)
            rtype, raw = _post("/images/edits", data=data, content_type=ctype, timeout=timeout)
        else:
            rtype, raw = _post("/images/generations", fields, timeout=timeout)
        return _decode_image_response(rtype, raw)

    return _with_retries(once, tries=tries, base_delay=5.0)


def _to_png(blob, max_side=1536):
    """Références : on borne la taille (upload plus léger, même rendu)."""
    if Image is None:
        return blob
    try:
        im = Image.open(io.BytesIO(blob))
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        im.thumbnail((max_side, max_side))
        out = io.BytesIO()
        im.save(out, "PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return blob


def fit_cover(blob, width, height, dest_path, quality=92):
    """Recadre l'image (cover, centré) au format exact de la vidéo et l'écrit en JPEG.

    Le modèle ne respecte pas toujours le ratio demandé (carré, 3:2, 16:9...),
    donc on normalise ici pour que le montage soit toujours propre."""
    if Image is None:
        raise AIError("Pillow manquant : pip install Pillow")
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    sw, sh = im.size
    scale = max(width / sw, height / sh)
    nw, nh = max(width, round(sw * scale)), max(height, round(sh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - width) // 2, (nh - height) // 2
    im = im.crop((left, top, left + width, top + height))
    if os.path.dirname(dest_path):
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    im.save(dest_path, "JPEG", quality=quality, optimize=True)
    return dest_path


def ping():
    """Test rapide de la connexion (Réglages → Tester)."""
    t0 = time.time()
    text = chat("Réponds uniquement: OK", model=fast_model(), tries=1, timeout=60)
    return {"ok": True, "model": fast_model(), "latency": round(time.time() - t0, 2), "reply": text[:40]}
