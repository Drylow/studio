"""Directed workspace API, deployed as app.workspace_api in private TubeForge.

Call install(app) before the root StaticFiles mount. All writes use the existing
store. Queueing never calls run_all or authors prompts. Model IDs are runtime data.
"""
import copy
import hashlib
import io
import json
import math
import re
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from app import channels, config, llm, pipeline, store
from app.util import now, read_json, write_json


PROFILE_NAMES = {
    "edo-daily": "Edo Daily",
    "aztec-daily": "Aztec Daily",
    "babylon-daily": "Babylon Daily",
    "imperial-china-daily": "Imperial China Daily",
    "ottoman-daily": "Ottoman Daily",
}
REVIEW_STATES = {"verified", "correct", "unreviewed"}
MAX_UPLOAD = 10 * 1024 * 1024
MAX_SCRIPT = 1024 * 1024


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise HTTPException(422, "Identifiant invalide")
    return value


def _text(value, field, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise HTTPException(422, f"Le champ {field} doit contenir du texte" + (" et ne peut pas être vide" if required else ""))
    return value


def _project(pid, writable=False):
    p = store.get_project(_identifier(pid))
    if not p or not p.get("codex_directed"):
        raise HTTPException(404, "Projet dirigé par Codex introuvable")
    if writable and pipeline.is_running(pid):
        raise HTTPException(409, "Une tâche est en cours sur ce projet")
    return copy.deepcopy(p)


@lru_cache(maxsize=8192)
def _digest_file(path, stamp):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    return digest if stamp == (after.st_size, after.st_mtime_ns, after.st_ctime_ns) else None


def _file_digest(base, relative):
    if not isinstance(relative, str) or not relative:
        return None
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        return None
    try:
        stat = path.stat()
        stamp = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        digest = _digest_file(path, stamp)
        after = path.stat()
        return digest if stamp == (after.st_size, after.st_mtime_ns, after.st_ctime_ns) else None
    except OSError:
        return None


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _profiles():
    # Unlike list_channels(), this read does not seed unrelated vendor channels.
    saved = {c["id"]: c for c in read_json(channels.FILE, []) or [] if isinstance(c, dict) and c.get("id")}
    out = []
    for cid, name in PROFILE_NAMES.items():
        c = saved.get(cid, {})
        sid = c.get("style_id", "pov-history")
        style = store.get_style(_identifier(sid)) or {}
        refs = copy.deepcopy(style.get("workspace_references", []))
        if not refs:
            sources = style.get("visuals", {}).get("reference_sources", [])
            refs = [{"path": path, "state": "unreviewed"} | next(
                (r for r in sources if isinstance(r, dict) and r.get("path", r.get("file")) == path), {})
                for path in style.get("visuals", {}).get("style_refs", [])]
        for ref in refs:
            ref["url"] = f"/style-media/{sid}/{ref['path']}"
            ref["exists"] = bool(_file_digest(store.style_dir(sid), ref["path"]))
        out.append({"id": cid, "name": c.get("name", name), "style_id": sid,
                    "setting": c.get("setting", ""), "historical_profile": c.get("historical_profile", False),
                    "configured": bool(c and style), "duration_minutes_min": 20,
                    "duration_minutes_max": 25,
                    "target_minutes": c.get("target_minutes", 22),
                    "style_prompt": style.get("visuals", {}).get("art_style", ""),
                    "thumbnail_prompt": style.get("thumbnail", {}).get("style", ""),
                    "background_direction": style.get("visuals", {}).get("background_direction", ""),
                    "video_preview": c.get("video_preview"), "thumbnail_preview": c.get("thumbnail_preview"),
                    "video_preview_url": f"/style-media/{sid}/{c['video_preview']}" if c.get("video_preview") else None,
                    "thumbnail_preview_url": f"/style-media/{sid}/{c['thumbnail_preview']}" if c.get("thumbnail_preview") else None,
                    "preview_label": c.get("preview_label", "Apercu existant"),
                    "references": refs,
                    "reference_update_pending": style.get("visuals", {}).get("reference_update_pending", True),
                    "reference_status": c.get("reference_status", "waiting_for_user_references")})
    return out


def _profile(cid):
    profile = next((p for p in _profiles() if p["id"] == cid), None)
    if not profile:
        raise HTTPException(422, "Chaîne inconnue")
    if not profile["configured"]:
        raise HTTPException(409, "La chaîne et son style doivent être préparés avant de créer une vidéo")
    return profile


def _styles():
    out = []
    for path in sorted(config.STYLES_DIR.glob("*/style.json")):
        raw = read_json(path, {})
        if not isinstance(raw, dict) or raw.get("archived"):
            continue
        sid = _identifier(path.parent.name)
        style = store.get_style(sid)
        if style:
            visuals = style.get("visuals", {})
            out.append({"id": sid, "name": style.get("name", sid),
                        "prompt": visuals.get("art_style", ""),
                        "background_direction": visuals.get("background_direction", "")})
    return out


def _default_models():
    style = store.get_style("pov-history") or {}
    return {"text_model": config.get("SCRIPT_MODEL") or config.get("FAST_MODEL"),
            "image_model": style.get("visuals", {}).get("image_model", "")}


def _capabilities(item):
    caps = {"text": None, "image": None}
    explicit = item.get("capabilities")
    if isinstance(explicit, dict):
        for role in caps:
            if isinstance(explicit.get(role), bool):
                caps[role] = explicit[role]
    modalities = item.get("output_modalities")
    if isinstance(modalities, list) and modalities and all(isinstance(x, str) for x in modalities):
        for role in caps:
            caps[role] = role in modalities
    return caps


async def _catalog():
    result = {"available": False, "models": [], "defaults": _default_models(),
              "checked_at": now(), "error": None, "generation_tested": False,
              "provider_connection": "not_tested"}
    if not config.get("PROXY_BASE_URL") or not config.get("PROXY_API_KEY"):
        result["error"] = "Le CLI Proxy n'est pas configuré"
        return result
    try:
        response = await llm.client().get(llm._url("/models"), headers=llm._headers(),
                                          timeout=15, follow_redirects=False)
        if response.status_code != 200:
            result["error"] = f"Le catalogue du CLI Proxy est indisponible (erreur {response.status_code})"
            return result
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Invalid catalog")
        seen = set()
        secret = config.get("PROXY_API_KEY")
        for item in payload["data"]:
            if not isinstance(item, dict):
                continue
            mid = item.get("id")
            if (not isinstance(mid, str) or not re.fullmatch(r"[A-Za-z0-9_./:@+-]{1,200}", mid)
                    or mid in seen or (secret and secret in mid)):
                continue
            seen.add(mid)
            caps = _capabilities(item)
            result["models"].append({"id": mid, "capabilities": caps,
                                     "suggested_role": "image" if "image" in mid.lower() else "text",
                                     "suggested_role_source": "id_heuristic",
                                     "capability_verified": all(x is not None for x in caps.values())})
        result["models"].sort(key=lambda m: m["id"])
        result["available"] = True
    except Exception:
        # Proxy errors may contain auth headers, credentials or upstream internals.
        result["error"] = "Le catalogue du CLI Proxy est indisponible"
    return result


def _models(body, catalog, defaults=None):
    if not catalog["available"]:
        raise HTTPException(503, catalog["error"])
    selected = {}
    defaults = defaults or catalog["defaults"]
    for role in ("text", "image"):
        key = f"{role}_model"
        mid = body.get(key, defaults.get(key))
        entry = next((m for m in catalog["models"] if m["id"] == mid), None)
        if not entry:
            raise HTTPException(422, f"Choisissez {key} dans le catalogue actuel du CLI Proxy")
        if entry["capabilities"][role] is False:
            raise HTTPException(422, f"Le modèle choisi pour {key} ne propose pas ce type de sortie")
        selected[role] = mid
    return selected


def _prepare(body, catalog):
    if body.get("auto_run") or body.get("mode", "review") != "review":
        raise HTTPException(422, "Ces vidéos doivent être relues et ne démarrent pas automatiquement")
    profile = _profile(body.get("profile_id", body.get("channel_id")))
    title = _text(body.get("title", ""), "title", required=True)
    if len(title.strip()) > 240:
        raise HTTPException(422, "Le titre ne peut pas dépasser 240 caractères")
    topic = _text(body.get("topic", ""), "topic")
    script = _text(body.get("custom_script", ""), "custom_script")
    if len(script.encode("utf-8")) > MAX_SCRIPT or "\x00" in script:
        raise HTTPException(422, "Le script doit être un texte UTF-8 de moins de 1 Mo, sans caractère nul")
    sid = _identifier(body.get("style_id", profile["style_id"]))
    if not any(style["id"] == sid for style in _styles()):
        raise HTTPException(422, "Choisissez un style visuel disponible")
    minutes = body.get("duration_minutes", 22)
    if (isinstance(minutes, bool) or not isinstance(minutes, (float, int))
            or not math.isfinite(minutes) or not 20 <= minutes <= 25):
        raise HTTPException(422, "La durée cible doit être comprise entre 20 et 25 minutes")
    return {"profile": profile, "title": title, "topic": topic, "script": script, "style_id": sid,
            "target_duration_seconds": minutes * 60, "models": _models(body, catalog)}


def _create(prepared, catalog):
    models, profile = prepared["models"], prepared["profile"]
    selected_style = store.get_style(prepared["style_id"])
    channel_style = store.get_style(profile["style_id"])
    p = store.create_project(prepared["title"], prepared["style_id"], topic=prepared["topic"],
                             mode="review", custom_script=prepared["script"], characters=[], overrides={
                                 "models.text": models["text"], "models.image": models["image"],
                                 "script.model": models["text"], "script.fast_model": models["text"],
                                 "visuals.image_model": models["image"],
                                 "thumbnail.model": models["image"], "thumbnail.count": 0,
                                 "visuals.auto_characters": False, "visuals.continuity": "off",
                             })
    # A visual preset must not replace the channel's configured voice provider.
    p["settings"]["voice"] = copy.deepcopy(channel_style["voice"])
    p.update(codex_directed=True, channel_id=profile["id"], profile_id=profile["id"],
             target_duration_seconds=prepared["target_duration_seconds"],
             script=prepared["script"], auto_promo_shorts=0, prompts_approved=False,
             workspace_queue={"state": "queued_for_authoring", "created": now()},
             model_snapshot={"text_model": models["text"], "image_model": models["image"],
                             "selected_at": now(), "catalog_checked_at": catalog["checked_at"],
                             "transport": "cli_proxy", "capabilities": {
                                 role: next(m["capabilities"] for m in catalog["models"] if m["id"] == mid)
                                 for role, mid in models.items()}},
             human_reviews={}, workspace_references=[],
             style_snapshot={"id": prepared["style_id"], "name": selected_style["name"],
                             "selected_at": now(),
                             "prompt": selected_style["visuals"].get("art_style", ""),
                             "background_direction": selected_style["visuals"].get("background_direction", "")})
    if p.get("script_history"):
        p["script_history"][-1]["text"] = prepared["script"]
    return store.save_project(p)


def _scene_evidence(p, s):
    pdir = store.project_dir(p["id"])
    image_hash = _file_digest(pdir, s.get("image"))
    if not image_hash:
        return None
    receipt_refs = (s.get("codex_receipt") or {}).get("references", [])
    requested = s.get("references") or receipt_refs
    if not requested:
        return None
    refs = []
    for ref in requested:
        path = ref.get("path") if isinstance(ref, dict) else ref
        owner = ref.get("owner", "studio" if requested is receipt_refs else "project") if isinstance(ref, dict) else "project"
        if owner == "studio":
            root = config.get("STUDIO_ROOT")
            if not root or not isinstance(ref, dict) or not ref.get("sha256"):
                return None
            base = Path(root).resolve()
        elif owner == "style":
            base = store.style_dir(p["style_id"])
        elif owner == "project":
            base = pdir
        else:
            return None
        digest = _file_digest(base, path)
        if not digest or isinstance(ref, dict) and ref.get("sha256") and digest != ref["sha256"]:
            return None
        refs.append({"path": path, "owner": owner, "sha256": digest,
                     "role": ref.get("role") if isinstance(ref, dict) else None})
    return {"image_sha256": image_hash, "references": refs,
            "authoring_sha256": _hash({k: s.get(k) for k in (
                "text", "prompt", "start", "end", "location_id", "characters", "references", "motion", "codex_receipt")}),
            "script_sha256": _hash(p.get("script")), "models_sha256": _hash(p.get("model_snapshot"))}


def _reference_path(p, s, index):
    receipt = (s.get("codex_receipt") or {}).get("references", [])
    refs = s.get("references") or receipt
    if index < 0 or index >= len(refs) or not isinstance(refs[index], dict):
        raise HTTPException(404, "Référence introuvable")
    ref = refs[index]
    owner = ref.get("owner", "studio" if refs is receipt else "project")
    if owner == "studio":
        root = config.get("STUDIO_ROOT")
        if not root or not ref.get("sha256"):
            raise HTTPException(404, "Cette référence du studio n'a pas d'empreinte de fichier enregistrée")
        base = Path(root).resolve()
    elif owner == "style":
        base = store.style_dir(p["style_id"])
    elif owner == "project":
        base = store.project_dir(p["id"])
    else:
        raise HTTPException(404, "Emplacement de référence inconnu")
    digest = _file_digest(base, ref.get("path"))
    if not digest or ref.get("sha256") and digest != ref["sha256"]:
        raise HTTPException(409, "La référence est absente ou a été modifiée")
    return (base / ref["path"]).resolve()


def _scope_evidence(p, scope, scene_evidence=None):
    if scope == "script":
        return _hash(p["script"]) if p.get("script", "").strip() else None
    media = p.get(scope) or {}
    digest = _file_digest(store.project_dir(p["id"]), media.get("file"))
    if not digest:
        return None
    if scope == "voiceover":
        if p.get("voiceover_stale"):
            return None
        return _hash({"file_sha256": digest, "script": p.get("script"), "media": media})
    return _hash({"file_sha256": digest, "script": p.get("script"), "media": media,
                  "voiceover": _scope_evidence(p, "voiceover"),
                  "scenes": scene_evidence if scene_evidence is not None else [
                      _scene_evidence(p, s) for s in p.get("scenes", [])]})


def _review(record, evidence):
    record = copy.deepcopy(record or {"state": "unreviewed", "notes": ""})
    if (record.get("state") == "verified" and not evidence
            or record.get("state") in ("verified", "correct") and record.get("evidence") != evidence):
        record["state"] = "stale"
    return record


def _technical_issues(p, scene_evidence=None):
    issues = []
    if p.get("technical_test"):
        issues.append("Ce test ou cet extrait n'est pas un épisode complet à publier")
    voice = p.get("voiceover") or {}
    duration = voice.get("duration")
    if p.get("voiceover_stale"):
        issues.append("La voix est à refaire après la modification du texte")
    if not _file_digest(store.project_dir(p["id"]), voice.get("file")):
        issues.append("Le fichier de voix est absent")
    duration_valid = type(duration) in (int, float) and math.isfinite(duration) and duration > 0
    if not duration_valid:
        issues.append("La durée réelle de la voix n'est pas enregistrée")
    scenes = p.get("scenes", [])
    if not scenes:
        issues.append("Le découpage écrit par Codex est absent")
    else:
        evidence = scene_evidence if scene_evidence is not None else [_scene_evidence(p, s) for s in scenes]
        if any(not item for item in evidence):
            issues.append("Une image ou une référence de plan est absente ou a été modifiée")
        cursor = 0
        clock_valid = True
        for s in scenes:
            start, end = s.get("start"), s.get("end")
            if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end))
                    or end <= start or start < 0 or abs(start - cursor) > 0.05):
                clock_valid = False
                break
            cursor = end
        if not clock_valid or not duration_valid or abs(cursor - duration) > 0.05:
            issues.append("Les plans doivent couvrir toute la voix, sans trou ni chevauchement")
        if " ".join(" ".join(s.get("text", "").split()) for s in scenes) != " ".join(p.get("script", "").split()):
            issues.append("Les extraits des plans doivent reprendre tout le texte exact, dans l'ordre")
    render = p.get("render")
    if render:
        if render.get("qa_pending"):
            issues.append("Le contrôle technique du rendu reste à terminer")
        if not _file_digest(store.project_dir(p["id"]), render.get("file")):
            issues.append("Le fichier du rendu est absent")
    if p.get("error"):
        issues.append("Une erreur de production reste à résoudre")
    return issues


