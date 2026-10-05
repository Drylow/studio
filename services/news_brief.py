"""Short sports analysis: reviewed narration, visible sources and original news cards.

This format does not download interviews. Its inputs are a manually reviewed
brief.json and public source images; narration and render caches stay in work/.
"""
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from services import media, newsvid, render, tts
from services.news_rights import image_rights

REPO = Path(__file__).resolve().parents[1]
FONTS = REPO / "static" / "fonts"


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate(plan):
    newsvid.channel(plan["channel"])
    sources = {s["id"]: s for s in plan["sources"]}
    if len(sources) != len(plan["sources"]) or not sources:
        raise ValueError("Sources manquantes ou identifiants en double.")
    for source in sources.values():
        if not source.get("name") or not source.get("url", "").startswith("https://"):
            raise ValueError("Chaque source doit avoir un nom et une adresse HTTPS.")
    segments = plan["segments"]
    if not segments or not plan.get("title") or not plan.get("reviewed_at"):
        raise ValueError("Le titre, les segments et la date de relecture sont obligatoires.")
    for seg in segments:
        if not seg.get("narration") or not seg.get("headline") or not seg.get("lines"):
            raise ValueError("Segment incomplet.")
        refs = seg.get("source_ids") or []
        if not refs or any(ref not in sources for ref in refs):
            raise ValueError("Chaque segment doit citer des sources connues.")
        visual = seg.get("visual") or {}
        if visual and (not visual.get("url", "").startswith("https://") or not visual.get("credit")):
            raise ValueError("Une image nécessite une URL HTTPS et un crédit.")
        image_rights(visual)
    text = "\n\n".join(s["narration"].strip() for s in segments)
    if not 550 <= len(text.split()) <= 900:
        raise ValueError("Une analyse de 4–6 minutes doit avoir entre 550 et 900 mots.")
    return text


def voice(plan, work, log=print):
    text = validate(plan)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    channel = newsvid.channel(plan["channel"])
    signature = hashlib.sha256(json.dumps([text, channel["voice_provider"], channel["voice"],
                                          1.0], ensure_ascii=False).encode()).hexdigest()
    audio, timings = work / "voice.mp3", work / "voice.json"
    if audio.is_file() and timings.is_file():
        cached = json.loads(timings.read_text(encoding="utf-8"))
        if cached.get("signature") == signature:
            log("Voix en cache.")
            return align_voice(text, work, cached, log)
    log(f"Voix : {len(text.split())} mots, {channel['brand']}.")
    result = tts.synthesize(text, str(audio), provider=channel["voice_provider"],
                            voice=channel["voice"], lang="en",
                            progress=lambda i, total: log(f"Voix : partie {i}/{total}"))
    result["signature"] = signature
    save_json(timings, result)
    return align_voice(text, work, result, log)


def align_voice(text, work, result, log):
    """Keep script spelling while timing captions against the actual recorded voice."""
    from services import align
    if result.get("alignment") == "audio_checked" or not align.available():
        return result
    import difflib
    import numpy as np
    from faster_whisper import WhisperModel
    log("Recalage des sous-titres sur la voix enregistrée…")
    # Decode with the existing FFmpeg, avoiding PyAV API differences between
    # machines. Whisper accepts a mono 16 kHz float array directly.
    pcm = media.run(["-i", str(work / "voice.mp3"), "-f", "f32le", "-ar", "16000",
                     "-ac", "1", "pipe:1"]).stdout
    model = WhisperModel(align._model_dir("en"), device="cpu", compute_type="int8", cpu_threads=2)
    segments, _ = model.transcribe(np.frombuffer(pcm, dtype=np.float32), language="en",
                                    word_timestamps=True, beam_size=1)
    words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
             for seg in segments for w in seg.words]
    normalize = lambda word: re.sub(r"[^a-z0-9]", "", word.lower())
    match = difflib.SequenceMatcher(None, [normalize(w) for w in text.split()],
                                    [normalize(w["w"]) for w in words], autojunk=False)
    if sum(b.size for b in match.get_matching_blocks()) / len(text.split()) < 0.85:
        raise ValueError("La transcription audio ne correspond pas assez au script : vérifier la voix.")
    result["words"] = tts.align_to_text(words, text)
    result["alignment"] = "audio_checked"
    save_json(work / "voice.json", result)
    return result


def _wrapped(draw, text, font, width):
    rows, row = [], ""
    for word in text.split():
        candidate = (row + " " + word).strip()
        if draw.textlength(candidate, font=font) > width and row:
            rows.append(row)
            row = word
        else:
            row = candidate
    if row:
        rows.append(row)
    return rows


