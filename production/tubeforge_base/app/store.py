"""Persistance des projets et des styles (fichiers JSON dans data/)."""
import copy
import shutil
import uuid
from pathlib import Path

from . import config
from .util import now, read_json, slugify, write_json, word_count

STEP_KEYS = ["script", "voiceover", "visuals", "render", "thumbnail"]

DEFAULT_ART_STYLE = (
    "2D digital cartoon illustration. Characters are simple stylized figures with a large, perfectly round, "
    "plain white ball-shaped head (no hair, no nose, no ears), two small black dot eyes, a tiny simple line "
    "mouth and occasional simple eyebrows to show emotion; white rounded hands. Their bodies have normal "
    "proportions and wear detailed, historically accurate clothing for the era. Detailed hand-drawn painterly "
    "backgrounds, clean bold black outlines, soft cel shading, cinematic warm or moody lighting, rich but "
    "slightly muted color palette, storybook comic look."
)

DEFAULT_THUMB_STYLE = (
    "YouTube thumbnail, first-person POV shot: the viewer's own hands are visible in the foreground holding "
    "or touching the key object of the story. Detailed graphic-novel / comic book illustration with bold ink "
    "outlines and crosshatching, dramatic cinematic lighting, high contrast, muted gritty palette with one warm "
    "light source, strong storytelling props that hint at the drama, sharp focus, 16:9."
)


def default_style(style_id: str = "default", name: str = "Style par dÃ©faut") -> dict:
    return {
        "id": style_id,
        "name": name,
        "language": "English",
        "script": {
            "word_count": 2500,
            "mode": "pro",
            "instructions": "",
            "references": [],
        },
        "voice": {
            "provider": "elevenlabs",
            "voice_id": "nPczCjzI2devNBz1zQrb",
            "voice_name": "Brian",
            "model_id": config.get("TTS_MODEL"),
            "speed": 1.0,
            "delivery": "balanced",
            "cut_silences": "none",
            "edge_voice": "en-US-AndrewMultilingualNeural",
            "local_voice": "",
            "local_engine": "auto",
            "local_exaggeration": 0.5,
            "local_cfg": 0.5,
            "local_temperature": 0.8,
        },
        "visuals": {
            "aspect": "16:9",
            "art_style": DEFAULT_ART_STYLE,
            "style_refs": [],
            "use_style_refs": False,
            "image_model": config.get("IMAGE_MODEL"),
            "avg_scene_seconds": 6.0,
            "min_scene_seconds": 2.0,
            "max_scene_seconds": 12.0,
            "auto_characters": True,
            "use_character_refs": True,
            "continuity": "smart",
            "captions": False,
            "motion_strength": 1.0,
        },
        "thumbnail": {"count": 2, "style": DEFAULT_THUMB_STYLE, "model": config.get("IMAGE_MODEL")},
        "shorts": {"promo_count": 0, "cta_spoken": "", "cta_line1": "", "cta_line2": "", "cta_line3": ""},
        "characters": [],
    }


# ------------------------------------------------------------------ styles

def style_dir(style_id: str) -> Path:
    return config.STYLES_DIR / style_id


