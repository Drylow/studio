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


FPS_DEFAULT = 30
Cancelled = media.Cancelled  # annulation (bouton Annuler) : tue ffmpeg immédiatement


# ── Mouvements de caméra ────────────────────────────────────────────────────

def _motion_filter(kind, n, strength, offset=0):
    """Mouvement de caméra au sous-pixel (filtre perspective, interpolation bicubique).

    zoompan arrondit le cadrage au pixel entier : l'image reste figée quelques images puis
    saute → l'écran « tremble ». Ici le cadrage est exact à chaque image : mouvement continu,
    à vitesse constante (les fondus entre scènes adoucissent déjà les départs)."""
    s = max(0.02, min(0.35, float(strength)))
    p = f"((in+{int(offset)})/{max(1, n - 1)})" if offset else f"(in/{max(1, n - 1)})"
    if kind == "zoom_out":
        z = f"(1+{s}*(1-{p}))"
    elif kind.startswith("pan_"):
        z = f"{1 + s:.4f}"
    else:
        z = f"(1+{s}*{p})"
    hw, hh = f"(W/2/{z})", f"(H/2/{z})"           # demi-taille du cadrage dans l'image source
    mx, my = f"(W-W/{z})", f"(H-H/{z})"           # marge de déplacement
    cx, cy = "(W/2)", "(H/2)"
    if kind == "pan_right":
        cx = f"({hw}+{mx}*{p})"
    elif kind == "pan_left":
        cx = f"({hw}+{mx}*(1-{p}))"
    elif kind == "pan_down":
        cy = f"({hh}+{my}*{p})"
    elif kind == "pan_up":
        cy = f"({hh}+{my}*(1-{p}))"
    elif kind == "zoom_in_tl":                    # glisse doucement vers le tiers haut-gauche
        cx, cy = f"({hw}+{mx}*(0.5-0.17*{p}))", f"({hh}+{my}*(0.5-0.17*{p}))"
    elif kind == "zoom_in_br":
        cx, cy = f"({hw}+{mx}*(0.5+0.17*{p}))", f"({hh}+{my}*(0.5+0.17*{p}))"
    l, r, t, b = f"{cx}-{hw}", f"{cx}+{hw}", f"{cy}-{hh}", f"{cy}+{hh}"
    # bilinéaire : identique à l'œil pour un zoom ≤ 1,35 (PSNR ~39 dB vs bicubique) et ~40 % plus rapide
    return (f"perspective=x0='{l}':y0='{t}':x1='{r}':y1='{t}':x2='{l}':y2='{b}':x3='{r}':y3='{b}'"
            f":interpolation=linear:eval=frame")


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


def _file_sig(path):
    if not path or not os.path.isfile(path):
        return None
    st = os.stat(path)
    return [os.path.basename(path), st.st_size, int(st.st_mtime)]


def _clip_key(image, frames, w, h, fps, motion, strength, layout=None, t0=0.0, track=None, extra=None):
    raw = json.dumps([_file_sig(image), frames, w, h, fps, motion, round(float(strength), 3),
                      _layout_sig(layout, t0, track), "persp1", extra])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ── Mise en page « tableau » (fond quadrillé + panneau + présentateur) ─────

def _layout_sig(layout, t0=0.0, track=None):
    if not layout:
        return None
    sig = [_file_sig(layout.get("bg")), _file_sig(layout.get("frame")), list(layout.get("panel") or [])]
    if layout.get("presenter"):
        sig += [_file_sig(layout["presenter"]), layout.get("pres_x"), layout.get("pres_y"), bool(layout.get("bob"))]
        if layout.get("rig"):
            sig.append(sorted((k, _file_sig(v)) for k, v in layout["rig"].items()))
        if layout.get("bob"):
            sig.append(round(float(t0), 3))
        if track:
            sig.append(hashlib.sha1(json.dumps(track).encode()).hexdigest()[:12])
    return sig


