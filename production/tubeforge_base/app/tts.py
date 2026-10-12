"""Synthèse vocale avec timings au mot près.

- ElevenLabs (par défaut) : endpoint /with-timestamps -> alignement caractère par caractère.
- Edge (secours gratuit, seulement si choisi explicitement dans le style/projet).

Sortie commune : liste de mots {"w", "s", "e", "c0", "c1"} où c0/c1 sont les positions
du mot dans le texte du script (pour retrouver la ponctuation et découper les scènes).
"""
import asyncio
import base64
import hashlib
import json
import re
import time
import wave
from pathlib import Path

import httpx

from . import config, events, local_tts
from .util import ffprobe_duration, run_cmd

ELEVEN_URL = "https://api.elevenlabs.io/v1"
DELIVERY = {"stable": 0.75, "balanced": 0.5, "creative": 0.3}
SILENCE_MODES = {"smooth": 0.75, "natural": 0.5, "jumpy": 0.25}
# Voix Edge par défaut selon la langue du script (si la voix choisie n'est pas dans la bonne langue)
EDGE_BY_LANG = {"french": "fr-FR-RemyMultilingualNeural", "english": "en-US-AndrewMultilingualNeural",
                "spanish": "es-ES-AlvaroNeural", "german": "de-DE-ConradNeural", "italian": "it-IT-DiegoNeural",
                "portuguese": "pt-BR-AntonioNeural", "arabic": "ar-SA-HamedNeural"}
