"""Inspect a TubeForge render and export frame-exact CapCut clips.

No generation, editorial rewriting, media approval or publication is automatic.
Run inspect, look at the generated contact sheets, then record that inspection
with accept. Export requires that review and verifies all 108 clip frame counts.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/TubeForge"))
from app import store
from app.util import now

PRIVATE = ROOT / "work/survivor-full-production-2026-10-12"
ART = ROOT / "output/imagegen/survivor-full-production-2026-10-12"
DELIVERY = ROOT / "output/videos/survivor-first-episodes-2026-10-12"
NAMES = {"patch": "01-Patch-Survives", "alien": "02-Alien-Aftermath"}
FPS = 24
FFMPEG = subprocess.check_output([str(ROOT / "venv/Scripts/python.exe"), "-c",
    "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"], text=True).strip()


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def project(episode):
    p = store.get_project(read(PRIVATE / "projects.json")[episode])
    assert p and p.get("render") and p["steps"]["render"]["state"] == "done"
    assert not any(step.get("state") == "running" for step in p["steps"].values())
    return p, store.project_dir(p["id"])


def audio_pcm(path):
    result = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path),
        "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
        capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def clock(p):
    previous = 0
    rows = []
    for scene in p["scenes"]:
        end = round(scene["end"] * FPS)
        assert end > previous
        rows.append({"id": scene["id"], "first_frame": previous, "end_frame_exclusive": end,
                     "frames": end - previous, "start": previous / FPS, "end": end / FPS,
                     "text": scene["text"], "location": scene["location_id"]})
        previous = end
    assert previous == round(p["voiceover"]["duration"] * FPS)
    return rows


def inspect(episode):
    import av
    p, directory = project(episode)
    movie = directory / p["render"]["file"]
    rows = clock(p)
    out = ART / "render-checks" / episode
    out.mkdir(parents=True, exist_ok=True)
    selected = {(s["first_frame"] + s["end_frame_exclusive"] - 1) // 2: s["id"] for s in rows}
    container = av.open(str(movie))
    video = container.streams.video[0]
    assert (video.width, video.height) == (1920, 1080)
    assert float(video.average_rate) == FPS and len(container.streams.audio) == 1
    video.codec_context.thread_count = 4
    video.codec_context.thread_type = "AUTO"
    count = 0
    for n, frame in enumerate(container.decode(video=0)):
        if n in selected:
            frame.to_image().save(out / f"{selected[n]:03d}.png")
        count += 1
    container.close()
    assert count == rows[-1]["end_frame_exclusive"]
    assert len(selected) == len(rows) == 108
    original = audio_pcm(directory / p["voiceover"]["file"])
    rendered = audio_pcm(movie)
    # Detect any offset introduced by muxing, then compare the entire narration.
    a, b = original[:160000], rendered[:160000]
    fft_size = 1 << (len(a) + len(b) - 1).bit_length()
    values = np.fft.irfft(np.fft.rfft(b, fft_size) * np.conj(np.fft.rfft(a, fft_size)), fft_size)
    lags = np.arange(-800, 801)
    lag = int(lags[np.argmax(values[lags % fft_size])])
    if lag >= 0:
        b, a = rendered[lag:], original
    else:
        a, b = original[-lag:], rendered
    size = min(len(a), len(b))
    a, b = a[:size], b[:size]
    similarity = float(np.dot(a, b) / np.sqrt(np.dot(a, a) * np.dot(b, b)))
    assert abs(lag) / 16000 < 0.05 and similarity > 0.97
    assert abs(len(rendered) / 16000 - p["voiceover"]["duration"]) < 0.1
    for start in range(1, 109, 12):
        sheet = Image.new("RGB", (1800, 1472), "#eae7df")
        draw = ImageDraw.Draw(sheet)
        for k, sid in enumerate(range(start, min(start + 12, 109))):
            im = Image.open(out / f"{sid:03d}.png").convert("RGB")
            im.thumbnail((596, 335))
            x, y = (k % 3) * 600, (k // 3) * 368
            draw.text((x + 8, y + 4), f"{episode}-{sid:03d} / rendered midpoint", fill="#111111")
            sheet.paste(im, (x, y + 24))
        sheet.save(out / f"contact-{start:03d}.jpg", quality=96)
    report = {"project_id": p["id"], "render_sha256": digest(movie), "width": 1920, "height": 1080,
              "fps": FPS, "decoded_video_frames": count, "video_seconds": count / FPS,
              "audio_seconds": len(rendered) / 16000, "voice_seconds": p["voiceover"]["duration"],
              "full_audio_similarity": similarity, "audio_lag_seconds": lag / 16000,
              "scenes": len(rows), "decoded_video_without_errors": True,
              "contact_sheets": [f"contact-{i:03d}.jpg" for i in range(1, 109, 12)],
              "visual_review": "pending", "user_approved": False}
    write(out / "verification.json", report)
    print(episode, "full render decoded", count, "frames; audio similarity", round(similarity, 5), flush=True)


def accept(episode, notes):
    from app import workspace_api as api
    assert notes, "Record actual contact-sheet inspection notes"
    p, directory = project(episode)
    report = read(ART / "render-checks" / episode / "verification.json")
    assert report["render_sha256"] == digest(directory / p["render"]["file"])
    assert all(s.get("codex_visual_review", {}).get("state") == "inspected" for s in p["scenes"])
    report.update(visual_review="inspected", reviewer="Codex", notes=notes, user_approved=False)
    write(ART / "render-checks" / episode / "verification.json", report)
    p["render"].update(qa_pending=False, publication_ready=False)
    p.setdefault("human_reviews", {})["render"] = {
        "state": "verified", "reviewer": "Codex", "source": "delegated_agent_montage_review",
        "user_approved": False, "reviewed_at": now(), "notes": notes,
        "evidence": api._scope_evidence(p, "render")}
    p["workspace_queue"].update(state="complete_agent_reviewed")
    store.save_project(p)
    full = api._full(p)
    assert full["technical_ready"] and full["publication_ready"]
    print(episode, "montage inspected; no YouTube publication performed", flush=True)


def export(episode):
    import av
    import urllib.request
    p, directory = project(episode)
    report = read(ART / "render-checks" / episode / "verification.json")
    movie = directory / p["render"]["file"]
    assert report["visual_review"] == "inspected" and report["render_sha256"] == digest(movie)
    with urllib.request.urlopen("http://127.0.0.1:8766/api/workspace/projects/" + p["id"], timeout=60) as response:
        assert json.load(response)["publication_ready"]
    rows = clock(p)
    folder = DELIVERY / NAMES[episode]
    clips = folder / "clips-capcut"
    clips.mkdir(parents=True, exist_ok=True)
    shutil.copy2(movie, folder / "video.mp4")
    shutil.copy2(directory / p["voiceover"]["file"], folder / "voiceover.mp3")
    shutil.copy2(directory / p["render"]["srt"], folder / "subtitles.srt")
    (folder / "script-en.txt").write_text(p["script"] + "\n", encoding="utf-8")
    shutil.copy2(ART / "render-checks" / episode / "verification.json", folder / "verification.json")
    thumb = ART / "scenes" / (episode + "-thumbnail.png")
    # Only technical size/format conversion of an already inspected generated image.
    Image.open(thumb).convert("RGB").resize((1280, 720), Image.Resampling.LANCZOS).save(folder / "thumbnail.jpg", quality=95)
    assert (folder / "thumbnail.jpg").stat().st_size < 2 * 1024 * 1024
    boundaries = ",".join(f"{s['end']:.9f}" for s in rows[:-1])
    existing = list(clips.glob("*.mp4"))
    if existing:
        assert len(existing) == len(rows), "Inspect partial export before restarting"
    else:
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(movie),
            "-map", "0:v:0", "-an", "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "18", "-b:v", "0",
            "-bf", "0", "-forced-idr", "1", "-pix_fmt", "yuv420p", "-force_key_frames", boundaries,
            "-f", "segment", "-segment_times", boundaries, "-segment_time_delta", str(0.5 / FPS),
            "-reset_timestamps", "1", "-segment_start_number", "1", "-segment_format", "mp4",
            "-n", str(clips / "%03d.mp4")], check=True)
    clip_frames = 0
    for row in rows:
        path = clips / f"{row['id']:03d}.mp4"
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            assert not container.streams.audio and (stream.width, stream.height) == (1920, 1080)
            assert stream.frames == row["frames"], f"{path.name}: wrong clip length {stream.frames} vs {row['frames']}"
            clip_frames += stream.frames
    assert clip_frames == report["decoded_video_frames"]
    with (folder / "timeline.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (folder / "CAPCUT.txt").write_text(
        "Importez les clips de clips-capcut dans l'ordre 001 a 108. Placez voiceover.mp3 au temps 00:00.\n"
        "Les clips sont muets et leurs longueurs couvrent exactement toute la voix, a 24 images/s.\n"
        "video.mp4 contient deja le montage et la voix. Ne superposez pas sa voix avec voiceover.mp3.\n"
        "Vous pouvez importer subtitles.srt separement. Ne modifiez pas les durees si vous voulez garder le calage.\n"
        "Les transitions ajoutees avec chevauchement peuvent modifier les timings.\n"
        "Animation legere de camera ; coupes franches. Aucune publication YouTube effectuee.\n", encoding="utf-8")
    files = [f for f in folder.rglob("*") if f.is_file() and f.name != "manifest.json"]
    manifest = {"title": p["title"], "project_id": p["id"], "video_seconds": report["video_seconds"],
        "voice_seconds": p["voiceover"]["duration"], "clips": len(rows), "clip_frames_sum": clip_frames,
        "fps": FPS, "published": False,
        "files": {f.relative_to(folder).as_posix(): {"sha256": digest(f), "bytes": f.stat().st_size} for f in files}}
    write(folder / "manifest.json", manifest)
    archive = DELIVERY / (NAMES[episode] + ".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for f in folder.rglob("*"):
            if f.is_file():
                bundle.write(f, f.relative_to(folder).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for filename, evidence in manifest["files"].items():
            assert hashlib.sha256(bundle.read(filename)).hexdigest() == evidence["sha256"]
    print(episode, "export complete; 108 ordered clips verified frame by frame in duration; ZIP hashes verified", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "accept", "export"])
    parser.add_argument("episode", choices=NAMES)
    parser.add_argument("--notes")
    args = parser.parse_args()
    if args.action == "accept":
        accept(args.episode, args.notes)
    else:
        {"inspect": inspect, "export": export}[args.action](args.episode)
