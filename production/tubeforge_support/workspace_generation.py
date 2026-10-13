"""Execute authored images in two review stages, then render verified assets."""
import asyncio
import copy
import hashlib
import io
import uuid
from collections import OrderedDict

from fastapi import APIRouter, HTTPException
from PIL import Image

from app import config, google_flow, llm, pipeline, store
from app.util import now
from . import workspace_api as api


_active_projects = set()
_active_generations = {}
_batch_permits = {}
_batch_tasks = {}
_reference_payloads = OrderedDict()
_reference_payload_bytes = 0
_REFERENCE_PAYLOAD_LIMIT = 64 * 1024 * 1024


def _reference_payload(path, source_hash):
    """Reuse upload encoding only after the caller verifies the exact source bytes."""
    global _reference_payload_bytes
    key = (str(path.resolve()), source_hash)
    if key in _reference_payloads:
        _reference_payloads.move_to_end(key)
        return _reference_payloads[key]
    payload = llm.png_for_upload(path)
    if len(payload) <= _REFERENCE_PAYLOAD_LIMIT:
        while _reference_payloads and _reference_payload_bytes + len(payload) > _REFERENCE_PAYLOAD_LIMIT:
            _, previous = _reference_payloads.popitem(last=False)
            _reference_payload_bytes -= len(previous)
        _reference_payloads[key] = payload
        _reference_payload_bytes += len(payload)
    return payload


def batch_concurrency(provider, phase):
    """Provider-wide semaphore remains the ceiling across all team projects."""
    key = 'USEAPI_IMAGE_CONCURRENCY' if provider == 'google_flow' else 'IMAGE_CONCURRENCY'
    ceiling = 3 if provider == 'google_flow' else 36
    try:
        value = max(1, min(ceiling, int(config.get(key) or ceiling)))
    except (TypeError, ValueError):
        value = ceiling
    return min(value, 3) if phase == 'preview' else value


def batch_running(pid):
    task = _batch_tasks.get(pid)
    return bool(task and not task.done())


def batch_status(p):
    status = copy.deepcopy(p.get("workspace_batch"))
    if status and status.get("state") in ("queued", "running", "stopping") and not batch_running(p["id"]):
        status.update(state="interrupted", error="The server was restarted. Check the last shot before resuming.")
    return status


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scene(p, sid):
    scene = next((s for s in p.get("scenes", []) if s["id"] == sid), None)
    if not scene:
        raise HTTPException(404, "Plan not found")
    return scene


def _signature(p, s):
    from . import workspace_characters
    from . import workspace_locations
    evidence = {"script": p.get("script"), "models": p.get("model_snapshot"),
                      "style": p.get("style_id"),
                      "cast_registry": workspace_characters.registry(p),
                      "aspect": p["settings"]["visuals"].get("aspect"),
                      "scene": {key: s.get(key) for key in (
                          "id", "text", "prompt", "prompt_author", "location_id", "characters",
                          "references", "character_variants", "workspace_regeneration_required",
                          "start", "end", "motion", "image")}}
    evidence['scene'].update({key: s[key] for key in workspace_locations.SCENE_KEYS if key in s})
    if workspace_locations.mode(p) == 'consistent' and workspace_locations.registry(p):
        evidence['location_registry'] = workspace_locations.registry(p)
    return api._hash(evidence)


def _same_inputs(p, scene, signature):
    try:
        return scene is not None and _signature(p, scene) == signature
    except Exception:
        # Invalidated authoring metadata cannot discard the receipt of a paid output.
        return False


