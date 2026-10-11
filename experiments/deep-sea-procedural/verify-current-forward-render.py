#!/usr/bin/env python3
"""Verify a completed forward-loop delivery and extract review frames in one AV decode.

This verifier is pinned to the current frozen forward bundle. It does not update scene/capture code,
render receipts, artwork approval, or continuous viewing/listening flags.
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

WIDTH, HEIGHT, FPS, DURATION = 1920, 1080, 30, 300
FRAMES = FPS * DURATION
FROZEN_BUNDLE = "d3460e0da70312fcfb26134c92ca09c696750ea02a62e11ffba77731c0c8ce5f"
NATIVE_FRAMES = [0, 1, 720, 1950, 3000, 3330, 4200, 5400, 6570, 6600, 7800, 8998, 8999]
WINDOWS = [("loop-after", 0, 4), ("near-pass-24s", 20, 28),
           ("near-pass-111s", 107, 115), ("near-pass-219s", 215, 223),
           ("loop-before", 296, 300)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(file):
    value = json.loads(file.read_text(encoding="utf8"))
    require(isinstance(value, dict), f"Expected JSON object: {file.name}")
    return value


def sha256(file):
    result = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def atomic_json(file, value):
    temporary = file.with_name(file.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")
    temporary.replace(file)


def probe(video):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                             "-of", "json", str(video)], capture_output=True, check=False)
    require(result.returncode == 0, "FFprobe metadata failed: " + result.stderr.decode(errors="replace"))
    return json.loads(result.stdout)


def frame_delta(left, right):
    with Image.open(left) as a, Image.open(right) as b:
        require(a.size == b.size == (WIDTH, HEIGHT), "Unexpected native frame dimensions.")
        delta = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        stats = ImageStat.Stat(delta)
        return math.sqrt(sum(value * value for value in stats.rms) / 3)


def contact_sheets(frames, label, directory):
    for offset in range(0, len(frames), 20):
        batch = frames[offset:offset + 20]
        sheet = Image.new("RGB", (1920, 294 * math.ceil(len(batch) / 4)), "#07161c")
        draw = ImageDraw.Draw(sheet)
        for i, (file, frame_index) in enumerate(batch):
            with Image.open(file) as source:
                image = source.convert("RGB")
                image.thumbnail((480, 270))
                x, y = i % 4 * 480, i // 4 * 294
                sheet.paste(image, (x, y))
                draw.text((x + 8, y + 274), f"{label}: {frame_index/FPS:.3f} s", fill="white")
        sheet.save(directory / f"{label}-contact-{offset//20+1:02d}.jpg", quality=94)


def validate_sources(video, sidecar, scene_check, manifest):
    capture, scene, checkpoint = load(sidecar), load(scene_check), load(manifest)
    require(capture.get("schema") == "deep-sea-sleep-loop-render-v1", "Expected completed loop capture receipt.")
    require(scene.get("schema") == "deep-sea-forward-loop-v1", "Expected forward-loop scene check schema.")
    require((capture.get("width"), capture.get("height"), capture.get("fps"),
             capture.get("frames"), capture.get("duration_seconds"))
            == (WIDTH, HEIGHT, FPS, FRAMES, DURATION), "Receipt must describe all 9,000 frames of the 300-second delivery.")
    require(capture.get("checkpoint_chunks") == 30 and len(checkpoint.get("chunks", [])) == 30,
            "Expected all 30 completed checkpoints.")
    require(sorted(chunk["index"] for chunk in checkpoint["chunks"]) == list(range(30))
            and all(chunk["frames"] == 300 for chunk in checkpoint["chunks"]),
            "Checkpoint indexes or frame totals are incomplete.")
    source = capture.get("source", {})
    require(source == checkpoint.get("identity"), "Final source identity differs from checkpoints.")
    require(source.get("scene_sha256") == scene.get("scene_bundle_sha256") == FROZEN_BUNDLE,
            "Capture/source-check scene hash differs from the frozen forward bundle.")
    require(source.get("page_sha256") == scene.get("served_asset_hashes", {}).get("index.html"),
            "Checked HTML differs from the captured HTML.")
    require(capture.get("browser_errors") == [] and scene.get("browser_errors") == []
            and scene.get("local_http_errors") == [] and scene.get("assets_changed_during_check") == [],
            "Browser/source check reported errors or changed assets.")
    require(scene.get("passed") is True and scene.get("endpoints_pixels_identical") is True
            and scene.get("rewind_pixels_identical") is True and scene.get("boundary_jump_suspected") is False,
            "Source loop/determinism checks did not pass.")
    require((scene.get("width"), scene.get("height"), scene.get("duration_seconds")) == (WIDTH, HEIGHT, DURATION),
            "Source scene check describes a different delivery.")
    for field in ("monotone_camera_progress", "constant_forward_speed", "track_completed",
                  "perspective_depth_scale_consistent", "camera_z_matches_unwrapped_progress",
                  "landmark_depth_matches_world_camera", "world_counts_stable", "finite_diagnostics"):
        require(scene.get(field) is True, f"Source forward-motion check failed: {field}")
    require(scene.get("reported_global_zoom") is False and scene.get("invalid_projections") == []
            and scene.get("invalid_diagnostics") == [] and scene.get("fish_extent_corridor_violations") == [],
            "Source diagnostic check has recorded failures.")
    layout = capture.get("scene", {}).get("layout", {})
    require(capture.get("video_generation_calls") == 0 and capture.get("algrow_calls") == 0
            and layout.get("runtime_network_calls") == 0, "Unexpected runtime/generation calls in the captured ledger.")
    require(capture.get("asset_generation_calls") == layout.get("asset_generation_calls") == 2
            and capture.get("external_images") == layout.get("source_images") == 2,
            "Captured original asset ledger differs from the frozen scene.")
    digest = sha256(video)
    require(capture.get("file") == video.name and capture.get("bytes") == video.stat().st_size
            and capture.get("sha256") == digest, "Delivery bytes/hash/name differ from the completed receipt.")
    return capture, scene, digest


def decode_and_extract(video, directory):
    # All outputs share one decoded video input. Only the one-second audio
    # master measurements are delegated separately; no second MP4 decode runs.
    native_expr = "+".join(f"eq(n,{index})" for index in NATIVE_FRAMES)
    motion_frames = [n for n in range(0, FRAMES, 5)
                     if any(start*FPS <= n < end*FPS for _, start, end in WINDOWS)]
    motion_expr = "+".join(f"between(n,{start*FPS},{end*FPS-1})" for _, start, end in WINDOWS)
    graph = ("[0:v:0]split=4[vfull][voverview][vnative][vmotion];"
             "[vfull]showinfo[full];"
             "[voverview]select='not(mod(n,150))'[overview];"
             f"[vnative]select='{native_expr}'[native];"
             f"[vmotion]select='not(mod(n,5))*({motion_expr})'[motion]")
    audio = directory / "decoded-audio.f32"
    temporary_audio = audio.with_name(audio.name + ".partial")
    command = ["ffmpeg", "-hide_banner", "-v", "info", "-xerror", "-y",
               "-threads", "2", "-i", str(video), "-filter_complex_threads", "1", "-filter_complex", graph,
               "-map", "[full]", "-an", "-fps_mode", "passthrough", "-f", "null", "-",
               "-map", "[overview]", "-an", "-fps_mode", "vfr", "-q:v", "2", "-threads", "1",
               str(directory / "overview-%03d.jpg"),
               "-map", "[native]", "-an", "-fps_mode", "vfr", "-threads", "1",
               str(directory / "native-%03d.png"),
               "-map", "[motion]", "-an", "-fps_mode", "vfr", "-q:v", "2", "-threads", "1",
               str(directory / "motion-%03d.jpg"),
               "-map", "0:a:0", "-vn", "-sn", "-dn", "-ac", "2", "-ar", "48000",
               "-acodec", "pcm_f32le", "-f", "f32le", str(temporary_audio)]
    frame_pattern = re.compile(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*(\S+).*?\bs:(\d+x\d+)")
    timebase_pattern = re.compile(r"config in time_base:\s*(\d+)/(\d+)")
    frame_count, timebase, first_pts, last_pts, failures = 0, None, None, None, []
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True, errors="replace")
    try:
        with (directory / "full-av-decode.log").open("w", encoding="utf8") as log:
            for line in process.stderr:
                log.write(line)
                base = timebase_pattern.search(line)
                if base:
                    timebase = Fraction(int(base[1]), int(base[2]))
                match = frame_pattern.search(line)
                if not match:
                    continue
                n, pts, pts_time, dimensions = int(match[1]), int(match[2]), match[3], match[4]
                if n != frame_count or dimensions != "1920x1080" or timebase is None:
                    failures.append({"frame": frame_count, "n": n, "dimensions": dimensions})
                elif Fraction(pts) * timebase != Fraction(n, FPS):
                    failures.append({"frame": n, "pts": pts, "timebase": str(timebase)})
                first_pts = pts if first_pts is None else first_pts
                last_pts = pts
                frame_count += 1
                if frame_count % 900 == 0:
                    print(f"Decoded and checked PTS: {frame_count}/{FRAMES}", flush=True)
        status = process.wait()
    finally:
        process.stderr.close()
        if process.poll() is None:
            process.terminate()
            process.wait()
    require(status == 0, "Full AV decode failed; inspect full-av-decode.log.")
    require(frame_count == FRAMES and not failures,
            f"Expected 9,000 complete frames with exact continuous PTS; count={frame_count}, failures={failures[:8]}")
    require(temporary_audio.stat().st_size % 8 == 0 and temporary_audio.stat().st_size >= 300*48000*8,
            "Decoded stereo 48 kHz audio is incomplete.")
    temporary_audio.replace(audio)
    overview = [(directory / f"overview-{i+1:03d}.jpg", i*150) for i in range(60)]
    native = [(directory / f"native-{i+1:03d}.png", n) for i, n in enumerate(NATIVE_FRAMES)]
    motion = [(directory / f"motion-{i+1:03d}.jpg", n) for i, n in enumerate(motion_frames)]
    for frames in (overview, native, motion):
        require(all(file.is_file() for file, _ in frames), "Missing final extracted review frames.")
        for file, n in frames:
            with Image.open(file) as frame:
                require(frame.size == (WIDTH, HEIGHT), f"Review frame has wrong size: {file.name}")
    require(len(list(directory.glob("overview-*.jpg"))) == len(overview)
            and len(list(directory.glob("native-*.png"))) == len(native)
            and len(list(directory.glob("motion-*.jpg"))) == len(motion), "Unexpected extra extracted frames.")
    contact_sheets(overview, "overview", directory)
    for name, start, end in WINDOWS:
        contact_sheets([(file, n) for file, n in motion if start*FPS <= n < end*FPS], name, directory)
    native_by_n = {n: file for file, n in native}
    boundary = frame_delta(native_by_n[8999], native_by_n[0])
    first_step = frame_delta(native_by_n[0], native_by_n[1])
    last_step = frame_delta(native_by_n[8998], native_by_n[8999])
    require(boundary < max(first_step, last_step)*2+2,
            "Encoded loop seam differs abnormally from ordinary neighboring frames.")
    contact_sheets([(native_by_n[n], n) for n in [8998, 8999, 0, 1]], "encoded-loop-seam", directory)
    return {"full_video_audio_decode_ok": True, "decoded_video_frames": frame_count,
            "exact_video_pts_grid_passed": True, "first_pts": first_pts, "last_pts": last_pts,
            "timebase": str(timebase), "decoded_audio_sample_frames": audio.stat().st_size//8,
            "overview_frames": len(overview), "nearpass_and_boundary_frames": len(motion),
            "native_frames": len(native), "encoded_visual_boundary_rms": boundary,
            "encoded_loop_edge_frames_pixel_identical": boundary == 0,
            "encoded_visual_ordinary_step_rms": [first_step, last_step],
            "audio_pcm_file": audio.name, "decoded_audio_pcm_sha256": sha256(audio),
            "decode_passes_started": 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--scene-check", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    options = parser.parse_args()
    video, scene_check, directory = options.video.resolve(), options.scene_check.resolve(), options.out_dir.resolve()
    sidecar = Path(str(video) + ".render.json")
    manifest = Path(str(video) + ".chunks") / "manifest.json"
    require(video.suffix == ".mp4" and ".partial" not in video.name, "Only a completed MP4 may be checked.")
    require(all(file.is_file() for file in (video, sidecar, scene_check, manifest)),
            "Wait for the complete MP4 and its final render receipt/checkpoints before checking.")
    require(not directory.exists() or not any(directory.iterdir()), "Use an empty QA output directory to prevent stale results.")
    initial_stat = video.stat()
    capture, scene, digest = validate_sources(video, sidecar, scene_check, manifest)
    metadata = probe(video)
    videos = [s for s in metadata["streams"] if s["codec_type"] == "video"]
    audios = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
    require(len(videos) == len(audios) == 1, "Expected one video and one audio stream.")
    v, a = videos[0], audios[0]
    require((v["width"], v["height"], v["r_frame_rate"], v["avg_frame_rate"], int(v["nb_frames"]))
            == (WIDTH, HEIGHT, "30/1", "30/1", FRAMES), "Unexpected encoded video format/frame count.")
    require(a["sample_rate"] == "48000" and a["channels"] == 2, "Expected 48 kHz stereo encoded audio.")
    require(abs(float(metadata["format"]["duration"])-DURATION) < .05
            and abs(float(v["duration"])-DURATION) < .05, "Expected exactly 300 seconds.")
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "metadata.json", metadata)
    decoded = decode_and_extract(video, directory)
    final_stat = video.stat()
    require((initial_stat.st_size, initial_stat.st_mtime_ns)
            == (final_stat.st_size, final_stat.st_mtime_ns), "Final MP4 changed during verification.")
    report = {"schema": "deep-sea-forward-render-qa-v1", "file": video.name,
              "sha256": digest, "bytes": video.stat().st_size, "duration_seconds": DURATION,
              "frames": FRAMES, "dimensions": [WIDTH, HEIGHT], "fps": "30/1",
              "source_scene_sha256": capture["source"]["scene_sha256"],
              "source_audio_sha256": capture["source"]["audio_sha256"],
              "source_forward_check_passed": scene["passed"],
              "source_endpoints_pixels_identical": scene["endpoints_pixels_identical"],
              "source_sample_hz": scene["sample_hz"], "source_check_limits": scene["limits"],
              "asset_generation_calls": capture["asset_generation_calls"],
              "paid_generation_calls": capture["paid_generation_calls"],
              "external_images": capture["external_images"], "algrow_calls": capture["algrow_calls"],
              "video_generation_calls": capture["video_generation_calls"],
              "video_technical_checks_passed": True, "audio_analysis_pending": True,
              "sampled_visual_review_completed": False, "human_continuous_viewing": False,
              "human_full_audio_listening": False, "artwork_approval_pending": True,
              "render_model": "Illustrated 2.5D projection with forward camera, not a complete 3D game world",
              **decoded}
    atomic_json(directory / "video-qa.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, RuntimeError) as error:
        print(f"Final forward-render check failed: {error}", file=sys.stderr)
        sys.exit(1)
