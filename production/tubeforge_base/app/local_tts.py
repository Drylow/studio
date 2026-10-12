"""Client de la voix locale (Chatterbox sur la carte AMD, licence MIT).

TubeForge démarre tout seul LOCAL_TTS_WORKERS processus local_tts/server.py (environnement
Python séparé avec PyTorch ROCm) la première fois qu'une voix locale est demandée, puis leur
répartit le texte groupe de phrases par groupe de phrases.

Chatterbox ne donne pas de timings au mot : comme on génère par groupes de phrases, on connaît
exactement le début et la fin de chaque groupe ; les mots sont répartis à l'intérieur
proportionnellement à leur longueur (précis à quelques dixièmes de seconde).
"""
import asyncio
import hashlib
import io
import json
import os
import re
import subprocess
import time
import wave
from pathlib import Path

import httpx

from . import config, events

ROOT = config.ROOT / "local_tts"
VOICES_DIR = ROOT / "voices"
# environnement Python séparé (PyTorch ROCm pour la carte AMD), hors du dossier du projet car
# ROCm n'aime pas les espaces dans les chemins
VENV_PY = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TubeForge" / "tts-venv" / "Scripts" / "python.exe"
SERVER = ROOT / "server.py"
LANG_CODES = {"english": "en", "french": "fr", "spanish": "es", "german": "de", "italian": "it",
              "portuguese": "pt", "arabic": "ar", "dutch": "nl", "polish": "pl", "turkish": "tr",
              "russian": "ru", "japanese": "ja", "chinese": "zh", "korean": "ko", "hindi": "hi"}
CHARS_PER_SEC = {"en": 17.0, "fr": 17.0}  # mesuré sur Chatterbox (pauses comprises)

_procs: dict[int, subprocess.Popen] = {}
_free: asyncio.Queue | None = None
_eng_sems: dict[str, asyncio.Semaphore] = {}
FAIR_WAIT = 180  # s : au-delà, l'autre langue passe (les deux modèles ne tiennent pas ensemble sur la carte)
_gate = {"engine": None, "active": 0, "waiting": {}, "since": {}}
_gate_cond: asyncio.Condition | None = None


class _EngineGate:
    """Un seul modèle Chatterbox à la fois : les phrases sont regroupées par moteur. Sans ça, une vidéo FR
    (multilingual) et une vidéo EN (turbo) en parallèle font recharger le modèle à chaque phrase."""

    def __init__(self, engine: str):
        self.engine = engine

    def _ok(self) -> bool:
        g, now = _gate, time.time()
        if g["engine"] is None:  # carte libre : priorité au moteur qui attend depuis le plus longtemps
            return min(g["since"], key=g["since"].get) == self.engine
        if g["engine"] != self.engine:
            return False
        return not any(e != self.engine and n > 0 and now - g["since"].get(e, now) > FAIR_WAIT
                       for e, n in g["waiting"].items())

    async def __aenter__(self):
        global _gate_cond
        if _gate_cond is None:
            _gate_cond = asyncio.Condition()
        g = _gate
        async with _gate_cond:
            g["waiting"][self.engine] = g["waiting"].get(self.engine, 0) + 1
            g["since"].setdefault(self.engine, time.time())
            try:
                while not self._ok():
                    try:
                        await asyncio.wait_for(_gate_cond.wait(), 5)
                    except asyncio.TimeoutError:
                        pass
            finally:
                g["waiting"][self.engine] -= 1
                if not g["waiting"][self.engine]:
                    g["since"].pop(self.engine, None)
            g["engine"] = self.engine
            g["active"] += 1
        return self

    async def __aexit__(self, *exc):
        async with _gate_cond:
            _gate["active"] -= 1
            if _gate["active"] <= 0:
                _gate["active"], _gate["engine"] = 0, None
            _gate_cond.notify_all()


def parallel_for(engine: str) -> int:
    """Générations simultanées par moteur (mesuré RX 7700 XT : 2 en parallèle = +45 % en multilingue,
    +65 % en Turbo par rapport à 1)."""
    slots = workers() * 2  # 2 phrases par processus : la carte génère pendant que Whisper vérifie l'autre
    if engine == "multilingual":
        return max(1, min(slots, config.get_int("LOCAL_TTS_MTL_PARALLEL") or slots))
    return slots
_start_lock: asyncio.Lock | None = None


class LocalTTSError(Exception):
    pass


def workers() -> int:
    return max(1, min(4, config.get_int("LOCAL_TTS_WORKERS") or 2))


