"""Client du proxy OpenAI-compatible (36 comptes ChatGPT+).

Le proxy fait lui-même la rotation entre les comptes : chaque requête simultanée part sur
un compte différent. On sature donc les comptes en gardant N requêtes en vol
(IMAGE_CONCURRENCY / LLM_CONCURRENCY, 36 par défaut) avec des retries sur 429/5xx.
"""
import asyncio
import base64
import io
import json
import logging
import random
import time

import httpx
from PIL import Image

from . import config, events

log = logging.getLogger("tubeforge.api")

_client: httpx.AsyncClient | None = None
_sems: dict[str, asyncio.Semaphore] = {}

STATS = {
    "llm": {"active": 0, "done": 0, "errors": 0, "retries": 0},
    "image": {"active": 0, "done": 0, "errors": 0, "retries": 0, "total_seconds": 0.0},
}

RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 529}
MODERATION_WORDS = ("safety", "moderation", "content_policy", "content policy", "policy", "flagged",
                    "not allowed", "rejected", "blocked", "inappropriate")


class ApiError(Exception):
    def __init__(self, msg: str, status: int | None = None, retryable: bool = False):
        super().__init__(msg)
        self.status = status
        self.retryable = retryable


class ModerationError(ApiError):
    pass


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(600, connect=30),
            limits=httpx.Limits(max_connections=300, max_keepalive_connections=60),
        )
    return _client


def sem(kind: str) -> asyncio.Semaphore:
    if kind not in _sems:
        n = config.get_int("IMAGE_CONCURRENCY" if kind == "image" else "LLM_CONCURRENCY")
        _sems[kind] = asyncio.Semaphore(max(1, n))
    return _sems[kind]


def reset_limits() -> None:
    """Appelé quand les réglages changent (nouvelle concurrence)."""
    _sems.clear()
    from . import google_flow
    google_flow.reset()


def _url(path: str) -> str:
    return config.get("PROXY_BASE_URL").rstrip("/") + path


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.get('PROXY_API_KEY')}"}


def _error_from(r: httpx.Response) -> ApiError:
    try:
        body = r.json()
        msg = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else str(body)
    except Exception:
        msg = r.text[:500]
    msg = msg or f"HTTP {r.status_code}"
    low = msg.lower()
    if r.status_code in (400, 403, 422) and any(w in low for w in MODERATION_WORDS):
        return ModerationError(f"Moderation refusal: {msg}", r.status_code)
    if r.status_code in RETRYABLE or "rate limit" in low or "quota" in low or "overloaded" in low:
        return ApiError(f"HTTP {r.status_code}: {msg}", r.status_code, retryable=True)
    if r.status_code in (401, 403):
        return ApiError(f"API key refused (HTTP {r.status_code}): {msg}", r.status_code, retryable=r.status_code == 403)
    return ApiError(f"HTTP {r.status_code}: {msg}", r.status_code)


async def _with_retry(kind: str, fn, attempts: int = 6, label: str = ""):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return await fn()
        except ModerationError:
            raise
        except ApiError as e:
            if not e.retryable:
                raise
            last = e
        except (httpx.TransportError, httpx.TimeoutException) as e:
            last = ApiError(f"Network error: {type(e).__name__} {e}", retryable=True)
        except (ValueError, KeyError, json.JSONDecodeError) as e:  # réponse illisible/vide
            last = ApiError(f"Invalid response: {e}", retryable=True)
        STATS[kind]["retries"] += 1
        wait = min(90, 3 * 2 ** attempt) + random.uniform(0, 3)
        events.log(f"⚠ {label or kind} : essai {attempt + 1}/{attempts} failed ({str(last)[:160]}) — retrying in "
                   f"{wait:.0f} s", "warn")
        await asyncio.sleep(wait)
    raise last or ApiError("failed")


# ---------------------------------------------------------------- texte

async def chat(messages: list[dict], model: str | None = None, effort: str | None = "low",
               attempts: int = 6, timeout: float | None = None, label: str = "text prompt",
               on_delta=None, hedge: bool = True) -> str:
    """Appel chat/completions en streaming (évite les timeouts proxy sur les longues générations).

    on_delta(morceau) est appelé à chaque bout de texte reçu (pour afficher l'écriture en direct)."""
    payload = {"model": model or config.get("FAST_MODEL"), "messages": messages, "stream": True}
    if effort:
        payload["reasoning_effort"] = effort

    async def once() -> str:
        parts: list[str] = []
        async with client().stream("POST", _url("/chat/completions"), json=payload, headers=_headers(),
                                   timeout=httpx.Timeout(900, connect=30, read=180)) as r:
            if r.status_code != 200:
                await r.aread()
                raise _error_from(r)
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if obj.get("error"):
                    raise ApiError(str(obj["error"]), retryable=True)
                for ch in obj.get("choices") or []:
                    piece = (ch.get("delta") or {}).get("content")
                    if piece:
                        parts.append(piece)
                        if on_delta:
                            on_delta(piece)
        text = "".join(parts).strip()
        if not text:
            raise ValueError("empty response")
        return text

    slow = effort in ("medium", "high")
    deadline = timeout or (480 if slow else 240)
    hedge_after = 150 if slow else 75  # au-delà, une requête « jumelle » part sur un autre compte

    async def once_bounded() -> str:
        try:
            return await asyncio.wait_for(once(), deadline)
        except asyncio.TimeoutError:
            raise ApiError(f"no complete response in {deadline:.0f}s", retryable=True)

    async def hedged() -> str:
        """Si un compte traîne, on relance en parallèle sur un autre et on garde la 1re réponse."""
        if not hedge:
            return await once_bounded()
        first = asyncio.create_task(once_bounded())
        done, _ = await asyncio.wait({first}, timeout=hedge_after)
        if first in done:
            return first.result()
        STATS["llm"]["hedges"] = STATS["llm"].get("hedges", 0) + 1
        events.log(f"⏳ {label} : no response after {hedge_after} s — une requête jumelle part sur un autre "
                   "compte, on garde la plus rapide", "warn")
        pending = {first, asyncio.create_task(once_bounded())}
        err: BaseException | None = None
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    if t.exception() is None:
                        return t.result()
                    err = t.exception()
            raise err
        finally:
            for t in pending:
                t.cancel()

    async with sem("llm"):
        STATS["llm"]["active"] += 1
        t0 = time.time()
        events.log(f"→ {label} · {payload['model']}" + (f" (thinking {effort})" if effort else "") + " …", "api")
        try:
            out = await _with_retry("llm", hedged, attempts, label)
            STATS["llm"]["done"] += 1
            events.log(f"← {label} : {len(out.split())} words received in {events.fmt_duration(time.time() - t0)}", "api")
            return out
        except Exception as e:
            STATS["llm"]["errors"] += 1
            events.log(f"✗ {label} : {str(e)[:200]}", "error")
            raise
        finally:
            STATS["llm"]["active"] -= 1


