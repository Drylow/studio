#!/usr/bin/env python3
"""Validate a reviewed native delivery kit; GoFile upload requires --upload.

All manifest paths are local and relative to the manifest directory. Required:
kind, video, thumbnail, titles, title, description, music_credits, review,
technical_review, prepared_manifest, native_receipt. Visual review must retain
sampled_visual_review.evidence_files relative to its own directory. A final kit
also needs the publication_review used by deliver-discord.py; youtube-test does
not assert copyright clearance. The five uploads are movie, thumbnail, titles,
complete description and music credits. No automatic upload retries/resumption.
--verify-existing-web explicitly reconciles five already-confirmed uploads using
retained evidence from the unmodified official website; it never uses the network.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import fcntl
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import tempfile

import requests
from PIL import Image

PAGE = re.compile(r"https://gofile\.io/d/[A-Za-z0-9]+")
SHA = re.compile(r"[a-f0-9]{64}")
CONTENT_ID = re.compile(r"[A-Za-z0-9-]+")


def save(path, value, private=False):
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600 if private else 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def hashes(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
            md5.update(block)
    return {"filename": path.name, "bytes": path.stat().st_size,
            "sha256": sha.hexdigest(), "md5": md5.hexdigest()}


def report(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("A review/manifest must be a JSON object.")
    return value


def local(base, name):
    if not isinstance(name, str) or not name.strip() or "://" in name:
        raise ValueError("An explicit local file path is required.")
    path = (base / name).resolve()
    if not path.is_file():
        raise ValueError("A required local file is missing: " + path.name)
    return path


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams", "-show_format",
                             "-of", "json", str(path)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("The actual media profile could not be read: " + path.name)
    return json.loads(result.stdout)


def video_profile(info):
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if len(videos) != 1 or not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        raise ValueError("The completed movie/source must contain one video and audio.")
    return videos[0]


def image_proof(path):
    with Image.open(path) as image:
        if image.format not in ("JPEG", "PNG") or min(image.size) < 1:
            raise ValueError("Thumbnail and visual evidence must be real PNG/JPEG images.")
        image.verify()


def picture_hash(path):
    result = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0",
                             "-c", "copy", "-f", "hash", "-hash", "sha256", "-"],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Picture-stream integrity could not be read: " + path.name)
    return result.stdout.strip()


def prepare(manifest):
    manifest = manifest.resolve()
    snapshots = {}
    def read_bytes(path):
        raw = path.read_bytes()
        snapshots[path] = hashlib.sha256(raw).hexdigest()
        return raw
    def read_json(path):
        value = json.loads(read_bytes(path).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("A review/manifest must be a JSON object.")
        return value
    def freeze_file(path, sha=None):
        snapshots[path] = sha or hashes(path)["sha256"]
    data, folder = read_json(manifest), manifest.parent
    kind = data.get("kind")
    if kind not in ("preview", "youtube-test", "final"):
        raise ValueError("kind must be preview, youtube-test or final.")
    resolve = lambda key: local(folder, data.get(key))
    video, thumbnail, titles, body, credits = [resolve(k) for k in
        ("video", "thumbnail", "titles", "description", "music_credits")]
    review_path, technical_path, project_path, native_path = [resolve(k) for k in
        ("review", "technical_review", "prepared_manifest", "native_receipt")]
    review, technical, project, native = map(read_json, (review_path, technical_path, project_path, native_path))
    movie = hashes(video)
    if movie["bytes"] < 1 or any(r.get("sha256") != movie["sha256"] for r in (technical, review)):
        raise ValueError("Exact video SHA must match technical QA and visual review.")
    native_video = local(native_path.parent, native.get("final_video"))
    finishing_inputs = []
    if native.get("export_completed") is not True \
            or local(technical_path.parent, technical.get("file")) != video:
        raise ValueError("Native completion and technical QA must identify this finished movie.")
    if "audio_finishing_receipt" in data:
        finishing_path = resolve("audio_finishing_receipt")
        finishing = read_json(finishing_path)
        native_sha = hashes(native_video)["sha256"]
        freeze_file(native_video, native_sha)
        gain = finishing.get("source_audio_gain_db")
        if type(gain) not in (int, float) or not math.isfinite(gain) or not 0 <= gain <= 12:
            raise ValueError("Audio finishing gain must be finite and between 0 and 12 dB.")
        if local(finishing_path.parent, finishing.get("parent_video")) != native_video \
                or local(finishing_path.parent, finishing.get("output_video")) != video \
                or native.get("output_sha256") != native_sha \
                or finishing.get("parent_sha256") != native_sha \
                or finishing.get("sha256") != movie["sha256"] \
                or finishing.get("bytes") != movie["bytes"] \
                or finishing.get("picture_stream_unchanged") is not True \
                or finishing.get("preserve_grading_music") is not True \
                or finishing.get("full_decode_passed") is not True \
                or finishing.get("source_interval_policy") != "half-open-sample-index" \
                or finishing.get("audio_sample_rate") != 48000 \
                or finishing.get("intro_analysis_outro_audio_gain_db") != 0:
            raise ValueError("Audio finishing must prove exact native parent, finished SHA and preserved grade/music levels.")
        expected_ranges = [(s["start_frame"] / float(project["fps"]), s["end_frame"] / float(project["fps"]))
                           for s in project["segments"] if s["kind"] == "source"]
        ranges = finishing.get("source_output_ranges")
        if not isinstance(ranges, list) or not expected_ranges or len(ranges) != len(expected_ranges):
            raise ValueError("Audio finishing source ranges do not match the prepared project.")
        for provided, expected in zip(ranges, expected_ranges):
            if not isinstance(provided, (list, tuple)) or len(provided) != 2 \
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in provided) \
                    or any(abs(v-e) > 1e-7 for v, e in zip(provided, expected)):
                raise ValueError("Audio finishing source ranges do not match the prepared project.")
        if finishing.get("source_output_sample_ranges") != [[round(a*48000), round(b*48000)] for a, b in expected_ranges]:
            raise ValueError("Audio finishing sample intervals do not match the prepared project.")
        checked_finishing = technical.get("audio_finishing", {})
        if checked_finishing.get("receipt_sha256") != snapshots[finishing_path] \
                or checked_finishing.get("output_sha256") != movie["sha256"] \
                or checked_finishing.get("parent_sha256") != native_sha:
            raise ValueError("Technical QA must explicitly validate this audio-finishing receipt and native parent.")
        parent_picture = picture_hash(native_video)
        if parent_picture != finishing.get("picture_stream_sha256") or picture_hash(video) != parent_picture:
            raise ValueError("Audio finishing changed the native picture stream.")
        finishing_inputs = [finishing_path, native_video]
    elif native_video != video or native.get("output_sha256") != movie["sha256"]:
        raise ValueError("Native output SHA differs; an explicit audio_finishing_receipt is required.")
    decode = technical.get("full_av_decode", {})
    if technical.get("completed") is not True or technical.get("technical_audio_passed") is not True \
            or technical.get("failures") != [] or technical.get("full_video_audio_decode_ok") is not True \
            or not isinstance(decode, dict) or decode.get("returncode") != 0:
        raise ValueError("Complete technical QA and actual full A/V decode must pass.")
    decode_log = local(technical_path.parent, decode.get("log"))
    freeze_file(decode_log)
    if decode_log.stat().st_size != 0:
        raise ValueError("Full A/V decode error log is not empty.")
    if any(review.get(k) is not True for k in ("technical_audio_passed", "full_video_audio_decode_ok",
                                               "finished_render_visual_reviewed")):
        raise ValueError("Visual review must confirm the completed technical result and inspected images.")
    visual = review.get("sampled_visual_review", {})
    if not isinstance(visual, dict) or visual.get("completed") is not True \
            or type(visual.get("reviewed_images")) is not int or visual["reviewed_images"] < 1 \
            or not isinstance(visual.get("method"), str) or not visual["method"].strip() \
            or not isinstance(visual.get("evidence_files"), list) or not visual["evidence_files"]:
        raise ValueError("Sampled visual review needs image count, method and retained evidence_files.")
    evidence = [local(review_path.parent, name) for name in visual["evidence_files"]]
    if len(set(evidence)) != len(evidence):
        raise ValueError("Visual evidence files must be distinct.")
    for path in evidence:
        freeze_file(path)
        image_proof(path)
    actual = probe(video)
    actual_video, qa_video = video_profile(actual), video_profile(technical.get("probe", {}))
    try:
        fps, frames = Fraction(str(project["fps"])), project["duration_frames"]
        expected_size = (project["width"], project["height"])
        profile_ok = type(frames) is int and frames > 0 and fps > 0 \
            and native.get("duration_frames") == technical.get("expected_frames") == frames \
            and Fraction(str(native.get("fps"))) == fps
        for record, stream in ((actual, actual_video), (technical["probe"], qa_video)):
            profile_ok = profile_ok and (stream.get("width"), stream.get("height")) == expected_size \
                and Fraction(stream.get("avg_frame_rate", "0")) == fps \
                and int(stream.get("nb_frames", 0)) == frames \
                and abs(float(record.get("format", {}).get("duration", 0)) - frames / float(fps)) < .1
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        profile_ok = False
    if not profile_ok:
        raise ValueError("Actual export profile, QA and prepared/native frame counts disagree.")
    if kind in ("youtube-test", "final") and any(
            r.get("source_quality", {}).get("accepted_for_final") is not True
            for r in (project, native, technical, review)):
        raise ValueError("Source quality must be accepted for youtube-test/final in all review records.")
    source = local(project_path.parent, project.get("original_source"))
    source_info = hashes(source)
    freeze_file(source, source_info["sha256"])
    source_video = video_profile(probe(source))
    dimensions = [source_video["width"], source_video["height"]]
    if not SHA.fullmatch(str(project.get("source_sha256", ""))) \
            or project["source_sha256"] != native.get("source_sha256") \
            or project["source_sha256"] != source_info["sha256"] \
            or any(r.get("source_dimensions") != dimensions for r in (project, native, technical)):
        raise ValueError("Original source SHA or actual source dimensions changed since preparation.")
    timeline = local(project_path.parent, project.get("timeline_file"))
    freeze_file(timeline)
    if snapshots[timeline] != project.get("timeline_sha256"):
        raise ValueError("Prepared timeline changed since export.")
    if "thumbnail_options" in data:
        raise ValueError("This uploader accepts one thumbnail; select it explicitly in the manifest.")
    freeze_file(thumbnail)
    image_proof(thumbnail)
    if thumbnail.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        raise ValueError("Thumbnail filename must use PNG/JPEG extension.")
    title = data.get("title", "")
    titles_text = read_bytes(titles).decode("utf-8")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 100 \
            or not titles_text.strip():
        raise ValueError("A short title and local title proposals are required.")
    attribution = project.get("music_attribution", {})
    credits_bytes = read_bytes(credits)
    credits_text = credits_bytes.decode("utf-8").strip()
    attribution_inputs = []
    if not credits_text:
        raise ValueError("A local music credits sidecar is required, even when no added music is used.")
    if attribution:
        credits_source = local(project_path.parent, attribution.get("file"))
        if credits_bytes != read_bytes(credits_source) \
                or snapshots[credits] != attribution.get("sha256") \
                or native.get("music_attribution", {}).get("sha256") != attribution.get("sha256"):
            raise ValueError("Local music credits must exactly match the prepared/native attribution.")
        attribution_inputs.append(credits_source)
    elif native.get("music_attribution") or native.get("music_segments") \
            or not isinstance(project.get("segments"), list) \
            or any(s.get("music_file") for s in project["segments"]):
        raise ValueError("Added music exists without prepared/native attribution; do not infer a license.")
    body_text, chapters = read_bytes(body).decode("utf-8").strip(), data.get("chapters", [])
    if not body_text or not isinstance(chapters, list) or not all(isinstance(x, str) for x in chapters) \
            or "Music credits\n" in body_text or "\nChapters\n" in body_text:
        raise ValueError("Description must be narrative text, with separate chapters and music credits.")
    complete = body_text + ("\n\nChapters\n" + "\n".join(chapters) if chapters else "") \
        + "\n\nMusic credits\n" + credits_text + "\n"
    if len(complete.strip()) > 5000:
        raise ValueError("Complete YouTube description exceeds 5000 characters.")
    inputs = [review_path, technical_path, project_path, native_path, decode_log,
              source, timeline, body, titles, credits, thumbnail, *evidence, *finishing_inputs, *attribution_inputs]
    if kind == "final":
        publication_path = resolve("publication_review")
        publication = read_json(publication_path)
        if publication.get("sha256") != movie["sha256"] or any(publication.get(k) is not True for k in
                ("source_rights_verified", "music_rights_verified", "youtube_checks_complete")) \
                or publication.get("youtube_copyright_status") != "clear" \
                or publication.get("claims") != [] or publication.get("blocked_territories") != []:
            raise ValueError("Final requires actual rights and YouTube clearance evidence; use youtube-test otherwise.")
        proof_names = publication.get("evidence_files")
        if not isinstance(proof_names, list) or not proof_names:
            raise ValueError("Publication review must retain evidence_files.")
        proofs = [local(publication_path.parent, name) for name in proof_names]
        for proof in proofs:
            freeze_file(proof)
        if any(p.stat().st_size == 0 for p in proofs):
            raise ValueError("Publication evidence is empty.")
        inputs += [publication_path, *proofs]
    description = folder / "description_with_credits.txt"
    if description in set(inputs + [video]):
        raise ValueError("Generated complete description would overwrite a validated input.")
    description.write_text(complete, encoding="utf-8")
    paths = [video, thumbnail, titles, description, credits]
    if len({p.name for p in paths}) != 5 or len(set(paths)) != 5:
        raise ValueError("The five upload files must have distinct filenames and paths.")
    rows = [hashes(path) for path in paths]
    if rows[0] != movie:
        raise ValueError("Movie changed after the exact-SHA review validation.")
    frozen = {p: snapshots[p] for p in set(inputs + [manifest])}
    if any(hashes(p)["sha256"] != sha for p, sha in frozen.items()):
        raise ValueError("A reviewed input changed while preparing the kit; restart validation.")
    normalized = {k: v for k, v in data.items() if k not in ("upload_receipt", "gofile_url")}
    validation = {str(p): sha for p, sha in frozen.items() if p != manifest}
    fingerprint = hashlib.sha256(json.dumps({"files": rows, "manifest": normalized,
            "validated_inputs": validation}, sort_keys=True).encode()).hexdigest()
    return {"manifest": manifest, "data": data, "paths": paths, "files": rows,
            "fingerprint": fingerprint, "frozen": frozen, "source_dimensions": dimensions,
            "export_dimensions": list(expected_size)}


def unchanged(kit):
    if any(hashes(p) != row for p, row in zip(kit["paths"], kit["files"])) \
            or any(hashes(p)["sha256"] != sha for p, sha in kit["frozen"].items()):
        raise RuntimeError("An upload file or reviewed input changed; stop and inspect pending.")


def data_from(response, label):
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed (HTTP {response.status_code}); no automatic retry.")
    try:
        body = response.json()
    except ValueError:
        raise RuntimeError(label + " returned unreadable JSON; no automatic retry.") from None
    if not isinstance(body, dict) or body.get("status") != "ok" or not isinstance(body.get("data"), dict):
        raise RuntimeError(label + " did not confirm success; no automatic retry.")
    return body["data"]


def matched_readback(data, folder, rows):
    """Use the normal authenticated contents API, not upload response alone."""
    children = data.get("children")
    if data.get("id") != folder or data.get("type") != "folder" or not isinstance(children, dict):
        raise RuntimeError("GoFile readback did not confirm the expected folder.")
    entries = list(children.values())
    if len(entries) != len(rows):
        raise RuntimeError("GoFile readback file count differs; pending retained.")
    matched = []
    for expected in rows:
        candidates = [x for x in entries if isinstance(x, dict) and x.get("name") == expected["filename"]]
        if len(candidates) != 1:
            raise RuntimeError("GoFile readback filenames differ; pending retained.")
        entry = candidates[0]
        size = entry.get("size")
        if isinstance(size, str) and size.isdigit():
            size = int(size)
        if entry.get("type") != "file" or type(size) is not int or size != expected["bytes"] \
                or entry.get("md5") != expected["md5"]:
            raise RuntimeError("GoFile API readback MD5/bytes mismatch; pending retained.")
        matched.append({**expected, "api_readback_matched": True})
    return matched


def ensure_private_ignored(path):
    root = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True)
    if root.returncode == 0 and subprocess.run(["git", "-C", root.stdout.strip(), "check-ignore",
            "--quiet", str(path)], capture_output=True).returncode != 0:
        raise ValueError("Private owner-token path must be Git-ignored before upload.")


def bind_delivery(kit, receipt_path, page):
    if hashes(kit["manifest"])["sha256"] != kit["frozen"][kit["manifest"]]:
        raise RuntimeError("Delivery manifest changed before binding the reviewed kit URL; inspect pending.")
    data = dict(kit["data"])
    data.update(gofile_url=page, upload_receipt=os.path.relpath(receipt_path, kit["manifest"].parent))
    expected_sha = hashlib.sha256((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()).hexdigest()
    save(kit["manifest"], data)
    if hashes(kit["manifest"])["sha256"] != expected_sha:
        raise RuntimeError("Delivery manifest changed while binding; pending retained.")
    # Only this known, verified local binding is allowed to change the frozen input.
    kit["frozen"][kit["manifest"]] = expected_sha
    kit["data"] = data


def frozen_json(path, snapshots):
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if path in snapshots and snapshots[path] != sha:
        raise RuntimeError("Existing-upload evidence changed; pending retained.")
    snapshots[path] = sha
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Existing-upload evidence must be a JSON object.")
    return value


def evidence_unchanged(snapshots):
    if any(hashes(path)["sha256"] != sha for path, sha in snapshots.items()):
        raise RuntimeError("Existing-upload evidence changed; pending retained.")


def private_owner(path, snapshots):
    ensure_private_ignored(path)
    if path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("Existing owner credentials must remain private (mode 600).")
    owner = frozen_json(path, snapshots)
    if not isinstance(owner.get("folder_id"), str) or not CONTENT_ID.fullmatch(owner["folder_id"]) \
            or not isinstance(owner.get("url"), str) or not PAGE.fullmatch(owner["url"]) \
            or not isinstance(owner.get("owner_token"), str) or not owner["owner_token"]:
        raise ValueError("Existing owner identity is incomplete; pending retained.")
    return owner


def official_web_readback(proof_path, owner, rows, snapshots):
    """Validate retained normal-site evidence, never synthesize/replay website auth."""
    proof_path = proof_path.resolve()
    proof = frozen_json(proof_path, snapshots)
    if type(proof.get("http_status")) is not int or proof["http_status"] != 200 \
            or proof.get("api_status") != "ok" or proof.get("public_url") != owner["url"] \
            or proof.get("folder_id") != owner["folder_id"] or proof.get("folder_type") != "folder":
        raise RuntimeError("Official web readback did not confirm the expected public folder.")
    if proof.get("public_listing_matched") is not True or proof.get("expected") != rows \
            or type(proof.get("expected_file_count")) is not int or proof["expected_file_count"] != len(rows):
        raise RuntimeError("Official web proof does not identify the exact reviewed kit.")
    metadata = proof.get("metadata")
    if not isinstance(metadata, dict) or any(type(metadata.get(k)) is not int for k in
            ("totalCount", "totalPages", "page", "pageSize")) \
            or metadata["totalCount"] != len(rows) or metadata["totalPages"] != 1 \
            or metadata["page"] != 1 or metadata["pageSize"] < len(rows) \
            or metadata.get("hasNextPage") is not False:
        raise RuntimeError("Official web listing is incomplete or paginated; pending retained.")
    files = proof.get("files")
    if not isinstance(files, list) or len(files) != len(rows) or any(not isinstance(f, dict) for f in files):
        raise RuntimeError("Official web readback file count differs; pending retained.")
    ids = [f.get("id") for f in files]
    if any(not isinstance(i, str) or not CONTENT_ID.fullmatch(i) for i in ids) or len(set(ids)) != len(ids):
        raise RuntimeError("Official web listing contains missing or duplicate file IDs.")
    # The same filename/type/bytes/MD5 controls apply to either readback method.
    matched_readback({"id": owner["folder_id"], "type": "folder",
                      "children": dict(zip(ids, files))}, owner["folder_id"], rows)
    if proof.get("direct_premium_api_readback_complete") is not False \
            or proof.get("blocked_mutations") != [] \
            or not isinstance(proof.get("method"), str) or not proof["method"].strip():
        raise RuntimeError("Official web evidence must distinguish its method and direct API limitation.")
    screenshot = local(proof_path.parent, proof.get("screenshot_path", "public-listing.png"))
    screenshot_sha = proof.get("screenshot_sha256")
    if not isinstance(screenshot_sha, str) or not SHA.fullmatch(screenshot_sha) \
            or hashes(screenshot)["sha256"] != screenshot_sha:
        raise RuntimeError("Official web screenshot SHA differs from the retained proof.")
    snapshots[screenshot] = screenshot_sha
    image_proof(screenshot)
    evidence_unchanged(snapshots)
    return {"proof": {"path": str(proof_path), "sha256": snapshots[proof_path]},
            "screenshot": {"path": str(screenshot), "sha256": screenshot_sha},
            "http_status": 200, "status": "ok", "folder_id": owner["folder_id"],
            "file_count": len(rows), "method": proof["method"],
            "captured_at": proof.get("generated_utc")}


def validated_existing_receipt(previous, kit, owner_path, snapshots):
    if previous.get("fingerprint") != kit["fingerprint"] or previous.get("kind") != kit["data"]["kind"] \
            or not isinstance(previous.get("url"), str) or not PAGE.fullmatch(previous["url"]):
        raise RuntimeError("Previous receipt does not match this reviewed kit; inspect before uploading.")
    if previous.get("official_web_client_readback_complete") is True:
        evidence = previous.get("official_web_client_readback")
        if previous.get("api_readback_complete") is not False \
                or previous.get("direct_premium_api_readback_complete") is not False \
                or previous.get("files") != [{**r, "official_web_client_readback_matched": True} for r in kit["files"]] \
                or not isinstance(evidence, dict) or not isinstance(evidence.get("proof"), dict):
            raise RuntimeError("Previous official web receipt is incomplete or falsely claims direct API success.")
        owner = private_owner(owner_path, snapshots)
        proof = local(kit["manifest"].parent, evidence["proof"].get("path"))
        actual = official_web_readback(proof, owner, kit["files"], snapshots)
        if owner["url"] != previous["url"] or actual != evidence:
            raise RuntimeError("Previous official web evidence SHA/identity changed; inspect before uploading.")
    elif previous.get("api_readback_complete") is not True \
            or previous.get("files") != [{**r, "api_readback_matched": True} for r in kit["files"]]:
        raise RuntimeError("Previous receipt does not match this reviewed kit; inspect before uploading.")
    evidence_unchanged(snapshots)


def reconcile_existing_web(kit, state, proof_path):
    """Explicit local reconciliation only; preserves pending on any failed check."""
    owner_path, pending_path, receipt_path = state
    archived_pending = pending_path.with_name("gofile-pending-confirmed.json")
    if archived_pending.exists():
        raise RuntimeError("A pending archive already exists; inspect instead of overwriting it.")
    snapshots = {}
    pending = frozen_json(pending_path, snapshots)
    if pending.get("fingerprint") != kit["fingerprint"] \
            or pending.get("intended_files") != kit["files"] \
            or pending.get("confirmed_files") != kit["files"]:
        raise RuntimeError("Pending does not contain five exact confirmed uploads for this reviewed kit.")
    owner = private_owner(owner_path, snapshots)
    if pending.get("url") != owner["url"]:
        raise RuntimeError("Pending and private owner public URL differ.")
    evidence = official_web_readback(proof_path, owner, kit["files"], snapshots)
    unchanged(kit)
    evidence_unchanged(snapshots)
    if receipt_path.exists():
        previous = frozen_json(receipt_path, snapshots)
        validated_existing_receipt(previous, kit, owner_path, snapshots)
        if previous.get("official_web_client_readback") != evidence:
            raise RuntimeError("An existing receipt identifies different web evidence; pending retained.")
    else:
        receipt = {"url": owner["url"], "kind": kit["data"]["kind"], "fingerprint": kit["fingerprint"],
                   "files": [{**r, "official_web_client_readback_matched": True} for r in kit["files"]],
                   "api_readback_complete": False, "direct_premium_api_readback_complete": False,
                   "official_web_client_readback_complete": True, "official_web_client_readback": evidence,
                   "source_dimensions": kit["source_dimensions"], "export_dimensions": kit["export_dimensions"],
                   "verified_at": datetime.now(timezone.utc).isoformat()}
        save(receipt_path, receipt)
        expected_sha = hashlib.sha256((json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode()).hexdigest()
        if hashes(receipt_path)["sha256"] != expected_sha:
            raise RuntimeError("Receipt changed while saving; pending retained.")
        snapshots[receipt_path] = expected_sha
    evidence_unchanged(snapshots)
    unchanged(kit)
    original_manifest = kit["manifest"].read_bytes()
    original_sha = hashlib.sha256(original_manifest).hexdigest()
    original_data = dict(kit["data"])
    original_mode = kit["manifest"].stat().st_mode & 0o777
    if original_sha != kit["frozen"][kit["manifest"]]:
        raise RuntimeError("Delivery manifest changed before binding; pending retained.")
    try:
        bind_delivery(kit, receipt_path, owner["url"])
        unchanged(kit)
        evidence_unchanged(snapshots)
    except (OSError, ValueError, RuntimeError):
        bound_sha = kit["frozen"][kit["manifest"]]
        # Undo only our exact binding; never replace somebody else's edited file.
        if bound_sha != original_sha and hashes(kit["manifest"])["sha256"] == bound_sha:
            fd, temporary = tempfile.mkstemp(prefix="delivery-binding-rollback.", dir=kit["manifest"].parent)
            try:
                os.fchmod(fd, original_mode)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(original_manifest)
                if hashes(kit["manifest"])["sha256"] == bound_sha:
                    Path(temporary).replace(kit["manifest"])
                    kit["frozen"][kit["manifest"]] = original_sha
                    kit["data"] = original_data
            finally:
                Path(temporary).unlink(missing_ok=True)
        raise
    # Retain the exact POST confirmations rather than deleting the recovery record.
    pending_path.rename(archived_pending)
    archived_pending.chmod(0o600)
    print(json.dumps({"status": "existing-upload-web-confirmed", "url": owner["url"],
                      "files": len(kit["files"]), "api_readback_complete": False,
                      "official_web_client_readback_complete": True}), flush=True)


def upload(kit, state):
    owner_path, pending_path, receipt_path = state
    ensure_private_ignored(owner_path)
    with requests.Session() as session:
        try:
            response = session.get("https://api.gofile.io/servers", timeout=(15, 30), allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError("GoFile server selection unavailable; no upload attempted.") from None
        servers = data_from(response, "GoFile server selection").get("servers", [])
        candidates = [s for s in servers if isinstance(s, dict)
                      and re.fullmatch(r"store[a-z0-9-]+", str(s.get("name", "")))]
        if not candidates:
            raise RuntimeError("GoFile returned no supported upload server.")
        chosen = next((s for s in candidates if s.get("zone") == "eu"), candidates[0])
        endpoint = "https://" + chosen["name"] + ".gofile.io/uploadFile"
        pending = {"fingerprint": kit["fingerprint"], "intended_files": kit["files"],
                   "confirmed_files": [], "url": None}
        save(pending_path, pending)
        folder = page = token = None
        for source, expected in zip(kit["paths"], kit["files"]):
            unchanged(kit)
            headers = {"Authorization": "Bearer " + token} if token else {}
            try:
                with source.open("rb") as stream:
                    response = session.post(endpoint, data={"folderId": folder} if folder else {}, headers=headers,
                        files={"file": (source.name, stream, mimetypes.guess_type(source.name)[0]
                                        or "application/octet-stream")}, timeout=(20, 180), allow_redirects=False)
            except requests.RequestException:
                raise RuntimeError("GoFile upload outcome uncertain; pending retained, no automatic retry.") from None
            result = data_from(response, "GoFile upload")
            size = result.get("size")
            if isinstance(size, str) and size.isdigit():
                size = int(size)
            if result.get("md5") != expected["md5"] or type(size) is not int \
                    or size != expected["bytes"] or hashes(source) != expected:
                raise RuntimeError("GoFile upload MD5/bytes mismatch; pending retained.")
            if folder is None:
                folder = result.get("parentFolder") or result.get("folderId")
                page = result.get("downloadPage")
                token = result.get("guestToken") or result.get("accountToken")
                if not isinstance(folder, str) or not re.fullmatch(r"[A-Za-z0-9-]+", folder) \
                        or not isinstance(page, str) or not PAGE.fullmatch(page) \
                        or not isinstance(token, str) or not token:
                    raise RuntimeError("GoFile did not confirm a reusable guest folder; pending retained.")
                save(owner_path, {"folder_id": folder, "url": page, "owner_token": token}, private=True)
            elif result.get("parentFolder", folder) != folder or result.get("downloadPage", page) != page:
                raise RuntimeError("GoFile upload folder changed; pending retained.")
            pending["url"] = page
            pending["confirmed_files"].append(expected)
            save(pending_path, pending)
            print(json.dumps({"uploaded": source.name, "bytes_verified": expected["bytes"]}), flush=True)
        unchanged(kit)
        try:
            response = session.get("https://api.gofile.io/contents/" + folder,
                                   headers={"Authorization": "Bearer " + token},
                                   timeout=(15, 30), allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError("GoFile API readback unavailable; pending retained, no automatic retry.") from None
        files = matched_readback(data_from(response, "GoFile folder readback"), folder, kit["files"])
        unchanged(kit)
        receipt = {"url": page, "kind": kit["data"]["kind"], "fingerprint": kit["fingerprint"],
                   "files": files, "api_readback_complete": True,
                   "source_dimensions": kit["source_dimensions"], "export_dimensions": kit["export_dimensions"],
                   "uploaded_at": datetime.now(timezone.utc).isoformat()}
        save(receipt_path, receipt)
        bind_delivery(kit, receipt_path, page)
        pending_path.unlink()
        print(json.dumps({"status": "upload-confirmed", "url": page, "files": len(files)}), flush=True)


def run(manifest, do_upload=False, verify_existing_web=None):
    manifest = manifest.resolve()
    folder = manifest.parent
    owner, pending, receipt = [folder / name for name in
        ("gofile-owner-private.json", "gofile-pending.json", "gofile-receipt.json")]
    with (folder / "gofile.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if pending.exists() and verify_existing_web is None:
            raise RuntimeError("Previous upload incomplete/uncertain; inspect pending before any retry.")
        kit = prepare(manifest)
        if verify_existing_web is not None and pending.exists():
            reconcile_existing_web(kit, (owner, pending, receipt), verify_existing_web)
        elif receipt.exists():
            snapshots = {}
            previous = frozen_json(receipt, snapshots)
            validated_existing_receipt(previous, kit, owner, snapshots)
            if verify_existing_web is not None:
                proof = previous.get("official_web_client_readback", {}).get("proof", {})
                if previous.get("official_web_client_readback_complete") is not True \
                        or proof.get("path") != str(verify_existing_web.resolve()):
                    raise RuntimeError("Existing receipt does not identify this explicit web proof.")
            unchanged(kit)
            evidence_unchanged(snapshots)
            if do_upload or verify_existing_web is not None:
                bind_delivery(kit, receipt, previous["url"])
                unchanged(kit)
                evidence_unchanged(snapshots)
            print(json.dumps({"status": "already-uploaded", "url": previous["url"]}), flush=True)
        elif verify_existing_web is not None:
            raise RuntimeError("No confirmed pending upload or receipt exists; no network attempt made.")
        elif do_upload:
            upload(kit, (owner, pending, receipt))
        else:
            print(json.dumps({"status": "validated-no-upload", "kind": kit["data"]["kind"],
                              "fingerprint": kit["fingerprint"], "files": kit["files"]}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--upload", action="store_true")
    mode.add_argument("--dry-run", action="store_true", help="Validate offline (default).")
    mode.add_argument("--verify-existing-web", type=Path, metavar="PROOF_PATH",
                      help="Reconcile existing confirmed uploads using retained official web-client proof; no network.")
    args = parser.parse_args()
    run(args.manifest, args.upload, args.verify_existing_web)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit("Upload stopped: " + str(error)) from None
