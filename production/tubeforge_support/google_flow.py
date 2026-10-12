"""Image transport for connected Flow accounts; no prompt authoring or fallback."""
import asyncio
import base64
import hashlib
import io
from pathlib import Path
import re
import time
from urllib.parse import quote, urlparse

import httpx
from dotenv import dotenv_values
from PIL import Image

from . import config
from .workspace_composition import ratio_matches

BASE = "https://api.useapi.net/v1/google-flow"
_client = None
_semaphore = None
_references = {}
_upload_locks = {}
_accounts = None
_accounts_at = 0
_cursor = 0
_cooldowns = {}


class FlowError(Exception):
    def __init__(self, message, status=None, *, global_configuration_error=False):
        super().__init__(message)
        self.status = status
        self.global_configuration_error = global_configuration_error


def setting(key):
    value = config.get(key)
    if value:
        return value
    studio = config.get("STUDIO_ROOT")
    return dotenv_values(Path(studio) / ".env").get(key, "") if studio else ""


def configured():
    return bool(setting("USEAPI_API_KEY") and setting("USEAPI_IMAGE_MODEL"))


def client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20), follow_redirects=False)
    return _client


def reset():
    global _semaphore, _accounts, _accounts_at, _cursor
    _semaphore = None
    _accounts = None
    _accounts_at = 0
    _cursor = 0
    _references.clear()
    _upload_locks.clear()
    _cooldowns.clear()


def _error(response):
    # Never forward response bodies: they can contain session identifiers or keys.
    try:
        body = str(response.json())
    except ValueError:
        body = ""
    code = response.status_code
    missing_captcha_provider = "no captcha provider api keys configured" in body.lower()
    if missing_captcha_provider:
        text = ("Aucun fournisseur captcha n'est configuré dans useapi. "
                "Configurez un fournisseur captcha dans les paramètres du compte useapi "
                "et vérifiez ses crédits avant de relancer le lot.")
    elif "ZERO_BALANCE" in body:
        text = "Captcha credits exhausted: top up the captcha provider in useapi."
    elif "MODEL_ACCESS_DENIED" in body:
        text = "The selected Google account does not have access to the requested model."
    elif code == 401:
        text = "The useapi key is rejected."
    elif code == 402:
        text = "The useapi subscription has expired or its credits are insufficient."
    elif code == 429:
        text = "Google Flow quota or rate limit reached. Try again after the delay indicated by useapi."
        delay = response.headers.get("Retry-After", "")
        if delay.isdigit():
            text += f" Attente : {delay} secondes."
    elif code == 596:
        text = "The Google session must be reconnected in useapi."
    else:
        text = f"Google Flow is unavailable or refused the request (HTTP {code})."
    return FlowError(text, code, global_configuration_error=missing_captcha_provider)


async def _get(path):
    response = await client().get(BASE + path, timeout=15, headers={"Authorization": "Bearer " + setting("USEAPI_API_KEY")})
    if response.status_code != 200:
        raise _error(response)
    return response.json()


async def status(force=False):
    global _accounts, _accounts_at
    if not configured():
        return {"configured": False, "available": False, "accounts": [], "error": "Configure the useapi key and image model in the studio .env."}
    try:
        if force or _accounts is None or time.monotonic() - _accounts_at > 20:
            data = await _get("/accounts")
            if not isinstance(data, dict):
                raise ValueError("Invalid account list")
            _accounts = [{"email": email, "health": "OK" if item.get("health") == "OK" else "error",
                          "backend": item.get("backend") if item.get("backend") in ("flow", "labs") else "unknown"}
                         for email, item in data.items() if isinstance(item, dict) and isinstance(email, str) and "@" in email]
            _accounts_at = time.monotonic()
        return {"configured": True, "available": any(a["health"] == "OK" for a in _accounts),
                "accounts": list(_accounts), "error": None if any(a["health"] == "OK" for a in _accounts) else "No connected and available Google Flow account."}
    except (httpx.HTTPError, ValueError, FlowError) as error:
        return {"configured": True, "available": False, "accounts": [],
                "error": str(error) if isinstance(error, FlowError) else "Connexion useapi indisponible."}


