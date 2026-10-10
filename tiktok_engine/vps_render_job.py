"""Isolated render adapter, packaged as production/news.py for the existing VPS worker."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

TOOLS = Path("/data/tiktok-tools")
NODE = TOOLS / "node-v22.20.0-linux-x64/bin/node"
SLUG = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*\Z")


def checked_slug(value):
    if not isinstance(value, str) or len(value) > 100 or not SLUG.fullmatch(value):
        raise ValueError("Invalid video or image name")
    return value


def write_result(job, result):
    temporary = job / "result.json.tmp"
    temporary.write_text(json.dumps(result), encoding="utf-8")
    temporary.replace(job / "result.json")


def main(job):
    engine = Path(__file__).resolve().parents[1] / "tiktok_engine"
    logpath = job / "build.log"
    result = {"videos": {}, "errors": {}, "complete": False}

    def note(message):
        with logpath.open("a", encoding="utf-8") as log:
            log.write(message + "\n")
        print(message, flush=True)

    def render(slug, inputs):
        work = job / "videos" / checked_slug(slug)
        timeline = work / "timeline.json"
        spec = json.loads(timeline.read_text(encoding="utf-8"))
        duration = spec.get("duration")
        if (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                or not math.isfinite(duration) or duration < 61 or spec.get("fps") != 30):
            raise ValueError("Invalid timeline duration or frame rate")
        if not isinstance(spec.get("images"), dict) or not spec["images"]:
            raise ValueError("Missing timeline images")
        for key in spec["images"]:
            image = work / "art" / (checked_slug(key) + ".png")
            if image.is_symlink() or not image.is_file() or not image.resolve().is_relative_to(work.resolve()):
                raise ValueError("Missing or unsafe image")
            spec["images"][key] = "/abs" + str(image)
        timeline.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        audio = work / "mix.flac"
        if audio.is_symlink() or not audio.is_file() or not audio.read_bytes().startswith(b"fLaC"):
            raise ValueError("Missing lossless audio")
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        output = work / "video.mp4"
        environment = dict(os.environ, PATH=str(NODE.parent) + os.pathsep + os.environ.get("PATH", ""),
                           PLAYWRIGHT_BROWSERS_PATH=str(TOOLS / "browsers"))
        note(slug + " render started")
        with logpath.open("a", encoding="utf-8") as log:
            subprocess.run([str(NODE), str(engine / "render.mjs"), "--spec", str(timeline),
                            "--audio", str(audio), "--workers", "4", "--fps", "30", "--preset", "medium",
                            "--crf", "10", "--out", str(output), "--ffmpeg", ffmpeg],
                           env=environment, stdout=log, stderr=log, check=True)
        raw = output.read_bytes()
        if raw[4:8] != b"ftyp":
            raise ValueError("Renderer did not produce an MP4")
        note(slug + " render complete")
        return {"duration": duration, "size": len(raw), "md5": hashlib.md5(raw).hexdigest(),
                "sha256": hashlib.sha256(raw).hexdigest(), "inputs_sha256": inputs,
                "video_base64": base64.b64encode(raw).decode("ascii")}

    try:
        plan = json.loads((job / "plan.json").read_text(encoding="utf-8"))
        slugs = plan.get("slugs")
        if not isinstance(slugs, list) or not 1 <= len(slugs) <= 2 or len(set(slugs)) != len(slugs):
            raise ValueError("Expected one or two distinct videos")
        for slug in slugs:
            checked_slug(slug)
            if not isinstance(plan.get("inputs_sha256", {}).get(slug), dict):
                raise ValueError("Missing input receipt")
        if not NODE.is_file() or not (TOOLS / "js/node_modules/playwright").is_dir() or not (TOOLS / "browsers").is_dir():
            raise RuntimeError("TikTok VPS dependencies absent; see tiktok_engine/VPS.md")
        (engine / "node_modules").symlink_to(TOOLS / "js/node_modules", target_is_directory=True)
        write_result(job, result)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(render, slug, plan["inputs_sha256"][slug]): slug for slug in slugs}
            for future in as_completed(futures):
                slug = futures[future]
                try:
                    result["videos"][slug] = future.result()
                except Exception as exc:
                    result["errors"][slug] = type(exc).__name__
                    note(slug + " failed (" + type(exc).__name__ + "); see build.log")
                write_result(job, result)
    except Exception as exc:
        result["errors"]["worker"] = type(exc).__name__
        note("Worker preparation failed (" + type(exc).__name__ + ")")
    finally:
        result["complete"] = True
        write_result(job, result)
        note("Batch finished")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    # The existing worker invokes: news.py build <jobdir> --no-upload.
    if len(sys.argv) < 3 or sys.argv[1] != "build":
        raise SystemExit("This adapter is executed by the existing VPS worker")
    sys.exit(main(Path(sys.argv[2]).resolve()))
