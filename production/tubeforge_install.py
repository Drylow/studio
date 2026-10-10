"""Install the user's pinned archive without overwriting another installation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from common import REPO
from tubeforge_configure import configure

ARCHIVE_SHA256 = 'a1c870ff57bc0adba8d34a8c851379f4bb8d42d1c9fd5a8d5f90f07791aacd16'


def unpack(archive, destination):
    archive, destination = Path(archive), Path(destination).resolve()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Archive version changed; review it before applying the integration')
    if destination.exists():
        raise ValueError('Destination already exists; existing projects will not be overwritten')
    with zipfile.ZipFile(archive) as source:
        entries = []
        for entry in source.infolist():
            parts = Path(entry.filename.replace('\\', '/')).parts
            if not parts or parts[0] != 'TubeForge' or '..' in parts or entry.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError('Unsafe archive member')
            target = (destination / Path(*parts[1:])).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Archive path escapes installation')
            entries.append((entry, target))
        destination.mkdir(parents=True)
        for entry, target in entries:
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as stream, target.open('wb') as output:
                    shutil.copyfileobj(stream, output)


def integrate(destination):
    destination = Path(destination).resolve()
    support = Path(REPO) / 'production/tubeforge_support'
    relative = destination.relative_to(Path(REPO)).as_posix()
    for file in ('app/config.py', 'app/pipeline.py', 'app/steps/render.py', 'app/tts.py', 'app/server.py', 'start.bat', 'batch.bat'):
        path = destination / file
        path.write_text(path.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
    patch_bytes = (support / 'vendor.patch').read_bytes().replace(b'\r\n', b'\n')
    subprocess.run(['git', 'apply', '--check', '--unidiff-zero', '--directory=' + relative, '-'],
                    input=patch_bytes, cwd=REPO, check=True)
    subprocess.run(['git', 'apply', '--unidiff-zero', '--directory=' + relative, '-'],
                    input=patch_bytes, cwd=REPO, check=True)
    path = destination / 'app/web/app.js'
    lines = path.read_text(encoding='utf-8').splitlines()
    for edit in reversed(json.loads((support / 'voice_ui.json').read_text(encoding='utf-8'))):
        start = edit['line'] - 1
        lines[start:start + edit['remove']] = edit['insert']
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for src, dst in [('main.py', '__main__.py'), ('__init__.py', '__init__.py'),
                     ('studio_bridge.py', 'studio_bridge.py'), ('import_review.py', 'import_review.py'),
                     ('benchmark.py', 'benchmark.py')]:
        shutil.copy2(support / src, destination / 'app' / dst)
    shutil.copy2(support / 'integration_tests.py', destination / 'tests/test_studio_bridge.py')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--directory', type=Path, default=Path(REPO) / 'work/TubeForge')
    args = parser.parse_args()
    destination = args.directory.resolve()
    if not destination.is_relative_to((Path(REPO) / 'work').resolve()):
        raise ValueError('TubeForge must stay in the private ignored work directory')
    unpack(args.archive, destination)
    integrate(destination)
    python = Path(REPO) / 'venv/Scripts/python.exe'
    subprocess.run([str(python), '-m', 'venv', str(destination / '.venv')], check=True)
    local = destination / '.venv/Scripts/python.exe'
    subprocess.run([str(local), '-m', 'pip', 'install', '-r',
                    str(Path(REPO) / 'production/tubeforge_support/requirements.lock')], check=True)
    configure(destination)
    from tubeforge_workspace import deploy
    deploy(destination)
    subprocess.run([str(local), '-m', 'pytest', '-q', 'tests'], cwd=destination, check=True)
    print('TubeForge installed. Start with production/tubeforge.ps1.')


if __name__ == '__main__':
    main()