def base_port() -> int:
    try:
        return int((config.get("LOCAL_TTS_URL") or "http://127.0.0.1:8790").rsplit(":", 1)[-1].strip("/"))
    except ValueError:
        return 8790


def ports() -> list[int]:
    return [base_port() + i for i in range(workers())]


def installed() -> bool:
    return VENV_PY.exists() and SERVER.exists()


def lang_code(language: str | None) -> str:
    return LANG_CODES.get(str(language or "english").lower(), str(language or "en")[:2].lower())


def engine_for(vs: dict) -> str:
    """Turbo (rapide) pour l'anglais, Multilingual pour le reste — sauf choix explicite."""
    if (vs.get("local_engine") or "auto") == "multilingual" or lang_code(vs.get("language")) != "en":
        return "multilingual"
    return "turbo"


SAMPLES_DIR = VOICES_DIR / "samples"
ACCENT_LANG = {"FR": "fr", "CA": "fr", "BE": "fr", "CH": "fr", "EN": "en", "US": "en", "UK": "en", "GB": "en",
               "AU": "en", "IE": "en"}
# la même phrase pour toutes les voix d'une langue, pour pouvoir les comparer
SAMPLE_TEXT = {"fr": "You have exactly ten seconds to decide. Behind this door, someone knows your real name.",
               "en": "You have exactly ten seconds to decide. Behind that door, someone knows your real name."}
_sampling = {"running": False, "done": 0, "total": 0}


