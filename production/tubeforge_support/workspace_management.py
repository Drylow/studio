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
        raise HTTPException(422, f"Le champ {field} est trop long ou contient un caractère invalide")
    return result


def _style(sid, active=False):
    s = store.get_style(api._identifier(sid))
    if not s or active and s.get("archived"):
        raise HTTPException(404, "Style visuel introuvable ou archivé")
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
    for field, section, key in (("prompt", "visuals", "art_style"),
                                ("background_direction", "visuals", "background_direction"),
                                ("thumbnail_prompt", "thumbnail", "style")):
        if field in body:
            s[section][key] = _text(body[field], field, 60000, required=field == "prompt")
    if "name" in body:
        s["name"] = _text(body["name"], "nom", required=True).strip()
    if "references" in body:
        supplied = body["references"]
        current = {r["path"]: r for r in s.get("workspace_references", [])}
        if not isinstance(supplied, list) or any(not isinstance(r, dict) for r in supplied):
            raise HTTPException(422, "Indiquez les références existantes dans leur ordre")
        paths = [r.get("path") for r in supplied]
        if any(not isinstance(p, str) or p not in current for p in paths) or len(paths) != len(set(paths)):
            raise HTTPException(422, "Les références doivent déjà exister et ne peuvent pas être répétées")
        s["workspace_references"] = [{k: v for k, v in current[p].items() if k not in ("url", "exists")} for p in paths]
        s["visuals"]["style_refs"] = paths
        s["visuals"]["reference_sources"] = copy.deepcopy(s["workspace_references"])
    for field, section in (("video_preview", "visuals"), ("thumbnail_preview", "thumbnail")):
        if field in body:
            path = body[field]
            if path is not None and not isinstance(path, str):
                raise HTTPException(422, "L'aperçu doit être un chemin d'image existant")
            allowed = {r["path"] for r in s.get("workspace_references", [])}
            allowed.add(s[section].get("preview"))
            if path and (path not in allowed or not api._file_digest(store.style_dir(s["id"]), path)):
                raise HTTPException(422, "Choisissez un aperçu parmi les images de ce style")
            s[section]["preview"] = path or None
    if "archived" in body:
        if not isinstance(body["archived"], bool):
            raise HTTPException(422, "Le statut archivé doit être vrai ou faux")
        if body["archived"]:
            if s["id"] == "pov-history":
                raise HTTPException(409, "Le style commun du studio ne peut pas être archivé")
            if any(p["style_id"] == s["id"] for p in api._profiles()):
                raise HTTPException(409, "Changez d'abord le style par défaut des chaînes qui utilisent ce style")
        s["archived"] = body["archived"]
    s["updated"] = now()
    return s


def _update_channel(c, body):
    for field, limit in (("name", 200), ("handle", 100), ("description", 5000), ("setting", 2000)):
        if field in body:
            c[field] = _text(body[field], field, limit, required=field == "name").strip()
    if "language" in body:
        if body["language"] not in ("English", "French", "Spanish", "German", "Italian", "Portuguese", "Japanese"):
            raise HTTPException(422, "Choisissez une langue disponible")
        c["language"] = body["language"]
    if "target_minutes" in body:
        minutes = body["target_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or not 20 <= minutes <= 25:
            raise HTTPException(422, "La durée cible doit être comprise entre 20 et 25 minutes")
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
            raise HTTPException(422, "Le statut archivé doit être vrai ou faux")
        if not body["archived"]:
            _style(c["style_id"], active=True)
        c["archived"] = body["archived"]
    c.update(workspace_managed=True, updated=now())
    return c


def install(app):
    if getattr(app.state, "workspace_management_installed", False):
        return
    router = APIRouter(prefix="/api/workspace/management")

    @router.get("")
    async def index():
        return {"channels": api._profiles(True), "styles": api._styles(True)}

    @router.post("/styles", status_code=201)
    async def create_style(body: dict):
        base = _style(body["base_id"], active=True) if body.get("base_id") else _style("pov-history", active=True)
        s = copy.deepcopy(base)
        s["id"] = "style-" + uuid.uuid4().hex[:12]
        s.update(archived=False, created=now(), workspace_managed=True)
        if not body.get("base_id"):
            s["workspace_references"] = []
            for section, key in (("visuals", "style_refs"), ("visuals", "reference_sources")):
                s[section][key] = []
            s["visuals"]["preview"] = None
            s["thumbnail"]["preview"] = None
        name = _text(body.get("name", ""), "nom", required=True)
        if not body.get("base_id"):
            _text(body.get("prompt", ""), "prompt vidéo", 60000, required=True)
        s = _update_style(s, body | {"name": name})
        if not s["visuals"].get("art_style", "").strip():
            raise HTTPException(422, "Le prompt du style vidéo est requis")
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

    @router.post("/channels", status_code=201)
    async def create_channel(body: dict):
        if not body.get("style_id"):
            raise HTTPException(422, "Choisissez le style par défaut de la chaîne")
        base = _style("pov-history", active=True)
        c = {"id": "channel-" + uuid.uuid4().hex[:12], "name": "", "handle": "", "description": "",
             "language": "English", "kind": "long", "auto_resolve": False, "target_minutes": 22,
             "voice": copy.deepcopy(base["voice"]), "created": now(), "archived": False}
        c["voice"]["provider"] = "algrow"
        return _save_channel(_update_channel(c, body | {"name": _text(body.get("name", ""), "nom", required=True)}))

    @router.put("/channels/{cid}")
    async def update_channel(cid: str, body: dict):
        c = _channel(cid)
        if not c:
            raise HTTPException(404, "Chaîne introuvable")
        return _save_channel(_update_channel(c, body))

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_management_installed = True
