"""Deploy the simple workspace without replacing projects or provider settings."""
import argparse
from pathlib import Path
import shutil
import subprocess

from common import REPO


def replace_once(root, relative, old, new):
    path = root / relative
    source = path.read_text(encoding='utf-8')
    if new in source:
        return
    if source.count(old) != 1:
        raise ValueError('Integration target changed: ' + relative)
    path.write_text(source.replace(old, new, 1), encoding='utf-8', newline='\n')


def deploy(root, seed=True):
    root = Path(root).resolve()
    if not root.is_relative_to((Path(REPO) / 'work').resolve()):
        raise ValueError('Workspace installation must stay in the private work directory')
    support = Path(REPO) / 'production/tubeforge_support'
    for name in ('workspace_api.py', 'workspace_seed.py', 'workspace_generation.py', 'workspace_management.py'):
        shutil.copy2(support / name, root / 'app' / name)
    web = root / 'app/web'
    legacy = web / 'legacy.html'
    if not legacy.exists():
        shutil.copy2(web / 'index.html', legacy)
    for name in ('workspace.js', 'workspace.css'):
        shutil.copy2(support / name, web / name)
    shutil.copy2(support / 'workspace.html', web / 'index.html')
    if 'workspace_api.install(app)' not in (root / 'app/server.py').read_text(encoding='utf-8'):
        replace_once(root, 'app/server.py',
            'app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")',
            'from . import workspace_api\nworkspace_api.install(app)\n\n'
            'app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")')
    replace_once(root, 'app/server.py',
        'workspace_api.install(app)\n',
        'workspace_api.install(app)\nfrom . import workspace_generation\nworkspace_generation.install(app)\n')
    replace_once(root, 'app/server.py',
        'workspace_generation.install(app)\n',
        'workspace_generation.install(app)\nfrom . import workspace_management\nworkspace_management.install(app)\n')
    replace_once(root, 'app/server.py',
        'if request.url.path in ("/", "/index.html", "/app.js", "/style.css"):',
        'if request.url.path in ("/", "/index.html", "/legacy.html", "/app.js", "/style.css", "/workspace.js", "/workspace.css"):')
    replace_once(root, 'app/server.py',
        '    mode = body.get("mode", "same")\n',
        '    if p.get("codex_directed"):\n'
        '        raise HTTPException(409, "Correction dirigee par Codex : conserver le prompt et les references explicites")\n'
        '    mode = body.get("mode", "same")\n')
    replace_once(root, 'app/pipeline.py',
        'async def do_thumbnails(p: dict, count: int | None = None, instruction: str = "") -> None:\n',
        'async def do_thumbnails(p: dict, count: int | None = None, instruction: str = "") -> None:\n'
        '    if p.get("codex_directed"):\n'
        '        raise RuntimeError("Miniature dirigee par Codex : aucun concept automatique")\n')
    replace_once(root, 'app/web/app.js',
        "  if (p.render) return '<span class=\"chip ok\">\u2713 Vid\u00e9o pr\u00eate</span>';",
        "  if (p.render) return '<span class=\"chip\">Export disponible - a verifier</span>';"
    )
    old_ui = web / 'app.js'
    old_ui.write_text(old_ui.read_text(encoding='utf-8').replace('videos pretes', 'exports disponibles')
                      .replace('vid\u00e9os pr\u00eates', 'exports disponibles'), encoding='utf-8', newline='\n')
    replace_once(root, 'app/steps/script.py',
        'def _models(p: dict) -> tuple[str, str]:\n',
        'def _models(p: dict) -> tuple[str, str]:\n'
        '    selected = p["settings"]["script"].get("model")\n'
        '    if selected:\n'
        '        return selected, "low" if p["settings"]["script"].get("mode") == "fast" else "medium"\n')
    # Existing per-project text calls must not silently ignore the saved selection.
    for name in ('script.py', 'visuals.py'):
        path = root / 'app/steps' / name
        source = path.read_text(encoding='utf-8')
        source = source.replace('model=config.get("FAST_MODEL")',
                                'model=p["settings"]["script"].get("model") or config.get("FAST_MODEL")')
        source = source.replace('model=config.get("SCRIPT_MODEL")',
                                'model=p["settings"]["script"].get("model") or config.get("SCRIPT_MODEL")')
        path.write_text(source, encoding='utf-8', newline='\n')
    for source, target in (('workspace_api_tests.py', 'test_workspace_api.py'),
                           ('workspace_generation_tests.py', 'test_workspace_generation.py'),
                           ('workspace_management_tests.py', 'test_workspace_management.py')):
        shutil.copy2(support / source, root / 'tests' / target)
    if seed:
        subprocess.run([str(root / '.venv/Scripts/python.exe'), '-m', 'app.workspace_seed'], cwd=root, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path(REPO) / 'work/TubeForge')
    args = parser.parse_args()
    deploy(args.directory)