def catalog() -> dict:
    try:
        return json.loads((VOICES_DIR / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def list_voices() -> list[dict]:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    cat = catalog()
    out = []
    for f in sorted(VOICES_DIR.glob("*.wav")):
        meta = cat.get(f.name, {})
        m = re.search(r"\b(FR|CA|BE|CH|EN|US|UK|GB|AU|IE)\b", f.stem)
        lang = meta.get("lang") or (ACCENT_LANG[m.group(1)] if m else "")
        out.append({"id": f.name, "name": f.stem, "lang": lang, "label": meta.get("label") or f.stem,
                    "accent": meta.get("accent") or (m.group(1) if m else ""), "gender": meta.get("gender", ""),
                    "desc": meta.get("desc", "your voice" if not meta else ""), "default": bool(meta.get("default")),
                    "sample": (SAMPLES_DIR / f"{f.stem}.mp3").exists()})
    return out


def default_voice(language: str | None) -> str | None:
    code = lang_code(language)
    voices = list_voices()
    for v in sorted(voices, key=lambda v: not v["default"]):
        if v["lang"] == code:
            return v["id"]
    return voices[0]["id"] if voices else None


def sampling_status() -> dict:
    return dict(_sampling)


async def make_samples(force: bool = False) -> int:
    """Échantillon de chaque voix (même phrase), généré par Chatterbox : c'est le vrai rendu dans les vidéos."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    todo = [v for v in list_voices() if force or not v["sample"]]
    todo.sort(key=lambda v: v["lang"] != "en")  # un moteur après l'autre (turbo puis multilingual)
    _sampling.update(running=True, done=0, total=len(todo))
    try:
        for v in todo:
            lang = v["lang"] or "en"
            engine = "turbo" if lang == "en" else "multilingual"
            await ensure_server(engine)
            wav = await synth(SAMPLE_TEXT[lang], "English" if lang == "en" else "French", v["id"], engine=engine)
            tmp = SAMPLES_DIR / f"_{v['name']}.wav"
            tmp.write_bytes(wav)
            subprocess.run([config.get("FFMPEG"), "-y", "-v", "error", "-i", str(tmp), "-ac", "1", "-b:a", "128k",
                            str(SAMPLES_DIR / f"{v['name']}.mp3")], check=True)
            tmp.unlink(missing_ok=True)
            _sampling["done"] += 1
            events.log(f"✓ Voice sample: {v['label']} ({_sampling['done']}/{len(todo)})", "ok")
    finally:
        _sampling["running"] = False
    return len(todo)


async def _health(port: int, timeout: float = 2.0) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(f"http://127.0.0.1:{port}/health")
        return r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


async def health() -> dict | None:
    hs = [h for h in await asyncio.gather(*(_health(p) for p in ports())) if h]
    if not hs:
        return None
    return hs[0] | {"workers": len(hs), "loaded": sorted({k for h in hs for k in h.get("loaded", [])}),
                    "vram_gb": round(sum(h.get("vram_gb", 0) for h in hs), 2)}


async def ensure_server(engine: str | None = None) -> dict:
    """Démarre les processus de voix locale s'ils ne tournent pas et charge le modèle demandé."""
    global _free, _start_lock
    if not installed():
        raise LocalTTSError("Local voice not installed (TubeForge/tts-venv environment missing).")
    if _start_lock is None:
        _start_lock = asyncio.Lock()
    async with _start_lock:
        ps = ports()
        per_proc_vram = float(config.get("LOCAL_TTS_VRAM_GB") or 10) / len(ps)
        started = []
        for port in ps:
            if await _health(port):
                continue
            proc = _procs.get(port)
            if proc is None or proc.poll() is not None:
                log_f = open(ROOT / f"server_{port}.log", "a", encoding="utf-8", errors="replace")
                env = dict(os.environ, PYTHONIOENCODING="utf-8", TQDM_DISABLE="1")
                _procs[port] = subprocess.Popen(
                    [str(VENV_PY), str(SERVER), "--port", str(port), "--vram", f"{per_proc_vram:.2f}"],
                    cwd=str(ROOT), stdout=log_f, stderr=subprocess.STDOUT, env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                started.append(port)
        if started:
            events.log(f"Starting local voice: {len(started)} processus Chatterbox on la carte AMD "
                       f"(≤ {per_proc_vram:.1f} Go chacun)…", "step")
        t0 = time.time()
        for port in ps:
            while not await _health(port):
                if _procs.get(port) and _procs[port].poll() is not None:
                    tail = (ROOT / f"server_{port}.log").read_text(encoding="utf-8", errors="replace")[-1500:]
                    raise LocalTTSError(f"Le moteur de voix locale s'est arrêté :\n{tail}")
                if time.time() - t0 > 300:
                    raise LocalTTSError("The local voice engine does not start (see local_tts/server_*.log)")
                await asyncio.sleep(1)
        if _free is None:
            _free = asyncio.Queue()
            for _ in range(2):
                for port in ps:
                    _free.put_nowait(port)
    if engine:
        async with _EngineGate(engine):
            todo = [p for p in ps if engine not in ((await _health(p)) or {}).get("loaded", [])]
            if todo:
                t1 = time.time()
                events.log(f"Loading Chatterbox model {engine} on {len(todo)} processus "
                           "(~20 s, plus long au tout premier lancement)…")

                async def load(port):
                    async with httpx.AsyncClient(timeout=httpx.Timeout(1800, connect=10)) as c:
                        r = await c.post(f"http://127.0.0.1:{port}/load", json={"engine": engine})
                    if r.status_code != 200:
                        raise LocalTTSError(f"Unable to load model: {r.text[:300]}")
                await asyncio.gather(*(load(p) for p in todo))
                events.log(f"✓ Local voice ready ({engine}, {events.fmt_duration(time.time() - t1)})", "ok")
    return await health() or {}


async def synth(text: str, language: str | None, voice: str | None, exaggeration: float = 0.5,
                cfg_weight: float = 0.5, temperature: float = 0.8, seed: int | None = None,
                engine: str = "auto", verify: bool = True, meta: dict | None = None) -> bytes:
    if _free is None:
        await ensure_server()
    body = {"text": text, "language": lang_code(language), "engine": engine, "exaggeration": exaggeration,
            "cfg_weight": cfg_weight, "temperature": temperature, "seed": seed, "verify": verify,
            "voice": str(VOICES_DIR / voice) if voice else None}
    eng = "multilingual" if engine == "multilingual" or lang_code(language) != "en" else "turbo"
    if eng not in _eng_sems:
        _eng_sems[eng] = asyncio.Semaphore(parallel_for(eng))
    async with _EngineGate(eng), _eng_sems[eng]:  # la porte englobe la file d'attente du moteur
        return await _synth_on_worker(body, meta)


async def _synth_on_worker(body: dict, meta: dict | None) -> bytes:
    last = None
    for attempt in range(3):
        port = await _free.get()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10)) as c:
                r = await c.post(f"http://127.0.0.1:{port}/tts", json=body)
            if r.status_code == 200:
                if meta is not None:
                    meta.update(wer=float(r.headers.get("X-WER", -1)), attempts=int(r.headers.get("X-Attempts", 1)))
                return r.content
            last = r.text[:400]
        except httpx.TransportError as e:
            last = str(e)
        finally:
            _free.put_nowait(port)
        if attempt < 2:
            events.log(f"⚠ Local voice: retrying ({(last or '')[:120]})", "warn")
            await ensure_server()
            await asyncio.sleep(2)
    raise LocalTTSError(f"Local voice: failed — {last}")


# ------------------------------------------------------------------ texte prononçable

_CUR = {"en": {"$": "dollars", "€": "euros", "£": "pounds"}, "fr": {"$": "dollars", "€": "euros", "£": "livres"}}
_PCT = {"en": "percent", "fr": "percent", "es": "por ciento", "de": "Prozent", "it": "per cento", "pt": "por cento"}


def speakable(text: str, language: str | None) -> str:
    """Écrit les nombres en toutes lettres (les modèles locaux prononcent mal les chiffres).

    Le texte affiché (sous-titres, scènes) reste inchangé : seul ce qui est lu change."""
    code = lang_code(language)
    if code not in ("en", "fr", "es", "de", "it", "pt") or not re.search(r"\d", text):
        return text
    from num2words import num2words

    def n2w(n, **kw):
        try:
            return num2words(n, lang=code, **kw)
        except (NotImplementedError, OverflowError, ValueError):
            return str(n)

    cur = _CUR.get(code, _CUR["en"])
    # monnaies : $300 / 300 € / €300
    text = re.sub(r"([$€£])\s?(\d[\d,. ]*\d|\d)", lambda m: f"{m.group(2)} {cur[m.group(1)]}", text)
    text = re.sub(r"(\d)\s?([$€£])", lambda m: f"{m.group(1)} {cur[m.group(2)]}", text)
    text = re.sub(r"(\d)\s?%", lambda m: f"{m.group(1)} {_PCT.get(code, 'percent')}", text)
    # ordinaux : 8th, 21st / 1er, 3e, 3ème
    if code == "en":
        text = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: n2w(int(m.group(1)), to="ordinal"), text)
    elif code == "fr":
        text = re.sub("\\b(\\d+)(er|re|e|ème|eme)\\b",
                      lambda m: "premier" if m.group(1) == "1" and m.group(2) == "er" else n2w(int(m.group(1)), to="ordinal"),
                      text)
    # années (1000-2099), sauf si suivies d'une unité monétaire déjà traitée
    text = re.sub(r"\b(1\d{3}|20\d{2})\b(?!\s?(?:dollars|euros|pounds|livres))",
                  lambda m: n2w(int(m.group(1)), to="year") if code == "en" else n2w(int(m.group(1))), text)
    # milliers séparés (3,000 / 3 000 / 3.000) et décimales
    sep_th = "," if code == "en" else r"[  .]"
    text = re.sub(rf"\b\d{{1,3}}(?:{sep_th}\d{{3}})+\b", lambda m: n2w(int(re.sub(r"\D", "", m.group(0)))), text)
    dec = r"\." if code == "en" else ","
    text = re.sub(rf"\b(\d+){dec}(\d+)\b", lambda m: n2w(float(f"{m.group(1)}.{m.group(2)}")), text)
    text = re.sub(r"\b\d+\b", lambda m: n2w(int(m.group(0))), text)
    return text


