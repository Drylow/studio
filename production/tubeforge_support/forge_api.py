"""Small production API over the existing guarded workspace operations.

No provider credentials, alternate renderer, autonomous review or second login.
Creation keys live in each project so reconnecting clients do not duplicate it.
"""
import asyncio
import copy
import inspect
import io
import re
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.openapi.utils import get_openapi

from app import pipeline, store
from . import workspace_api as api, workspace_generation as generation
from .workspace_identity import current_owner, current_name, personal_projects

PREFIX = "/api/forge/v1"
PUBLIC = "/api/forge/v1"
NATIVE = "/api/2d"
_create_lock = asyncio.Lock()
ACTIONS = {
    "write-script": "/api/workspace/projects/{pid}/script/generate",
    "voice": "/api/workspace/projects/{pid}/voice/generate",
    "prepare": "/api/workspace/projects/{pid}/images/prepare",
    "preview": "/api/workspace/projects/{pid}/images/generate",
    "images": "/api/workspace/projects/{pid}/images/generate",
    "corrections": "/api/workspace/projects/{pid}/images/generate",
    "render": "/api/workspace/projects/{pid}/render",
}


def routes(app):
    # FastAPI versions may retain included routers instead of flattening them.
    def flatten(items):
        for route in items:
            included = getattr(route, "original_router", None)
            if included is not None:
                yield from flatten(included.routes)
            else:
                yield route
    return list(flatten(app.routes))


async def invoke(app, path, method="POST", **kwargs):
    route = next((r for r in routes(app) if getattr(r, "path", None) == path
                  and method in (getattr(r, "methods", None) or [])), None)
    if route is None:
        raise HTTPException(501, "This workspace operation is not installed")
    result = route.endpoint(**kwargs)
    return await result if inspect.isawaitable(result) else result


def status(p):
    """No file hashing, catalog/provider request or entire shot payload on polls."""
    pid = p["id"]
    active = pipeline.is_running(pid) or generation.batch_running(pid) or pid in generation._active_projects
    scenes = p.get("scenes") or []
    batch = p.get("workspace_batch") or {}
    stale = not active and (batch.get("state") in ("running", "queued", "stopping") or any(
        s.get("state") == "running" for s in (p.get("steps") or {}).values()))
    state = "running" if active else "interrupted" if stale else "failed" if p.get("error") else "idle"
    return {"id": pid, "title": p.get("title"), "channel_id": p.get("channel_id"),
            "owner_id": p.get("owner_id"), "state": state, "running": bool(active),
            "error": p.get("error"), "steps": p.get("steps") or {},
            "images": {"total": len(scenes), "done": sum(bool(s.get("image")) for s in scenes),
                       "failed": sum(s.get("status") == "error" for s in scenes)},
            "batch": {k: batch.get(k) for k in ("id", "state", "phase", "done", "total", "processed", "failed_scene_ids")},
            "duration_seconds": (p.get("voiceover") or {}).get("duration"),
            "voice_available": bool(p.get("voiceover")), "render_available": bool(p.get("render")),
            "validation": "Use the project or outputs endpoint for fresh file and review checks",
            "updated": p.get("updated"), "poll_after_seconds": 5,
            "project_url": f"/2d#/video/{pid}/texte"}


def external_urls(value):
    if isinstance(value, list):
        return [external_urls(v) for v in value]
    if isinstance(value, dict):
        return {k: (NATIVE + v if k.endswith("url") and isinstance(v, str) and
                    v.startswith(("/media/", "/style-media/", "/api/workspace/")) else external_urls(v))
                for k, v in value.items()}
    return value


def operation_catalog(app):
    rows = []
    for route in routes(app):
        path = getattr(route, "path", "")
        if not (path.startswith("/api/") or path.startswith(("/media/", "/style-media/"))):
            continue
        for method in sorted(getattr(route, "methods", None) or []):
            if method in ("HEAD", "OPTIONS"):
                continue
            rows.append({"method": method, "path": path,
                         "public_path": path if path.startswith(PREFIX) else NATIVE + path,
                         "name": getattr(route, "name", ""),
                         "family": "forge" if path.startswith(PREFIX) else "workspace" if
                         path.startswith("/api/workspace") else "legacy"})
    return sorted(rows, key=lambda r: (r["public_path"], r["method"]))


