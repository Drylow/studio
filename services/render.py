"""Montage vidéo local (ffmpeg) : images fixes → vidéo animée calée sur la voix.

Pipeline :
  1. un clip par scène, avec mouvement de caméra (zoom/pan type Ken Burns) —
     rendus en parallèle et MIS EN CACHE (régénérer 1 image ne refait qu'1 clip) ;
  2. assemblage : coupe franche (concat sans réencodage) ou fondus enchaînés
     (xfade, par paquets pour ne pas exploser la mémoire) ;
  3. passe finale : voix off + musique (ducking auto sous la voix) + sous-titres
     ASS incrustés + titres de section + normalisation du volume (-14 LUFS).

La timeline est calculée en FRAMES entières → aucune dérive image/voix, même
sur 30 min de vidéo.
"""
import hashlib
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import media

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "fonts")

MOTIONS = ["zoom_in", "pan_right", "zoom_out", "pan_left", "zoom_in_tl", "pan_down", "zoom_in_br", "pan_up"]


class Cancelled(Exception):
    pass


# ── Mouvements de caméra ────────────────────────────────────────────────────

def _motion_expr(kind, n, strength):
    s = max(0.02, min(0.35, float(strength)))
    p = f"(on/{max(1, n - 1)})"
    e = f"({p}*{p}*(3-2*{p}))"                    # ease in-out (smoothstep)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    full = f"{1 + s:.4f}"
    if kind == "zoom_out":
        return f"1+{s}*(1-{e})", cx, cy
    if kind == "pan_right":
        return full, f"(iw-iw/zoom)*{e}", cy
    if kind == "pan_left":
        return full, f"(iw-iw/zoom)*(1-{e})", cy
    if kind == "pan_down":
        return full, cx, f"(ih-ih/zoom)*{e}"
    if kind == "pan_up":
        return full, cx, f"(ih-ih/zoom)*(1-{e})"
    if kind == "zoom_in_tl":   # zoom vers le haut-gauche (tiers)
        return f"1+{s}*{e}", f"(iw-iw/zoom)*0.33*{e}+({cx})*(1-{e})", f"(ih-ih/zoom)*0.33*{e}+({cy})*(1-{e})"
    if kind == "zoom_in_br":
        return f"1+{s}*{e}", f"(iw-iw/zoom)*0.67*{e}+({cx})*(1-{e})", f"(ih-ih/zoom)*0.67*{e}+({cy})*(1-{e})"
    if kind == "none":
        return "1", "0", "0"
    return f"1+{s}*{e}", cx, cy                   # zoom_in (défaut)


def pick_motions(count, mode="auto", seed=0):
    """Enchaîne des mouvements variés sans répéter deux fois le même d'affilée."""
    if mode in ("none", "static"):
        return ["none"] * count
    if mode in MOTIONS:
        return [mode] * count
    rnd = random.Random(seed)
    out, prev = [], None
    for _ in range(count):
        choices = [m for m in MOTIONS if m != prev]
        m = rnd.choice(choices)
        out.append(m)
        prev = m
    return out


