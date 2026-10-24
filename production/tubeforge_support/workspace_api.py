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

from app import channels, config, google_flow, llm, pipeline, store
from app.util import now, read_json, write_json
from .workspace_identity import current_owner, owner_of, personal_projects


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
        raise HTTPException(422, "Invalid identifier")
    return value


def _text(value, field, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise HTTPException(422, f"The field {field} must contain text" + (" and cannot be empty" if required else ""))
    return value


def _visual_policy():
    return read_json(config.DATA / "workspace-visual-policy.json", {}) or {}


def _default_style_id():
    return _identifier(_visual_policy().get("default_style_id", "pov-history"))


def _check_image_provider(provider, style_id=None):
    selected = store.get_style(style_id) if style_id else None
    required = (selected or {}).get("workspace_image_provider") or _visual_policy().get("image_provider")
    if required and provider != required:
        raise HTTPException(422, "Use the image provider configured for this style")


def _project(pid, writable=False):
    p = store.get_project(_identifier(pid))
    if not p or not p.get("codex_directed"):
        raise HTTPException(404, "Codex-led project not found")
    if writable:
        external = p.get('workspace_external_execution') or {}
        if external.get('backend') == 'runpod' and external.get('state') in ('queued', 'running', 'cleanup_required'):
            raise HTTPException(409, 'A RunPod render is reserved; finish or reconcile its job before editing')
        from . import workspace_generation as generation
        if (pipeline.is_running(pid) or generation.batch_running(pid)
                or pid in generation._active_projects):
            raise HTTPException(409, "A task is in progress on this project")
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


def _style_references(style):
    refs = copy.deepcopy(style.get("workspace_references", []))
    if not refs:
        sources = style.get("visuals", {}).get("reference_sources", [])
        refs = [{"path": path, "state": "unreviewed"} | next(
            (r for r in sources if isinstance(r, dict) and r.get("path", r.get("file")) == path), {})
            for path in style.get("visuals", {}).get("style_refs", [])]
    return refs


def _profiles(include_archived=False):
    # Unlike list_channels(), this read does not seed unrelated vendor channels.
    saved = {c["id"]: c for c in read_json(channels.FILE, []) or [] if isinstance(c, dict) and c.get("id")}
    out = []
    visible = dict(PROFILE_NAMES)
    visible.update({cid: c.get("name", cid) for cid, c in saved.items() if c.get("workspace_managed")})
    for cid, name in visible.items():
        c = saved.get(cid, {})
        if c.get("archived") and not include_archived:
            continue
        sid = c.get("style_id", _default_style_id())
        style = store.get_style(_identifier(sid)) or {}
        refs = _style_references(style)
        for ref in refs:
            ref["url"] = f"/style-media/{sid}/{ref['path']}"
            ref["exists"] = bool(_file_digest(store.style_dir(sid), ref["path"]))
        video_preview = c.get("video_preview") or style.get("visuals", {}).get("preview")
        thumbnail_preview = c.get("thumbnail_preview") or style.get("thumbnail", {}).get("preview")
        out.append({"id": cid, "name": c.get("name", name), "style_id": sid,
                    "style_name": style.get("name", sid), "archived": bool(c.get("archived")),
                    "handle": c.get("handle", ""), "description": c.get("description", ""),
                    "language": c.get("language", "English"),
                    "voice": dict(style.get("voice") or {}, **(c.get("voice") or {})),
                    "setting": c.get("setting", ""), "historical_profile": c.get("historical_profile", False),
                    "configured": bool(c and style and not style.get("archived")), "duration_minutes_min": 20 if c.get('historical_profile') else 3,
                    "duration_minutes_max": 25 if c.get('historical_profile') else 30,
                    "target_minutes": c.get("target_minutes", 22),
                    "style_prompt": style.get("visuals", {}).get("art_style", ""),
                    "thumbnail_prompt": style.get("thumbnail", {}).get("style", ""),
                    "background_direction": style.get("visuals", {}).get("background_direction", ""),
                    "video_preview": video_preview, "thumbnail_preview": thumbnail_preview,
                    "video_preview_url": f"/style-media/{sid}/{video_preview}" if video_preview else None,
                    "thumbnail_preview_url": f"/style-media/{sid}/{thumbnail_preview}" if thumbnail_preview else None,
                    "preview_label": c.get("preview_label", "Existing preview"),
                    "references": refs,
                    "reference_update_pending": style.get("visuals", {}).get("reference_update_pending", True),
                    "reference_status": c.get("reference_status", "waiting_for_user_references")})
    return out


def _profile(cid):
    profile = next((p for p in _profiles() if p["id"] == cid), None)
    if not profile:
        raise HTTPException(422, "Unknown channel")
    if not profile["configured"]:
        raise HTTPException(409, "The channel and its style must be prepared before creating a video")
    return profile


def _styles(include_archived=False):
    from . import workspace_characters as cast
    out = []
    for path in sorted(config.STYLES_DIR.glob("*/style.json")):
        raw = read_json(path, {})
        if not isinstance(raw, dict) or raw.get("archived") and not include_archived:
            continue
        sid = _identifier(path.parent.name)
        style = store.get_style(sid)
        if style:
            visuals = style.get("visuals", {})
            out.append({"id": sid, "name": style.get("name", sid),
                        "characters": cast.style_summary(style),
                        "main_character": style.get("workspace_main_character"),
                        "drawing_reference_path": (style.get('workspace_drawing_reference') or {}).get('path'),
                        "image_provider": style.get("workspace_image_provider"),
                        "image_model": visuals.get("image_model", ""),
                        "is_default": sid == _default_style_id(),
                        "archived": bool(style.get("archived")),
                        "prompt": visuals.get("art_style", ""),
                        "background_direction": visuals.get("background_direction", ""),
                        "background_mode": visuals.get('background_mode', 'free'),
                        "thumbnail_prompt": style.get("thumbnail", {}).get("style", ""),
                        "video_preview_url": f"/style-media/{sid}/{visuals['preview']}" if visuals.get("preview") else None,
                        "thumbnail_preview_url": f"/style-media/{sid}/{style['thumbnail']['preview']}" if style.get("thumbnail", {}).get("preview") else None,
                        "references": [{**r, "url": f"/style-media/{sid}/{r['path']}",
                                        "exists": bool(_file_digest(store.style_dir(sid), r["path"]))}
                                       for r in _style_references(style)]})
    return out


def _default_models():
    style = store.get_style(_default_style_id()) or {}
    provider = config.get("IMAGE_PROVIDER") or "cli_proxy"
    return {"text_model": config.get("SCRIPT_MODEL") or config.get("FAST_MODEL"),
            "image_model": google_flow.setting("USEAPI_IMAGE_MODEL") if provider == "google_flow" else style.get("visuals", {}).get("image_model", ""),
            "image_provider": provider}


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


async def _proxy_catalog():
    result = {"available": False, "models": [], "defaults": _default_models(),
              "checked_at": now(), "error": None, "generation_tested": False,
              "provider_connection": "not_tested"}
    if not config.get("PROXY_BASE_URL") or not config.get("PROXY_API_KEY"):
        result["error"] = "The Proxy CLI is not configured"
        return result
    try:
        response = await llm.client().get(llm._url("/models"), headers=llm._headers(),
                                          timeout=15, follow_redirects=False)
        if response.status_code != 200:
            result["error"] = f"The CLI Proxy catalog is unavailable (error {response.status_code})"
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
        result["error"] = "The CLI Proxy catalog is unavailable"
    return result


async def _catalog():
    result = await _proxy_catalog()
    proxy_available = result["available"]
    for item in result["models"]:
        item["provider"] = "cli_proxy"
        if (_visual_policy().get("image_provider") == "google_flow"
                and not any(s.get("image_provider") == "cli_proxy" for s in _styles())):
            item["capabilities"]["image"] = False
    flow = await google_flow.status()
    result["image_provider_policy"] = _visual_policy().get("image_provider")
    result["providers"] = {"cli_proxy": {"available": proxy_available, "error": result["error"]},
                           "google_flow": flow}
    model = google_flow.setting("USEAPI_IMAGE_MODEL")
    if flow["available"] and isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_.+-]{1,100}", model):
        result["models"].append({"id": model, "provider": "google_flow", "label": "Google Flow · " + model,
                                "capabilities": {"text": False, "image": True}, "suggested_role": "image",
                                "suggested_role_source": "configured_provider", "capability_verified": True})
    result["available"] = bool(result["models"]) or proxy_available
    if result["available"]:
        result["error"] = None
    return result


