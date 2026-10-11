"""Execute authored images in two review stages, then render verified assets."""
import asyncio
import copy
import hashlib
import io
import uuid

from fastapi import APIRouter, HTTPException
from PIL import Image

from app import config, google_flow, llm, pipeline, store
from app.util import now
from . import workspace_api as api


_active_projects = set()
_batch_tasks = {}


def batch_running(pid):
    task = _batch_tasks.get(pid)
    return bool(task and not task.done())


def batch_status(p):
    status = copy.deepcopy(p.get("workspace_batch"))
    if status and status.get("state") in ("queued", "running", "stopping") and not batch_running(p["id"]):
        status.update(state="interrupted", error="Le serveur a été redémarré. Vérifiez le dernier plan avant de reprendre.")
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
        raise HTTPException(404, "Plan introuvable")
    return scene


def _signature(p, s):
    from . import workspace_characters
    return api._hash({"script": p.get("script"), "models": p.get("model_snapshot"),
                      "style": p.get("style_id"),
                      "cast_registry": workspace_characters.registry(p),
                      "aspect": p["settings"]["visuals"].get("aspect"),
                      "scene": {key: s.get(key) for key in (
                          "id", "text", "prompt", "prompt_author", "location_id", "characters",
                          "references", "character_variants", "workspace_regeneration_required",
                          "start", "end", "motion", "image")}})


def _prepare(p, s, body):
    from . import workspace_planning, workspace_composition, workspace_characters
    prompt = s.get("prompt")
    if (not isinstance(prompt, str) or not prompt.strip() or "renderer-only import" in prompt.lower()
            or not (s.get("prompt_author") == "codex" or workspace_planning.authored(p, s)) or not s.get("location_id")
            or not isinstance(s.get("text"), str) or not s["text"].strip()
            or s["text"] not in p.get("script", "") or not isinstance(s.get("characters"), list)
            or any(not isinstance(c, str) or not c.strip() for c in s["characters"])):
        raise HTTPException(422, "Ce plan doit avoir une narration, un lieu, des personnages nommés et un prompt écrit par Codex")
    if body.get("confirm_prompt") != prompt:
        raise HTTPException(409, "Le prompt confirmé ne correspond pas au prompt exact enregistré")
    model = (p.get("model_snapshot") or {}).get("image_model")
    if not isinstance(model, str) or not model or body.get("image_model") != model:
        raise HTTPException(409, "Confirmez le modèle image enregistré dans ce projet")
    provider = (p.get("model_snapshot") or {}).get("image_provider", "cli_proxy")
    if body.get("image_provider", provider) != provider:
        raise HTTPException(409, "Le fournisseur confirmé ne correspond pas à celui du projet")
    api._check_image_provider(provider)
    if provider == "google_flow" and not google_flow.configured():
        raise HTTPException(503, "Google Flow n'est pas configuré")
    if provider == "cli_proxy" and (not config.get("PROXY_API_KEY") or not config.get("PROXY_BASE_URL")):
        raise HTTPException(503, "Le CLI Proxy n'est pas configuré")
    if provider not in ("cli_proxy", "google_flow"):
        raise HTTPException(422, "Fournisseur image inconnu")
    refs = s.get("references")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, dict) for ref in refs):
        raise HTTPException(422, "Enregistrez au moins une référence réelle, dans l'ordre exact à envoyer")
    if workspace_planning.allowed(p):
        workspace_characters.validate(p, s)
    payloads, sources, receipts = [], [], []
    for index, ref in enumerate(refs):
        path = api._reference_path(p, s, index)
        source_hash = _digest(path)
        if ref.get("sha256") and source_hash != ref["sha256"]:
            raise HTTPException(409, "Une référence a été modifiée depuis sa préparation")
        payload = llm.png_for_upload(path)
        if _digest(path) != source_hash:
            raise HTTPException(409, "Une référence a changé pendant sa lecture")
        payloads.append(payload)
        sources.append((path, source_hash))
        receipts.append({"path": ref["path"], "owner": ref.get("owner", "project"),
                         "role": ref.get("role"), "sha256": source_hash,
                         "character": ref.get("character"), "variant": ref.get("variant"),
                         "source_sha256": source_hash, "sent_sha256": hashlib.sha256(payload).hexdigest()})
    aspect = p["settings"]["visuals"].get("aspect", "16:9")
    if workspace_planning.allowed(p):
        if aspect != "16:9" or workspace_composition.contradictory(prompt):
            raise HTTPException(422, "Les plans de cette chaîne doivent être plein cadre paysage 16:9, sans composition verticale ni personnage en surimpression")
    if aspect not in llm.ASPECTS:
        raise HTTPException(422, "Le format d'image enregistré n'est pas pris en charge")
    return prompt, model, aspect, payloads, sources, receipts


