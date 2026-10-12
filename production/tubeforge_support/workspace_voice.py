"""Narrate the exact supplied script without rewriting authored scenes."""
import asyncio
import copy
import math
from pathlib import Path
import uuid

import httpx
from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException

from app import config, pipeline, store, tts
from app.util import now
from . import workspace_api as api, workspace_generation as generation, workspace_management as management


def voice_settings(body):
    if not isinstance(body, dict):
        raise HTTPException(422, "Choose a voice")
    vid = api._text(body.get("voice_id"), "voice", required=True).strip()
    name = api._text(body.get("voice_name", vid), "voice name").strip()
    speed = body.get("speed", 1)
    if (len(vid) > 200 or any(c.isspace() for c in vid) or len(name) > 200
            or type(speed) not in (int, float) or not math.isfinite(speed) or not 0.7 <= speed <= 1.2):
        raise HTTPException(422, "Choose a voice and a speed between 0.7 and 1.2")
    provider = body.get("provider", "algrow")
    if provider not in ("algrow", "ai33"):
        raise HTTPException(422, "Choose Algrow or AI33 Pro with an ElevenLabs voice")
    if vid.startswith("elevenlabs_"):
        vid = vid[len("elevenlabs_"):]
    if "_" in vid:
        raise HTTPException(422, "Enter an ElevenLabs voice ID")
    return {"provider": provider, "voice_id": vid, "voice_name": name, "speed": speed}


def _key(provider="algrow"):
    root = config.get("STUDIO_ROOT")
    key = (dotenv_values(Path(root) / ".env").get("AI33_API_KEY" if provider == "ai33" else "ALGROW_API_KEY") if root else None)
    if not key:
        raise HTTPException(409, "Configure the studio voice connection")
    return key


def _writable(pid):
    p = api._project(pid, writable=True)
    if generation.batch_running(pid) or pid in generation._active_projects:
        raise HTTPException(409, "Wait for image generation to finish")
    return p


def _save_settings(p, voice):
    old = p["settings"].get("voice", {})
    changed = any(old.get(k) != voice[k] for k in ("provider", "voice_id", "speed"))
    p["settings"]["voice"] = dict(old, **voice)
    if changed and p.get("voiceover"):
        p["voiceover_stale"] = True
        p.setdefault("human_reviews", {}).pop("voiceover", None)
        p["human_reviews"].pop("render", None)
    store.save_project(p)


async def narrate(p):
    async def run(progress):
        script = p["script"]
        voice = dict(p["settings"]["voice"], language=p["settings"].get("language", "English"))
        folder = store.project_dir(p["id"]) / "voice-generations" / uuid.uuid4().hex
        folder.mkdir(parents=True)
        try:
            synthesize = tts.synthesize
            if voice["provider"] == "ai33":
                from . import studio_bridge
                synthesize = studio_bridge.voice
            result = await synthesize(script, voice, folder,
                progress=lambda d, t: progress(d, t, "Text-to-speech…"))
            duration = result.get("duration")
            if (type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0
                    or not api._file_digest(folder, result.get("file"))):
                raise ValueError("Missing narration output")
            # The job owns project edits; never replace any authored prompt or asset.
            if p["script"] != script:
                raise ValueError("Script changed during narration")
            previous = p.get("voiceover")
            if previous:
                p.setdefault("voiceover_history", []).append(copy.deepcopy(previous))
            store.save_words(p["id"], result.get("words") or [])
            p["voiceover"] = {"file": (folder / result["file"]).relative_to(store.project_dir(p["id"])).as_posix(),
                "duration": duration, "ts": now(), "provider": voice["provider"], "voice": voice["voice_name"],
                "voice_id": voice["voice_id"], "speed": voice["speed"], "script_hash": api._hash(script)}
            p["voiceover_stale"] = False
            if p.get("render"):
                p.setdefault("render_history", []).append(copy.deepcopy(p["render"]))
            p["render"] = None
            p.setdefault("human_reviews", {}).pop("voiceover", None)
            p["human_reviews"].pop("render", None)
            p["steps"]["render"] = {"state": "idle", "msg": "", "done": 0, "total": 0}
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError("Voice generation failed. The previous narration is kept; try again explicitly") from None
    await pipeline._step(p, "voiceover", run)


def install(app):
    if getattr(app.state, "workspace_voice_installed", False):
        return
    router = APIRouter(prefix="/api/workspace")

    @router.get("/voices")
    async def voices(search: str = "", language: str = "English", provider: str = "algrow"):
        if provider not in ("algrow", "ai33"):
            raise HTTPException(422, "Choose Algrow or AI33 Pro")
        key = _key(provider)
        langs = {"English": "en", "French": "fr", "Spanish": "es", "German": "de",
                 "Italian": "it", "Portuguese": "pt", "Japanese": "ja"}
        if len(search) > 200 or language not in langs:
            raise HTTPException(422, "Invalid search or language")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get("https://api.ai33.pro/v3/voices" if provider == "ai33" else "https://api.algrow.online/api/voices",
                    params={"search": search, "language": langs[language], "page_size": 60,
                            **({"provider": "elevenlabs"} if provider == "ai33" else {"sort": "trending"})},
                    headers={"Accept": "application/json", **({"xi-api-key": key} if provider == "ai33" else {"Authorization": "Bearer " + key})})
                response.raise_for_status()
                entries = response.json().get("data" if provider == "ai33" else "voices") or []
            return {"voices": [{"id": v["voice_id"].removeprefix("elevenlabs_"), "name": v.get("name") or v["voice_id"],
                "accent": v.get("accent", ""), "preview_url": v.get("preview_url")}
                for v in entries if isinstance(v, dict) and isinstance(v.get("voice_id"), str)]}
        except Exception:
            raise HTTPException(502, "The voice catalog is unavailable. Your saved voice remains usable") from None

    @router.put("/projects/{pid}/voice")
    async def save_voice(pid: str, body: dict):
        p = _writable(pid)
        _save_settings(p, voice_settings(body))
        return api._full(p)

    @router.post("/projects/{pid}/voice/channel-default")
    async def save_default(pid: str, body: dict):
        p = _writable(pid)
        voice = voice_settings(body)
        channel = management._channel(p.get("profile_id") or p.get("channel_id"))
        if not channel or channel.get("archived"):
            raise HTTPException(409, "The channel is no longer available")
        channel["voice"] = dict(channel.get("voice") or {}, **voice)
        channel["updated"] = now()
        management._save_channel(channel)
        _save_settings(p, voice)
        return api._full(p)

    @router.post("/projects/{pid}/voice/generate", status_code=202)
    async def generate_voice(pid: str, body: dict):
        p = _writable(pid)
        if not (p.get("script") or "").strip():
            raise HTTPException(409, "Paste and save the script before generating the voice")
        if body.get("script_hash") != api._hash(p["script"]):
            raise HTTPException(409, "The text has changed. Refresh the project before generating the voice")
        voice = voice_settings(body)
        _key(voice["provider"])
        _save_settings(p, voice)
        pipeline.start(pid, narrate)
        return api._full(p)

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_voice_installed = True