def _merge_defaults(d: dict, defaults: dict) -> dict:
    for k, v in defaults.items():
        if k not in d:
            d[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(d[k], dict):
            _merge_defaults(d[k], v)
    return d


def list_styles() -> list[dict]:
    out = []
    for f in sorted(config.STYLES_DIR.glob("*/style.json")):
        s = read_json(f)
        if s:
            out.append(_merge_defaults(s, default_style(s.get("id", f.parent.name))))
    if not out:
        s = default_style()
        save_style(s)
        out.append(s)
    return out


def get_style(style_id: str) -> dict | None:
    s = read_json(style_dir(style_id) / "style.json")
    return _merge_defaults(s, default_style(style_id)) if s else None


def save_style(style: dict) -> dict:
    write_json(style_dir(style["id"]) / "style.json", style)
    return style


def new_style(name: str, base: dict | None = None) -> dict:
    sid = slugify(name, 30)
    while style_dir(sid).exists():
        sid = f"{slugify(name, 24)}-{uuid.uuid4().hex[:4]}"
    s = copy.deepcopy(base) if base else default_style(sid, name)
    s["id"], s["name"] = sid, name
    if base:
        shutil.copytree(style_dir(base["id"]), style_dir(sid), dirs_exist_ok=True)
    return save_style(s)


def delete_style(style_id: str) -> None:
    shutil.rmtree(style_dir(style_id), ignore_errors=True)


# ------------------------------------------------------------------ projets

_cache: dict[str, dict] = {}
_mtimes: dict[str, float] = {}  # date du fichier lors de notre derniÃ¨re lecture/Ã©criture


def project_dir(pid: str) -> Path:
    return config.PROJECTS_DIR / pid


def _mtime(f: Path) -> float:
    try:
        return f.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def _load_all() -> None:
    """Recharge les projets modifiÃ©s par un autre processus (ex. batch en ligne de commande)."""
    seen = set()
    for f in config.PROJECTS_DIR.glob("*/project.json"):
        pid = f.parent.name
        seen.add(pid)
        mt = _mtime(f)
        if pid in _cache and _mtimes.get(pid) == mt:
            continue
        p = read_json(f)
        if p and p.get("id"):
            _cache[p["id"]] = p
            _mtimes[p["id"]] = mt
    for pid in list(_cache):
        if pid not in seen and not project_dir(pid).exists():
            _cache.pop(pid, None)


def list_projects(archived: bool | None = None) -> list[dict]:
    _load_all()
    ps = [p for p in _cache.values() if archived is None or bool(p.get("archived")) == archived]
    return sorted(ps, key=lambda p: p.get("created", 0), reverse=True)


def get_project(pid: str) -> dict | None:
    f = project_dir(pid) / "project.json"
    if pid not in _cache or _mtimes.get(pid) != _mtime(f):
        p = read_json(f)
        if p and p.get("id"):
            _cache[pid] = p
            _mtimes[pid] = _mtime(f)
    return _cache.get(pid)


def save_project(p: dict) -> dict:
    p["updated"] = now()
    _cache[p["id"]] = p
    f = project_dir(p["id"]) / "project.json"
    write_json(f, p)
    _mtimes[p["id"]] = _mtime(f)
    return p


_last_save: dict[str, float] = {}


def save_throttled(p: dict, force: bool = False) -> None:
    """Sauvegarde au plus toutes les 1,5 s (progression, texte en directâ€¦)."""
    t = now()
    if force or t - _last_save.get(p["id"], 0) > 1.5:
        _last_save[p["id"]] = t
        save_project(p)


def new_steps() -> dict:
    return {k: {"state": "idle", "msg": "", "done": 0, "total": 0} for k in STEP_KEYS}


def create_project(title: str, style_id: str, *, topic: str = "", video_url: str = "", mode: str = "auto",
                   custom_script: str = "", overrides: dict | None = None,
                   characters: list[str] | None = None) -> dict:
    """characters = ids des personnages permanents du style Ã  inclure (None = ceux Â« inclus par dÃ©faut Â»)."""
    _load_all()
    style = get_style(style_id) or list_styles()[0]
    pid = f"{slugify(title or topic or 'video', 40)}-{uuid.uuid4().hex[:6]}"
    settings = {k: copy.deepcopy(style[k]) for k in ("script", "voice", "visuals", "thumbnail", "shorts")}
    settings["language"] = style.get("language", "English")
    for path, value in (overrides or {}).items():  # ex. {"script.word_count": 1500}
        if value in (None, ""):
            continue
        node = settings
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
    pdir = project_dir(pid)
    pdir.mkdir(parents=True, exist_ok=True)
    wanted = characters
    chosen = []
    for c in style.get("characters", []):
        if (c["id"] in wanted) if wanted is not None else c.get("auto_include", False):
            chosen.append(c)
    characters = []
    for c in chosen:
        c = copy.deepcopy(c)
        if c.get("image"):
            src = style_dir(style["id"]) / c["image"]
            if src.exists():
                dst = pdir / "characters" / src.name
                dst.parent.mkdir(exist_ok=True)
                shutil.copy2(src, dst)
                c["image"] = f"characters/{src.name}"
            else:
                c["image"] = None
        c["source"] = "style"
        c["enabled"] = True
        characters.append(c)
    p = {
        "id": pid,
        "owner_id": __import__(__package__ + ".workspace_identity", fromlist=["current_owner"]).current_owner(),
        "title": title.strip(),
        "title_auto": not title.strip(),
        "topic": topic.strip(),
        "video_url": video_url.strip(),
        "video_context": "",
        "style_id": style["id"],
        "style_name": style["name"],
        "created": now(),
        "updated": now(),
        "archived": False,
        "mode": mode if mode in ("auto", "review") else "auto",
        "settings": settings,
        "characters": characters,
        "bible": None,
        "custom_script": bool(custom_script.strip()),
        "script": custom_script.strip(),
        "script_history": [],
        "voiceover": None,
        "scenes": [],
        "render": None,
        "thumbnails": [],
        "thumbnail_selected": 0,
        "steps": new_steps(),
        "error": None,
    }
    if p["custom_script"]:
        p["steps"]["script"]["state"] = "done"
        add_history(p, "upload", p["script"])
    return save_project(p)


def add_style_character(p: dict, style_char_id: str) -> dict:
    """Ajoute au projet un personnage permanent du style (bibliothÃ¨que), avec sa fiche."""
    style = get_style(p["style_id"]) or {}
    c = next((x for x in style.get("characters", []) if x["id"] == style_char_id), None)
    if not c:
        raise KeyError("Character not found in style")
    if any(x["id"] == c["id"] for x in p["characters"]):
        return p
    c = copy.deepcopy(c)
    if c.get("image"):
        src = style_dir(style["id"]) / c["image"]
        if src.exists():
            dst = project_dir(p["id"]) / "characters" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            c["image"] = f"characters/{src.name}"
        else:
            c["image"] = None
    c.update(source="style", enabled=True)
    p["characters"].append(c)
    return save_project(p)


def add_history(p: dict, kind: str, text: str) -> None:
    prev = p["script_history"][-1]["words"] if p["script_history"] else 0
    words = word_count(text)
    p["script_history"].append({"ts": now(), "kind": kind, "words": words, "delta": words - prev, "text": text})
    p["script_history"] = p["script_history"][-40:]


def delete_project(pid: str) -> None:
    _cache.pop(pid, None)
    shutil.rmtree(project_dir(pid), ignore_errors=True)


def duplicate_project(pid: str) -> dict:
    src = get_project(pid)
    new_id = f"{pid.rsplit('-', 1)[0]}-{uuid.uuid4().hex[:6]}"
    shutil.copytree(project_dir(pid), project_dir(new_id), ignore=shutil.ignore_patterns("render", "*.tmp"))
    p = copy.deepcopy(src)
    p.update(id=new_id, title=(src["title"] or "Untitled") + " (copie)", created=now(), archived=False,
             render=None, error=None)
    from .workspace_identity import current_owner
    p['owner_id'] = current_owner()
    for k, st in p["steps"].items():
        if st["state"] == "running":
            st.update(state="idle", msg="")
    p["steps"]["render"] = {"state": "idle", "msg": "", "done": 0, "total": 0}
    return save_project(p)


def features(p: dict) -> dict:
    scenes = p.get("scenes") or []
    return {
        "title": bool(p.get("title")),
        "script": bool(p.get("script")),
        "voice": bool(p.get("voiceover")),
        "visuals": bool(scenes) and all(s.get("image") for s in scenes),
        "render": bool(p.get("render")),
        "thumbnail": bool(p.get("thumbnails")),
    }


def thumbnail_path(p: dict) -> str | None:
    thumbs = p.get("thumbnails") or []
    if thumbs:
        i = min(p.get("thumbnail_selected", 0), len(thumbs) - 1)
        selected = thumbs[i]
        if isinstance(selected, str) and selected:
            return selected
        if isinstance(selected, dict) and (selected.get("file") or selected.get("path")):
            return selected.get("file") or selected.get("path")
    for s in p.get("scenes") or []:
        if s.get("image"):
            return s["image"]
    return None


def words_path(pid: str) -> Path:
    return project_dir(pid) / "words.json"


def load_words(pid: str) -> list[dict]:
    return read_json(words_path(pid), []) or []


def save_words(pid: str, words: list[dict]) -> None:
    write_json(words_path(pid), words)


def reset_stale_running() -> None:
    """Au dÃ©marrage : les Ã©tapes marquÃ©es 'running' d'une session prÃ©cÃ©dente sont interrompues."""
    for p in list_projects():
        if now() - (p.get("updated") or 0) < 120:  # probablement en cours dans un autre processus (batch CLI)
            continue
        changed = False
        for st in p["steps"].values():
            if st["state"] == "running":
                st.update(state="error", msg="Interrompu (serveur redÃ©marrÃ©) â€” clique sur â–¶ Reprendre : "
                                             "Ã§a repart lÃ  oÃ¹ Ã§a s'Ã©tait arrÃªtÃ©")
                changed = True
        for s in p.get("scenes") or []:
            if s.get("status") in ("running", "queued"):
                s["status"] = "idle"
                changed = True
        if changed:
            save_project(p)
