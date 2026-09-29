"""Voix off multi-fournisseurs, avec timings au MOT (pour caler images + sous-titres).

  edge        Voix neuronales Microsoft (gratuit, sans clé) — timings natifs (WordBoundary)
  elevenlabs  ELEVENLABS_API_KEY — endpoint /with-timestamps (alignement caractère)
  openai      OPENAI_TTS_KEY (+ OPENAI_TTS_BASE optionnel) — pas de timings :
              estimation proportionnelle aux caractères, phrase par phrase
  algrow      ALGROW_API_KEY — voix ElevenLabs via Algrow (job asynchrone) ; timings mot à mot
              tirés du SRT d'alignement (generate_srt, +20 % de caractères)
  algrow_stealth  ALGROW_API_KEY — modèle « Stealth » d'Algrow (autre réserve de caractères) ;
              timings estimés puis recalés sur les silences de la voix

synthesize() renvoie {"path", "duration", "words": [{"w","s","e"}]}.
"""
import asyncio
import base64
import json
import os
import re
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from services import media


class TTSError(Exception):
    pass


PROVIDERS = ("edge", "elevenlabs", "openai", "algrow", "algrow_stealth")

# Voix mises en avant dans l'UI (la liste complète Edge est chargée à la demande).
EDGE_FEATURED = {
    "fr": ["fr-FR-HenriNeural", "fr-FR-RemyMultilingualNeural", "fr-FR-DeniseNeural",
           "fr-FR-VivienneMultilingualNeural", "fr-FR-EloiseNeural", "fr-CA-ThierryNeural",
           "fr-CA-AntoineNeural", "fr-CH-FabriceNeural", "fr-BE-GerardNeural"],
    "en": ["en-US-AndrewMultilingualNeural", "en-US-BrianMultilingualNeural", "en-US-ChristopherNeural",
           "en-US-GuyNeural", "en-US-EricNeural", "en-US-AvaMultilingualNeural",
           "en-US-EmmaMultilingualNeural", "en-GB-RyanNeural", "en-GB-ThomasNeural", "en-GB-SoniaNeural"],
}
OPENAI_VOICES = ["onyx", "ash", "echo", "ballad", "sage", "verse", "alloy", "coral", "nova", "shimmer", "fable"]


def provider_status():
    return {
        "edge": _edge_installed(),
        "elevenlabs": bool(_env("ELEVENLABS_API_KEY")),
        "openai": bool(_env("OPENAI_TTS_KEY")),
        "algrow": bool(_env("ALGROW_API_KEY")),
        "algrow_stealth": bool(_env("ALGROW_API_KEY")),
    }


def _env(name, default=""):
    return (os.getenv(name) or default).strip()


def _edge_installed():
    import importlib.util
    return importlib.util.find_spec("edge_tts") is not None


# ── Découpage du texte ──────────────────────────────────────────────────────

_SENT_RE = re.compile(r"(?<=[.!?…])\s+")


def split_sentences(text):
    return [s.strip() for s in _SENT_RE.split((text or "").strip()) if s.strip()]


def chunk_text(text, max_chars):
    """Paquets de phrases entières ≤ max_chars (coupe dure en dernier recours)."""
    chunks, cur = [], ""
    for s in split_sentences(text):
        if cur and len(cur) + len(s) + 1 > max_chars:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    out = []
    for c in chunks:
        while len(c) > max_chars:
            cut = c.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            out.append(c[:cut].strip())
            c = c[cut:].strip()
        if c:
            out.append(c)
    return out or [(text or "").strip()]


# ── Edge TTS ────────────────────────────────────────────────────────────────

def _edge_ssl_fix():
    """Respecte SSL_CERT_FILE (proxys d'entreprise) : edge-tts force certifi sinon."""
    cafile = _env("SSL_CERT_FILE")
    if cafile and os.path.isfile(cafile):
        try:
            import edge_tts.communicate as c
            c._SSL_CTX = ssl.create_default_context(cafile=cafile)
        except Exception:
            pass


