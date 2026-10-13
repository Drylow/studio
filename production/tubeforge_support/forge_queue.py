"""Persistent, resource-aware production queue; reviews never auto-approve assets."""
import asyncio
from contextlib import asynccontextmanager
import copy
import uuid

from fastapi import APIRouter, HTTPException
from app import config, pipeline, store
from app.util import now, read_json, write_json
from . import forge_api as forge, workspace_api as api, workspace_generation as generation
from .workspace_identity import identity, current_owner, current_name

_lock = asyncio.Lock()
_task = None
ACTIVE = {"voice", "prepare", "preview", "images", "render"}


def load():
    return read_json(config.DATA / "forge-production-queue.json", {"jobs": []})


def save(data):
    write_json(config.DATA / "forge-production-queue.json", data)


def fingerprint(p):
    return api._hash({"script": p.get("script"), "models": p.get("model_snapshot"),
                      "voice": p.get("settings", {}).get("voice"), "style": p.get("style_snapshot")})


def capacities():
    return {"voice": max(1, config.get_int("TTS_CONCURRENCY")),
            "prepare": min(2, max(1, config.get_int("PROJECT_PARALLEL"))),
            "images": min(2, max(1, config.get_int("PROJECT_PARALLEL"))),
            "render": max(1, config.get_int("RENDER_CONCURRENCY")),
            "projects": max(1, config.get_int("PROJECT_PARALLEL"))}


def resource(stage):
    return "images" if stage in ("images", "preview") else stage


def running_usage(projects, jobs=None):
    usage = {key: 0 for key in capacities()}
    for p in projects:
        pid = p["id"]
        if not forge.status(p)["running"]:
            continue
        usage["projects"] += 1
        if generation.batch_running(pid) or pid in generation._active_projects:
            usage["images"] += 1
        elif (p.get("steps", {}).get("voiceover") or {}).get("state") == "running":
            usage["voice"] += 1
        elif (p.get("steps", {}).get("planning") or {}).get("state") == "running":
            usage["prepare"] += 1
        elif (p.get("steps", {}).get("render") or {}).get("state") == "running":
            usage["render"] += 1
        else:
            reserved = next((j for j in jobs or [] if j['project_id'] == pid and j['state'] == 'running'), None)
            if reserved and resource(reserved.get('stage')) in usage:
                usage[resource(reserved['stage'])] += 1
    return usage


def next_stage(p, automatic_plans):
    if not (p.get("script") or "").strip():
        return None, "awaiting_script", "Save the reviewed narration first"
    if not p.get("voiceover") or p.get("voiceover_stale"):
        return "voice", "queued", "Voice first"
    if not api._file_digest(store.project_dir(p["id"]), p["voiceover"].get("file")):
        return None, "blocked", "Saved voice file is missing; inspect before a paid retry"
    if not p.get("scenes"):
        from . import workspace_planning
        if automatic_plans and workspace_planning.allowed(p):
            return "prepare", "queued", "Prepare shots against the actual audio clock"
        return None, "awaiting_authoring", "Import authored shots and inspected references"
    scenes = p["scenes"]
    if any(not s.get("image") for s in scenes[:3]):
        return "preview", "queued", "Generate three preview shots"
    full = api._full(p)
    if any(s["human_review"]["state"] != "verified" for s in full["scenes"][:3]):
        return None, "awaiting_preview_review", "Inspect and review the first three images"
    if any(not s.get("image") for s in scenes[3:]):
        return "images", "queued", "Generate the remaining missing images"
    if (any(s["human_review"]["state"] != "verified" for s in full["scenes"])
            or full["human_reviews"]["voiceover"]["state"] != "verified"):
        return None, "awaiting_review", "Inspect every image and check audio/timing"
    if not full["technical_ready"]:
        return None, "blocked", "; ".join(str(v) for v in full["technical_issues"])[:500]
    if not p.get("render"):
        return "render", "queued", "Render the verified edit on VPS CPU"
    if full["human_reviews"]["render"]["state"] != "verified":
        return None, "awaiting_final_review", "Rendered; inspect the final edit before publication"
    return None, "done", "Current edit and reviews complete"