def _image_provider(body, catalog, defaults=None):
    defaults = defaults or catalog["defaults"]
    mid = body.get("image_model", defaults.get("image_model"))
    provider = body.get("image_provider")
    if provider is None:
        if mid == defaults.get("image_model"):
            provider = defaults.get("image_provider", "cli_proxy")
        else:
            matches = [m for m in catalog["models"] if m["id"] == mid and m["capabilities"]["image"] is not False]
            provider = matches[0].get("provider", "cli_proxy") if len(matches) == 1 else "cli_proxy"
    if provider not in ("cli_proxy", "google_flow"):
        raise HTTPException(422, "Choose an available image provider")
    _check_image_provider(provider, body.get("style_id"))
    return provider


def _models(body, catalog, defaults=None):
    if not catalog["available"]:
        raise HTTPException(503, catalog["error"])
    selected = {}
    defaults = defaults or catalog["defaults"]
    for role in ("text", "image"):
        key = f"{role}_model"
        mid = body.get(key, defaults.get(key))
        provider = _image_provider(body, catalog, defaults) if role == "image" else "cli_proxy"
        entry = next((m for m in catalog["models"] if m["id"] == mid and m.get("provider", "cli_proxy") == provider), None)
        if not entry:
            raise HTTPException(422, f"Choose {key} in the provider\'s current catalog")
        if entry["capabilities"][role] is False:
            raise HTTPException(422, f"The model chosen for {key} ne propose pas ce type de sortie")
        selected[role] = mid
    return selected


