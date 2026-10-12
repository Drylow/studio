"""Orchestration : exécute les étapes d'un projet, gère les tâches en cours et les batchs CSV."""
import asyncio
import csv
import io
import logging
import re
import traceback
import uuid

import contextvars
import time

from . import config, events, store, tts
from .steps import render as render_step
from .steps import scenes as scenes_step
from .steps import script as script_step
from .steps import thumbnails as thumbs_step
from .steps import visuals
from .util import now, read_json, write_json

log = logging.getLogger("tubeforge.pipeline")

_jobs: dict[str, asyncio.Task] = {}
_side_tasks: set[asyncio.Task] = set()
_project_slots: asyncio.Semaphore | None = None
BATCHES_FILE = config.DATA / "batches.json"


class Busy(Exception):
    pass


def project_slots() -> asyncio.Semaphore:
    global _project_slots
    if _project_slots is None:
        _project_slots = asyncio.Semaphore(max(1, config.get_int("PROJECT_PARALLEL")))
    return _project_slots


def is_running(pid: str) -> bool:
    t = _jobs.get(pid)
    return bool(t and not t.done())


def running_ids() -> list[str]:
    return [pid for pid, t in _jobs.items() if not t.done()]


def start(pid: str, fn, *args) -> None:
    """Lance fn(p, *args) en tâche de fond (une seule tâche principale par projet)."""
    if is_running(pid):
        raise Busy("A generation is already in progress on this project")
    _jobs[pid] = asyncio.create_task(_wrap(pid, fn, *args))


def start_side(coro, p: dict | None = None) -> None:
    """Petites tâches (une scène, un personnage) en parallèle de la tâche principale."""
    ctx = contextvars.copy_context()
    if p is not None:
        ctx.run(events.current.set, p)
    t = asyncio.create_task(coro, context=ctx)
    _side_tasks.add(t)
    t.add_done_callback(_side_tasks.discard)


async def _wrap(pid: str, fn, *args) -> None:
    p = store.get_project(pid)
    if not p:
        return
    p["error"] = None
    events.current.set(p)
    try:
        await fn(p, *args)
    except asyncio.CancelledError:
        events.log("■ Generation stopped", "warn")
        for st in p["steps"].values():
            if st["state"] == "running":
                st.update(state="error", msg="Stopped")
        for s in p.get("scenes") or []:
            if s.get("status") in ("queued", "running"):
                s["status"] = "idle"
        p["error"] = "Generation stopped"
    except Exception as e:  # noqa: BLE001
        log.debug("Projet %s : %s\n%s", pid, e, traceback.format_exc())
        events.log(f"✗ ERREUR : {str(e)[:400]}", "error")
        p["error"] = str(e)[:600]
    finally:
        store.save_project(p)


def stop(pid: str) -> bool:
    t = _jobs.get(pid)
    if t and not t.done():
        t.cancel()
        return True
    return False


def _progress(p: dict, key: str):
    def cb(done: int, total: int, msg: str = "") -> None:
        st = p["steps"][key]
        st["done"], st["total"] = done, total
        if msg:
            st["msg"] = msg
        visuals.save_throttled(p)
    return cb


STEP_NAMES = {"script": "Script", "voiceover": "Voiceover", "visuals": "Visuels", "render": "Rendu",
              "thumbnail": "Thumbnails", "resolve": "Montage DaVinci Resolve"}


async def _step(p: dict, key: str, coro_fn, *args, **kw):
    st = p["steps"].setdefault(key, {"state": "idle", "msg": "", "done": 0, "total": 0})
    t0 = time.time()
    st.update(state="running", msg="", done=0, total=0, started=t0)
    events.log(f"▶ {STEP_NAMES.get(key, key)}", "step")
    store.save_project(p)
    try:
        res = await coro_fn(*args, progress=_progress(p, key), **kw)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        st.update(state="error", msg=str(e)[:500])
        events.log(f"✗ {STEP_NAMES.get(key, key)} failed after {events.fmt_duration(time.time() - t0)}", "error")
        store.save_project(p)
        raise
    st.update(state="done", msg="", took=round(time.time() - t0))
    events.log(f"■ {STEP_NAMES.get(key, key)} completed in {events.fmt_duration(time.time() - t0)}", "step")
    store.save_project(p)
    return res


