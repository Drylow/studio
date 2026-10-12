"""Serveur web local (FastAPI) : API + interface façon TubeGen."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import channels, config, events, llm, local_tts, pipeline, planner, shorts, store, thumbstudio, tts, youtube
from .steps import script as script_step
from .steps import visuals

log = logging.getLogger("tubeforge.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.reset_stale_running()
    events.log(f"Serveur prêt — ouvre http://localhost:{config.get_int('PORT')} · proxy "
               f"{config.get('PROXY_BASE_URL')} · {config.get_int('IMAGE_CONCURRENCY')} images en parallèle · "
               f"ElevenLabs {'OK' if config.get('ELEVENLABS_API_KEY') else 'non configuré'}", "step")
    yield


app = FastAPI(title="TubeForge", lifespan=lifespan)


@app.middleware("http")
async def no_cache_ui(request, call_next):
    """L'interface est toujours revalidée : une mise à jour du code est visible sans vider le cache."""
    resp = await call_next(request)
    if request.url.path in ("/", "/index.html", "/legacy.html", "/app.js", "/style.css", "/workspace.js", "/workspace.css"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def _project(pid: str) -> dict:
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "Projet introuvable")
    return p


def _scene(p: dict, sid: int) -> dict:
    for s in p["scenes"]:
        if s["id"] == sid:
            return s
    raise HTTPException(404, "Scène introuvable")


def _start(pid: str, fn, *args) -> dict:
    try:
        pipeline.start(pid, fn, *args)
    except pipeline.Busy as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


def _deep_merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def summary(p: dict) -> dict:
    f = store.features(p)
    return {
        "id": p["id"], "title": p.get("title") or "(titre en cours…)", "created": p["created"],
        "updated": p.get("updated"), "archived": p.get("archived", False), "mode": p.get("mode"),
        "style_name": p.get("style_name"), "features": f, "thumb": store.thumbnail_path(p),
        "steps": p["steps"], "running": pipeline.is_running(p["id"]), "error": p.get("error"),
        "duration": (p.get("voiceover") or {}).get("duration"), "scenes": len(p.get("scenes") or []),
        "render": p.get("render"),
        "last_log": (p.get("log") or [{}])[-1].get("m"),
        "format": p.get("format", "long"), "kind": (p.get("short") or {}).get("kind"), "parent_id": p.get("parent_id"),
        "channel_id": p.get("channel_id"), "slot": (p.get("post") or {}).get("slot"),
        "posted": bool((p.get("post") or {}).get("posted")),
    }


def full(p: dict) -> dict:
    out = {k: v for k, v in p.items() if k not in ("script_history", "video_context")}
    out["script_history"] = [{k: v for k, v in h.items() if k != "text"} for h in p.get("script_history", [])]
    out["video_context_words"] = len((p.get("video_context") or "").split())
    out["running"] = pipeline.is_running(p["id"])
    out["features"] = store.features(p)
    return out


# ------------------------------------------------------------------ état / réglages

@app.get("/api/state")
async def state():
    from . import studio_bridge
    return {"stats": llm.stats(), "running": pipeline.running_ids(),
            "has_algrow": studio_bridge.algrow_configured(),
            "has_elevenlabs": bool(config.get("ELEVENLABS_API_KEY")),
            "has_proxy": bool(config.get("PROXY_API_KEY"))}


@app.get("/api/settings")
async def get_settings():
    return config.public_settings()


@app.put("/api/settings")
async def put_settings(body: dict):
    changes = {k: str(v).strip() for k, v in body.items() if k in config.DEFAULTS and "…" not in str(v)
               and str(v).strip() != "•••"}
    config.update(changes)
    llm.reset_limits()
    return config.public_settings()


@app.get("/api/elevenlabs/voices")
async def eleven_voices():
    try:
        return await tts.eleven_voices()
    except tts.TTSError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ voix locale (Chatterbox, carte AMD)

@app.get("/api/local-tts")
async def local_tts_status():
    return {"installed": local_tts.installed(), "health": await local_tts.health(), "voices": local_tts.list_voices()}


@app.post("/api/local-tts/start")
async def local_tts_start(body: dict | None = None):
    pipeline.start_side(local_tts.ensure_server((body or {}).get("engine") or "turbo"))
    return {"ok": True}


@app.post("/api/local-tts/voices")
async def local_tts_add_voice(name: str = Form(...), file: UploadFile = File(...)):
    """Ajoute une voix de référence (10 à 20 s de parole propre suffisent)."""
    import re as _re
    import tempfile
    safe = _re.sub(r'[\/:*?"<>|]+', "", name).strip()[:60] or "Ma voix"
    local_tts.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "x.wav").suffix) as tmp:
        tmp.write(await file.read())
    out = local_tts.VOICES_DIR / f"{safe}.wav"
    from .util import run_cmd
    try:
        await run_cmd([config.get("FFMPEG"), "-y", "-v", "error", "-i", tmp.name, "-t", "20", "-ac", "1", "-ar", "24000",
                       "-af", "loudnorm=I=-18:TP=-2", str(out)])
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    events.log(f"Voix locale ajoutée : {safe}", "ok")
    return local_tts.list_voices()