def _prepare(body, catalog):
    if body.get("auto_run") or body.get("mode", "review") != "review":
        raise HTTPException(422, "These videos must be reviewed and do not start automatically")
    profile = _profile(body.get("profile_id", body.get("channel_id")))
    title = _text(body.get("title", ""), "title", required=True)
    if len(title.strip()) > 240:
        raise HTTPException(422, "The title cannot exceed 240 characters")
    topic = _text(body.get("topic", ""), "topic")
    script = _text(body.get("custom_script", ""), "custom_script")
    if len(script.encode("utf-8")) > MAX_SCRIPT or "\x00" in script:
        raise HTTPException(422, "The script must be UTF-8 text under 1 MB, with no null character")
    sid = _identifier(body.get("style_id", profile["style_id"]))
    if not any(style["id"] == sid for style in _styles()):
        raise HTTPException(422, "Choose an available visual style")
    minutes = None if script.strip() else body.get("duration_minutes", profile.get("target_minutes", 22))
    lower, upper = profile['duration_minutes_min'], profile['duration_minutes_max']
    if (not script.strip() and (isinstance(minutes, bool) or not isinstance(minutes, (float, int))
            or not math.isfinite(minutes) or not lower <= minutes <= upper)):
        raise HTTPException(422, f'Target duration must be between {lower} and {upper} minutes')
    selected = store.get_style(sid) or {}
    defaults = dict(catalog["defaults"])
    if selected.get("workspace_image_provider"):
        defaults.update(image_provider=selected["workspace_image_provider"],
                        image_model=selected.get("visuals", {}).get("image_model", ""))
    model_body = body | {"style_id": sid}
    return {"profile": profile, "title": title, "topic": topic, "script": script, "style_id": sid,
            "target_duration_seconds": minutes * 60 if minutes is not None else None, "models": _models(model_body, catalog, defaults),
            "image_provider": _image_provider(model_body, catalog, defaults)}


def _create(prepared, catalog):
    models, profile = prepared["models"], prepared["profile"]
    selected_style = store.get_style(prepared["style_id"])
    channel_style = store.get_style(profile["style_id"])
    p = store.create_project(prepared["title"], prepared["style_id"], topic=prepared["topic"],
                             mode="review", custom_script=prepared["script"], characters=[], overrides={
                                 "models.text": models["text"], "models.image": models["image"],
                                 "script.model": models["text"], "script.fast_model": models["text"],
                                 "visuals.image_model": models["image"],
                                 "visuals.image_provider": prepared["image_provider"],
                                 "visuals.aspect": "16:9",
                                 "thumbnail.image_provider": prepared["image_provider"],
                                 "thumbnail.model": models["image"], "thumbnail.count": 0,
                                 "visuals.auto_characters": False, "visuals.continuity": "off",
                                 "visuals.background_mode": selected_style.get('visuals', {}).get('background_mode', 'free'),
                             })
    # A visual preset must not replace the channel's configured voice provider.
    p["settings"]["voice"] = copy.deepcopy(channel_style["voice"])
    saved_channel = next((c for c in read_json(channels.FILE, []) if c.get("id") == profile["id"]), {})
    p["settings"]["voice"].update({k: v for k, v in saved_channel.get("voice", {}).items() if v not in (None, "")})
    if p["settings"]["voice"].get("provider") not in ("algrow", "ai33"):
        p["settings"]["voice"]["provider"] = "algrow"
    p["settings"]["language"] = profile["language"]
    p.update(codex_directed=True, channel_id=profile["id"], profile_id=profile["id"],
             main_character=selected_style.get("workspace_main_character"),
             target_duration_seconds=prepared["target_duration_seconds"],
             script=prepared["script"], auto_promo_shorts=0, prompts_approved=False,
             workspace_queue={"state": "queued_for_authoring", "created": now()},
             model_snapshot={"text_model": models["text"], "image_model": models["image"],
                             "image_provider": prepared["image_provider"], "text_provider": "cli_proxy",
                             "selected_at": now(), "catalog_checked_at": catalog["checked_at"],
                             "transport": prepared["image_provider"], "capabilities": {
                                 role: next(m["capabilities"] for m in catalog["models"] if m["id"] == mid and
                                            m.get("provider", "cli_proxy") == (prepared["image_provider"] if role == "image" else "cli_proxy"))
                                 for role, mid in models.items()}},
             human_reviews={}, workspace_references=[],
             style_snapshot={"id": prepared["style_id"], "name": selected_style["name"],
                             "selected_at": now(),
                             "prompt": selected_style["visuals"].get("art_style", ""),
                             "background_direction": selected_style["visuals"].get("background_direction", "")})
    p['style_snapshot']['background_mode'] = p['settings']['visuals']['background_mode']
    if p.get("script_history"):
        p["script_history"][-1]["text"] = prepared["script"]
    if selected_style.get("workspace_cast_registry"):
        p["style_cast_snapshot"] = copy.deepcopy(selected_style["workspace_cast_registry"])
    p['drawing_reference_snapshot'] = copy.deepcopy(selected_style.get('workspace_drawing_reference'))
    return store.save_project(p)


