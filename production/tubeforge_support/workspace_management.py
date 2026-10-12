"""Editable styles and channel defaults, without changing existing projects."""
import copy
import math
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app import channels, store
from app.util import now, read_json, write_json
from . import workspace_api as api


def _text(value, field, limit=200, required=False):
    result = api._text(value, field, required=required)
    if len(result) > limit or "\x00" in result:
        raise HTTPException(422, f"The field {field} is too long or contains an invalid character")
    return result


def _style(sid, active=False):
    s = store.get_style(api._identifier(sid))
    if not s or active and s.get("archived"):
        raise HTTPException(404, "Visual style not found or archived")
    s = copy.deepcopy(s)
    s["workspace_references"] = api._style_references(s)
    return s


def _channel(cid):
    api._identifier(cid)
    return copy.deepcopy(next((c for c in read_json(channels.FILE, [])
                               if c.get("id") == cid and (cid in api.PROFILE_NAMES or c.get("workspace_managed"))), None))


def _save_channel(c):
    existing = read_json(channels.FILE, [])
    found = any(x.get("id") == c["id"] for x in existing)
    write_json(channels.FILE, [c if x.get("id") == c["id"] else x for x in existing] + ([] if found else [c]))
    return next(p for p in api._profiles(True) if p["id"] == c["id"])


def _update_style(s, body):
    if "image_provider" in body:
        if body["image_provider"] not in ("cli_proxy", "google_flow"):
            raise HTTPException(422, "Unknown image provider")
        s["workspace_image_provider"] = body["image_provider"]
    if "image_model" in body:
        s["visuals"]["image_model"] = _text(body["image_model"], "image model", 200, required=True).strip()
    for field, section, key in (("prompt", "visuals", "art_style"),
                                ("background_direction", "visuals", "background_direction"),
                                ("thumbnail_prompt", "thumbnail", "style")):
        if field in body:
            s[section][key] = _text(body[field], field, 60000, required=field == "prompt")
    if "name" in body:
        s["name"] = _text(body["name"], "name", required=True).strip()
    if "references" in body:
        supplied = body["references"]
        current = {r["path"]: r for r in s.get("workspace_references", [])}
        if not isinstance(supplied, list) or any(not isinstance(r, dict) for r in supplied):
            raise HTTPException(422, "Specify the existing references in their order")
        paths = [r.get("path") for r in supplied]
        if any(not isinstance(p, str) or p not in current for p in paths) or len(paths) != len(set(paths)):
            raise HTTPException(422, "References must already exist and cannot be repeated")
        s["workspace_references"] = [{k: v for k, v in current[p].items() if k not in ("url", "exists")} for p in paths]
        s["visuals"]["style_refs"] = paths
        s["visuals"]["reference_sources"] = copy.deepcopy(s["workspace_references"])
    for field, section in (("video_preview", "visuals"), ("thumbnail_preview", "thumbnail")):
        if field in body:
            path = body[field]
            if path is not None and not isinstance(path, str):
                raise HTTPException(422, "The preview must be an existing image path")
            allowed = {r["path"] for r in s.get("workspace_references", [])}
            allowed.add(s[section].get("preview"))
            if path and (path not in allowed or not api._file_digest(store.style_dir(s["id"]), path)):
                raise HTTPException(422, "Choose a preview from this style's images")
            s[section]["preview"] = path or None
    if "archived" in body:
        if not isinstance(body["archived"], bool):
            raise HTTPException(422, "Archived status must be true or false")
        if body["archived"]:
            if s["id"] == api._default_style_id():
                raise HTTPException(409, "The studio's shared style cannot be archived")
            if any(p["style_id"] == s["id"] for p in api._profiles()):
                raise HTTPException(409, "First change the default style of the channels that use this style")
        s["archived"] = body["archived"]
    s["updated"] = now()
    return s