# Voix standard d'ElevenLabs (proposées si la clé n'a pas la permission de lister les voix)
PREMADE_VOICES = [
    {"voice_id": "nPczCjzI2devNBz1zQrb", "name": "Brian", "labels": "homme, américain, grave — narration"},
    {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "labels": "homme, américain, grave"},
    {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "labels": "homme, britannique, chaleureux — narration"},
    {"voice_id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel", "labels": "homme, britannique, posé — info"},
    {"voice_id": "pqHfZKP75CvOlQylNhV4", "name": "Bill", "labels": "homme âgé, américain — documentaire"},
    {"voice_id": "cjVigY5qzO86Huf0OWal", "name": "Eric", "labels": "homme, américain, doux"},
    {"voice_id": "iP95p4xoKVk53GoZ742B", "name": "Chris", "labels": "homme, américain, décontracté"},
    {"voice_id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam", "labels": "jeune homme, américain"},
    {"voice_id": "N2lVS1w4EtoT3dr4eOWO", "name": "Callum", "labels": "homme, voix rauque"},
    {"voice_id": "CwhRBWXzGAHq8TQ4Fs17", "name": "Roger", "labels": "homme, américain, assuré"},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "labels": "femme, américaine, douce"},
    {"voice_id": "pFZP5JQG7iQjIQuC4Bku", "name": "Lily", "labels": "femme, britannique — narration"},
    {"voice_id": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice", "labels": "femme, britannique, claire"},
    {"voice_id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "labels": "femme, américaine, chaleureuse"},
]

_tts_sem: asyncio.Semaphore | None = None


def tts_sem() -> asyncio.Semaphore:
    global _tts_sem
    if _tts_sem is None:
        _tts_sem = asyncio.Semaphore(max(1, config.get_int("TTS_CONCURRENCY")))
    return _tts_sem


class TTSError(Exception):
    pass


def split_text(text: str, max_chars: int) -> list[tuple[int, str]]:
    """Découpe le texte en morceaux (offset, texte) aux fins de paragraphes/phrases."""
    chunks: list[tuple[int, str]] = []
    pos, n = 0, len(text)
    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            break
        end = min(n, pos + max_chars)
        if end < n:
            window = text[pos:end]
            cut = window.rfind("\n")
            if cut < max_chars * 0.5:
                m = list(re.finditer(r"[.!?…][\"'”»)]?\s", window))
                cut = m[-1].end() if m and m[-1].end() > max_chars * 0.4 else -1
            if cut < max_chars * 0.3:
                cut = window.rfind(" ")
            end = pos + (cut if cut > 0 else len(window))
        chunk = text[pos:end].rstrip()
        if chunk:
            chunks.append((pos, chunk))
        pos = end
    return chunks


def words_from_chars(chunk: str, offset: int, chars: list[str], starts: list[float], ends: list[float]) -> list[dict]:
    """Construit les mots à partir d'un alignement caractère par caractère (ElevenLabs)."""
    times: list[tuple[float, float] | None] = [None] * len(chunk)
    p = 0
    for ch, s, e in zip(chars, starts, ends):
        if p >= len(chunk):
            break
        if chunk[p] == ch:
            times[p] = (s, e)
            p += 1
            continue
        look = chunk.find(ch, p, p + 4) if ch.strip() else -1
        if look >= 0:
            times[look] = (s, e)
            p = look + 1
    words = []
    for m in re.finditer(r"\S+", chunk):
        ts = [t for t in times[m.start():m.end()] if t]
        if not ts:
            continue
        words.append({"w": m.group(), "s": ts[0][0], "e": ts[-1][1],
                      "c0": offset + m.start(), "c1": offset + m.end()})
    return words


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def align_tokens(chunk: str, offset: int, tokens: list[tuple[str, float, float]]) -> list[dict]:
    """Associe les mots renvoyés par Edge (sans ponctuation) aux positions dans le texte."""
    words, cursor = [], 0
    low = chunk.lower()
    for tok, s, e in tokens:
        t = tok.strip()
        if not t:
            continue
        idx, look = -1, cursor
        while True:  # cherche le jeton en début de mot
            idx = low.find(t.lower(), look, cursor + len(t) + 60)
            if idx <= 0 or not chunk[idx - 1].isalnum():
                break
            look = idx + 1
        if idx < 0:
            nt = _norm(t)
            for m in re.finditer(r"\S+", chunk[cursor:cursor + len(t) + 60]):
                if nt and nt in _norm(m.group()):
                    idx = cursor + m.start()
                    t = m.group()
                    break
        if idx < 0:
            words.append({"w": t, "s": s, "e": e, "c0": offset + cursor, "c1": offset + cursor})
            continue
        end = idx + len(t)
        while end < len(chunk) and not chunk[end].isspace():  # garde la ponctuation collée
            end += 1
        words.append({"w": chunk[idx:end], "s": s, "e": e, "c0": offset + idx, "c1": offset + end})
        cursor = end
    return words


def _cache_key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


async def _eleven_chunk(offset: int, chunk: str, prev_text: str, next_text: str,
                        vs: dict, cache: Path) -> dict:
    """Un morceau ElevenLabs. Mis en cache : une relance ne refacture pas les morceaux déjà faits."""
    key = config.get("ELEVENLABS_API_KEY")
    model = vs.get("model_id") or config.get("TTS_MODEL")
    body = {
        "text": chunk,
        "model_id": model,
        "voice_settings": {
            "stability": DELIVERY.get(vs.get("delivery", "balanced"), 0.5),
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": max(0.7, min(1.2, float(vs.get("speed", 1.0)))),
        },
    }
    if "v3" not in model:  # La variante expressive ne gère pas la continuité previous/next
        if prev_text:
            body["previous_text"] = prev_text[-600:]
        if next_text:
            body["next_text"] = next_text[:300]
    ck = "eleven_" + _cache_key("eleven", vs.get("voice_id"), body)
    mp3, js = cache / f"{ck}.mp3", cache / f"{ck}.json"
    if mp3.exists() and js.exists():
        al = json.loads(js.read_text(encoding="utf-8"))
    else:
        url = f"{ELEVEN_URL}/text-to-speech/{vs['voice_id']}/with-timestamps?output_format=mp3_44100_128"
        async with tts_sem():
            last = None
            for attempt in range(5):
                try:
                    async with httpx.AsyncClient(timeout=300) as c:
                        r = await c.post(url, json=body, headers={"xi-api-key": key})
                    if r.status_code == 200:
                        break
                    last = f"HTTP {r.status_code}: {r.text[:400]}"
                    if "quota_exceeded" in r.text:
                        m = re.search(r"(\d+) credits remaining, while (\d+) credits are required", r.text)
                        left = f" Il reste {m.group(1)} crédits, ce morceau en demande {m.group(2)}." if m else ""
                        raise TTSError("Crédits ElevenLabs épuisés." + left + " Les morceaux déjà générés sont "
                                       "gardés en cache : relance quand tes crédits sont rechargés, ou choisis "
                                       "la voix de secours (Edge).")
                    if r.status_code in (401, 403, 404, 422) or (r.status_code == 400 and "busy" not in r.text):
                        raise TTSError(f"ElevenLabs a refusé la requête — {last}")
                except httpx.TransportError as e:
                    last = f"réseau : {e}"
                await asyncio.sleep(3 * 2 ** attempt)
            else:
                raise TTSError(f"ElevenLabs indisponible après 5 essais — {last}")
        data = r.json()
        al = data.get("alignment") or data.get("normalized_alignment")
        if not al:
            raise TTSError("ElevenLabs n'a pas renvoyé d'alignement")
        mp3.write_bytes(base64.b64decode(data["audio_base64"]))
        js.write_text(json.dumps(al), encoding="utf-8")
    words = words_from_chars(chunk, offset, al["characters"], al["character_start_times_seconds"],
                             al["character_end_times_seconds"])
    return {"path": mp3, "words": words}


async def _edge_chunk(offset: int, chunk: str, vs: dict, cache: Path) -> dict:
    import edge_tts

    rate = int(round((float(vs.get("speed", 1.0)) - 1.0) * 100))
    voice = vs.get("edge_voice") or "en-US-AndrewMultilingualNeural"
    want = EDGE_BY_LANG.get(str(vs.get("language", "")).lower())
    if want and voice[:2] != want[:2]:  # voix anglaise sur un script français, etc.
        voice = want
    ck = "edge_" + _cache_key("edge", voice, rate, chunk)
    mp3, js = cache / f"{ck}.mp3", cache / f"{ck}.json"
    if mp3.exists() and js.exists():
        tokens = json.loads(js.read_text(encoding="utf-8"))
    else:
        async with tts_sem():
            for attempt in range(4):
                tokens = []
                try:
                    comm = edge_tts.Communicate(chunk, voice, rate=f"{rate:+d}%", boundary="WordBoundary")
                    with open(mp3, "wb") as fh:
                        async for ev in comm.stream():
                            if ev["type"] == "audio":
                                fh.write(ev["data"])
                            elif ev["type"] == "WordBoundary":
                                s = ev["offset"] / 1e7
                                tokens.append((ev["text"], s, s + ev["duration"] / 1e7))
                    break
                except Exception as e:  # noqa: BLE001 — service gratuit parfois capricieux
                    mp3.unlink(missing_ok=True)
                    if attempt == 3:
                        raise TTSError(f"Edge TTS a échoué : {e}")
                    await asyncio.sleep(2 * (attempt + 1))
        js.write_text(json.dumps(tokens), encoding="utf-8")
    return {"path": mp3, "words": align_tokens(chunk, offset, [tuple(t) for t in tokens])}


def _read_wav(path: Path) -> tuple[wave._wave_params, bytes]:
    with wave.open(str(path), "rb") as w:
        return w.getparams(), w.readframes(w.getnframes())


def cut_silences(wav_path: Path, words: list[dict], keep: float) -> list[dict]:
    """Réduit chaque silence entre deux mots à `keep` secondes et recale les timings."""
    params, raw = _read_wav(wav_path)
    rate, bpf = params.framerate, params.sampwidth * params.nchannels
    total = len(raw) / bpf / rate
    cuts = []  # (début, fin) en secondes à supprimer
    bounds = [(0.0, 0.0)] + [(w["s"], w["e"]) for w in words] + [(total, total)]
    for (s0, e0), (s1, e1) in zip(bounds, bounds[1:]):
        gap = s1 - e0
        if gap > keep + 0.05:
            half = keep / 2
            cuts.append((e0 + half, s1 - half))
    if not cuts:
        return words
    out, last = [], 0
    for a, b in cuts:
        ia, ib = int(a * rate) * bpf, int(b * rate) * bpf
        out.append(raw[last:ia])
        last = ib
    out.append(raw[last:])
    with wave.open(str(wav_path), "wb") as w:
        w.setparams(params)
        w.writeframes(b"".join(out))

    def shift(t: float) -> float:
        removed = 0.0
        for a, b in cuts:
            if t >= b:
                removed += b - a
            elif t > a:
                removed += t - a
        return t - removed

    return [w | {"s": round(shift(w["s"]), 3), "e": round(shift(w["e"]), 3)} for w in words]


async def synthesize(text: str, vs: dict, out_dir: Path, progress=None) -> dict:
    """Génère voice.mp3 + mots alignés. `vs` = réglages voix du projet."""
    provider = vs.get("provider", "elevenlabs")
    if provider == "algrow":
        from . import studio_bridge
        return await studio_bridge.voice(text, vs, out_dir, progress)
    cache = out_dir / "tts_cache"
    cache.mkdir(parents=True, exist_ok=True)
    if provider == "elevenlabs":
        if not config.get("ELEVENLABS_API_KEY"):
            raise TTSError("Clé ElevenLabs manquante : ajoute-la dans Réglages (ELEVENLABS_API_KEY).")
        if not vs.get("voice_id"):
            raise TTSError("Aucune voix ElevenLabs choisie.")
        chunks = split_text(text, 2400)
    elif provider == "local":
        if not local_tts.installed():
            raise TTSError("Voix locale non installée.")
        chunks = local_tts.split_for_local(text)
    else:
        chunks = split_text(text, 1500)
    done = 0
    t_start = time.time()
    who = (f"ElevenLabs ({vs.get('voice_name') or vs.get('voice_id')}, {vs.get('model_id')})"
           if provider == "elevenlabs" else
           f"voix locale Chatterbox ({vs.get('local_voice') or local_tts.default_voice(vs.get('language'))})"
           if provider == "local" else f"Edge ({vs.get('edge_voice')})")
    events.log(f"Voix off : {len(text):,} caractères en {len(chunks)} segment(s) via {who}".replace(",", " "))

    async def run(i, off, ch, pause=0.0):
        nonlocal done
        if provider == "local":
            res = await local_tts.chunk_audio(off, ch, pause, vs, cache)
        elif provider == "elevenlabs":
            prev_t = text[max(0, off - 600):off]
            nxt = text[off + len(ch):off + len(ch) + 300]
            res = await _eleven_chunk(off, ch, prev_t, nxt, vs, cache)
        else:
            res = await _edge_chunk(off, ch, vs, cache)
        done += 1
        if provider != "local" or done % 10 == 0 or done == len(chunks):
            el = time.time() - t_start
            events.log(f"✓ Segment voix {done}/{len(chunks)} — reste ≈ "
                       f"{events.fmt_duration(el / done * (len(chunks) - done))}", "ok")
        if progress:
            progress(done, len(chunks))
        return res

    if provider == "local":
        await local_tts.ensure_server(local_tts.engine_for(vs))  # démarre le moteur et charge le modèle
        results = await asyncio.gather(*(run(i, off, ch, pause) for i, (off, ch, pause) in enumerate(chunks)))
    else:
        results = await asyncio.gather(*(run(i, off, ch) for i, (off, ch) in enumerate(chunks)))

    # concaténation + recalage des timings
    words, t = [], 0.0
    for res in results:
        dur = ffprobe_duration(res["path"])
        for w in res["words"]:
            words.append(w | {"s": round(w["s"] + t, 3), "e": round(min(w["e"], dur) + t, 3)})
        t += dur
    wav = out_dir / "voice.wav"
    inputs = []
    for res in results:
        inputs += ["-i", res["path"].name]
    n = len(results)
    filt = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    await run_cmd([config.get("FFMPEG"), "-y", "-v", "error", *inputs, "-filter_complex", filt, "-map", "[a]",
                   "-ar", "44100", "-ac", "1", str(wav.resolve())], cwd=cache)
    keep = SILENCE_MODES.get(vs.get("cut_silences", "none"))
    if keep:
        words = cut_silences(wav, words, keep)
    mp3 = out_dir / "voice.mp3"
    speed = float(vs.get("speed", 1.0))
    tempo = []
    if provider == "local" and abs(speed - 1.0) > 0.01:  # Chatterbox n'a pas de réglage de vitesse
        tempo = ["-filter:a", f"atempo={speed:.3f}"]
        words = [w | {"s": round(w["s"] / speed, 3), "e": round(w["e"] / speed, 3)} for w in words]
    await run_cmd([config.get("FFMPEG"), "-y", "-v", "error", "-i", str(wav), *tempo, "-c:a", "libmp3lame",
                   "-b:a", "192k", str(mp3)])
    duration = ffprobe_duration(mp3)
    events.log(f"✓ Voix off prête : {events.fmt_duration(duration)} d'audio, {len(words)} mots calés "
               f"(en {events.fmt_duration(time.time() - t_start)})", "ok")
    wav.unlink(missing_ok=True)
    used = {r["path"].stem for r in results}
    prefix = {"elevenlabs": "eleven_", "local": "local_"}.get(provider, "edge_")
    for f in cache.glob(prefix + "*"):  # ménage, sans jamais toucher aux morceaux payés d'un autre fournisseur
        if f.stem not in used:
            f.unlink(missing_ok=True)
    return {"file": "voice.mp3", "duration": duration, "words": words}


async def eleven_voices() -> list[dict]:
    key = config.get("ELEVENLABS_API_KEY")
    if not key:
        return []
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{ELEVEN_URL}/voices", headers={"xi-api-key": key})
    if r.status_code == 401 and "voices_read" in r.text:
        return [v | {"category": "premade"} for v in PREMADE_VOICES]
    if r.status_code != 200:
        raise TTSError(f"ElevenLabs /voices : HTTP {r.status_code} {r.text[:300]}")
    out = []
    for v in r.json().get("voices", []):
        labels = v.get("labels") or {}
        out.append({
            "voice_id": v["voice_id"], "name": v.get("name"), "category": v.get("category"),
            "preview_url": v.get("preview_url"),
            "labels": ", ".join(str(x) for x in labels.values() if x),
        })
    return out