def _validate_drawing_reference(p, scene):
    guide = p.get('drawing_reference_snapshot')
    if not guide:
        return
    expected = _file_digest(store.style_dir(p['style_id']), guide.get('path'))
    if not expected or expected != guide.get('sha256') or guide.get('review_state') != 'verified':
        raise HTTPException(409, 'The preset drawing guide is missing or changed')
    for ref in scene.get('references') or []:
        if not isinstance(ref, dict) or ref.get('role') not in ('style', 'style-only'):
            continue
        folder = store.style_dir(p['style_id']) if ref.get('owner') == 'style' else store.project_dir(p['id'])
        if (ref.get('sha256') == expected and ref.get('review_state') == 'verified'
                and _file_digest(folder, ref.get('path')) == expected):
            return
    raise HTTPException(422, 'Attach the preset drawing guide to this shot; character references alone are insufficient')


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
    from . import workspace_characters, workspace_locations
    authoring_keys = ("text", "prompt", "start", "end", "location_id", "characters", "references", "motion", "codex_receipt")
    if "character_variants" in s:
        authoring_keys += ("character_variants",)
    authoring_keys += tuple(key for key in workspace_locations.SCENE_KEYS if key in s)
    if workspace_locations.mode(p) == 'consistent' and workspace_locations.registry(p):
        try:
            workspace_locations.validate(p, s)
        except HTTPException:
            return None
    result = {"image_sha256": image_hash, "references": refs,
              "authoring_sha256": _hash({k: s.get(k) for k in authoring_keys}),
              "script_sha256": _hash(p.get("script")), "models_sha256": _hash(p.get("model_snapshot"))}
    entries = workspace_characters.summary(p)
    selected_variants = s.get("character_variants") or {}
    if entries:
        result["cast_registry_sha256"] = _hash({
            name: entries[name]["variants"].get(key)
            for name, key in selected_variants.items() if name in entries})
    if workspace_locations.mode(p) == 'consistent' and workspace_locations.registry(p):
        result['location_registry_sha256'] = _hash(workspace_locations.summary(p).get(s.get('location_id')))
    return result


