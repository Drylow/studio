"""Continuous, resumable review and render handoff for explicitly frozen films.

Run on the production server. This never authors prompts, generates images,
retries image requests, changes providers, approves primary reviews or publishes.
The input contract lists the exact expected asset for every narrated interval.
"""
import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

try:
    from . import visual_audit as audit
except ImportError:
    import visual_audit as audit


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Asset path leaves its project")
    return target


@contextmanager
def exclusive(path, nonblocking=True):
    import fcntl
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        mode = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        try:
            fcntl.flock(handle, mode)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate_contract(film):
    expected = film["expected"]
    if (not expected or len(expected) != len(film["timings"])
            or [r["shot_id"] for r in expected] != list(range(1, len(expected) + 1))):
        raise ValueError("Expected assets must cover every interval exactly once")
    if len({r["asset_id"] for r in expected}) != len(expected):
        raise ValueError("Duplicate expected asset")
    for row, timing in zip(expected, film["timings"]):
        if row["shot_id"] != timing["id"] or not 0 < timing["duration"] <= 7:
            raise ValueError("Frozen timing mismatch")
        if not row["authored_action"]:
            raise ValueError("Primary-authored action required")
        if row.get("frozen", True) and (not row["prompt"] or not row["references"]):
            raise ValueError("Primary-authored action, prompt and references required")
        audit.route_primary({}, row)


def receipts(film):
    result = {}
    for stage in film["stages"]:
        for path in Path(stage).glob("*-receipt.json"):
            row = read(path)
            if row.get("state") != "done":
                continue
            asset = row["asset_id"]
            if asset in result and result[asset]["sha256"] != row["sha256"]:
                raise ValueError("Conflicting immutable asset receipts")
            result[asset] = row
    return result


def exact_source(film, expected, row):
    if any(row.get(k) != expected.get(k) for k in ("asset_id", "shot_id", "prompt", "references")):
        raise ValueError("Completed source differs from frozen authoring")
    if sha(inside(film["project_root"], row["path"])) != row["sha256"]:
        raise ValueError("Completed image hash changed")
    for ref in row["references"]:
        root = film["style_root"] if ref["owner"] == "style" else film["project_root"]
        if ref["review_state"] != "verified" or sha(inside(root, ref["path"])) != ref["sha256"]:
            raise ValueError("An inspected reference changed")


def primary_decisions(film):
    good = {r["asset_id"]: r for r in read(Path(film["directory"]) / "primary-shot-review.json", [])}
    bad = {r["asset_id"]: r for r in read(Path(film["directory"]) / "primary-rejections.json", [])}
    return good, bad


def previous_reviews(film):
    """Reuse attributable evidence without pretending it is a primary review."""
    result = {}
    files = [Path(film["directory"]) / "continuous-qc" / "evidence" / "report.json"]
    for stage in film["stages"]:
        files += list(Path(stage).glob("proxy-review*/evidence/report.json"))
    for path in files:
        report = read(path, {})
        for row in report.get("results", []):
            if row.get("source") != "cli_proxy_vision" or not row.get("hashes"):
                continue
            item = row.get("item", {})
            source = item.get("path")
            if source:
                result[(str(Path(source).resolve()), row["hashes"][-1])] = row
    return result


def review_item(film, expected, row):
    refs = []
    for ref in row["references"]:
        root = film["style_root"] if ref["owner"] == "style" else film["project_root"]
        refs.append({"role": "drawing-only" if ref["role"] == "style-only" else ref["role"],
                     "path": str(inside(root, ref["path"]))})
    return {"id": row["shot_id"], "path": str(inside(film["project_root"], row["path"])),
            "references": refs, "characters": expected["characters"],
            "narration": expected.get("narration", ""),
            "authored_action": expected["authored_action"], "risk_flags": expected.get("risk_flags", [])}


