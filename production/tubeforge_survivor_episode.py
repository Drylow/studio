"""Compile Codex's explicit storyboard and import inspected media into TubeForge.

No AI authoring, reference choice, image calls, or automatic visual approval here.
The storyboard and reference index are authored files. Word timestamps come from
the already-recorded TubeForge narration. Generation uses the unchanged image CLI.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/TubeForge"))
from app import store, workspace_characters as cast
from app.util import now

BASE = ROOT / "output/imagegen/survivor-full-production-2026-10-12"
PRIVATE = ROOT / "work/survivor-full-production-2026-10-12"
EPISODES = {"patch": "chaines/survivor-projet/episode-01-supermarket",
            "alien": "chaines/alien-aftermath-projet/episode-01-gas-station"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compile_episode(name):
    source = ROOT / EPISODES[name]
    p = store.get_project(read(PRIVATE / "projects.json")[name])
    assert p and p.get("voiceover") and not p.get("voiceover_stale")
    assert p["script"].strip() == (source / "script-en.txt").read_text(encoding="utf-8").strip()
    text, words = p["script"], store.load_words(p["id"])
    assert len(words) == len(text.split())
    index = read(BASE / "reference-index.json")
    paragraphs = list(re.finditer(r"\S.*?(?=\n\s*\n|\Z)", text, re.S))
    specs = [row.split("|") for row in (source / "storyboard-production.txt").read_text(encoding="utf-8").splitlines()
             if row.strip() and not row.startswith("#")]
    assert [int(s[0]) for s in specs] == list(range(1, len(paragraphs) + 1))
    registry = {}
    for person, data in index["characters"].items():
        registry[person] = {"required": True, "variants": {"default": {
            "description": data["description"], "references": [
                {"owner": "project", "path": f, "sha256": digest(ROOT / f), "role": "identity",
                 "character": person, "variant": "default", "review_state": "verified"}
                for f in data["files"]]}}}
    stub = {"id": p["id"], "style_id": p["style_id"], "style_cast_snapshot": {},
            "workspace_cast_registry": registry, "model_snapshot": {"image_provider": "cli_proxy"}}
    output = []
    for spec, paragraph in zip(specs, paragraphs):
        num, cut, locs, people, objects, actions = spec
        cut = int(cut)
        sentences = [m for m in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", paragraph.group(), re.S) if m.group().strip()]
        if cut:
            assert 0 < cut < len(sentences), (name, num, cut, len(sentences))
            spans = [(0, sentences[cut - 1].end()), (sentences[cut].start(), len(paragraph.group()))]
        else:
            spans = [(0, len(paragraph.group()))]
        columns = [locs.split(">"), people.split(">"), objects.split(">"), actions.split("~")]
        assert all(len(col) == len(spans) for col in columns), (num, [len(c) for c in columns])
        for (a, b), location, names, props, action in zip(spans, *columns):
            c0, c1 = paragraph.start() + a, paragraph.start() + b
            narration = text[c0:c1].strip()
            aligned = [w for w in words if c0 <= w["c0"] < c1]
            assert aligned and " ".join(w["w"] for w in aligned) == " ".join(narration.split())
            actors = [v.strip() for v in names.split(",") if v.strip() and v.strip() != "-"]
            objnames = [v.strip() for v in props.split(",") if v.strip() and v.strip() != "-"]
            refs = [{"path": index["locations"][name][location], "role": "location", "label": location}]
            for actor in actors:
                if actor in registry:
                    refs.extend(copy.deepcopy(registry[actor]["variants"]["default"]["references"]))
            for obj in objnames:
                refs.append({"path": index["objects"][obj], "role": "object", "label": obj})
            if any(actor not in registry for actor in actors):
                refs.append({"path": index["characters"]["Mara"]["files"][0], "role": "style-only",
                             "label": "Anatomy only for unnamed one-off human; not Mara, no band/teal bag"})
            for ref in refs:
                ref.update(owner="project", sha256=digest(ROOT / ref["path"]))
            sid = len(output) + 1
            row = {"id": sid, "name": f"{name}-{sid:03d}", "text": narration, "c0": c0, "c1": c1,
                   "paragraph": int(num), "location_id": location, "characters": actors,
                   "character_variants": {v: "default" for v in actors if v in registry},
                   "references": refs, "objects": objnames, "action": action.strip(),
                   "start": aligned[0]["s"], "prompt_author": "codex", "human_review": None,
                   "motion": "zoom_in" if sid % 2 else "zoom_out"}
            labels = "\n".join(f"Image {i}: {r.get('character') or r.get('label')}; role {r['role']}."
                               for i, r in enumerate(refs, 1))
            prompt = (index["scene_contract"] + "\nActual narration: " + narration + "\n"
                      + labels + "\nConcrete scene, authored by Codex: " + action.strip()
                      + "\nDraw only this listed cast, each once: " + ", ".join(actors)
                      + ". No extra people from identity references. Match the location master's camera, "
                        "fixed walls/doors/windows/props and its explicit damage/lighting state. Only the "
                        "listed action and carried/placed objects change. Character reference sheets are "
                        "identity guides, never an extra portrait, ghost or scene background. "
                      + "\n\n" + cast.binding(stub, row))
            row["prompt"] = prompt
            row["prompt_file"] = f"output/imagegen/survivor-full-production-2026-10-12/prompts/scenes/{row['name']}.txt"
            prompt_path = ROOT / row["prompt_file"]
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt + "\n", encoding="utf-8")
            output.append(row)
    assert " ".join(" ".join(s["text"].split()) for s in output) == " ".join(text.split())
    output[0]["start"] = 0
    for i, row in enumerate(output):
        row["end"] = output[i + 1]["start"] if i + 1 < len(output) else p["voiceover"]["duration"]
        assert row["end"] > row["start"]
    result = {"project_id": p["id"], "script_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "voice_sha256": digest(store.project_dir(p["id"]) / p["voiceover"]["file"]),
              "voice_seconds": p["voiceover"]["duration"], "author": "Codex",
              "characters": registry, "scenes": output}
    write(BASE / (name + "-storyboard.json"), result)
    print(name, len(output), "authored plans; exact script/word coverage, voice timeline", round(result["voice_seconds"], 2))


def install_plan(name):
    plan = read(BASE / (name + "-storyboard.json"))
    p = store.get_project(plan["project_id"])
    assert hashlib.sha256(p["script"].encode()).hexdigest() == plan["script_sha256"]
    directory = store.project_dir(p["id"])
    assert digest(directory / p["voiceover"]["file"]) == plan["voice_sha256"]
    assert not any(v.get("state") == "running" for v in p["steps"].values())
    plan_digest = digest(BASE / (name + "-storyboard.json"))
    if p.get("workspace_production_plan_digest") == plan_digest:
        print(name, "plan already installed; media preserved")
        return
    if p.get("workspace_production_plan"):
        assert not any(s.get("image") for s in p["scenes"]), "Review existing production media before replacing a plan"
    p.setdefault("workspace_production_history", []).append({"created": now(),
        "reason": "User authorized complete episode production and supplied voice ID",
        "scenes": copy.deepcopy(p["scenes"]), "cast": copy.deepcopy(p.get("workspace_cast_registry")),
        "queue": copy.deepcopy(p.get("workspace_queue")), "preview_only": p.get("workspace_preview_only")})
    references = {}
    for row in plan["scenes"]:
        for ref in row["references"]:
            source = ROOT / ref["path"]
            assert digest(source) == ref["sha256"]
            relative = "production-v1/refs/" + ref["sha256"][:16] + "-" + source.name
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
            assert digest(target) == ref["sha256"]
            references[ref["path"]] = relative
    registry = copy.deepcopy(plan["characters"])
    for name_, entry in list(registry.items()):
        if not any(name_ in row["characters"] for row in plan["scenes"]):
            del registry[name_]
            continue
        for ref in entry["variants"]["default"]["references"]:
            ref["path"] = references[ref["path"]]
    p["workspace_cast_registry"] = registry
    rows = copy.deepcopy(plan["scenes"])
    for row in rows:
        for ref in row["references"]:
            ref["path"] = references[ref["path"]]
        row.update(status="idle", image=None, codex_visual_review={"state": "pending"})
        cast.validate(p, row)
    p.update(scenes=rows, workspace_preview_only=False, prompts_approved=False,
             workspace_production_plan=plan["script_sha256"],
             workspace_production_plan_digest=plan_digest,
             workspace_queue={"state": "production_images_pending", "created": now()},
             workspace_production_authorization={"source": "human_request", "scope": "complete both first episodes",
                "agent_visual_review_authorized": True, "publish_authorized": False})
    p["settings"]["visuals"].update(aspect="16:9", motion_strength=0.25)
    p["steps"]["visuals"].update(state="idle", done=0, total=len(rows), msg="Plans authored; media pending")
    store.save_project(p)
    write(directory / "production-v1/authored-storyboard.json", plan)
    print(name, "plan installed in TubeForge; no image calls or approval fabricated")


def import_reviewed(name):
    """Only import frames explicitly inspected and recorded by Codex, never unseen output."""
    from app import workspace_api as api
    from PIL import Image
    ffmpeg = subprocess.check_output([str(ROOT / "venv/Scripts/python.exe"), "-c",
        "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"], text=True).strip()
    plan = read(BASE / (name + "-storyboard.json"))
    p = store.get_project(plan["project_id"])
    assert hashlib.sha256(p["script"].encode()).hexdigest() == plan["script_sha256"]
    directory = store.project_dir(p["id"])
    assert digest(directory / p["voiceover"]["file"]) == plan["voice_sha256"]
    reviews = read(BASE / "scene-reviews.json")["scenes"]
    added = 0
    for scene in p["scenes"]:
        record = reviews.get(scene["name"])
        if not record or record["state"] != "inspected":
            continue
        native = ROOT / record["native_file"]
        assert digest(native) == record["native_sha256"]
        if scene.get("codex_visual_review", {}).get("native_sha256") == record["native_sha256"]:
            continue
        if record.get("reuse_registry"):
            actual = next(a for a in read(ROOT / record["reuse_registry"])["assets"] if a["id"] == record["reuse_asset"])
        else:
            actual = read(PRIVATE / (record.get("receipt_id", scene["name"]) + "-receipt.json"))
            actual.pop("model", None)
        assert actual["sha256"] == record["native_sha256"]
        for ref in actual["ordered_references"]:
            assert digest(ROOT / ref["path"]) == ref["sha256"]
        if actual.get("mask"):
            assert digest(ROOT / actual["mask"]["path"]) == actual["mask"]["sha256"]
        relative = f"production-v1/images/{scene['id']:03d}-{record['native_sha256'][:16]}.png"
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(native),
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xd0d0d0",
                "-frames:v", "1", "-n", str(target)], check=True)
        assert Image.open(target).size == (1920, 1080)
        if scene.get("image"):
            scene.setdefault("generation_history", []).append({"image": scene["image"],
                "human_review": scene.get("human_review"), "external_generation": scene.get("workspace_external_generation")})
        scene.update(image=relative, status="done", workspace_external_generation=actual,
            codex_visual_review={**record, "native_sha256": record["native_sha256"], "reviewer": "Codex", "user_approved": False})
        scene["original_cli_prompt"] = actual.get("prompt") or actual.get("prompt_file")
        scene["human_review"] = {"state": "verified", "notes": record["notes"], "reviewer": "Codex",
            "source": "delegated_agent_visual_review", "reviewed_at": now(), "evidence": api._scene_evidence(p, scene)}
        assert scene["human_review"]["evidence"]
        cast.validate(p, scene)
        write(directory / f"production-v1/receipts/{scene['id']:03d}.json", actual)
        added += 1
    done = sum(bool(s.get("image")) for s in p["scenes"])
    complete = done == len(p["scenes"])
    p["steps"]["visuals"].update(state="done" if complete else "idle", done=done, total=len(p["scenes"]),
        msg=f"Codex inspected {done}/{len(p['scenes'])} images; generation continues" if not complete else "All images inspected")
    p["workspace_queue"]["state"] = "images_ready_for_render" if complete else "production_images_pending"
    store.save_project(p)
    print(name, "imported", added, "new inspected frames;", done, "/", len(p["scenes"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["compile", "install", "import-reviewed"])
    parser.add_argument("episode", choices=EPISODES)
    args = parser.parse_args()
    {"compile": compile_episode, "install": install_plan, "import-reviewed": import_reviewed}[args.action](args.episode)