# ------------------------------------------------------------------ découpage + timings

def split_for_local(text: str, max_chars: int = 240) -> list[tuple[int, str, float]]:
    """Groupes de phrases (offset, texte, pause après en secondes)."""
    out: list[tuple[int, str, float]] = []
    for para in re.finditer(r"[^\n]+", text):
        p_off, ptxt = para.start(), para.group()
        sents = [(m.start() + p_off, m.group()) for m in re.finditer(r"[^.!?…]+(?:[.!?…]+[\"'”’»)]*|$)\s*", ptxt)
                 if m.group().strip()]
        pieces: list[tuple[int, str]] = []
        for off, s in sents:
            if len(s) <= max_chars:
                pieces.append((off, s))
                continue
            cur_off, cur = off, ""
            for m in re.finditer(r"[^,;:—]+[,;:—]?\s*", s):  # phrase trop longue : coupe aux virgules
                if cur and len(cur) + len(m.group()) > max_chars:
                    pieces.append((cur_off, cur))
                    cur_off, cur = off + m.start(), ""
                cur += m.group()
            if cur:
                pieces.append((cur_off, cur))
        group_off, group = None, ""
        start = len(out)
        for off, s in pieces:
            if group and len(group) + len(s) > max_chars:
                out.append((group_off, group.rstrip(), 0.0))
                group_off, group = None, ""
            if group_off is None:
                group_off = off
            group += s
        if group:
            out.append((group_off, group.rstrip(), 0.0))
        if len(out) > start:  # pause plus longue en fin de paragraphe
            o, t, _ = out[-1]
            out[-1] = (o, t, -1.0)
    final = []
    for o, t, pause in out:
        if pause < 0:
            pause = 0.65
        elif re.search(r"[.!?…][\"'”’»)]*$", t):
            pause = 0.32
        else:
            pause = 0.14
        final.append((o, t, pause))
    return final