def _full(p):
    out = copy.deepcopy(p)
    out.pop("script_history", None)
    out.pop("video_context", None)
    scenes = out.get("scenes", [])
    evidence = [_scene_evidence(p, s) for s in scenes]
    for s, item in zip(scenes, evidence):
        s["human_review"] = _review(s.get("human_review"), item)
        s["image_url"] = f"/media/{p['id']}/{s['image']}" if s.get("image") else None
        receipt_refs = (s.get("codex_receipt") or {}).get("references", [])
        refs = s.get("references") or receipt_refs
        if refs:
            visible = []
            for i, ref in enumerate(refs):
                entry = copy.deepcopy(ref) if isinstance(ref, dict) else {"path": ref}
                entry["owner"] = entry.get("owner", "studio" if refs is receipt_refs else "project")
                entry["url"] = f"/api/workspace/projects/{p['id']}/scenes/{s['id']}/references/{i}"
                visible.append(entry)
            s["references"] = visible
            if refs is receipt_refs:
                s["sent_references"] = copy.deepcopy(visible)
    scopes = {scope: _review(p.get("human_reviews", {}).get(scope), _scope_evidence(p, scope, evidence))
              for scope in ("script", "voiceover", "render")}
    out["human_reviews"] = scopes
    checks = [s["human_review"]["state"] for s in scenes] + [v["state"] for v in scopes.values()]
    scenes_verified = bool(scenes) and all(s["human_review"]["state"] == "verified" for s in scenes)
    out["technical_issues"] = _technical_issues(p, evidence)
    out["technical_ready"] = not out["technical_issues"]
    ready = scenes_verified and out["technical_ready"] and all(scopes[k]["state"] == "verified" for k in ("script", "voiceover"))
    out["publication_ready"] = bool(ready and scopes["render"]["state"] == "verified")
    out["running"] = pipeline.is_running(p["id"])
    if out["running"]:
        state = "running"
    elif p.get("error"):
        state = "failed"
    elif "correct" in checks:
        state = "needs_correction"
    elif out["publication_ready"]:
        state = "publication_ready"
    elif (p.get("render") or {}).get("qa_pending"):
        state = "rendered_qa_pending"
    elif p.get("render") and not out["technical_ready"]:
        state = "technical_review_required"
    elif p.get("render"):
        state = "rendered_awaiting_review"
    elif not p.get("script", "").strip():
        state = "waiting_for_script"
    elif not p.get("voiceover"):
        state = "waiting_for_voiceover"
    elif not scenes:
        state = "waiting_for_scenes"
    elif any(not item for item in evidence):
        state = "waiting_for_images"
    elif ready:
        state = "ready_to_render"
    else:
        state = "awaiting_review"
    out["review_state"] = state
    out["duration_minutes"] = p.get("target_duration_seconds", 0) / 60
    out["references"] = copy.deepcopy(p.get("workspace_references", []))
    for ref in out["references"]:
        ref["url"] = f"/media/{p['id']}/{ref['path']}"
    return out