BOB_AMP, BOB_PERIOD = 4.0, 3.2  # respiration du présentateur (px à 1080p, secondes)


def _bob_expr(layout, t0=0.0):
    y = int(layout["pres_y"])
    if not layout.get("bob"):
        return str(y)
    amp = BOB_AMP * float(layout.get("scale") or 1.0)
    return f"{y}+{amp:.2f}*sin(2*PI*(t+{float(t0):.4f})/{BOB_PERIOD})"


def prepare_layout(workdir, board_cfg, presenter_src, width, height, with_presenter=True, rig=None,
                   rig_mode="poses"):
    """Prépare fond, cadre du panneau et présentateur (image fixe ou rig animé) → dict `layout`.

    rig = {"A": chemin, "mid": …, "point": …, "tap": …, "A~mid": …} (poses du prof, même cadrage)."""
    from PIL import Image
    from services import board
    g = board.geometry(board_cfg, width, height)
    keys = ("bg_color", "line_color", "major_color", "pattern", "cell", "major_every", "paper", "panel_width",
            "border", "border_color", "radius", "shadow", "shadow_color", "shadow_offset")
    raw = json.dumps([board_cfg.get(k) for k in keys] + [width, height])
    tag = hashlib.sha1(raw.encode()).hexdigest()[:10]
    bg = os.path.join(workdir, f"board_{tag}.png")
    fr = os.path.join(workdir, f"frame_{tag}.png")
    if not os.path.isfile(bg):
        board.make_background(board_cfg, bg + ".tmp.png", width, height)
        os.replace(bg + ".tmp.png", bg)
    if not os.path.isfile(fr):
        board.make_frame(board_cfg, bg, fr + ".tmp.png", width, height)
        os.replace(fr + ".tmp.png", fr)
    layout = {"bg": bg, "frame": fr, "panel": list(g["panel"]), "presenter": None, "rig": None,
              "scale": height / 1080.0}
    if not with_presenter:
        return layout
    ph = g["presenter_h"]
    ow = int(round(float(board_cfg.get("presenter_outline") or 0) * height / 1080.0))
    oc = board_cfg.get("outline_color") or "#FFFFFF"

    def scaled(src, name):
        sig = hashlib.sha1(json.dumps([_file_sig(src), ph, ow, oc]).encode()).hexdigest()[:10]
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
        dst = os.path.join(workdir, f"presenter_{safe}_{sig}.png")
        if not os.path.isfile(dst):
            im = Image.open(src).convert("RGBA")
            im = im.resize((max(2, round(im.width * ph / im.height)), ph), Image.LANCZOS)
            if ow:
                im = board.outline(im, ow, oc)
            im.save(dst + ".tmp.png", "PNG")
            os.replace(dst + ".tmp.png", dst)
        return dst

    frames = {k: scaled(v, k) for k, v in (rig or {}).items() if v and os.path.isfile(v)}
    if frames.get("A"):
        layout.update({"presenter": frames["A"], "rig": frames, "rig_mode": rig_mode})
    elif presenter_src and os.path.isfile(presenter_src):
        layout["presenter"] = scaled(presenter_src, "static")
    if layout["presenter"]:
        shift = ow + 2 if ow else 0  # le contour agrandit l'image : les pieds restent au même endroit
        layout.update({"pres_x": max(0, g["presenter_x"] - shift), "pres_y": g["presenter_bottom"] - ph - shift,
                       "bob": bool(board_cfg.get("bob", False))})
    return layout


def presenter_track(layout, words, total, fps, dest, start_f=0, count=None):
    """Écrit la liste concat (ffmpeg) de l'animation du présentateur ; None si pas de rig."""
    if not layout or not layout.get("rig"):
        return None
    from services import presenter
    segs = presenter.track_segments(layout.get("rig_mode"), words or [], total, fps)
    if count is not None:
        segs = presenter.slice_timeline(segs, start_f, count)
    base = os.path.dirname(os.path.abspath(dest))
    paths = {k: os.path.relpath(v, base) if os.path.splitdrive(v)[0] == os.path.splitdrive(base)[0]
             else os.path.abspath(v) for k, v in layout["rig"].items()}
    presenter.write_concat(segs, paths, dest, fps)
    return segs


