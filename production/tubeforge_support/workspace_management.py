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
    if 'camera_policy' in body:
        if body['camera_policy'] not in ('stable', 'varied'):
            raise HTTPException(422, 'Choose a stable camera axis or varied camera views')
        s['visuals']['camera_policy'] = body['camera_policy']
    if 'background_mode' in body:
        if body['background_mode'] not in ('free', 'consistent'):
            raise HTTPException(422, 'Choose free backgrounds or consistent locations')
        s['visuals']['background_mode'] = body['background_mode']
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
    if 'drawing_reference_path' in body:
        path = body['drawing_reference_path']
        ref = next((row for row in s.get('workspace_references', []) if row.get('path') == path), None)
        if not ref or api._file_digest(store.style_dir(s['id']), path) != ref.get('sha256'):
            raise HTTPException(422, 'Choose an existing drawing reference that has not changed')
        ref.update(review_state='verified', role='style-only', owner='style')
        s['workspace_drawing_reference'] = copy.deepcopy(ref)
        s['visuals']['reference_sources'] = copy.deepcopy(s['workspace_references'])
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
            s['visuals']['background_mode'] = 'free'
            for key in ("workspace_cast_registry", "workspace_main_character", "workspace_character_references", "workspace_drawing_reference"):
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

    @router.post('/presets', status_code=201)
    async def create_preset(body: dict):
        if not body.get('voice'):
            raise HTTPException(422, 'Specify the ElevenLabs voice for this channel')
        visual = body.get('preset', {})
        if not isinstance(visual, dict):
            raise HTTPException(422, 'Enter the visual preset settings')
        name = _text(body.get('name', ''), 'name', required=True).strip()
        template = body.get('template_style_id')
        base = _style(template or api._default_style_id(), active=True)
        c = {'id': 'channel-' + uuid.uuid4().hex[:12], 'name': name, 'handle': '', 'description': '',
             'language': 'English', 'kind': 'long', 'auto_resolve': False, 'target_minutes': 15,
             'voice': copy.deepcopy(base['voice']), 'created': now(), 'archived': False}
        # Validate channel inputs before creating files; no voice/image calls happen here.
        c = _update_channel(c, {k: v for k, v in body.items() if k != 'style_id'})
        style_body = visual | {'name': name}
        if template:
            style_body['base_id'] = template
        else:
            style_body.pop('base_id', None)
        previous_channels = read_json(channels.FILE, [])
        style = await create_style(style_body)
        c['style_id'] = style['id']
        try:
            return {'channel': _save_channel(c), 'preset': style}
        except Exception:
            write_json(channels.FILE, previous_channels)
            # Keep imported files recoverable rather than permanently deleting them.
            orphan = _style(style['id'])
            orphan['archived'] = True
            store.save_style(orphan)
            raise

    @router.put('/presets/{cid}')
    async def update_preset(cid: str, body: dict):
        c = _channel(cid)
        if not c:
            raise HTTPException(404, 'Channel not found')
        visual = body.get('preset', {})
        if not isinstance(visual, dict):
            raise HTTPException(422, 'Enter the visual preset settings')
        original = _style(c['style_id'])
        updated_channel = _update_channel(copy.deepcopy(c), {k: v for k, v in body.items() if k != 'style_id'})
        # Every field is validated before any existing record is written.
        updated_style = _update_style(copy.deepcopy(original), visual | {'name': updated_channel['name']})
        edits = body.get('characters', [])
        if not isinstance(edits, list) or len(edits) > 500 or any(not isinstance(item, dict) for item in edits):
            raise HTTPException(422, 'Enter the existing character variants')
        main_names = set()
        for item in edits:
            name, variant, description = _character_fields(updated_style, item)
            selected = (updated_style.get('workspace_cast_registry', {}).get(name, {}).get('variants', {}).get(variant))
            if not selected:
                raise HTTPException(404, 'Import this character variant before saving it')
            selected['description'] = description
            if item.get('verify'):
                for ref in selected['references']:
                    if api._file_digest(store.style_dir(original['id']), ref.get('path')) != ref.get('sha256'):
                        raise HTTPException(409, 'The character reference changed; import a new image')
                    ref['review_state'] = 'verified'
            if item.get('is_main'):
                main_names.add(name)
        if len(main_names) > 1:
            raise HTTPException(422, 'Choose one main character for this preset')
        if main_names:
            updated_style['workspace_main_character'] = next(iter(main_names))
        elif any(item.get('name') == updated_style.get('workspace_main_character') and item.get('is_main') is False for item in edits):
            updated_style.pop('workspace_main_character', None)
        others = [row for row in api._profiles(True) if row['id'] != cid and row['style_id'] == original['id']]
        if others:
            import shutil
            updated_style['id'] = 'style-' + uuid.uuid4().hex[:12]
            updated_style.update(is_default=False, workspace_managed=True, archived=False, created=now())
            shutil.copytree(store.style_dir(original['id']), store.style_dir(updated_style['id']))
            updated_channel['style_id'] = updated_style['id']
        previous_channels = read_json(channels.FILE, [])
        store.save_style(updated_style)
        try:
            channel = _save_channel(updated_channel)
        except Exception:
            write_json(channels.FILE, previous_channels)
            if others:
                updated_style['archived'] = True
                store.save_style(updated_style)
            else:
                store.save_style(original)
            raise
        return {'channel': channel, 'preset': next(row for row in api._styles(True) if row['id'] == updated_style['id'])}

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_management_installed = True