def card(plan, seg, index, dest, image_path=None):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    ch = newsvid.channel(plan["channel"])
    im = Image.new("RGB", (1920, 1080), "#08121D")
    d = ImageDraw.Draw(im)
    font = lambda size: ImageFont.truetype(str(FONTS / "Poppins-700.ttf"), size)
    accent = ch["accent2"]
    d.rectangle((0, 0, 1920, 12), fill=ch["accent"])
    d.text((94, 58), ch["brand"], font=font(40), fill=accent)
    d.text((1510, 66), plan["date"], font=font(26), fill="#9AABB9")
    d.line((94, 148, 1826, 148), fill="#243A4C", width=2)
    d.text((94, 183), f"ANALYSIS  /  {index + 1:02d}", font=font(24), fill=accent)
    width = 870 if image_path else 1600
    heading_font = font(60)
    headings = _wrapped(d, seg["headline"], heading_font, width)
    if len(headings) > 3:
        raise ValueError("Titre trop long pour la carte.")
    y = 245
    for line in headings:
        d.text((94, y), line, font=heading_font, fill="white")
        y += 80
    y += 45
    for line in seg["lines"]:
        rows = _wrapped(d, line, font(34), width - 55)
        d.rounded_rectangle((94, y + 15, 105, y + 26), radius=3, fill=accent)
        for row in rows:
            if y > 790:
                raise ValueError("Texte trop long pour la carte.")
            d.text((131, y), row, font=font(34), fill="#CFDBE5")
            y += 53
        y += 18
    if image_path:
        with Image.open(image_path) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            photo = ImageOps.contain(source, (750, 585))
        px, py = 1076 + (750 - photo.width) // 2, 243 + (585 - photo.height) // 2
        im.paste(photo, (px, py))
        d.rounded_rectangle((1064, 231, 1838, 840), radius=12, outline=ch["accent"], width=3)
    names = {s["id"]: s["name"] for s in plan["sources"]}
    credit = "Sources: " + " / ".join(names[s] for s in seg["source_ids"])
    if image_path:
        credit += "  |  " + seg["visual"]["credit"]
    d.text((94, 873), credit, font=font(21), fill="#93A9BB")
    d.rectangle((0, 928, 1920, 1080), fill="#030911")
    im.save(dest)
    return str(dest)


def build(job, work_root, log=print):
    from services import music
    from services.newsvid_render import check_sheets, TENSE
    job, work_root = Path(job), Path(work_root)
    plan = json.loads((job / "brief.json").read_text(encoding="utf-8"))
    text = validate(plan)
    work = work_root / "news_brief" / job.name
    audio = voice(plan, work, log)
    if not 235 <= audio["duration"] <= 365:
        raise ValueError(f"Voix hors du format 4–6 min : {audio['duration']:.1f} s.")
    pictures = work / "cards"
    pictures.mkdir(exist_ok=True)
    scenes, token = [], 0
    for i, seg in enumerate(plan["segments"]):
        photo = None
        if seg.get("visual"):
            url = seg["visual"]["url"]
            photo = work / ("source-" + hashlib.sha256(url.encode()).hexdigest()[:16] + ".img")
            if not photo.exists():
                request = urllib.request.Request(url, headers={"User-Agent": "EdgerunnersStudio/1.0"})
                with urllib.request.urlopen(request, timeout=40) as response:
                    photo.write_bytes(response.read())
        start = next((w["s"] for w in audio["words"] if w["t"] >= token), None)
        if start is None:
            raise ValueError("Timings de voix incomplets.")
        path = card(plan, seg, i, pictures / f"card_{i:02d}.png", photo)
        scenes.append({"image": path, "start": 0 if i == 0 else start, "motion": "none"})
        token += len(seg["narration"].split())
    save_json(work / "scenes.json", scenes)
    (job / "script.txt").write_text(text + "\n", encoding="utf-8")
    (job / "captions.srt").write_text(render.build_srt(audio["words"]), encoding="utf-8")
    track = work / "music.mp3"
    if not track.exists():
        music.generate("", str(track), minutes=1, track=TENSE)
    video = work / "video.mp4"
    ch = newsvid.channel(plan["channel"])
    result = render.render_video(str(work), scenes, str(work / "voice.mp3"), str(video),
                                 words=audio["words"], motion="none", transition_dur=0.25,
                                 captions={"mode": "phrase", "size": 46, "highlight": ch["accent2"]},
                                 music_path=str(track), music_volume=0.035,
                                 progress=lambda p, msg: log(f"{p:.0%} {msg}"))
    check_sheets(str(video), str(job / "check"), every=5)
    save_json(job / "result.json", {"file": str(video), "minutes": round(result["duration"] / 60, 2),
                                   "size": video.stat().st_size, "format": "analysis_brief",
                                   "review_required": True, "segments": len(scenes)})
    log(f"Montage terminé : {result['duration'] / 60:.2f} minutes ; planches à vérifier.")
    return video