_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-pix_fmt", "yuv420p"]


def _scene_filter(W, H, motion, n, strength, offset=0, count=None, fps=None):
    """Image « cover » au format W×H + mouvement de caméra (frames [offset, offset+count[ de son mouvement).
    fps : cadence déclarée explicitement (xfade exige une cadence constante sur ses deux entrées)."""
    # l'image est décodée et recadrée UNE fois, puis répétée en mémoire (loop) : pas de décodage / mise à
    # l'échelle à chaque image
    f = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,"
         f"loop=loop=-1:size=1,setpts=N/({int(fps or FPS_DEFAULT)}*TB)")
    if motion != "none":
        f += "," + _motion_filter(motion, n, strength, offset)
    f += ",format=yuv420p"
    if count:
        f += f",trim=end_frame={int(count)},setpts=PTS-STARTPTS"
    if fps and count:
        f += f",settb=AVTB,fps={int(fps)}"
    return f


def render_clip(image, dest, frames, w, h, fps, motion, strength, crf=18, cancelled=None, layout=None, t0=0.0,
                track=None, motion_frames=None, prev=None):
    """Clip d'une scène. Même encodeur/profil pour tous les clips → concat sans réencodage sûr.

    motion_frames : longueur du mouvement de l'image (≥ frames : le mouvement continue pendant le
    fondu vers la scène suivante, montré au début du clip suivant).
    prev = {"image", "motion", "n", "offset", "tf"} : le clip commence par un fondu de tf images
    depuis la fin du mouvement de la scène précédente → les fondus sont faits ici, en parallèle,
    et la vidéo finale n'est plus qu'un collage des clips (aucun réencodage).

    layout (mise en page tableau) : la scène est animée DANS le panneau, posée sur le fond, sous
    le cadre (contour + coins arrondis), avec le présentateur par-dessus si layout["presenter"]
    (track = liste concat de son animation pour ce clip ; t0 = début du clip dans la vidéo, pour
    que la respiration soit continue d'un clip à l'autre)."""
    iw, ih = (layout["panel"][2], layout["panel"][3]) if layout else (w, h)
    n = int(motion_frames or frames)
    loop = ["-loop", "1", "-framerate", str(fps), "-i"]      # fonds / cadres fixes de la mise en page
    one = ["-i"]                                            # images de scène : répétées par le filtre loop
    tune = ["-tune", "stillimage"] if motion == "none" and not prev else []
    if not layout and not prev:
        media.run(one + [image, "-vf", _scene_filter(iw, ih, motion, n, strength, fps=fps), "-frames:v", str(frames),
                         "-r", str(fps)] + _X264 + tune + ["-crf", str(crf), "-an", dest], cancelled=cancelled)
        return dest
    args, graph, idx = [], [], 0
    if prev and int(prev.get("tf") or 0) > 0:
        tf = int(prev["tf"])
        args += one + [prev["image"]] + one + [image]
        graph.append(f"[0:v]{_scene_filter(iw, ih, prev['motion'], prev['n'], strength, prev['offset'], tf, fps)}[pa]")
        graph.append(f"[1:v]{_scene_filter(iw, ih, motion, n, strength, 0, frames, fps)}[pb]")
        graph.append(f"[pa][pb]xfade=transition=fade:duration={tf / fps:.4f}:offset=0[p]")
        idx = 2
    else:
        args += one + [image]
        graph.append(f"[0:v]{_scene_filter(iw, ih, motion, n, strength, fps=fps)}[p]")
        idx = 1
    out = "p"
    if layout:
        px, py = layout["panel"][0], layout["panel"][1]
        args += loop + [layout["bg"]]
        graph += [f"[{idx}:v]setsar=1[b]", f"[b][p]overlay=x={px}:y={py}:shortest=1[bp]"]
        out, idx = "bp", idx + 1
        if layout.get("frame"):
            args += loop + [layout["frame"]]
            graph.append(f"[{out}][{idx}:v]overlay=0:0:shortest=1[bf]")
            out, idx = "bf", idx + 1
        if layout.get("presenter"):
            if track:
                args += ["-f", "concat", "-safe", "0", "-i", track]
            else:
                args += loop + [layout["presenter"]]
            graph.append(f"[{out}][{idx}:v]overlay=x={layout['pres_x']}:y='{_bob_expr(layout, t0)}':eval=frame[bq]")
            out = "bq"
    graph.append(f"[{out}]format=yuv420p[v]")
    media.run(args + ["-filter_complex", ";".join(graph), "-map", "[v]", "-frames:v", str(frames),
                      "-r", str(fps)] + _X264 + tune + ["-crf", str(crf), "-an", dest], cancelled=cancelled)
    return dest