# ------------------------------------------------------------------ étapes

def _invalidate_after_script(p: dict) -> None:
    p["voiceover"], p["scenes"], p["render"], p["bible"] = None, [], None, None
    p["characters"] = [c for c in p.get("characters", []) if c.get("source") == "style"]
    for k in ("voiceover", "visuals", "render"):
        p["steps"][k] = {"state": "idle", "msg": "", "done": 0, "total": 0}
    p["voiceover_stale"] = False


async def do_script(p: dict) -> None:
    if p.get("codex_directed"):
        raise RuntimeError("Codex-led project: import a valid script, with no automatic rewrite")
    if p.get("script"):  # « Tout réécrire » : on repart de zéro ; sinon on reprend l'écriture interrompue
        p.pop("script_job", None)

    async def run(progress):
        await script_step.generate(p, progress=progress)
        _invalidate_after_script(p)
    await _step(p, "script", run)


async def do_voiceover(p: dict) -> None:
    if p.get("codex_directed"):
        raise RuntimeError("Codex-led project: import the valid narration and scene breakdown")
    if not p.get("script"):
        raise RuntimeError("Pas de script")

    async def run(progress):
        progress(0, 1, "Text-to-speech…")
        vs = dict(p["settings"]["voice"], language=p["settings"].get("language", "English"))
        res = await tts.synthesize(p["script"], vs, store.project_dir(p["id"]),
                                   progress=lambda d, t: progress(d, t, f"Voice {d}/{t} segments"))
        if (p.get("short") or {}).get("kind") == "promo":
            from .shorts import hold_tail
            res["duration"] = await hold_tail(store.project_dir(p["id"]) / res["file"])
        store.save_words(p["id"], res["words"])
        same_script = p.get("scenes") and p.get("scenes_script_hash") == scenes_step.script_hash(p["script"])
        if same_script and scenes_step.retime(p["scenes"], res["words"], res["duration"]):
            pass  # même texte : on garde scènes, prompts et images, seuls les timings changent
        else:
            _split_scenes(p, res["words"], res["duration"])
        p["voiceover"] = {"file": res["file"], "duration": res["duration"], "ts": now(),
                          "provider": p["settings"]["voice"].get("provider"),
                          "voice": (p["settings"]["voice"].get("voice_name") or p["settings"]["voice"].get("voice_id"))
                          if p["settings"]["voice"].get("provider") in ("elevenlabs", "algrow")
                          else (p["settings"]["voice"].get("local_voice") or "auto").removesuffix(".wav")
                          if p["settings"]["voice"].get("provider") == "local"
                          else p["settings"]["voice"].get("edge_voice")}
        p["voiceover_stale"] = False
        p["render"] = None
        p["steps"]["visuals"] = {"state": "idle", "msg": "", "done": 0, "total": 0}
        p["steps"]["render"] = {"state": "idle", "msg": "", "done": 0, "total": 0}
    await _step(p, "voiceover", run)


def _split_scenes(p: dict, words: list[dict], duration: float) -> None:
    v = p["settings"]["visuals"]
    sc = scenes_step.split(words, p["script"], duration, float(v.get("avg_scene_seconds", 6)),
                           float(v.get("min_scene_seconds", 2)), float(v.get("max_scene_seconds", 12)))
    p["scenes"] = [{"id": i + 1, "start": s["start"], "end": s["end"], "text": s["text"], "c0": s["c0"],
                    "c1": s["c1"], "prompt": "", "characters": [], "motion": None, "image": None,
                    "status": "idle", "error": None} for i, s in enumerate(sc)]
    p["scenes_script_hash"] = scenes_step.script_hash(p["script"])
    p["prompts_approved"] = False


