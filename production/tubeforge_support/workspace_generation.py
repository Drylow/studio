"""Execute one explicitly confirmed, authored scene through the existing proxy."""
import asyncio
import copy
import hashlib
import io
import uuid

from fastapi import APIRouter, HTTPException
from PIL import Image

from app import config, llm, pipeline, store
from app.util import now
from . import workspace_api as api


_active_projects = set()


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
    return api._hash({"script": p.get("script"), "models": p.get("model_snapshot"),
                      "aspect": p["settings"]["visuals"].get("aspect"),
                      "scene": {key: s.get(key) for key in (
                          "id", "text", "prompt", "prompt_author", "location_id", "characters",
                          "references", "start", "end", "motion", "image")}})


def _prepare(p, s, body):
    prompt = s.get("prompt")
    if (not isinstance(prompt, str) or not prompt.strip() or "renderer-only import" in prompt.lower()
            or s.get("prompt_author") != "codex" or not s.get("location_id")
            or not isinstance(s.get("text"), str) or not s["text"].strip()
            or s["text"] not in p.get("script", "") or not isinstance(s.get("characters"), list)
            or any(not isinstance(c, str) or not c.strip() for c in s["characters"])):
        raise HTTPException(422, "Ce plan doit avoir une narration, un lieu, des personnages nommés et un prompt écrit par Codex")
    if body.get("confirm_prompt") != prompt:
        raise HTTPException(409, "Le prompt confirmé ne correspond pas au prompt exact enregistré")
    model = (p.get("model_snapshot") or {}).get("image_model")
    if not isinstance(model, str) or not model or body.get("image_model") != model:
        raise HTTPException(409, "Confirmez le modèle image enregistré dans ce projet")
    if not config.get("PROXY_API_KEY") or not config.get("PROXY_BASE_URL"):
        raise HTTPException(503, "Le CLI Proxy n'est pas configuré")
    refs = s.get("references")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, dict) for ref in refs):
        raise HTTPException(422, "Enregistrez au moins une référence réelle, dans l'ordre exact à envoyer")
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
                         "source_sha256": source_hash, "sent_sha256": hashlib.sha256(payload).hexdigest()})
    aspect = p["settings"]["visuals"].get("aspect", "16:9")
    if aspect not in llm.ASPECTS:
        raise HTTPException(422, "Le format d'image enregistré n'est pas pris en charge")
    return prompt, model, aspect, payloads, sources, receipts


async def generate(pid, sid, body):
    p = api._project(pid, writable=True)
    if (pid in _active_projects or pipeline.is_running(pid)
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
    receipt = {"id": job_id, "prompt": prompt, "model": model, "aspect": aspect,
               "references": references, "transport": "cli_proxy", "endpoint": "/images/edits",
               "started_at": now(), "state": "running", "previous_image": previous_image}
    _active_projects.add(pid)
    succeeded = False
    try:
        s.update(status="running", generation_id=job_id, error=None)
        p["workspace_generation"] = {"id": job_id, "scene_id": sid, "state": "running"}
        p["render"] = None
        p["steps"]["visuals"].update(state="running", msg="Génération du plan confirmé")
        store.save_project(p)
        # Nonempty refs route this existing helper to /images/edits. No composition or rewrite.
        data = await llm.generate_image(prompt, model=model, aspect=aspect, refs=payloads,
                                        attempts=1, label=f"Plan dirigé {sid}")
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


def install(app):
    if getattr(app.state, "workspace_generation_installed", False):
        return
    router = APIRouter(prefix="/api/workspace")

    @router.post("/projects/{pid}/scenes/{sid}/generate")
    async def generate_scene(pid: str, sid: int, body: dict):
        return await generate(pid, sid, body)

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_generation_installed = True