def install(app):
    if getattr(app.state, "forge_api_installed", False):
        return
    router = APIRouter(prefix=PREFIX, tags=["Forge production API"])

    @router.get("/health")
    async def health():
        return {"ok": True, "version": 1, "execution": "VPS", "renderer": "CPU",
                "authentication": "existing portal session", "automatic_review": False,
                "actions": list(ACTIONS), "native_base": NATIVE}

    @router.get("/presets")
    async def presets():
        from . import workspace_planning, workspace_writing
        styles = {s["id"]: s for s in api._styles()}
        rows = []
        for c in api._profiles():
            p = {"channel_id": c["id"], "style_id": c["style_id"]}
            rows.append(c | {"style": styles.get(c["style_id"]),
                             "can_write_script": workspace_writing.allowed(p),
                             "can_prepare_images": workspace_planning.allowed(p)})
        return external_urls(rows)

    @router.get("/videos")
    async def videos(scope: str = "mine", archived: bool = False):
        if scope not in ("mine", "team"):
            raise HTTPException(422, "Choose mine or team")
        return [status(p) for p in personal_projects(store.list_projects(archived), scope)
                if p.get("codex_directed")]

    @router.post("/videos", status_code=201)
    async def create(body: dict):
        key = body.get("idempotency_key")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
            raise HTTPException(422, "Provide a unique idempotency_key (1–128 letters, digits, . _ : -)")
        if set(body) - {"idempotency_key", "channel_id", "title", "script", "brief", "minutes"}:
            raise HTTPException(422, "Use channel_id, title, script, brief, minutes and idempotency_key")
        signature = api._hash(body)
        async with _create_lock:
            # Include archives: a retry must never silently create a new production.
            for p in store.list_projects(True) + store.list_projects(False):
                receipt = p.get("forge_api_creation") or {}
                if receipt.get("member") == current_owner() and receipt.get("key") == key:
                    if receipt.get("request_hash") != signature:
                        raise HTTPException(409, "This idempotency_key was already used with different input")
                    return status(p) | {"reused": True}
            catalog = await api._catalog()
            native = {"channel_id": body.get("channel_id"), "title": body.get("title"),
                      "custom_script": body.get("script", ""), "topic": body.get("brief", ""),
                      "duration_minutes": body.get("minutes", 15), "mode": "review"}
            p = api._create(api._prepare(native, catalog), catalog)
            p.update(owner_id=current_owner(), owner_name=current_name())
            p["forge_api_creation"] = {"member": current_owner(), "key": key, "request_hash": signature}
            store.save_project(p)
            return status(p) | {"reused": False}

    @router.get("/videos/{pid}")
    async def project(pid: str):
        return external_urls(api._ui_project(api._full(api._project(pid))))

    @router.get("/videos/{pid}/status")
    async def progress(pid: str):
        return status(api._project(pid))

    @router.get("/videos/{pid}/transcript")
    async def transcript(pid: str):
        p = api._project(pid)
        if not p.get("voiceover") or p.get("voiceover_stale"):
            raise HTTPException(409, "Generate the current saved script's voice first")
        return {"duration_seconds": p["voiceover"]["duration"], "words": store.load_words(pid),
                "word_schema": {"w": "spoken word", "s": "start seconds", "e": "end seconds"}}

    @router.post("/videos/{pid}/actions/{action}", status_code=202)
    async def action(pid: str, action: str, body: dict):
        if action not in ACTIONS:
            raise HTTPException(422, "Choose " + ", ".join(ACTIONS))
        p = api._project(pid)
        # Retries during an active request never start a second paid call.
        if status(p)["running"]:
            raise HTTPException(409, "A task is already active; poll status before any new action")
        args = {"pid": pid}
        payload = dict(body)
        if action in ("voice", "prepare", "write-script"):
            payload["script_hash"] = api._hash(p.get("script") or "")
        if action == "voice":
            if p.get("voiceover") and not p.get("voiceover_stale") and not payload.pop("regenerate", False):
                if not api._file_digest(store.project_dir(pid), p["voiceover"].get("file")):
                    raise HTTPException(409, "Saved voice file is missing; inspect before explicit regenerate")
                return status(p) | {"reused": True}
            payload = dict(p["settings"]["voice"], **payload)
        elif action == "write-script":
            payload.setdefault("title", p.get("title"))
            payload.setdefault("brief", p.get("topic") or "")
            payload.setdefault("minutes", p.get("duration_minutes") or 15)
        elif action in ("preview", "images", "corrections"):
            payload.update(phase={"preview": "preview", "images": "remaining", "corrections": "corrections"}[action],
                           confirmation=api._generation_confirmation(p), **(p.get("model_snapshot") or {}))
        if action != "render":
            args["body"] = payload
        try:
            await invoke(app, ACTIONS[action], **args)
        except pipeline.Busy:
            raise HTTPException(409, "A task is already running") from None
        return status(api._project(pid)) | {"action": action}

    @router.post("/videos/{pid}/stop")
    async def stop(pid: str):
        p = api._project(pid)
        batch = generation.batch_running(pid)
        if batch:
            p["workspace_batch"].update(stop_requested=True, state="stopping")
            store.save_project(p)
        return {"batch_draining": bool(batch), "task_cancel_requested": pipeline.stop(pid),
                "note": "Already submitted provider requests may finish; inspect status before retrying"}

    @router.post("/videos/{pid}/review")
    async def review(pid: str, body: dict):
        # The caller supplies actual inspection notes; never generate approvals here.
        if not body.get("reviewer") or not body.get("source") or not body.get("notes"):
            raise HTTPException(422, "Supply reviewer, source and actual inspection notes")
        return external_urls(await invoke(app, "/api/workspace/projects/{pid}/review", pid=pid, body=body))

    @router.post('/videos/{pid}/references/generate', status_code=202)
    async def generate_reference(pid: str, body: dict):
        """Authored reference work uses the same server/provider image semaphore."""
        from app import llm
        from app.util import now
        from PIL import Image
        p = api._project(pid, writable=True)
        asset = api._identifier(body.get('asset_id'))
        prompt = api._text(body.get('prompt'), 'prompt', required=True)
        role = body.get('role', 'character')
        if role not in ('character', 'location', 'pose', 'style'):
            raise HTTPException(422, 'Choose character, location, pose or style')
        refs = body.get('references')
        if len(prompt) > 30000 or not isinstance(refs, list) or not 1 <= len(refs) <= 12:
            raise HTTPException(422, 'Supply an authored prompt and 1–12 ordered inspected references')
        sources = []
        for ref in refs:
            if not isinstance(ref, dict) or ref.get('owner') not in ('project', 'style') or ref.get('review_state') != 'verified':
                raise HTTPException(422, 'Reference sources must be explicitly inspected and bound')
            base = store.style_dir(p['style_id']) if ref['owner'] == 'style' else store.project_dir(pid)
            if not ref.get('sha256') or api._file_digest(base, ref.get('path')) != ref['sha256']:
                raise HTTPException(409, 'A reference source is missing or changed')
            sources.append((base / ref['path'], ref['sha256']))
        signature = api._hash({'prompt': prompt, 'refs': refs, 'role': role, 'models': p.get('model_snapshot')})
        previous = (p.get('workspace_reference_jobs') or {}).get(asset)
        if previous:
            if previous.get('input_hash') != signature:
                raise HTTPException(409, 'Use a new asset_id for changed reference inputs')
            if previous.get('state') == 'done' and api._file_digest(store.project_dir(pid), previous.get('path')) == previous.get('sha256'):
                return {'asset': previous, 'reused': True}
            raise HTTPException(409, 'An attempt already exists; inspect its result before an explicit new asset_id')
        async def generate(p):
            async def work(progress):
                record = p['workspace_reference_jobs'][asset]
                payloads = [generation._reference_payload(path, digest) for path, digest in sources]
                if any(api._file_digest(path.parent, path.name) != digest for path, digest in sources):
                    raise RuntimeError('Reference source changed before dispatch')
                receipt = {}
                data = await llm.generate_image(prompt, model=p['model_snapshot']['image_model'], aspect='16:9',
                    refs=payloads, provider=p['model_snapshot'].get('image_provider', 'cli_proxy'),
                    label='Reference ' + asset, receipt=receipt, attempts=1)
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    if image.width * image.height > 20000000 or abs(image.width / image.height - 16/9) > .06:
                        raise RuntimeError('Reference image must be full-frame landscape 16:9')
                    buf=io.BytesIO(); image.convert('RGB').save(buf, 'PNG')
                relative='refs/generated-'+asset+'.png'
                target=store.project_dir(pid)/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(buf.getvalue())
                record.update(state='done', path=relative, sha256=api._file_digest(store.project_dir(pid),relative), receipt=receipt)
                p.setdefault('workspace_references', []).append({'path':relative,'owner':'project','role':role,
                    'label':asset,'sha256':record['sha256'],'review_state':'unreviewed','created':now()})
                progress(1,1,'Reference generated; actual inspection required')
            await pipeline._step(p,'references',work)
        p.setdefault('workspace_reference_jobs', {})[asset]={'state':'queued','input_hash':signature,'prompt':prompt,
            'references':copy.deepcopy(refs),'created':now()}
        store.save_project(p);pipeline.start(pid,generate)
        return {'asset_id':asset,'state':'queued','reused':False}

    @router.get("/videos/{pid}/outputs")
    async def outputs(pid: str):
        p = api._full(api._project(pid))
        return {"id": pid, "duration_seconds": (p.get("voiceover") or {}).get("duration"),
                "publication_ready": p["publication_ready"], "review_state": p["review_state"],
                "technical_issues": p["technical_issues"], "reviews": p["human_reviews"],
                "video": PUBLIC + f"/videos/{pid}/download?kind=video" if p.get("render") else None,
                "voice": PUBLIC + f"/videos/{pid}/download?kind=voice" if p.get("voiceover") else None,
                "shots": [{"id": s["id"], "start": s.get("start"), "end": s.get("end"),
                           "image": NATIVE + f"/media/{pid}/" + quote(s["image"], safe="/") if s.get("image") else None,
                           "review": s["human_review"]} for s in p.get("scenes") or []]}

    @router.get("/videos/{pid}/download")
    async def download(pid: str, kind: str = "video"):
        p = api._project(pid)
        if kind not in ("video", "voice", "subtitles"):
            raise HTTPException(422, "Choose video, voice or subtitles")
        rel = ((p.get("render") or {}).get("file") if kind == "video" else
               (p.get("voiceover") or {}).get("file") if kind == "voice" else "render/subtitles.srt")
        base = store.project_dir(pid)
        if not api._file_digest(base, rel):
            raise HTTPException(404, "Output not available")
        file = (base / rel).resolve()
        return FileResponse(file, filename=f"{pid}-{kind}{file.suffix}", headers={"Cache-Control": "private, no-store"})

    @router.get("/endpoints")
    async def endpoints():
        return {"endpoints": operation_catalog(app), "schema": PUBLIC + "/openapi.json"}

    @router.get("/openapi.json")
    async def schema():
        result = get_openapi(title="TubeForge API", version="1", routes=routes(app))
        result["paths"] = {(p if p.startswith(PREFIX) else NATIVE + p): item
                           for p, item in result["paths"].items() if p.startswith("/api/") or
                           p.startswith(("/media/", "/style-media/"))}
        result["servers"] = [{"url": "/"}]
        result.setdefault("components", {}).setdefault("securitySchemes", {})["portalSession"] = {
            "type": "http", "scheme": "bearer", "description": "Portal session token, not the member access key"}
        result["security"] = [{"portalSession": []}]
        return result

    @router.get("/LLM.txt", response_class=PlainTextResponse)
    async def llm(request: Request):
        from pathlib import Path
        guide = (Path(__file__).parent / "forge_docs" / "LLM.txt").read_text(encoding="utf-8")
        guide = guide.split("\nINITIAL COMPLETE ENDPOINT INVENTORY\n")[0]
        catalog = "\n".join(f"{r['method']} {r['public_path']} [{r['family']}]" for r in operation_catalog(app))
        return guide + "\n\nLIVE COMPLETE ENDPOINT INVENTORY\n" + catalog + "\n"

    static = next((i for i, r in enumerate(app.routes) if getattr(r, "path", None) == ""), len(app.routes))
    app.router.routes[static:static] = router.routes
    app.state.forge_api_installed = True
