"""Import the manually inspected school-backpack revision; no generation calls."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/TubeForge"))
from app import store, workspace_characters as cast
from app.util import now
from tubeforge_survivor_styles import STYLES

PID = "zombie-outbreak-30-days-trapped-in-a-sup-e56f42"
RULE = ("Patch wears a normal orange school backpack; Reed wears a normal gray school backpack. "
        "Each has two shoulder straps, a main zipper and a front zipped pocket; no handbag, "
        "briefcase or flap/clasp bag. Keep thin black stick torsos and limbs, white heads, "
        "mitten hands and oval feet. Bag off/on states follow the narrated action; no duplicates.")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite(text):
    return (text.replace("small orange flap bag, black clasp, orange handle",
                         "normal orange school backpack, two shoulder straps, main zipper and front zipped pocket")
            .replace("small gray flap bag with black clasp and handle",
                     "normal gray school backpack, two shoulder straps, main zipper and front zipped pocket")
            .replace("small gray flap bag with short gray handle and one black clasp",
                     "normal gray school backpack, two shoulder straps, main zipper and front zipped pocket"))


def persisted_scenes(scenes):
    """Drop only read-only API presentation fields from the pre-edit snapshot."""
    scenes = copy.deepcopy(scenes)
    for scene in scenes:
        scene.pop("image_url", None)
        scene.pop("image_available", None)
        if scene.get("human_review") == {"state": "unreviewed", "notes": ""}:
            scene["human_review"] = None
        for ref in scene.get("references", []):
            ref.pop("url", None)
    return scenes


def update():
    base = ROOT / "output/imagegen/survivor-backpacks-2026-10-12"
    record = json.loads((base / "registre.json").read_text(encoding="utf-8"))
    for asset in record["assets"]:
        assert digest(ROOT / asset["file"]) == asset["sha256"]
        assert digest(ROOT / asset["prompt"]) == asset["prompt_sha256"]
        for ref in asset["ordered_references"]:
            assert digest(ROOT / ref["path"]) == ref["sha256"]
    p = store.get_project(PID)
    assert p
    if p.get("workspace_backpack_revision") == "school-v1":
        print("Backpack revision already imported; subsequent edits preserved.")
        return
    live = requests.get("http://127.0.0.1:8766/api/workspace/projects/" + PID, timeout=20)
    live.raise_for_status()
    state = live.json()
    assert not state["running"] and not any(s.get("status") in ("queued", "running") for s in state["scenes"])
    before = json.loads((ROOT / "work/survivor-backpacks-2026-10-12/project-before.json").read_text(encoding="utf-8"))
    assert p["script"] == before["script"], "User script changed; review before import"
    assert persisted_scenes(p["scenes"]) == persisted_scenes(before["scenes"]), "User scenes changed; review before import"
    assert len(p["scenes"]) == 3 and not p.get("voiceover") and not p.get("render")
    directory = store.project_dir(PID)
    destination = directory / "school-backpacks-v1"
    assert not destination.exists(), "Inspect incomplete import before retrying"
    shutil.copytree(base, destination)
    p.setdefault("workspace_visual_revision_history", []).append({
        "created": now(), "reason": "User requested ordinary school backpacks",
        "scenes": copy.deepcopy(p["scenes"]), "cast": copy.deepcopy(p.get("workspace_cast_registry")),
        "style_snapshot": copy.deepcopy(p.get("style_snapshot")),
        "style_cast_snapshot": copy.deepcopy(p.get("style_cast_snapshot")),
        "script": p["script"], "workspace_references": copy.deepcopy(p.get("workspace_references"))})
    updated_styles = {}
    for sid, title, name, description, sources in STYLES:
        style = store.get_style(sid)
        assert style and style.get("workspace_survivor_seeded")
        style.setdefault("workspace_identity_history", []).append({
            "created": now(), "character": name,
            "entry": copy.deepcopy(style["workspace_cast_registry"][name]),
            "visuals": copy.deepcopy(style["visuals"]), "thumbnail": copy.deepcopy(style["thumbnail"]),
            "workspace_references": copy.deepcopy(style.get("workspace_references"))})
        body = "refs/" + name.lower() + "-school-backpack-v1.png"
        target = store.style_dir(sid) / body
        assert not target.exists()
        shutil.copy2(ROOT / sources[0], target)
        variant = style["workspace_cast_registry"][name]["variants"]["default"]
        old = variant["references"][0]
        variant["references"][0] = {**old, "path": body, "sha256": digest(target)}
        variant["description"] = description
        guide = dict(variant["references"][0], role="style-only")
        for field in ("workspace_references",):
            style[field] = [guide if r.get("path") == old["path"] else r for r in style.get(field, [])]
        style["visuals"]["style_refs"] = [body if v == old["path"] else v for v in style["visuals"].get("style_refs", [])]
        style["visuals"]["reference_sources"] = [guide if r.get("path") == old["path"] else r for r in style["visuals"].get("reference_sources", [])]
        style["visuals"]["preview"] = body
        style["visuals"]["art_style"] = rewrite(style["visuals"]["art_style"]) + "\n" + RULE
        style["thumbnail"]["style"] = rewrite(style["thumbnail"]["style"]) + "\n" + RULE
        style["workspace_backpack_revision"] = "school-v1"
        store.save_style(style)
        updated_styles[sid] = style
    patch = p["workspace_cast_registry"]["Patch"]["variants"]["default"]
    old_body = patch["references"][0]
    body = "school-backpacks-v1/characters/patch-v2.png"
    patch["references"][0] = {**old_body, "path": body, "sha256": digest(directory / body)}
    patch["description"] = STYLES[0][3]
    p["style_cast_snapshot"]["Patch"] = copy.deepcopy(updated_styles["survivor-patch"]["workspace_cast_registry"]["Patch"])
    for scene in p["scenes"]:
        sid = scene["id"]
        asset = next(a for a in record["assets"] if a["id"] == f"plan-{sid:02d}")
        infected = "Delivery Infected" if sid == 3 else "Cart Infected"
        references = []
        for index, original in enumerate(asset["ordered_references"]):
            if index in (2, 3):
                ref = copy.deepcopy(patch["references"][index - 2])
            else:
                src = ROOT / original["path"]
                dst = destination / "input-copies" / src.name
                dst.parent.mkdir(exist_ok=True)
                if not dst.exists():
                    shutil.copy2(src, dst)
                ref = {"owner": "project", "path": dst.relative_to(directory).as_posix(),
                       "sha256": digest(dst), "role": "location" if index == 1 else "continuity"}
            assert ref["sha256"] == original["sha256"]
            references.append(ref)
        # Explicitly authored FUTURE binding, separate from the actual four-image edit receipt.
        references.append(copy.deepcopy(p["workspace_cast_registry"][infected]["variants"]["default"]["references"][0]))
        scene.setdefault("generation_history", []).append({"image": scene.get("image"),
            "references": copy.deepcopy(scene.get("references")), "prompt": scene.get("prompt"), "changed_at": now()})
        original = (ROOT / asset["prompt"]).read_text(encoding="utf-8")
        scene.update(image=f"school-backpacks-v1/A-REGARDER/{sid:02d}.png", status="done",
                     references=references, characters=["Patch", infected],
                     character_variants={"Patch": "default", infected: "default"},
                     original_cli_prompt=original, workspace_external_generation=asset,
                     human_review=None, prompt_author="codex")
        scene["prompt"] = (original + "\nImage 5 supplies the same green infected identity already visible "
                           "in image 1; never a third person. Preserve its outfit and green exposed parts.\n\n"
                           + cast.binding(p, scene))
        scene["workspace_future_reference_note"] = record["future_regeneration_note"]
        scene["codex_visual_review"] = {"state": "inspected", "notes": asset["visual_review"], "user_approved": False}
        cast.validate(p, scene)
        assert digest(directory / scene["image"]) == asset["delivery_sha256"]
    p["style_snapshot"]["prompt"] = rewrite(p["style_snapshot"]["prompt"]) + "\n" + RULE
    p["settings"]["visuals"]["art_style"] = rewrite(p["settings"]["visuals"].get("art_style", "")) + "\n" + RULE
    for ref in p.get("workspace_references", []):
        if ref.get("sha256") == old_body["sha256"]:
            ref.update(path=body, owner="project", sha256=patch["references"][0]["sha256"])
    script = (ROOT / "chaines/survivor-projet/episode-01-supermarket/script-en.txt").read_text(encoding="utf-8")
    p.setdefault("script_history", []).append({"text": script, "ts": now(), "kind": "edit",
        "words": len(script.split()), "delta": len(script.split()) - len(p["script"].split()),
        "reason": "School backpack vocabulary; previous text preserved in revision history"})
    p.update(script=script, custom_script=True, workspace_backpack_revision="school-v1", prompts_approved=False)
    store.save_project(p)
    print("Imported both backpack identities, updated 3 previews and backpack script vocabulary; no media jobs launched.")


if __name__ == "__main__":
    update()