def _prepare(p, s, body):
    from . import workspace_planning, workspace_composition, workspace_characters, workspace_locations
    prompt = s.get("prompt")
    if (not isinstance(prompt, str) or not prompt.strip() or "renderer-only import" in prompt.lower()
            or not (s.get("prompt_author") == "codex" or workspace_planning.authored(p, s)) or not s.get("location_id")
            or not isinstance(s.get("text"), str) or not s["text"].strip()
            or s["text"] not in p.get("script", "") or not isinstance(s.get("characters"), list)
            or any(not isinstance(c, str) or not c.strip() for c in s["characters"])):
        raise HTTPException(422, "This shot must have narration, a location, named characters, and a prompt written by Codex")
    if body.get("confirm_prompt") != prompt:
        raise HTTPException(409, "The confirmed prompt does not match the exact saved prompt")
    model = (p.get("model_snapshot") or {}).get("image_model")
    if not isinstance(model, str) or not model or body.get("image_model") != model:
        raise HTTPException(409, "Confirm the image model saved in this project")
    provider = (p.get("model_snapshot") or {}).get("image_provider", "cli_proxy")
    if body.get("image_provider", provider) != provider:
        raise HTTPException(409, "The confirmed provider does not match the project's provider")
    api._check_image_provider(provider, p.get("style_id"))
    api._validate_drawing_reference(p, s)
    if provider == "google_flow" and not google_flow.configured():
        raise HTTPException(503, "Google Flow is not configured")
    if provider == "cli_proxy" and (not config.get("PROXY_API_KEY") or not config.get("PROXY_BASE_URL")):
        raise HTTPException(503, "The Proxy CLI is not configured")
    if provider not in ("cli_proxy", "google_flow"):
        raise HTTPException(422, "Unknown image provider")
    refs = s.get("references")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, dict) for ref in refs):
        raise HTTPException(422, "Save at least one real reference, in the exact order to send")
    if workspace_planning.allowed(p):
        workspace_characters.validate(p, s)
    workspace_locations.validate(p, s)
    payloads, sources, receipts = [], [], []
    for index, ref in enumerate(refs):
        path = api._reference_path(p, s, index)
        source_hash = _digest(path)
        if ref.get("sha256") and source_hash != ref["sha256"]:
            raise HTTPException(409, "A reference has been modified since it was prepared")
        payload = _reference_payload(path, source_hash)
        if _digest(path) != source_hash:
            raise HTTPException(409, "A reference changed while it was being read")
        payloads.append(payload)
        sources.append((path, source_hash))
        receipts.append({"path": ref["path"], "owner": ref.get("owner", "project"),
                         "role": ref.get("role"), "sha256": source_hash,
                         "character": ref.get("character"), "variant": ref.get("variant"),
                         "location_id": ref.get("location_id"), "location_view": ref.get("location_view"),
                         "source_sha256": source_hash, "sent_sha256": hashlib.sha256(payload).hexdigest()})
    aspect = p["settings"]["visuals"].get("aspect", "16:9")
    if workspace_planning.allowed(p):
        if aspect != "16:9" or workspace_composition.contradictory(prompt):
            raise HTTPException(422, "Shots in this channel must be full-frame landscape 16:9, with no vertical composition or superimposed character")
    if aspect not in llm.ASPECTS:
        raise HTTPException(422, "The saved aspect ratio is not supported")
    return prompt, model, aspect, payloads, sources, receipts


def _other_generations(pid, sid=None):
    return [record for (project, scene), record in _active_generations.items()
            if project == pid and scene != sid]


