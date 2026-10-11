"""Check the real encoded preview and prepare honest visual-review material."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[3]
folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "output/nature-sleep/light-preview"
movie = folder / "Quiet-Little-Worlds-Garden-24s.mp4"
qa = folder / "qa"
qa.mkdir(parents=True, exist_ok=True)
receipt = json.loads((folder / "render-receipt.json").read_text())
digest = hashlib.sha256(movie.read_bytes()).hexdigest()
if digest != receipt["sha256"]:
    raise SystemExit("The movie differs from its render receipt.")
source_path = Path(receipt["source"])
if hashlib.sha256(source_path.read_bytes()).hexdigest() != receipt["source_sha256"]:
    raise SystemExit("The original illustrated garden changed during export.")
if (receipt["source_geometry"]["width"], receipt["source_geometry"]["height"]) != (1672, 941):
    raise SystemExit("Unexpected original artwork dimensions.")
probe = json.loads(subprocess.check_output([
    "/usr/bin/ffprobe", "-v", "error", "-count_frames", "-show_streams",
    "-show_format", "-of", "json", str(movie),
], text=True))
video = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
audio = [stream for stream in probe["streams"] if stream["codec_type"] == "audio"]
if len(video) != 1 or audio:
    raise SystemExit("The preview must contain one video stream and no audio.")
stream = video[0]
if (stream["width"], stream["height"], stream["avg_frame_rate"], int(stream["nb_read_frames"])) != (1920, 1080, "30/1", 720):
    raise SystemExit("Unexpected dimensions, rate or frame count.")
if abs(float(probe["format"]["duration"]) - 24) > .001:
    raise SystemExit("Unexpected duration.")
decoded = subprocess.run([
    "/usr/bin/ffmpeg", "-hide_banner", "-v", "error", "-i", str(movie),
    "-map", "0:v:0", "-f", "null", "-",
], text=True, capture_output=True)
(qa / "full-decode.log").write_text(decoded.stderr)
if decoded.returncode or decoded.stderr.strip():
    raise SystemExit("The full video decode reported an error.")

indices = [0, 1, 2, 178, 179, 180, 358, 359, 360, 538, 539, 540, 716, 717, 718, 719]
expression = "+".join(f"eq(n,{frame})" for frame in indices)
subprocess.run([
    "/usr/bin/ffmpeg", "-hide_banner", "-v", "error", "-i", str(movie),
    "-vf", f"select='{expression}'", "-vsync", "0", "-y", str(qa / "decoded-%02d.png"),
], check=True)
frames = {}
items = []
for ordinal, frame in enumerate(indices, 1):
    path = qa / f"decoded-{ordinal:02d}.png"
    image = Image.open(path).convert("RGB")
    frames[frame] = image
    items.append({"frame": frame, "time_seconds": frame / 30, "file": str(path)})
sheet = Image.new("RGB", (1440, 904), "#151d21")
draw = ImageDraw.Draw(sheet)
for ordinal, item in enumerate(items):
    x = ordinal % 4 * 360
    y = ordinal // 4 * 226
    small = frames[item["frame"]].resize((360, 202), Image.Resampling.LANCZOS)
    sheet.paste(small, (x, y))
    draw.text((x + 8, y + 207), f'{item["time_seconds"]:.3f}s — frame {item["frame"]}', fill="white")
sheet.save(qa / "decoded-contact-sheet.jpg", quality=95)

def mean_difference(first: Image.Image, second: Image.Image) -> float:
    return sum(ImageStat.Stat(ImageChops.difference(first, second)).mean) / 3

seam_difference = mean_difference(frames[719], frames[0])
nearby = [mean_difference(frames[a], frames[b]) for a, b in [(0, 1), (1, 2), (716, 717), (717, 718), (718, 719)]]
report = {
    "movie": str(movie), "sha256": digest, "bytes": movie.stat().st_size,
    "technical_pass": True, "width": 1920, "height": 1080, "fps": 30,
    "duration_seconds": 24, "decoded_frames": 720, "audio_streams": 0,
    "complete_decode_returncode": decoded.returncode, "complete_decode_errors": decoded.stderr,
    "shader_start_end_exact_match": receipt["cycle_endpoint_exact_match"],
    "decoded_seam_mean_absolute_rgb_difference_0_to_255": seam_difference,
    "decoded_near_seam_mean_absolute_rgb_differences_0_to_255": nearby,
    "seam_metric_note": "Lossy encoding makes frame 0 differ slightly from later frames. Exact shader cycle plus actual boundary pictures must be reviewed; this metric is not visual approval.",
    "source_dimensions": {"width": 1672, "height": 941},
    "native_4k": False, "source_image_unchanged": True,
    "captures": items, "contact_sheet": str(qa / "decoded-contact-sheet.jpg"),
    "visual_review_complete": False,
}
(qa / "technical-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"technical_pass": True, "duration_seconds": 24, "decoded_frames": 720, "seam_mean_difference": seam_difference, "contact_sheet": report["contact_sheet"]}))
