"""Deployment regression tests, using a disposable reconstruction of the archive."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from tubeforge_install import integrate, unpack
from tubeforge_workspace import deploy


def test_workspace_deployment_preserves_projects_and_is_repeatable():
    repo = Path(__file__).resolve().parent.parent
    archive = Path.home() / 'Downloads/TubeForge.zip'
    if not archive.exists():
        pytest.skip('Private archive unavailable')
    import tempfile
    with tempfile.TemporaryDirectory(prefix='workspace-install-', dir=repo / 'work') as tmp:
        destination = Path(tmp) / 'TubeForge'
        unpack(archive, destination)
        integrate(destination)
        private_project = destination / 'data/projects/user-saved/project.json'
        private_project.parent.mkdir(parents=True, exist_ok=True)
        private_project.write_text('{"id":"user-saved","script":"Keep this text"}', encoding='utf-8')
        before = hashlib.sha256(private_project.read_bytes()).hexdigest()
        deploy(destination, seed=False)
        first = {str(p.relative_to(destination)): p.read_bytes() for p in (
            destination / 'app/server.py', destination / 'app/pipeline.py',
            destination / 'app/web/index.html', destination / 'app/steps/script.py',
            destination / 'app/steps/visuals.py', destination / 'app/web/legacy.html')}
        deploy(destination, seed=False)
        assert before == hashlib.sha256(private_project.read_bytes()).hexdigest()
        assert all((destination / name).read_bytes() == content for name, content in first.items())
        assert b'workspace.js' in (destination / 'app/web/index.html').read_bytes()
        assert b'app.js' in (destination / 'app/web/legacy.html').read_bytes()
        assert b'workspace_api.install(app)' in (destination / 'app/server.py').read_bytes()
        assert b'Export disponible - a verifier' in (destination / 'app/web/app.js').read_bytes()
        assert b'get("model")' in (destination / 'app/steps/script.py').read_bytes()