async def generate(pid, sid, body, *, batch_id=None):
    p = api._project(pid, writable=True)
    if (pid in _active_projects or pipeline.is_running(pid)
            or batch_running(pid) and (p.get("workspace_batch") or {}).get("id") != batch_id
            or any(s.get("status") in ("running", "queued") for s in p.get("scenes", []))
            or any(step.get("state") == "running" for step in p.get("steps", {}).values())):
        raise HTTPException(409, "Une tâche est déjà en cours sur ce projet")
    s = _scene(p, sid)
    try:
        prompt, model, aspect, payloads, sources, references = _prepare(p, s, body)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Une référence est illisible ; vérifiez les fichiers du plan") from None
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
    succeeded = False
    try:
        s.update(status="running", generation_id=job_id, error=None)
        p["workspace_generation"] = {"id": job_id, "scene_id": sid, "state": "running", "batch_id": batch_id}
        p["render"] = None
        p["steps"]["visuals"].update(state="running", msg="Génération du plan confirmé")
        store.save_project(p)
        # Nonempty refs route this existing helper to /images/edits. No composition or rewrite.
        extra = {"provider": provider, "receipt": receipt.setdefault("provider_receipt", {})} if provider == "google_flow" else {}
        data = await llm.generate_image(prompt, model=model, aspect=aspect, refs=payloads,
                                        attempts=1, label=f"Plan dirigé {sid}", **extra)
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
        scene = _scene(current, sid)
        if _signature(current, scene) != signature or any(_digest(path) != digest for path, digest in sources):
            receipt["state"] = "obsolete_unselected"
            current.setdefault("workspace_generation_history", []).append(receipt)
            store.save_project(current)
            raise HTTPException(409, "Le plan ou ses références ont changé ; l'image est conservée mais n'est pas sélectionnée")
        receipt["state"] = "generated_unreviewed"
        scene.setdefault("generation_history", []).append(copy.deepcopy(receipt))
        scene.update(image=relative, status="done", uploaded=False, error=None, generation_receipt=receipt,
                     sent_references=copy.deepcopy(references),
                     human_review={"state": "unreviewed", "notes": "Nouvelle image à regarder avec ses références"})
        scene.pop("workspace_regeneration_required", None)
        scene.pop("clip", None)
        current["render"] = None
        if previous_render:
            current.setdefault("render_history", []).append(previous_render)
        current["workspace_generation"]["state"] = "generated_unreviewed"
        current["steps"]["visuals"].update(
            state="done" if all(x.get("image") for x in current["scenes"]) else "idle",
            msg="Nouvelle image à vérifier")
        current["steps"]["render"].update(state="idle", msg="Image modifiée : le montage reste à refaire")
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
        raise safe from None
    except Exception:
        raise HTTPException(502, "La génération du plan a échoué ; aucune correction automatique n'a été appliquée") from None
    finally:
        _active_projects.discard(pid)
        if not succeeded:
            current = store.get_project(pid)
            if current and (current.get("workspace_generation") or {}).get("id") == job_id:
                current = copy.deepcopy(current)
                scene = next((x for x in current.get("scenes", []) if x["id"] == sid), None)
                if scene and scene.get("generation_id") == job_id:
                    scene.update(status="error", error="Génération interrompue ou échouée ; le plan précédent est conservé")
                    if _signature(current, scene) == signature and current.get("render") is None:
                        current["render"] = previous_render
                current["workspace_generation"]["state"] = "failed"
                current["steps"]["visuals"].update(state="error", msg="Ce plan reste à corriger")
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
        generation = p.get("workspace_generation") or {}
        if generation.get("batch_id") == previous.get("id"):
            for scene in p.get("scenes", []):
                if scene.get("generation_id") == generation.get("id") and scene.get("status") == "running":
                    scene.update(status="error", error="Génération interrompue : vérifiez le résultat avant de reprendre")
            generation["state"] = "failed"
            p["steps"]["visuals"].update(state="error")
        store.save_project(p)


