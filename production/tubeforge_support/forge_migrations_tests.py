"""Migration contract tests; no paid requests or media processing."""
import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from app import config, store

if Path(__file__).parent.name == 'tests':
    from test_forge_api import client, create, workspace
    from app import forge_migrations as migrations
else:
    from .forge_api_tests import client, create, workspace
    from . import forge_migrations as migrations


BASE = '/api/forge/v1/videos/'


def fixture_project(client):
    pid = create(client).json()['id']
    p = store.get_project(pid)
    root = store.project_dir(pid)
    (root / 'images').mkdir(exist_ok=True)
    (root / 'images/one.jpg').write_bytes(b'original-image-fixture')
    p['scenes'] = [{'id': 1, 'image': 'images/one.jpg', 'references': [],
                    'generation_receipt': {'model': 'old-model', 'transport': 'old-provider'},
                    'human_review': {'state': 'verified', 'evidence': 'old-evidence'}}]
    p['voiceover'] = {'file': 'voice.wav', 'duration': 12}
    (root / 'voice.wav').write_bytes(b'original-audio-fixture')
    store.save_project(p)
    return pid


def body(client, pid, **changes):
    info = client.get(BASE + pid + '/model-migration').json()
    return dict(idempotency_key='test-migration', expected_snapshot_sha256=info['snapshot_sha256'],
                image_model='future-image-fixture', image_provider='cli_proxy',
                acknowledge_untested_model=True, **changes)


def test_backup_replay_and_preserved_provenance(client):
    pid = fixture_project(client)
    original = copy.deepcopy(store.get_project(pid))
    payload = body(client, pid)
    response = client.post(BASE + pid + '/model-migration', json=payload)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt['backup']['selected_images'] == 1
    assert receipt['generation_started'] is False and receipt['render_started'] is False
    p = store.get_project(pid)
    assert p['scenes'][0]['generation_receipt'] == original['scenes'][0]['generation_receipt']
    assert p['scenes'][0]['image'] == original['scenes'][0]['image']
    assert p['scenes'][0]['workspace_regeneration_required'] is True
    assert p['voiceover'] == original['voiceover']
    assert p['model_snapshot']['image_model'] == p['settings']['visuals']['image_model'] == 'future-image-fixture'
    assert p['model_snapshot']['generation_tested'] is False
    replay = client.post(BASE + pid + '/model-migration', json=payload)
    assert replay.status_code == 200 and replay.json()['reused']
    assert len(store.get_project(pid)['image_model_migrations']) == 1
    downloaded = client.get(receipt['backup_url'])
    assert hashlib.sha256(downloaded.content).hexdigest() == receipt['backup']['sha256']
    with zipfile.ZipFile(migrations.backup_dir(pid, receipt['id']) / 'backup.zip') as z:
        assert z.read('project/images/one.jpg') == b'original-image-fixture'
        assert json.loads(z.read('project-before.json'))['model_snapshot'] == original['model_snapshot']
    payload['image_model'] = 'fixture-image'
    assert client.post(BASE + pid + '/model-migration', json=payload).status_code == 409


def test_provider_exception_is_project_scoped(client):
    pid = fixture_project(client)
    (config.DATA / 'workspace-visual-policy.json').write_text(json.dumps({'image_provider': 'google_flow'}))
    payload = body(client, pid)
    assert client.post(BASE + pid + '/model-migration', json=payload).status_code == 422
    (config.DATA / 'workspace-model-migration-policy.json').write_text(json.dumps({'project_providers': {pid: ['cli_proxy']}}))
    assert client.post(BASE + pid + '/model-migration', json=payload).status_code == 200
    migrations.check_provider(store.get_project(pid), 'cli_proxy')
    with pytest.raises(HTTPException):
        migrations.check_provider({'id': 'another-project'}, 'cli_proxy')
    assert json.loads((config.DATA / 'workspace-visual-policy.json').read_text())['image_provider'] == 'google_flow'


def test_stale_hash_busy_unavailable_and_untested_guards(client):
    pid = fixture_project(client)
    payload = body(client, pid)
    assert client.post(BASE+pid+'/model-migration', json=payload | {'expected_snapshot_sha256': '0'*64}).status_code == 409
    assert client.post(BASE+pid+'/model-migration', json=payload | {'image_model': 'not-in-catalog'}).status_code == 422
    assert client.post(BASE+pid+'/model-migration', json=payload | {'acknowledge_untested_model': False}).status_code == 409
    p = store.get_project(pid); p['workspace_external_execution'] = {'state': 'running'}; store.save_project(p)
    assert client.post(BASE+pid+'/model-migration', json=payload).status_code == 409
    assert not store.get_project(pid).get('image_model_migrations')


def test_failed_backup_leaves_project_unchanged(client, monkeypatch):
    pid = fixture_project(client)
    payload = body(client, pid)
    before = copy.deepcopy(store.get_project(pid))
    def fail(*args):
        raise HTTPException(507, 'Backup unavailable')
    monkeypatch.setattr(migrations, 'make_backup', fail)
    assert client.post(BASE+pid+'/model-migration', json=payload).status_code == 507
    assert store.get_project(pid) == before


def test_missing_selected_image_and_traversal_are_rejected(client):
    pid = fixture_project(client)
    payload = body(client, pid)
    p = store.get_project(pid); p['scenes'][0]['image'] = '../outside.jpg'; store.save_project(p)
    assert client.post(BASE+pid+'/model-migration', json=payload).status_code == 409
    assert not store.get_project(pid).get('image_model_migrations')


def test_other_worker_migration_lock_is_respected(client):
    import fcntl
    pid = fixture_project(client)
    payload = body(client, pid)
    root = config.DATA / 'model-migrations' / 'locks'; root.mkdir(parents=True)
    with (root / (pid + '.lock')).open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert client.post(BASE+pid+'/model-migration', json=payload).status_code == 409
    assert not store.get_project(pid).get('image_model_migrations')