async def tick(app):
    async with _lock:
        data = load()
        projects = {p["id"]: p for p in store.list_projects()}
        usage, limits = running_usage(projects.values(), data['jobs']), capacities()
        jobs = sorted(data["jobs"], key=lambda j: (-j.get("priority", 0), j.get("last_dispatch", 0), j["created"]))
        for job in jobs:
            if job["state"] in ("cancelled", "interrupted", "failed", "changed", "done"):
                continue
            p = projects.get(job["project_id"])
            if not p or p.get("archived"):
                job.update(state="blocked", message="Project missing or archived"); continue
            if fingerprint(p) != job["input_hash"]:
                job.update(state="changed", message="Script, voice or frozen preset changed; inspect and explicitly resume"); continue
            if forge.status(p)["running"]:
                if job.get("stage"):
                    job.update(state="running", message="Native stage active")
                else:
                    job.update(state="waiting_external_job", message="Existing project job is active")
                continue
            if job["state"] == "running":
                step = {"voice": "voiceover", "prepare": "planning", "render": "render"}.get(job["stage"])
                failed = (p.get("steps", {}).get(step) or {}).get("state") == "error" if step else (
                    (p.get("workspace_batch") or {}).get("state") != "done")
                if failed or p.get("error"):
                    job.update(state="failed", message="Stage failed or stopped; saved outputs kept, no automatic paid retry")
                    continue
                job.setdefault("completed_stages", []).append(job["stage"])
                job["stage"] = None
            stage, state, message = next_stage(p, job["automatic_plans"])
            job.update(state=state, message=message)
            if not stage:
                continue
            lane = resource(stage)
            if usage[lane] >= limits[lane] or usage["projects"] >= limits["projects"]:
                job.update(state="queued", message=f"Waiting for {lane} capacity")
                continue
            # Save the reservation BEFORE the billable request. On restart it holds
            # for explicit inspection rather than silently replaying an uncertain call.
            job.update(state="running", stage=stage, last_dispatch=now(), message="Starting " + stage)
            save(data)
            marker = identity.set({"username": job["member_id"], "display_name": job["member_name"]})
            try:
                body = {}
                if lane == "images":
                    provider = (p.get("model_snapshot") or {}).get("image_provider", "cli_proxy")
                    body["concurrency"] = min(generation.batch_concurrency(provider, "preview" if stage == "preview" else "remaining"),
                        max(1, generation.batch_concurrency(provider, "remaining") // limits["images"]))
                await forge.invoke(app, forge.PREFIX + "/videos/{pid}/actions/{action}", pid=p["id"], action=stage, body=body)
                usage[lane] += 1; usage["projects"] += 1
            except HTTPException as exc:
                job.update(state="blocked" if exc.status_code in (409, 422) else "failed", stage=None,
                           message=str(exc.detail)[:500])
            except Exception:
                job.update(state="interrupted", message="Uncertain dispatch result; inspect the native project before resuming")
            finally:
                identity.reset(marker)
        save(data)


async def run(app):
    data = load()
    for job in data["jobs"]:
        if job["state"] == "running":
            job.update(state="interrupted", message="Server restarted during dispatch; inspect outputs before explicit resume")
    save(data)
    while True:
        try:
            await tick(app)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Preserve queue; a transient scheduler error never retries a paid stage.
            await asyncio.sleep(5)
        await asyncio.sleep(3)


def install(app):
    if getattr(app.state, "forge_queue_installed", False):
        return
    router = APIRouter(prefix=forge.PREFIX, tags=["Production queue"])

    @router.get("/queue")
    async def queue():
        data = load()
        return data | {"limits": capacities(), "usage": running_usage(store.list_projects(), data['jobs']),
                       "poll_after_seconds": 5}

    @router.post("/queue", status_code=202)
    async def enqueue(body: dict):
        pids = body.get("project_ids")
        if (not isinstance(pids, list) or not 1 <= len(pids) <= 100
                or any(not isinstance(v, str) for v in pids) or len(set(pids)) != len(pids)):
            raise HTTPException(422, "Provide 1–100 distinct project_ids")
        automatic = body.get("automatic_plans", True)
        if type(automatic) is not bool:
            raise HTTPException(422, "automatic_plans must be a boolean")
        prepared = [api._project(pid) for pid in pids]
        async with _lock:
            data = load(); output = []
            for p in prepared:
                existing = next((j for j in data["jobs"] if j["project_id"] == p["id"] and
                                 j["state"] != "cancelled"), None)
                if existing:
                    output.append(existing); continue
                job = {"id": uuid.uuid4().hex, "project_id": p["id"], "title": p.get("title"),
                       "member_id": current_owner(), "member_name": current_name(), "created": now(),
                       "input_hash": fingerprint(p), "automatic_plans": automatic, "priority": 0,
                       "state": "queued", "stage": None, "message": "Queued", "completed_stages": []}
                data["jobs"].append(job); output.append(job)
            save(data)
        return {"jobs": output}

    @router.post("/queue/{jid}/resume")
    async def resume(jid: str):
        async with _lock:
            data = load(); job = next((j for j in data["jobs"] if j["id"] == jid), None)
            if not job: raise HTTPException(404, "Queue job not found")
            p = api._project(job["project_id"])
            if forge.status(p)["running"]: raise HTTPException(409, "Native job is still active")
            job.update(state="queued", stage=None, message="Explicitly resumed", input_hash=fingerprint(p))
            save(data)
        return job

    @router.post("/queue/{jid}/cancel")
    async def cancel(jid: str):
        async with _lock:
            data = load(); job = next((j for j in data["jobs"] if j["id"] == jid), None)
            if not job: raise HTTPException(404, "Queue job not found")
            if job["state"] == "running":
                await forge.invoke(app, forge.PREFIX + "/videos/{pid}/stop", pid=job["project_id"])
            job.update(state="cancelled", message="Cancelled; submitted provider calls may finish")
            save(data)
        return job

    static = next((i for i, r in enumerate(app.routes) if getattr(r, "path", None) == ""), len(app.routes))
    app.router.routes[static:static] = router.routes
    previous = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        global _task
        async with previous(application):
            _task = asyncio.create_task(run(application))
            try:
                yield
            finally:
                _task.cancel()
                await asyncio.gather(_task, return_exceptions=True)
    app.router.lifespan_context = lifespan
    app.state.forge_queue_installed = True