@app.delete("/api/local-tts/voices/{name}")
async def local_tts_del_voice(name: str):
    (local_tts.VOICES_DIR / Path(name).name).unlink(missing_ok=True)
    return local_tts.list_voices()


@app.get("/api/voices/gallery")
async def voices_gallery():
    return {"voices": local_tts.list_voices(), "texts": local_tts.SAMPLE_TEXT, "sampling": local_tts.sampling_status(),
            "installed": local_tts.installed()}


@app.post("/api/voices/gallery/samples")
async def voices_gallery_samples(body: dict | None = None):
    if local_tts.sampling_status()["running"]:
        return {"ok": True, "already": True}
    pipeline.start_side(local_tts.make_samples(bool((body or {}).get("force"))))
    return {"ok": True}


@app.get("/voice-sample/{name}")
async def voice_sample(name: str):
    return FileResponse(_safe(local_tts.SAMPLES_DIR, Path(name).name), headers={"Cache-Control": "no-cache"})


@app.get("/local-voice/{name}")
async def local_voice_file(name: str):
    return FileResponse(_safe(local_tts.VOICES_DIR, Path(name).name))


@app.post("/api/voice/preview")
async def voice_preview(body: dict):
    """Échantillon court avec les réglages actuels (voix locale ou Edge)."""
    import uuid as _uuid
    vs = dict(body.get("voice") or {})
    vs["language"] = body.get("language") or vs.get("language") or "English"
    text = (body.get("text") or "").strip()
    if not text:
        text = ("Tu as dix-neuf ans, et ce soir, tout bascule. Personne ne t'a prévenu." if vs["language"] == "French"
                else "You're nineteen years old, and tonight, everything changes. Nobody warned you.")
    text = text[:400]
    if vs.get("provider") == "algrow" and len(text) < 200:
        if body.get("text", "").strip():
            raise HTTPException(400, "Algrow demande au moins 200 caracteres pour un apercu vocal")
        text = ("You wake before sunrise. Outside, footsteps move along the narrow street, and a merchant opens "
                "his shutters. By the river, workers unload the first baskets of the day. The city is already "
                "awake, and your morning has only just begun." if vs["language"] != "French" else
                "Tu te leves avant le soleil. Dehors, des pas traversent la rue et un marchand ouvre ses volets. "
                "Au bord de la riviere, les porteurs dechargent les premiers paniers. La ville est deja reveillee, "
                "mais ta journee commence a peine.")
    out_dir = config.DATA / "previews"
    out_dir.mkdir(exist_ok=True)
    for old in sorted(f for f in out_dir.glob("*") if f.is_file())[:-20]:
        old.unlink(missing_ok=True)
    try:
        if vs.get("provider") == "local":
            engine = local_tts.engine_for(vs)
            await local_tts.ensure_server(engine)
            data = await local_tts.synth(text, vs["language"], vs.get("local_voice") or local_tts.default_voice(vs["language"]),
                                         float(vs.get("local_exaggeration", 0.5)), float(vs.get("local_cfg", 0.5)),
                                         float(vs.get("local_temperature", 0.8)), engine=engine)
            name = f"{_uuid.uuid4().hex[:8]}.wav"
        else:
            tmp = out_dir / f"_{_uuid.uuid4().hex[:6]}"
            tmp.mkdir()
            res = await tts.synthesize(text, vs, tmp)
            data = (tmp / res["file"]).read_bytes()
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
            name = f"{_uuid.uuid4().hex[:8]}.mp3"
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Aperçu impossible : {e}")
    (out_dir / name).write_bytes(data)
    return {"url": f"/preview-audio/{name}"}


@app.get("/preview-audio/{name}")
async def preview_audio(name: str):
    return FileResponse(_safe(config.DATA / "previews", Path(name).name))


