"""Retirer un passage d'une vidéo déjà faite sans rien régénérer.

Le passage est enlevé du script, de la voix (coupe au mot près grâce aux timings) et les scènes suivantes sont
décalées : les images restent les mêmes, seul le rendu est à refaire.
"""
import re
import subprocess

from . import config, store
from .steps import scenes as scenes_step
from .util import ffprobe_duration

FADE = 0.012  # s : petit fondu pour éviter un clic à la coupe


def _cut_audio(mp3, t0: float, t1: float) -> None:
    tmp = mp3.with_name("voice_cut.mp3")
    filt = (f"[0]atrim=0:{t0:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={max(0.0, t0 - FADE):.3f}:d={FADE}[a];"
            f"[0]atrim={t1:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={FADE}[b];[a][b]concat=n=2:v=0:a=1[o]")
    subprocess.run([config.get("FFMPEG"), "-y", "-v", "error", "-i", str(mp3), "-filter_complex", filt,
                    "-map", "[o]", "-c:a", "libmp3lame", "-b:a", "192k", str(tmp)], check=True)
    tmp.replace(mp3)


def _remap(t: float, t0: float, t1: float) -> float:
    if t <= t0:
        return t
    return t0 if t < t1 else t - (t1 - t0)


def cut(p: dict, a: int, b: int) -> float:
    """Enlève script[a:b] (et sa voix). Renvoie la durée retirée."""
    words = store.load_words(p["id"])
    inside = [i for i, w in enumerate(words) if w["c0"] >= a and w["c1"] <= b]
    if not inside:
        return 0.0
    i, j = inside[0], inside[-1] + 1
    duration = p["voiceover"]["duration"]
    t0 = words[i]["s"]
    t1 = words[j]["s"] if j < len(words) else duration
    d, n = t1 - t0, b - a
    _cut_audio(store.project_dir(p["id"]) / p["voiceover"]["file"], t0, t1)
    kept = words[:i]
    for w in words[j:]:
        kept.append(w | {"s": round(w["s"] - d, 3), "e": round(w["e"] - d, 3), "c0": w["c0"] - n, "c1": w["c1"] - n})
    store.save_words(p["id"], kept)

    def shift_c(c):
        return c if c < a else (a if c < b else c - n)

    script = p["script"][:a] + p["script"][b:]
    scenes = []
    for s in p["scenes"]:
        s = s | {"start": round(_remap(s["start"], t0, t1), 3), "end": round(_remap(s["end"], t0, t1), 3),
                 "c0": shift_c(s.get("c0", 0)), "c1": shift_c(s.get("c1", 0))}
        if s["end"] - s["start"] < 0.05:
            continue  # scène entièrement dans le passage coupé
        if scenes and s["end"] - s["start"] < 0.6:  # trop courte après la coupe : fusion avec la précédente
            scenes[-1]["end"], scenes[-1]["c1"] = s["end"], s["c1"]
            continue
        scenes.append(s)
    for k, s in enumerate(scenes):
        s["id"] = k + 1
        if k:
            s["start"] = scenes[k - 1]["end"]
        s["text"] = script[s["c0"]:s["c1"]].strip() or s["text"]
    p["script"], p["scenes"] = script, scenes
    p["scenes_script_hash"] = scenes_step.script_hash(script)
    new_dur = ffprobe_duration(store.project_dir(p["id"]) / p["voiceover"]["file"])
    scenes[-1]["end"] = new_dur
    p["voiceover"]["duration"] = new_dur
    p["render"], p["resolve"] = None, None
    for k in ("render", "resolve"):
        p["steps"][k] = {"state": "idle", "msg": "", "done": 0, "total": 0}
    store.save_project(p)
    return d


def cut_pattern(p: dict, pattern: str) -> list[str]:
    """Enlève tous les passages qui correspondent à l'expression (de la fin vers le début)."""
    removed = []
    for m in reversed(list(re.finditer(pattern, p["script"]))):
        if cut(p, m.start(), m.end()) > 0:
            removed.append(m.group(0).strip())
    return removed[::-1]
