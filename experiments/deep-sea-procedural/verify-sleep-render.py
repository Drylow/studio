#!/usr/bin/env python3
"""Check a finished five-minute sleep render and prepare images for human review.

Requires FFmpeg, FFprobe, and Pillow. Passing machine checks never marks the
render as visually reviewed: qa.json keeps that decision for a separate review.
"""

import argparse
import array
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


DURATION = 300
RATE = 48000
FPS = 30
FRAMES = DURATION * FPS
WIDTH, HEIGHT = 1920, 1080
NATIVE_TIMES = [0, 1 / FPS, 25, 65, 100, 140, 180, 220, 260,
                DURATION - 2 / FPS, DURATION - 1 / FPS]
MOTION_SEQUENCES = [
    ("angler", 0, 5, 8), ("jelly", 62, 5, 8), ("ray", 211, 5, 8),
    ("shoal", 173, 5, 8), ("boundary-before", 296, 4, 6),
    ("boundary-after", 0, 4, 6),
]
AMBIENCE_FIELDS = (
    "seconds", "sample_rate", "channels", "peak_dbfs", "rms_dbfs",
    "boundary_sample_step", "maximum_adjacent_step", "samples_clipped",
    "periodic_synthesis", "external_samples",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(arguments):
    result = subprocess.run(arguments, stdin=subprocess.DEVNULL,
                            capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{arguments[0]} failed: {detail[-3000:]}")
    return result.stdout


def read_json(file):
    with file.open(encoding="utf-8") as stream:
        value = json.load(stream)
    require(isinstance(value, dict), f"Expected a JSON object: {file.name}")
    return value


def digest(file):
    checksum = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def dbfs(amplitude):
    require(math.isfinite(amplitude) and amplitude > 0,
            "The ambience must contain finite, non-silent audio.")
    return 20 * math.log10(amplitude)


def check_ambience(report, file):
    """Compare the JSON measurements with its sibling periodic PCM master."""
    require(all(key in report for key in AMBIENCE_FIELDS),
            "The ambience report is incomplete.")
    require(report["seconds"] == DURATION and report["sample_rate"] == RATE
            and report["channels"] == 2, "Expected a 300-second stereo 48 kHz master.")
    require(report["periodic_synthesis"] is True and report["external_samples"] == 0,
            "Expected the original periodic ambience without external samples.")
    require(report["samples_clipped"] == 0, "The ambience report contains clipping.")
    count, peak, squared, clipped = 0, 0, 0, 0
    first, previous, maximum_steps = None, None, [0, 0]
    with wave.open(str(file), "rb") as stream:
        require((stream.getnchannels(), stream.getsampwidth(), stream.getframerate(),
                 stream.getnframes(), stream.getcomptype())
                == (2, 2, RATE, DURATION * RATE, "NONE"),
                "The master WAV must be exactly 300 seconds of stereo 48 kHz PCM16.")
        while raw := stream.readframes(RATE):
            samples = array.array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            require(len(samples) % 2 == 0, "Incomplete stereo PCM master frame.")
            if first is None:
                first = samples[:2].tolist()
            for i in range(0, len(samples), 2):
                pair = (samples[i], samples[i + 1])
                for channel, value in enumerate(pair):
                    peak = max(peak, abs(value))
                    squared += value * value
                    clipped += abs(value) >= 32767
                    if previous is not None:
                        maximum_steps[channel] = max(maximum_steps[channel],
                                                     abs(value - previous[channel]))
                previous = pair
            count += len(samples)
    boundary = [first[channel] - previous[channel] for channel in range(2)]
    require(clipped == 0, "The source WAV contains clipped samples.")
    require(boundary == report["boundary_sample_step"]
            and maximum_steps == report["maximum_adjacent_step"],
            "The ambience report does not match the master WAV boundary measurements.")
    require(abs(dbfs(peak / 32768) - report["peak_dbfs"]) < .01
            and abs(dbfs(math.sqrt(squared / count) / 32768) - report["rms_dbfs"]) < .01,
            "The ambience report does not match the master WAV level measurements.")
    require(all(abs(boundary[c]) <= maximum_steps[c] * 1.5 + 4 for c in range(2)),
            "The source WAV has an abnormal boundary step.")
    return peak / 32768


def check_encoded_audio(video, source_peak):
    """Stream PCM from the delivered MP4 without keeping five minutes in memory."""
    valid_samples = DURATION * RATE * 2
    edge_samples = RATE * 2
    first = array.array("f")
    last = array.array("f")
    decoded_samples, peak, clipped = 0, 0., 0
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(video),
             "-map", "0:a:0", "-vn", "-sn", "-dn", "-f", "f32le",
             "-acodec", "pcm_f32le", "pipe:1"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
        )
        try:
            while raw := process.stdout.read(edge_samples * 4):
                require(len(raw) % 8 == 0, "Incomplete decoded stereo audio frame.")
                samples = array.array("f")
                samples.frombytes(raw)
                if sys.byteorder != "little":
                    samples.byteswap()
                for value in samples:
                    require(math.isfinite(value), "Decoded audio contains a non-finite sample.")
                    peak = max(peak, abs(value))
                    clipped += abs(value) >= .999
                if len(first) < edge_samples:
                    first.extend(samples[:edge_samples - len(first)])
                # Keep the last second inside the exact 300-second program;
                # AAC decoder padding beyond that interval is not the loop bed.
                valid = samples[:max(0, valid_samples - decoded_samples)]
                last.extend(valid)
                if len(last) > edge_samples:
                    del last[:-edge_samples]
                decoded_samples += len(samples)
            status = process.wait()
            if status:
                errors.seek(0)
                detail = errors.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"FFmpeg audio decode failed: {detail[-3000:]}")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
    require(decoded_samples >= valid_samples, "Decoded audio ends before 300 seconds.")
    require(clipped == 0, "The finished MP4 contains clipped audio samples.")
    require(peak <= source_peak * 1.4,
            "The encoded ambience peak exceeds the source by more than about 3 dB.")
    boundary = [abs(first[c] - last[-2 + c]) for c in range(2)]
    normal_steps = [max(
        max(abs(first[i] - first[i - 2]) for i in range(2 + c, len(first), 2)),
        max(abs(last[i] - last[i - 2]) for i in range(2 + c, len(last), 2)),
    ) for c in range(2)]
    require(all(boundary[c] <= normal_steps[c] * 2 + .001 for c in range(2)),
            "The encoded ambience has an abnormal loop-boundary step.")
    return peak, clipped, {
        "decoded_sample_frames": decoded_samples // 2,
        "valid_duration_sample_frames": valid_samples // 2,
        "boundary_step": boundary,
        "first_last_second_max_normal_step": normal_steps,
        "loop_bed_source": "The original 300-second periodic PCM master is the source for future long mixes; repeated AAC packets are not used as the narration bed.",
    }


