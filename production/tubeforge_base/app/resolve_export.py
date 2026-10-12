"""Export vers DaVinci Resolve : TubeForge construit la timeline tout seul, piste par piste.

    V1  scènes (un clip par image, zoom/pan intégré)       A1  voix off
    V2  sous-titres (une image transparente par mot actif)  A2  bruitages (whoosh, impact…)
    V3  accroche animée (séquence PNG transparente)

Tout reste modifiable dans Resolve : remplacer une scène, déplacer un bruitage, changer un sous-titre…
Le rendu final peut être lancé par TubeForge via Resolve (Studio : script externe autorisé).

Modèle : le projet « TubeForge - Modèle TikTok » (réglages 1080x1920 24 i/s, preset de rendu, chutier
« Pack ») est exporté en .drp ; chaque chaîne a son projet créé à partir de ce modèle, avec une timeline
par short nommée par son créneau de publication (« 2026-10-10 12h30 Titre »).
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image

from . import config, events, store
from .steps import render as render_step

RESOLVE_EXE = Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe")
RESOLVE_MODULES = Path(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules")
RESOLVE_LIB = Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
FPS = render_step.FPS
TEMPLATE_NAME = "TubeForge - Modèle TikTok"
TEMPLATE_DRP = config.ROOT / "assets" / "resolve" / "TubeForge_Modele_TikTok.drp"
PRESET = "TubeForge TikTok 1080x1920"
PACK_DIRS = [config.ROOT / "assets" / "sfx" / "pack", config.ROOT / "assets" / "pack"]
_lock = threading.Lock()  # Resolve ne gère qu'un projet / une timeline à la fois


class ResolveError(Exception):
    pass


def safe_name(text: str, maxlen: int) -> str:
    """Nom accepté par Resolve / Windows : pas de ponctuation spéciale ni de point final."""
    import re
    name = re.sub(r"[^\w\- ']+", " ", text, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip(" .-'")
    return name[:maxlen].strip(" .-'") or "TubeForge"


def installed() -> bool:
    return RESOLVE_EXE.exists() and RESOLVE_MODULES.exists()


def connect(launch: bool = True, wait: float = 240):
    """Se connecte à Resolve (le lance si besoin)."""
    if str(RESOLVE_MODULES) not in sys.path:
        sys.path.append(str(RESOLVE_MODULES))
    os.environ.setdefault("RESOLVE_SCRIPT_API", str(RESOLVE_MODULES.parent))
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(RESOLVE_LIB))
    import DaVinciResolveScript as dvr  # noqa: E402

    r = dvr.scriptapp("Resolve")
    if r:
        return r
    if not launch:
        raise ResolveError("DaVinci Resolve n'est pas ouvert")
    subprocess.Popen([str(RESOLVE_EXE)])
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(3)
        r = dvr.scriptapp("Resolve")
        if r and r.GetProjectManager():
            return r
    raise ResolveError("DaVinci Resolve ne répond pas (Préférences > Système > Général : "
                       "« Script externe » doit être sur « Local »)")


# ------------------------------------------------------------------ préparation des fichiers

async def prepare_assets(p: dict, progress=None) -> dict:
    """Clips par scène + images de sous-titres + séquence d'accroche + voix + bruitages."""
    from . import tiktok_fx as fx

    pdir = store.project_dir(p["id"])
    out = pdir / "render" / "resolve"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    (out / "scenes").mkdir(parents=True)
    (out / "captions").mkdir()
    (out / "hook").mkdir()
    (out / "sfx").mkdir()
    v = p["settings"]["visuals"]
    W, H = (1080, 1920) if v.get("aspect") == "9:16" else (1920, 1080)
    total = p["voiceover"]["duration"]
    words = store.load_words(p["id"])

    # scènes calées à l'image près (même calcul que le rendu)
    scenes, f_prev = [], 0
    for k, s in enumerate(p["scenes"]):
        end_t = total if k == len(p["scenes"]) - 1 else s["end"]
        f_end = round(end_t * FPS)
        n = max(0, f_end - f_prev)
        if n:
            scenes.append({"id": s["id"], "image": str((pdir / s["image"]).resolve()), "frames": n, "f0": f_prev,
                           "motion": s.get("motion") or "zoom_in",
                           "out": str((out / "scenes" / f"scene_{s['id']:03d}_clip.mp4").resolve())})
        f_prev = max(f_prev, f_end)
    plan = render_step.tiktok_plan(p, words, scenes) if render_step.is_tiktok(p) else None

    # 1) clips des scènes (en parallèle sur plusieurs processus)
    workers = max(1, config.get_int("RENDER_WORKERS"))
    chunks = [scenes[i::workers] for i in range(workers)]
    done_frames = [0] * len(chunks)
    total_frames = sum(s["frames"] for s in scenes)

    async def run(i, chunk):
        if not chunk:
            return
        jf = out / f"job_{i}.json"
        jf.write_text(json.dumps({"width": W, "height": H, "fps": FPS, "ffmpeg": config.get("FFMPEG"),
                                  "scenes": chunk, "strength": v.get("motion_strength", 1.0), "per_scene": True}),
                      encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "app.render_worker", str(jf),
                                                    cwd=str(config.ROOT), stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            if line.startswith(b"P "):
                done_frames[i] = int(line.split()[1])
                if progress:
                    progress(sum(done_frames), total_frames, f"Clips des scènes pour Resolve {100 * sum(done_frames) // max(1, total_frames)}%")
        err = await proc.stderr.read()
        if await proc.wait() != 0:
            raise ResolveError(f"Clips des scènes : {err.decode(errors='ignore')[-500:]}")
        jf.unlink(missing_ok=True)
    events.log(f"Export Resolve : {len(scenes)} clips de scènes…")
    await asyncio.gather(*(run(i, c) for i, c in enumerate(chunks)))

    # 2) sous-titres : séquence PNG transparente image par image (mot prononcé en couleur, apparition
    #    douce) — Resolve ignore la durée demandée pour des images fixes, la séquence est fiable.
    captions_info = None
    if plan and plan["groups"]:
        from concurrent.futures import ThreadPoolExecutor
        ec = plan.get("endcard")
        caps = fx.TikTokCaptions(plan["groups"], W, H, hide_until=plan["hook"]["duration"],
                                 hide_after=float(ec["start"]) if ec else 1e9)
        n_frames = round(total * FPS)
        empty = out / "captions" / "empty.png"
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(empty)
        frames_todo = []
        for k in range(n_frames):
            ov = caps.overlay(k / FPS)
            frames_todo.append((k, ov))

        def save(item):
            k, ov = item
            path = out / "captions" / f"cap_{k:05d}.png"
            if ov is None:
                shutil.copyfile(empty, path)
                return
            frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            frame.alpha_composite(ov[0], (max(0, ov[1][0]), max(0, ov[1][1])))
            frame.save(path, compress_level=3)
        with ThreadPoolExecutor(max_workers=8) as pool:
            await asyncio.to_thread(lambda: list(pool.map(save, frames_todo)))
        empty.unlink(missing_ok=True)
        captions_info = {"pattern": str((out / "captions" / "cap_%05d.png").resolve()), "frames": n_frames}

    # 3) accroche : séquence PNG transparente (claque, secousse, flash)
    hook_info = None
    if plan and plan["hook"]["text"]:
        hook = fx.Hook(plan["hook"]["text"], plan["hook"]["highlight"], W, H, plan["hook"]["duration"])
        n = int(plan["hook"]["duration"] * FPS)
        for k in range(n):
            t = k / FPS
            frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fl = hook.flash(t)
            if fl > 0:
                frame = Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl)))
            ov = hook.overlay(t)
            if ov:
                frame.alpha_composite(ov[0], (max(0, ov[1][0]), max(0, ov[1][1])))
            frame.save(out / "hook" / f"hook_{k:04d}.png")
        hook_info = {"pattern": str((out / "hook" / "hook_%04d.png").resolve()), "frames": n,
                     "text": plan["hook"]["text"]}

    # 3b) écran de fin (short pub) : séquence PNG transparente
    endcard_info = None
    if plan and plan.get("endcard"):
        ec = plan["endcard"]
        card = fx.EndCard(float(ec["start"]), ec.get("cta") or {}, ec.get("thumb"), W, H)
        (out / "endcard").mkdir()
        f0, f1 = round(ec["start"] * FPS), round(total * FPS)
        for k in range(f1 - f0):
            ov = card.overlay(ec["start"] + k / FPS)
            ov[0].save(out / "endcard" / f"end_{k:04d}.png", compress_level=3)
        endcard_info = {"pattern": str((out / "endcard" / "end_%04d.png").resolve()), "frames": f1 - f0, "f0": f0}

    # 4) voix + bruitages
    voice = out / "voice.wav"
    subprocess.run([config.get("FFMPEG"), "-y", "-v", "error", "-i", str(pdir / p["voiceover"]["file"]),
                    "-ar", "48000", "-ac", "1", str(voice)], check=True)
    sfx_items = []
    if plan:
        from . import sfx as sfxlib
        for i, e in enumerate(plan["sfx"]):
            src = sfxlib.pick(e["kind"], e.get("variant", 0))
            dst = out / "sfx" / f"{i:02d}_{e['kind']}_fx{src.suffix}"
            shutil.copy2(src, dst)
            secs = sfxlib.load(dst).size / sfxlib.SR
            sfx_items.append({"file": str(dst.resolve()), "f0": round(e["t"] * FPS), "gain": e["gain"],
                              "kind": e["kind"], "frames": max(2, int(secs * FPS + 0.999))})
    manifest = {"width": W, "height": H, "fps": FPS, "total_frames": round(total * FPS),
                "scenes": [{"file": s["out"], "f0": s["f0"], "frames": s["frames"], "id": s["id"]} for s in scenes],
                "captions": captions_info, "hook": hook_info, "endcard": endcard_info,
                "voice": str(voice.resolve()), "sfx": sfx_items, "srt": str((pdir / "render" / "subtitles.srt").resolve())}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


