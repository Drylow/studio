#!/usr/bin/env python3
"""Prepare reviewed scene media and original chapter cards for a native edit.

This is source-media preparation, not final composition. The separate renderer
and Kdenlive exporter retain their source-quality and editorial review gates.
All episode media must already be local; this helper performs no downloads.
"""

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
from fractions import Fraction
import re
import shutil
import subprocess
import time


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def probe(path, count=False):
    command = [os.environ.get("CHESS_FFPROBE", "ffprobe"), "-v", "error"]
    if count:
        command += ["-count_frames"]
    command += ["-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def run(command, log, cwd):
    with log.open("w", encoding="utf-8") as output:
        subprocess.run(command, cwd=cwd, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def local_basename(value):
    """Resolve a portable local filename, never a URL or signed source."""
    if not isinstance(value, str) or not value or "://" in value or any(c in value for c in "\n\r\x00"):
        raise ValueError("Source media must use a local filename")
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def prepare_rows(data, source_root):
    rows = data.get("source_map", data.get("rows"))
    if not isinstance(rows, list) or not rows or data.get("master_fps") != 30:
        raise ValueError("Expected a nonempty source_map at master_fps=30")
    source_defs = data.get("sources", {})
    cache = {}
    offset = 0
    dimensions = None
    for row in rows:
        if row.get("kind") not in ("source", "chapter_card"):
            raise ValueError("Unknown source-map row kind")
        frames = row.get("duration_frames")
        if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
            raise ValueError("Every row needs a positive integer duration_frames")
        if row.get("master_in_frames") != offset or row.get("master_out_frames") != offset + frames:
            raise ValueError("Source-map rows must be contiguous and end-exclusive")
        offset += frames
        if row["kind"] == "chapter_card":
            if not isinstance(row.get("title"), str) or not row["title"].strip():
                raise ValueError("A chapter card needs a title")
            continue
        start, end = row.get("source_in"), row.get("source_out")
        if (isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start):
            raise ValueError("A source row needs increasing source_in/source_out seconds")
        if abs((end-start)*30 - frames) > 1:
            raise ValueError("Source duration differs from its planned frame count")
        definition = source_defs.get(row.get("source_id", row.get("episode")), {})
        if not definition and row.get("episode", "").startswith("S02E"):
            definition = source_defs.get(row["episode"][-2:], {})
        value = row.get("file") or row.get("filename") or definition.get("filename") or definition.get("file")
        if not value:
            episode = row.get("episode", "").lower()
            if not episode or any(c not in "s0123456789e" for c in episode):
                raise ValueError("No local source filename could be resolved")
            value = f"the-sopranos-{episode}-english-acquired.mp4"
        filename = local_basename(value)
        path = (source_root / filename).resolve(strict=True)
        if path.parent != source_root:
            raise ValueError("Source filename escapes source-root")
        if filename not in cache:
            info = probe(path)
            video = next(s for s in info["streams"] if s["codec_type"] == "video")
            audios = [s for s in info["streams"] if s["codec_type"] == "audio"]
            shape = [video["width"], video["height"]]
            if not audios or shape not in ([1280, 720], [1920, 1080], [2560, 1440], [3840, 2160]):
                raise ValueError("Preparation requires a native HD video with original dialogue audio")
            if dimensions is not None and dimensions != shape:
                raise ValueError("Sources have different dimensions; no automatic resizing is allowed")
            dimensions = shape
            language = audios[0].get("tags", {}).get("language", "und").lower()
            if not re.fullmatch(r"[a-z]{3}", language):
                language = "und"
            cache[filename] = {"path": path, "sha256": digest(path), "probe": info,
                               "dimensions": shape, "audio_language": language}
        expected = row.get("source_sha256") or definition.get("sha256")
        if expected and expected != cache[filename]["sha256"]:
            raise ValueError(f"Original-source checksum mismatch: {filename}")
        if end > float(cache[filename]["probe"]["format"]["duration"]) + .05:
            raise ValueError(f"Cut extends beyond original source: {filename}")
        row["file"] = filename
        row["source_sha256"] = cache[filename]["sha256"]
    if offset != data.get("master_duration_frames") or dimensions is None:
        raise ValueError("Source-map total or video dimensions are missing")
    return rows, cache, dimensions, offset


def find_font(explicit, bold=False):
    if explicit:
        return explicit.resolve(strict=True)
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    windows = "arialbd.ttf" if bold else "arial.ttf"
    candidates = [Path("/usr/share/fonts/truetype/dejavu") / name,
                  Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / windows,
                  Path("/System/Library/Fonts/Supplemental") / ("Arial Bold.ttf" if bold else "Arial.ttf")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError("No chapter font found; pass --font and --font-bold")


def encode_row(row, index, out, source_root, dimensions, heading):
    started = time.monotonic()
    identifier = row.get("id", row.get("chapter", f"row-{index}"))
    # Use a fixed prefix and index: user-provided labels never become paths.
    destination = out / f"part-{index:02d}.mkv"
    state = destination.with_suffix(".state.json")
    signature = {k: row.get(k) for k in ("kind", "title", "source_sha256", "source_in", "source_out", "duration_frames")}
    signature.update({"dimensions": dimensions, "heading": heading, "recipe": "native-pcm-v1"})
    if destination.exists() and state.exists() and json.loads(state.read_text(encoding="utf-8")).get("signature") == signature:
        previous = probe(destination, True)
        video = next(s for s in previous["streams"] if s["codec_type"] == "video")
        if int(video.get("nb_read_frames", -1)) == row["duration_frames"]:
            return {"index": index, "path": str(destination), "seconds": 0, "reused": True}
    count = row["duration_frames"]
    duration = count / 30
    command = [os.environ.get("CHESS_FFMPEG", "ffmpeg"), "-hide_banner", "-v", "error", "-y", "-threads", "2"]
    if row["kind"] == "source":
        command += ["-ss", str(row["source_in"]), "-i", str(source_root / row["file"]), "-map", "0:v:0", "-map", "0:a:0",
                    "-vf", f"fps=30,trim=end_frame={count},setpts=PTS-STARTPTS,setsar=1,format=yuv420p",
                    "-af", f"atrim=duration={duration:.9f},asetpts=PTS-STARTPTS,aresample=48000,apad=whole_dur={duration:.9f},atrim=duration={duration:.9f}"]
    else:
        title = f"chapter-{index:02d}.txt"
        (out / title).write_text(row["title"], encoding="utf-8")
        width, height = dimensions
        scale = height / 720
        layers = [
            f"drawbox=x={round(140*scale)}:y={round(190*scale)}:w={round(1000*scale)}:h={round(340*scale)}:color=0x22271f:t=fill",
            f"drawbox=x={round(190*scale)}:y={round(235*scale)}:w={round(64*scale)}:h={max(1,round(4*scale))}:color=0x81b64c:t=fill",
            f"drawbox=x={round(1026*scale)}:y={round(481*scale)}:w={round(64*scale)}:h={max(1,round(4*scale))}:color=0x81b64c:t=fill",
            f"drawtext=fontfile=chapter-regular.ttf:textfile=chapter-heading.txt:fontsize={round(22*scale)}:fontcolor=0xb6b9af:x=(w-tw)/2:y={round(275*scale)}",
            f"drawtext=fontfile=chapter-bold.ttf:textfile={title}:fontsize={round(39*scale)}:fontcolor=0xf1eee7:x=(w-tw)/2:y=(h-th)/2+{round(8*scale)}",
            "fade=t=in:st=0:d=0.18", f"fade=t=out:st={max(0,duration-.18):.9f}:d=0.18", "setsar=1,format=yuv420p",
        ]
        command += ["-f", "lavfi", "-i", f"color=c=0x151714:s={width}x{height}:r=30", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-map", "0:v:0", "-map", "1:a:0", "-vf", ",".join(layers)]
    command += ["-frames:v", str(count), "-t", f"{duration:.9f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-threads", "2", "-c:a", "pcm_s16le", "-ac", "2", "-ar", "48000", str(destination)]
    run(command, destination.with_suffix(".log"), out)
    info = probe(destination, True)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    if int(video.get("nb_read_frames", -1)) != count or [video["width"], video["height"]] != dimensions:
        raise ValueError("Prepared fragment frame count or native dimensions changed")
    elapsed = time.monotonic() - started
    state.write_text(json.dumps({"signature": signature, "encoding_seconds": elapsed, "probe": info}, indent=2), encoding="utf-8")
    print(json.dumps({"part": index, "id": identifier, "frames": count, "seconds": round(elapsed, 2)}), flush=True)
    return {"index": index, "path": str(destination), "seconds": elapsed, "reused": False}


def check_master_profile(info, frames, dimensions):
    """Check the measured media profile without assuming nominal fps is exact."""
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    # Matroska intermediates have millisecond timestamps. Check their absolute
    # timestamp rounding budget, rather than a fps tolerance that incorrectly
    # rejects short clips. ffprobe prints duration with six decimal places.
    video_duration = float(video.get("duration", 0))
    format_duration = float(info["format"].get("duration", 0))
    average_rate = float(Fraction(video.get("avg_frame_rate", "0/1")))
    rate_precision_budget = abs(average_rate) * .0000005 / max(video_duration-.0000005, .0000005) + 1e-9
    if (len(info["streams"]) != 2 or int(video.get("nb_read_frames", -1)) != frames
            or [video["width"], video["height"]] != dimensions
            or video.get("codec_name") != "h264" or audio.get("codec_name") != "aac"
            or Fraction(video.get("r_frame_rate", "0/1")) != 30
            or not math.isfinite(video_duration) or video_duration <= 0
            or not math.isfinite(format_duration) or not math.isfinite(average_rate)
            or abs(video_duration - frames/30) > .003
            or abs(format_duration - frames/30) > .003
            or abs(average_rate - frames/max(video_duration, .0000005)) > rate_precision_budget
            or audio.get("sample_rate") != "48000" or audio.get("channels") != 2):
        raise ValueError("Master stream, frame-count, dimension, or audio checks failed")
    return info


def validate_master(master, frames, dimensions, out):
    info = check_master_profile(probe(master, True), frames, dimensions)
    run([os.environ.get("CHESS_FFMPEG", "ffmpeg"), "-hide_banner", "-v", "error", "-xerror", "-threads", "2", "-i", str(master),
         "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], out / "full-decode.log", out)
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--heading", default="TONY vs RICHIE")
    parser.add_argument("--audio-language", help="Optional ISO 639-2 code, such as eng; defaults to original audio tags or und")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-bold", type=Path)
    parser.add_argument("--verify-only", action="store_true", help="Recheck an existing source-master-manifest.json and MP4 without reencoding")
    args = parser.parse_args()
    started = time.monotonic()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_root = args.source_root.resolve(strict=True)
    data = json.loads(args.source_map.read_text(encoding="utf-8"))
    rows, sources, dimensions, frames = prepare_rows(data, source_root)
    languages = {entry["audio_language"] for entry in sources.values()}
    language = args.audio_language or (next(iter(languages)) if len(languages) == 1 else "und")
    if not re.fullmatch(r"[a-z]{3}", language):
        raise ValueError("--audio-language must be a three-letter ISO 639-2 code")
    manifest_path = out / "source-master-manifest.json"
    parts = []
    previous = None
    if args.verify_only:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        parts = previous.get("parts", [])
        master = out / local_basename(previous["master"])
        fields = ("kind", "id", "title", "source_in", "source_out", "source_sha256", "duration_frames", "master_in_frames", "master_out_frames")
        planned = [{key: row.get(key) for key in fields} for row in rows]
        recorded = [{key: row.get(key) for key in fields} for row in previous.get("source_map", [])]
        if (previous.get("frames") != frames or previous.get("native_source_dimensions") != dimensions
                or planned != recorded or digest(master) != previous.get("sha256")):
            raise ValueError("Existing master does not match its reviewed receipt")
    else:
        shutil.copyfile(find_font(args.font), out / "chapter-regular.ttf")
        shutil.copyfile(find_font(args.font_bold, True), out / "chapter-bold.ttf")
        (out / "chapter-heading.txt").write_text(args.heading, encoding="utf-8")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(encode_row, row, i, out, source_root, dimensions, args.heading) for i, row in enumerate(rows)]
            for future in concurrent.futures.as_completed(futures):
                parts.append(future.result())
        parts.sort(key=lambda item: item["index"])
        concat = out / "concat.ffconcat"
        concat.write_text("ffconcat version 1.0\n" + "".join(
            f"file '{Path(part['path']).name}'\nduration {rows[part['index']]['duration_frames']/30:.9f}\n" for part in parts), encoding="utf-8")
        master = out / f"source-master-native{dimensions[1]}p30.mp4"
        if master.resolve() in [entry["path"] for entry in sources.values()]:
            raise ValueError("Output master would overwrite an original source")
        run([os.environ.get("CHESS_FFMPEG", "ffmpeg"), "-hide_banner", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
             "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-metadata:s:a:0", f"language={language}", "-video_track_timescale", "90000", "-movflags", "+faststart", str(master)], out / "concat.log", out)
    info = validate_master(master, frames, dimensions, out)
    elapsed = time.monotonic()-started
    manifest = {"schema": "conversation-chess-native-source-master-v1", "master": str(master), "sha256": digest(master),
                "bytes": master.stat().st_size, "fps": 30, "frames": frames, "duration_seconds": frames/30,
                "native_source_dimensions": dimensions, "source_media_upscaled": False,
                "audio": "Original dialogue; stereo 48 kHz; PCM intermediates and one AAC encode",
                "subtitle_streams": 0, "added_watermarks": False, "full_video_audio_decode_ok": True,
                "final_composition_software": "Kdenlive/MLT, performed separately", "source_map": rows,
                "original_sources": {name: {"sha256": entry["sha256"], "native_dimensions": entry["dimensions"], "audio_language": entry["audio_language"]} for name, entry in sources.items()},
                "probe": info, "preparation_seconds": previous.get("preparation_seconds", elapsed) if previous else elapsed,
                "last_validation_seconds": elapsed, "parts": parts,
                "verification_only": args.verify_only}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("master", "sha256", "bytes", "frames", "duration_seconds", "preparation_seconds", "verification_only")}), flush=True)


if __name__ == "__main__":
    main()