def _summary(p):
    full = _full(p) if p.get("codex_directed") else p | {
        "publication_ready": False, "technical_ready": False, "technical_issues": [],
        "running": pipeline.is_running(p["id"])}
    keys = ("id", "title", "profile_id", "channel_id", "style_id", "style_name", "created", "updated",
            "archived", "steps", "error", "running", "review_state", "publication_ready", "model_snapshot",
            "target_duration_seconds", "duration_minutes", "workspace_queue", "render", "technical_ready", "technical_issues")
    return {k: full.get(k) for k in keys} | {"scenes": len(p.get("scenes", [])),
            "duration": (p.get("voiceover") or {}).get("duration"), "readonly": not p.get("codex_directed", False),
            "legacy_url": f"/legacy.html#/p/{p['id']}/script", "legacy_api_url": f"/api/projects/{p['id']}",
            "codex_directed": p.get("codex_directed", False),
            "review_state": full["review_state"] if p.get("codex_directed") else "legacy_readonly"}


def _batches():
    return [b for b in pipeline.list_batches() if b.get("workspace_directed")]


async def _upload(file, base, role, label):
    data = await file.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(422, "L'image de référence doit peser au maximum 10 Mo")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 20_000_000:
                raise HTTPException(422, "L'image de référence dépasse 20 millions de pixels")
            image.load()
            buf = io.BytesIO()
            image.convert("RGB").save(buf, "PNG")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Image de référence illisible") from None
    relative = f"refs/{uuid.uuid4().hex}.png"
    path = base / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    return {"id": uuid.uuid4().hex, "path": relative, "role": role, "label": label[:200],
            "sha256": hashlib.sha256(buf.getvalue()).hexdigest(), "state": "unreviewed", "uploaded_at": now()}