def frame_rms(left, right):
    with Image.open(left) as a, Image.open(right) as b:
        require(a.size == b.size == (WIDTH, HEIGHT), "A native review frame has wrong dimensions.")
        difference = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        return math.sqrt(sum(value * value for value in ImageStat.Stat(difference).rms) / 3)


def panels(files, label, directory):
    width, height, columns = 480, 270, 4
    for offset in range(0, len(files), 20):
        batch = files[offset:offset + 20]
        sheet = Image.new("RGB", (width * columns, (height + 24) * math.ceil(len(batch) / columns)),
                          "#0a171c")
        draw = ImageDraw.Draw(sheet)
        for i, file in enumerate(batch):
            with Image.open(file) as source:
                image = source.convert("RGB")
            image.thumbnail((width, height))
            x, y = i % columns * width, i // columns * (height + 24)
            sheet.paste(image, (x, y))
            draw.text((x + 8, y + height + 4), f"{label} {file.stem}", fill="white")
        sheet.save(directory / f"{label}-contact-{offset // 20 + 1}.jpg", quality=94)


def numbered_frames(directory, prefix, count, digits=2):
    files = [directory / f"{prefix}-{i:0{digits}d}.jpg" for i in range(1, count + 1)]
    require(all(file.is_file() for file in files), f"Missing extracted {prefix} frames.")
    return files


