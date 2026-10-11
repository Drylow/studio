#!/usr/bin/env python3
"""Validate or prepare the authored Tommy/Alfie multi-source intermediate.

The default is read-only preflight. --prepare requires a new --out directory.
This creates native 720p scene media, not a final composition or upload. Source
review flags remain exactly as authored; decoding does not establish visual,
listening, final-render or platform clearance review.
"""

import argparse
import copy
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess


FPS = 30
DIMENSIONS = [1280, 720]
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TIMESTAMP_BUDGET = .0011  # Matroska timestamps are rounded to milliseconds.
FFMPEG = os.environ.get("CHESS_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("CHESS_FFPROBE", "ffprobe")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def frame_at(value, name):
    require(number(value), f"{name} must be a finite timestamp")
    frame = round(value * FPS)
    require(abs(value * FPS - frame) < 1e-6, f"{name} must be aligned to 30 fps")
    return frame


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def expected_sha(value, name):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            f"{name} needs a lowercase SHA256")
    return value


def load_json(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f"{path.name} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def repository_root():
    for path in Path(__file__).resolve().parents:
        if (path / "AGENTS.md").is_file() and (path / ".git").exists():
            return path
    raise ValueError("Could not discover the repository root from this helper")


def local_path(value, root):
    require(isinstance(value, str) and value and "://" not in value
            and not any(c in value for c in "\r\n\x00"), "Expected a local media path")
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve(strict=True)


def probe(path, frames=False):
    command = [FFPROBE, "-v", "error", "-show_streams", "-show_format"]
    if frames:
        command += ["-count_frames", "-show_frames", "-show_entries",
                    "frame=media_type,best_effort_timestamp_time,nb_samples"]
    result = subprocess.run(command + ["-of", "json", str(path)],
                            check=True, capture_output=True, text=True)
    require(not result.stderr.strip(), f"Media probing reported errors for {path.name}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def streams(info):
    videos = [s for s in info["streams"] if s.get("codec_type") == "video"]
    audios = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    require(len(videos) == 1 and len(audios) == 1,
            "Sources and intermediates must have exactly one video and one original audio track")
    return videos[0], audios[0]


def rate(value, name):
    try:
        result = Fraction(value)
    except (ValueError, TypeError, ZeroDivisionError) as error:
        raise ValueError(f"Invalid {name}: {value}") from error
    return result


def source_profile(info, definition, name):
    video, audio = streams(info)
    require([video.get("width"), video.get("height")] == DIMENSIONS
            and definition.get("dimensions") == DIMENSIONS,
            f"{name}: preserve the actual native 1280x720 dimensions")
    require(rate(video.get("r_frame_rate"), "source fps") == 25
            and rate(video.get("avg_frame_rate"), "source average fps") == 25
            and rate(definition.get("fps"), "authored source fps") == 25,
            f"{name}: expected native 25 fps source; no rate-change substitution")
    require(video.get("sample_aspect_ratio") == "1:1", f"{name}: source must use square pixels")
    require(video.get("field_order") in ("progressive", "unknown", None), f"{name}: interlaced source is unsupported")
    rotations = [video.get("tags", {}).get("rotate", 0)] + [
        s.get("rotation", 0) for s in video.get("side_data_list", [])]
    require(all(float(r) % 360 == 0 for r in rotations), f"{name}: source has unresolved display rotation")
    require(audio.get("sample_rate") == "48000" and audio.get("channels") == 2,
            f"{name}: expected original stereo 48 kHz audio; do not silently downmix")
    for key in ("color_space", "color_transfer", "color_primaries"):
        require(video.get(key) == "bt709", f"{name}: inconsistent original {key}")
    require(video.get("color_range") == "tv", f"{name}: inconsistent original color range")
    duration = float(info["format"]["duration"])
    require(math.isfinite(duration) and duration > 0, f"{name}: invalid source duration")
    authored_duration = definition.get("duration_seconds")
    require(number(authored_duration) and abs(duration - authored_duration) <= .002,
            f"{name}: measured source duration differs from the authored preflight")
    for track in (video, audio):
        require(abs(float(track.get("start_time", 0))) <= .002,
                f"{name}: source tracks do not start together at zero")
    return duration, min(float(s.get("duration", duration)) for s in (video, audio))


def validate_annotations(timeline, rows, frames, rating_schema):
    annotations = timeline.get("annotations")
    require(isinstance(annotations, list) and annotations, "An authored long needs annotations")
    by_id = {row["id"]: row for row in rows if row["kind"] == "source"}
    cards = [row for row in rows if row["kind"] == "chapter_card"]
    ratings = {r["id"]: r for r in rating_schema["categories"]}
    previous_frame, previous_score, previous_control = 0, 0.0, .5
    ids, holds, replay_checks = set(), 0, []
    for index, annotation in enumerate(annotations):
        require(isinstance(annotation, dict), f"Annotation {index} must be an object")
        identifier = annotation.get("id")
        require(isinstance(identifier, str) and identifier and identifier not in ids,
                "Annotation IDs must be nonempty and unique")
        ids.add(identifier)
        at = frame_at(annotation.get("source_at"), f"{identifier}.source_at")
        require(previous_frame < at < frames, f"{identifier}: annotations must increase inside the master")
        previous_frame = at
        row = by_id.get(annotation.get("source_fragment"))
        require(row is not None and row["master_in_frames"] <= at < row["master_out_frames"],
                f"{identifier}: annotation must lie in its retained source fragment")
        original = frame_at(annotation.get("original_source_at"), f"{identifier}.original_source_at")
        require(annotation.get("original_source_id") == row["source_id"]
                and original == frame_at(row["source_in"], "source_in") + at - row["master_in_frames"],
                f"{identifier}: source/master annotation coordinates disagree")
        hold = frame_at(annotation.get("hold_seconds"), f"{identifier}.hold_seconds")
        require(3 * FPS <= hold <= 9 * FPS, f"{identifier}: analysis hold must be 3–9 seconds")
        holds += hold
        replay = annotation.get("replay_seconds", 3)
        require(number(replay) and 2 <= replay <= 4, f"{identifier}: replay must be 2–4 seconds")
        replay_start = max(0, at - frame_at(replay, f"{identifier}.replay_seconds"))
        require(all(card["master_out_frames"] <= replay_start or card["master_in_frames"] >= at
                    for card in cards), f"{identifier}: replay overlaps a chapter card")
        replay_checks.append({"id": identifier, "source_in_frames": replay_start, "source_out_frames": at})
        speaker = annotation.get("speaker")
        require(speaker in ("white", "black") and annotation.get("player") ==
                ("tommy" if speaker == "white" else "alfie"), f"{identifier}: inconsistent fixed camps")
        rating = ratings.get(annotation.get("rating"))
        require(rating is not None, f"{identifier}: unknown rating")
        comment = annotation.get("comment")
        require(isinstance(comment, str) and comment.strip() and len(comment) <= 260,
                f"{identifier}: expected a nonempty comment of at most 260 characters")
        reading_minimum = (len(comment.encode("utf-16-le")) / 2 / rating_schema["typewriter_cps"]
                           + rating_schema["bubble_delay_seconds"] + rating_schema["minimum_reading_seconds"])
        require(hold / FPS + 1e-9 >= reading_minimum, f"{identifier}: insufficient typing/reading time")
        score_text, control = annotation.get("score_text"), annotation.get("control_after")
        require(isinstance(score_text, str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?", score_text),
                f"{identifier}: expected a numeric editorial score")
        score = float(score_text)
        require(math.isfinite(score) and number(control) and 0 <= control <= 1,
                f"{identifier}: invalid score/control")
        effect = rating["bar_effect"]
        if effect == "neutral":
            require(score == previous_score and abs(control - previous_control) <= 1e-7,
                    f"{identifier}: Best/Great must preserve the score and bar")
        else:
            gain = effect in ("gain", "small_gain")
            score_shift = (score - previous_score) * (1 if speaker == "white" else -1)
            bar_shift = (control - previous_control) * (-1 if speaker == "white" else 1)
            require((score_shift >= -1e-9 and bar_shift >= -1e-9) if gain
                    else (score_shift <= 1e-9 and bar_shift <= 1e-9),
                    f"{identifier}: score/bar movement contradicts this speaker's rating")
        previous_score, previous_control = score, control
        require(isinstance(annotation.get("reviewed"), bool), f"{identifier}: preserve an explicit review flag")
    return holds, replay_checks


def validate_plan(plan, timeline, root, timeline_path, source_meta):
    require(plan.get("schema") == "conversation-chess-multi-source-edit-v1"
            and timeline.get("schema") == "conversation-chess-clip-v1", "Unsupported plan/timeline schema")
    require(plan.get("fps") == FPS and plan.get("native_dimensions") == DIMENSIONS,
            "Plan must preserve native 1280x720 at a 30 fps master cadence")
    require(local_path(plan.get("timeline"), timeline_path.parent) == timeline_path,
            "--timeline does not match the timeline named by --plan")
    require("conversations" not in timeline, "This duel keeps one fixed global pair of camps")
    require(plan.get("first_speaker") == "Tommy" and all(
        document.get("white_label") == "Tommy" and document.get("black_label") == "Alfie"
        for document in (plan, timeline)), "Keep Tommy White and Alfie Black throughout this edit")
    require(timeline.get("initial_score_text") == "0.0" and timeline.get("initial_control") == .5,
            "The global conversation must start at score 0.0/control 0.5")
    opening = timeline.get("opening")
    require(isinstance(opening, dict) and opening == plan.get("opening")
            and opening.get("speaker") == "white" and opening.get("label") == "Tommy"
            and opening.get("source_at") == 0 and isinstance(opening.get("reviewed"), bool)
            and isinstance(opening.get("evidence"), str) and opening["evidence"].strip(),
            "Plan and timeline need the same explicit Tommy White-first opening evidence")
    require(plan.get("editorial_omissions_disclosed") is True, "Disclose the authored scene omissions")
    rows = plan.get("source_map")
    require(isinstance(rows, list) and len(rows) == 29, "Expected exactly 22 source cuts and 7 chapter cards")
    require(all(isinstance(row, dict) for row in rows), "Every source-map row must be an object")
    require(sum(row.get("kind") == "source" for row in rows) == 22
            and sum(row.get("kind") == "chapter_card" for row in rows) == 7,
            "Expected exactly 22 source cuts and 7 chapter cards")
    require(rows[0].get("kind") == rows[-1].get("kind") == "source",
            "The master must begin and end with retained source dialogue")
    cursor, identifiers, used_sources, previous_by_source = 0, set(), set(), {}
    for index, row in enumerate(rows):
        identifier, count = row.get("id"), row.get("duration_frames")
        require(isinstance(identifier, str) and identifier and identifier not in identifiers,
                "Source-map IDs must be nonempty and unique")
        identifiers.add(identifier)
        require(integer(count) and count > 0, f"{identifier}: expected a positive frame count")
        require(integer(row.get("master_in_frames")) and integer(row.get("master_out_frames"))
                and row["master_in_frames"] == cursor and row["master_out_frames"] == cursor + count,
                f"{identifier}: source-map rows must join contiguously with exclusive ends")
        cursor += count
        require(isinstance(row.get("reason"), str) and row["reason"].strip(),
                f"{identifier}: keep an explicit editorial reason")
        if row["kind"] == "chapter_card":
            title = row.get("title")
            require(FPS <= count <= 6 * FPS and isinstance(title, str) and title.strip()
                    and len(title) <= 60 and all(c.isprintable() for c in title),
                    f"{identifier}: chapter cards need a single-line title and an authored 1–6 second duration")
            require(index > 0 and rows[index - 1]["kind"] == "source"
                    and index + 1 < len(rows) and rows[index + 1]["kind"] == "source",
                    f"{identifier}: chapter cards must separate retained source cuts")
            continue
        source_id = row.get("source_id")
        require(source_id in source_meta, f"{identifier}: missing authored source definition")
        used_sources.add(source_id)
        source = source_meta[source_id]
        require(row.get("source_sha256") == source["sha256"]
                and local_path(row.get("source_file"), root) == source["path"],
                f"{identifier}: row does not match its exact original source")
        start, end = frame_at(row.get("source_in"), f"{identifier}.source_in"), frame_at(row.get("source_out"), f"{identifier}.source_out")
        require(0 <= start < end and end - start == count and end / FPS <= source["usable_duration"] + .001,
                f"{identifier}: source interval must match frames and remain inside both tracks")
        require(start >= previous_by_source.get(source_id, 0), f"{identifier}: source cuts must remain ordered without replaying dialogue")
        previous_by_source[source_id] = end
        if index and rows[index - 1]["kind"] == "source":
            require(rows[index - 1]["source_id"] == source_id,
                    f"{identifier}: episode changes require an explicit chapter card")
    require(used_sources == set(source_meta), "Every original source definition must be used")
    require(opening.get("actual_source_start") == rows[0]["source_in"]
            and opening.get("source_episode") == rows[0].get("episode"),
            "Opening evidence must identify the first retained source cut")
    require(integer(plan.get("master_duration_frames")) and cursor == plan["master_duration_frames"]
            and frame_at(plan.get("master_duration_seconds"), "master_duration_seconds") == cursor,
            "Authored master duration does not equal the joined frame count")
    require(timeline.get("source_in") == 0 and frame_at(timeline.get("source_out"), "timeline.source_out") == cursor,
            "Timeline must use the exact planned master coordinates")
    hashes = timeline.get("source_quality", {}).get("original_source_hashes")
    require(hashes == {name: source["sha256"] for name, source in source_meta.items()},
            "Timeline original-source hashes differ from the plan")
    require(timeline.get("analysis_background") == "replay", "This candidate expects muted replay backgrounds")
    rating_schema, _ = load_json(root / "experiments/conversation-chess/ratings.json")
    holds, replay_checks = validate_annotations(timeline, rows, cursor, rating_schema)
    intro, outro = frame_at(timeline.get("intro_seconds"), "intro_seconds"), frame_at(timeline.get("outro_seconds"), "outro_seconds")
    require(intro == 16 * FPS and 6 * FPS <= outro <= 20 * FPS, "Preserve the 16 second guide and authored recap")
    final_frames = cursor + intro + outro + holds
    require(600 * FPS <= final_frames <= 900 * FPS, "The authored final duration must be 10–15 minutes")
    return rows, cursor, final_frames, replay_checks


def find_font(explicit, bold=False):
    if explicit is not None:
        return explicit.resolve(strict=True)
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / filename
    require(path.is_file(), "Supply --font/--font-bold pointing to existing local fonts")
    return path.resolve()


def preflight(args):
    root = repository_root()
    plan_path, timeline_path = args.plan.resolve(strict=True), args.timeline.resolve(strict=True)
    plan, plan_sha = load_json(plan_path)
    timeline, timeline_sha = load_json(timeline_path)
    require(args.out is None or not (args.out.exists() or args.out.is_symlink()),
            "Choose a new unique --out directory; existing preparations are preserved")
    definitions = plan.get("sources")
    require(isinstance(definitions, dict) and set(definitions) == {"s02e02", "s02e06", "s03e06"},
            "Expected the three authored Peaky Blinders original sources")
    source_meta = {}
    for name, definition in definitions.items():
        require(isinstance(definition, dict), f"{name}: source definition must be an object")
        path = local_path(definition.get("file"), root)
        before = path.stat()
        wanted = expected_sha(definition.get("sha256"), name)
        measured = sha256(path)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                f"{name}: source changed during hashing")
        require(measured == wanted and definition.get("bytes") == after.st_size,
                f"{name}: exact source SHA256/byte count mismatch")
        info = probe(path)
        duration, usable_duration = source_profile(info, definition, name)
        source_meta[name] = {"path": path, "sha256": measured, "bytes": after.st_size,
                             "mtime_ns": after.st_mtime_ns, "duration": duration,
                             "usable_duration": usable_duration, "probe": info}
    rows, frames, final_frames, replays = validate_plan(plan, timeline, root, timeline_path, source_meta)
    assets = {}
    project_root = root / "experiments/conversation-chess"
    for slot, music in timeline.get("music", {}).items():
        require(isinstance(music, dict), f"music.{slot} must be an object")
        path = local_path(music.get("file"), project_root)
        wanted = expected_sha(music.get("sha256"), f"music.{slot}")
        require(sha256(path) == wanted, f"music.{slot}: SHA256 mismatch")
        assets["music." + slot] = {"file": str(path), "sha256": wanted}
    mascot = timeline.get("mascot", {})
    require(isinstance(mascot, dict), "mascot must identify an existing local asset")
    mascot_path = local_path(mascot.get("file"), project_root)
    mascot_sha = sha256(mascot_path)
    if "sha256" in mascot:
        require(mascot_sha == expected_sha(mascot["sha256"], "mascot"), "Mascot SHA256 mismatch")
    assets["mascot"] = {"file": str(mascot_path), "sha256": mascot_sha}
    regular, bold = find_font(args.font), find_font(args.font_bold, True)
    for executable in (FFMPEG, FFPROBE):
        subprocess.run([executable, "-version"], check=True, capture_output=True)
    encoders = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], check=True,
                              capture_output=True, text=True).stdout
    filters = subprocess.run([FFMPEG, "-hide_banner", "-filters"], check=True,
                             capture_output=True, text=True).stdout
    require(all(re.search(r"\b" + name + r"\b", encoders) for name in ("libx264", "pcm_s16le")),
            "FFmpeg must provide libx264 and pcm_s16le")
    require(all(re.search(r"\b" + name + r"\b", filters) for name in
                ("fps", "trim", "atrim", "aresample", "apad", "afade", "drawtext", "color", "anullsrc")),
            "FFmpeg is missing required local preparation filters")
    report = {"technical_preflight_valid": True, "media_written": False,
              "repository_root": str(root), "plan": str(plan_path), "plan_sha256": plan_sha,
              "timeline": str(timeline_path), "timeline_sha256": timeline_sha,
              "native_dimensions": DIMENSIONS, "source_fps": 25, "master_fps": FPS,
              "source_cut_count": 22, "chapter_card_count": 7, "annotation_count": len(timeline["annotations"]),
              "master_frames": frames, "master_seconds": frames / FPS,
              "final_expected_frames": final_frames, "final_expected_seconds": final_frames / FPS,
              "source_hashes": {name: s["sha256"] for name, s in source_meta.items()},
              "replay_ranges": replays, "referenced_assets": assets,
              "review_flags_inherited": {"source_reviewed": timeline.get("source_reviewed"),
                                         "accepted_for_final": timeline.get("source_quality", {}).get("accepted_for_final"),
                                         "opening_reviewed": timeline["opening"]["reviewed"],
                                         "annotation_reviewed": {a["id"]: a["reviewed"] for a in timeline["annotations"]}},
              "visual_or_listening_review_performed": False, "final_export_review_performed": False,
              "youtube_clearance_verified": False}
    return plan, timeline, rows, source_meta, regular, bold, report


