"""Explicit, backed-up project image-model migrations; no paid calls or rendering."""
import asyncio
import copy
import hashlib
import json
import re
import shutil
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict

from app import config, store
from . import workspace_api as api
from .workspace_identity import current_owner
from app.util import now, read_json, write_json

_lock = asyncio.Lock()


class MigrationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    expected_snapshot_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    image_model: str = Field(min_length=1, max_length=150)
    image_provider: str
    acknowledge_untested_model: bool = False


@asynccontextmanager
async def project_lock(pid):
    # API has multiple workers: an asyncio lock alone cannot prevent duplicate
    # migrations across processes. This lock lives outside the public media tree.
    import fcntl
    api._identifier(pid)
    root = config.DATA / 'model-migrations' / 'locks'
    root.mkdir(parents=True, exist_ok=True)
    with (root / (pid + '.lock')).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HTTPException(409, 'Another migration is active for this project') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def policy_allows(p, provider):
    """Server-owned exception scoped to an exact project; never a client flag."""
    policy = read_json(config.DATA / 'workspace-model-migration-policy.json', {}) or {}
    return provider in policy.get('project_providers', {}).get(p['id'], [])


def check_provider(p, provider):
    if policy_allows(p, provider):
        return
    api._check_image_provider(provider, p.get('style_id'))


def backup_dir(pid, mid):
    api._identifier(pid)
    if not re.fullmatch(r'[a-f0-9]{32}', mid):
        raise HTTPException(422, 'Invalid migration ID')
    return config.DATA / 'model-migrations' / pid / mid


def ensure_idle(p):
    # In-memory jobs are checked by _project(writable=True); also refuse persisted
    # reservations from other processes and interrupted batches.
    for field in ('workspace_batch', 'workspace_external_execution', 'workspace_generation'):
        if (p.get(field) or {}).get('state') in ('running', 'queued', 'stopping'):
            raise HTTPException(409, 'Reconcile or finish the active project job before migration')
    if any(s.get('status') in ('running', 'queued') for s in p.get('scenes', [])):
        raise HTTPException(409, 'A shot is still active')
    if any(s.get('state') in ('running', 'queued') for s in p.get('steps', {}).values()):
        raise HTTPException(409, 'A project step is still active')


def make_backup(p, mid):
    """Keep all project files, full JSON and external references, then verify bytes."""
    dest = backup_dir(p['id'], mid)
    dest.mkdir(parents=True, exist_ok=False)
    root = store.project_dir(p['id']).resolve()
    files = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise HTTPException(409, 'Project contains a symlink; inspect before backup')
        if path.is_file():
            files['project/' + path.relative_to(root).as_posix()] = path
    for s in p.get('scenes', []):
        if s.get('image') and not api._file_digest(root, s['image']):
            raise HTTPException(409, 'A selected image is missing; migration was not applied')
        for i, ref in enumerate(s.get('references') or []):
            path = api._reference_path(p, s, i).resolve()
            # Keep owner/path mapping in the manifest and full project JSON.
            if not path.is_relative_to(root):
                name = hashlib.sha256(str(path).encode()).hexdigest() + path.suffix
                files['external-references/' + name] = path
    total = sum(f.stat().st_size for f in files.values())
    if shutil.disk_usage(dest).free < total * 2 + 100 * 1024 * 1024:
        raise HTTPException(507, 'Insufficient disk space for a verified migration backup')
    manifest = []
    archive = dest / 'backup.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_STORED) as z:
        z.writestr('project-before.json', json.dumps(p, ensure_ascii=False, indent=2))
        for name, src in sorted(files.items()):
            before = digest(src)
            z.write(src, name)
            if digest(src) != before:
                raise HTTPException(409, 'A source changed during backup; migration was not applied')
            manifest.append({'entry': name, 'source': str(src), 'sha256': before, 'bytes': src.stat().st_size})
        z.writestr('manifest.json', json.dumps(manifest, indent=2))
    with zipfile.ZipFile(archive) as z:
        for entry in manifest:
            with z.open(entry['entry']) as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != entry['sha256']:
                    raise HTTPException(500, 'Backup verification failed; migration was not applied')
    return {'file': 'backup.zip', 'sha256': digest(archive), 'bytes': archive.stat().st_size,
            'files': len(manifest), 'selected_images': sum(bool(s.get('image')) for s in p.get('scenes', []))}