@app.get("/api/youtube/transcript")
async def yt_transcript(url: str):
    try:
        text = await youtube.transcript(url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Transcription indisponible : {e}")
    return {"text": text, "words": len(text.split())}


# ------------------------------------------------------------------ styles

@app.get("/api/styles")
async def styles():
    return store.list_styles()


@app.post("/api/styles")
async def create_style(body: dict):
    base = store.get_style(body["base_id"]) if body.get("base_id") else None
    return store.new_style(body.get("name") or "Nouveau style", base)


@app.get("/api/styles/{sid}")
async def get_style(sid: str):
    s = store.get_style(sid)
    if not s:
        raise HTTPException(404, "Style introuvable")
    return s


@app.put("/api/styles/{sid}")
async def put_style(sid: str, body: dict):
    s = store.get_style(sid)
    if not s:
        raise HTTPException(404, "Style introuvable")
    body.pop("id", None)
    _deep_merge(s, body)
    return store.save_style(s)


@app.delete("/api/styles/{sid}")
async def del_style(sid: str):
    if len(store.list_styles()) <= 1:
        raise HTTPException(400, "Impossible de supprimer le dernier style")
    store.delete_style(sid)
    return {"ok": True}


@app.post("/api/styles/{sid}/refs")
async def add_style_ref(sid: str, file: UploadFile = File(...)):
    s = store.get_style(sid)
    d = store.style_dir(sid) / "refs"
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.glob("*"))) + 1
    path = d / f"ref{n}_{Path(file.filename or 'x').stem[:20]}.png"
    Image.open(file.file).convert("RGB").save(path)
    s["visuals"]["style_refs"].append(f"refs/{path.name}")
    return store.save_style(s)


@app.delete("/api/styles/{sid}/refs/{name}")
async def del_style_ref(sid: str, name: str):
    s = store.get_style(sid)
    s["visuals"]["style_refs"] = [r for r in s["visuals"]["style_refs"] if Path(r).name != name]
    (store.style_dir(sid) / "refs" / name).unlink(missing_ok=True)
    return store.save_style(s)