# ------------------------------------------------------------------ modèle et projets

def _configure(project, w: int, h: int, fps: int) -> None:
    for key, val in (("timelineResolutionWidth", str(w)), ("timelineResolutionHeight", str(h)),
                     ("timelineFrameRate", str(fps)), ("timelinePlaybackFrameRate", str(fps))):
        project.SetSetting(key, val)


def _preset_names(project) -> list[str]:
    out = []
    for x in project.GetRenderPresetList() or []:
        out.append(x if isinstance(x, str) else (x.get("PresetName") or x.get("Name") or ""))
    return out


def _ensure_preset(project, w: int, h: int) -> None:
    if PRESET in _preset_names(project):
        return
    project.SetCurrentRenderFormatAndCodec("mp4", "H264")
    project.SetRenderSettings({"FormatWidth": w, "FormatHeight": h, "ExportVideo": True, "ExportAudio": True})
    project.SaveAsNewRenderPreset(PRESET)


def _switch(pm, name: str):
    """Ouvre un projet sans perdre le travail en cours dans celui qui est ouvert."""
    cur = pm.GetCurrentProject()
    if cur and cur.GetName() == name:
        return cur
    if cur:
        pm.SaveProject()
    return pm.LoadProject(name)


def _import_pack(project) -> int:
    """Importe le pack de l'utilisateur (bruitages, images, logos…) dans le chutier « Pack »."""
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    pack = next((f for f in root.GetSubFolderList() or [] if f.GetName() == "Pack"), None) or mp.AddSubFolder(root, "Pack")
    have = {c.GetClipProperty("File Path") for c in pack.GetClipList() or []}
    files = [str(p.resolve()) for d in PACK_DIRS if d.exists() for p in sorted(d.rglob("*"))
             if p.is_file() and p.suffix.lower() in (".wav", ".mp3", ".png", ".jpg", ".jpeg", ".mov", ".mp4", ".webp")]
    files = [x for x in files if x not in have]
    if files:
        mp.SetCurrentFolder(pack)
        mp.ImportMedia(files)
    mp.SetCurrentFolder(root)
    return len(files)