async def start_batch(pid, body):
    p = api._project(pid, writable=True)
    if batch_running(pid) or pid in _active_projects:
        raise HTTPException(409, "Une génération est déjà en cours sur ce projet")
    _recover_batch(p)
    if (any(s.get("status") in ("running", "queued") for s in p.get("scenes", []))
            or any(step.get("state") == "running" for step in p.get("steps", {}).values())):
        raise HTTPException(409, "Une tâche est déjà en cours sur ce projet")
    phase = body.get("phase")
    if phase not in ("preview", "remaining", "corrections"):
        raise HTTPException(422, "Choisissez le test des trois premiers plans, les images restantes ou les corrections")
    if body.get("confirmation") != api._generation_confirmation(p):
        raise HTTPException(409, "Le projet a changé. Actualisez avant de lancer la génération")
    scenes = p.get("scenes", [])
    if not scenes:
        raise HTTPException(422, "Enregistrez d'abord le découpage et les prompts écrits par Codex")
    if phase in ("remaining", "corrections") and not _preview_verified(p):
        raise HTTPException(409, "Regardez et marquez vérifiés les trois premiers plans avant de continuer")
    candidates = scenes[:3] if phase == "preview" else scenes[3:]
    targets = [s for s in candidates if (s.get("workspace_regeneration_required") is True
                                       if phase == "corrections" else _missing(p, s))]
    if not targets:
        raise HTTPException(409, "Aucun plan n’est marqué à corriger" if phase == "corrections"
                            else "Toutes les images de cette étape existent déjà")
    model = (p.get("model_snapshot") or {}).get("image_model")
    provider = (p.get("model_snapshot") or {}).get("image_provider", "cli_proxy")
    if body.get("image_model") != model or body.get("image_provider", provider) != provider:
        raise HTTPException(409, "Le modèle ou le fournisseur du projet a changé")
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
            raise HTTPException(422, f"Une référence du plan {scene['id']} est illisible") from None
    job = {"id": uuid.uuid4().hex, "phase": phase, "state": "queued", "started_at": now(),
           "scene_ids": [s["id"] for s in targets], "done": 0, "total": len(targets),
           "current_scene_id": None, "stop_requested": False, "error": None}
    if phase == "corrections":
        job.update(processed=0, failed_scene_ids=[], scene_errors={})
    p["workspace_batch"] = job
    store.save_project(p)
    _batch_tasks[pid] = asyncio.create_task(_run_batch(pid, job["id"], _batch_signature(p), sources))
    return api._full(p)


def _update_batch(pid, job_id, **changes):
    p = api._project(pid)
    if (p.get("workspace_batch") or {}).get("id") != job_id:
        raise HTTPException(409, "Le lot de génération a changé")
    p["workspace_batch"].update(changes)
    store.save_project(p)
    return p


def _check_batch_inputs(p, signature, sources):
    if (_batch_signature(p) != signature
            or any(api._file_digest(path.parent, path.name) != digest for path, digest in sources.items())):
        raise HTTPException(409, "Le découpage, le modèle ou les références ont changé. Le lot a été arrêté")
    if p["workspace_batch"]["phase"] in ("remaining", "corrections") and not _preview_verified(p):
        raise HTTPException(409, "La validation des trois premiers plans a changé. Le lot a été arrêté")


