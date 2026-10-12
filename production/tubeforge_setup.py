"""Install the complete Git-tracked TubeForge sources into a fresh private folder.

No archive, content generation, provider substitution or existing-data overwrite.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "production/tubeforge_base"
PRESETS = ROOT / "production/tubeforge_presets"


def python_in(root):
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_sources(destination):
    destination = Path(destination).resolve()
    if not destination.is_relative_to((ROOT / "work").resolve()) or destination == (ROOT / "work").resolve():
        raise ValueError("Choose a fresh subfolder inside the ignored work directory")
    if destination.exists():
        raise ValueError("Destination exists; use workspace deployment --no-seed for updates")
    shutil.copytree(SOURCE, destination)
    (destination / "tests").mkdir()
    from tubeforge_workspace import deploy
    deploy(destination, seed=False)
    return destination


def seed_presets(destination, private, voice_id):
    """Copy named inspected references exactly; preserve existing styles/channels."""
    sys.path.insert(0, str(destination))
    from app import config, store
    from app.util import now, read_json, write_json
    installed = []
    channels_file = config.DATA / "channels.json"
    channels = read_json(channels_file, [])
    for path in sorted(PRESETS.glob("*.json")):
        preset = json.loads(path.read_text(encoding="utf-8"))
        sid = preset["id"]
        if store.get_style(sid):
            installed.append({"id": sid, "status": "preserved_existing"})
            continue
        style = store.default_style(sid, preset["name"])
        style.update(workspace_managed=True, workspace_survivor_seeded=True, archived=False,
                     workspace_image_provider=preset["image_provider"],
                     workspace_authoring_mode=preset["authoring_mode"],
                     workspace_main_character=preset["main_character"], created=now())
        style["visuals"].update(preset["visuals"], image_model=private.get("AI_IMAGE_MODEL", ""),
                                image_provider=preset["image_provider"])
        style["script"]["model"] = private.get("AI_TEXT_MODEL", "")
        style["thumbnail"].update(style=preset["thumbnail_direction"], count=0,
                                  model=private.get("AI_IMAGE_MODEL", ""), image_provider=preset["image_provider"])
        style["voice"].update(preset["voice"], voice_id=voice_id, voice_name="Survivor narrator",
                              model_id=private.get("TTS_MODEL", ""))
        style["workspace_cast_registry"] = {}
        for name, identity in preset["characters"].items():
            refs = []
            for n, (relative, expected) in enumerate(zip(identity["files"], identity["sha256"], strict=True), 1):
                source = (ROOT / relative).resolve()
                if not source.is_relative_to(ROOT) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                    raise ValueError("Reference changed; inspect it and update the preset digest first")
                filename = f"refs/{name.lower().replace(' ', '-')}-{n:02d}.png"
                target = store.style_dir(sid) / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                refs.append({"path": filename, "owner": "style", "role": "identity", "character": name,
                             "variant": "default", "review_state": "verified", "sha256": expected,
                             "label": name, "review_provenance": preset["review_provenance"]})
            style["workspace_cast_registry"][name] = {"required": True, "variants": {"default": {
                "description": identity["description"], "references": refs}}}
        main_refs = style["workspace_cast_registry"][preset["main_character"]]["variants"]["default"]["references"]
        guide = dict(main_refs[0], role="style-only")
        style["workspace_references"] = [guide]
        style["visuals"].update(style_refs=[guide["path"]], reference_sources=[copy.deepcopy(guide)], preview=guide["path"])
        style["workspace_location_catalog"] = preset["location_masters"]
        store.save_style(style)
        cid = sid + "-channel"
        if not any(c["id"] == cid for c in channels):
            channels.append({"id": cid, "name": "Patch Survives" if sid == "survivor-patch" else "Alien Aftermath",
                             "style_id": sid, "language": "English", "kind": "long", "workspace_managed": True,
                             "archived": False, "auto_resolve": False, "target_minutes": 15,
                             "voice": copy.deepcopy(style["voice"]), "created": now()})
        installed.append({"id": sid, "characters": len(preset["characters"]), "status": "installed"})
    write_json(channels_file, channels)
    policy = config.DATA / "workspace-visual-policy.json"
    if not policy.exists():
        write_json(policy, {"default_style_id": "survivor-alien-aftermath", "image_provider": "cli_proxy"})
    return installed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "work/TubeForge")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--voice-id", default="rU18Fk3uSDhmg5Xh41o4")
    parser.add_argument("--sources-only", action="store_true", help="Offline staging only, without configuration, environments or preset import")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Invalid port")
    private = {}
    if not args.sources_only:
        from dotenv import dotenv_values
        private = dotenv_values(ROOT / ".env")
        required = ("AI_BASE_URL", "AI_API_KEY", "AI_TEXT_MODEL", "AI_IMAGE_MODEL", "ALGROW_API_KEY")
        missing = [k for k in required if not private.get(k)]
        if missing:
            parser.error("Set private root .env values first: " + ", ".join(missing))
    destination = install_sources(args.directory)
    if args.sources_only:
        print("Sources staged offline; no API calls, dependencies or private configuration copied.")
        return
    repo_env = ROOT / "venv"
    if not python_in(repo_env).is_file():
        subprocess.run([sys.executable, "-m", "venv", str(repo_env)], check=True)
    repo_python = python_in(repo_env)
    requirements = ROOT / "production/tubeforge_base/requirements.txt"
    subprocess.run([str(repo_python), "-m", "pip", "install", "-r", str(requirements)], check=True)
    subprocess.run([str(repo_python), "-m", "venv", str(destination / ".venv")], check=True)
    local_python = python_in(destination / ".venv")
    subprocess.run([str(local_python), "-m", "pip", "install", "-r", str(requirements)], check=True)
    ffmpeg = subprocess.check_output([str(repo_python), "-c",
        "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"], text=True).strip()
    from dotenv import set_key
    values = {"PROXY_BASE_URL": private["AI_BASE_URL"], "PROXY_API_KEY": private["AI_API_KEY"],
              "SCRIPT_MODEL": private["AI_TEXT_MODEL"], "FAST_MODEL": private.get("AI_FAST_MODEL") or private["AI_TEXT_MODEL"],
              "IMAGE_MODEL": private["AI_IMAGE_MODEL"], "TTS_MODEL": private.get("TTS_MODEL", ""),
              "IMAGE_PROVIDER": "cli_proxy", "STUDIO_ROOT": str(ROOT), "HOST": "127.0.0.1", "PORT": str(args.port),
              "RENDER_BACKEND": "native", "RENDER_WORKERS": "2", "IMAGE_CONCURRENCY": "3", "LLM_CONCURRENCY": "3",
              "FFMPEG": private.get("FFMPEG") or ffmpeg,
              "FFPROBE": private.get("FFPROBE") or shutil.which("ffprobe") or "",
              "USEAPI_API_KEY": private.get("USEAPI_API_KEY", ""), "USEAPI_IMAGE_MODEL": private.get("USEAPI_IMAGE_MODEL", "")}
    for key, value in values.items():
        set_key(str(destination / ".env"), key, str(value), quote_mode="always")
    # Run seeding in the installed interpreter, not the setup interpreter's cached modules.
    code = ("import sys; sys.path.insert(0, sys.argv[1]); "
            "from tubeforge_setup import seed_presets; from dotenv import dotenv_values; "
            "from pathlib import Path; print(seed_presets(Path(sys.argv[2]), dotenv_values(Path(sys.argv[3])), sys.argv[4]))")
    subprocess.run([str(local_python), "-c", code, str(ROOT / "production"), str(destination),
                    str(ROOT / ".env"), args.voice_id], cwd=destination, check=True)
    print(f"Installed. Start from {destination}: .venv interpreter -m app serve --port {args.port}.")
    print("Default render is explicitly native FFmpeg. OVNI is optional and must be selected after its installation.")


if __name__ == "__main__":
    main()