async def generate(pid, sid, body, *, batch_id=None):
    # The executor applies its own narrow authorization; other writable APIs stay locked.
    p = api._project(pid)
    authorized_batch = (batch_id is not None and batch_running(pid)
                        and (p.get("workspace_batch") or {}).get("id") == batch_id
                        and _batch_permits.get((pid, sid)) == batch_id)
    other = _other_generations(pid, sid)
    limit = (p.get('workspace_batch') or {}).get('concurrency', 1) if authorized_batch else 1
    if (pipeline.is_running(pid) or (pid, sid) in _active_generations
            or not authorized_batch and (pid in _active_projects or batch_running(pid)
                or any(s.get("status") in ("running", "queued") for s in p.get("scenes", []))
                or any(step.get("state") == "running" for step in p.get("steps", {}).values()))
            or authorized_batch and (len(other) >= limit or any(r.get("batch_id") != batch_id for r in other)
                or pid in _active_projects and not other
                or any(step.get("state") == "running" for key, step in p.get("steps", {}).items() if key != "visuals")
                or any(s.get("status") in ("running", "queued") and (pid, s["id"]) not in _active_generations
                       for s in p.get("scenes", [])))):
        raise HTTPException(409, "A task is already running on this project")
    s = _scene(p, sid)
    try:
        prompt, model, aspect, payloads, sources, references = _prepare(p, s, body)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "A reference is unreadable; check the shot files") from None
    signature = _signature(p, s)
    previous_image = {"path": s.get("image"), "sha256": api._file_digest(store.project_dir(pid), s.get("image")),
                      "human_review": copy.deepcopy(s.get("human_review")),
                      "generation_receipt": copy.deepcopy(s.get("generation_receipt"))}
    previous_render = copy.deepcopy(p.get("render"))
    job_id = uuid.uuid4().hex
    provider = (p.get("model_snapshot") or {}).get("image_provider", "cli_proxy")
    receipt = {"id": job_id, "prompt": prompt, "model": model, "aspect": aspect,
               "references": references, "transport": provider,
               "endpoint": "/v1/google-flow/images" if provider == "google_flow" else "/images/edits",
               "started_at": now(), "state": "running", "previous_image": previous_image}
    _active_projects.add(pid)
    _active_generations[(pid, sid)] = {"id": job_id, "scene_id": sid, "batch_id": batch_id}
    succeeded = False
    try:
        s.update(status="running", generation_id=job_id, error=None)
        p["workspace_generation"] = {"id": job_id, "scene_id": sid, "state": "running", "batch_id": batch_id}
        p.setdefault("workspace_generations", {})[str(sid)] = copy.deepcopy(p["workspace_generation"])
        p["render"] = None
        p["steps"]["visuals"].update(state="running", msg="Confirmed shot generation")
        store.save_project(p)
        # Nonempty refs route this existing helper to /images/edits. No composition or rewrite.
        extra = {"provider": provider, "receipt": receipt.setdefault("provider_receipt", {})} if provider == "google_flow" else {}
        data = await llm.generate_image(prompt, model=model, aspect=aspect, refs=payloads,
                                        attempts=1, label=f"Directed shot {sid}", **extra)
        with Image.open(io.BytesIO(data)) as image:
            extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(image.format)
            image.verify()
        if not extension:
            raise ValueError("Unsupported output image")
        relative = f"images/{sid:03d}-directed-{job_id}{extension}"
        destination = store.project_dir(pid) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)
        receipt.update(image={"path": relative, "sha256": hashlib.sha256(data).hexdigest()}, finished_at=now())
        current = api._project(pid)
        scene = next((x for x in current.get("scenes", []) if x["id"] == sid), None)
        if not _same_inputs(current, scene, signature) or any(
                api._file_digest(path.parent, path.name) != digest for path, digest in sources):
            receipt["state"] = "obsolete_unselected"
            current.setdefault("workspace_generation_history", []).append(receipt)
            store.save_project(current)
            raise HTTPException(409, "The shot or its references have changed; the image is kept but not selected")
        receipt["state"] = "generated_unreviewed"
        scene.setdefault("generation_history", []).append(copy.deepcopy(receipt))
        scene.update(image=relative, status="done", uploaded=False, error=None, generation_receipt=receipt,
                     sent_references=copy.deepcopy(references),
                     human_review={"state": "unreviewed", "notes": "New image to watch with its references"})
        scene.pop("workspace_regeneration_required", None)
        scene.pop("clip", None)
        current["render"] = None
        if previous_render and previous_render not in current.get("render_history", []):
            current.setdefault("render_history", []).append(previous_render)
        if (current.get("workspace_generation") or {}).get("id") == job_id:
            current["workspace_generation"]["state"] = "generated_unreviewed"
        record = current.setdefault("workspace_generations", {}).setdefault(str(sid), {
            "id": job_id, "scene_id": sid, "batch_id": batch_id})
        if record.get("id") == job_id:
            record["state"] = "generated_unreviewed"
        current["steps"]["visuals"].update(
            state="running" if _other_generations(pid, sid) else (
                "done" if all(x.get("image") for x in current["scenes"]) else "idle"),
            msg="New image to check")
        current["steps"]["render"].update(state="idle", msg="Image modified: the edit still needs to be redone")
        store.save_project(current)
        succeeded = True
        return api._full(current)
    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise
    except google_flow.FlowError as error:
        safe = HTTPException(502, str(error))
        safe.workspace_safe_detail = True  # FlowError is already sanitized by our transport.
        safe.workspace_global_configuration_error = getattr(error, "global_configuration_error", False)
        raise safe from None
    except Exception:
        raise HTTPException(502, "Shot generation failed; no automatic correction was applied") from None
    finally:
        _active_generations.pop((pid, sid), None)
        if not _other_generations(pid):
            _active_projects.discard(pid)
        if not succeeded:
            current = store.get_project(pid)
            if current:
                current = copy.deepcopy(current)
                # Keep known upstream outcomes recoverable without replaying a paid call.
                # The transport can know a job ID before a subsequent media read fails.
                history = current.setdefault('workspace_generation_history', [])
                if not any(item.get('id') == job_id for item in history):
                    receipt.update(state='failed_unselected', finished_at=now())
                    history.append(copy.deepcopy(receipt))
                scene = next((x for x in current.get("scenes", []) if x["id"] == sid), None)
                if scene and scene.get("generation_id") == job_id:
                    scene.update(status="error", error="Generation interrupted or failed; the previous shot is kept")
                    if (not _other_generations(pid) and (not authorized_batch or limit == 1)
                            and _same_inputs(current, scene, signature) and current.get("render") is None):
                        current["render"] = previous_render
                if (current.get("workspace_generation") or {}).get("id") == job_id:
                    current["workspace_generation"]["state"] = "failed"
                record = current.get("workspace_generations", {}).get(str(sid), {})
                if record.get("id") == job_id:
                    record["state"] = "failed"
                current["steps"]["visuals"].update(
                    state="running" if _other_generations(pid) else "error", msg="This shot still needs correction")
                store.save_project(current)