def resplit(p: dict) -> None:
    """Redécoupe les scènes avec les durées actuelles (sans régénérer la voix)."""
    words = store.load_words(p["id"])
    if not words or not p.get("voiceover"):
        raise RuntimeError("A voice-over is needed to split the scenes")
    _split_scenes(p, words, p["voiceover"]["duration"])
    p["render"] = None
    p["steps"]["visuals"] = {"state": "idle", "msg": "", "done": 0, "total": 0}
    p["steps"]["render"] = {"state": "idle", "msg": "", "done": 0, "total": 0}
    store.save_project(p)


async def do_detect_characters(p: dict) -> None:
    if p.get("codex_directed"):
        raise RuntimeError("Project managed by Codex: characters and references chosen manually")
    from .steps import visuals as vis

    async def run(progress):
        progress(0, 1, "Reading the script and detecting characters…")
        added = await vis.detect_characters(p, max_n=8, generate_images=False)
        progress(0, len(added), f"{len(added)} character(s) found — creating profiles…")
        await vis.ensure_character_images(p, added)
        p["steps"]["visuals"]["msg"] = f"{len(added)} character(s) added — uncheck those you don\'t want to keep"
    await _step(p, "visuals", run)
    p["steps"]["visuals"]["msg"] = "Characters ready — uncheck those not to keep"
    store.save_project(p)


async def do_prompts(p: dict, only_missing: bool = True) -> None:
    if p.get("codex_directed"):
        raise RuntimeError("Codex-led project: import the valid prompts and references")
    if not p.get("scenes"):
        raise RuntimeError("Generate the voice-over first (the scenes depend on it)")
    await _step(p, "visuals", visuals.write_prompts, p, only_missing=only_missing)
    p["steps"]["visuals"]["msg"] = "Prompts ready — review them then generate the images"
    store.save_project(p)


async def do_images(p: dict, ids: list[int] | None = None, retry_failed: bool = True) -> None:
    if p.get("codex_directed"):
        raise RuntimeError("Codex-led project: use the reviewed images and their explicit references")
    if not p.get("scenes"):
        raise RuntimeError("No scenes")
    if any(not s.get("prompt") for s in p["scenes"] if ids is None or s["id"] in ids):
        await do_prompts(p)
    p["prompts_approved"] = True

    async def run(progress):
        await visuals.ensure_character_images(p)
        res = await visuals.generate_images(p, ids, progress=progress)
        if res["failed"] and retry_failed:
            failed = [s["id"] for s in p["scenes"] if s.get("status") == "error"]
            progress(0, len(failed), f"Nouvel essai de {len(failed)} image(s)…")
            res = await visuals.generate_images(p, failed, progress=progress)
        if res["failed"]:
            raise RuntimeError(f"{res['failed']} image(s) failed — see the scenes in red")
    await _step(p, "visuals", run)
    p["render"] = None if p.get("render") and ids is None else p.get("render")
    store.save_project(p)


async def do_render(p: dict) -> None:
    await _step(p, "render", render_step.render, p)
    from . import montage_md
    montage_md.write(p)


async def do_resolve(p: dict, render: bool = True) -> None:
    """Construit la timeline dans DaVinci Resolve (et y lance le rendu)."""
    from . import montage_md, resolve_export
    await _step(p, "resolve", resolve_export.export, p, render=render)
    montage_md.write(p)


async def do_thumbnails(p: dict, count: int | None = None, instruction: str = "") -> None:
    if p.get("codex_directed"):
        raise RuntimeError("Codex-led thumbnail: no automatic concept")
    await _step(p, "thumbnail", thumbs_step.generate, p, count=count, instruction=instruction)


