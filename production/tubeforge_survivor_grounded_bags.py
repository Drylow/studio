"""Import the manually inspected floor-standing school-backpack revision; no generation calls."""
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
from tubeforge_survivor_backpacks import RULE as OLD_RULE

PID = "zombie-outbreak-30-days-trapped-in-a-sup-e56f42"
RULE = ("Backpacks are SEPARATE props, never worn on the stick bodies. Patch's orange school backpack "
        "and Reed's gray school backpack stand upright on the floor beside their owner, bases in visible "
        "floor contact with a small contact shadow. No body straps, no floating bags, no duplicate bags. "
        "If narration requires a relocation, explicitly carry by the top handle with visible hand contact "
        "and put the same bag down at the destination. Thin black stick torsos/limbs and white heads, "
        "mitten hands and oval feet remain unchanged.")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite(text):
    text = text.replace(OLD_RULE, "")
    for color in ("orange", "gray"):
        for wording in (f"normal {color} school backpack worn on the back, two shoulder straps, main zipper and front zipped pocket",
                        f"normal {color} school backpack worn on the back with two shoulder straps, main zipper and front zipped pocket",
                        f"normal {color} school backpack, two shoulder straps, main zipper and front zipped pocket"):
            text = text.replace(wording, f"separate normal {color} school backpack standing upright on the floor beside its owner, main zipper and front zipped pocket, no body straps")
    return text


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
    base = ROOT / "output/imagegen/survivor-grounded-bags-2026-10-12"
    record = json.loads((base / "registre.json").read_text(encoding="utf-8"))
    for asset in record["assets"]:
        assert digest(ROOT / asset["file"]) == asset["sha256"]
        assert digest(ROOT / asset["prompt"]) == asset["prompt_sha256"]
        for ref in asset["ordered_references"]:
            assert digest(ROOT / ref["path"]) == ref["sha256"]
    p = store.get_project(PID)
    assert p
    if p.get("workspace_backpack_revision") == "floor-v1":
        print("Backpack revision already imported; subsequent edits preserved.")
        return
    live = requests.get("http://127.0.0.1:8766/api/workspace/projects/" + PID, timeout=20)
    live.raise_for_status()
    state = live.json()
    assert not state["running"] and not any(s.get("status") in ("queued", "running") for s in state["scenes"])
    before = json.loads((ROOT / "work/survivor-grounded-bags-2026-10-12/project-before.json").read_text(encoding="utf-8"))
    assert p["script"] == before["script"], "User script changed; review before import"
    assert persisted_scenes(p["scenes"]) == persisted_scenes(before["scenes"]), "User scenes changed; review before import"
    assert len(p["scenes"]) == 3 and not p.get("voiceover") and not p.get("render")
    directory = store.project_dir(PID)
    destination = directory / "floor-backpacks-v1"
    if destination.exists():
        # A partial technical import may have copied these exact assets before saving the project.
        # Never replace an existing different file when recovering it.
        for source in base.rglob("*"):
            if source.is_file():
                target = destination / source.relative_to(base)
                assert target.is_file() and digest(target) == digest(source), "Partial import differs; inspect before recovering"
    else:
        shutil.copytree(base, destination)
    p.setdefault("workspace_visual_revision_history", []).append({
        "created": now(), "reason": "User rejected suspended bags and requested floor-standing backpacks",
        "scenes": copy.deepcopy(p["scenes"]), "cast": copy.deepcopy(p.get("workspace_cast_registry")),
        "style_snapshot": copy.deepcopy(p.get("style_snapshot")),
        "style_cast_snapshot": copy.deepcopy(p.get("style_cast_snapshot")),
        "script": p["script"], "workspace_references": copy.deepcopy(p.get("workspace_references"))})
    updated_styles = {}
    for sid, title, name, description, sources in STYLES:
        style = store.get_style(sid)
        assert style and style.get("workspace_survivor_seeded")
        if style.get("workspace_backpack_revision") == "floor-v1":
            variant = style["workspace_cast_registry"][name]["variants"]["default"]
            assert variant["description"] == description
            assert variant["references"][0]["sha256"] == digest(ROOT / sources[0])
            assert digest(store.style_dir(sid) / variant["references"][0]["path"]) == digest(ROOT / sources[0])
            updated_styles[sid] = style
            continue
        style.setdefault("workspace_identity_history", []).append({
            "created": now(), "character": name,
            "entry": copy.deepcopy(style["workspace_cast_registry"][name]),
            "visuals": copy.deepcopy(style["visuals"]), "thumbnail": copy.deepcopy(style["thumbnail"]),
            "workspace_references": copy.deepcopy(style.get("workspace_references"))})
        body = "refs/" + name.lower() + "-floor-backpack-v1.png"
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
        style["workspace_backpack_revision"] = "floor-v1"
        store.save_style(style)
        updated_styles[sid] = style
    patch = p["workspace_cast_registry"]["Patch"]["variants"]["default"]
    old_body = patch["references"][0]
    body = "floor-backpacks-v1/characters/patch.png"
    patch["references"][0] = {**old_body, "path": body, "sha256": digest(directory / body)}
    patch["description"] = STYLES[0][3]
    p["style_cast_snapshot"]["Patch"] = copy.deepcopy(updated_styles["survivor-patch"]["workspace_cast_registry"]["Patch"])
    for scene in p["scenes"]:
        sid = scene["id"]
        asset = next(a for a in record["assets"] if a.get("scene_id") == sid and a.get("current"))
        infected = "Delivery Infected" if sid == 3 else "Cart Infected"
        references = []
        for index, original in enumerate(asset["ordered_references"]):
            infected_ref = p["workspace_cast_registry"][infected]["variants"]["default"]["references"][0]
            if original["sha256"] == infected_ref["sha256"]:
                ref = copy.deepcopy(infected_ref)
            elif original["sha256"] in [r["sha256"] for r in patch["references"]]:
                ref = copy.deepcopy(next(r for r in patch["references"] if r["sha256"] == original["sha256"]))
            else:
                src = ROOT / original["path"]
                # Different generations often share plan-01.png: bind copies by hash as well as filename.
                dst = destination / "input-copies" / (original["sha256"][:16] + "-" + src.name)
                dst.parent.mkdir(exist_ok=True)
                if not dst.exists():
                    shutil.copy2(src, dst)
                ref = {"owner": "project", "path": dst.relative_to(directory).as_posix(),
                       "sha256": digest(dst), "role": "location" if "/masters/" in original["path"] else "continuity"}
            assert ref["sha256"] == original["sha256"]
            references.append(ref)
        scene.setdefault("generation_history", []).append({"image": scene.get("image"),
            "references": copy.deepcopy(scene.get("references")), "prompt": scene.get("prompt"), "changed_at": now()})
        original = (ROOT / asset["prompt"]).read_text(encoding="utf-8")
        scene.update(image=f"floor-backpacks-v1/A-REGARDER/{sid:02d}.png", status="done",
                     references=references, characters=["Patch", infected],
                     character_variants={"Patch": "default", infected: "default"},
                     original_cli_prompt=original, workspace_external_generation=asset,
                     human_review=None, prompt_author="codex")
        scene["prompt"] = original + "\n\n" + cast.binding(p, scene)
        scene.pop("workspace_future_reference_note", None)
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
        "reason": "Floor-standing bag vocabulary; previous text preserved in revision history"})
    p.update(script=script, custom_script=True, workspace_backpack_revision="floor-v1", prompts_approved=False)
    store.save_project(p)
    print("Imported both floor-standing bag identities, updated 3 previews and script prop states; no media jobs launched.")


if __name__ == "__main__":
    update()