def _run_clips(todo, workers, cancelled, on_done):
    """Rend des clips en parallèle ; en cas d'annulation/erreur, ne lance plus rien et tue le reste."""
    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        futs = {ex.submit(render_clip, *args, cancelled=cancelled, **(kw or {})): dest for dest, args, kw in todo}
        for fut in as_completed(futs):
            fut.result()
            os.replace(futs[fut] + ".tmp.mp4", futs[fut])
            on_done()
    finally:
        ex.shutdown(wait=True, cancel_futures=True)


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
                 normalize=True, quality="fast", tail=0.6, layout=None, progress=None, cancelled=None):
    """Monte la vidéo finale. scenes = [{"image": path, "start": sec}, ...] (triées).

    layout (voir prepare_layout) : mise en page tableau. Les clips contiennent fond + panneau ;
    le présentateur est incrusté une seule fois dans la passe finale (mouvement continu,
    et il reste immobile pendant les fondus entre scènes)."""
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
    clip_layout = dict(layout, presenter=None, rig=None) if layout else None
    last = len(scenes) - 1
    # le mouvement d'une image continue pendant le fondu vers la suivante (montré au début du clip suivant)
    mlen = [frames[i] + (tf if fade and i < last else 0) for i in range(len(scenes))]
    crf = 18 if quality == "high" else 20  # les clips SONT la vidéo finale : plus de second encodage
    jobs = []
    for i, s in enumerate(scenes):
        mv = s.get("motion") or motions[i]
        prev = None
        if fade and i > 0:
            ps = scenes[i - 1]
            prev = {"image": ps["image"], "motion": ps.get("motion") or motions[i - 1], "n": mlen[i - 1],
                    "offset": frames[i - 1], "tf": max(0, min(tf, frames[i] - 1))}
        extra = [mlen[i], crf, [_file_sig(prev["image"]), prev["motion"], prev["n"], prev["offset"], prev["tf"]]
                 if prev else None]
        key = _clip_key(s["image"], frames[i], width, height, fps, mv, motion_strength, clip_layout, extra=extra)
        jobs.append((i, s["image"], os.path.join(clips_dir, f"c{i:04d}_{key}.mp4"), frames[i], mv, mlen[i], prev))

    # 1) clips, fondus compris (parallèle + cache)
    todo = [j for j in jobs if not os.path.isfile(j[2])]
    workers = max(1, min(6, (os.cpu_count() or 2) // 2))
    done = len(jobs) - len(todo)
    tick(0.02, f"Animation des scènes ({done}/{len(jobs)} en cache)…")
    if todo:
        def one_done():
            nonlocal done
            done += 1
            tick(0.02 + 0.83 * done / len(jobs), f"Animation des scènes {done}/{len(jobs)}")
        stop = cancelled or (lambda: False)
        _run_clips([(dest, (img, dest + ".tmp.mp4", n, width, height, fps, mv, motion_strength, crf),
                     {"layout": clip_layout, "motion_frames": ml, "prev": pv})
                    for (_, img, dest, n, mv, ml, pv) in todo], workers, stop, one_done)
    keep = {os.path.basename(j[2]) for j in jobs}
    for f in os.listdir(clips_dir):  # purge des clips obsolètes
        if f not in keep:
            try:
                os.remove(os.path.join(clips_dir, f))
            except OSError:
                pass

    # 2) assemblage : simple collage des clips (fondus déjà faits), sans réencodage
    tick(0.86, "Assemblage des scènes…")
    assembled = os.path.join(workdir, "assembled.mp4")
    _concat_copy([j[2] for j in jobs], assembled, workdir)
    inputs, in_durs, temp = [assembled], None, [assembled]

    # 3) passe finale : mixage audio (+ sous-titres / présentateur s'il y en a)
    tick(0.9, "Mixage audio et export…")
    ass = build_ass(words or [], os.path.join(workdir, "captions.ass"), width, height, captions, overlays)
    try:
        track = None
        if layout and layout.get("rig"):
            track = os.path.join(workdir, "presenter_track.txt")
            presenter_track(layout, words, total, fps, track)
        _final_pass(workdir, inputs, in_durs, transition_dur, voice_path, out_path, total, ass, music_path,
                    music_volume, normalize, quality, fps, cancelled=cancelled,
                    presenter=layout if layout and layout.get("presenter") else None, track=track)
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


def _rel(path, base):
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return os.path.abspath(path)


def _final_pass(workdir, videos, vdurs, t, voice, out_path, total, ass, music, music_volume, normalize,
                quality, fps, cancelled=None, presenter=None, track=None):
    args = []
    for v in videos:
        args += ["-i", _rel(v, workdir)]
    n = len(videos)
    args += ["-i", os.path.abspath(voice)]
    has_music = bool(music and os.path.isfile(music))
    if has_music:
        args += ["-stream_loop", "-1", "-i", os.path.abspath(music)]
    graph = []
    vlabel = "0:v"  # une seule vidéo : les clips assemblés (fondus déjà intégrés)
    if presenter:  # présentateur incrusté par-dessus toute la vidéo
        pi = n + 1 + (1 if has_music else 0)
        if track:  # animation (bouche, yeux, baguette) calée sur la voix
            args += ["-f", "concat", "-safe", "0", "-i", _rel(track, workdir)]
        else:
            args += ["-loop", "1", "-framerate", str(fps), "-i", _rel(presenter["presenter"], workdir)]
        graph.append(f"[{vlabel}][{pi}:v]overlay=x={presenter['pres_x']}:y='{_bob_expr(presenter)}'"
                     f":eval=frame[pv]")
        vlabel = "pv"
    if ass:
        try:  # chemin relatif = pas d'échappement « C\: » à gérer sous Windows
            fonts = os.path.relpath(FONTS_DIR, workdir).replace("\\", "/")
        except ValueError:  # données sur un autre disque que l'app
            fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
        graph.append(f"[{vlabel}]ass={os.path.basename(ass)}:fontsdir='{fonts}'[v]")
        vmap = "[v]"
    else:
        vmap = f"[{vlabel}]" if (n > 1 or presenter) else "0:v"
    va, vm = n, n + 1  # index des entrées voix / musique
    fade_st = max(0.0, total - 1.5)
    # normalisation sur la voix seule : sur le mixage, loudnorm remonterait la musique à chaque pause
    vnorm = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000," if normalize else ""
    if has_music:
        graph.append(f"[{va}:a]aformat=sample_rates=48000:channel_layouts=stereo,{vnorm}apad,asplit=2[vo][sc]")
        graph.append(f"[{vm}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={float(music_volume):.3f},"
                     f"afade=t=in:d=2[mu]")
        graph.append("[mu][sc]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=450[duck]")
        graph.append("[vo][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]")
    else:
        graph.append(f"[{va}:a]aformat=sample_rates=48000:channel_layouts=stereo,{vnorm}apad[mix]")
    chain = f"[mix]afade=t=out:st={fade_st:.2f}:d=1.5[a]"
    graph.append(chain)
    copy_video = n == 1 and not ass and not presenter
    if copy_video:
        venc = ["-c:v", "copy"]
    elif quality == "high":
        venc = ["-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-crf", "20", "-pix_fmt", "yuv420p"]
    tmp = out_path + ".tmp.mp4"
    media.run(args + ["-filter_complex", ";".join(graph), "-map", vmap, "-map", "[a]"] + venc +
              ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
               "-movflags", "+faststart", os.path.abspath(tmp)], cwd=workdir, cancelled=cancelled)
    os.replace(tmp, out_path)


def thumbnail_frame(video, dest, at=1.0):
    media.run(["-ss", f"{at:.2f}", "-i", video, "-frames:v", "1", "-q:v", "3", dest])
    return dest


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(s, default="video"):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = _SAFE.sub("_", s.strip())[:80].strip("_")
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
                motion_strength=0.1, words=None, script_text="", title="", layout=None, extras=None,
                progress=None, cancelled=None):
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
    segs = None
    if layout and layout.get("rig"):
        from services import presenter
        segs = presenter.track_segments(layout.get("rig_mode"), words or [], total, fps)
    jobs, t0 = [], 0
    for i, s in enumerate(scenes):
        mv = motions[i] if motion != "none" else "none"
        start = t0 / fps
        sub = None
        if segs:
            from services import presenter
            sub = presenter.slice_timeline(segs, t0, frames[i])
        key = _clip_key(s["image"], frames[i], width, height, fps, mv, motion_strength, layout, start, sub)
        jobs.append((s["image"], os.path.join(cdir, f"p{i:04d}_{key}.mp4"), frames[i], mv, start, sub))
        t0 += frames[i]
    todo = [j for j in jobs if not os.path.isfile(j[1])]
    tracks = []
    for j in todo:  # une liste concat par clip (animation du présentateur sur ce morceau)
        if j[5]:
            from services import presenter
            tp = j[1] + ".track.txt"
            paths = {k: os.path.relpath(v, os.path.dirname(tp)) for k, v in layout["rig"].items()}
            presenter.write_concat(j[5], paths, tp, fps)
            tracks.append(tp)
    done = len(jobs) - len(todo)
    tick(0.02, f"Clips {done}/{len(jobs)}…")
    workers = max(1, min(4, (os.cpu_count() or 2) // 2))
    if todo:
        def one_done():
            nonlocal done
            done += 1
            tick(0.02 + 0.83 * done / len(jobs), f"Clips {done}/{len(jobs)}")
        try:
            _run_clips([(dest, (img, dest + ".tmp.mp4", n, width, height, fps, mv, motion_strength, 18),
                         {"layout": layout, "t0": start, "track": dest + ".track.txt" if sub else None})
                        for (img, dest, n, mv, start, sub) in todo],
                       workers, cancelled or (lambda: False), one_done)
        finally:
            for tp in tracks:
                try:
                    os.remove(tp)
                except OSError:
                    pass
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
        for i, (img, dest, n, mv, _, _) in enumerate(jobs):
            z.write(dest, f"clips/{i + 1:0{pad}d}.mp4")
            z.write(img, f"images/{i + 1:0{pad}d}{os.path.splitext(img)[1]}")
        z.write(voice_path, "voiceover.mp3")
        z.writestr("timestamps.txt", "\n".join(stamps) + "\n")
        z.writestr("subtitles.srt", build_srt(words or []))
        z.writestr("script.txt", script_text or "")
        for arc, src in (extras or {}).items():  # fond quadrillé, présentateur détouré…
            if src and os.path.isfile(src):
                z.write(src, arc)
        z.writestr("LISEZMOI.txt", readme)
    os.replace(tmp, zip_path)
    tick(1.0, "Pack montage prêt.")
    return {"path": zip_path, "clips": len(jobs), "duration": round(total, 3)}