@app.post("/api/styles/{sid}/references/youtube")
async def add_style_reference_youtube(sid: str, body: dict):
    s = store.get_style(sid)
    try:
        text = await youtube.transcript(body["url"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Transcription indisponible : {e}")
    s["script"]["references"].append({"title": body.get("title") or body["url"], "text": text})
    return store.save_style(s)


@app.post("/api/styles/{sid}/characters/{cid}/image")
async def style_character_image(sid: str, cid: str):
    s = store.get_style(sid)
    c = next((c for c in s["characters"] if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, "Personnage introuvable")
    fake = {"id": "_", "style_id": sid, "settings": {"visuals": s["visuals"]}}
    try:
        await visuals.generate_character_image(fake, c, owner_dir=store.style_dir(sid))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    return store.save_style(s)


# ------------------------------------------------------------------ projets

@app.get("/api/projects")
async def projects(archived: int = 0):
    return [summary(p) for p in store.list_projects(bool(archived))]


@app.post("/api/projects")
async def create_project(body: dict):
    overrides = {}
    if body.get("word_count"):
        overrides["script.word_count"] = int(body["word_count"])
    if body.get("aspect"):
        overrides["visuals.aspect"] = body["aspect"]
    if body.get("language"):
        overrides["language"] = body["language"]
    p = store.create_project(body.get("title", ""), body.get("style_id") or store.list_styles()[0]["id"],
                             topic=body.get("topic", ""), video_url=body.get("video_url", ""),
                             mode=body.get("mode", "auto"), custom_script=body.get("custom_script", ""),
                             overrides=overrides, characters=body.get("characters"))
    ch = channels.get(body.get("channel_id"))
    if body.get("format") != "short" and body.get("promo_shorts") is not None:
        p["auto_promo_shorts"] = max(0, min(3, int(body["promo_shorts"] or 0)))
        if ch:
            p["promo_channel"] = ch["id"]
        store.save_project(p)
    if body.get("format") == "short":
        shorts.apply_short_settings(p)
        if ch:
            channels.apply(p, ch)
            if body.get("language"):
                p["settings"]["language"] = body["language"]
            p["short"] = {"kind": "standalone"}
        if body.get("word_count"):
            p["settings"]["script"]["word_count"] = min(220, int(body["word_count"]))
        store.save_project(p)
        if ch:
            planner.assign(ch)
    if body.get("auto_run", True):
        pipeline.start(p["id"], pipeline.run_all, p["mode"])
    return full(p)


@app.get("/api/projects/{pid}")
async def get_project(pid: str):
    return full(_project(pid))


@app.patch("/api/projects/{pid}")
async def patch_project(pid: str, body: dict):
    p = _project(pid)
    for k in ("title", "mode", "archived", "topic", "video_url"):
        if k in body:
            p[k] = body[k]
            if k == "title":
                p["title_auto"] = False
            if k == "video_url":
                p["video_context"] = ""
    if "settings" in body:
        _deep_merge(p["settings"], body["settings"])
    return full(store.save_project(p))


@app.delete("/api/projects/{pid}")
async def delete_project(pid: str):
    pipeline.stop(pid)
    store.delete_project(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/shorts")
async def make_shorts(pid: str, body: dict | None = None):
    """Tire 1 à 3 shorts TikTok d'une longue vidéo (nouveaux projets lancés automatiquement)."""
    p = _project(pid)
    count = max(1, min(3, int((body or {}).get("count") or 2)))
    mode = (body or {}).get("mode") or "auto"
    kind = "standalone" if (body or {}).get("kind") == "standalone" else "promo"
    ch = channels.get((body or {}).get("channel_id"))

    async def job():
        try:
            created = await shorts.shorts_from_long(p, count, mode, kind=kind, channel=ch)
            for sp in created:
                pipeline.start(sp["id"], pipeline.run_all, mode)
        except Exception as e:  # noqa: BLE001
            events.log(f"✗ Shorts : {e}", "error", p)
            store.save_project(p)
    pipeline.start_side(job(), p)
    return {"ok": True}


@app.post("/api/projects/{pid}/duplicate")
async def duplicate(pid: str):
    _project(pid)
    return summary(store.duplicate_project(pid))


@app.post("/api/projects/{pid}/run")
async def run(pid: str, body: dict | None = None):
    p = _project(pid)
    mode = (body or {}).get("mode") or p.get("mode")
    # En mode relecture, « continuer » valide les prompts seulement s'ils existent déjà (donc déjà relus)
    if (body or {}).get("approve") and p.get("scenes") and all(s.get("prompt") for s in p["scenes"]):
        p["prompts_approved"] = True
    return _start(pid, pipeline.run_all, mode)


@app.post("/api/projects/{pid}/stop")
async def stop(pid: str):
    return {"stopped": pipeline.stop(pid)}


# --- script

@app.post("/api/projects/{pid}/script/generate")
async def gen_script(pid: str):
    _project(pid)
    return _start(pid, pipeline.do_script)


@app.put("/api/projects/{pid}/script")
async def put_script(pid: str, body: dict):
    p = _project(pid)
    text = body.get("text", "")
    if text != p.get("script"):
        p["script"] = text
        store.add_history(p, "edit", text)
        p["steps"]["script"]["state"] = "done" if text.strip() else "idle"
        if p.get("voiceover"):
            p["voiceover_stale"] = True
        store.save_project(p)
    return full(p)


@app.post("/api/projects/{pid}/script/selection")
async def script_selection(pid: str, body: dict):
    p = _project(pid)
    try:
        await script_step.rewrite_selection(p, int(body["start"]), int(body["end"]), body.get("action", "adjust"),
                                            body.get("instruction", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if p.get("voiceover"):
        p["voiceover_stale"] = True
        store.save_project(p)
    return full(p)


@app.get("/api/projects/{pid}/script/history")
async def script_history(pid: str):
    return _project(pid).get("script_history", [])


@app.post("/api/projects/{pid}/script/restore")
async def script_restore(pid: str, body: dict):
    p = _project(pid)
    h = p["script_history"][int(body["index"])]
    p["script"] = h["text"]
    store.add_history(p, "restore", h["text"])
    if p.get("voiceover"):
        p["voiceover_stale"] = True
    return full(store.save_project(p))


@app.post("/api/projects/{pid}/title/generate")
async def gen_title(pid: str):
    p = _project(pid)
    p["title"] = await script_step.generate_title(p)
    return full(store.save_project(p))


@app.post("/api/projects/{pid}/context/fetch")
async def fetch_context(pid: str, body: dict):
    p = _project(pid)
    p["video_url"] = body.get("url", p.get("video_url", ""))
    try:
        p["video_context"] = await youtube.transcript(p["video_url"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Transcription indisponible : {e}")
    return full(store.save_project(p))


# --- voix

@app.post("/api/projects/{pid}/voiceover/generate")
async def gen_voice(pid: str):
    _project(pid)
    return _start(pid, pipeline.do_voiceover)


# --- visuels

@app.post("/api/projects/{pid}/visuals/prompts")
async def gen_prompts(pid: str, body: dict | None = None):
    p = _project(pid)
    only_missing = not (body or {}).get("all")
    if not only_missing:
        p["bible"] = None
        for s in p["scenes"]:
            s["prompt"] = ""
    return _start(pid, pipeline.do_prompts, only_missing)


@app.post("/api/projects/{pid}/visuals/images")
async def gen_images(pid: str, body: dict | None = None):
    p = _project(pid)
    scope = (body or {}).get("scope", "all")
    ids = None
    if scope == "next10":
        ids = [s["id"] for s in p["scenes"] if not s.get("image")][:10]
    elif scope == "failed":
        ids = [s["id"] for s in p["scenes"] if s.get("status") == "error"]
    elif scope == "ids":
        ids = [int(x) for x in body.get("ids", [])]
    return _start(pid, pipeline.do_images, ids)


@app.post("/api/projects/{pid}/visuals/resplit")
async def resplit(pid: str, body: dict | None = None):
    p = _project(pid)
    if pipeline.is_running(pid):
        raise HTTPException(409, "Une génération est en cours")
    for k in ("avg_scene_seconds", "min_scene_seconds", "max_scene_seconds"):
        if body and body.get(k) is not None:
            p["settings"]["visuals"][k] = float(body[k])
    try:
        pipeline.resplit(p)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return full(p)


@app.put("/api/projects/{pid}/scenes/{sid}")
async def put_scene(pid: str, sid: int, body: dict):
    p = _project(pid)
    s = _scene(p, sid)
    for k in ("prompt", "motion", "characters", "image_model"):
        if k in body:
            s[k] = body[k]
    return store.save_project(p) and s


@app.post("/api/projects/{pid}/scenes/{sid}/regenerate")
async def regen_scene(pid: str, sid: int, body: dict):
    p = _project(pid)
    s = _scene(p, sid)
    if p.get("codex_directed"):
        raise HTTPException(409, "Correction dirigee par Codex : conserver le prompt et les references explicites")
    mode = body.get("mode", "same")
    if s.get("status") == "running":
        raise HTTPException(409, "Cette scène est déjà en cours")
    s["status"] = "queued"
    store.save_project(p)

    if mode == "custom":
        if not (body.get("prompt") or "").strip():
            raise HTTPException(400, "Écris un prompt")
        s["prompt"] = body["prompt"].strip()
        s["critique"] = ""

    async def job():
        try:
            if mode == "full":
                await visuals.rewrite_scene_prompt(p, s)
            elif mode == "fix":
                await visuals.critique_and_fix(p, s, body.get("instruction", ""))
            # une image refaite à la main garde le lien avec la précédente (même univers)
            use_prev = None if mode in ("same", "adjust") else (visuals.continuity_mode(p) != "off")
            await visuals.generate_scene_image(p, s, body.get("instruction") if mode == "adjust" else None,
                                               use_prev=use_prev)
        except Exception as e:  # noqa: BLE001
            log.warning("scène %s : %s", sid, e)
        finally:
            store.save_project(p)
    pipeline.start_side(job(), p)
    return s


@app.post("/api/projects/{pid}/scenes/{sid}/upload")
async def upload_scene(pid: str, sid: int, file: UploadFile = File(...)):
    p = _project(pid)
    s = _scene(p, sid)
    pdir = store.project_dir(pid)
    rel = visuals._next_image_name(pdir, s)
    (pdir / rel).parent.mkdir(parents=True, exist_ok=True)
    Image.open(file.file).convert("RGB").save(pdir / rel)
    s.update(image=rel, status="done", error=None, uploaded=True)
    store.save_project(p)
    return s


@app.delete("/api/projects/{pid}/scenes/{sid}")
async def delete_scene(pid: str, sid: int):
    p = _project(pid)
    idx = next((i for i, s in enumerate(p["scenes"]) if s["id"] == sid), None)
    if idx is None:
        raise HTTPException(404, "Scène introuvable")
    if len(p["scenes"]) == 1:
        raise HTTPException(400, "Impossible de supprimer la dernière scène")
    s = p["scenes"].pop(idx)
    if idx > 0:  # fusion avec la précédente pour garder le timing
        prev = p["scenes"][idx - 1]
        prev["end"], prev["text"] = s["end"], (prev["text"] + " " + s["text"]).strip()
    else:
        nxt = p["scenes"][0]
        nxt["start"], nxt["text"] = s["start"], (s["text"] + " " + nxt["text"]).strip()
    p["render"] = None
    return full(store.save_project(p))


# --- personnages

@app.post("/api/projects/{pid}/characters")
async def add_character(pid: str, body: dict):
    p = _project(pid)
    cid = (body.get("name") or "perso").lower().replace(" ", "_")[:30]
    while any(c["id"] == cid for c in p["characters"]):
        cid += "_2"
    c = {"id": cid, "name": body.get("name", cid), "description": body.get("description", ""),
         "image": None, "every_image": bool(body.get("every_image")), "enabled": True, "source": "manual"}
    p["characters"].append(c)
    store.save_project(p)
    if body.get("generate_image", True) and c["description"]:
        async def job():
            await visuals.ensure_character_images(p, [c])
        pipeline.start_side(job(), p)
    return full(p)


@app.post("/api/projects/{pid}/characters/from-style")
async def add_character_from_style(pid: str, body: dict):
    p = _project(pid)
    try:
        return full(store.add_style_character(p, body["id"]))
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.put("/api/projects/{pid}/characters/{cid}")
async def put_character(pid: str, cid: str, body: dict):
    p = _project(pid)
    c = next((c for c in p["characters"] if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, "Personnage introuvable")
    for k in ("name", "description", "every_image", "enabled"):
        if k in body:
            c[k] = body[k]
    return full(store.save_project(p))


@app.post("/api/projects/{pid}/characters/detect")
async def detect_characters(pid: str):
    p = _project(pid)
    if not p.get("script"):
        raise HTTPException(400, "Il faut un script pour détecter les personnages")
    return _start(pid, pipeline.do_detect_characters)


@app.delete("/api/projects/{pid}/characters/{cid}")
async def del_character(pid: str, cid: str):
    p = _project(pid)
    p["characters"] = [c for c in p["characters"] if c["id"] != cid]
    for s in p["scenes"]:
        s["characters"] = [x for x in s.get("characters") or [] if x != cid]
    return full(store.save_project(p))


@app.post("/api/projects/{pid}/characters/{cid}/image")
async def character_image(pid: str, cid: str):
    p = _project(pid)
    c = next((c for c in p["characters"] if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, "Personnage introuvable")
    async def job():
        await visuals.ensure_character_images(p, [c])
    c["status"] = "running"
    store.save_project(p)
    pipeline.start_side(job(), p)
    return full(p)


# --- rendu & miniatures

@app.post("/api/projects/{pid}/render")
async def render(pid: str):
    _project(pid)
    return _start(pid, pipeline.do_render)


@app.post("/api/projects/{pid}/resolve")
async def to_resolve(pid: str, body: dict | None = None):
    _project(pid)
    return _start(pid, pipeline.do_resolve, bool((body or {}).get("render", True)))


@app.post("/api/projects/{pid}/thumbnails")
async def thumbnails(pid: str, body: dict | None = None):
    p = _project(pid)
    b = body or {}

    async def job():
        try:
            await pipeline.do_thumbnails(p, b.get("count") or 2, b.get("instruction", ""))
        except Exception as e:  # noqa: BLE001
            log.warning("miniatures : %s", e)
    pipeline.start_side(job(), p)
    return {"ok": True}


@app.post("/api/projects/{pid}/thumbnails/select")
async def select_thumb(pid: str, body: dict):
    p = _project(pid)
    p["thumbnail_selected"] = int(body["index"])
    return full(store.save_project(p))


# ------------------------------------------------------------------ studio miniatures

def _tset(sid: str) -> dict:
    s = thumbstudio.get_set(sid)
    if not s:
        raise HTTPException(404, "Série introuvable")
    return s


def _titem(s: dict, iid: str) -> dict:
    it = next((i for i in s["items"] if i["id"] == iid), None)
    if not it:
        raise HTTPException(404, "Miniature introuvable")
    return it


@app.get("/api/thumbstudio")
async def ts_list():
    return thumbstudio.list_sets()


@app.post("/api/thumbstudio")
async def ts_create(title: str = Form(""), idea: str = Form(""), text: str = Form(""), count: int = Form(4),
                    style_id: str = Form(""), aspect: str = Form("16:9"), style_text: str = Form(""),
                    file: UploadFile | None = File(None)):
    if not (title.strip() or idea.strip()):
        raise HTTPException(400, "Donne au moins un titre ou une idée")
    ref = None
    if file is not None and file.filename:
        import io
        buf = io.BytesIO()
        Image.open(file.file).convert("RGB").save(buf, "PNG")
        ref = buf.getvalue()
    s = thumbstudio.create(title, idea, text, count, style_id, aspect, style_text, ref)
    pipeline.start_side(thumbstudio.generate(s))
    return s


@app.post("/api/thumbstudio/{sid}/more")
async def ts_more(sid: str, body: dict | None = None):
    s = _tset(sid)
    pipeline.start_side(thumbstudio.generate(s, int((body or {}).get("count") or 2)))
    return s


@app.post("/api/thumbstudio/{sid}/items/{iid}/edit")
async def ts_edit(sid: str, iid: str, body: dict):
    s = _tset(sid)
    it = _titem(s, iid)
    if not it.get("file"):
        raise HTTPException(400, "Cette miniature n'a pas encore d'image")
    pipeline.start_side(thumbstudio.edit(s, it, body.get("instruction", "")))
    return s


@app.post("/api/thumbstudio/{sid}/items/{iid}/variations")
async def ts_var(sid: str, iid: str, body: dict | None = None):
    s = _tset(sid)
    pipeline.start_side(thumbstudio.variations(s, _titem(s, iid), int((body or {}).get("count") or 2)))
    return s


@app.post("/api/thumbstudio/{sid}/items/{iid}/to-project")
async def ts_to_project(sid: str, iid: str, body: dict):
    s = _tset(sid)
    _project(body["project_id"])
    return summary(thumbstudio.to_project(s, _titem(s, iid), body["project_id"]))


@app.delete("/api/thumbstudio/{sid}/items/{iid}")
async def ts_del_item(sid: str, iid: str):
    s = _tset(sid)
    thumbstudio.delete_item(s, iid)
    return s


@app.delete("/api/thumbstudio/{sid}")
async def ts_del(sid: str):
    thumbstudio.delete_set(sid)
    return {"ok": True}


@app.get("/thumbstudio-media/{rel:path}")
async def ts_media(rel: str):
    return FileResponse(_safe(thumbstudio.DIR, rel), headers={"Cache-Control": "max-age=86400"})


@app.get("/thumbstudio-download/{rel:path}")
async def ts_download(rel: str):
    return FileResponse(_safe(thumbstudio.DIR, rel), filename=f"miniature-{rel.replace('/', '-')}")


# ------------------------------------------------------------------ chaînes + planning

def _channel(cid: str) -> dict:
    ch = channels.get(cid)
    if not ch:
        raise HTTPException(404, "Chaîne introuvable")
    return ch


@app.get("/api/channels")
async def list_channels():
    return [ch | {"plan": planner.summary(ch)} for ch in channels.list_channels()]


@app.post("/api/channels")
async def create_channel(body: dict):
    body = dict(body)
    body.pop("id", None)
    return channels.save(body)


@app.put("/api/channels/{cid}")
async def update_channel(cid: str, body: dict):
    old = _channel(cid)
    ch = channels.save(old | {k: v for k, v in body.items() if k != "id"})
    # heures ou premier jour changés : on replanifie tout ce qui n'est pas encore publié
    planner.assign(ch, reset=any(old.get(k) != ch.get(k) for k in ("post_times", "posts_per_day", "start_date")))
    return ch


@app.delete("/api/channels/{cid}")
async def delete_channel(cid: str):
    _channel(cid)
    channels.delete(cid)
    return {"ok": True}


@app.get("/api/channels/{cid}/plan")
async def channel_plan(cid: str):
    ch = _channel(cid)
    planner.assign(ch)
    return {"channel": ch, "summary": planner.summary(ch), "items": planner.items(ch)}


@app.post("/api/channels/{cid}/assign")
async def channel_assign(cid: str, body: dict | None = None):
    ch = _channel(cid)
    return {"assigned": planner.assign(ch, reset=bool((body or {}).get("reset")))}


@app.post("/api/channels/{cid}/export")
async def channel_export(cid: str):
    import asyncio
    return await asyncio.to_thread(planner.export, _channel(cid))


@app.post("/api/channels/{cid}/open")
async def channel_open(cid: str):
    import os
    d = planner.channel_dir(_channel(cid))
    d.mkdir(parents=True, exist_ok=True)
    os.startfile(str(d))  # noqa: S606 — ouvre le dossier dans l'explorateur de l'utilisateur
    return {"dir": str(d)}


@app.post("/api/channels/{cid}/clip")
async def channel_clip(cid: str, body: dict):
    """Clipping : lien YouTube ou vidéo TubeForge -> shorts pour cette chaîne (lancés tout de suite)."""
    ch = _channel(cid)
    url, pid = (body.get("url") or "").strip(), body.get("project_id")
    count = max(1, min(5, int(body.get("count") or 2)))
    kind = body.get("kind") if body.get("kind") in ("promo", "standalone") else ch["kind"]
    mode = body.get("mode") or "auto"
    if not url and not pid:
        raise HTTPException(400, "Donne un lien YouTube ou choisis une vidéo")
    p_long = _project(pid) if pid else None

    async def job():
        try:
            created = (await shorts.shorts_from_long(p_long, count, mode, kind=kind, channel=ch) if p_long
                       else await shorts.shorts_from_url(url, count, mode, kind=kind, channel=ch))
            for sp in created:
                pipeline.start(sp["id"], pipeline.run_all, mode)
        except Exception as e:  # noqa: BLE001
            events.log(f"✗ Clipping : {e}", "error", p_long)
            if p_long:
                store.save_project(p_long)
    pipeline.start_side(job(), p_long)
    return {"ok": True}


@app.post("/api/channels/{cid}/resolve-all")
async def channel_resolve_all(cid: str):
    """Monte dans Resolve tous les shorts prêts de la chaîne qui n'y sont pas encore (un par un)."""
    ch = _channel(cid)
    n = 0
    for it in planner.items(ch):
        p = store.get_project(it["id"])
        if it["status"] == "ready" and not it["resolve"] and not pipeline.is_running(p["id"]):
            pipeline.start(p["id"], pipeline.do_resolve, True)
            n += 1
    return {"started": n}


@app.post("/api/channels/{cid}/ideas")
async def channel_ideas(cid: str, body: dict | None = None):
    ch = _channel(cid)
    n = max(1, min(60, int((body or {}).get("count") or 30)))
    items = await shorts.ideas(ch, n, (body or {}).get("theme") or "")
    lines = ["title;context;channel"] + [f"{i['title'].replace(';', ',')};{i['context'].replace(';', ',')};{ch['id']}"
                                         for i in items]
    return {"ideas": items, "csv": "\n".join(lines)}


@app.post("/api/projects/{pid}/post")
async def project_posted(pid: str, body: dict):
    p = _project(pid)
    planner.set_posted(p, bool(body.get("posted", True)))
    return {"ok": True}


@app.post("/api/projects/{pid}/move")
async def project_move(pid: str, body: dict):
    planner.move(_project(pid), -1 if int(body.get("dir", 1)) < 0 else 1)
    return {"ok": True}


@app.post("/api/projects/{pid}/channel")
async def project_channel(pid: str, body: dict):
    """Rattache un short existant à une chaîne (ou l'en détache)."""
    p = _project(pid)
    ch = channels.get(body.get("channel_id"))
    if ch:
        p.setdefault("post", {}).pop("slot", None)
        channels.apply(p, ch)
        store.save_project(p)
        planner.assign(ch)
    else:
        p.pop("channel_id", None)
        p.pop("post", None)
        store.save_project(p)
    return full(p)


@app.post("/api/resolve/template")
async def resolve_template(body: dict | None = None):
    import asyncio

    from . import resolve_export
    if not resolve_export.installed():
        raise HTTPException(400, "DaVinci Resolve n'est pas installé")
    return await asyncio.to_thread(resolve_export.template, bool((body or {}).get("rebuild")))


# ------------------------------------------------------------------ batch

@app.post("/api/batch")
async def batch(file: UploadFile | None = File(None), mode: str = Form("auto"), style_id: str = Form(""),
                channel_id: str = Form(""), csv_text: str = Form(""), name: str = Form("")):
    raw = await file.read() if file else csv_text.encode("utf-8")
    rows = pipeline.parse_csv(raw)
    if not rows:
        raise HTTPException(400, "CSV vide ou illisible (il faut au moins une colonne 'title' ou 'source')")
    default_style = style_id or store.list_styles()[0]["id"]
    b, created = await pipeline.launch_batch(rows, mode, default_style,
                                             name or (file.filename if file else "") or "batch.csv",
                                             default_channel=channel_id or None)
    clips = sum(1 for r in rows if r.get("source"))
    return {"batch": b, "projects": [summary(p) for p in created], "clips": clips}


@app.get("/api/batches")
async def batches():
    out = []
    for b in pipeline.list_batches():
        ps = [store.get_project(pid) for pid in b["projects"]]
        out.append(b | {"projects": [summary(p) for p in ps if p]})
    return out


# ------------------------------------------------------------------ fichiers

def _safe(base: Path, rel: str) -> Path:
    path = (base / rel).resolve()
    if not str(path).startswith(str(base.resolve())) or not path.is_file():
        raise HTTPException(404, "Fichier introuvable")
    return path


@app.get("/media/{pid}/{rel:path}")
async def media(pid: str, rel: str):
    return FileResponse(_safe(store.project_dir(pid), rel), headers={"Cache-Control": "max-age=3600"})


@app.get("/style-media/{sid}/{rel:path}")
async def style_media(sid: str, rel: str):
    return FileResponse(_safe(store.style_dir(sid), rel))


@app.get("/download/{pid}")
async def download(pid: str, what: str = "video"):
    p = _project(pid)
    pdir = store.project_dir(pid)
    title = (p.get("render") or {}).get("download_name") or "video.mp4"
    if what == "srt":
        return FileResponse(_safe(pdir, "render/subtitles.srt"), filename=title.replace(".mp4", ".srt"))
    if what == "voice":
        return FileResponse(_safe(pdir, "voice.mp3"), filename=title.replace(".mp4", ".mp3"))
    if what == "thumb":
        rel = store.thumbnail_path(p)
        if not rel:
            raise HTTPException(404, "Pas de miniature")
        return FileResponse(_safe(pdir, rel), filename=title.replace(".mp4", ".png"))
    if what == "montage":
        f = pdir / "render" / "MONTAGE.md"
        if not f.exists():
            from . import montage_md
            montage_md.write(p)
        return FileResponse(f, filename=title.replace(".mp4", " - MONTAGE.md"))
    if what == "resolve":
        return FileResponse(_safe(pdir, "render/resolve_final.mp4"), filename=title.replace(".mp4", " (Resolve).mp4"))
    if what == "script":
        f = pdir / "script.txt"
        f.write_text(f"Title: {p.get('title', '')}\n\n{p.get('script', '')}", encoding="utf-8")
        return FileResponse(f, filename=title.replace(".mp4", ".txt"))
    return FileResponse(_safe(pdir, "render/final.mp4"), filename=title)


@app.get("/exemple.csv")
async def example_csv():
    return FileResponse(config.ROOT / "exemple.csv", filename="exemple.csv")


@app.get("/exemple_tiktok.csv")
async def example_tiktok_csv():
    return FileResponse(config.ROOT / "exemple_tiktok.csv", filename="exemple_tiktok.csv")


@app.exception_handler(Exception)
async def errors(request, exc):
    log.exception("Erreur API")
    return JSONResponse({"detail": str(exc)[:500]}, status_code=500)


from . import workspace_api
workspace_api.install(app)
from . import workspace_generation
workspace_generation.install(app)
from . import workspace_management
workspace_management.install(app)
from . import workspace_voice
workspace_voice.install(app)
from . import workspace_planning
workspace_planning.install(app)
from . import workspace_writing
workspace_writing.install(app)

app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
