#!/usr/bin/env python3
"""Build a portable, editable Kdenlive timeline and export with Kdenlive.

Input is the separate-media manifest produced by render-clip.mjs --prepare-project.
The final export is performed by Kdenlive, never by an ffmpeg assembly command.
Qt/MLT alpha compositing needs a real X11/Wayland display, including an Xvfb one.
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
import uuid
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def props(node, values):
    for name, value in values.items():
        ET.SubElement(node, "property", name=name).text = str(value)


def smpte(frames, fps):
    seconds, remainder = divmod(frames, fps)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}:{remainder:02}"


def generate(manifest_path, bundle):
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != "conversation-chess-kdenlive-interchange-v1":
        raise ValueError("Expected the separate-media conversation-chess manifest")
    fps = int(data["fps"])
    if fps != 30 or int(data["width"]) != 1920 or int(data["height"]) != 1080:
        raise ValueError("This project requires the reviewed 1920x1080, 30fps preparation")
    total = int(data["duration_frames"])
    segments = data["segments"]
    cursor = 0
    for segment in segments:
        start, end = int(segment["start_frame"]), int(segment["end_frame"])
        if start != cursor or end <= start:
            raise ValueError("Manifest boundaries must be contiguous, positive, and end-exclusive")
        if int(segment["duration_frames"]) != end - start:
            raise ValueError("Inconsistent frame count in manifest")
        if segment.get("kind") not in ("intro", "source", "analysis"):
            raise ValueError("Unknown timeline segment kind")
        if segment["kind"] == "source" and not segment.get("dialogue_audio_file"):
            raise ValueError("A source segment must preserve its original dialogue track")
        cursor = end
    if cursor != total:
        raise ValueError("Timeline does not end at duration_frames")
    if data.get("voiceover") is not False:
        raise ValueError("The reviewed pilot forbids additional voiceover")
    original = Path(data["original_source"]).resolve(strict=True)
    source_probe = probe(original)
    video = next(s for s in source_probe["streams"] if s["codec_type"] == "video")
    if int(video["height"]) < 720:
        raise ValueError("A genuine source of at least 720p is required")
    source_hash = digest(original)
    if source_hash != data["source_sha256"]:
        raise ValueError("Source SHA256 differs from the reviewed manifest")

    bundle.mkdir(parents=True, exist_ok=True)
    media = bundle / "media"
    media.mkdir(exist_ok=True)
    sequence_uuid = "{" + str(uuid.uuid4()) + "}"
    root = ET.Element("mlt", {
        "LC_NUMERIC": "C", "producer": "main_bin", "root": str(bundle), "version": "7.30.0",
    })
    ET.SubElement(root, "profile", {
        "colorspace": "709", "description": "HD 1080p 30 fps", "display_aspect_den": "9",
        "display_aspect_num": "16", "frame_rate_den": "1", "frame_rate_num": str(fps),
        "height": "1080", "progressive": "1", "sample_aspect_den": "1",
        "sample_aspect_num": "1", "width": "1920",
    })
    black = ET.SubElement(root, "producer", id="black", **{"in": "0", "out": str(total - 1)})
    props(black, {
        "length": total, "eof": "pause", "resource": "black", "aspect_ratio": 1,
        "mlt_service": "color", "kdenlive:playlistid": "black_track", "mlt_image_format": "rgba",
        "set.test_audio": 0,
    })
    copied, assets, registered = {}, [], {}

    def asset(path_string, role, needed_frames, label):
        path = Path(path_string).resolve(strict=True)
        key = (str(path), role)
        if key in registered:
            identity = registered[key]
            row = next(item for item in assets if item["producer"] == identity)
            if needed_frames > row["frames"]:
                producer = root.find(f"producer[@id='{identity}']")
                producer.set("out", str(needed_frames - 1))
                producer.find("property[@name='length']").text = str(needed_frames)
                producer.find("property[@name='kdenlive:duration']").text = smpte(needed_frames, fps)
                row["frames"] = needed_frames
            return identity
        sha = digest(path)
        if str(path) not in copied:
            filename = f"{path.stem}-{sha[:12]}{path.suffix}"
            destination = media / filename
            if not destination.exists() or digest(destination) != sha:
                temporary = destination.with_suffix(destination.suffix + ".copying")
                shutil.copy2(path, temporary)
                temporary.replace(destination)
            copied[str(path)] = "media/" + filename
        resource = copied[str(path)]
        identity = "clip" + str(len(assets) + 10)
        bin_id = str(len(assets) + 10)
        image = path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg")
        info = probe(path) if not image else None
        streams = info.get("streams", []) if info else []
        stream_duration = float(info.get("format", {}).get("duration", 0)) if info else 0
        length = max(needed_frames, math.ceil(stream_duration * fps), 1)
        producer = ET.SubElement(root, "producer", id=identity, **{"in": "0", "out": str(length - 1)})
        video_index = next((s["index"] for s in streams if s["codec_type"] == "video"), -1)
        audio_index = next((s["index"] for s in streams if s["codec_type"] == "audio"), -1)
        values = {
            "resource": resource, "mlt_service": "qimage" if image else "avformat",
            "length": length, "eof": "pause", "kdenlive:id": bin_id,
            "kdenlive:clipname": label, "kdenlive:folderid": 3, "kdenlive:proxy": "-",
            "kdenlive:duration": smpte(length, fps), "kdenlive:file_size": path.stat().st_size,
            "seekable": 1, "threads": 2,
        }
        if role == "audio":
            values.update({"audio_index": audio_index, "video_index": -1, "set.test_image": 1})
        elif role == "video":
            values.update({"audio_index": -1, "video_index": 0 if image else video_index,
                           "set.test_audio": 1, "mlt_image_format": "rgba"})
        if image:
            values.update({"ttl": 1, "loop": 1})
        props(producer, values)
        row = {"producer": identity, "bin_id": bin_id, "resource": resource,
               "original_path": str(path), "sha256": sha, "role": role, "frames": length}
        assets.append(row)
        registered[key] = identity
        return identity

    asset(str(original), "original", math.ceil(float(source_probe["format"]["duration"]) * fps), "Original HD source")
    # Native Kdenlive audio tracks precede video tracks in the MLT multitrack.
    track_specs = [
        ("A2 — Analysis SFX", "audio"), ("A1 — Original dialogue", "audio"),
        ("V1 — Source / intro background", "video"), ("V2 — Muted slow replays", "video"),
        ("V3 — Intro / bar / rating / mascot", "video"),
    ]
    track_entries = [[] for _ in track_specs]
    for index, segment in enumerate(segments):
        start, length = int(segment["start_frame"]), int(segment["duration_frames"])
        kind = segment["kind"]
        title = f"{index + 1:02} {kind}"
        background_track = 3 if kind == "analysis" else 2
        background = asset(segment["background_file"], "video", length, title + " — background")
        track_entries[background_track].append((start, length, background))
        graphic = asset(segment["graphics_file"], "video", length, title + " — graphics")
        track_entries[4].append((start, length, graphic))
        if segment.get("dialogue_audio_file"):
            if kind != "source":
                raise ValueError("Original dialogue must only occur in source segments")
            sound = asset(segment["dialogue_audio_file"], "audio", length, title + " — dialogue")
            track_entries[1].append((start, length, sound))
        if segment.get("sfx_file"):
            if kind != "analysis":
                raise ValueError("Analysis SFX must not overlap original dialogue segments")
            sound = asset(segment["sfx_file"], "audio", length, title + " — SFX")
            track_entries[0].append((start, length, sound))

    for index, ((name, kind), entries) in enumerate(zip(track_specs, track_entries)):
        playlists = []
        for layer in range(2):
            playlist_id = f"playlist_{index}_{layer}"
            playlist = ET.SubElement(root, "playlist", id=playlist_id)
            if kind == "audio":
                props(playlist, {"kdenlive:audio_track": 1})
            if layer == 0:
                end = 0
                for start, length, identity in entries:
                    if start < end:
                        raise ValueError("Overlapping clips in an individual native track")
                    if start > end:
                        ET.SubElement(playlist, "blank", length=str(start - end))
                    ET.SubElement(playlist, "entry", producer=identity, **{"in": "0", "out": str(length - 1)})
                    end = start + length
                if end < total:
                    ET.SubElement(playlist, "blank", length=str(total - end))
            playlists.append(playlist_id)
        tractor = ET.SubElement(root, "tractor", id=f"track_{index}", **{"in": "0", "out": str(total - 1)})
        values = {"kdenlive:track_name": name, "kdenlive:trackheight": 75,
                  "kdenlive:timeline_active": 1, "kdenlive:collapsed": 0,
                  "kdenlive:thumbs_format": "", "kdenlive:audio_rec": ""}
        if kind == "audio":
            values["kdenlive:audio_track"] = 1
        props(tractor, values)
        for identity in playlists:
            ET.SubElement(tractor, "track", producer=identity, hide="video" if kind == "audio" else "audio")

    sequence = ET.SubElement(root, "tractor", id=sequence_uuid, **{"in": "0", "out": str(total - 1)})
    props(sequence, {
        "kdenlive:uuid": sequence_uuid, "kdenlive:control_uuid": sequence_uuid,
        "kdenlive:clipname": "Tony / Janice — conversation review", "kdenlive:id": 1,
        "kdenlive:producer_type": 17, "kdenlive:folderid": 2,
        "kdenlive:duration": smpte(total, fps), "kdenlive:maxduration": total,
        "kdenlive:sequenceproperties.documentuuid": sequence_uuid,
        "kdenlive:sequenceproperties.hasAudio": 1, "kdenlive:sequenceproperties.hasVideo": 1,
        "kdenlive:sequenceproperties.tracksCount": 5, "kdenlive:sequenceproperties.tracks": 5,
        "kdenlive:sequenceproperties.activeTrack": 4, "kdenlive:sequenceproperties.audioTarget": 1,
        "kdenlive:sequenceproperties.videoTarget": 2, "kdenlive:sequenceproperties.position": 480,
        "kdenlive:sequenceproperties.zonein": 0, "kdenlive:sequenceproperties.zoneout": total,
        "kdenlive:sequenceproperties.zoom": 4, "kdenlive:sequenceproperties.scrollPos": 0,
        "kdenlive:sequenceproperties.verticalzoom": 1, "kdenlive:sequenceproperties.disablepreview": 0,
        "kdenlive:sequenceproperties.groups": "[]", "kdenlive:sequenceproperties.guides": "[]",
    })
    ET.SubElement(sequence, "track", producer="black", **{"in": "0", "out": str(total - 1)})
    for index, (_, kind) in enumerate(track_specs, start=1):
        ET.SubElement(sequence, "track", producer=f"track_{index - 1}")
        transition = ET.SubElement(sequence, "transition", id=f"transition_{index}")
        common = {"a_track": 0, "b_track": index, "internal_added": 237, "always_active": 1}
        if kind == "audio":
            common.update({"mlt_service": "mix", "kdenlive_id": "mix", "accepts_blanks": 1, "sum": 1})
        else:
            common.update({"mlt_service": "qtblend", "kdenlive_id": "qtblend", "compositing": 0,
                           "distort": 0, "rotate_center": 0})
        props(transition, common)

    main_bin = ET.SubElement(root, "playlist", id="main_bin")
    props(main_bin, {
        "kdenlive:folder.-1.2": "Sequences", "kdenlive:sequenceFolder": 2,
        "kdenlive:folder.-1.3": "Prepared media", "kdenlive:docproperties.audioChannels": 2,
        "kdenlive:docproperties.documentid": int(time.time() * 1000),
        "kdenlive:docproperties.kdenliveversion": "24.12.3", "kdenlive:docproperties.version": "1.1",
        "kdenlive:docproperties.profile": "atsc_1080p_30", "kdenlive:docproperties.uuid": sequence_uuid,
        "kdenlive:docproperties.opensequences": sequence_uuid,
        "kdenlive:docproperties.activetimeline": sequence_uuid,
        "kdenlive:docproperties.sessionid": "{" + str(uuid.uuid4()) + "}",
        "kdenlive:docproperties.enableproxy": 0, "kdenlive:docproperties.enableexternalproxy": 0,
        "kdenlive:docproperties.generateproxy": 0, "kdenlive:docproperties.generateimageproxy": 0,
        "kdenlive:docproperties.enableTimelineZone": 0, "kdenlive:docproperties.seekOffset": 30000,
        "kdenlive:binZoom": 4, "kdenlive:extraBins": "project_bin:-1:0", "xml_retain": 1,
    })
    ET.SubElement(main_bin, "entry", producer=sequence_uuid, **{"in": "0", "out": str(total - 1)})
    for item in assets:
        ET.SubElement(main_bin, "entry", producer=item["producer"], **{"in": "0", "out": str(item["frames"] - 1)})
    project_tractor = ET.SubElement(root, "tractor", id="project_tractor", **{"in": "0", "out": str(total - 1)})
    props(project_tractor, {"kdenlive:projectTractor": 1})
    ET.SubElement(project_tractor, "track", producer=sequence_uuid, **{"in": "0", "out": str(total - 1)})
    ET.indent(root)
    project = bundle / "project.kdenlive"
    temporary = project.with_suffix(".kdenlive.writing")
    ET.ElementTree(root).write(temporary, encoding="utf-8", xml_declaration=True)
    temporary.replace(project)
    report = {
        "project": str(project), "fps": fps, "duration_frames": total, "duration_seconds": total / fps,
        "tracks": [name for name, _ in track_specs], "source_sha256": source_hash,
        "source_dimensions": [video["width"], video["height"]], "proxies_enabled": False,
        "source_segments": sum(s["kind"] == "source" for s in segments),
        "analysis_segments": sum(s["kind"] == "analysis" for s in segments), "assets": assets,
        "render_backend": "Kdenlive native application / MLT", "export_completed": False,
    }
    (bundle / "bundle-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (bundle / "project-manifest.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (bundle / "README.txt").write_text(
        "Open project.kdenlive in Kdenlive to edit the five separate timeline tracks.\n"
        "The original HD source remains in the project bin; proxies are disabled.\n"
        "Animated captions are separate transparent clips, regenerated from the reviewed JSON timeline.\n"
        "The media/ folder must travel with the project. If the whole folder is moved, run:\n"
        "python /path/to/repository/experiments/conversation-chess/export-kdenlive.py "
        "--relocate --bundle /new/path/to/bundle\n"
        "For a manual edit, use Kdenlive's Render command; rebuilding from the input manifest "
        "replaces the generated timeline.\n"
        "Native rendering needs X11/Wayland (an authenticated Xvfb display is supported).\n"
        "Qt offscreen cannot be used for the transparent overlays in this project.\n",
        encoding="utf-8",
    )
    return project, report


def render(project, destination, report, display=None, xauthority=None):
    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    if xauthority:
        env["XAUTHORITY"] = str(Path(xauthority).resolve(strict=True))
    if not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
        raise RuntimeError("Qt/MLT compositing needs X11/Wayland: start authenticated Xvfb or use a graphical session")
    if env.get("DISPLAY"):
        env["QT_QPA_PLATFORM"] = "xcb"
    else:
        env["QT_QPA_PLATFORM"] = "wayland"
    env["XDG_CONFIG_HOME"] = str(project.parent / ".render-config")
    env["XDG_CACHE_HOME"] = str(project.parent / ".render-cache")
    env["XDG_DATA_HOME"] = str(project.parent / ".render-data")
    preset_name = "Conversation Review — H264 CRF17 AAC192"
    preset_directory = Path(env["XDG_DATA_HOME"]) / "kdenlive" / "export"
    preset_directory.mkdir(parents=True, exist_ok=True)
    presets = ET.Element("profiles", version="1")
    group = ET.SubElement(presets, "group", name="Conversation Review", renderer="avformat", type="av")
    ET.SubElement(group, "profile", name=preset_name, extension="mp4", args=(
        "f=mp4 movflags=+faststart vcodec=libx264 crf=17 preset=medium g=30 "
        "pix_fmt=yuv420p acodec=aac ab=192k ar=48000 channels=2 threads=4"
    ))
    ET.ElementTree(presets).write(preset_directory / "customprofiles.xml", encoding="utf-8", xml_declaration=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    log = project.parent / "kdenlive-export.log"
    command = ["/usr/bin/kdenlive", "--render", "--render-preset", preset_name, str(project), str(destination)]
    print("Kdenlive native export started:", destination, flush=True)
    job_copy = project.parent / "native-render-job.mlt"
    last_progress = -10
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=project.parent, env=env, stdout=output, stderr=subprocess.STDOUT)
        while process.poll() is None:
            contents = log.read_text(encoding="utf-8", errors="replace")
            for candidate in reversed(re.findall(r'"(/tmp/kdenlive-[^"\s]+\.mlt)"', contents)):
                generated_job = Path(candidate)
                if generated_job.is_file():
                    try:
                        shutil.copy2(generated_job, job_copy)
                    except FileNotFoundError:
                        # Kdenlive removes its temporary job immediately after completion.
                        continue
                    break
            progress = re.findall(r"Progress: (\d+) %, frame (\d+)", contents)
            if progress:
                percent, frame = map(int, progress[-1])
                if percent >= last_progress + 10:
                    print(f"Kdenlive export: {percent}% (frame {frame})", flush=True)
                    last_progress = percent
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    if process.returncode:
        raise RuntimeError(f"Kdenlive export failed ({process.returncode}); inspect {log}")
    final_probe = probe(destination)
    video = next(s for s in final_probe["streams"] if s["codec_type"] == "video")
    if int(video["width"]) != 1920 or int(video["height"]) != 1080:
        raise RuntimeError("Kdenlive export profile changed unexpectedly")
    if int(video.get("nb_frames", 0)) != report["duration_frames"]:
        raise RuntimeError("Kdenlive output frame count differs from the reviewed timeline")
    if Fraction(video["avg_frame_rate"]) != report["fps"]:
        raise RuntimeError("Kdenlive output frame rate differs from the reviewed timeline")
    audio = next((s for s in final_probe["streams"] if s["codec_type"] == "audio"), None)
    if not audio or audio["codec_name"] != "aac" or int(audio.get("sample_rate", 0)) != 48000:
        raise RuntimeError("Kdenlive export must contain 48kHz AAC audio")
    if abs(float(final_probe["format"]["duration"]) - report["duration_seconds"]) > 0.1:
        raise RuntimeError("Kdenlive export duration differs from the reviewed timeline")
    report.update(export_completed=True, final_video=str(destination), export_command=command,
                  export_preset={"name": preset_name, "crf": 17, "audio_bitrate": "192k", "preset": "medium"},
                  output_sha256=digest(destination), output_probe=final_probe)
    (project.parent / "bundle-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"native_project": str(project), "final_video": str(destination),
                      "frames": report["duration_frames"], "export_backend": "Kdenlive / MLT"}), flush=True)


def relocate(bundle):
    project = bundle / "project.kdenlive"
    tree = ET.parse(project)
    tree.getroot().set("root", str(bundle))
    tree.write(project, encoding="utf-8", xml_declaration=True)
    manifest = bundle / "bundle-manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["project"] = str(project)
        data["relocated_media_root"] = str(bundle)
        manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Project media root updated:", bundle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--render", type=Path)
    parser.add_argument("--display")
    parser.add_argument("--xauthority", type=Path)
    parser.add_argument("--relocate", action="store_true", help="Rebase relative media paths after moving the whole bundle")
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    if args.relocate:
        relocate(bundle)
        return
    if not args.manifest:
        parser.error("--manifest is required unless --relocate is used")
    project, report = generate(args.manifest.resolve(strict=True), bundle)
    print(json.dumps({"native_project": str(project), "frames": report["duration_frames"],
                      "tracks": report["tracks"], "source_segments": report["source_segments"],
                      "analysis_segments": report["analysis_segments"]}), flush=True)
    if args.render:
        render(project, args.render.resolve(), report, args.display, args.xauthority)


if __name__ == "__main__":
    main()