def _pct(v, unit="%"):
    v = int(round(float(v or 0)))
    return f"{'+' if v >= 0 else ''}{v}{unit}"


def _edge(text, voice, dest, speed=1.0, pitch=0):
    import edge_tts
    _edge_ssl_fix()
    rate = _pct((float(speed or 1.0) - 1.0) * 100)

    async def go():
        com = edge_tts.Communicate(text, voice or "fr-FR-HenriNeural", rate=rate,
                                   pitch=_pct(pitch, "Hz"), boundary="WordBoundary")
        words = []
        with open(dest, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7
                    words.append({"w": ch["text"], "s": round(s, 3),
                                  "e": round(s + ch["duration"] / 1e7, 3)})
        return words

    last = None
    for _ in range(3):
        try:
            return asyncio.run(go())
        except Exception as e:  # coupure websocket → on retente
            last = e
    raise TTSError(f"Edge TTS a échoué: {last}")


def edge_voices(lang=None):
    import edge_tts
    _edge_ssl_fix()
    voices = asyncio.run(edge_tts.list_voices())
    out = []
    for v in voices:
        if lang and not v["Locale"].lower().startswith(lang.lower()):
            continue
        out.append({"id": v["ShortName"], "locale": v["Locale"], "gender": v.get("Gender", ""),
                    "name": v["ShortName"].split("-", 2)[-1].replace("Neural", "")})
    return out


# ── ElevenLabs ──────────────────────────────────────────────────────────────

def _eleven(text, voice, dest_mp3, model="eleven_multilingual_v2", speed=1.0, stability=0.5,
            similarity=0.75, style=0.3):
    key = _env("ELEVENLABS_API_KEY")
    if not key:
        raise TTSError("ELEVENLABS_API_KEY manquante dans le .env.")
    body = {"text": text, "model_id": model or "eleven_multilingual_v2",
            "voice_settings": {"stability": stability, "similarity_boost": similarity,
                               "style": style, "use_speaker_boost": True,
                               "speed": max(0.7, min(1.2, float(speed or 1.0)))}}
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{voice or 'pNInz6obpgDQGcFmaJgB'}"
           "/with-timestamps?output_format=mp3_44100_128")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise TTSError(f"ElevenLabs {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    with open(dest_mp3, "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or {}
    return _chars_to_words(al.get("characters") or [], al.get("character_start_times_seconds") or [],
                           al.get("character_end_times_seconds") or [])


def _chars_to_words(chars, starts, ends):
    words, cur, cs, ce = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "s": round(cs, 3), "e": round(ce, 3)})
            cur, cs = "", None
            continue
        if cs is None:
            cs = s
        cur += ch
        ce = e
    if cur:
        words.append({"w": cur, "s": round(cs, 3), "e": round(ce, 3)})
    return words


# ── OpenAI TTS (clé API OpenAI classique) ───────────────────────────────────