def select(film, sources, reviews):
    """Fail closed on missing, changed, rejected, risky or unreviewed assets."""
    primary, rejected = primary_decisions(film)
    selected, pending, audit_jobs = [], [], []
    for expected in film["expected"]:
        asset = expected["asset_id"]
        if not expected.get("frozen", True):
            pending.append({"id": expected["shot_id"], "asset_id": asset, "state": "awaiting_primary_authoring"})
            continue
        row = sources.get(asset)
        if row is None:
            pending.append({"id": expected["shot_id"], "asset_id": asset, "state": "awaiting_image"})
            continue
        exact_source(film, expected, row)
        good, bad = primary.get(asset), rejected.get(asset)
        if bad and bad["sha256"] == row["sha256"]:
            pending.append({"id": row["shot_id"], "asset_id": asset, "state": "primary_rejected"})
            continue
        if good and good.get("state") == "verified" and good.get("source") == "primary_agent_actual_pixel_inspection" and good["sha256"] == row["sha256"]:
            selected.append(dict(good, ordered_references=row["references"]))
            continue
        item = review_item(film, expected, row)
        evidence = reviews.get((item["path"], row["sha256"]))
        if evidence and any(evidence.get("item", {}).get(k) != item[k]
                            for k in ("authored_action", "narration", "characters")):
            evidence = None
        # Required scene-anchor inspections are routed straight to primary review.
        mandatory = expected.get("requires_primary", False)
        if mandatory:
            pending.append({"id": row["shot_id"], "asset_id": asset, "sha256": row["sha256"], "state": "awaiting_primary_anchor"})
            continue
        if evidence is None:
            audit_jobs.append((expected, row, item))
            pending.append({"id": row["shot_id"], "asset_id": asset, "state": "awaiting_proxy_review"})
            continue
        check = audit.route_primary(audit.validate(evidence), item) if evidence.get("state") == "proxy_reviewed" else {"requires_primary_review": True}
        if check["requires_primary_review"] or expected.get("risk_flags"):
            pending.append({"id": row["shot_id"], "asset_id": asset, "sha256": row["sha256"],
                            "state": "awaiting_primary_review", "summary": evidence.get("summary", evidence.get("error_type", "Uncertain audit"))})
            continue
        # Bind the proof to the actual reference files as well as the candidate.
        hashes = [sha(ref["path"]) for ref in item["references"]] + [row["sha256"]]
        old_paths = evidence.get("item", {}).get("references", [])
        # Older scoped auditors sent a subset of ordered refs; verify THEIR bytes.
        if old_paths:
            actual = [sha(ref["path"]) for ref in old_paths] + [row["sha256"]]
            if actual != evidence["hashes"]:
                raise ValueError("Prior audit reference hash changed")
        elif hashes != evidence["hashes"]:
            raise ValueError("Audit evidence lacks its reference context")
        selected.append({"asset_id": asset, "shot_id": row["shot_id"], "path": row["path"],
                         "sha256": row["sha256"], "location": row.get("location"),
                         "state": "verified", "source": "cli_proxy_vision", "notes": evidence["summary"],
                         "ordered_references": row["references"], "primary_inspection_claimed": False,
                         "proxy_evidence": {k: evidence[k] for k in ("cache_key", "confidence", "checks")} |
                                           {"requires_primary_review": False}})
    return selected, pending, audit_jobs


def prepare_render(film, selected, base):
    if not film.get("automatic_render", False) or len(selected) != len(film["expected"]):
        return "not_ready"
    from app import store
    project = store.get_project(film["project_id"])
    if hashlib.sha256(project["script"].encode()).hexdigest() != film["script_sha256"]:
        raise ValueError("Original script changed")
    voice = project["voiceover"]["file"]
    if sha(inside(film["project_root"], voice)) != film["voice_sha256"]:
        raise ValueError("Original voice changed")
    q = Path(film["directory"]) / "render"
    if (q / "render-started.json").exists():
        return "render_already_reserved"
    worker = Path(film["render_worker"])
    renderer = Path(film["renderer"])
    if sha(worker) != film["render_worker_sha256"] or sha(renderer) != film["renderer_sha256"]:
        raise ValueError("Render implementation changed since contract approval")
    q.mkdir(exist_ok=True)
    images, scenes = [], []
    for selected_row, expected, timing in zip(selected, film["expected"], film["timings"]):
        if selected_row["asset_id"] != expected["asset_id"]:
            raise ValueError("Render selection ordering mismatch")
        scenes.append({"id": timing["id"], "start": timing["start"], "end": timing["end"],
                       "image": selected_row["path"], "sha256": selected_row["sha256"],
                       "asset_id": selected_row["asset_id"], "narration": expected.get("narration", ""),
                       "prompt": expected["prompt"], "references": expected["references"], "motion": "static"})
        images.append({"id": timing["id"], "state": "verified", "path": selected_row["path"],
                       "sha256": selected_row["sha256"], "source": selected_row["source"],
                       "notes": selected_row["notes"], "background_state": "pass"})
    plan = {"key": film["key"], "project_id": film["project_id"], "duration": film["timings"][-1]["end"],
            "voiceover": {"file": voice}, "voice_sha256": film["voice_sha256"],
            "script_sha256": film["script_sha256"], "scenes": scenes, "expected_shots": len(scenes),
            "intro_fade_seconds": 1, "transition_seconds": .5, "outro_fade_seconds": 5, "host": "VPS"}
    write(q / "final-plan.json", plan)
    write(q / "project-before-render.json", project)
    write(q / "visual-review.json", {"state": "attributed_source_reviews_complete", "images": images,
                                    "primary_every_source_claimed": False})
    (q / "render_worker.py").write_bytes(worker.read_bytes())
    (q / "slideshow_render.py").write_bytes(renderer.read_bytes())
    # Reservation precedes launch. A crash never silently creates a second render.
    write(q / "render-started.json", {"state": "reserved", "host": "VPS", "at": time.time()})
    with (q / "render.log").open("ab") as log:
        child = subprocess.Popen(["flock", str(Path(base) / "continuous-render.lock"), sys.executable,
                                  str(q / "render_worker.py"), str(q)], stdout=log, stderr=log,
                                 start_new_session=True, env=os.environ | {"PYTHONPATH": str(Path.cwd())})
    write(q / "render-started.json", {"state": "running_or_waiting_render_slot", "pid": child.pid,
                                     "key": film["key"], "host": "VPS", "at": time.time()})
    return "render_dispatched"