async def run_all(p: dict, mode: str | None = None) -> None:
    """Pipeline complet. mode 'auto' = de A à Z ; 'review' = s'arrête pour relire les prompts et avant le rendu."""
    mode = mode or p.get("mode", "auto")
    t_all = time.time()
    if project_slots().locked():
        events.log(f"Queued ({config.get_int('PROJECT_PARALLEL')} videos max in parallel)…")
    async with project_slots():
        events.log(f"══ Starting ({'Auto' if mode == 'auto' else 'Relecture'}) ══", "step")
        if not p.get("script"):
            await do_script(p)
        if not p.get("title"):
            p["title"] = await script_step.generate_title(p)
            p["title_auto"] = True
            store.save_project(p)
        if p.get("format") == "short" and not (p.get("short") or {}).get("hook_text"):
            from . import shorts
            await shorts.write_meta(p)
        if not p.get("voiceover"):
            await do_voiceover(p)
            limit = ((p["settings"].get("shorts") or {}).get("target_seconds") or 90) + 15
            if p.get("format") == "short" and p["voiceover"]["duration"] > min(185, limit):
                events.log(f"⚠ Short trop long ({p['voiceover']['duration']:.0f} s > 90 s) : raccourcis le script "
                           "(sélection → Raccourcir) puis régénère la voix", "warn")
        if not p["scenes"] or any(not s.get("prompt") for s in p["scenes"]):
            await do_prompts(p)
        if mode == "review" and not p.get("prompts_approved"):
            p["steps"]["visuals"]["msg"] = "Waiting for your prompt review"
            store.save_project(p)
            return
        thumbs_needed = not p.get("thumbnails") and int(p["settings"]["thumbnail"].get("count", 0) or 0) > 0

        async def thumbs_safe():
            try:
                await do_thumbnails(p)
            except Exception as e:  # noqa: BLE001 — une miniature ratée ne bloque pas la vidéo
                log.warning("thumbnails %s: %s", p["id"], e)

        if any(not s.get("image") for s in p["scenes"]):
            await asyncio.gather(do_images(p), thumbs_safe() if thumbs_needed else asyncio.sleep(0))
        elif thumbs_needed:
            await thumbs_safe()
        if mode == "review":
            p["steps"]["render"]["msg"] = "Images ready — review them then start rendering"
            store.save_project(p)
            return
        await do_render(p)
        events.log(f"══ VIDEO COMPLETED in {events.fmt_duration(time.time() - t_all)} ══", "ok")
    from . import channels
    # short d'une chaîne : montage dans le projet Resolve de la chaîne (une seule timeline à la fois)
    ch = channels.get(p.get("channel_id"))
    if p.get("format") == "short" and ch and ch.get("auto_resolve") and p.get("render"):
        from . import resolve_export
        done = (p.get("resolve") or {}).get("render_status") == "Complete" and \
            (p.get("resolve") or {}).get("ts", 0) >= p["render"].get("ts", 0)
        if resolve_export.installed() and not done:
            try:
                await do_resolve(p, True)
            except Exception as e:  # noqa: BLE001 — la vidéo automatique reste publiable
                events.log(f"⚠ Montage Resolve impossible ({str(e)[:200]}) — the automatic video remains ready", "warn")
    # shorts pub TikTok automatiques une fois la vidéo longue terminée (hors du créneau de cette vidéo)
    n_promo = int(p.get("auto_promo_shorts") or 0)
    if n_promo > 0 and p.get("format") != "short" and p.get("render") and not p.get("promo_done"):
        from . import shorts
        p["promo_done"] = True
        store.save_project(p)
        try:
            created = await shorts.shorts_from_long(p, n_promo, "auto", kind="promo",
                                                    channel=channels.get(p.get("promo_channel")))
            for sp in created:
                start(sp["id"], run_all, "auto")
        except Exception as e:  # noqa: BLE001 — la vidéo longue est finie, un échec ici ne la touche pas
            events.log(f"✗ Shorts pub : {e}", "error")


# ------------------------------------------------------------------ batch CSV