# ---------------------------------------------------------------- images

ASPECTS = {
    "16:9": ("1536x1024", "16:9"),
    "9:16": ("1024x1536", "9:16"),
    "1:1": ("1024x1024", "1:1"),
}


async def _image_bytes_from(r: httpx.Response) -> bytes:
    if r.status_code != 200:
        raise _error_from(r)
    ctype = r.headers.get("content-type", "")
    if ctype.startswith("image/"):
        data = r.content
    else:
        body = r.json()
        item = (body.get("data") or [{}])[0]
        if item.get("b64_json"):
            data = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            data = (await client().get(item["url"], timeout=120)).content
        else:
            raise ValueError(f"no image in response: {str(body)[:300]}")
    Image.open(io.BytesIO(data)).verify()  # lève si l'image est corrompue
    return data


async def generate_image(prompt: str, model: str = "", aspect: str = "16:9",
                         refs: list[bytes] | None = None, attempts: int = 5, label: str = "image", provider: str | None = None, receipt: dict | None = None) -> bytes:
    """Génère une image. Avec `refs`, passe par /images/edits (images de référence)."""
    if provider == "google_flow":
        from . import google_flow
        STATS["image"]["active"] += 1
        started = time.time()
        try:
            data = await google_flow.generate(prompt, model, aspect, refs, receipt)
            STATS["image"]["done"] += 1
            STATS["image"]["total_seconds"] += time.time() - started
            return data
        except Exception:
            STATS["image"]["errors"] += 1
            raise
        finally:
            STATS["image"]["active"] -= 1
    if provider not in (None, "cli_proxy"):
        raise ApiError("Unknown image provider")
    size, ratio = ASPECTS.get(aspect, ASPECTS["16:9"])
    model = model or config.get("IMAGE_MODEL")
    if not model:
        raise ApiError("Choose an image model in private configuration")

    async def once() -> bytes:
        if refs:
            files = [("image[]", (f"ref{i}.png", b, "image/png")) for i, b in enumerate(refs)]
            data = {"model": model, "prompt": prompt, "size": size, "aspect_ratio": ratio}
            r = await client().post(_url("/images/edits"), data=data, files=files, headers=_headers(), timeout=600)
        else:
            payload = {"model": model, "prompt": prompt, "size": size, "aspect_ratio": ratio, "n": 1}
            r = await client().post(_url("/images/generations"), json=payload, headers=_headers(), timeout=600)
        return await _image_bytes_from(r)

    async def once_bounded() -> bytes:
        try:
            return await asyncio.wait_for(once(), 360)
        except asyncio.TimeoutError:
            raise ApiError("image: no response in 360s", retryable=True)

    async def hedged() -> bytes:
        """Image anormalement lente (> 150 s) : une jumelle part sur un autre compte."""
        first = asyncio.create_task(once_bounded())
        done, _ = await asyncio.wait({first}, timeout=150)
        if first in done:
            return first.result()
        STATS["image"]["hedges"] = STATS["image"].get("hedges", 0) + 1
        events.log(f"⏳ {label} : slow (> 150 s) — a twin is sent on another account", "warn")
        pending = {first, asyncio.create_task(once_bounded())}
        err: BaseException | None = None
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    if t.exception() is None:
                        return t.result()
                    err = t.exception()
            raise err
        finally:
            for t in pending:
                t.cancel()

    async with sem("image"):
        STATS["image"]["active"] += 1
        t0 = time.time()
        try:
            out = await _with_retry("image", hedged, attempts, label)
            STATS["image"]["done"] += 1
            STATS["image"]["total_seconds"] += time.time() - t0
            return out
        except Exception:
            STATS["image"]["errors"] += 1
            raise
        finally:
            STATS["image"]["active"] -= 1


def png_for_upload(path, max_side: int = 1536) -> bytes:
    """Charge une image locale et la ré-encode en PNG raisonnable pour l'envoyer en référence."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def stats() -> dict:
    img = STATS["image"]
    avg = img["total_seconds"] / img["done"] if img["done"] else None
    return {
        "llm": dict(STATS["llm"]),
        "image": {k: v for k, v in img.items() if k != "total_seconds"} | {"avg_seconds": avg},
        "limits": {"image": config.get_int("IMAGE_CONCURRENCY"), "llm": config.get_int("LLM_CONCURRENCY")},
    }