def _openai(text, voice, dest, speed=1.0, instructions=""):
    key = _env("OPENAI_TTS_KEY")
    if not key:
        raise TTSError("OPENAI_TTS_KEY manquante dans le .env.")
    base = _env("OPENAI_TTS_BASE", "https://api.openai.com/v1").rstrip("/")
    body = {"model": _env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"), "voice": voice or "onyx",
            "input": text, "response_format": "mp3", "speed": float(speed or 1.0)}
    if instructions:
        body["instructions"] = instructions
    req = urllib.request.Request(base + "/audio/speech", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            f.write(r.read())
    except urllib.error.HTTPError as e:
        raise TTSError(f"OpenAI TTS {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    return None  # pas de timings → estimés après coup


# ── Algrow (ElevenLabs / Stealth, jobs asynchrones) ────────────────────────

ALGROW_BASE = "https://api.algrow.online"


def _algrow_call(method, path, fields=None, timeout=60):
    key = _env("ALGROW_API_KEY")
    if not key:
        raise TTSError("ALGROW_API_KEY absente du .env.")
    data, headers = None, {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if fields is not None:
        import uuid
        boundary = "----drylow" + uuid.uuid4().hex
        parts = []
        for k, v in fields.items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
        parts.append(f"--{boundary}--\r\n")
        data = "".join(parts).encode("utf-8")
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    req = urllib.request.Request((_env("ALGROW_BASE") or ALGROW_BASE) + path, data=data, method=method,
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise TTSError(f"Algrow {e.code} : {detail}")
    except urllib.error.URLError as e:
        raise TTSError(f"Algrow injoignable : {e}")


def _download(url, dest, timeout=180):
    with urllib.request.urlopen(url, timeout=timeout) as r, open(dest, "wb") as f:
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            f.write(b)
    return dest


def _srt_words(srt_text):
    """SRT → mots avec timings (répartis dans chaque bloc au prorata des caractères)."""
    def ts(x):
        h, m, rest = x.strip().split(":")
        sec, ms = rest.replace(".", ",").split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000.0
    words = []
    for block in re.split(r"\n\s*\n", (srt_text or "").replace("\r", "")):
        lines = [x for x in block.strip().split("\n") if x.strip()]
        arrow = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if arrow is None:
            continue
        a, b = lines[arrow].split("-->")
        try:
            s0, s1 = ts(a), ts(b.split()[0])
        except (ValueError, IndexError):
            continue
        toks = " ".join(lines[arrow + 1:]).split()
        if not toks:
            continue
        total = float(sum(len(t) + 1 for t in toks))
        t = s0
        for tok in toks:
            d = (s1 - s0) * (len(tok) + 1) / total
            words.append({"w": tok, "s": round(t, 3), "e": round(t + d, 3)})
            t += d
    return words


def _algrow(text, voice, dest, sub="elevenlabs", model="", speed=1.0, progress=None, srt=True, max_wait=1800):
    """Job Algrow : envoi → attente (polling) → MP3 + timings (SRT si ElevenLabs)."""
    import time
    if not voice:
        raise TTSError("Choisis une voix Algrow (ID de voix).")
    fields = {"script": text, "voice_id": voice, "provider": sub, "custom_title": "voiceover"}
    if sub == "stealth":
        fields.update({"speaking_rate": f"{max(0.5, min(2.0, float(speed or 1))):.2f}", "temperature": "1.1",
                       "stealth_model": model or "1.5"})
    else:
        fields.update({"model_id": model or "eleven_multilingual_v2", "stability": "0.5",
                       "similarity_boost": "0.75", "style": "0.0",
                       "speed": f"{max(0.7, min(1.2, float(speed or 1))):.2f}",
                       "generate_srt": "true" if srt else "false"})
    job = _algrow_call("POST", "/api/generate-simple", fields)
    jid = job.get("job_id")
    if not jid:
        raise TTSError("Algrow : pas de job_id (" + json.dumps(job)[:200] + ")")
    t0 = time.time()
    while True:
        time.sleep(3)
        st = _algrow_call("GET", f"/api/job-status/{jid}")
        status = st.get("status")
        if status == "completed" and st.get("audio_url"):
            break
        if status == "failed":
            raise TTSError("Algrow : " + (st.get("error_message") or st.get("error") or "échec de la génération"))
        if time.time() - t0 > max_wait:
            raise TTSError("Algrow : la génération prend trop de temps (job " + str(jid) + ").")
        if progress:
            progress(min(0.9, (time.time() - t0) / 120.0))
    _download(st["audio_url"], dest)
    if st.get("transcript_url"):
        try:
            with urllib.request.urlopen(st["transcript_url"], timeout=60) as r:
                return _srt_words(r.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 — sans SRT on estime puis on recale sur les silences
            return None
    return None


def algrow_voices(search="", lang="", stealth=False):
    if stealth:
        data = _algrow_call("GET", "/api/voices/stealth")
        return [{"id": v.get("voice_id"), "name": v.get("name") or v.get("voice_id"), "gender": v.get("gender", ""),
                 "preview_url": v.get("preview_url")} for v in data.get("voices") or []]
    q = urllib.parse.urlencode({k: v for k, v in {"search": search, "language": lang, "page_size": 60,
                                                  "sort": "trending"}.items() if v})
    data = _algrow_call("GET", "/api/voices?" + q)
    return [{"id": v.get("voice_id"), "name": v.get("name"), "gender": v.get("gender", ""),
             "accent": v.get("accent", ""), "preview_url": v.get("preview_url"),
             "description": v.get("description", "")} for v in data.get("voices") or []]


def algrow_credits():
    return _algrow_call("GET", "/api/credits")


# ── Recalage sur les silences (voix sans timings natifs) ────────────────────

def _silences(path, noise="-34dB", min_d=0.14):
    import subprocess
    p = subprocess.run([media.ffmpeg_bin(), "-hide_banner", "-nostdin", "-i", path, "-af",
                        f"silencedetect=noise={noise}:d={min_d}", "-f", "null", "-"],
                       capture_output=True, creationflags=media._NO_WINDOW)
    err = p.stderr.decode("utf-8", "replace")
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return [(max(0.0, a), b) for a, b in zip(starts, ends)]


def snap_to_silences(words, path):
    """Timings estimés → fins de phrase recalées sur les vraies pauses de la voix.

    Les images changent en fin de phrase : ce recalage suffit à les caler pile sur la voix."""
    if not words:
        return words
    sil = _silences(path)
    if not sil:
        return words
    anchors, last_t, used = [], 0.0, set()
    for k, w in enumerate(words):
        if w["w"][-1:] not in ".!?…" or k == len(words) - 1:
            continue
        best = None
        for j, (a, b) in enumerate(sil):
            if j in used or a <= last_t:
                continue
            d = abs(a - w["e"])
            if d <= 2.5 and (best is None or d < best[0]):
                best = (d, j)
        if best:
            a, b = sil[best[1]]
            used.add(best[1])
            anchors.append((k, a, b))
            last_t = b
    if not anchors:
        return words
    out = [dict(w) for w in words]
    seg_start_i, seg_start_t = 0, max(0.0, sil[0][1] if sil[0][0] <= 0.05 else 0.0)
    for k, a, b in anchors + [(len(words) - 1, words[-1]["e"], None)]:
        seg = out[seg_start_i:k + 1]
        span = max(0.05, a - seg_start_t)
        weights = [len(x["w"]) + 1 for x in seg]
        tot = float(sum(weights))
        t = seg_start_t
        for x, wt in zip(seg, weights):
            d = span * wt / tot
            x["s"], x["e"] = round(t, 3), round(t + d * 0.92, 3)
            t += d
        seg_start_i, seg_start_t = k + 1, (b if b is not None else a)
    return out


def _norm(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


def align_to_text(words, text):
    """Remplace les mots TTS par les mots du texte d'origine (ponctuation incluse).

    Edge renvoie les mots sans ponctuation ; on les ré-aligne sur les tokens du
    script (flux de caractères normalisés) pour que les sous-titres gardent
    virgules/points et que la coupe des lignes tombe au bon endroit. Un mot TTS
    peut couvrir plusieurs tokens (« 10 000 ») et inversement (« jusqu'au »)."""
    tokens = (text or "").split()
    if not words or not tokens:
        return words
    stream, owner = [], []
    for ti, tok in enumerate(tokens):
        for ch in _norm(tok):
            stream.append(ch)
            owner.append(ti)
    flat = "".join(stream)
    pos, out, last_t = 0, [], -1
    for w in words:
        n = _norm(w["w"])
        if not n:
            continue
        idx = flat.find(n, pos, pos + len(n) + 60)
        if idx == -1:  # décrochage : on cherche plus loin pour se resynchroniser
            idx = flat.find(n, pos, pos + len(n) + 600)
        if idx == -1:
            out.append({"w": w["w"], "s": w["s"], "e": w["e"], "_t": max(last_t, 0), "_x": 1})
            continue
        first, ti = owner[idx], owner[idx + len(n) - 1]
        pos = idx + len(n)
        if out and out[-1].get("_t") == ti and not out[-1].get("_x"):  # même token découpé
            out[-1]["e"] = w["e"]
            continue
        first = max(first, last_t + 1)
        out.append({"w": " ".join(tokens[first:ti + 1]) if first <= ti else tokens[ti],
                    "s": w["s"], "e": w["e"], "_t": ti})
        last_t = ti
    for w in out:
        w["t"] = w.pop("_t", 0)  # index du token dans le texte (sert à retrouver les sections)
        w.pop("_x", None)
    return out


def estimate_words(text, total):
    """Timings approximatifs : répartis au prorata des caractères (+ pauses de ponctuation)."""
    tokens = (text or "").split()
    if not tokens or total <= 0:
        return []
    weights = []
    for t in tokens:
        w = len(t) + 1
        if t[-1:] in ".!?…":
            w += 6
        elif t[-1:] in ",;:":
            w += 3
        weights.append(w)
    unit = total / float(sum(weights))
    words, t0 = [], 0.0
    for ti, (tok, w) in enumerate(zip(tokens, weights)):
        dur = w * unit
        speak = dur - (6 * unit if tok[-1:] in ".!?…" else 3 * unit if tok[-1:] in ",;:" else 0)
        words.append({"w": tok, "s": round(t0, 3), "e": round(t0 + max(0.05, speak), 3), "t": ti})
        t0 += dur
    return words


# ── Point d'entrée ──────────────────────────────────────────────────────────

_MAX_CHARS = {"edge": 3000, "elevenlabs": 4500, "openai": 3800, "algrow": 90000, "algrow_stealth": 40000}


def synthesize(text, dest, *, provider="edge", voice="", speed=1.0, pitch=0, model="",
               instructions="", progress=None):
    """Synthétise tout le texte vers `dest` (mp3) et renvoie durée + timings mot à mot."""
    provider = provider if provider in PROVIDERS else "edge"
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        raise TTSError("Texte vide.")
    chunks = chunk_text(text, _MAX_CHARS[provider])
    tmpdir = tempfile.mkdtemp(prefix="tts_", dir=os.path.dirname(dest) or None)
    parts, all_words, offset, tok_offset = [], [], 0.0, 0
    try:
        for i, chunk in enumerate(chunks):
            if progress:
                progress(i, len(chunks))
            part = os.path.join(tmpdir, f"part_{i:03d}.mp3")
            if provider == "edge":
                words = _edge(chunk, voice, part, speed=speed, pitch=pitch)
            elif provider == "elevenlabs":
                words = _eleven(chunk, voice, part, model=model or "eleven_multilingual_v2", speed=speed)
            elif provider in ("algrow", "algrow_stealth"):
                words = _algrow(chunk, voice, part, sub="stealth" if provider == "algrow_stealth" else "elevenlabs",
                                model=model, speed=speed)
            else:
                words = _openai(chunk, voice, part, speed=speed, instructions=instructions)
            dur = media.duration(part)
            if words:
                words = align_to_text(words, chunk)
            else:
                words = estimate_words(chunk, dur)
                if provider.startswith("algrow"):  # pas de timings natifs : recalage sur les pauses
                    words = snap_to_silences(words, part)
            for w in words:
                all_words.append({"w": w["w"], "s": round(w["s"] + offset, 3), "e": round(w["e"] + offset, 3),
                                  "t": int(w.get("t", 0)) + tok_offset})
            parts.append(part)
            offset += dur
            tok_offset += len(chunk.split())
        media.concat_audio(parts, dest)
        total = media.duration(dest)
        if progress:
            progress(len(chunks), len(chunks))
        return {"path": dest, "duration": round(total, 3), "words": all_words}
    finally:
        for p in parts:
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