async def tick(config, do_audit=True, reviewer=None):
    base = Path(config["base"])
    if (base / "OWNER_PAUSED.json").exists():
        write(base / "continuous-status.json", {"state": "owner_paused", "at": time.time()})
        return []
    reviewer = reviewer or audit.review
    snapshots, all_jobs = [], []
    for film in config["films"]:
        try:
            validate_contract(film)
            source = receipts(film)
            reviews = previous_reviews(film)
            selected, pending, jobs = select(film, source, reviews)
            snapshot = {"key": film["key"], "expected": len(film["expected"]), "selected": len(selected),
                        "pending": pending, "at": time.time(), "state": "all_sources_pass" if not pending else "in_progress"}
            write(Path(film["directory"]) / "continuous-qc" / "selected.json", selected)
            write(Path(film["directory"]) / "continuous-qc" / "status.json", snapshot)
            snapshots.append(snapshot)
            if not pending:
                snapshot["render"] = prepare_render(film, selected, base)
            all_jobs.extend((film, expected, row, item) for expected, row, item in jobs)
        except (ValueError, KeyError, OSError) as exc:
            snapshots.append({"key": film["key"], "state": "blocked_contract", "error": str(exc)[:300]})
    write(base / "continuous-status.json", {"state": "running", "at": time.time(), "films": snapshots})
    if not do_audit or not all_jobs:
        return snapshots
    # Same global review lock as the existing scoped audits; never multiply calls.
    with exclusive(base / "proxy-audit-global.lock") as locked:
        if not locked:
            return snapshots
        sem = asyncio.Semaphore(min(3, max(1, config.get("audit_concurrency", 3))))

        async def one(film, expected, row, item):
            async with sem:
                if (base / "OWNER_PAUSED.json").exists():
                    return None
                out = Path(film["directory"]) / "continuous-qc" / "evidence"
                result = await reviewer(item, config["audit_model"], out)
                return film, result

        # Small waves start reviewing immediately, keeping status fresh.
        results = await asyncio.gather(*(one(*job) for job in all_jobs[:config.get("audit_wave", 12)]))
        grouped = {}
        for value in results:
            if value is None:
                continue
            film, result = value
            grouped.setdefault(film["key"], (film, []))[1].append(result)
        for film, results in grouped.values():
            out = Path(film["directory"]) / "continuous-qc" / "evidence" / "report.json"
            previous = read(out, {}).get("results", [])
            indexed = {r["cache_key"]: r for r in previous}
            indexed.update({r["cache_key"]: r for r in results})
            write(out, {"source": "cli_proxy_vision", "revision": audit.REVISION,
                        "results": list(indexed.values()), "primary_agent_inspection_claimed": False})
    return snapshots


async def run(config, once=False, do_audit=True):
    if sys.platform == "win32":
        raise RuntimeError("Run production supervision on the VPS only")
    base = Path(config["base"])
    with exclusive(base / "continuous-supervisor.lock") as locked:
        if not locked:
            raise RuntimeError("A supervisor already owns this batch")
        while True:
            try:
                await tick(config, do_audit)
            except Exception as exc:
                # Receipts precede calls, so an ambiguous result remains held.
                # Never let an unrelated status-write failure stop all films.
                write(base / "continuous-supervisor-error.json",
                      {"state": "retrying_supervision_only", "error_type": type(exc).__name__, "at": time.time()})
                if once:
                    raise
            if once:
                break
            await asyncio.sleep(min(30, max(2, config.get("poll_seconds", 10))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(read(args.config), args.once, not args.no_audit))
