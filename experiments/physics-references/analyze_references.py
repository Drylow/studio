"""Probe downloaded reference clips, sample visuals and measure audio envelopes."""
from pathlib import Path
import hashlib
import io
import json
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw


def run(args):
    return subprocess.check_output(args)


root = Path(sys.argv[1]).resolve()
frames = root / "frames"
frames.mkdir(exist_ok=True)
records = []
for movie in sorted((root / "media").glob("*.mp4")):
    info = json.loads(movie.with_suffix(".info.json").read_text(encoding="utf-8"))
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)]))
    duration = float(probe["format"]["duration"])
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    raw = run(["ffmpeg", "-v", "error", "-i", str(movie), "-vn", "-ac", "1", "-ar", "24000", "-f", "f32le", "pipe:1"])
    wave = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    block = 240
    count = len(wave) // block
    rms = np.sqrt(np.mean(wave[:count * block].reshape(count, block) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-9))
    # Envelope peaks are measurable cues; they do not identify materials or sounds.
    candidates = sorted((i for i in range(1, count - 1) if rms[i] > rms[i - 1] and rms[i] >= rms[i + 1]), key=lambda i: rms[i], reverse=True)
    peaks = []
    for i in candidates:
        if all(abs(i - j) >= 25 for j in peaks):
            peaks.append(i)
        if len(peaks) == 12:
            break
    picture_duration = min(duration, float(video.get("duration", duration)))
    sample_times = [i * 0.5 for i in range(math.ceil(picture_duration * 2)) if i * 0.5 < picture_duration - 0.06]
    thumb_w, thumb_h, columns, label_h = 150, 267, 8, 22
    sheet = Image.new("RGB", (columns * thumb_w, 55 + math.ceil(len(sample_times) / columns) * (thumb_h + label_h)), "#202a22")
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 8), info["title"], fill="white")
    draw.text((10, 30), movie.stem + " | sampled every 0.5s | research reference", fill="#e8e1cd")
    for i, t in enumerate(sample_times):
        data = run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(movie), "-frames:v", "1", "-vf", f"scale={thumb_w}:{thumb_h}", "-f", "image2pipe", "-vcodec", "png", "pipe:1"])
        pic = Image.open(io.BytesIO(data)).convert("RGB")
        x, y = i % columns * thumb_w, 55 + i // columns * (thumb_h + label_h)
        sheet.paste(pic, (x, y + label_h))
        draw.text((x + 4, y + 3), f"{t:.2f}s", fill="#e8e1cd")
    sheet.save(frames / (movie.stem + ".jpg"), quality=90)
    records.append({
        "id": movie.stem, "title": info["title"], "channel": info.get("channel"),
        "channel_id": info.get("channel_id"), "url": "https://www.youtube.com/shorts/" + movie.stem,
        "upload_date": info.get("upload_date"), "views_at_download": info.get("view_count"),
        "duration_seconds": round(duration, 6), "width": video["width"], "height": video["height"],
        "fps": video["r_frame_rate"], "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
        "bytes": movie.stat().st_size, "sha256": hashlib.sha256(movie.read_bytes()).hexdigest(),
        "relative_file": "media/" + movie.name, "contact_sheet": "frames/" + movie.stem + ".jpg",
        "sampled_frames": len(sample_times),
        "audio_peak_dbfs": round(20 * math.log10(max(float(np.max(np.abs(wave))), 1e-9)), 2),
        "audio_rms_dbfs": round(20 * math.log10(max(float(np.sqrt(np.mean(wave ** 2))), 1e-9)), 2),
        "rms_10ms_local_maxima": [{"time": round(i / 100, 2), "dbfs": round(float(db[i]), 2)} for i in sorted(peaks)],
    })
    print(movie.stem, f"{duration:.2f}s", f"{len(sample_times)} frames sampled", flush=True)
(root / "manifest.json").write_text(json.dumps({"date": "2026-10-07", "purpose": "Reference research for original procedural pixel-art fruit simulations; not composition inputs", "clips": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