def _clip_key(image, frames, w, h, fps, motion, strength):
    st = os.stat(image)
    raw = json.dumps([os.path.basename(image), st.st_size, int(st.st_mtime), frames, w, h, fps,
                      motion, round(float(strength), 3)])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def render_clip(image, dest, frames, w, h, fps, motion, strength, crf=17):
    if motion == "none":  # image fixe : pas besoin de zoompan (bien plus rapide)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},"
              f"setsar=1,format=yuv420p")
        media.run(["-loop", "1", "-framerate", str(fps), "-i", image, "-vf", vf, "-frames:v", str(frames),
                   "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                   "-crf", str(crf), "-an", dest])
        return dest
    z, x, y = _motion_expr(motion, frames, strength)
    vf = (f"scale={w * 2}:{h * 2}:flags=lanczos,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
          f"setsar=1,format=yuv420p")
    media.run(["-i", image, "-vf", vf, "-frames:v", str(frames), "-r", str(fps),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-an", dest])
    return dest


# ── Sous-titres ASS ─────────────────────────────────────────────────────────

def _ass_color(hex_color, alpha=0):
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_text(t):
    return (t or "").replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def group_caption_lines(words, max_words=6, max_chars=34):
    """Regroupe les mots en lignes lisibles (coupe sur la ponctuation)."""
    lines, cur = [], []
    for wd in words:
        cur.append(wd)
        text = " ".join(x["w"] for x in cur)
        end_punct = wd["w"][-1:] in ".!?…:;,"
        if len(cur) >= max_words or len(text) >= max_chars or (end_punct and len(cur) >= 2) \
                or wd["w"][-1:] in ".!?…":
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def build_ass(words, dest, w, h, captions, overlays=None):
    """Écrit le fichier .ass (sous-titres + titres de section). Renvoie dest ou None."""
    captions = captions or {}
    mode = captions.get("mode", "none")
    overlays = overlays or []
    if mode == "none" and not overlays:
        return None
    vertical = h > w
    font = captions.get("font") or "Poppins ExtraBold"
    size = int(captions.get("size") or (78 if vertical else 66))
    size = round(size * h / (1920 if vertical else 1080))
    outline = max(2, round(size * 0.09))
    pos = captions.get("position", "bottom")
    align = 2 if pos == "bottom" else 5
    margin_v = round(h * (0.08 if pos == "bottom" else 0))
    if vertical and pos == "bottom":
        margin_v = round(h * 0.22)
    base = _ass_color(captions.get("color", "#FFFFFF"))
    hl = _ass_color(captions.get("highlight", "#FFD60A"))
    out_c = _ass_color(captions.get("outline", "#000000"))
    title_size = round(size * 1.35)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{size},{base},{hl},{out_c},&H80000000,0,0,0,0,100,100,0,0,1,{outline},"
        f"{max(1, outline // 2)},{align},80,80,{margin_v},1",
        f"Style: Title,{font},{title_size},{base},{hl},{out_c},&H80000000,0,0,0,0,100,100,1,0,1,"
        f"{round(outline * 1.3)},{outline},5,80,80,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    upper = bool(captions.get("uppercase"))
    fmt = (lambda s: s.upper()) if upper else (lambda s: s)
    if mode in ("phrase", "karaoke") and words:
        groups = group_caption_lines(words, max_words=4 if mode == "karaoke" else 7,
                                     max_chars=24 if mode == "karaoke" else 40)
        for gi, g in enumerate(groups):
            start = g[0]["s"]
            nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g[-1]["e"] + 0.6
            end = max(g[-1]["e"] + 0.15, start + 0.4)
            end = min(end, nxt) if nxt > start else end
            if mode == "phrase":
                txt = _ass_text(fmt(" ".join(x["w"] for x in g)))
                lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Cap,,0,0,0,,{txt}")
                continue
            for i, wd in enumerate(g):
                ws = start if i == 0 else wd["s"]
                we = g[i + 1]["s"] if i + 1 < len(g) else end
                if we <= ws:
                    continue
                parts = []
                for j, x in enumerate(g):
                    t = _ass_text(fmt(x["w"]))
                    parts.append("{\\c" + hl + "\\fscx108\\fscy108}" + t + "{\\c" + base + "\\fscx100\\fscy100}"
                                 if j == i else t)
                lines.append(f"Dialogue: 0,{_ass_time(ws)},{_ass_time(we)},Cap,,0,0,0,,{' '.join(parts)}")
    for ov in overlays:
        txt = _ass_text(fmt(ov.get("text", "")))
        if not txt:
            continue
        s, e = float(ov["start"]), float(ov["end"])
        lines.append(f"Dialogue: 1,{_ass_time(s)},{_ass_time(e)},Title,,0,0,0,,{{\\fad(250,300)}}{txt}")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return dest


# ── Rendu complet ───────────────────────────────────────────────────────────

def _frames_timeline(scenes, fps, total):
    """Bornes en frames entières : scène i = [F_i, F_{i+1}[, dernière → fin de la voix."""
    starts = [0] + [int(round(float(s["start"]) * fps)) for s in scenes[1:]]
    end_f = int(round(total * fps))
    bounds = starts + [end_f]
    out = []
    for i in range(len(scenes)):
        out.append(max(2, bounds[i + 1] - bounds[i]))
    return out


def render_video(workdir, scenes, voice_path, out_path, *, width=1920, height=1080, fps=30,
                 motion="auto", motion_strength=0.12, transition="fade", transition_dur=0.35,
                 words=None, captions=None, overlays=None, music_path=None, music_volume=0.12,
                 normalize=True, quality="fast", tail=0.6, progress=None, cancelled=None):
    """Monte la vidéo finale. scenes = [{"image": path, "start": sec}, ...] (triées)."""
    def tick(pct, msg):
        if progress:
            progress(max(0.0, min(1.0, pct)), msg)
        if cancelled and cancelled():
            raise Cancelled("Rendu annulé.")

    if not scenes:
        raise media.MediaError("Aucune scène à monter.")
    for s in scenes:
        if not s.get("image") or not os.path.isfile(s["image"]):
            raise media.MediaError(f"Image manquante pour la scène {s.get('index', '?')}.")
    voice_dur = media.duration(voice_path)
    total = voice_dur + float(tail)
    fps = int(fps)
    frames = _frames_timeline(scenes, fps, total)
    fade = transition == "fade" and transition_dur > 0 and len(scenes) > 1
    tf = int(round(transition_dur * fps)) if fade else 0

    clips_dir = os.path.join(workdir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    motions = pick_motions(len(scenes), motion, seed=len(scenes))
    jobs = []
    for i, s in enumerate(scenes):
        n = frames[i] + (tf if fade and i < len(scenes) - 1 else 0)
        mv = s.get("motion") or motions[i]
        key = _clip_key(s["image"], n, width, height, fps, mv, motion_strength)
        jobs.append((i, s["image"], os.path.join(clips_dir, f"c{i:04d}_{key}.mp4"), n, mv))

    # 1) clips (parallèle + cache)
    todo = [j for j in jobs if not os.path.isfile(j[2])]
    workers = max(1, min(4, (os.cpu_count() or 2) // 2))
    done = len(jobs) - len(todo)
    tick(0.02, f"Animation des scènes ({done}/{len(jobs)} en cache)…")
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(render_clip, img, dest + ".tmp.mp4", n, width, height, fps, mv,
                              motion_strength): (dest,) for (_, img, dest, n, mv) in todo}
            for fut in as_completed(futs):
                fut.result()
                dest = futs[fut][0]
                os.replace(dest + ".tmp.mp4", dest)
                done += 1
                tick(0.02 + 0.68 * done / len(jobs), f"Animation des scènes {done}/{len(jobs)}")
    keep = {os.path.basename(j[2]) for j in jobs}
    for f in os.listdir(clips_dir):  # purge des clips obsolètes
        if f not in keep:
            try:
                os.remove(os.path.join(clips_dir, f))
            except OSError:
                pass

    # 2) assemblage — en fondu, l'enchaînement est fait DANS la passe finale (1 encodage de moins)
    tick(0.72, "Assemblage des scènes…")
    clip_paths = [j[2] for j in jobs]
    durs = [f / fps for f in frames]
    temp, batch = [], 24
    if not fade:
        assembled = os.path.join(workdir, "assembled.mp4")
        _concat_copy(clip_paths, assembled, workdir)
        inputs, in_durs = [assembled], None
        temp.append(assembled)
    elif len(clip_paths) <= batch:
        inputs, in_durs = clip_paths, durs
    else:
        inputs, in_durs = [], []
        groups = [list(range(i, min(i + batch, len(clip_paths)))) for i in range(0, len(clip_paths), batch)]
        for gi, g in enumerate(groups):
            part = os.path.join(workdir, f"part_{gi:03d}.mp4")
            _xfade_chain([clip_paths[i] for i in g], [durs[i] for i in g], transition_dur, fps, part)
            inputs.append(part)
            in_durs.append(sum(durs[i] for i in g))
            temp.append(part)
            tick(0.72 + 0.12 * (gi + 1) / len(groups), f"Assemblage {gi + 1}/{len(groups)}")

    # 3) passe finale
    tick(0.86, "Fondus, sous-titres, mixage audio et export…")
    ass = build_ass(words or [], os.path.join(workdir, "captions.ass"), width, height, captions, overlays)
    try:
        _final_pass(workdir, inputs, in_durs, transition_dur, voice_path, out_path, total, ass, music_path,
                    music_volume, normalize, quality, fps)
    finally:
        for t in temp:
            try:
                os.remove(t)
            except OSError:
                pass
    tick(1.0, "Vidéo prête.")
    return {"path": out_path, "duration": round(total, 3)}


def _concat_copy(paths, dest, workdir):
    lst = os.path.join(workdir, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in paths:
            f.write("file '" + os.path.relpath(p, workdir).replace("\\", "/") + "'\n")
    media.run(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy", os.path.basename(dest)],
              cwd=workdir)


def _xfade_graph(n, durs, t, fps):
    """Graphe xfade pour n entrées vidéo (0..n-1). Renvoie (filtres, label de sortie)."""
    graph = [f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={fps}[v{i}]" for i in range(n)]
    prev, offset = "v0", 0.0
    for i in range(1, n):
        offset += durs[i - 1]
        graph.append(f"[{prev}][v{i}]xfade=transition=fade:duration={t:.3f}:offset={offset:.3f}[x{i}]")
        prev = f"x{i}"
    return graph, prev


def _xfade_chain(inputs, durs, t, fps, dest):
    """xfade sur une liste de clips. durs[i] = durée « utile » du clip i (sans recouvrement)."""
    if len(inputs) == 1:
        media.run(["-i", inputs[0], "-c", "copy", dest])
        return
    args = []
    for p in inputs:
        args += ["-i", p]
    graph, out = _xfade_graph(len(inputs), durs, t, fps)
    media.run(args + ["-filter_complex", ";".join(graph), "-map", f"[{out}]",
                      "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", dest])


def _rel(path, base):
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return os.path.abspath(path)


def _final_pass(workdir, videos, vdurs, t, voice, out_path, total, ass, music, music_volume, normalize,
                quality, fps):
    args = []
    for v in videos:
        args += ["-i", _rel(v, workdir)]
    n = len(videos)
    args += ["-i", os.path.abspath(voice)]
    has_music = bool(music and os.path.isfile(music))
    if has_music:
        args += ["-stream_loop", "-1", "-i", os.path.abspath(music)]
    graph = []
    vlabel = "0:v"
    if n > 1:
        xg, vlabel = _xfade_graph(n, vdurs, t, fps)
        graph += xg
    if ass:
        try:  # chemin relatif = pas d'échappement « C\: » à gérer sous Windows
            fonts = os.path.relpath(FONTS_DIR, workdir).replace("\\", "/")
        except ValueError:  # données sur un autre disque que l'app
            fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
        graph.append(f"[{vlabel}]ass={os.path.basename(ass)}:fontsdir='{fonts}'[v]")
        vmap = "[v]"
    else:
        vmap = f"[{vlabel}]" if n > 1 else "0:v"
    va, vm = n, n + 1  # index des entrées voix / musique
    fade_st = max(0.0, total - 1.5)
    if has_music:
        graph.append(f"[{va}:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,asplit=2[vo][sc]")
        graph.append(f"[{vm}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={float(music_volume):.3f}[mu]")
        graph.append("[mu][sc]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=450[duck]")
        graph.append("[vo][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]")
    else:
        graph.append(f"[{va}:a]aformat=sample_rates=48000:channel_layouts=stereo,apad[mix]")
    chain = "[mix]"
    if normalize:
        chain += "loudnorm=I=-14:TP=-1.5:LRA=11,"
    chain += f"afade=t=out:st={fade_st:.2f}:d=1.5[a]"
    graph.append(chain)
    copy_video = n == 1 and not ass
    if copy_video:
        venc = ["-c:v", "copy"]
    elif quality == "high":
        venc = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    tmp = out_path + ".tmp.mp4"
    media.run(args + ["-filter_complex", ";".join(graph), "-map", vmap, "-map", "[a]"] + venc +
              ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
               "-movflags", "+faststart", os.path.abspath(tmp)], cwd=workdir)
    os.replace(tmp, out_path)


def thumbnail_frame(video, dest, at=1.0):
    media.run(["-ss", f"{at:.2f}", "-i", video, "-frames:v", "1", "-q:v", "3", dest])
    return dest


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(s, default="video"):
    s = _SAFE.sub("_", (s or "").strip())[:80].strip("_")
    return s or default


# ── Pack montage (clips calés sur la voix, façon « Render videos » de TubeGen) ──

def _srt_time(t):
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words, max_words=7, max_chars=42):
    out = []
    groups = group_caption_lines(words or [], max_words=max_words, max_chars=max_chars)
    for i, g in enumerate(groups):
        start = g[0]["s"]
        end = g[-1]["e"] + 0.1
        if i + 1 < len(groups):
            end = min(end, groups[i + 1][0]["s"])
        out.append(f"{i + 1}\n{_srt_time(start)} --> {_srt_time(max(end, start + 0.3))}\n"
                   + " ".join(x["w"] for x in g) + "\n")
    return "\n".join(out)


def export_pack(workdir, scenes, voice_path, zip_path, *, width=1920, height=1080, fps=30, motion="none",
                motion_strength=0.1, words=None, script_text="", title="", progress=None, cancelled=None):
    """ZIP prêt pour CapCut/Premiere : 1 clip MP4 par scène, durée EXACTE de sa phrase.

    Les clips mis bout à bout = durée de la voix off, à la frame près → on les glisse
    dans l'ordre sur la timeline avec voiceover.mp3 et tout est synchronisé."""
    import zipfile

    def tick(p, msg):
        if progress:
            progress(max(0.0, min(1.0, p)), msg)
        if cancelled and cancelled():
            raise Cancelled("Export annulé.")

    total = media.duration(voice_path)
    fps = int(fps)
    frames = _frames_timeline(scenes, fps, total)
    cdir = os.path.join(workdir, "pack_clips")
    os.makedirs(cdir, exist_ok=True)
    motions = pick_motions(len(scenes), motion, seed=len(scenes))
    jobs = []
    for i, s in enumerate(scenes):
        mv = motions[i] if motion != "none" else "none"
        key = _clip_key(s["image"], frames[i], width, height, fps, mv, motion_strength)
        jobs.append((s["image"], os.path.join(cdir, f"p{i:04d}_{key}.mp4"), frames[i], mv))
    todo = [j for j in jobs if not os.path.isfile(j[1])]
    done = len(jobs) - len(todo)
    tick(0.02, f"Clips {done}/{len(jobs)}…")
    workers = max(1, min(4, (os.cpu_count() or 2) // 2))
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(render_clip, img, dest + ".tmp.mp4", n, width, height, fps, mv,
                              motion_strength, 18): dest for (img, dest, n, mv) in todo}
            for fut in as_completed(futs):
                fut.result()
                os.replace(futs[fut] + ".tmp.mp4", futs[fut])
                done += 1
                tick(0.02 + 0.83 * done / len(jobs), f"Clips {done}/{len(jobs)}")
    keep = {os.path.basename(j[1]) for j in jobs}
    for f in os.listdir(cdir):
        if f not in keep:
            try:
                os.remove(os.path.join(cdir, f))
            except OSError:
                pass

    tick(0.87, "Création du ZIP…")
    pad = max(3, len(str(len(scenes))))
    t, stamps = 0, []
    for i, s in enumerate(scenes):
        a, b = t / fps, (t + frames[i]) / fps
        stamps.append(f"{i + 1:0{pad}d}\t{_srt_time(a)} --> {_srt_time(b)}\t{frames[i] / fps:.3f}s\t"
                      + (s.get("text") or "").replace("\n", " "))
        t += frames[i]
    readme = (f"{title}\n\n"
              f"{len(scenes)} clips · {fps} i/s · {width}x{height} · durée totale {total:.2f} s\n\n"
              "MONTAGE (CapCut / Premiere / DaVinci) :\n"
              "1. Importe voiceover.mp3 sur la piste audio, au tout début (0:00).\n"
              "2. Sélectionne TOUS les fichiers du dossier clips/ (déjà triés dans l'ordre) et glisse-les d'un coup "
              "sur la piste vidéo à 0:00, collés les uns aux autres.\n"
              f"3. C'est calé : chaque clip dure exactement le temps de sa phrase (réglage projet : {fps} i/s).\n"
              "4. Optionnel : importe subtitles.srt pour les sous-titres, et ajoute ta musique.\n\n"
              "timestamps.txt = numéro, début → fin, durée et texte de chaque clip.\n")
    tmp = zip_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for i, (img, dest, n, mv) in enumerate(jobs):
            z.write(dest, f"clips/{i + 1:0{pad}d}.mp4")
            z.write(img, f"images/{i + 1:0{pad}d}{os.path.splitext(img)[1]}")
        z.write(voice_path, "voiceover.mp3")
        z.writestr("timestamps.txt", "\n".join(stamps) + "\n")
        z.writestr("subtitles.srt", build_srt(words or []))
        z.writestr("script.txt", script_text or "")
        z.writestr("LISEZMOI.txt", readme)
    os.replace(tmp, zip_path)
    tick(1.0, "Pack montage prêt.")
    return {"path": zip_path, "clips": len(jobs), "duration": round(total, 3)}
