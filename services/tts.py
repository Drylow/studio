"""Voix off multi-fournisseurs, avec timings au MOT (pour caler images + sous-titres).

  edge        Voix neuronales Microsoft (gratuit, sans clé) — timings natifs (WordBoundary)
  elevenlabs  ELEVENLABS_API_KEY — endpoint /with-timestamps (alignement caractère)
  openai      OPENAI_TTS_KEY (+ OPENAI_TTS_BASE optionnel) — pas de timings :
              estimation proportionnelle aux caractères, phrase par phrase

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
import urllib.request

from services import media


class TTSError(Exception):
    pass


PROVIDERS = ("edge", "elevenlabs", "openai")

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
    }


def _env(name, default=""):
    return (os.getenv(name) or default).strip()


def _edge_installed():
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


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


def _norm(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


def align_to_text(words, text):
    """Remplace les mots TTS par les mots du texte d'origine (ponctuation incluse).

    Edge renvoie les mots sans ponctuation ; on les ré-aligne sur les tokens du
    script (flux de caractères normalisés) pour que les sous-titres gardent
    virgules/points et que la coupe des lignes tombe au bon endroit."""
    tokens = (text or "").split()
    if not words or not tokens:
        return words
    stream, owner = [], []
    for ti, tok in enumerate(tokens):
        for ch in _norm(tok):
            stream.append(ch)
            owner.append(ti)
    flat = "".join(stream)
    pos, out = 0, []
    for w in words:
        n = _norm(w["w"])
        if not n:
            continue
        idx = flat.find(n, pos, pos + len(n) + 40)
        if idx == -1:
            out.append({"w": w["w"], "s": w["s"], "e": w["e"], "_t": out[-1]["_t"] if out else 0, "_x": 1})
            continue
        ti = owner[idx + len(n) - 1]
        pos = idx + len(n)
        if out and out[-1].get("_t") == ti and not out[-1].get("_x"):  # même token découpé
            out[-1]["e"] = w["e"]
            continue
        out.append({"w": tokens[ti], "s": w["s"], "e": w["e"], "_t": ti})
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

_MAX_CHARS = {"edge": 3000, "elevenlabs": 4500, "openai": 3800}


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
            else:
                words = _openai(chunk, voice, part, speed=speed, instructions=instructions)
            dur = media.duration(part)
            words = align_to_text(words, chunk) if words else estimate_words(chunk, dur)
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
