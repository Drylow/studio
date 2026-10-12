"""Étape finale · Rendu — assemble images animées + voix off en MP4 (+ sous-titres .srt)."""
import asyncio
import json
import math
import re
import sys
import time
from pathlib import Path

from .. import config, events, store
from ..util import fmt_srt_time, now, run_cmd

FPS = 24  # comme TubeGen ; ~20 % de rendu en moins qu'à 30 i/s
_render_sem: asyncio.Semaphore | None = None


def render_sem() -> asyncio.Semaphore:
    global _render_sem
    if _render_sem is None:
        _render_sem = asyncio.Semaphore(max(1, config.get_int("RENDER_CONCURRENCY")))
    return _render_sem


def caption_groups(words: list[dict], max_chars: int = 42, max_dur: float = 3.6) -> list[dict]:
    """Sous-titres lisibles : une phrase = un bloc si elle tient, sinon découpe équilibrée
    (de préférence après une virgule) — jamais de mot orphelin en fin de phrase."""
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?…][\"'”’»)]*$", w["w"]):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    groups = []
    for sent in sentences:
        text = " ".join(x["w"] for x in sent)
        dur = sent[-1]["e"] - sent[0]["s"]
        k = max(math.ceil(len(text) / max_chars), math.ceil(dur / max_dur), 1)
        k = min(k, len(sent))
        if k == 1:
            groups.append({"start": sent[0]["s"], "end": sent[-1]["e"], "text": text})
            continue
        # positions de coupe équilibrées en caractères, recalées sur une virgule proche
        lens = [len(x["w"]) + 1 for x in sent]
        total = sum(lens)
        cuts, acc, i = [], 0, 0
        for part in range(1, k):
            target = total * part / k
            while i < len(sent) - 1 and acc + lens[i] <= target:
                acc += lens[i]
                i += 1
            best = i
            for j in range(max(1, i - 3), min(len(sent) - 1, i + 3)):
                if sent[j - 1]["w"].endswith((",", ";", ":", "—")) and (not cuts or j > cuts[-1]):
                    best = j
                    break
            if (not cuts or best > cuts[-1]) and 0 < best < len(sent):
                cuts.append(best)
        bounds = [0] + cuts + [len(sent)]
        for a, b in zip(bounds, bounds[1:]):
            part = sent[a:b]
            groups.append({"start": part[0]["s"], "end": part[-1]["e"], "text": " ".join(x["w"] for x in part)})
    for a, b in zip(groups, groups[1:]):  # pas de trou visuel entre deux sous-titres proches
        if b["start"] - a["end"] < 0.6:
            a["end"] = b["start"]
        else:
            a["end"] += 0.3
    if groups:
        groups[-1]["end"] += 0.4
    return groups