def run_logged(command, path, cwd):
    with path.open("x", encoding="utf-8") as log:
        subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)


def write_json(path, data):
    with path.open("x", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")


def verify_intermediate(path, count):
    info = probe(path, frames=True)
    video, audio = streams(info)
    require(len(info["streams"]) == 2 and video.get("codec_name") == "h264"
            and audio.get("codec_name") == "pcm_s16le"
            and video.get("pix_fmt") == "yuv420p" and video.get("sample_aspect_ratio") == "1:1"
            and [video.get("width"), video.get("height")] == DIMENSIONS
            and rate(video.get("r_frame_rate"), "intermediate fps") == FPS
            and int(video.get("nb_read_frames", -1)) == count
            and audio.get("sample_rate") == "48000" and audio.get("channels") == 2,
            f"{path.name}: intermediate stream profile/frame count mismatch")
    require(abs(float(info["format"]["duration"]) - count / FPS) <= .002,
            f"{path.name}: intermediate duration drift")
    require(all(abs(float(s.get("start_time", 0))) <= TIMESTAMP_BUDGET for s in (video, audio)),
            f"{path.name}: tracks must start together at zero")
    picture_count, audio_samples = 0, 0
    for frame in info.pop("frames"):
        timestamp = float(frame["best_effort_timestamp_time"])
        if frame["media_type"] == "video":
            expected_time = picture_count / FPS
            picture_count += 1
        else:
            require(frame["media_type"] == "audio", "Unexpected decoded stream")
            expected_time = audio_samples / SAMPLE_RATE
            audio_samples += int(frame["nb_samples"])
        require(abs(timestamp - expected_time) <= TIMESTAMP_BUDGET,
                f"{path.name}: a decoded timestamp breaks the authored frame/sample cadence")
    require(picture_count == count and audio_samples == count * SAMPLES_PER_FRAME,
            f"{path.name}: decoded picture/audio sample totals disagree with the authored duration")
    info["decoded_counts"] = {"video_frames": picture_count, "audio_samples_per_channel": audio_samples,
                              "continuous_timestamps": True, "timestamp_budget_seconds": TIMESTAMP_BUDGET}
    return info


def encode_part(row, index, out, sources):
    parts = out / "parts"
    destination = parts / f"part-{index:02d}.mkv"
    count, duration = row["duration_frames"], row["duration_frames"] / FPS
    command = [FFMPEG, "-nostdin", "-hide_banner", "-v", "error", "-n", "-threads", "2"]
    if row["kind"] == "source":
        command += ["-ss", f'{row["source_in"]:.9f}', "-i", str(sources[row["source_id"]]["path"]),
                    "-map", "0:v:0", "-map", "0:a:0", "-vf",
                    f"fps=fps=30:start_time=0:round=near,trim=end_frame={count},setpts=N/(30*TB),setsar=1,format=yuv420p",
                    "-af", f"atrim=start=0,aresample=48000:first_pts=0,apad,atrim=end_sample={count * SAMPLES_PER_FRAME},"
                    f"asetpts=N/(48000*TB),afade=t=in:st=0:d=0.02,afade=t=out:st={duration - .02:.9f}:d=0.02"]
    else:
        titlefile = f"chapter-{index:02d}.txt"
        (out / titlefile).write_text(row["title"], encoding="utf-8")
        size = min(40, 1080 // max(len(row["title"]), 1))
        layers = ["drawtext=fontfile=chapter-regular.ttf:text='TOMMY / ALFIE':expansion=none:"
                  "fontsize=22:fontcolor=0xaaaaaa:x=(w-tw)/2:y=252",
                  f"drawtext=fontfile=chapter-bold.ttf:textfile={titlefile}:expansion=none:"
                  f"fontsize={size}:fontcolor=0xf2f2f2:x=(w-tw)/2:y=(h-th)/2", "setsar=1", "format=yuv420p"]
        command += ["-f", "lavfi", "-i", "color=c=0x202020:s=1280x720:r=30",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-map", "0:v:0", "-map", "1:a:0", "-vf",
                    f"trim=end_frame={count},setpts=N/(30*TB)," + ",".join(layers),
                    "-af", f"atrim=end_sample={count * SAMPLES_PER_FRAME},asetpts=N/(48000*TB)"]
    # Both filters end at exact frame/sample counts. -frames:v or a global -t
    # can stop muxing before the final PCM samples. Set the encoder time base
    # explicitly: a 25 fps input must not quantize the filtered 30 fps PTS to
    # its original cadence. Passthrough keeps the finite filter's timestamps;
    # adding -r would conflict with this mode on supported FFmpeg versions.
    command += ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-threads", "2",
                "-pix_fmt", "yuv420p", "-enc_time_base:v", "1:30", "-fps_mode:v", "passthrough", "-color_range", "tv",
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                "-c:a", "pcm_s16le", "-enc_time_base:a", "1:48000", "-ar", "48000", "-ac", "2", "-metadata:s:a:0", "language=eng",
                "-map_metadata", "-1", "-avoid_negative_ts", "disabled", str(destination)]
    run_logged(command, parts / f"part-{index:02d}.log", out)
    info = verify_intermediate(destination, count)
    print(json.dumps({"prepared_part": index + 1, "total_parts": 29, "id": row["id"], "frames": count}), flush=True)
    return {"index": index, "id": row["id"], "path": str(destination), "frames": count,
            "sha256": sha256(destination), "bytes": destination.stat().st_size, "probe": info}


def concatenate_parts(concat, master, out):
    # Matroska's millisecond ticks can advertise avg_frame_rate=1000/33 even
    # when decoded PTS follow exact 30 fps within one mux tick. Specify the
    # already-verified picture cadence for the stream-copy muxer; this does not
    # resample or stop either stream. verify_intermediate checks actual PTS.
    run_logged([FFMPEG, "-nostdin", "-hide_banner", "-v", "error", "-n", "-f", "concat", "-safe", "1",
                "-i", str(concat), "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "-r:v", str(FPS),
                "-map_metadata", "-1", "-metadata:s:a:0", "language=eng", "-avoid_negative_ts", "disabled", str(master)],
               out / "concatenate.log", out)


def prepare(args, state):
    plan, timeline, rows, sources, regular, bold, report = state
    out = args.out.resolve()
    # Revalidate exact authored JSON immediately before the first write.
    require(sha256(args.plan.resolve()) == report["plan_sha256"]
            and sha256(args.timeline.resolve()) == report["timeline_sha256"],
            "Plan/timeline changed after preflight; run preflight again")
    out.mkdir(parents=True, exist_ok=False)
    (out / "parts").mkdir()
    shutil.copyfile(regular, out / "chapter-regular.ttf")
    shutil.copyfile(bold, out / "chapter-bold.ttf")
    write_json(out / "preflight.json", report)
    parts = [encode_part(row, index, out, sources) for index, row in enumerate(rows)]
    concat = out / "parts.ffconcat"
    with concat.open("x", encoding="utf-8") as output:
        output.write("ffconcat version 1.0\n")
        for index, row in enumerate(rows):
            output.write(f"file 'parts/part-{index:02d}.mkv'\nduration {row['duration_frames'] / FPS:.9f}\n")
    master = out / "source-master-1280x720-30fps.mkv"
    concatenate_parts(concat, master, out)
    run_logged([FFMPEG, "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-threads", "2",
                "-i", str(master), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
               out / "full-video-audio-decode.log", out)
    info = verify_intermediate(master, report["master_frames"])
    for name, source in sources.items():
        require(sha256(source["path"]) == source["sha256"], f"{name}: original source changed during preparation")
    require(sha256(args.plan.resolve()) == report["plan_sha256"]
            and sha256(args.timeline.resolve()) == report["timeline_sha256"],
            "Plan/timeline changed during preparation; no remapped timeline will be certified")
    master_sha = sha256(master)
    source_edit = {"schema": "conversation-chess-prepared-multi-source-edit-v1",
                   "plan_file": report["plan"], "plan_sha256": report["plan_sha256"],
                   "authored_timeline_file": report["timeline"], "authored_timeline_sha256": report["timeline_sha256"],
                   "original_source_hashes": report["source_hashes"], "native_dimensions": DIMENSIONS,
                   "source_fps": 25, "master_fps": FPS, "speed_change": False, "source_media_upscaled": False,
                   "source_map": copy.deepcopy(rows), "master_sha256": master_sha,
                   "master_frames": report["master_frames"], "audio_samples_per_channel": report["master_frames"] * SAMPLES_PER_FRAME,
                   "audio": "Original stereo 48 kHz dialogue decoded to PCM s16le; 20 ms cut-edge fades; silent authored chapter cards",
                   "recipe": "Native H264 CRF16 MKV/PCM parts, fps=30 cadence conversion, exact frame/sample trims, concatenation by stream copy",
                   "technical_full_video_audio_decode_ok": True, "technical_continuous_timestamps_ok": True,
                   "master_visual_review_performed": False, "master_boundary_listening_performed": False,
                   "final_export_review_performed": False, "youtube_clearance_verified": False,
                   "review_note": "Inherited source/annotation review flags describe only the authored source evidence. No new visual, listening or final-render review is inferred from preparation."}
    remapped = copy.deepcopy(timeline)
    remapped.update(source_sha256=master_sha, source_in=0, source_out=report["master_frames"] / FPS,
                    source_edit=source_edit,
                    source_edit_status="Intermediate prepared and technically decoded. Review evidence is inherited; master/final visual and listening review remain separate.")
    timeline_out = out / "timeline.json"
    write_json(timeline_out, remapped)
    manifest = {"schema": "conversation-chess-native-multi-source-master-v1", "master": str(master),
                "sha256": master_sha, "bytes": master.stat().st_size, "fps": FPS, "frames": report["master_frames"],
                "duration_seconds": report["master_seconds"], "native_dimensions": DIMENSIONS,
                "timeline": str(timeline_out), "timeline_sha256": sha256(timeline_out),
                "final_expected_frames": report["final_expected_frames"], "final_expected_seconds": report["final_expected_seconds"],
                "full_video_audio_decode_ok": True, "probe": info, "parts": parts,
                "source_edit": source_edit, "review_flags_inherited": report["review_flags_inherited"],
                "final_export_review_performed": False, "youtube_clearance_verified": False}
    write_json(out / "source-master-manifest.json", manifest)
    return {"technical_preparation_valid": True, "media_written": True, "source": str(master), "source_sha256": master_sha,
            "timeline": str(timeline_out), "manifest": str(out / "source-master-manifest.json"),
            "master_frames": report["master_frames"], "master_seconds": report["master_seconds"],
            "final_expected_frames": report["final_expected_frames"], "final_expected_seconds": report["final_expected_seconds"],
            "final_export_review_performed": False, "youtube_clearance_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="Explicit authored source-map JSON")
    parser.add_argument("--timeline", type=Path, required=True, help="Explicit authored timeline JSON named by the plan")
    parser.add_argument("--prepare", action="store_true", help="Prepare source media after the read-only preflight passes")
    parser.add_argument("--out", type=Path, help="New unique output directory; required only with --prepare")
    parser.add_argument("--font", type=Path, help="Existing local regular chapter font")
    parser.add_argument("--font-bold", type=Path, help="Existing local bold chapter font")
    args = parser.parse_args()
    if args.prepare and args.out is None:
        parser.error("--prepare requires --out pointing to a new unique directory")
    try:
        state = preflight(args)
        result = prepare(args, state) if args.prepare else state[-1]
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