def _batch_signature(p):
    frozen = copy.deepcopy(p)
    for scene in frozen.get("scenes", []):
        scene.pop("image", None)
        scene.pop("workspace_regeneration_required", None)
    return api._generation_confirmation(frozen)


def _missing(p, scene):
    return scene.get("workspace_regeneration_required") is True or not api._file_digest(
        store.project_dir(p["id"]), scene.get("image"))


def _preview_verified(p):
    return all(api._review(s.get("human_review"), api._scene_evidence(p, s))["state"] == "verified"
               for s in p.get("scenes", [])[:3])


def _recover_batch(p):
    previous = p.get("workspace_batch") or {}
    if previous.get("state") in ("queued", "running", "stopping") and not batch_running(p["id"]):
        previous.update(state="interrupted", finished_at=now())
        records = list((p.get("workspace_generations") or {}).values()) + [p.get("workspace_generation") or {}]
        for generation in records:
            if generation.get("batch_id") == previous.get("id"):
                for scene in p.get("scenes", []):
                    if scene.get("generation_id") != generation.get("id") or scene.get("status") != "running":
                        continue
                    scene.update(status="error", error="Generation interrupted: check the result before resuming")
                generation["state"] = "failed"
                p["steps"]["visuals"].update(state="error")
        store.save_project(p)


async def start_batch(pid, body):
    p = api._project(pid, writable=True)
    if batch_running(pid) or pid in _active_projects:
        raise HTTPException(409, "A generation is already in progress for this project")
    _recover_batch(p)
    if (any(s.get("status") in ("running", "queued") for s in p.get("scenes", []))
            or any(step.get("state") == "running" for step in p.get("steps", {}).values())):
        raise HTTPException(409, "A task is already running on this project")
    phase = body.get("phase")
    if phase not in ("preview", "remaining", "corrections"):
        raise HTTPException(422, "Choose the test of the first three shots, the remaining images, or the corrections")
    if body.get("confirmation") != api._generation_confirmation(p):
        raise HTTPException(409, "The project has changed. Refresh before starting generation")
    scenes = p.get("scenes", [])
    if not scenes:
        raise HTTPException(422, "First save the breakdown and prompts written by Codex")
    if phase in ("remaining", "corrections") and not _preview_verified(p):
        raise HTTPException(409, "Watch and mark the first three shots as verified before continuing")
    candidates = scenes[:3] if phase == "preview" else scenes[3:]
    targets = [s for s in candidates if (s.get("workspace_regeneration_required") is True
                                       if phase == "corrections" else _missing(p, s))]
    if not targets:
        raise HTTPException(409, "No shot is marked for correction" if phase == "corrections"
                            else "All images for this step already exist")
    model = (p.get("model_snapshot") or {}).get("image_model")
    provider = (p.get("model_snapshot") or {}).get("image_provider", "cli_proxy")
    if body.get("image_model") != model or body.get("image_provider", provider) != provider:
        raise HTTPException(409, "The project model or provider has changed")
    # Validate the entire requested batch before the first billable request.
    sources = {}
    for scene in targets:
        try:
            prepared = _prepare(p, scene, {"confirm_prompt": scene.get("prompt"), "image_model": model,
                                          "image_provider": provider})
            sources.update(dict(prepared[4]))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, f"A reference for shot {scene['id']} is unreadable") from None
    job = {"id": uuid.uuid4().hex, "phase": phase, "state": "queued", "started_at": now(),
           "scene_ids": [s["id"] for s in targets], "done": 0, "total": len(targets),
           "current_scene_id": None, "current_scene_ids": [], "stop_requested": False, "error": None,
           "concurrency": batch_concurrency(provider, phase),
           "processed": 0, "failed_scene_ids": [], "scene_errors": {}}
    requested = body.get('concurrency', job['concurrency'])
    if type(requested) is not int or not 1 <= requested <= job['concurrency']:
        raise HTTPException(422, 'Batch concurrency must be a positive integer within the shared limit')
    job['concurrency'] = requested
    if p.get("render") and p["render"] not in p.get("render_history", []):
        p.setdefault("render_history", []).append(copy.deepcopy(p["render"]))
    p["workspace_batch"] = job
    store.save_project(p)
    _batch_tasks[pid] = asyncio.create_task(_run_batch(pid, job["id"], _batch_signature(p), sources))
    return api._full(p)