def spread_words(chunk: str, offset: int, duration: float) -> list[dict]:
    """Répartit les mots du groupe sur sa durée (poids = longueur + pauses de ponctuation)."""
    toks = list(re.finditer(r"\S+", chunk))
    if not toks:
        return []
    weights = []
    for m in toks:
        w = len(m.group()) + 1.5
        if re.search(r"[.!?…][\"'”’»)]*$", m.group()):
            w += 6
        elif re.search(r"[,;:—]$", m.group()):
            w += 3
        weights.append(w)
    total = sum(weights)
    t, words = 0.0, []
    for m, w in zip(toks, weights):
        d = duration * w / total
        words.append({"w": m.group(), "s": round(t, 3), "e": round(t + d * 0.85, 3),
                      "c0": offset + m.start(), "c1": offset + m.end()})
        t += d
    return words


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.getnframes() / w.getframerate()


def pad_wav(data: bytes, pause: float) -> tuple[bytes, float, float]:
    """Ajoute un silence en fin de groupe. Retourne (wav, durée parole, durée totale)."""
    with wave.open(io.BytesIO(data), "rb") as w:
        params, frames = w.getparams(), w.readframes(w.getnframes())
    speech = len(frames) / (params.sampwidth * params.nchannels) / params.framerate
    frames += b"\x00" * (int(pause * params.framerate) * params.sampwidth * params.nchannels)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(frames)
    return buf.getvalue(), speech, speech + pause


def voice_fingerprint(voice: str | None) -> str:
    if not voice:
        return "default"
    f = VOICES_DIR / voice
    st = f.stat() if f.exists() else None
    return f"{voice}:{st.st_size if st else 0}:{int(st.st_mtime) if st else 0}"


async def chunk_audio(offset: int, chunk: str, pause: float, vs: dict, cache: Path) -> dict:
    lang = vs.get("language", "English")
    voice = vs.get("local_voice") or default_voice(lang)
    engine = engine_for(vs)
    params = {"exaggeration": float(vs.get("local_exaggeration", 0.5)), "cfg_weight": float(vs.get("local_cfg", 0.5)),
              "temperature": float(vs.get("local_temperature", 0.8))}
    key = "local_" + hashlib.sha1(json.dumps([voice_fingerprint(voice), params, engine, lang_code(lang),
                                              chunk, pause], ensure_ascii=False).encode()).hexdigest()[:20]
    wav_path, js = cache / f"{key}.wav", cache / f"{key}.json"
    if wav_path.exists() and js.exists():
        meta = json.loads(js.read_text(encoding="utf-8"))
    else:
        # contrôle qualité : une durée très éloignée de l'attendu = phrase ratée (coupée, répétée…)
        said = speakable(chunk, lang)
        expected = len(said) / CHARS_PER_SEC.get(lang_code(lang), 14.5)
        best, best_gap = None, None
        verify = bool(vs.get("local_verify", True))
        for attempt in range(3):
            info: dict = {}
            raw = await synth(said, lang, voice, engine=engine, seed=None if attempt == 0 else 1000 + attempt,
                              verify=verify, meta=info, **params)
            if info.get("attempts", 1) > 1:
                events.log(f"↻ Phrase regenerated {info['attempts'] - 1}× (Whisper check): “ {chunk[:50]}… »", "warn")
            secs = wav_seconds(raw)
            ratio = secs / max(expected, 0.5)
            gap = abs(1 - ratio)
            if best is None or gap < best_gap:
                best, best_gap = raw, gap
            if 0.45 <= ratio <= 2.2:
                break
            events.log(f"⚠ Phrase to redo (duration {secs:.1f} s au lieu de ~{expected:.1f} s) : « {chunk[:50]}… »",
                       "warn")
        padded, speech, total = pad_wav(best, pause)
        wav_path.write_bytes(padded)
        meta = {"speech": speech, "total": total, "engine": engine}
        js.write_text(json.dumps(meta), encoding="utf-8")
    return {"path": wav_path, "words": spread_words(chunk, offset, meta["speech"])}
