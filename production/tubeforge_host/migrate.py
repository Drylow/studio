"""Rebase desktop file metadata and select native CPU rendering on the host.

Never change narration, authored prompts, identity images or completed video data.
The unmodified uploaded tree is backed up by the deployment operator first.
"""
import argparse
import json
import hashlib
import shutil
from pathlib import Path


def rebase(value, previous, destination, key=""):
    if isinstance(value, dict):
        return {k: rebase(v, previous, destination, k) for k, v in value.items()}
    if isinstance(value, list):
        return [rebase(v, previous, destination, key) for v in value]
    if isinstance(value, str) and key not in {"prompt", "script", "text", "description", "art_style", "content"}:
        normalized = value.replace("\\", "/")
        prefix = previous.replace("\\", "/").rstrip("/")
        if normalized.startswith(prefix + "/"):
            return destination.rstrip("/") + normalized[len(prefix):]
    return value


def migrate(directory, previous):
    changed = []
    for file in Path(directory).rglob("*.json"):
        try:
            old = json.loads(file.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            continue
        new = rebase(old, previous, "/opt/studio")
        if file.name in ("project.json", "style.json") and isinstance(new, dict):
            if file.name == "project.json":
                new.setdefault("settings", {}).setdefault("visuals", {})["render_backend"] = "native"
            else:
                new.setdefault("visuals", {})["render_backend"] = "native"
        if new != old:
            temporary = file.with_suffix(".migration.tmp")
            temporary.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
            temporary.replace(file)
            changed.append(file.relative_to(directory).as_posix())
    return changed


def enrich_survivor_cast(directory, studio):
    """Add only missing identities from the shipped inspected presets; preserve edits."""
    directory, studio = Path(directory), Path(studio)
    added = []
    for source in (studio / "production/tubeforge_presets").glob("*.json"):
        preset = json.loads(source.read_text(encoding="utf-8"))
        style_dir = directory / "styles" / preset["id"]
        path = style_dir / "style.json"
        if not path.is_file():
            continue
        style = json.loads(path.read_text(encoding="utf-8"))
        registry = style.setdefault("workspace_cast_registry", {})
        changed = False
        for name, identity in preset["characters"].items():
            if name in registry:
                continue
            refs = []
            for n, (file, expected) in enumerate(zip(identity["files"], identity["sha256"], strict=True), 1):
                src = (studio / file).resolve()
                if not src.is_relative_to(studio.resolve()) or hashlib.sha256(src.read_bytes()).hexdigest() != expected:
                    raise ValueError("Inspect a changed identity before importing its reference")
                relative = f"refs/host-cast-{name.lower().replace(' ', '-')}-{n:02d}.png"
                target = style_dir / relative
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                    raise ValueError("Preserve an existing edited character file")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                refs.append({"path": relative, "owner": "style", "character": name, "role": "identity",
                             "variant": "default", "review_state": "verified", "sha256": expected,
                             "review_provenance": preset["review_provenance"], "label": name})
            registry[name] = {"required": True, "variants": {"default": {
                "description": identity["description"], "references": refs}}}
            added.append({"style": preset["id"], "character": name})
            changed = True
        if changed:
            path.write_text(json.dumps(style, ensure_ascii=False, indent=1), encoding="utf-8")
    return added


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--previous-root", required=True)
    parser.add_argument("--enrich-survivor-cast", type=Path, metavar="STUDIO", help="Add only missing inspected Survivor identities from this source clone")
    args = parser.parse_args()
    result = migrate(args.directory, args.previous_root)
    identities = enrich_survivor_cast(args.directory, args.enrich_survivor_cast) if args.enrich_survivor_cast else []
    print(json.dumps({"metadata_files_updated": len(result), "native_render_selected": True, "added_cast": identities}))
