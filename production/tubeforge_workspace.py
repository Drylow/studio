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
    for name in ('workspace_api.py', 'forge_api.py', 'workspace_seed.py', 'workspace_generation.py', 'workspace_management.py', 'workspace_visuals.py', 'workspace_voice.py', 'workspace_planning.py', 'workspace_composition.py', 'workspace_characters.py', 'workspace_locations.py', 'workspace_writing.py', 'workspace_access.py', 'workspace_identity.py', 'studio_bridge.py', 'google_flow.py'):
        shutil.copy2(support / name, root / 'app' / name)
    shutil.copytree(support / 'scriptwriting', root / 'app/scriptwriting', dirs_exist_ok=True)
    shutil.copy2(support / 'forge_migrations.py', root / 'app/forge_migrations.py')
    shutil.copytree(support / 'forge_docs', root / 'app/forge_docs', dirs_exist_ok=True)
    shutil.copy2(support / 'forge_queue.py', root / 'app/forge_queue.py')
    web = root / 'app/web'
    legacy = web / 'legacy.html'
    if not legacy.exists():
        shutil.copy2(web / 'index.html', legacy)
    for name in ('workspace.js', 'workspace.css'):
        shutil.copy2(support / name, web / name)
    shutil.copy2(support / 'workspace.html', web / 'index.html')
    # Patch upgraded installations too; the portable base contains this already.
    replace_once(root, 'app/store.py', '        "id": pid,\n',
                 '        "id": pid,\n        "owner_id": __import__(__package__ + ".workspace_identity", fromlist=["current_owner"]).current_owner(),\n')
    if '"owner_name":' not in (root / 'app/store.py').read_text(encoding='utf-8'):
        replace_once(root, 'app/store.py',
                     '        "owner_id": __import__(__package__ + ".workspace_identity", fromlist=["current_owner"]).current_owner(),\n',
                     '        "owner_id": __import__(__package__ + ".workspace_identity", fromlist=["current_owner"]).current_owner(),\n'
                     '        "owner_name": __import__(__package__ + ".workspace_identity", fromlist=["current_name"]).current_name(),\n')
    duplicate = root / 'app/store.py'
    source = duplicate.read_text(encoding='utf-8')
    if "from .workspace_identity import current_owner" not in source:
        replace_once(root, 'app/store.py', '    p["steps"]["render"] = {"state": "idle", "msg": "", "done": 0, "total": 0}\n',
                     '    from .workspace_identity import current_owner\n    p["owner_id"] = current_owner()\n'
                     '    p["steps"]["render"] = {"state": "idle", "msg": "", "done": 0, "total": 0}\n')
    replace_once(root, 'app/config.py', 'SECRET_KEYS = ',
                 'DEFAULTS.update({"IMAGE_PROVIDER": "cli_proxy", "USEAPI_API_KEY": "",\n'
                 '                 "USEAPI_IMAGE_MODEL": "", "USEAPI_IMAGE_CONCURRENCY": "3"})\n\n'
                 'SECRET_KEYS = ')
    replace_once(root, 'app/config.py', 'SECRET_KEYS = {"PROXY_API_KEY", "ELEVENLABS_API_KEY"}',
                 'SECRET_KEYS = {"PROXY_API_KEY", "ELEVENLABS_API_KEY", "USEAPI_API_KEY"}')
    replace_once(root, 'app/llm.py', 'label: str = "image") -> bytes:',
                 'label: str = "image", provider: str | None = None, receipt: dict | None = None) -> bytes:')
    replace_once(root, 'app/llm.py', '    size, ratio = ASPECTS.get(aspect, ASPECTS["16:9"])',
                 '    if provider == "google_flow":\n'
                 '        from . import google_flow\n'
                 '        STATS["image"]["active"] += 1\n'
                 '        started = time.time()\n'
                 '        try:\n'
                 '            data = await google_flow.generate(prompt, model, aspect, refs, receipt)\n'
                 '            STATS["image"]["done"] += 1\n'
                 '            STATS["image"]["total_seconds"] += time.time() - started\n'
                 '            return data\n'
                 '        except Exception:\n'
                 '            STATS["image"]["errors"] += 1\n'
                 '            raise\n'
                 '        finally:\n'
                 '            STATS["image"]["active"] -= 1\n'
                 '    if provider not in (None, "cli_proxy"):\n'
                 '        raise ApiError("Unknown image provider")\n'
                 '    size, ratio = ASPECTS.get(aspect, ASPECTS["16:9"])')
    replace_once(root, 'app/llm.py', '    _sems.clear()\n',
                 '    _sems.clear()\n    from . import google_flow\n    google_flow.reset()\n')
    replace_once(root, 'app/llm.py', '               on_delta=None) -> str:',
                 '               on_delta=None, hedge: bool = True) -> str:')
    replace_once(root, 'app/llm.py', '        first = asyncio.create_task(once_bounded())\n'
                 '        done, _ = await asyncio.wait({first}, timeout=hedge_after)\n',
                 '        if not hedge:\n            return await once_bounded()\n'
                 '        first = asyncio.create_task(once_bounded())\n'
                 '        done, _ = await asyncio.wait({first}, timeout=hedge_after)\n')
    # A directed one-attempt image must use one provider call and one queue slot.
    # The legacy latency hedge otherwise doubles paid work behind that slot.
    replace_once(root, 'app/llm.py',
                 '        first = asyncio.create_task(once_bounded())\n'
                 '        done, _ = await asyncio.wait({first}, timeout=150)\n',
                 '        if attempts == 1:\n            return await once_bounded()\n'
                 '        first = asyncio.create_task(once_bounded())\n'
                 '        done, _ = await asyncio.wait({first}, timeout=150)\n')
    replace_once(root, 'app/steps/visuals.py', '                                    label=f"Fiche {c[\'name\']}")',
                 '                                    label=f"Fiche {c[\'name\']}", provider=v.get("image_provider", "cli_proxy"))')
    replace_once(root, 'app/steps/visuals.py', '                                                label=f"Image #{s[\'id\']}")',
                 '                                                label=f"Image #{s[\'id\']}", provider=v.get("image_provider", "cli_proxy"))')
    if 'provider=t.get("image_provider", "cli_proxy")' not in (root / 'app/steps/thumbnails.py').read_text(encoding='utf-8'):
      replace_once(root, 'app/steps/thumbnails.py', '                                           label="Miniature")',
                 '                                           label="Miniature", provider=t.get("image_provider", "cli_proxy"))')
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
        'workspace_management.install(app)\n',
        'workspace_management.install(app)\nfrom . import workspace_voice\nworkspace_voice.install(app)\n')
    replace_once(root, 'app/server.py',
        'workspace_voice.install(app)\n',
        'workspace_voice.install(app)\nfrom . import workspace_planning\nworkspace_planning.install(app)\n')
    replace_once(root, 'app/server.py',
        'workspace_planning.install(app)\n',
        'workspace_planning.install(app)\nfrom . import workspace_writing\nworkspace_writing.install(app)\n')
    replace_once(root, 'app/server.py',
        'workspace_writing.install(app)\n',
        'workspace_writing.install(app)\nfrom . import workspace_access\nworkspace_access.install(app)\n')
    replace_once(root, 'app/server.py',
        'workspace_access.install(app)\n',
        'workspace_access.install(app)\nfrom . import forge_api\nforge_api.install(app)\n')
    replace_once(root, 'app/server.py',
        'forge_api.install(app)\n',
        'forge_api.install(app)\nfrom . import forge_queue\nforge_queue.install(app)\n')
    replace_once(root, 'app/server.py',
        'if request.url.path in ("/", "/index.html", "/app.js", "/style.css"):',
        'if request.url.path in ("/", "/index.html", "/legacy.html", "/app.js", "/style.css", "/workspace.js", "/workspace.css"):')
    if 'if p.get("codex_directed"):' not in (root / 'app/server.py').read_text(encoding='utf-8'):
      replace_once(root, 'app/server.py',
        '    mode = body.get("mode", "same")\n',
        '    if p.get("codex_directed"):\n'
        '        raise HTTPException(409, "Preserve the authored prompt and explicit references for this shot")\n'
        '    mode = body.get("mode", "same")\n')
    if 'if p.get("codex_directed"):' not in (root / 'app/pipeline.py').read_text(encoding='utf-8'):
      replace_once(root, 'app/pipeline.py',
        'async def do_thumbnails(p: dict, count: int | None = None, instruction: str = "") -> None:\n',
        'async def do_thumbnails(p: dict, count: int | None = None, instruction: str = "") -> None:\n'
        '    if p.get("codex_directed"):\n'
        '        raise RuntimeError("Authored thumbnail: automatic concepts are disabled")\n')
    old_ui = web / 'app.js'
    old_ui.write_text(old_ui.read_text(encoding='utf-8').replace('Export disponible - a verifier',
                      'Export available - needs review'), encoding='utf-8', newline='\n')
    replace_once(root, 'app/web/app.js',
        "  if (p.render) return '<span class=\"chip ok\">\u2713 Vid\u00e9o pr\u00eate</span>';",
        "  if (p.render) return '<span class=\"chip\">Export available - needs review</span>';"
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
    replace_once(root, 'app/config.py', '    "LLM_CONCURRENCY": "36",\n',
                 '    "LLM_CONCURRENCY": "36",\n    "WORKSPACE_PLAN_CONCURRENCY": "6",\n')
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
                           ('forge_api_tests.py', 'test_forge_api.py'),
                           ('forge_queue_tests.py', 'test_forge_queue.py'),
                           ('workspace_generation_tests.py', 'test_workspace_generation.py'),
                           ('workspace_management_tests.py', 'test_workspace_management.py'),
                           ('workspace_voice_tests.py', 'test_workspace_voice.py'),
                           ('workspace_planning_tests.py', 'test_workspace_planning.py'),
                           ('workspace_locations_tests.py', 'test_workspace_locations.py'),
                           ('workspace_characters_tests.py', 'test_workspace_characters.py'),
                           ('workspace_writing_tests.py', 'test_workspace_writing.py'),
                           ('workspace_access_tests.py', 'test_workspace_access.py'),
                           ('google_flow_tests.py', 'test_google_flow.py')):
        shutil.copy2(support / source, root / 'tests' / target)
    if seed:
        python = root / ('.venv/Scripts/python.exe' if __import__('os').name == 'nt' else '.venv/bin/python')
        subprocess.run([str(python), '-m', 'app.workspace_seed'], cwd=root, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path(REPO) / 'work/TubeForge')
    parser.add_argument('--no-seed', action='store_true', help='Preserve channel/style data during an update')
    args = parser.parse_args()
    deploy(args.directory, seed=not args.no_seed)