def _reference_path(p, s, index):
    receipt = (s.get("codex_receipt") or {}).get("references", [])
    refs = s.get("references") or receipt
    if index < 0 or index >= len(refs) or not isinstance(refs[index], dict):
        raise HTTPException(404, "Reference not found")
    ref = refs[index]
    owner = ref.get("owner", "studio" if refs is receipt else "project")
    if owner == "studio":
        root = config.get("STUDIO_ROOT")
        if not root or not ref.get("sha256"):
            raise HTTPException(404, "This studio reference has no saved file fingerprint")
        base = Path(root).resolve()
    elif owner == "style":
        base = store.style_dir(p["style_id"])
    elif owner == "project":
        base = store.project_dir(p["id"])
    else:
        raise HTTPException(404, "Unknown reference location")
    digest = _file_digest(base, ref.get("path"))
    if not digest or ref.get("sha256") and digest != ref["sha256"]:
        raise HTTPException(409, "The reference is missing or has been modified")
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
        issues.append("This test or excerpt is not a complete episode to publish")
    voice = p.get("voiceover") or {}
    duration = voice.get("duration")
    if p.get("voiceover_stale"):
        issues.append("The voice needs to be redone after the text change")
    if not _file_digest(store.project_dir(p["id"]), voice.get("file")):
        issues.append("The voice file is missing")
    duration_valid = type(duration) in (int, float) and math.isfinite(duration) and duration > 0
    if not duration_valid:
        issues.append("The actual voice duration is not recorded")
    scenes = p.get("scenes", [])
    if not scenes:
        issues.append("The cut written by Codex is missing")
    else:
        evidence = scene_evidence if scene_evidence is not None else [_scene_evidence(p, s) for s in scenes]
        if any(not item for item in evidence):
            issues.append("An image or shot reference is missing or has been modified")
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
            issues.append("The shots must cover the entire voice, with no gaps or overlaps")
        if " ".join(" ".join(s.get("text", "").split()) for s in scenes) != " ".join(p.get("script", "").split()):
            issues.append("The shot excerpts must reproduce all the exact text, in order")
    render = p.get("render")
    if render:
        if render.get("qa_pending"):
            issues.append("The technical render check remains to be completed")
        if not _file_digest(store.project_dir(p["id"]), render.get("file")):
            issues.append("The render file is missing")
    if p.get("error"):
        issues.append("A production error remains to be resolved")
    return issues


def _generation_confirmation(p):
    from . import workspace_characters
    return _hash({"script": p.get("script"), "models": p.get("model_snapshot"),
                  "cast_registry": workspace_characters.registry(p),
                  "style": p.get("style_id"), "aspect": p["settings"]["visuals"].get("aspect"),
                  "scenes": [{k: s.get(k) for k in (
                      "id", "text", "prompt", "prompt_author", "location_id", "characters", "character_variants",
                      "references", "start", "end", "motion", "image", "workspace_regeneration_required")} for s in p.get("scenes", [])]})


def _duration_info(p):
    words = len((p.get("script") or "").split())
    voice = p.get("voiceover") or {}
    duration = voice.get("duration")
    if (not p.get("voiceover_stale") and type(duration) in (int, float)
            and math.isfinite(duration) and duration > 0
            and _file_digest(store.project_dir(p["id"]), voice.get("file"))):
        return {"kind": "actual", "seconds": duration, "word_count": words}
    if words:
        return {"kind": "estimated", "seconds": words * 60 / 145, "word_count": words,
                "words_per_minute": 145}
    target = p.get("target_duration_seconds")
    if type(target) in (int, float) and math.isfinite(target) and target > 0:
        return {"kind": "target", "seconds": target, "word_count": 0}
    return {"kind": "unknown", "seconds": None, "word_count": 0}


def _full(p):
    from . import workspace_locations
    out = copy.deepcopy(p)
    if any(s.get('location_view') for s in p.get('scenes') or []):
        out['workspace_camera_audit'] = workspace_locations.audit(p['scenes'])
    out['location_registry_hash'] = _hash(p.get('workspace_location_registry') or {})
    out['owner_id'] = owner_of(p)
    out.pop("script_history", None)
    out.pop("video_context", None)
    scenes = out.get("scenes", [])
    evidence = [_scene_evidence(p, s) for s in scenes]
    for s, item in zip(scenes, evidence):
        s["image_available"] = bool(_file_digest(store.project_dir(p["id"]), s.get("image")))
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
    checks = [s["human_review"]["state"] for s in scenes] + [scopes[k]["state"] for k in ("voiceover", "render")]
    scenes_verified = bool(scenes) and all(s["human_review"]["state"] == "verified" for s in scenes)
    out["technical_issues"] = _technical_issues(p, evidence)
    out["technical_ready"] = not out["technical_issues"]
    ready = scenes_verified and out["technical_ready"] and scopes["voiceover"]["state"] == "verified"
    out["publication_ready"] = bool(ready and scopes["render"]["state"] == "verified")
    from . import workspace_generation, workspace_planning, workspace_writing
    out["can_prepare_images"] = workspace_planning.allowed(p)
    out["can_write_script"] = workspace_writing.allowed(p)
    out["workspace_batch"] = workspace_generation.batch_status(p)
    out["generation_confirmation"] = _generation_confirmation(p)
    out["script_hash"] = _hash(p.get("script") or "")
    out["running"] = pipeline.is_running(p["id"]) or workspace_generation.batch_running(p["id"])
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
    out["duration_info"] = _duration_info(p)
    seconds = out["duration_info"]["seconds"]
    out["duration_minutes"] = seconds / 60 if seconds is not None else None
    out["references"] = copy.deepcopy(p.get("workspace_references", []))
    for ref in out["references"]:
        ref["url"] = f"/media/{p['id']}/{ref['path']}"
    return out