def install(router):
    @router.get('/videos/{pid}/model-migration')
    async def migration_options(pid: str):
        p = api._project(pid)
        return {'project_id': pid, 'model_snapshot': p.get('model_snapshot'),
                'snapshot_sha256': api._hash(p.get('model_snapshot') or {}),
                'settings_visual_model': p.get('settings', {}).get('visuals', {}).get('image_model'),
                'project_provider_exceptions': (read_json(config.DATA / 'workspace-model-migration-policy.json', {}) or {}).get('project_providers', {}).get(pid, []),
                'review_states': sorted(api.REVIEW_STATES), 'migrations': p.get('image_model_migrations', []),
                'generation_started': False, 'render_started': False}

    @router.post('/videos/{pid}/model-migration')
    async def migrate(pid: str, body: MigrationRequest):
        request = body.model_dump()
        signature = api._hash(request)
        async with _lock, project_lock(pid):
            p = api._project(pid, True)
            for previous in p.get('image_model_migrations', []):
                if previous['idempotency_key'] == body.idempotency_key:
                    if previous['request_sha256'] != signature:
                        raise HTTPException(409, 'Migration key already used with different input')
                    return dict(previous, reused=True)
            ensure_idle(p)
            if api._hash(p.get('model_snapshot') or {}) != body.expected_snapshot_sha256:
                raise HTTPException(409, 'Model snapshot changed; read migration options again')
            if body.image_provider not in ('cli_proxy', 'google_flow'):
                raise HTTPException(422, 'Unsupported image provider')
            check_provider(p, body.image_provider)
            # The shared catalog masks image capability under the global Flow
            # policy. After project policy validation, read the real proxy catalog
            # without changing that global mask for other projects.
            catalog = await (api._proxy_catalog() if body.image_provider == 'cli_proxy' else api._catalog())
            if not catalog.get('available'):
                raise HTTPException(503, 'The requested provider catalog is unavailable')
            entry = next((m for m in catalog['models'] if m['id'] == body.image_model
                          and m.get('provider', 'cli_proxy') == body.image_provider), None)
            if not entry or (entry.get('capabilities') or {}).get('image') is False:
                raise HTTPException(422, 'Choose an image model in the current provider catalog')
            if not entry.get('generation_tested') and not body.acknowledge_untested_model:
                raise HTTPException(409, 'Model generation is untested; explicitly acknowledge a one-shot test')
            # Catalog lookup yielded: reject any concurrent project changes before copying.
            current = api._project(pid, True)
            ensure_idle(current)
            if api._hash(current) != api._hash(p):
                raise HTTPException(409, 'Project changed during preflight; retry after reading it')
            before_hash = api._hash(p)
            mid = uuid.uuid4().hex
            backup = make_backup(p, mid)
            if api._hash(api._project(pid, True)) != before_hash:
                raise HTTPException(409, 'Project changed during backup; migration was not applied')
            old = copy.deepcopy(p.get('model_snapshot') or {})
            new = copy.deepcopy(old)
            new.update(image_model=body.image_model, image_provider=body.image_provider,
                       transport=body.image_provider, selected_at=now(),
                       capability_verified=False, generation_tested=False)
            new.setdefault('capabilities', {})['image'] = copy.deepcopy(entry.get('capabilities') or {})
            p['model_snapshot'] = new
            p['settings']['visuals'].update(image_model=body.image_model, image_provider=body.image_provider)
            # Existing media/provenance are retained verbatim. Reviews become stale
            # naturally because their evidence contains the old model snapshot hash.
            for s in p.get('scenes', []):
                s['workspace_regeneration_required'] = True
            if p.get('render'):
                p.setdefault('render_history', []).append(copy.deepcopy(p['render']))
            p['render'] = None
            p['prompts_approved'] = False
            p['steps']['visuals'].update(state='idle', msg='Model migrated; existing shots retained pending regeneration')
            p['steps']['render'].update(state='idle', msg='Model migrated; render requires regenerated and reviewed shots')
            receipt = {'id': mid, 'project_id': pid, 'idempotency_key': body.idempotency_key,
                       'request_sha256': signature, 'before_project_sha256': before_hash,
                       'previous_model_snapshot': old, 'model_snapshot': new, 'backup': backup,
                       'backup_url': f'/api/forge/v1/videos/{pid}/model-migrations/{mid}/backup',
                       'member': current_owner(), 'created': now(), 'state': 'migrated',
                       'generation_started': False, 'render_started': False}
            p.setdefault('image_model_migrations', []).append(receipt)
            write_json(backup_dir(pid, mid) / 'receipt.json', receipt)
            store.save_project(p)
            return dict(receipt, reused=False)

    @router.get('/videos/{pid}/model-migrations/{mid}/backup')
    async def download_backup(pid: str, mid: str):
        p = api._project(pid)
        record = next((m for m in p.get('image_model_migrations', []) if m['id'] == mid), None)
        if not record:
            raise HTTPException(404, 'Migration not found')
        path = backup_dir(pid, mid) / 'backup.zip'
        if not path.is_file() or digest(path) != record['backup']['sha256']:
            raise HTTPException(409, 'Backup missing or changed')
        return FileResponse(path, filename=f'{pid}-before-migration.zip', headers={'Cache-Control': 'private, no-store'})