def _correction_error(exc):
    if getattr(exc, "workspace_safe_detail", False):
        return str(exc.detail)[:500]
    if exc.detail == "La génération du plan a échoué ; aucune correction automatique n'a été appliquée":
        return exc.detail
    # A raw HTTPException from an upstream client must not expose its response body.
    return f"La tentative de ce plan a échoué (HTTP {exc.status_code}). L’image précédente est conservée ; aucune nouvelle tentative automatique."


async def _run_batch(pid, job_id, signature, sources):
    state, error = "done", None
    try:
        p = _update_batch(pid, job_id, state="running")
        for sid in p["workspace_batch"]["scene_ids"]:
            current = api._project(pid)
            if current["workspace_batch"].get("stop_requested"):
                state = "stopped"
                break
            _check_batch_inputs(current, signature, sources)
            scene = _scene(current, sid)
            # Never overwrite an image selected by the user or another request.
            if not _missing(current, scene):
                raise HTTPException(409, "Une image a été ajoutée pendant la génération. Actualisez le projet")
            _update_batch(pid, job_id, current_scene_id=sid)
            correction = current["workspace_batch"]["phase"] == "corrections"
            if correction:
                _update_batch(pid, job_id, processed=current["workspace_batch"]["processed"] + 1)
            try:
                await generate(pid, sid, {"confirm_prompt": scene["prompt"],
                    "image_model": current["model_snapshot"]["image_model"],
                    "image_provider": current["model_snapshot"].get("image_provider", "cli_proxy")}, batch_id=job_id)
            except HTTPException as exc:
                if not correction:
                    raise
                latest = api._project(pid)
                failed = latest["workspace_batch"]["failed_scene_ids"] + [sid]
                errors = dict(latest["workspace_batch"]["scene_errors"], **{str(sid): _correction_error(exc)})
                _update_batch(pid, job_id, failed_scene_ids=failed, scene_errors=errors)
                _check_batch_inputs(api._project(pid), signature, sources)
                continue
            latest = api._project(pid)
            _update_batch(pid, job_id, done=latest["workspace_batch"]["done"] + 1)
            if correction:
                _check_batch_inputs(api._project(pid), signature, sources)
        latest = api._project(pid)
        if state == "done" and latest["workspace_batch"].get("failed_scene_ids"):
            state = "done_with_errors"
            error = f"{len(latest['workspace_batch']['failed_scene_ids'])} plan(s) restent à corriger ; aucune nouvelle tentative automatique."
        if api._project(pid)["workspace_batch"].get("stop_requested"):
            state = "stopped"
    except asyncio.CancelledError:
        state, error = "interrupted", "Génération interrompue. Vérifiez le dernier plan avant de reprendre"
    except HTTPException as exc:
        state, error = "failed", str(exc.detail)
    except Exception:
        state, error = "failed", "Le lot a échoué. Les images terminées sont conservées ; aucune nouvelle tentative automatique"
    finally:
        try:
            _update_batch(pid, job_id, state=state, error=error, current_scene_id=None, finished_at=now())
        finally:
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
            raise HTTPException(409, "Aucun lot de génération n'est en cours")
        p["workspace_batch"].update(stop_requested=True, state="stopping")
        store.save_project(p)
        return api._full(p)

    @router.post("/projects/{pid}/render", status_code=202)
    async def render_project(pid: str):
        p = api._project(pid, writable=True)
        if batch_running(pid) or pid in _active_projects:
            raise HTTPException(409, "Attendez la fin de la génération des images")
        full = api._full(p)
        if (not full["technical_ready"] or not full["scenes"]
                or any(s["human_review"]["state"] != "verified" for s in full["scenes"])
                or full["human_reviews"]["voiceover"]["state"] != "verified"):
            raise HTTPException(409, "Vérifiez la voix, les images et les timings avant de lancer le montage")
        pipeline.start(pid, pipeline.do_render)
        return api._full(api._project(pid))

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_generation_installed = True