async def _account():
    global _cursor
    state = await status()
    healthy = [a["email"] for a in state["accounts"] if a["health"] == "OK" and _cooldowns.get(a["email"], 0) <= time.monotonic()]
    if not healthy:
        raise FlowError(state["error"] or "No Google Flow account available; check sessions and quotas.")
    account = healthy[_cursor % len(healthy)]
    _cursor += 1
    return account


async def _upload(account, payload):
    digest = hashlib.sha256(payload).hexdigest()
    key = (account, digest)
    async with _upload_locks.setdefault(key, asyncio.Lock()):
        if key in _references:
            return _references[key]
        with Image.open(io.BytesIO(payload)) as image:
            content_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
            image.verify()
        if not content_type or len(payload) > 20 * 1024 * 1024:
            raise FlowError("A reference exceeds the allowed size or uses an unsupported format.")
        response = await client().post(BASE + "/assets/" + quote(account, safe=""), content=payload,
                                       headers={"Authorization": "Bearer " + setting("USEAPI_API_KEY"), "Content-Type": content_type})
        if response.status_code != 200:
            _cooldown(account, response)
            raise _error(response)
        ref = response.json().get("mediaGenerationId", {}).get("mediaGenerationId")
        if not isinstance(ref, str) or not ref:
            raise FlowError("useapi did not return the reference identifier.")
        _references[key] = ref
        return ref


def _cooldown(account, response):
    if response.status_code == 429:
        delay = response.headers.get("Retry-After", "1800")
        _cooldowns[account] = time.monotonic() + (int(delay) if delay.isdigit() else 1800)


async def generate(prompt, model, aspect, refs=None, receipt=None):
    global _semaphore
    if not configured():
        raise FlowError("Google Flow is not configured in the studio.")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,100}", model):
        raise FlowError("The Google Flow model must be specified explicitly.")
    if aspect not in ("16:9", "9:16", "1:1", "4:3", "3:4"):
        raise FlowError("Format d'image Google Flow non pris en charge.")
    refs = refs or []
    if len(refs) > 10:
        raise FlowError("Google Flow accepts a maximum of 10 references: none will be removed automatically.")
    if _semaphore is None:
        try:
            limit = int(setting("USEAPI_IMAGE_CONCURRENCY") or 3)
        except ValueError:
            limit = 3
        _semaphore = asyncio.Semaphore(max(1, min(limit, 3)))
    async with _semaphore:
        account = await _account()
        body = {"email": account, "prompt": prompt, "model": model, "aspectRatio": aspect, "count": 1}
        started = time.monotonic()
        try:
            for number, payload in enumerate(refs, 1):
                body[f"reference_{number}"] = await _upload(account, payload)
            # One POST only. No hedge, replay after timeout, model switch or proxy fallback.
            response = await client().post(BASE + "/images", json=body,
                                           headers={"Authorization": "Bearer " + setting("USEAPI_API_KEY")})
            if response.status_code != 200:
                _cooldown(account, response)
                raise _error(response)
            result = response.json()
            media = result.get("media", [])
            if len(media) != 1:
                raise FlowError("useapi did not return exactly one image.")
            generated = media[0]["image"]["generatedImage"]
            if generated.get("encodedImage"):
                content = base64.b64decode(generated["encodedImage"], validate=True)
            elif generated.get("fifeUrl"):
                url = generated["fifeUrl"]
                if urlparse(url).scheme != "https":
                    raise FlowError("The image download link is invalid.")
                # Separate client: no useapi credential is sent to the media host.
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as download_client:
                    download = await download_client.get(url)
                    download.raise_for_status()
                    content = download.content
            else:
                raise FlowError("useapi n'a pas fourni de fichier image.")
            with Image.open(io.BytesIO(content)) as image:
                dimensions = list(image.size)
                image.verify()
            if receipt is not None:
                receipt.update(account=account, job_id=result.get("jobId"), dimensions=dimensions,
                               seconds=round(time.monotonic() - started, 2), count=1)
            if not ratio_matches(dimensions, aspect):
                raise FlowError("Google Flow returned an image in the wrong format. It is not selected; check the history before trying again.")
            return content
        except httpx.TimeoutException:
            raise FlowError("Google Flow timed out. Check the useapi history before restarting: an image may have been created.") from None
        except httpx.HTTPError:
            raise FlowError("Google Flow connection interrupted. Check the useapi history before restarting.") from None
        except (ValueError, KeyError, TypeError):
            raise FlowError("Unreadable Google Flow response. Check the useapi history before restarting.") from None