ALIASES = {
    "title": ["title", "title", "name", "name", "video", "video"],
    "topic": ["topic", "sujet", "context", "contexte", "instructions", "notes", "description", "brief"],
    "style": ["style", "style_id"],
    "words": ["words", "words", "word_count", "longueur", "length", "nb_mots"],
    "video_url": ["video_url", "youtube", "url", "reference", "ref", "lien"],
    "script": ["script", "text", "custom_script"],
    "aspect": ["aspect", "format", "ratio"],
    "voice_id": ["voice_id", "voice", "voice"],
    "provider": ["provider", "tts", "provider"],
    "language": ["language", "langue", "lang"],
    "characters": ["characters", "characters", "persos"],
    "shorts": ["shorts", "shorts_pub", "promo", "nb_shorts", "count", "nombre"],
    "channel": ["channel", "channel", "channel", "compte", "account", "tiktok"],
    "seconds": ["seconds", "secondes", "duree", "duration", "target duration (s)", "duree visee (s)", "duration"],
    "source": ["source", "clip", "clipper", "a_clipper", "from", "depuis"],
}


LANG_ALIASES = {"fr": "French", "français": "French", "francais": "French", "french": "French",
                "en": "English", "anglais": "English", "english": "English", "es": "Spanish", "espagnol": "Spanish",
                "de": "German", "allemand": "German", "it": "Italian", "italien": "Italian", "pt": "Portuguese",
                "portugais": "Portuguese", "ar": "Arabic", "arabe": "Arabic"}


def parse_csv(raw: bytes) -> list[dict]:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    known = {a for al in ALIASES.values() for a in al}
    if not any(h in known for h in header):  # pas d'en-tête : une colonne = un titre
        return [{"title": r[0].strip(), "topic": r[1].strip() if len(r) > 1 else ""} for r in rows if r[0].strip()]
    col = {}
    for key, al in ALIASES.items():
        for i, h in enumerate(header):
            if h in al and key not in col:
                col[key] = i
    out = []
    for r in rows[1:]:
        item = {k: (r[i].strip() if i < len(r) else "") for k, i in col.items()}
        if item.get("title") or item.get("topic") or item.get("script") or item.get("source"):
            out.append(item)
    return out


LONG_WORDS = ("long", "longue", "youtube", "16:9", "video", "video")
SHORT_WORDS = ("short", "tiktok", "court", "reel", "shorts", "9:16")


def create_from_rows(rows: list[dict], mode: str, default_style: str,
                     default_channel: str | None = None) -> list[dict]:
    from . import channels, planner
    styles = {s["id"]: s for s in store.list_styles()}
    by_name = {s["name"].lower(): s["id"] for s in styles.values()}
    created = []
    touched = {}
    for r in rows:
        if r.get("source"):
            continue  # lignes de clipping : traitées par launch_batch
        ch = channels.get(r.get("channel") or default_channel)
        fmt = str(r.get("aspect", "")).strip().lower()
        sid = r.get("style") or (ch or {}).get("style_id") or default_style
        sid = sid if sid in styles else by_name.get(sid.lower(), default_style)
        overrides = {}
        if r.get("words", "").strip().isdigit():
            overrides["script.word_count"] = int(r["words"])
        secs = str(r.get("seconds", "")).strip()
        if secs.isdigit():
            overrides["shorts.target_seconds"] = min(180, int(secs))
        if r.get("aspect") in ("16:9", "9:16"):
            overrides["visuals.aspect"] = r["aspect"]
        is_short = fmt in SHORT_WORDS or (ch is not None and fmt not in LONG_WORDS)
        if r.get("voice_id"):
            overrides["voice.voice_id"] = r["voice_id"]
        if r.get("language"):
            overrides["language"] = LANG_ALIASES.get(r["language"].strip().lower(), r["language"].strip())
        if r.get("provider", "").lower() in ("elevenlabs", "edge", "local", "algrow"):
            overrides["voice.provider"] = r["provider"].lower()
        chars = None
        if r.get("characters", "").strip():
            names = [x.strip().lower() for x in re.split(r"[,;+/]", r["characters"]) if x.strip()]
            pool = styles[sid].get("characters", [])
            chars = [c["id"] for c in pool if c["id"].lower() in names or c["name"].lower() in names]
            if any(n in ("none", "none", "non") for n in names):
                chars = []
        p = store.create_project(r.get("title", ""), sid, topic=r.get("topic", ""),
                                 video_url=r.get("video_url", ""), mode=mode,
                                 custom_script=r.get("script", ""), overrides=overrides, characters=chars)
        if is_short:
            from .shorts import apply_short_settings
            apply_short_settings(p)
            if overrides.get("shorts.target_seconds"):
                p["settings"]["shorts"]["target_seconds"] = overrides["shorts.target_seconds"]
                p["settings"]["script"]["word_count"] = round(overrides["shorts.target_seconds"] * 2.3)
            if ch:
                channels.apply(p, ch)
                if r.get("language"):
                    p["settings"]["language"] = overrides["language"]
                p["short"] = {"kind": "standalone"}
                touched[ch["id"]] = ch
            store.save_project(p)
            created.append(p)
            continue
        if ch:
            p["promo_channel"] = ch["id"]  # les shorts pub de cette vidéo iront sur cette chaîne
        if str(r.get("shorts", "")).strip().isdigit():
            p["auto_promo_shorts"] = min(3, int(r["shorts"]))
            store.save_project(p)
        elif (styles[sid].get("shorts") or {}).get("promo_count"):
            p["auto_promo_shorts"] = int(styles[sid]["shorts"]["promo_count"])
        store.save_project(p)
        created.append(p)
    for ch in touched.values():
        planner.assign(ch)
    return created