def write_srt(groups: list[dict], path: Path) -> None:
    lines = []
    for i, g in enumerate(groups, 1):
        lines += [str(i), f"{fmt_srt_time(g['start'])} --> {fmt_srt_time(g['end'])}", g["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def is_tiktok(p: dict) -> bool:
    return p.get("format") == "short" or p["settings"]["visuals"].get("caption_style") == "tiktok"


def tiktok_plan(p: dict, words: list[dict], scenes: list[dict]) -> dict:
    """Habillage TikTok : groupes de mots, accroche, liste des bruitages (temps, type, volume)."""
    from .. import tiktok_fx as fx
    groups = fx.tiktok_groups(words) if words else []
    meta = p.get("short") or {}
    hook_text = meta.get("hook_text", "")
    first_end = next((w["e"] for w in words if re.search(r"[.!?…][\"'”’»)]*$", w["w"])), 2.4) if words else 2.4
    hook_dur = max(1.8, min(3.0, first_end + 0.2)) if hook_text else 0.0
    sfx = []
    if hook_text:
        sfx += [{"t": 0.0, "kind": "whoosh", "gain": 0.32}, {"t": 0.08, "kind": "impact", "gain": 0.55},
                {"t": max(0.0, hook_dur - 0.18), "kind": "swish", "gain": 0.22}]
    last = hook_dur
    for i, sc in enumerate(scenes[1:], 1):
        t = sc["f0"] / FPS
        if t - last < 1.3 or t < hook_dur + 0.3:
            continue
        sfx.append({"t": max(0.0, t - 0.1), "kind": "swish" if i % 2 else "whoosh", "gain": 0.15, "variant": i})
        last = t
    endcard = None
    if meta.get("kind") == "promo" and words:
        total = words[-1]["e"] + 0.3
        # l'écran de fin démarre sur la phrase d'appel à l'action (la dernière), au moins 2 s avant la fin
        last_start = words[-1]["s"]
        for i in range(len(words) - 2, -1, -1):
            if re.search(r"[.!?…][\"'”’»)]*$", words[i]["w"]):
                last_start = words[i + 1]["s"]
                break
        start = max(hook_dur + 1.0, min(last_start, total - 2.0))
        thumb = meta.get("endcard_thumb")
        endcard = {"start": start, "cta": meta.get("cta") or {},
                   "thumb": str((store.project_dir(p["id"]) / thumb).resolve()) if thumb else None}
        sfx = [e for e in sfx if e["t"] < start - 1.5]
        sfx += [{"t": max(0.0, start - 1.5), "kind": "riser", "gain": 0.16},
                {"t": start, "kind": "hit", "gain": 0.4}]
    p.setdefault("short", {})["sfx"] = sfx
    p["short"]["hook_duration"] = hook_dur
    p["short"]["endcard_start"] = endcard["start"] if endcard else None
    return {"groups": groups, "hook": {"text": hook_text, "highlight": meta.get("hook_highlight", ""),
                                       "duration": hook_dur}, "punch": True, "sfx": sfx, "endcard": endcard}


def mix_audio(voice: Path, sfx_events: list[dict], out: Path) -> None:
    import numpy as np

    from .. import sfx as sfxlib
    x = sfxlib.load(voice)
    sr = sfxlib.SR
    end = x.size
    for e in sfx_events:
        s = sfxlib.load(sfxlib.pick(e["kind"], e.get("variant", 0))) * float(e.get("gain", 0.2))
        a = int(e["t"] * sr)
        if a >= end:
            continue
        b = min(end, a + s.size)
        x[a:b] += s[: b - a]
    peak = float(np.abs(x).max()) or 1.0
    if peak > 0.97:  # limiteur simple
        x = x * (0.97 / peak)
    import wave
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


async def render(p: dict, progress=None) -> dict:
    pdir = store.project_dir(p["id"])
    scenes = p["scenes"]
    missing = [s["id"] for s in scenes if not s.get("image") or not (pdir / s["image"]).exists()]
    if missing:
        raise RuntimeError(f"Scènes sans image : {missing[:15]}{'…' if len(missing) > 15 else ''}")
    if not p.get("voiceover"):
        raise RuntimeError("Pas de voix off")
    v = p["settings"]["visuals"]
    W, H = (1080, 1920) if v.get("aspect") == "9:16" else (1920, 1080)
    total = p["voiceover"]["duration"]
    out_dir = pdir / "render"
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("chunk_*"):
        f.unlink()

    # images par scène, calées à l'image près sur la voix
    jobs_scenes, f_prev = [], 0
    for k, s in enumerate(scenes):
        end_t = total if k == len(scenes) - 1 else s["end"]
        f_end = round(end_t * FPS)
        jobs_scenes.append({"image": str((pdir / s["image"]).resolve()), "frames": max(0, f_end - f_prev),
                            "motion": s.get("motion") or "zoom_in", "f0": f_prev})
        f_prev = max(f_prev, f_end)
    total_frames = f_prev

    words = store.load_words(p["id"])
    groups = caption_groups(words) if words else []
    srt = out_dir / "subtitles.srt"
    write_srt(groups, srt)
    tiktok = tiktok_plan(p, words, jobs_scenes) if is_tiktok(p) else None

    backend = v.get("render_backend") or config.get("RENDER_BACKEND")
    if backend not in ("auto", "native", "ovni"):
        raise RuntimeError("Unknown render backend")
    plain = not tiktok and not v.get("captions")
    if backend == "ovni" and not plain:
        raise RuntimeError("OVNI does not yet support TubeForge captions or TikTok graphics; select native")
    if backend == "ovni" or (backend == "auto" and plain and config.get("STUDIO_ROOT")):
        from .. import studio_bridge
        async with render_sem():
            return await studio_bridge.render(p, jobs_scenes, total_frames, W, H, FPS, out_dir, progress)
    events.log("Rendu TubeForge natif : habillage et sous-titres conserves")

    workers = max(1, config.get_int("RENDER_WORKERS"))
    target = total_frames / workers
    chunks, cur, acc = [], [], 0
    for js in jobs_scenes:
        cur.append(js)
        acc += js["frames"]
        if acc >= target * (len(chunks) + 1) and len(chunks) < workers - 1:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)

    progress_frames = [0] * len(chunks)
    t_render = time.time()
    last_decile = [-1]
    events.log(f"Rendu : {len(scenes)} scènes, {total_frames} images vidéo ({W}×{H}, {FPS} i/s), "
               f"{len(chunks)} processus en parallèle")

    async def run_chunk(i: int, chunk: list[dict]) -> Path:
        out = out_dir / f"chunk_{i:02d}.mp4"
        job = {"width": W, "height": H, "fps": FPS, "out": str(out), "ffmpeg": config.get("FFMPEG"),
               "scenes": chunk, "strength": v.get("motion_strength", 1.0),
               "captions": groups if v.get("captions") else [], "tiktok": tiktok}
        jf = out_dir / f"chunk_{i:02d}.json"
        jf.write_text(json.dumps(job), encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "app.render_worker", str(jf), cwd=str(config.ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        async def read_err():
            return await proc.stderr.read()
        err_task = asyncio.create_task(read_err())
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            m = re.match(rb"P (\d+)", line)
            if m:
                progress_frames[i] = int(m.group(1))
                done = sum(progress_frames)
                pct = 100 * done // max(1, total_frames)
                if pct // 10 > last_decile[0]:
                    last_decile[0] = pct // 10
                    el = time.time() - t_render
                    eta = el / max(done, 1) * (total_frames - done)
                    events.log(f"Rendu {pct} % — reste ≈ {events.fmt_duration(eta)}")
                if progress:
                    progress(done, total_frames, f"Rendu {pct}%")
        code = await proc.wait()
        err = await err_task
        if code != 0:
            raise RuntimeError(f"Rendu segment {i} échoué : {err.decode(errors='ignore')[-800:]}")
        jf.unlink(missing_ok=True)
        return out

    async with render_sem():
        if progress:
            progress(0, total_frames, "Rendu 0%")
        outs = await asyncio.gather(*(run_chunk(i, c) for i, c in enumerate(chunks)))
        lst = out_dir / "chunks.txt"
        lst.write_text("".join(f"file '{o.name}'\n" for o in outs), encoding="utf-8")
        if progress:
            progress(total_frames, total_frames, "Assemblage audio + vidéo…")
        audio = (pdir / p["voiceover"]["file"]).resolve()
        if tiktok:  # voix + bruitages (whoosh, impact…) mixés à l'image près
            audio = (out_dir / "mix.wav").resolve()
            await asyncio.to_thread(mix_audio, (pdir / p["voiceover"]["file"]).resolve(), tiktok["sfx"], audio)
            events.log(f"Bruitages : {len(tiktok['sfx'])} placés (accroche, coupes)")
        await run_cmd([config.get("FFMPEG"), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "chunks.txt",
                       "-i", str(audio), "-map", "0:v", "-map", "1:a",
                       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                       "final.mp4"], cwd=out_dir)
        for o in outs:
            o.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]+', "", p.get("title") or "video").strip()[:80] or "video"
    p["render"] = {"file": "render/final.mp4", "srt": "render/subtitles.srt", "duration": total_frames / FPS,
                   "ts": now(), "width": W, "height": H, "download_name": f"{safe_title}.mp4"}
    store.save_project(p)
    size = (pdir / "render/final.mp4").stat().st_size / 1e6
    events.log(f"✓ Vidéo rendue : {events.fmt_duration(total_frames / FPS)}, {size:.0f} Mo "
               f"(en {events.fmt_duration(time.time() - t_render)})", "ok")
    return p["render"]