def _update_batch(pid, job_id, **changes):
    p = api._project(pid)
    if (p.get("workspace_batch") or {}).get("id") != job_id:
        raise HTTPException(409, "The generation batch has changed")
    p["workspace_batch"].update(changes)
    store.save_project(p)
    return p


def _check_batch_inputs(p, signature, sources):
    if (_batch_signature(p) != signature
            or any(api._file_digest(path.parent, path.name) != digest for path, digest in sources.items())):
        raise HTTPException(409, "The breakdown, model, or references have changed. The batch was stopped")
    if p["workspace_batch"]["phase"] in ("remaining", "corrections") and not _preview_verified(p):
        raise HTTPException(409, "Validation of the first three shots has changed. The batch was stopped")


def _correction_error(exc):
    if getattr(exc, "workspace_safe_detail", False):
        return str(exc.detail)[:500]
    if exc.detail == "Shot generation failed; no automatic correction was applied":
        return exc.detail
    # A raw HTTPException from an upstream client must not expose its response body.
    return f"The attempt for this shot failed (HTTP {exc.status_code}). The previous image is kept; no new automatic attempt."


def _collect_batch_result(pid, job_id, sid, task):
    """Read current state and save without an await: sibling results cannot be lost."""
    failure = None
    try:
        task.result()
    except HTTPException as exc:
        failure = exc
    except BaseException:
        failure = HTTPException(502, "Shot generation failed; no automatic correction was applied")
    current = api._project(pid)
    job = current["workspace_batch"]
    if failure:
        _update_batch(pid, job_id, failed_scene_ids=job["failed_scene_ids"] + [sid],
                      scene_errors=dict(job["scene_errors"], **{str(sid): _correction_error(failure)}))
    else:
        _update_batch(pid, job_id, done=job["done"] + 1)
    _batch_permits.pop((pid, sid), None)
    return failure


