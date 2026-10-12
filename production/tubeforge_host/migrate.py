"""Rebase desktop file metadata and select native CPU rendering on the host.

Never change narration, authored prompts, identity images or completed video data.
The unmodified uploaded tree is backed up by the deployment operator first.
"""
import argparse
import json
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--previous-root", required=True)
    args = parser.parse_args()
    result = migrate(args.directory, args.previous_root)
    print(json.dumps({"metadata_files_updated": len(result), "native_render_selected": True}))
