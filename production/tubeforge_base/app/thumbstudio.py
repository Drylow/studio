"""Studio miniatures : créer des miniatures sans projet vidéo (comme le Thumbnail Studio de TubeGen)."""
import asyncio
import shutil
import uuid

from . import config, events, llm, store
from .steps.thumbnails import thumb_prompt, write_concepts
from .util import now, read_json, write_json

DIR = config.DATA / "thumbstudio"
INDEX = DIR / "index.json"
_sets: list[dict] | None = None


def _load() -> list[dict]:
    global _sets
    if _sets is None:
        _sets = read_json(INDEX, []) or []
        for s in _sets:  # tâches interrompues par un redémarrage
            for it in s["items"]:
                if it.get("status") in ("running", "queued"):
                    it.update(status="error", error="Interrompu")
    return _sets


def _save() -> None:
    write_json(INDEX, _load())


def list_sets() -> list[dict]:
    return _load()


def get_set(sid: str) -> dict | None:
    return next((s for s in _load() if s["id"] == sid), None)


def _style_for(s: dict) -> tuple[str, str]:
    st = store.get_style(s.get("style_id") or "") or store.list_styles()[0]
    style = (s.get("style_text") or "").strip() or st["thumbnail"]["style"]
    return style, s.get("model") or st["thumbnail"].get("model", config.get("IMAGE_MODEL"))


def create(title: str, idea: str, text: str, count: int, style_id: str, aspect: str, style_text: str = "",
           ref: bytes | None = None) -> dict:
    sid = uuid.uuid4().hex[:10]
    d = DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    s = {"id": sid, "created": now(), "title": title.strip(), "idea": idea.strip(), "text": text.strip(),
         "count": max(1, min(8, int(count or 4))), "style_id": style_id, "aspect": aspect or "16:9",
         "style_text": style_text, "ref": None, "items": []}
    if ref:
        (d / "ref.png").write_bytes(ref)
        s["ref"] = f"{sid}/ref.png"
    _load().insert(0, s)
    _save()
    return s


async def _render(s: dict, item: dict, concept: dict, refs: list[bytes] | None) -> None:
    style, model = _style_for(s)
    item["status"] = "running"
    _save()
    try:
        img = await llm.generate_image(thumb_prompt(style, concept, bool(refs)), model, s["aspect"], refs,
                                       label="Thumbnail (studio)")
        n = 1
        while (DIR / s["id"] / f"t{n:02d}.png").exists():
            n += 1
        rel = f"{s['id']}/t{n:02d}.png"
        (DIR / rel).write_bytes(img)
        item.update(file=rel, status="done", error=None)
        events.log(f"✓ Thumbnail studio « {s['title'] or s['idea'][:40]}”: thumbnail ready", "ok")
    except Exception as e:  # noqa: BLE001
        item.update(status="error", error=str(e)[:300])
        events.log(f"✗ Thumbnail studio: {str(e)[:160]}", "error")
    _save()


async def generate(s: dict, count: int | None = None) -> None:
    """Écrit des concepts puis génère les images en parallèle (sur les 36 comptes)."""
    count = count or s["count"]
    events.log(f"Thumbnail studio: {count} variant(s) for “{s['title'] or s['idea'][:50]} »", "step")
    placeholders = [{"id": uuid.uuid4().hex[:8], "status": "queued", "file": None, "prompt": "", "text": ""}
                    for _ in range(count)]
    s["items"] = placeholders + s["items"]
    _save()
    try:
        style, _ = _style_for(s)
        concepts = await write_concepts(s["title"] or s["idea"][:80], s["idea"], style, count,
                                        forced_text=s.get("text", ""))
    except Exception as e:  # noqa: BLE001
        for it in placeholders:
            it.update(status="error", error=f"Concepts : {e}"[:300])
        _save()
        return
    refs = [llm.png_for_upload(DIR / s["ref"])] if s.get("ref") else None
    jobs = []
    for it, c in zip(placeholders, concepts):
        it.update(prompt=c["prompt"], text=c.get("text", ""))
        jobs.append(_render(s, it, c, refs))
    for it in placeholders[len(concepts):]:
        it.update(status="error", error="Pas de concept")
    await asyncio.gather(*jobs)


async def edit(s: dict, item: dict, instruction: str) -> None:
    """Retouche une miniature existante (nouvelle version ajoutée à côté)."""
    _, model = _style_for(s)
    new = {"id": uuid.uuid4().hex[:8], "status": "running", "file": None, "prompt": item.get("prompt", ""),
           "text": item.get("text", ""), "parent": item["id"], "instruction": instruction}
    s["items"].insert(s["items"].index(item), new)
    _save()
    try:
        prompt = (f"Edit this YouTube thumbnail: {instruction}. Keep the same illustration style and overall "
                  "quality; keep text perfectly legible.")
        img = await llm.generate_image(prompt, model, s["aspect"], [llm.png_for_upload(DIR / item["file"])])
        n = 1
        while (DIR / s["id"] / f"t{n:02d}.png").exists():
            n += 1
        rel = f"{s['id']}/t{n:02d}.png"
        (DIR / rel).write_bytes(img)
        new.update(file=rel, status="done")
    except Exception as e:  # noqa: BLE001
        new.update(status="error", error=str(e)[:300])
    _save()


async def variations(s: dict, item: dict, count: int = 2) -> None:
    """Nouvelles variantes proches d'une miniature qui plaît."""
    style, _ = _style_for(s)
    try:
        concepts = await write_concepts(s["title"] or s["idea"][:80],
                                        f"{s['idea']}\n\nMake close variations of this concept the user liked: "
                                        f"{item.get('prompt', '')}", style, count, forced_text=s.get("text", ""))
    except Exception:  # noqa: BLE001
        concepts = [{"prompt": item.get("prompt", ""), "text": item.get("text", "")}] * count
    refs = [llm.png_for_upload(DIR / item["file"])] if item.get("file") else None
    new_items = [{"id": uuid.uuid4().hex[:8], "status": "queued", "file": None, "prompt": c["prompt"],
                  "text": c.get("text", ""), "parent": item["id"]} for c in concepts]
    idx = s["items"].index(item)
    s["items"][idx:idx] = new_items
    _save()
    await asyncio.gather(*(_render(s, it, c, refs) for it, c in zip(new_items, concepts)))


def delete_set(sid: str) -> None:
    global _sets
    _sets = [s for s in _load() if s["id"] != sid]
    shutil.rmtree(DIR / sid, ignore_errors=True)
    _save()


def delete_item(s: dict, item_id: str) -> None:
    item = next((i for i in s["items"] if i["id"] == item_id), None)
    if item:
        s["items"].remove(item)
        if item.get("file"):
            (DIR / item["file"]).unlink(missing_ok=True)
        _save()


def to_project(s: dict, item: dict, pid: str) -> dict:
    p = store.get_project(pid)
    pdir = store.project_dir(pid) / "thumbs"
    pdir.mkdir(parents=True, exist_ok=True)
    n = 1
    while (pdir / f"thumb_{n:02d}.png").exists():
        n += 1
    shutil.copy2(DIR / item["file"], pdir / f"thumb_{n:02d}.png")
    p["thumbnails"] = (p.get("thumbnails") or []) + [{"file": f"thumbs/thumb_{n:02d}.png",
                                                       "prompt": item.get("prompt", ""), "text": item.get("text", "")}]
    p["thumbnail_selected"] = len(p["thumbnails"]) - 1
    return store.save_project(p)
