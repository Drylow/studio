"""Register the two requested survival styles and inspected main-character assets."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/TubeForge"))
from app import store
from app.util import now
from dotenv import dotenv_values


ART = (
    "Very simple flat 2D cartoon illustration with crisp black outlines and matte fills. "
    "Human adults have oversized perfectly circular smooth pure white heads, two small black "
    "oval eyes, tiny line mouths, no nose, ears, hair, eyebrows or realistic faces. Bodies and "
    "limbs are thin black stick lines, with pure white mitten hands and white oval shoes, exactly "
    "matching the supplied full-body reference proportions. No muscular bodies or bulky costumes. "
    "Every named individual appears once only; references depict the same individual, never an "
    "extra character. No duplicate identities, floating portraits or ghost overlays. "
    "Keep each character's own fixed markings, scarf and bag; do not transfer them to others. "
    "One landscape 16:9 scene, sparse shallow frontal setting, one readable action or interaction. "
    "No deep cinematic vistas, realistic rendering, gradients on white faces, text or watermarks. "
    "The background has few simple outlined props on a matte muted blue/gray/beige palette. "
)
BACKGROUND = (
    "Simple shallow 2D locations. Establish one master image and fixed door/window/object positions "
    "for each distinct room; use that exact master for subsequent shots in that room. Explicit "
    "variants for new views or damage; destroyed objects never return intact. Every shot advances "
    "a narrated action, consequence, observation or exchange, not just another zoom of the same tableau."
)
STYLES = (
    ("survivor-patch", "Patch Survives — cartoon simple", "Patch",
     "Round white head; small orange bandage above anatomical RIGHT eye, viewer LEFT in frontal views. "
     "Thin black stick body, white mitten hands and oval shoes; small orange flap bag, black clasp, orange handle. "
     "No hair, hat or eyebrows. Preserve the exact head/body proportion of the approved identity.",
     ["output/imagegen/survivor-launch-2026-10-12/01-patch-character.png",
      "output/imagegen/survivor-launch-2026-10-12/references/patch-head.png"]),
    ("survivor-alien-aftermath", "Alien Aftermath — cartoon simple", "Reed",
     "Round pure white head, small black oval eyes and short line mouth; no forehead bandage. "
     "Thin black stick body, white mitten hands and oval shoes, tiny dusty blue-gray scarf and small gray flap bag "
     "with short gray handle and one black clasp. Match the inspected whole-body identity reference.",
     ["output/imagegen/alien-main-reference-2026-10-12/reed.png"]),
)


def register():
    model = dotenv_values(ROOT / ".env").get("AI_IMAGE_MODEL")
    if not model:
        raise ValueError("The configured image selection is missing")
    results = []
    for sid, title, name, description, sources in STYLES:
        existing = store.get_style(sid)
        if existing:
            if existing.get("workspace_survivor_seeded"):
                results.append({"style_id": sid, "status": "preserved_existing_style"})
                continue
            raise ValueError("A different style already owns the requested identifier")
        # Verify all inputs before creating any style data.
        inspected = []
        for source in sources:
            path = ROOT / source
            if not path.is_file():
                raise ValueError("An inspected character source is missing")
            inspected.append((path, hashlib.sha256(path.read_bytes()).hexdigest()))
        style = store.default_style(sid, title)
        style.update(workspace_managed=True, workspace_survivor_seeded=True, archived=False,
                     workspace_image_provider="cli_proxy", workspace_authoring_mode="codex",
                     workspace_main_character=name, created=now())
        style["visuals"].update(art_style=ART + "Main character identity: " + description,
                                background_direction=BACKGROUND, image_model=model, image_provider="cli_proxy",
                                aspect="16:9", auto_characters=False, use_character_refs=True, use_style_refs=True,
                                continuity="off", avg_scene_seconds=6, preview="refs/main-01.png")
        style["thumbnail"].update(style=ART + "Simple readable thumbnail with one clear story conflict.",
                                  model=model, image_provider="cli_proxy", count=0, preview=None)
        style["voice"]["provider"] = "algrow"
        style["shorts"]["promo_count"] = 0
        directory = store.style_dir(sid) / "refs"
        directory.mkdir(parents=True, exist_ok=True)
        refs = []
        for index, (source, digest) in enumerate(inspected, 1):
            relative = f"refs/main-{index:02d}.png"
            shutil.copy2(source, store.style_dir(sid) / relative)
            refs.append({"path": relative, "owner": "style", "role": "identity", "character": name,
                         "variant": "default", "review_state": "verified", "sha256": digest,
                         "label": f"{name} — {'corps entier' if index == 1 else 'visage'}"})
        style["workspace_cast_registry"] = {name: {"required": True, "variants": {
            "default": {"description": description, "references": refs}}}}
        guide = dict(refs[0], role="style-only")
        style["workspace_references"] = [guide]
        style["visuals"].update(style_refs=[guide["path"]], reference_sources=[copy.deepcopy(guide)])
        store.save_style(style)
        results.append({"style_id": sid, "main_character": name, "references": len(refs), "status": "installed"})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    register()
