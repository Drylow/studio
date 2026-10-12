"""Save an additive private workspace snapshot and verify its archived contents."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SKIP = {"__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".git"}


def digest_stream(stream):
    result = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        result.update(chunk)
    return result.hexdigest()


def collect():
    selected = {}

    def add(path, archive_name=None):
        if path.is_symlink() or not path.is_file():
            return
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError("Workspace file resolved outside the repository")
        selected[archive_name or path.relative_to(ROOT).as_posix()] = path

    def tree(relative):
        base = ROOT / relative
        if base.exists():
            for path in base.rglob("*"):
                if not any(part in SKIP for part in path.relative_to(base).parts):
                    add(path)

    for name in ("README.md", "README_REPRISE.md", "CLAUDE.md", "AGENTS.md", ".env", ".env.example", "requirements.txt", ".gitignore"):
        add(ROOT / name)
    for pattern in ("tubeforge*.py", "tubeforge*.ps1"):
        for path in (ROOT / "production").glob(pattern):
            add(path)
    for name in ("common.py", "REPRISE.md", "COHERENCE_2D_CODEX.txt", "reprise_snapshot.py"):
        add(ROOT / "production" / name)
    for folder in ("production/tubeforge_support", "work/TubeForge/app", "work/TubeForge/tests", "work/TubeForge/assets", "work/TubeForge/data", "skills/facelessos", "chaines/survivor-projet", "chaines/alien-aftermath-projet", "output/channel-kits/survivor-launch-2026-10-12", "output/imagegen/survivor-launch-2026-10-12", "output/imagegen/patch-channel-kit-2026-10-12", "output/imagegen/alien-channel-kit-2026-10-12", "output/imagegen/survival-styles-tests-2026-10-12", "output/imagegen/survival-consistency-tests-2026-10-12", "work/survivor-launch-2026-10-12", "work/patch-channel-kit-2026-10-12", "work/alien-channel-kit-2026-10-12"):
        tree(folder)
    for name in (".env", ".env.example", "README.md", "requirements.txt", "start.bat", "batch.bat", "resolve_batch.py", "install_voix_locale.bat"):
        add(ROOT / "work/TubeForge" / name)
    add(ROOT / "output/channel-kits/survivor-launch-2026-10-12.zip")
    tree("output/imagegen/alien-main-reference-2026-10-12")
    tree("output/tubeforge-style-characters-2026-10-12")
    tree("work/alien-main-reference-2026-10-12")
    tree("output/imagegen/patch-supermarket-pilot-2026-10-12")
    tree("work/patch-supermarket-pilot-2026-10-12")
    skill = Path.home() / ".codex/skills/.system/imagegen"
    if skill.exists():
        for path in skill.rglob("*"):
            if path.is_file() and not path.is_symlink() and not any(part in SKIP for part in path.relative_to(skill).parts):
                selected["_local_tools/imagegen/" + path.relative_to(skill).as_posix()] = path
    return selected


def snapshot():
    private_root = (ROOT / "work/reprise").resolve()
    if not private_root.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Snapshot destination escaped private work directory")
    ignored = subprocess.run(["git", "check-ignore", str(private_root / "probe")], cwd=ROOT, capture_output=True)
    if ignored.returncode != 0:
        raise ValueError("Private snapshot destination is not ignored by Git")
    files = collect()
    total = sum(path.stat().st_size for path in files.values())
    if shutil.disk_usage(ROOT).free < total + 256 * 1024 * 1024:
        raise OSError("Insufficient space for a complete private snapshot")
    stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
    destination = private_root / ("snapshot-" + stamp)
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination / "workspace-private.zip"
    entries = []
    try:
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as zipped:
            for index, (name, path) in enumerate(sorted(files.items()), 1):
                before = path.stat()
                hasher = hashlib.sha256()
                with path.open("rb") as source, zipped.open(name, "w", force_zip64=True) as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                        hasher.update(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RuntimeError("A source changed during the snapshot; inspect before repeating")
                entries.append({"path": name, "bytes": after.st_size, "sha256": hasher.hexdigest()})
                if index % 200 == 0:
                    print(f"Archived {index}/{len(files)} files", flush=True)
            record = {"created_at_local": datetime.datetime.now().astimezone().isoformat(), "private_contains_credentials": True, "root": str(ROOT), "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "file_count": len(entries), "source_bytes": total, "files": entries}
            manifest = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
            zipped.writestr("_snapshot-manifest.json", manifest)
        with zipfile.ZipFile(archive) as zipped:
            for index, entry in enumerate(entries, 1):
                with zipped.open(entry["path"]) as stream:
                    if digest_stream(stream) != entry["sha256"]:
                        raise RuntimeError("Archived content verification failed")
                if index % 200 == 0:
                    print(f"Verified {index}/{len(entries)} files", flush=True)
        (destination / "manifest.json").write_text(manifest, encoding="utf-8")
        with archive.open("rb") as stream:
            archive_hash = digest_stream(stream)
        pointer = {"snapshot": destination.relative_to(ROOT).as_posix(), "archive": archive.relative_to(ROOT).as_posix(), "archive_sha256": archive_hash, "files": len(entries), "source_bytes": total, "verified": True, "private_contains_credentials": True}
        temporary = private_root / "latest.next.json"
        temporary.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
        temporary.replace(private_root / "latest.json")
        (destination / "LIRE-ICI.txt").write_text("Snapshot prive complet de TubeForge et du travail Survivor. Contient des configurations privees : ne pas publier.\nVerification SHA256 de chaque entree effectuee. Lire README_REPRISE.md dans le ZIP pour reprendre.\nExtraire uniquement dans un dossier neuf ; ne pas ecraser une installation en cours.\nDependances Python exclues : utiliser les requirements sauvegardes si migration.\n", encoding="utf-8")
        print(f"Verified snapshot: {destination}\nFiles: {len(entries)}\nSource size: {total / 1024**2:.1f} MiB", flush=True)
        return pointer
    except Exception:
        (destination / "INCOMPLETE.txt").write_text("Snapshot incomplet ; ne pas restaurer. Le pointeur latest n'a pas ete remplace.\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    snapshot()
