"""Fabrique une vidéo TikTok « pixel » de A à Z à partir d'un script découpé en temps forts.

    python tiktok_engine/build.py <dossier_de_travail> --script tiktok_engine/videos/<nom>/script.json [--stills]

Étapes (chacune est sautée si son fichier existe déjà) :
  voice.mp3     voix ElevenLabs via Algrow (clé ALGROW_API_KEY), ou déposée à la main (+ words.srt)
  words.json    mots datés : SRT d'Algrow s'il existe, sinon Whisper sur l'audio
  timeline.json les éléments visuels calés sur les mots (ancres "mot", "mot#2", "mot+0.3", nombre = secondes)
  mix.wav       voix + bruitages synthétisés (impact, tampon, tic de compteur), -14 LUFS
  video.mp4     rendu Chromium image par image (render.mjs)
  check/        planche d'images fixes pour la relecture
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
SR = 44100
LEAD = 0.06          # un visuel arrive très légèrement avant le mot


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def tokens(text):
    """Mots normalisés ; « 422 000 » devient un seul nombre « 422000 »."""
    raw = [t for t in re.split(r"[\s  ]+", text) if norm(t)]
    out = []
    for t in raw:
        n = norm(t)
        if out and re.fullmatch(r"\d{3}", n) and re.fullmatch(r"\d+", out[-1][0]) and not re.search(r"[.,;:!?]$", out[-1][1]):
            out[-1] = (out[-1][0] + n, out[-1][1] + " " + t)
        else:
            out.append((n, t))
    return out


# ---------------------------------------------------------------- voix et mots datés
def make_voice(work, script):
    dest = os.path.join(work, "voice.mp3")
    if os.path.exists(dest):
        return dest
    from services import tts
    v = script["voice"]
    text = " ".join(b["say"].strip() for b in script["beats"])
    words = tts._algrow(text, v["voice_id"], dest, sub="elevenlabs", model=v.get("model", "eleven_v4"),
                        speed=v.get("speed", 1.0), srt=True)
    if words:
        with open(os.path.join(work, "words.json"), "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False)
    return dest


def fake_voice(work, script):
    """Aperçu sans crédits : mots datés estimés (≈ 15 caractères/s) et voix muette de la même durée."""
    words, t = [], 0.3
    for b in script["beats"]:
        for raw in b["say"].split():
            d = (len(raw) + 1) / 15.0
            words.append({"w": raw, "s": round(t, 3), "e": round(t + d, 3)})
            t += d + (0.35 if re.search(r"[.?!:]$", raw) else 0.12 if raw.endswith(",") else 0)
    with open(os.path.join(work, "words.json"), "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{t + 0.3:.2f}",
                    "-c:a", "libmp3lame", "-b:a", "64k", os.path.join(work, "voice.mp3")], check=True)


def wav16(src, dst):
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", dst], check=True)
    with wave.open(dst) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def timed_words(work):
    path = os.path.join(work, "words.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    srt = os.path.join(work, "words.srt")
    if os.path.exists(srt):
        from services.tts import _srt_words
        words = _srt_words(open(srt, encoding="utf-8").read())
    else:
        from faster_whisper import WhisperModel
        from services import align
        audio = wav16(os.path.join(work, "voice.mp3"), os.path.join(work, "voice16.wav"))
        model = WhisperModel(align._model_dir("fr"), device="cpu", compute_type="int8")
        segs, _ = model.transcribe(audio, language="fr", word_timestamps=True, beam_size=5)
        words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in s.words]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    return words


def align_script(script, words):
    """Pour chaque mot du script : (début, fin) mesurés sur la voix."""
    stoks = []
    for bi, b in enumerate(script["beats"]):
        for n, raw in tokens(b["say"]):
            stoks.append({"beat": bi, "n": n, "raw": raw})
    glued = []                        # Whisper coupe « c 'est », « lui -même » : on recolle au mot précédent
    for w in words:
        if glued and re.match(r"^['’-]", w["w"].strip()):
            glued[-1] = {"w": glued[-1]["w"] + w["w"].strip(), "s": glued[-1]["s"], "e": w["e"]}
        else:
            glued.append(dict(w))
    words = glued
    wtoks = []
    for w in words:
        for n, _ in tokens(w["w"]):
            wtoks.append({"n": n, "s": w["s"], "e": w["e"]})
    # nombres collés côté voix (« 422 » « 000 ») déjà fusionnés par tokens() mot à mot : on refusionne
    merged = []
    for w in wtoks:
        if merged and re.fullmatch(r"\d{3}", w["n"]) and re.fullmatch(r"\d+", merged[-1]["n"]):
            merged[-1] = {"n": merged[-1]["n"] + w["n"], "s": merged[-1]["s"], "e": w["e"]}
        else:
            merged.append(dict(w))
    sm = difflib.SequenceMatcher(None, [t["n"] for t in stoks], [w["n"] for w in merged], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                stoks[i1 + k]["s"], stoks[i1 + k]["e"] = merged[j1 + k]["s"], merged[j1 + k]["e"]
        elif tag == "replace":
            # mots mal entendus (« poux » → « poues ») : appariés par ressemblance, dans l'ordre
            j = j1
            for i in range(i1, i2):
                best, score = None, 0.5
                for jj in range(j, j2):
                    r = difflib.SequenceMatcher(None, stoks[i]["n"], merged[jj]["n"]).ratio()
                    if r > score:
                        best, score = jj, r
                if best is not None:
                    stoks[i]["s"], stoks[i]["e"] = merged[best]["s"], merged[best]["e"]
                    j = best + 1
    # mots non reconnus : interpolés entre les voisins
    known = [i for i, t in enumerate(stoks) if "s" in t]
    if not known:
        raise SystemExit("alignement impossible : aucun mot reconnu")
    for i, t in enumerate(stoks):
        if "s" in t:
            continue
        prev = max([k for k in known if k < i], default=None)
        nxt = min([k for k in known if k > i], default=None)
        if prev is None:
            t["s"] = t["e"] = stoks[nxt]["s"]
        elif nxt is None:
            t["s"] = t["e"] = stoks[prev]["e"]
        else:
            f = (i - prev) / (nxt - prev)
            t["s"] = t["e"] = stoks[prev]["e"] + f * (stoks[nxt]["s"] - stoks[prev]["e"])
    print(f"alignement : {len(known)}/{len(stoks)} mots reconnus", flush=True)
    return stoks


# ---------------------------------------------------------------- timeline
def resolve(anchor, beat_toks, beat_start, beat_end):
    if anchor is None:
        return None
    if isinstance(anchor, (int, float)):
        return beat_start + anchor
    m = re.fullmatch(r"\s*(.+?)(?:#(\d+))?\s*([+-]\s*[\d.]+)?\s*", str(anchor))
    word, nth, off = m.group(1), int(m.group(2) or 1), float((m.group(3) or "0").replace(" ", ""))
    if word == "start":
        return beat_start + off
    if word == "end":
        return beat_end + off
    key, end = norm(word), False
    if key.endswith("fin"):          # « mot.fin » = fin du mot
        pass
    if word.endswith(">"):
        key, end = norm(word[:-1]), True
    def elided(raw):                 # « l'hiver » répond aussi à l'ancre « hiver »
        return norm(re.sub(r"^\w{1,2}['’]", "", raw))
    hits = [t for t in beat_toks if t["n"].startswith(key) or elided(t["raw"]).startswith(key)]
    if len(hits) < nth:
        raise SystemExit(f"ancre introuvable : {anchor!r} dans « {' '.join(t['raw'] for t in beat_toks)} »")
    t = hits[nth - 1]
    return (t["e"] if end else t["s"] - LEAD) + off


def build_timeline(script, stoks, duration):
    scenes, cur = [], None
    beats = script["beats"]
    for bi, b in enumerate(beats):
        bt = [t for t in stoks if t["beat"] == bi]
        start, end = bt[0]["s"] - LEAD, bt[-1]["e"]
        if bi == 0:
            start = 0.0
        if not b.get("keep") or cur is None:
            cur = {"start": round(max(0.0, start), 3), "els": []}
            for k in ("glow", "particles", "density", "wind"):
                if k in b:
                    cur[k] = b[k]
            scenes.append(cur)
        for e in b.get("els", []):
            e = dict(e)
            e["at"] = round(resolve(e.get("at", 0), bt, start, end), 3)
            for k in ("out", "litAt", "drawAt"):
                if k in e:
                    e[k] = round(resolve(e[k], bt, start, end), 3)
            for lst in ("keys", "moves"):
                for item in e.get(lst, []):
                    item["at"] = round(resolve(item["at"], bt, start, end), 3)
            if isinstance(e.get("strike"), dict):
                e["strike"]["at"] = round(resolve(e["strike"]["at"], bt, start, end), 3)
            cur["els"].append(e)
    art = os.path.join(os.path.dirname(os.path.abspath(script["_path"])), "art")
    images = {n: "/abs" + os.path.join(art, n + ".png") for n in script.get("art", {})
              if os.path.exists(os.path.join(art, n + ".png"))}
    return {"duration": round(duration, 3), "fps": script.get("fps", 30), "palette": script.get("palette", {}),
            "images": images, "scenes": scenes}


# ---------------------------------------------------------------- bruitages
def _env(n, a=0.002, r=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def sfx(kind):
    if kind == "impact":
        n = int(0.6 * SR); t = np.arange(n) / SR
        f = 120 * np.exp(-t * 5) + 38
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.003, 0.22)
        s += np.random.RandomState(1).randn(n) * _env(n, 0.001, 0.025) * 0.5
        return s * 0.9
    if kind == "stamp":
        n = int(0.18 * SR); t = np.arange(n) / SR
        s = np.sin(2 * np.pi * 150 * t) * _env(n, 0.001, 0.05)
        s += np.convolve(np.random.RandomState(2).randn(n), np.ones(30) / 30, "same") * _env(n, 0.001, 0.03) * 3
        return s * 0.8
    if kind == "pop":
        n = int(0.09 * SR); t = np.arange(n) / SR
        f = np.linspace(520, 1040, n)
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * _env(n, 0.001, 0.03) * 0.18
    if kind == "tick":
        n = int(0.025 * SR); t = np.arange(n) / SR
        return np.sign(np.sin(2 * np.pi * 1500 * t)) * _env(n, 0.0005, 0.008) * 0.12
    if kind == "rumble":
        n = int(3.0 * SR); t = np.arange(n) / SR
        noise = np.convolve(np.random.RandomState(3).randn(n), np.ones(400) / 400, "same") * 6
        s = (np.sin(2 * np.pi * 46 * t) * 0.5 + noise) * np.minimum(1, t / 0.4) * np.exp(-t / 1.6)
        return s * 0.35
    if kind == "whoosh":
        n = int(0.5 * SR); t = np.arange(n) / SR
        s = np.random.RandomState(4).randn(n)
        k = np.linspace(4, 60, n).astype(int)
        s = np.array([s[max(0, i - k[i]):i + 1].mean() for i in range(n)]) * 4
        return s * np.sin(np.pi * t / t[-1]) * 0.25
    raise ValueError(kind)


def cues(timeline):
    out = []
    for sc in timeline["scenes"]:
        for e in sc["els"]:
            at, kind = e["at"], e.get("in")
            if kind == "slam" or e.get("flash"):
                out.append((at, "impact"))
            elif e.get("type") == "stamp":
                out.append((at + 0.06, "stamp"))
            elif kind == "pop" and e.get("type") in ("sprite", "text"):
                out.append((at, "pop"))
            if e.get("type") == "counter":
                d = e.get("dur", 1.2)
                out += [(at + k * 0.06, "tick") for k in range(int(d / 0.06))]
                for kk in e.get("keys", []):
                    out += [(kk["at"] + k * 0.06, "tick") for k in range(int(kk.get("dur", 1.2) / 0.06))]
            if e.get("type") == "endcard":
                out.append((at, "whoosh"))
            if e.get("sfx"):
                out.append((at, e["sfx"]))
    return out


def mix(work, timeline):
    dst = os.path.join(work, "mix.wav")
    if os.path.exists(dst):
        return dst
    raw = os.path.join(work, "voice44.wav")
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-i", os.path.join(work, "voice.mp3"), "-ac", "1", "-ar", str(SR), raw],
                   check=True)
    with wave.open(raw) as w:
        voice = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = int(timeline["duration"] * SR) + SR
    bus = np.zeros(n, np.float32)
    bus[:len(voice)] += voice
    fx = np.zeros(n, np.float32)
    cache = {}
    for at, kind in cues(timeline):
        s = cache.setdefault(kind, sfx(kind).astype(np.float32))
        i = int(max(0, at) * SR)
        j = min(n, i + len(s))
        fx[i:j] += s[:j - i]
    bus += fx * 0.32
    bus = np.clip(bus, -1, 1)
    tmp = os.path.join(work, "mix_raw.wav")
    with wave.open(tmp, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((bus * 32767).astype(np.int16).tobytes())
    # loudnorm en deux passes : une seule passe reste ~2 dB sous la cible
    probe = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", tmp, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(probe[probe.rindex("{"):probe.rindex("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-i", tmp, "-af", af, "-ar", str(SR), "-ac", "2", dst], check=True)
    return dst


def audio_duration(path):
    out = subprocess.run([ffmpeg_exe(), "-i", path], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def covers(work, script):
    """Miniatures 1080×1920 (bloc "covers" du script : une liste d'éléments par miniature, sans animation)."""
    out = os.path.join(work, "covers")
    os.makedirs(out, exist_ok=True)
    base = build_timeline({**script, "beats": []}, [], 1.0)
    for i, els in enumerate(script.get("covers", [])):
        tl = dict(base, duration=1.0, scenes=[{"start": 0, "glow": {"y": 520, "r": 300, "a": 0.2},
                                                "els": [dict({k: v for k, v in e.items() if k != "flash"}, at=0,
                                                             **{"in": "none"}) for e in els]}])
        path = os.path.join(out, f"cover_{i + 1}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tl, f, ensure_ascii=False)
        subprocess.run([shutil.which("node") or "node", os.path.join(HERE, "render.mjs"), "--spec", path,
                        "--stills", "0.5", "--stills-dir", out], check=True)
        os.replace(os.path.join(out, "still_0.50.png"), os.path.join(out, f"cover_{i + 1}.png"))
    print("COVERS DONE", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--script", required=True)
    ap.add_argument("--stills", action="store_true", help="planche d'images fixes seulement, pas de rendu vidéo")
    ap.add_argument("--workers", default="3")
    ap.add_argument("--fake-voice", action="store_true", help="minutage estimé et voix muette (aperçu sans crédits)")
    ap.add_argument("--covers", action="store_true", help="seulement les miniatures (bloc \"covers\" du script)")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    script = json.load(open(a.script, encoding="utf-8"))
    script["_path"] = a.script
    if a.covers:
        return covers(a.work, script)
    if a.fake_voice:
        fake_voice(a.work, script)
    make_voice(a.work, script)
    words = timed_words(a.work)
    stoks = align_script(script, words)
    tail = script.get("tail", 2.0)
    timeline = build_timeline(script, stoks, audio_duration(os.path.join(a.work, "voice.mp3")) + tail)
    tl = os.path.join(a.work, "timeline.json")
    with open(tl, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=1)
    print("TIMELINE DONE", flush=True)
    node = shutil.which("node") or "node"
    chk = os.path.join(a.work, "check")
    times = [round(x, 2) for x in np.arange(0.5, timeline["duration"], 1.5)]
    subprocess.run([node, os.path.join(HERE, "render.mjs"), "--spec", tl, "--stills", ",".join(map(str, times)),
                    "--stills-dir", chk], check=True)
    files = [os.path.join(chk, f"still_{t:.2f}.png") for t in times]
    cols = 8
    rows = [files[i:i + cols] for i in range(0, len(files), cols)]
    for r, row in enumerate(rows):
        inputs = sum((["-i", f] for f in row), [])
        filt = "".join(f"[{i}]scale=180:-1[v{i}];" for i in range(len(row))) + "".join(f"[v{i}]" for i in range(len(row)))
        filt += f"hstack={len(row)}" if len(row) > 1 else "null"
        subprocess.run([ffmpeg_exe(), "-v", "error", "-y", *inputs, "-filter_complex", filt,
                        os.path.join(chk, f"sheet_{r:02d}.jpg")], check=True)
    print("SHEETS DONE", flush=True)
    if a.stills:
        return
    mixed = mix(a.work, timeline)
    print("MIX DONE", flush=True)
    subprocess.run([node, os.path.join(HERE, "render.mjs"), "--spec", tl, "--audio", mixed, "--workers", a.workers,
                    "--out", os.path.join(a.work, "video.mp4"), "--ffmpeg", ffmpeg_exe()], check=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