def template(rebuild: bool = False) -> dict:
    """Crée (ou met à jour) le projet modèle et l'exporte en .drp. Tes retouches dans ce projet
    (réglages, LUT, chutiers…) sont reprises par chaque nouveau projet de chaîne."""
    with _lock:
        return _template(connect(), rebuild)


def _template(r, rebuild: bool = False) -> dict:
    pm = r.GetProjectManager()
    project = _switch(pm, TEMPLATE_NAME)
    created = project is None
    if created:
        project = pm.CreateProject(TEMPLATE_NAME)
        if not project:
            raise ResolveError("Impossible de créer le projet modèle dans Resolve")
    if created or rebuild:
        _configure(project, 1080, 1920, FPS)
    _ensure_preset(project, 1080, 1920)
    n = _import_pack(project)
    pm.SaveProject()
    TEMPLATE_DRP.parent.mkdir(parents=True, exist_ok=True)
    ok = pm.ExportProject(TEMPLATE_NAME, str(TEMPLATE_DRP), False)
    return {"project": TEMPLATE_NAME, "drp": str(TEMPLATE_DRP), "exported": bool(ok), "pack_added": n,
            "preset": PRESET, "created": created}


def _channel_project(pm, pname: str, manifest: dict):
    project = _switch(pm, pname)
    if project:
        return project
    if TEMPLATE_DRP.exists() and pm.ImportProject(str(TEMPLATE_DRP), pname):
        project = _switch(pm, pname)
    if not project:
        project = pm.CreateProject(pname)
    if not project:
        raise ResolveError(f"Impossible de créer le projet Resolve « {pname} »")
    _configure(project, manifest["width"], manifest["height"], manifest["fps"])
    return project