def _update_channel(c, body):
    if "voice" in body:
        from .workspace_voice import voice_settings
        c["voice"] = dict(c.get("voice") or {}, **voice_settings(body["voice"]))
    for field, limit in (("name", 200), ("handle", 100), ("description", 5000), ("setting", 2000)):
        if field in body:
            c[field] = _text(body[field], field, limit, required=field == "name").strip()
    if "language" in body:
        if body["language"] not in ("English", "French", "Spanish", "German", "Italian", "Portuguese", "Japanese"):
            raise HTTPException(422, "Choose an available language")
        c["language"] = body["language"]
    if "target_minutes" in body:
        minutes = body["target_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or not (20 if c.get("historical_profile") else 3) <= minutes <= (25 if c.get("historical_profile") else 30):
            raise HTTPException(422, "Choose a target duration within this channel’s range")
        c["target_minutes"] = minutes
    if "style_id" in body:
        _style(body["style_id"], active=True)
        if c.get("style_id") != body["style_id"]:
            # Keep files and record old previews, but never label them as the new style.
            c.setdefault("preview_history", []).append({"style_id": c.get("style_id"),
                "video_preview": c.pop("video_preview", None), "thumbnail_preview": c.pop("thumbnail_preview", None),
                "changed_at": now()})
        c["style_id"] = body["style_id"]
    if "archived" in body:
        if not isinstance(body["archived"], bool):
            raise HTTPException(422, "Archived status must be true or false")
        if not body["archived"]:
            _style(c["style_id"], active=True)
        c["archived"] = body["archived"]
    c.update(workspace_managed=True, updated=now())
    return c


def _character_fields(s, body):
    name = _text(body.get("name", ""), "character", 100, required=True).strip()
    variant = api._identifier(body.get("variant", "default"))
    description = _text(body.get("description", ""), "character description", 6000, required=True).strip()
    entries = s.get("workspace_cast_registry") or {}
    if any(other != name and other.casefold() == name.casefold() for other in entries):
        raise HTTPException(422, "Use the exact name of the existing character")
    for field in ("is_main", "verify"):
        if field in body and type(body[field]) is not bool:
            raise HTTPException(422, "The main character choice and validation must be explicit")
    return name, variant, description


def _save_character(s, name, variant, description, ref=None, is_main=None, verify=False):
    entries = s.setdefault("workspace_cast_registry", {})
    entry = entries.setdefault(name, {"required": True, "variants": {}})
    selected = entry["variants"].get(variant)
    if selected is None:
        if not ref:
            raise HTTPException(404, "Character variant not found")
        selected = entry["variants"][variant] = {"description": description, "references": []}
    selected["description"] = description
    if ref:
        selected["references"].append({**ref, "owner": "style", "role": "identity", "character": name,
                                       "variant": variant, "review_state": "unreviewed"})
    if verify:
        for image in selected["references"]:
            digest = api._file_digest(store.style_dir(s["id"]), image.get("path"))
            if not digest or digest != image.get("sha256"):
                raise HTTPException(409, "A reference has changed or cannot be found; import a new image")
            image["review_state"] = "verified"
    if is_main:
        s["workspace_main_character"] = name
    elif is_main is False and s.get("workspace_main_character") == name:
        s.pop("workspace_main_character", None)
    s["updated"] = now()
    store.save_style(s)
    return next(item for item in api._styles(True) if item["id"] == s["id"])


def install(app):
    if getattr(app.state, "workspace_management_installed", False):
        return
    router = APIRouter(prefix="/api/workspace/management")

    @router.get("")
    async def index():
        return {"channels": api._profiles(True), "styles": api._styles(True)}

    @router.post("/styles", status_code=201)
    async def create_style(body: dict):
        base = _style(body["base_id"], active=True) if body.get("base_id") else _style(api._default_style_id(), active=True)
        s = copy.deepcopy(base)
        s["id"] = "style-" + uuid.uuid4().hex[:12]
        s.update(archived=False, created=now(), workspace_managed=True)
        if not body.get("base_id"):
            for key in ("workspace_cast_registry", "workspace_main_character", "workspace_character_references"):
                s.pop(key, None)
            s["workspace_references"] = []
            for section, key in (("visuals", "style_refs"), ("visuals", "reference_sources")):
                s[section][key] = []
            s["visuals"]["preview"] = None
            s["thumbnail"]["preview"] = None
        name = _text(body.get("name", ""), "name", required=True)
        if not body.get("base_id"):
            _text(body.get("prompt", ""), "video prompt", 60000, required=True)
        s = _update_style(s, body | {"name": name})
        if not s["visuals"].get("art_style", "").strip():
            raise HTTPException(422, "The video style prompt is required")
        if body.get("base_id"):
            import shutil
            shutil.copytree(store.style_dir(base["id"]), store.style_dir(s["id"]))
        store.save_style(s)
        return next(item for item in api._styles(True) if item["id"] == s["id"])

    @router.put("/styles/{sid}")
    async def update_style(sid: str, body: dict):
        store.save_style(_update_style(_style(sid), body))
        return next(item for item in api._styles(True) if item["id"] == sid)

    @router.post("/styles/{sid}/references")
    async def reference(sid: str, file: UploadFile = File(...), label: str = Form("")):
        s = _style(sid, active=True)
        ref = await api._upload(file, store.style_dir(sid), "style", label)
        s = _style(sid, active=True)
        s.setdefault("workspace_references", []).append(ref)
        s["visuals"].setdefault("style_refs", []).append(ref["path"])
        s["visuals"]["reference_sources"] = copy.deepcopy(s["workspace_references"])
        store.save_style(s)
        return ref

    @router.post("/styles/{sid}/characters")
    async def upload_character(sid: str, file: UploadFile = File(...), name: str = Form(...),
                               description: str = Form(...), variant: str = Form("default"),
                               is_main: bool = Form(False)):
        s = _style(sid, active=True)
        name, variant, description = _character_fields(s, {"name": name, "variant": variant,
                                                        "description": description, "is_main": is_main})
        ref = await api._upload(file, store.style_dir(sid), "character", name)
        s = _style(sid, active=True)
        _character_fields(s, {"name": name, "variant": variant, "description": description, "is_main": is_main})
        return _save_character(s, name, variant, description, ref=ref, is_main=is_main)

    @router.put("/styles/{sid}/characters")
    async def update_character(sid: str, body: dict):
        s = _style(sid, active=True)
        name, variant, description = _character_fields(s, body)
        return _save_character(s, name, variant, description, is_main=body.get("is_main"),
                               verify=body.get("verify", False))

    @router.post("/channels", status_code=201)
    async def create_channel(body: dict):
        if not body.get("voice"):
            raise HTTPException(422, "Specify the ElevenLabs voice ID for this new channel")
        if not body.get("style_id"):
            raise HTTPException(422, "Choose the channel's default style")
        base = _style(api._default_style_id(), active=True)
        c = {"id": "channel-" + uuid.uuid4().hex[:12], "name": "", "handle": "", "description": "",
             "language": "English", "kind": "long", "auto_resolve": False, "target_minutes": 22,
             "voice": copy.deepcopy(base["voice"]), "created": now(), "archived": False}
        c["voice"]["provider"] = "algrow"
        return _save_channel(_update_channel(c, body | {"name": _text(body.get("name", ""), "name", required=True)}))

    @router.put("/channels/{cid}")
    async def update_channel(cid: str, body: dict):
        c = _channel(cid)
        if not c:
            raise HTTPException(404, "Channel not found")
        return _save_channel(_update_channel(c, body))

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_management_installed = True