def _summary(p):
    full = _full(p) if p.get("codex_directed") else p | {
        "publication_ready": False, "technical_ready": False, "technical_issues": [],
        "running": pipeline.is_running(p["id"]), "duration_info": _duration_info(p)}
    keys = ("id", "owner_id", "owner_name", "title", "profile_id", "channel_id", "style_id", "style_name", "created", "updated",
            "archived", "steps", "error", "running", "review_state", "publication_ready", "model_snapshot",
            "target_duration_seconds", "duration_minutes", "duration_info", "workspace_queue", "render", "technical_ready", "technical_issues")
    return {k: full.get(k) for k in keys} | {"owner_id": owner_of(p), "thumb": store.thumbnail_path(p), "scenes": len(p.get("scenes", [])),
            "duration": (p.get("voiceover") or {}).get("duration"), "readonly": not p.get("codex_directed", False),
            "legacy_url": f"/legacy.html#/p/{p['id']}/script", "legacy_api_url": f"/api/projects/{p['id']}",
            "codex_directed": p.get("codex_directed", False),
            "review_state": full["review_state"] if p.get("codex_directed") else "legacy_readonly"}


def _ui_project(full):
    """Omit archival payload from screen reads; keep stored evidence untouched."""
    omitted = {"history", "planning_receipt", "generation_receipt", "workspace_generations", "reference_preparation_scenes"}

    def compact(value):
        if isinstance(value, dict):
            return {key: compact(item) for key, item in value.items()
                    if key not in omitted and not key.endswith("_history")}
        if isinstance(value, list):
            return [compact(item) for item in value]
        return value

    return compact(full)


def _batches():
    return [b for b in pipeline.list_batches() if b.get("workspace_directed")]