async def clip_row(r: dict, mode: str, default_channel: str | None = None) -> list[dict]:
    """Ligne CSV de clipping : source = lien YouTube ou titre / id d'une vidéo TubeForge."""
    from . import channels, shorts
    ch = channels.get(r.get("channel") or default_channel)
    kind = (ch or {}).get("kind") or "promo"
    count = max(1, min(5, int(r["shorts"]))) if str(r.get("shorts", "")).strip().isdigit() else 2
    src = r["source"].strip()
    if "youtu" in src:
        return await shorts.shorts_from_url(src, count, mode, kind=kind, channel=ch)
    key = src.lower()
    p_long = next((p for p in store.list_projects(None) if p["id"] == src or (p.get("title") or "").lower() == key
                   or (p.get("title") or "").lower().startswith(key)), None)
    if not p_long:
        raise ValueError(f"Video to clip not found: \" {src} »")
    return await shorts.shorts_from_long(p_long, count, mode, kind=kind, channel=ch)


async def launch_batch(rows: list[dict], mode: str, default_style: str, name: str,
                       default_channel: str | None = None, wait_clips: bool = False) -> tuple[dict, list[dict]]:
    """Crée et lance tout un CSV. Les lignes de clipping sont écrites en parallèle puis ajoutées au batch."""
    created = create_from_rows(rows, mode, default_style, default_channel)
    for p in created:
        start(p["id"], run_all, mode)
    b = save_batch([p["id"] for p in created], mode, name)
    clips = [r for r in rows if r.get("source")]

    async def one(r):
        try:
            ps = await clip_row(r, mode, default_channel)
        except Exception as e:  # noqa: BLE001
            events.log(f"✗ Clipping « {r['source'][:80]} » : {e}", "error")
            return
        for p in ps:
            start(p["id"], run_all, mode)
        add_to_batch(b["id"], [p["id"] for p in ps])

    if clips:
        job = asyncio.gather(*(one(r) for r in clips))
        if wait_clips:
            await job
        else:
            _side_tasks.add(asyncio.ensure_future(job))
    return b, created


def add_to_batch(batch_id: str, project_ids: list[str]) -> None:
    batches = read_json(BATCHES_FILE, []) or []
    for b in batches:
        if b["id"] == batch_id:
            b["projects"] += [pid for pid in project_ids if pid not in b["projects"]]
    write_json(BATCHES_FILE, batches)


def save_batch(project_ids: list[str], mode: str, name: str) -> dict:
    batches = read_json(BATCHES_FILE, []) or []
    b = {"id": uuid.uuid4().hex[:8], "name": name, "created": now(), "mode": mode, "projects": project_ids}
    batches.insert(0, b)
    write_json(BATCHES_FILE, batches[:50])
    return b


def list_batches() -> list[dict]:
    return read_json(BATCHES_FILE, []) or []