def install(app):
    """Register once, including when called after the vendor root static mount."""
    if getattr(app.state, "workspace_api_installed", False):
        return
    router = APIRouter(prefix="/api/workspace")

    @router.get("")
    async def workspace():
        return {"profiles": _profiles(), "styles": _styles(), "models": await _catalog(), "batches": _batches(),
                "projects": [_summary(p) for p in store.list_projects(False)],
                "connection": {"has_proxy": bool(config.get("PROXY_API_KEY") and config.get("PROXY_BASE_URL"))},
                "settings": {k: config.get(k) for k in (
                    "PROJECT_PARALLEL", "IMAGE_CONCURRENCY", "LLM_CONCURRENCY", "RENDER_BACKEND")} | _default_models()}

    @router.get("/profiles")
    @router.get("/channels")
    async def profiles():
        return _profiles()

    @router.get("/styles")
    async def styles():
        return _styles()

    @router.get("/models")
    async def models():
        return await _catalog()

    @router.post("/models/refresh")
    async def refresh_models():
        return await _catalog()

    @router.put("/settings")
    async def settings(body: dict):
        catalog = await _catalog()
        selected = _models(body, catalog)
        style = copy.deepcopy(store.get_style("pov-history"))
        if not style:
            raise HTTPException(409, "Le style commun des chaînes doit être préparé avant de changer les modèles")
        style["visuals"]["image_model"] = selected["image"]
        style["thumbnail"]["model"] = selected["image"]
        store.save_style(style)
        config.update({"SCRIPT_MODEL": selected["text"], "FAST_MODEL": selected["text"]})
        return _default_models()

    @router.put("/profiles/{cid}")
    async def update_profile(cid: str, body: dict):
        profile = _profile(cid)
        style = copy.deepcopy(store.get_style(profile["style_id"]))
        for field, section, key in (("style_prompt", "visuals", "art_style"),
                                    ("thumbnail_prompt", "thumbnail", "style")):
            if field in body:
                style[section][key] = _text(body[field], field)
        if "references" in body:
            supplied = body["references"]
            existing = {r["path"]: r for r in profile["references"]}
            if not isinstance(supplied, list) or any(not isinstance(r, dict) for r in supplied):
                raise HTTPException(422, "Indiquez les références existantes dans l'ordre souhaité")
            paths = [r.get("path") for r in supplied]
            if any(not isinstance(path, str) or path not in existing for path in paths) or len(paths) != len(set(paths)):
                raise HTTPException(422, "Une référence doit déjà exister et ne peut apparaître qu'une fois ; ajoutez d'abord les nouveaux fichiers")
            style["workspace_references"] = [{k: v for k, v in existing[path].items() if k != "url"} for path in paths]
            style["visuals"]["style_refs"] = paths
            style["visuals"]["reference_sources"] = copy.deepcopy(style["workspace_references"])
        store.save_style(style)
        return _profile(cid)

    @router.post("/profiles/{cid}/references")
    async def profile_reference(cid: str, file: UploadFile = File(...), label: str = Form("")):
        profile = _profile(cid)
        ref = await _upload(file, store.style_dir(profile["style_id"]), "style", label)
        profile = _profile(cid)
        style = copy.deepcopy(store.get_style(profile["style_id"]))
        style["workspace_references"] = [{k: v for k, v in r.items() if k != "url"} for r in profile["references"]] + [ref]
        style["visuals"].setdefault("style_refs", []).append(ref["path"])
        store.save_style(style)
        return _profile(cid)

    @router.get("/projects")
    async def projects(archived: bool = False):
        return [_summary(p) for p in store.list_projects(archived)]

    @router.post("/projects", status_code=201)
    async def create_project(body: dict):
        catalog = await _catalog()
        return _full(_create(_prepare(body, catalog), catalog))

    @router.get("/projects/{pid}")
    async def project(pid: str):
        return _full(_project(pid))

    @router.put("/projects/{pid}/title")
    async def title(pid: str, body: dict):
        p = _project(pid, True)
        text = _text(body.get("title", ""), "title", required=True).strip()
        if len(text) > 240:
            raise HTTPException(422, "Le titre ne peut pas dépasser 240 caractères")
        p.update(title=text, title_auto=False)
        return _full(store.save_project(p))

    @router.get("/projects/{pid}/scenes/{sid}/references/{index}")
    async def scene_reference(pid: str, sid: int, index: int):
        p = _project(pid)
        scene = next((s for s in p.get("scenes", []) if s["id"] == sid), None)
        if not scene:
            raise HTTPException(404, "Plan introuvable")
        return FileResponse(_reference_path(p, scene, index), headers={"Cache-Control": "no-store"})

    @router.put("/projects/{pid}/script")
    async def script(pid: str, body: dict):
        p = _project(pid, True)
        text = _text(body.get("text"), "text")
        if len(text.encode("utf-8")) > MAX_SCRIPT or "\x00" in text:
            raise HTTPException(422, "Le script doit être un texte UTF-8 de moins de 1 Mo, sans caractère nul")
        if text != p.get("script"):
            p.update(script=text, custom_script=bool(text.strip()), voiceover_stale=bool(p.get("voiceover")),
                     render=None, prompts_approved=False)
            store.add_history(p, "codex_manual", text)
            for key in ("voiceover", "visuals", "render"):
                p["steps"][key].update(state="idle", msg="Texte modifié : la voix et les images restent à vérifier")
        p["steps"]["script"].update(state="done" if text.strip() else "idle")
        return _full(store.save_project(p))

    @router.put("/projects/{pid}/scenes")
    async def scenes(pid: str, body: dict):
        p = _project(pid, True)
        rows = body.get("scenes")
        if not isinstance(rows, list) or len(rows) > 2000:
            raise HTTPException(422, "Le découpage doit être une liste ordonnée de 2 000 plans maximum")
        output, seen = [], set()
        old = {s["id"]: s for s in p.get("scenes", [])}
        for row in rows:
            if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0 or row["id"] in seen:
                raise HTTPException(422, "Chaque plan doit avoir un numéro positif et unique")
            seen.add(row["id"])
            for field in ("text", "prompt", "location_id"):
                _text(row.get(field), field, required=True)
            if row["text"] not in p.get("script", ""):
                raise HTTPException(422, "La narration du plan doit reprendre un extrait exact du texte écrit")
            if not isinstance(row.get("characters"), list) or any(not isinstance(c, str) for c in row["characters"]):
                raise HTTPException(422, "Indiquez la liste des personnages nommés du plan")
            refs = row.get("references")
            if not isinstance(refs, list):
                raise HTTPException(422, "Indiquez les références du plan dans leur ordre exact")
            for ref in refs:
                if not isinstance(ref, dict) or ref.get("owner", "project") not in ("project", "style", "studio"):
                    raise HTTPException(422, "Chaque référence doit indiquer son fichier et son dossier : projet, style ou studio")
                if ref.get("owner") == "studio":
                    root = config.get("STUDIO_ROOT")
                    if not root or not ref.get("sha256"):
                        raise HTTPException(422, "Une référence du studio nécessite le dossier configuré et l'empreinte du fichier d'origine")
                    base = Path(root).resolve()
                else:
                    base = store.style_dir(p["style_id"]) if ref.get("owner") == "style" else store.project_dir(pid)
                digest = _file_digest(base, ref.get("path"))
                if not digest or ref.get("sha256") and digest != ref["sha256"]:
                    raise HTTPException(422, "Le fichier de référence est absent, modifié ou hors du dossier prévu")
            timed = "start" in row or "end" in row
            if timed:
                start, end = row.get("start"), row.get("end")
                if (any(type(x) not in (float, int) or not math.isfinite(x) for x in (start, end))
                        or start < 0 or end <= start):
                    raise HTTPException(422, "Le début et la fin du plan doivent être des durées valides, calées sur la voix réelle")
            image = row.get("image")
            if image and not _file_digest(store.project_dir(pid), image):
                raise HTTPException(422, "L'image du plan est absente ou hors du dossier du projet")
            allowed = ("id", "text", "prompt", "location_id", "characters", "references", "start", "end", "image", "motion")
            scene = {k: copy.deepcopy(row[k]) for k in allowed if k in row}
            # Presentation URLs are not authoring input and cannot affect review hashes.
            scene["references"] = [{k: v for k, v in ref.items() if k != "url"} for ref in scene["references"]]
            if old.get(row["id"], {}).get("codex_receipt"):
                scene["codex_receipt"] = copy.deepcopy(old[row["id"]]["codex_receipt"])
            scene.update(status="done" if image else "idle", prompt_author="codex",
                         human_review=old.get(row["id"], {}).get("human_review"))
            output.append(scene)
        p.update(scenes=output, render=None, prompts_approved=False)
        p["steps"]["visuals"].update(state="done" if output and all(s.get("image") for s in output) else "idle")
        p["steps"]["render"].update(state="idle")
        return _full(store.save_project(p))

    @router.post("/projects/{pid}/review")
    async def review(pid: str, body: dict):
        p = _project(pid, True)
        state = body.get("state")
        if state not in REVIEW_STATES:
            raise HTTPException(422, "Choisissez un état : vérifié, à corriger ou à vérifier")
        scope = body.get("scope", "scene")
        if scope == "scene":
            s = next((s for s in p.get("scenes", []) if s["id"] == body.get("scene_id")), None)
            if not s:
                raise HTTPException(404, "Plan introuvable")
            evidence = _scene_evidence(p, s)
        elif scope in ("script", "voiceover", "render"):
            evidence = _scope_evidence(p, scope)
        else:
            raise HTTPException(422, "Élément à vérifier inconnu")
        if state == "verified" and not evidence:
            raise HTTPException(409, "Validation impossible : le texte, un fichier ou une référence manque ou a été modifié")
        record = {"state": state, "notes": _text(body.get("notes", ""), "notes"),
                  "reviewer": _text(body.get("reviewer", "local_human"), "reviewer", required=True),
                  "source": "explicit_human_review", "reviewed_at": now(), "evidence": evidence}
        if scope == "scene":
            s["human_review"] = record
        else:
            p.setdefault("human_reviews", {})[scope] = record
        return _full(store.save_project(p))

    @router.post("/projects/{pid}/references")
    async def project_reference(pid: str, file: UploadFile = File(...), role: str = Form("location"), label: str = Form("")):
        _project(pid, True)
        if role not in ("location", "character", "pose", "style"):
            raise HTTPException(422, "Type de référence inconnu")
        ref = await _upload(file, store.project_dir(pid), role, label)
        p = _project(pid, True)
        p.setdefault("workspace_references", []).append(ref)
        return _full(store.save_project(p))

    @router.get("/batches")
    async def batches():
        return _batches()

    @router.post("/batches", status_code=201)
    async def batch(body: dict):
        rows = body.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100 or any(not isinstance(r, dict) for r in rows):
            raise HTTPException(422, "Le lot doit contenir entre 1 et 100 vidéos")
        name = _text(body.get("name", "Batch dirige"), "name", required=True)
        catalog = await _catalog()
        defaults = {key: body[key] for key in ("text_model", "image_model") if key in body}
        prepared = [_prepare(defaults | row, catalog) for row in rows]
        created = []
        previous_batches = copy.deepcopy(pipeline.list_batches())
        try:
            for item in prepared:
                created.append(_create(item, catalog))
            b = pipeline.save_batch([p["id"] for p in created], "review", name)
            b.update(workspace_directed=True, queue_state="queued_for_authoring",
                     model_snapshots={p["id"]: p["model_snapshot"] for p in created})
            batches = pipeline.list_batches()
            batches = [b if x["id"] == b["id"] else x for x in batches]
            write_json(pipeline.BATCHES_FILE, batches)
            for p in created:
                p["workspace_queue"]["batch_id"] = b["id"]
                store.save_project(p)
        except Exception:
            # Validation is completed before any creation; clean up partial store failures.
            for p in created:
                store.delete_project(p["id"])
            write_json(pipeline.BATCHES_FILE, previous_batches)
            raise
        return {"batch": b, "projects": [_full(p) for p in created]}

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_api_installed = True