async def _upload(file, base, role, label):
    data = await file.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(422, "The reference image must be at most 10 MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 20_000_000:
                raise HTTPException(422, "The reference image exceeds 20 million pixels")
            image.load()
            buf = io.BytesIO()
            image.convert("RGB").save(buf, "PNG")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Reference image unreadable") from None
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
                "connection": {"has_proxy": bool(config.get("PROXY_API_KEY") and config.get("PROXY_BASE_URL")),
                               "has_google_flow": google_flow.configured()},
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
        await google_flow.status(force=True)
        return await _catalog()

    @router.put("/settings")
    async def settings(body: dict):
        catalog = await _catalog()
        selected = _models(body, catalog)
        provider = _image_provider(body, catalog)
        style = copy.deepcopy(store.get_style(_default_style_id()))
        if not style:
            raise HTTPException(409, "The shared channel style must be prepared before changing models")
        style["visuals"]["image_model"] = selected["image"]
        style["thumbnail"]["model"] = selected["image"]
        store.save_style(style)
        changes = {"SCRIPT_MODEL": selected["text"], "FAST_MODEL": selected["text"], "IMAGE_PROVIDER": provider}
        if provider == "google_flow":
            changes["USEAPI_IMAGE_MODEL"] = selected["image"]
        config.update(changes)
        return _default_models()

    @router.get('/performance')
    async def performance():
        return {key: config.get_int(key) for key in ('IMAGE_CONCURRENCY', 'LLM_CONCURRENCY',
                'WORKSPACE_PLAN_CONCURRENCY', 'TTS_CONCURRENCY', 'PROJECT_PARALLEL', 'RENDER_CONCURRENCY')} | {
                'flow_concurrency': min(3, max(1, config.get_int('USEAPI_IMAGE_CONCURRENCY'))),
                'render_workers': config.get_int('RENDER_WORKERS')}

    @router.put('/performance')
    async def update_performance(body: dict):
        limits = {'IMAGE_CONCURRENCY':36, 'LLM_CONCURRENCY':24, 'WORKSPACE_PLAN_CONCURRENCY':8,
                  'TTS_CONCURRENCY':6, 'PROJECT_PARALLEL':12, 'RENDER_CONCURRENCY':2}
        if not body or set(body) - set(limits):
            raise HTTPException(422, 'Choose the available concurrency settings.')
        if any(type(value) is not int or not 1 <= value <= limits[key] for key, value in body.items()):
            raise HTTPException(422, 'Concurrency must be a whole number within the displayed limits.')
        from . import workspace_generation
        if any(llm.STATS[k]['active'] for k in ('llm','image')) or workspace_generation._batch_tasks or any(
                pipeline.is_running(p['id']) for p in store.list_projects()):
            raise HTTPException(409, 'Wait for active jobs to finish before changing concurrency.')
        config.update({key:str(value) for key,value in body.items()})
        llm.reset_limits()
        return await performance()

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
                raise HTTPException(422, "Specify the existing references in the desired order")
            paths = [r.get("path") for r in supplied]
            if any(not isinstance(path, str) or path not in existing for path in paths) or len(paths) != len(set(paths)):
                raise HTTPException(422, "A reference must already exist and can appear only once; add the new files first")
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
    async def projects(archived: bool = False, scope: str = "mine"):
        if scope not in ('mine', 'team'):
            raise HTTPException(422, 'Choose mine or team for the video workspace.')
        return [_summary(p) for p in personal_projects(store.list_projects(archived), scope)]

    @router.post("/projects", status_code=201)
    async def create_project(body: dict):
        catalog = await _catalog()
        return _full(_create(_prepare(body, catalog), catalog))

    @router.get("/projects/{pid}")
    async def project(pid: str, view: str = "full"):
        if view not in ("full", "ui"):
            raise HTTPException(422, "Choose full or ui project data")
        full = _full(_project(pid))
        return _ui_project(full) if view == "ui" else full

    @router.put("/projects/{pid}/title")
    async def title(pid: str, body: dict):
        p = _project(pid, True)
        text = _text(body.get("title", ""), "title", required=True).strip()
        if len(text) > 240:
            raise HTTPException(422, "The title cannot exceed 240 characters")
        p.update(title=text, title_auto=False)
        return _full(store.save_project(p))

    @router.get("/projects/{pid}/scenes/{sid}/references/{index}")
    async def scene_reference(pid: str, sid: int, index: int):
        p = _project(pid)
        scene = next((s for s in p.get("scenes", []) if s["id"] == sid), None)
        if not scene:
            raise HTTPException(404, "Plan not found")
        return FileResponse(_reference_path(p, scene, index), headers={"Cache-Control": "no-store"})

    @router.put("/projects/{pid}/script")
    async def script(pid: str, body: dict):
        p = _project(pid, True)
        text = _text(body.get("text"), "text")
        if len(text.encode("utf-8")) > MAX_SCRIPT or "\x00" in text:
            raise HTTPException(422, "The script must be UTF-8 text under 1 MB, with no null character")
        if text != p.get("script"):
            p.update(script=text, custom_script=bool(text.strip()), voiceover_stale=bool(p.get("voiceover")),
                     render=None, prompts_approved=False)
            store.add_history(p, "codex_manual", text)
            for key in ("voiceover", "visuals", "render"):
                p["steps"][key].update(state="idle", msg="Text modified: the voice and images still need checking")
        p["steps"]["script"].update(state="done" if text.strip() else "idle")
        return _full(store.save_project(p))

    @router.put("/projects/{pid}/scenes")
    async def scenes(pid: str, body: dict):
        p = _project(pid, True)
        rows = body.get("scenes")
        if not isinstance(rows, list) or len(rows) > 2000:
            raise HTTPException(422, "The breakdown must be an ordered list of no more than 2,000 shots")
        output, seen = [], set()
        old = {s["id"]: s for s in p.get("scenes", [])}
        for row in rows:
            if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0 or row["id"] in seen:
                raise HTTPException(422, "Each shot must have a positive and unique number")
            seen.add(row["id"])
            for field in ("text", "prompt", "location_id"):
                _text(row.get(field), field, required=True)
            if row["text"] not in p.get("script", ""):
                raise HTTPException(422, "The shot narration must include an exact excerpt from the written text")
            if not isinstance(row.get("characters"), list) or any(not isinstance(c, str) for c in row["characters"]):
                raise HTTPException(422, "Enter the list of named characters in the shot")
            refs = row.get("references")
            if not isinstance(refs, list):
                raise HTTPException(422, "Enter the shot references in their exact order")
            for ref in refs:
                if not isinstance(ref, dict) or ref.get("owner", "project") not in ("project", "style", "studio"):
                    raise HTTPException(422, "Each reference must specify its file and folder: project, style, or studio")
                if ref.get("owner") == "studio":
                    root = config.get("STUDIO_ROOT")
                    if not root or not ref.get("sha256"):
                        raise HTTPException(422, "A studio reference requires the configured folder and the original file fingerprint")
                    base = Path(root).resolve()
                else:
                    base = store.style_dir(p["style_id"]) if ref.get("owner") == "style" else store.project_dir(pid)
                digest = _file_digest(base, ref.get("path"))
                if not digest or ref.get("sha256") and digest != ref["sha256"]:
                    raise HTTPException(422, "The reference file is missing, modified, or outside the expected folder")
            timed = "start" in row or "end" in row
            if timed:
                start, end = row.get("start"), row.get("end")
                if (any(type(x) not in (float, int) or not math.isfinite(x) for x in (start, end))
                        or start < 0 or end <= start):
                    raise HTTPException(422, "The shot start and end must be valid durations, aligned with the actual voice")
            image = row.get("image")
            if image and not _file_digest(store.project_dir(pid), image):
                raise HTTPException(422, "The shot image is missing or outside the project folder")
            from . import workspace_locations
            allowed = ("id", "text", "prompt", "location_id", "characters", "character_variants", "references", "start", "end", "image", "motion") + workspace_locations.SCENE_KEYS
            scene = {k: copy.deepcopy(row[k]) for k in allowed if k in row}
            # Presentation URLs are not authoring input and cannot affect review hashes.
            scene["references"] = [{k: v for k, v in ref.items() if k != "url"} for ref in scene["references"]]
            if old.get(row["id"], {}).get("codex_receipt"):
                scene["codex_receipt"] = copy.deepcopy(old[row["id"]]["codex_receipt"])
            previous = old.get(row["id"], {})
            if "character_variants" not in row and previous.get("character_variants") is not None:
                scene["character_variants"] = copy.deepcopy(previous["character_variants"])
            if previous.get("workspace_regeneration_required"):
                scene["workspace_regeneration_required"] = True
            if previous.get("generation_history"):
                scene["generation_history"] = copy.deepcopy(previous["generation_history"])
            if image and image == previous.get("image"):
                for key in ("generation_receipt", "sent_references"):
                    if previous.get(key):
                        scene[key] = copy.deepcopy(previous[key])
            scene.update(status="done" if image else "idle", prompt_author="codex",
                         human_review=old.get(row["id"], {}).get("human_review"))
            if previous.get("prompt_author") == "configured_text_proxy" and scene.get("prompt") == previous.get("prompt"):
                scene["prompt_author"] = "configured_text_proxy"
            workspace_locations.validate(p, scene)
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
            raise HTTPException(422, "Choose a status: verified, needs correction, or to be checked")
        scope = body.get("scope", "scene")
        if scope == "scene":
            s = next((s for s in p.get("scenes", []) if s["id"] == body.get("scene_id")), None)
            if not s:
                raise HTTPException(404, "Plan not found")
            evidence = _scene_evidence(p, s)
        elif scope in ("script", "voiceover", "render"):
            evidence = _scope_evidence(p, scope)
        else:
            raise HTTPException(422, "Unknown item to check")
        if state == "verified" and not evidence:
            raise HTTPException(409, "Validation impossible: the text, a file, or a reference is missing or has been modified")
        source = body.get("source", "explicit_human_review")
        if source not in ("explicit_human_review", "delegated_ai_inspection"):
            raise HTTPException(422, "Specify explicit_human_review or delegated_ai_inspection")
        record = {"state": state, "notes": _text(body.get("notes", ""), "notes"),
                  "reviewer": _text(body.get("reviewer", "local_human"), "reviewer", required=True),
                  "source": source, "reviewed_at": now(), "evidence": evidence}
        if scope == "scene":
            s["human_review"] = record
        else:
            p.setdefault("human_reviews", {})[scope] = record
        return _full(store.save_project(p))

    @router.put('/projects/{pid}/locations')
    async def location_registry(pid: str, body: dict):
        from . import workspace_locations
        p = _project(pid, True)
        if body.get('previous_hash') != _hash(p.get('workspace_location_registry') or {}):
            raise HTTPException(409, 'The location registry changed; refresh before saving')
        proposed = copy.deepcopy(p)
        proposed['workspace_location_registry'] = body.get('locations')
        if not isinstance(body.get('locations'), dict):
            raise HTTPException(422, 'Enter the complete authored location registry')
        workspace_locations.check_registry(proposed)
        # Preserve selected source media and old receipts. Changed geometry invalidates review evidence.
        if p.get('render'):
            p.setdefault('render_history', []).append(copy.deepcopy(p['render']))
        p.update(workspace_location_registry=copy.deepcopy(body['locations']), render=None)
        return _full(store.save_project(p))

    @router.post("/projects/{pid}/references")
    async def project_reference(pid: str, file: UploadFile = File(...), role: str = Form("location"), label: str = Form("")):
        _project(pid, True)
        if role not in ("location", "character", "pose", "style"):
            raise HTTPException(422, "Unknown reference type")
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
            raise HTTPException(422, "The batch must contain between 1 and 100 videos")
        name = _text(body.get("name", "Batch dirige"), "name", required=True)
        catalog = await _catalog()
        defaults = {key: body[key] for key in ("text_model", "image_model", "image_provider") if key in body}
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