# ------------------------------------------------------------------ construction de la timeline

def build_timeline(p: dict, manifest: dict, render: bool = True) -> dict:
    with _lock:
        return _build_timeline(p, manifest, render)


def _build_timeline(p: dict, manifest: dict, render: bool = True) -> dict:
    """Crée (ou réutilise) le projet Resolve, importe tout, place chaque élément, lance le rendu."""
    from . import channels
    r = connect()
    pm = r.GetProjectManager()
    ch = channels.get(p.get("channel_id"))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if ch:  # un projet par chaîne, une timeline par short (rangées par créneau de publication)
        if not TEMPLATE_DRP.exists():
            _template(r)
        pname = safe_name(f"TubeForge - {ch['name']}", 70)
        project = _channel_project(pm, pname, manifest)
        slot = ((p.get("post") or {}).get("slot") or "").replace(":", "h")
        tl_name = safe_name(f"{slot} {p.get('title') or 'Short'}", 80)
    else:
        pname = safe_name("TubeForge - " + (p.get("title") or p["id"]), 70)
        project = _switch(pm, pname)
        if project is None:
            project = pm.CreateProject(pname)
            if not project:
                raise ResolveError(f"Impossible de créer le projet Resolve « {pname} »")
            _configure(project, manifest["width"], manifest["height"], manifest["fps"])
        tl_name = f"{safe_name(p.get('title') or 'Video', 45)} - {stamp}"
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    old_name = (p.get("resolve") or {}).get("timeline") if (p.get("resolve") or {}).get("project") == pname else None
    for i in range(project.GetTimelineCount(), 0, -1):  # nouveau montage du même short : on remplace l'ancien
        tl = project.GetTimelineByIndex(i)
        if tl and tl.GetName() in (tl_name, old_name):
            mp.DeleteTimelines([tl])
    old_bins = [f for f in root.GetSubFolderList() or [] if f.GetName() in (tl_name, old_name)]
    if old_bins:
        mp.DeleteFolders(old_bins)
    folder = mp.AddSubFolder(root, tl_name if ch else f"TubeForge {stamp}")
    mp.SetCurrentFolder(folder)

    def import_files(paths: list[str]) -> dict:
        items = mp.ImportMedia(paths) or []
        by_name = {}
        for it in items:
            by_name[it.GetClipProperty("File Name")] = it
        return by_name

    scenes = import_files([s["file"] for s in manifest["scenes"]])
    cap_item = None
    if manifest.get("captions"):
        got = mp.ImportMedia([{"FilePath": manifest["captions"]["pattern"], "StartIndex": 0,
                               "EndIndex": manifest["captions"]["frames"] - 1}]) or []
        cap_item = got[0] if got else None
    voice = import_files([manifest["voice"]])
    sfx = import_files([s["file"] for s in manifest["sfx"]]) if manifest["sfx"] else {}
    hook_item = None
    if manifest.get("hook"):
        got = mp.ImportMedia([{"FilePath": manifest["hook"]["pattern"], "StartIndex": 0,
                               "EndIndex": manifest["hook"]["frames"] - 1}]) or []
        hook_item = got[0] if got else None

    end_item = None
    if manifest.get("endcard"):
        got = mp.ImportMedia([{"FilePath": manifest["endcard"]["pattern"], "StartIndex": 0,
                               "EndIndex": manifest["endcard"]["frames"] - 1}]) or []
        end_item = got[0] if got else None

    timeline = mp.CreateEmptyTimeline(tl_name)
    if not timeline:
        raise ResolveError("Impossible de créer la timeline")
    project.SetCurrentTimeline(timeline)
    while timeline.GetTrackCount("video") < (4 if end_item else 3):
        timeline.AddTrack("video")
    # bruitages : un son ne peut pas en chevaucher un autre sur la même piste -> plusieurs pistes
    sfx_tracks: list[int] = []  # dernière image occupée par piste
    sfx_slots = []
    for e in manifest["sfx"]:
        for ti, busy_until in enumerate(sfx_tracks):
            if e["f0"] >= busy_until:
                sfx_tracks[ti] = e["f0"] + e["frames"]
                sfx_slots.append(ti)
                break
        else:
            sfx_tracks.append(e["f0"] + e["frames"])
            sfx_slots.append(len(sfx_tracks) - 1)
    while timeline.GetTrackCount("audio") < 1 + max(1, len(sfx_tracks)):
        timeline.AddTrack("audio", "mono")
    for i, name in ((1, "Scènes"), (2, "Sous-titres"), (3, "Accroche"), (4, "Fin YouTube")):
        if i <= timeline.GetTrackCount("video"):
            timeline.SetTrackName("video", i, name)
    timeline.SetTrackName("audio", 1, "Voix off")
    for i in range(len(sfx_tracks)):
        timeline.SetTrackName("audio", 2 + i, f"Bruitages {i + 1}")
    start = timeline.GetStartFrame()
    infos = []
    for s in manifest["scenes"]:
        it = scenes.get(Path(s["file"]).name)
        if it:
            infos.append({"mediaPoolItem": it, "startFrame": 0, "endFrame": s["frames"], "trackIndex": 1,
                          "recordFrame": start + s["f0"], "mediaType": 1})
    if cap_item:
        infos.append({"mediaPoolItem": cap_item, "startFrame": 0, "endFrame": manifest["captions"]["frames"],
                      "trackIndex": 2, "recordFrame": start, "mediaType": 1})
    if hook_item:
        infos.append({"mediaPoolItem": hook_item, "startFrame": 0, "endFrame": manifest["hook"]["frames"],
                      "trackIndex": 3, "recordFrame": start, "mediaType": 1})
    if end_item:
        infos.append({"mediaPoolItem": end_item, "startFrame": 0, "endFrame": manifest["endcard"]["frames"],
                      "trackIndex": 4, "recordFrame": start + manifest["endcard"]["f0"], "mediaType": 1})
    vitem = next(iter(voice.values()), None)
    if vitem:
        infos.append({"mediaPoolItem": vitem, "startFrame": 0, "endFrame": manifest["total_frames"],
                      "trackIndex": 1, "recordFrame": start, "mediaType": 2})
    for s, slot in zip(manifest["sfx"], sfx_slots):
        it = sfx.get(Path(s["file"]).name)
        if it:
            infos.append({"mediaPoolItem": it, "startFrame": 0, "endFrame": s["frames"], "trackIndex": 2 + slot,
                          "recordFrame": start + s["f0"], "mediaType": 2})
    placed = mp.AppendToTimeline(infos) or []
    # volume des bruitages (les sons du kit sont normalisés : on les baisse sous la voix)
    for item in placed:
        try:
            name = item.GetName() or ""
            match = next((s for s in manifest["sfx"] if Path(s["file"]).name == name), None)
            if match:
                item.SetProperty("Volume", round(20 * __import__("math").log10(max(0.05, match["gain"])), 1))
        except Exception:  # noqa: BLE001
            pass
    pm.SaveProject()
    result = {"project": pname, "timeline": timeline.GetName(), "placed": len(placed), "expected": len(infos)}
    if render:
        out_dir = store.project_dir(p["id"]) / "render"
        if not (PRESET in _preset_names(project) and project.LoadRenderPreset(PRESET)):
            project.SetCurrentRenderFormatAndCodec("mp4", "H264")
        project.SetCurrentRenderMode(1)
        project.SetRenderSettings({"SelectAllFrames": False, "MarkIn": start,
                                   "MarkOut": start + manifest["total_frames"] - 1,
                                   "TargetDir": str(out_dir.resolve()), "CustomName": "resolve_final",
                                   "FormatWidth": manifest["width"], "FormatHeight": manifest["height"]})
        job = project.AddRenderJob()
        if not job or not project.StartRendering(job):
            raise ResolveError("Resolve n'a pas pu lancer le rendu")
        t0 = time.time()
        while project.IsRenderingInProgress() and time.time() - t0 < 1800:
            time.sleep(2)
        st = project.GetRenderJobStatus(job) or {}
        result["render_status"] = st.get("JobStatus")
        result["render_file"] = str(out_dir / "resolve_final.mp4")
        pm.SaveProject()
    return result


async def export(p: dict, render: bool = True, progress=None) -> dict:
    if not installed():
        raise ResolveError("DaVinci Resolve n'est pas installé")
    if not p.get("voiceover") or not all(s.get("image") for s in p["scenes"]):
        raise ResolveError("Il faut la voix off et toutes les images avant l'export")
    manifest = await prepare_assets(p, progress)
    if progress:
        progress(1, 1, "Construction de la timeline dans DaVinci Resolve…")
    events.log("Construction de la timeline dans DaVinci Resolve…", "step")
    res = await asyncio.to_thread(build_timeline, p, manifest, render)
    p["resolve"] = res | {"ts": time.time()}
    store.save_project(p)
    events.log(f"✓ Resolve : projet « {res['project']} », timeline « {res['timeline']} » "
               f"({res['placed']}/{res['expected']} éléments placés)"
               + (f", rendu : {res.get('render_status')}" if render else ""), "ok")
    return res
