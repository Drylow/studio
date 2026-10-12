"""Import the explicitly inspected green-zombie revision without image generation."""
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

PID = "zombie-outbreak-30-days-trapped-in-a-sup-e56f42"
RULE = ("Living humans including Patch keep PURE WHITE heads, mitten hands and oval feet. "
        "Infected zombies alone have flat pale desaturated GREEN heads, both mitten hands "
        "and both oval feet, target #A8BE87, matching their verified green references. "
        "Their bodies/limbs remain black stick lines and their own outfits remain unchanged. "
        "No hero bandage/bag on zombies; no green recoloring of living humans.")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update():
    base = ROOT / "output/imagegen/patch-green-zombies-2026-10-12"
    reg = json.loads((base / "registre.json").read_text(encoding="utf-8"))
    for asset in reg["assets"]:
        assert digest(ROOT / asset["file"]) == asset["sha256"]
        assert digest(ROOT / asset["prompt"]) == asset["prompt_sha256"]
        for ref in asset["ordered_references"]:
            assert digest(ROOT / ref["path"]) == ref["sha256"]
    p = store.get_project(PID)
    assert p
    if p.get("workspace_green_zombie_revision") == "head-hands-feet-v1":
        print("Green-zombie revision already imported; current project edits preserved.")
        return
    live = requests.get("http://127.0.0.1:8766/api/workspace/projects/" + PID, timeout=20)
    live.raise_for_status()
    state = live.json()
    assert not state["running"] and not any(s.get("status") in ("queued", "running") for s in state["scenes"])
    assert len(p["scenes"]) == 3
    assert not p.get("voiceover") and not p.get("render")
    directory = store.project_dir(PID)
    destination = directory / "green-zombies-v1"
    assert not destination.exists(), "Inspect incomplete import before retrying"
    shutil.copytree(base, destination)
    p.setdefault("workspace_visual_revision_history", []).append({
        "created": now(), "reason": "User requested green zombie heads, hands and feet",
        "scenes": copy.deepcopy(p["scenes"]), "cast": copy.deepcopy(p.get("workspace_cast_registry")),
        "style_snapshot": copy.deepcopy(p.get("style_snapshot"))})
    entries = p.setdefault("workspace_cast_registry", {})
    for name, stem, outfit in (("Cart Infected", "cart-green-full", "olive-gray ragged vest"),
                               ("Delivery Infected", "delivery-green-full", "dusty navy-blue vest with two pockets")):
        description = ("Adult with round pale desaturated GREEN head, small black oval eyes and tiny mouth, "
                       "GREEN mitten hands and GREEN oval feet. Black thin stick body/limbs. " + outfit + ". "
                       "No Patch bandage/bag, hair, eyebrows, ears, nose, realistic anatomy or gore.")
        relative = "green-zombies-v1/characters/" + stem + ".png"
        ref = {"owner": "project", "path": relative, "sha256": digest(directory / relative),
               "role": "identity", "character": name, "variant": "default", "review_state": "verified"}
        entries[name] = {"required": True, "variants": {"default": {"description": description, "references": [ref]}}}
        style = store.get_style("survivor-patch")
        style_file = "refs/" + stem + ".png"
        style_target = store.style_dir(style["id"]) / style_file
        if not style_target.exists():
            shutil.copy2(directory / relative, style_target)
        assert digest(style_target) == ref["sha256"]
        style.setdefault("workspace_cast_registry", {})[name] = {"required": True, "variants": {"default": {
            "description": description, "references": [{**ref, "owner": "style", "path": style_file}]}}}
        if RULE not in style["visuals"]["art_style"]:
            style["visuals"]["art_style"] += "\n" + RULE
        if RULE not in style["thumbnail"]["style"]:
            style["thumbnail"]["style"] += "\n" + RULE
        style["workspace_zombie_colour"] = {"target": "#A8BE87", "parts": ["head", "hands", "feet"]}
        store.save_style(style)
    patch_refs = entries["Patch"]["variants"]["default"]["references"]
    for scene in p["scenes"]:
        sid = scene["id"]
        asset = next(a for a in reg["assets"] if a["id"] == f"plan-{sid:02d}-green-full")
        infected = "Delivery Infected" if sid == 3 else "Cart Infected"
        references = []
        for index, original in enumerate(asset["ordered_references"]):
            if index == 2:
                ref = copy.deepcopy(entries[infected]["variants"]["default"]["references"][0])
            elif index in (3, 4):
                ref = copy.deepcopy(patch_refs[index - 3])
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
        scene.setdefault("generation_history", []).append({"image": scene.get("image"),
            "references": copy.deepcopy(scene.get("references")), "prompt": scene.get("prompt"), "changed_at": now()})
        original_prompt = (ROOT / asset["prompt"]).read_text(encoding="utf-8")
        scene.update(image=f"green-zombies-v1/A-REGARDER/{sid:02d}.png", status="done", references=references,
                     characters=[infected, "Patch"], character_variants={infected: "default", "Patch": "default"},
                     original_cli_prompt=original_prompt, workspace_external_generation=asset,
                     human_review=None, prompt_author="codex")
        scene["prompt"] = original_prompt + "\n\n" + cast.binding(p, scene)
        scene["codex_visual_review"] = {"state": "inspected", "notes": asset["visual_review"], "user_approved": False}
        cast.validate(p, scene)
        assert digest(directory / scene["image"]) == asset["delivery_sha256"]
    p["style_snapshot"]["prompt"] += "\n" + RULE
    if RULE not in p["settings"]["visuals"].get("art_style", ""):
        p["settings"]["visuals"]["art_style"] = p["settings"]["visuals"].get("art_style", "") + "\n" + RULE
    p["workspace_green_zombie_revision"] = "head-hands-feet-v1"
    p["prompts_approved"] = False
    store.save_project(p)
    print("Imported green zombie identities and all 3 image previews; Patch and existing script preserved.")


if __name__ == "__main__":
    update()