async def _run_batch(pid, job_id, signature, sources):
    state, error = "done", None
    pending = {}
    try:
        p = _update_batch(pid, job_id, state="running")
        job = p["workspace_batch"]
        scene_ids, limit = job["scene_ids"], job["concurrency"]
        correction = job["phase"] == "corrections"
        next_index, halted = 0, False
        while pending or next_index < len(scene_ids) and not halted:
            while not halted and next_index < len(scene_ids) and len(pending) < limit:
                current = api._project(pid)
                if current["workspace_batch"].get("stop_requested"):
                    state, halted = "stopped", True
                    break
                _check_batch_inputs(current, signature, sources)
                sid = scene_ids[next_index]
                scene = _scene(current, sid)
                # Selected images only change for explicitly missing/flagged targets.
                if not _missing(current, scene) or correction and scene.get("workspace_regeneration_required") is not True:
                    raise HTTPException(409, "The shot selection has changed. The batch was stopped")
                _batch_permits[(pid, sid)] = job_id
                task = asyncio.create_task(generate(pid, sid, {"confirm_prompt": scene["prompt"],
                    "image_model": current["model_snapshot"]["image_model"],
                    "image_provider": current["model_snapshot"].get("image_provider", "cli_proxy")}, batch_id=job_id))
                pending[task] = sid
                active_ids = list(pending.values())
                _update_batch(pid, job_id, processed=current["workspace_batch"]["processed"] + 1,
                              current_scene_ids=active_ids, current_scene_id=active_ids[0])
                next_index += 1
            if not pending:
                break
            completed, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in sorted(completed, key=lambda item: scene_ids.index(pending[item])):
                sid = pending.pop(task)
                failure = _collect_batch_result(pid, job_id, sid, task)
                # Global account configuration cannot be fixed by trying another scene.
                # Close admission, but drain the already-started billable calls as usual.
                if failure and (getattr(failure, "workspace_global_configuration_error", False)
                                or not correction and not halted):
                    state, error, halted = "failed", _correction_error(failure), True
            current = api._project(pid)
            active_ids = list(pending.values())
            _update_batch(pid, job_id, current_scene_ids=active_ids,
                          current_scene_id=active_ids[0] if active_ids else None)
            _check_batch_inputs(current, signature, sources)
            if current["workspace_batch"].get("stop_requested"):
                state, halted = "stopped", True
        latest = api._project(pid)
        if state == "done" and latest["workspace_batch"].get("failed_scene_ids"):
            state = "done_with_errors"
            error = f"{len(latest['workspace_batch']['failed_scene_ids'])} shot(s) remain to be fixed; no new automatic attempt."
    except asyncio.CancelledError:
        state, error = "interrupted", "Generation interrupted. Check the last shots before resuming"
    except HTTPException as exc:
        state, error = "failed", str(exc.detail)
    except Exception:
        state, error = "failed", "The batch failed. Completed images are kept; no new automatic attempt"
    finally:
        # Stop/cancel/input errors close admission, but already-started billable calls finish.
        if pending:
            drain = asyncio.gather(*pending, return_exceptions=True)
            while not drain.done():
                try:
                    await asyncio.shield(drain)
                except asyncio.CancelledError:
                    state = "interrupted"
            for task, sid in list(pending.items()):
                _collect_batch_result(pid, job_id, sid, task)
        try:
            if api._project(pid)["workspace_batch"].get("stop_requested"):
                state = "stopped"
            _update_batch(pid, job_id, state=state, error=error, current_scene_id=None,
                          current_scene_ids=[], finished_at=now())
        finally:
            for key, permit in list(_batch_permits.items()):
                if key[0] == pid and permit == job_id:
                    _batch_permits.pop(key, None)
            _batch_tasks.pop(pid, None)


def install(app):
    if getattr(app.state, "workspace_generation_installed", False):
        return
    router = APIRouter(prefix="/api/workspace")

    @router.post("/projects/{pid}/scenes/{sid}/generate")
    async def generate_scene(pid: str, sid: int, body: dict):
        return await generate(pid, sid, body)

    @router.post("/projects/{pid}/images/generate", status_code=202)
    async def generate_images(pid: str, body: dict):
        return await start_batch(pid, body)

    @router.post("/projects/{pid}/images/stop")
    async def stop_images(pid: str):
        p = api._project(pid)
        if not batch_running(pid):
            raise HTTPException(409, "No generation batch is in progress")
        p["workspace_batch"].update(stop_requested=True, state="stopping")
        store.save_project(p)
        return api._full(p)

    @router.post("/projects/{pid}/render", status_code=202)
    async def render_project(pid: str):
        p = api._project(pid, writable=True)
        if batch_running(pid) or pid in _active_projects:
            raise HTTPException(409, "Wait for image generation to finish")
        full = api._full(p)
        if (not full["technical_ready"] or not full["scenes"]
                or any(s["human_review"]["state"] != "verified" for s in full["scenes"])
                or full["human_reviews"]["voiceover"]["state"] != "verified"):
            raise HTTPException(409, "Check the voice, images, and timings before starting the edit")
        pipeline.start(pid, pipeline.do_render)
        return api._full(api._project(pid))

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_generation_installed = True