def verify(options):
    video = options.video.resolve()
    scene_file = options.scene_check.resolve()
    ambience_file = options.ambience_check.resolve()
    directory = options.out_dir.resolve()
    sidecar = Path(str(video) + ".render.json")
    master = ambience_file.with_suffix(".wav")
    for file in (video, sidecar, scene_file, ambience_file, master):
        require(file.is_file(), f"Required input is missing: {file}")
    require(directory != video,
            "The review directory must not replace the video.")
    capture, loop, ambience = read_json(sidecar), read_json(scene_file), read_json(ambience_file)
    source = capture["source"]
    sha = digest(video)
    require(sha == capture["sha256"] and video.stat().st_size == capture["bytes"]
            and video.name == capture["file"], "The video does not match its capture sidecar.")
    require((capture["width"], capture["height"], capture["fps"], capture["frames"],
             capture["duration_seconds"]) == (WIDTH, HEIGHT, FPS, FRAMES, DURATION),
            "The capture sidecar describes a different render format.")
    require(capture.get("browser_errors") == [] and capture["scene"]["antialias"] is True,
            "The capture must have native antialiasing and no browser errors.")
    require(capture["paid_generation_calls"] == 0 and capture["external_images"] == 0,
            "Expected the original procedural scene without generated or external images.")
    require(loop["passed"] is True and loop["endpoints_pixel_identical"] is True
            and loop["rock_overlap_count"] == 0, "The scene loop checks did not pass.")
    require((loop["width"], loop["height"], loop["duration_seconds"])
            == (WIDTH, HEIGHT, DURATION), "The scene check describes a different loop.")
    require(loop["scene_bundle_sha256"] == source["scene_sha256"],
            "The checked scene bundle differs from the one used for this render.")
    require(digest(master) == source["audio_sha256"],
            "The ambience master differs from the one used for this render.")
    source_peak = check_ambience(ambience, master)
    metadata = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams",
                               "-show_format", "-of", "json", str(video)]))
    videos = [s for s in metadata["streams"] if s["codec_type"] == "video"]
    audios = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
    require(len(videos) == len(audios) == 1, "Expected one video and one audio stream.")
    v, a = videos[0], audios[0]
    require((v["width"], v["height"], v["r_frame_rate"], v["avg_frame_rate"],
             int(v["nb_read_frames"])) == (WIDTH, HEIGHT, "30/1", "30/1", FRAMES),
            "Expected 9,000 native 1080p frames at exactly 30 fps.")
    require(abs(float(metadata["format"]["duration"]) - DURATION) < .05
            and abs(float(v["duration"]) - DURATION) < .05,
            "The finished render must be 300 seconds long.")
    require(a["sample_rate"] == str(RATE) and a["channels"] == 2,
            "The finished audio must be stereo 48 kHz.")
    run(["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(video),
         "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
    print("Full 300-second video/audio decode passed.", flush=True)
    directory.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(video),
         "-vf", "fps=1/5", "-q:v", "2", str(directory / "sample-%03d.jpg")])
    files = numbered_frames(directory, "sample", 60, digits=3)
    panels(files, "overview", directory)
    for time in NATIVE_TIMES:
        run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", str(time),
             "-i", str(video), "-frames:v", "1", "-update", "1",
             str(directory / f"native-{time:.3f}.png")])
    boundary = frame_rms(directory / "native-299.967.png", directory / "native-0.000.png")
    first_step = frame_rms(directory / "native-0.000.png", directory / "native-0.033.png")
    last_step = frame_rms(directory / "native-299.933.png", directory / "native-299.967.png")
    require(boundary < max(first_step, last_step) * 2 + 2,
            "The encoded visual boundary differs abnormally from ordinary adjacent frames.")
    print(f"Encoded visual boundary RMS: {boundary}; ordinary steps: {first_step}, {last_step}",
          flush=True)
    peak, clipping, encoded_audio = check_encoded_audio(video, source_peak)
    print(f"Encoded audio boundary: {json.dumps(encoded_audio)}", flush=True)
    motion_count = 0
    for name, start, seconds, rate in MOTION_SEQUENCES:
        run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", str(start),
             "-i", str(video), "-t", str(seconds), "-vf", f"fps={rate}",
             "-q:v", "2", str(directory / f"{name}-%02d.jpg")])
        sequence = numbered_frames(directory, name, seconds * rate)
        motion_count += len(sequence)
        panels(sequence, name, directory)
    # Preserve the public report shape used by delivery tooling. Review flags
    # always start false; only a separate actual review can change them.
    report = {
        "schema": "deep-sea-sleep-qa-v1", "file": video.name, "sha256": sha,
        "bytes": video.stat().st_size,
        "duration_seconds": float(metadata["format"]["duration"]),
        "frames": FRAMES, "dimensions": [WIDTH, HEIGHT], "fps": "30/1",
        "color_space": v.get("color_space"), "full_video_audio_decode_ok": True,
        "audio_peak_dbfs": dbfs(peak), "audio_clipping_samples": clipping,
        "audio_periodic_master_check": {key: ambience[key] for key in AMBIENCE_FIELDS},
        "encoded_audio_boundary": encoded_audio,
        "finished_render_visual_reviewed": False, "human_continuous_viewing": False,
        "human_full_audio_listening": False, "sampled_movie_frames": len(files),
        "motion_movie_frames": motion_count, "native_movie_frames": len(NATIVE_TIMES),
        "loop_geometry_check_passed": loop["passed"],
        "loop_endpoints_pixel_identical": loop["endpoints_pixel_identical"],
        "loop_sample_hz": loop["sample_hz"], "loop_rock_overlap_count": loop["rock_overlap_count"],
        "encoded_visual_boundary_rms": boundary,
        "encoded_visual_ordinary_step_rms": [first_step, last_step],
        "source_scene_sha256": source["scene_sha256"],
        "paid_generation_calls": 0, "external_images": 0,
    }
    temporary = directory / "qa.json.partial"
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(directory / "qa.json")
    print(json.dumps(report, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="Finished 300-second MP4.")
    parser.add_argument("--scene-check", type=Path, required=True,
                        help="JSON report from verify-sleep-loop.mjs.")
    parser.add_argument("--ambience-check", type=Path, required=True,
                        help="Ambience JSON report with its matching .wav in the same directory.")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="Directory for qa.json, review frames, and contact sheets.")
    options = parser.parse_args()
    try:
        verify(options)
    except (OSError, ValueError, KeyError, RuntimeError, wave.Error) as error:
        print(f"Sleep-render verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
