"""Technical execution of the manually authored Edo episode, without AI writing."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import textwrap

from common import REPO
from services import align, media, render, tts


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return "".join(c for c in text.lower() if c.isalnum())


def timestamp(seconds):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def measure_words(audio, language):
    import numpy as np
    if not align.available():
        return None
    # Feed decoded samples to the existing aligner; avoid incompatible decoder APIs.
    decoded = subprocess.run([media.ffmpeg_bin(), "-hide_banner", "-v", "error", "-i", str(audio),
                              "-f", "f32le", "-ar", "16000", "-ac", "1", "pipe:1"],
                             capture_output=True, check=True)
    samples = np.frombuffer(decoded.stdout, dtype=np.float32)
    return align.words_from_audio(samples, language)


def speech(episode, work):
    text = "\n\n".join(s["narration"] for s in episode["shots"])
    identity = {"text": text, "voice": episode["voice"]}
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    audio, result = work / "narration.mp3", work / "voice.json"
    if result.exists() and audio.exists():
        old = read(result)
        if old.get("signature") != signature:
            raise SystemExit("Narration changed: choose a new work directory before generating again.")
        print("Voice already cached", flush=True)
        return
    config = episode["voice"]
    print("Generating the approved narration with the configured voice provider", flush=True)
    res = tts.synthesize(text, str(audio), provider=config["provider"], voice=config["id"],
                         speed=config["speed"], lang=episode["language"])
    save(result, {"signature": signature, "duration": res["duration"],
                  "audio_sha256": digest(audio), "provider": config["provider"],
                  "provider_words": res["words"]})
    print(f"Voice complete: {res['duration']:.2f} seconds", flush=True)


def timeline(episode, work):
    audio = work / "narration.mp3"
    voice = read(work / "voice.json")
    if digest(audio) != voice["audio_sha256"]:
        raise SystemExit("Audio changed since voice generation.")
    text = "\n\n".join(s["narration"] for s in episode["shots"])
    measured = work / "measured_words.json"
    if measured.exists():
        cached = read(measured)
        if cached["audio_sha256"] != digest(audio):
            raise SystemExit("Measured transcript references different narration.")
        raw = cached["words"]
    else:
        print("Measuring words on actual narration audio", flush=True)
        raw = measure_words(audio, episode["language"])
        if not raw:
            raise SystemExit("No measured word timings; estimated provider timings are not accepted.")
        save(measured, {"audio_sha256": digest(audio), "words": raw})
    expected = [normalized(t) for t in text.split()]
    heard = [normalized(w["w"]) for w in raw]
    matcher = difflib.SequenceMatcher(None, expected, heard, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    coverage = matched / max(1, len(expected))
    print(f"Measured transcript coverage: {coverage:.2%}", flush=True)
    if coverage < 0.94:
        raise SystemExit("Narration/transcript discrepancy needs manual review before timing shots.")
    words = tts.align_to_text(raw, text)
    if len(words) != len(expected):
        raise SystemExit("Alignment did not retain the complete authored script.")
    if any(b["s"] < a["s"] for a, b in zip(words, words[1:])):
        raise SystemExit("Non-monotonic word timestamps.")
    total = media.duration(str(audio))
    cursor, shots = 0, []
    for index, shot in enumerate(episode["shots"]):
        count = len(shot["narration"].split())
        start = 0.0 if index == 0 else words[cursor]["s"]
        shots.append({**shot, "start": start, "word_start": cursor,
                      "word_end": cursor + count - 1})
        cursor += count
    for i, shot in enumerate(shots):
        shot["end"] = shots[i + 1]["start"] if i + 1 < len(shots) else total
        if shot["end"] <= shot["start"]:
            raise SystemExit(f"Invalid shot duration: {shot['id']}")
    save(work / "words.json", words)
    save(work / "timeline.json", {"duration": total, "coverage": coverage,
                                  "audio_sha256": digest(audio), "shots": shots})
    subtitles = []
    chunk = []
    for word in words:
        chunk.append(word)
        if len(" ".join(w["w"] for w in chunk)) >= 65 or word["w"].endswith((".", "?", "!")):
            subtitles.append(chunk)
            chunk = []
    if chunk:
        subtitles.append(chunk)
    srt = []
    for i, block in enumerate(subtitles, 1):
        srt.extend([str(i), f"{timestamp(block[0]['s'])} --> {timestamp(block[-1]['e'])}",
                    "\n".join(textwrap.wrap(" ".join(w["w"] for w in block), width=42)), ""])
    (work / "subtitles.srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"Timeline complete: {len(shots)} shots, {total:.2f} seconds", flush=True)


def freeze(episode, work):
    from PIL import Image
    reviews = read(work / "reference_review.json")
    assets = {}
    for shot in episode["shots"]:
        for reference in shot["references"]:
            path = Path(REPO) / reference
            name = path.stem
            if name not in reviews or not reviews[name].get("accepted"):
                raise SystemExit(f"Reference not manually accepted: {name}")
            with Image.open(path) as im:
                dimensions = list(im.size)
            assets[reference] = {"sha256": digest(path), "dimensions": dimensions,
                                 "review": reviews[name]["notes"]}
    save(work / "frozen_references.json", assets)
    print(f"Frozen references: {len(assets)}", flush=True)


def validate_images(episode, work):
    from PIL import Image
    frozen = read(work / "frozen_references.json")
    for name, meta in frozen.items():
        if digest(Path(REPO) / name) != meta["sha256"]:
            raise SystemExit(f"Canonical reference changed: {name}")
    reviews = read(work / "image_review.json")
    for shot in episode["shots"]:
        path = Path(REPO) / shot["image"]
        review = reviews.get(shot["id"], {})
        if not review.get("accepted") or review.get("sha256") != digest(path):
            raise SystemExit(f"Shot must be reviewed before rendering: {shot['id']}")
        with Image.open(path) as im:
            if abs(im.width / im.height - 16 / 9) > 0.025:
                raise SystemExit(f"Shot aspect ratio invalid: {shot['id']}")
    return True


def export_video(episode, work, width, height):
    validate_images(episode, work)
    plan = read(work / "timeline.json")
    if plan["audio_sha256"] != digest(work / "narration.mp3"):
        raise SystemExit("Timeline references different narration.")
    if [{k: s[k] for k in ("id", "image", "narration", "motion")} for s in plan["shots"]] != [
            {k: s[k] for k in ("id", "image", "narration", "motion")} for s in episode["shots"]]:
        raise SystemExit("Shot selection changed: rebuild the measured timeline before rendering.")
    scenes = [{"image": str(Path(REPO) / s["image"]), "start": s["start"],
               "motion": s["motion"]} for s in plan["shots"]]
    build = work / "render"
    build.mkdir(exist_ok=True)
    final = work / "Edo-Daily-01.mp4"
    result = render.render_video(str(build), scenes, str(work / "narration.mp3"), str(final),
                                 width=width, height=height, fps=30, motion_strength=0.045,
                                 transition="fade", transition_dur=0.2, quality="high",
                                 captions={"mode": "none"}, tail=0.4,
                                 progress=lambda p, msg: print(f"{p:.0%} {msg}", flush=True))
    save(work / "render_result.json", result)
    print("Render complete", flush=True)


def image_sheets(episode, work):
    from PIL import Image, ImageDraw
    folder = work / "image-check"
    folder.mkdir(exist_ok=True)
    ready = [s for s in episode["shots"] if (Path(REPO) / s["image"]).exists()]
    for offset in range(0, len(ready), 6):
        sheet = Image.new("RGB", (1800, 1620), "#181818")
        draw = ImageDraw.Draw(sheet)
        for j, shot in enumerate(ready[offset:offset + 6]):
            with Image.open(Path(REPO) / shot["image"]) as source:
                frame = source.convert("RGB")
                frame.thumbnail((900, 506))
                x, y = (j % 2) * 900, (j // 2) * 540
                sheet.paste(frame, (x, y))
                draw.text((x + 8, y + 510), shot["id"] + " - " + shot["location"], fill="white")
        sheet.save(folder / f"images_{offset // 6 + 1:02d}.jpg", quality=95)
    print(f"Contact sheets ready: {len(ready)}/{len(episode['shots'])} images", flush=True)


def qa(episode, work):
    from PIL import Image, ImageDraw
    plan = read(work / "timeline.json")
    final = work / "Edo-Daily-01.mp4"
    check = work / "check"
    check.mkdir(exist_ok=True)
    frames = []
    for shot in plan["shots"]:
        span = shot["end"] - shot["start"]
        for part, fraction in enumerate((0.2, 0.5, 0.8), 1):
            at = shot["start"] + span * fraction
            path = check / f"{shot['id']}_{part}.jpg"
            media.run(["-ss", str(at), "-i", str(final), "-frames:v", "1", "-q:v", "2", str(path)])
            frames.append((f"{shot['id']}.{part}", at, path))
    for batch in range(0, len(frames), 12):
        sheet = Image.new("RGB", (1280, 840), "#181818")
        draw = ImageDraw.Draw(sheet)
        for j, (sid, at, path) in enumerate(frames[batch:batch + 12]):
            with Image.open(path) as im:
                im.thumbnail((426, 239))
                x, y = (j % 3) * 426, (j // 3) * 210
                im.thumbnail((426, 185))
                sheet.paste(im, (x, y))
                draw.text((x + 8, y + 187), f"{sid} - {at:.2f}s", fill="white")
        sheet.save(check / f"sheet_{batch // 12 + 1:02d}.jpg", quality=94)
    decoded = subprocess.run([media.ffmpeg_bin(), "-hide_banner", "-v", "error", "-i", str(final),
                              "-f", "null", "-"], capture_output=True, text=True)
    if decoded.returncode or decoded.stderr.strip():
        raise SystemExit("Decode errors: " + decoded.stderr[:500])
    duration = media.duration(str(final))
    if abs(duration - (plan["duration"] + 0.4)) > 0.2:
        raise SystemExit("Export duration disagrees with measured narration.")
    save(work / "qa_technical.json", {"decoded_without_errors": True, "duration": duration,
                                      "video_sha256": digest(final), "review_frames": len(frames),
                                      "visual_review_pending": True})
    print(f"Technical QA complete: {len(frames)} scene captures; visual review required", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("voice", "timeline", "freeze", "render", "qa", "image-sheets"))
    parser.add_argument("manifest")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()
    os.chdir(REPO)
    episode = read(args.manifest)
    work = Path(REPO) / episode["workdir"]
    work.mkdir(parents=True, exist_ok=True)
    if args.stage == "voice":
        speech(episode, work)
    elif args.stage == "timeline":
        timeline(episode, work)
    elif args.stage == "freeze":
        freeze(episode, work)
    elif args.stage == "render":
        export_video(episode, work, args.width, args.height)
    elif args.stage == "image-sheets":
        image_sheets(episode, work)
    else:
        qa(episode, work)
