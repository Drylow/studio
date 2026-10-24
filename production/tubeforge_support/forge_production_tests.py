"""Production API contracts. All provider and controller calls are mocked."""
import copy
from pathlib import Path
import pytest
from app import store
if Path(__file__).parent.name == 'tests':
    from test_forge_api import client, create, workspace
    from app import forge_production as prod
else:
    from .forge_api_tests import client, create, workspace
    from . import forge_production as prod

BASE = '/api/forge/v1/videos/'


def project(client):
    pid = create(client).json()['id']
    p = store.get_project(pid)
    p['scenes'] = [{'id': i, 'start': i-1, 'end': i, 'prompt': 'Original ' + str(i),
                    'image': f'images/{i}.jpg', 'references': [{'path': 'ref.png'}],
                    'human_review': {'state': 'verified', 'evidence': 'old'},
                    'generation_receipt': {'sha256': 'original'}} for i in range(1, 127)]
    p['render'] = {'file': 'render/old.mp4'}
    store.save_project(p)
    return pid


def patch(pid, edits):
    return {'idempotency_key': 'patch-fixture', 'scenes': [
        {'id': i, 'prompt': text, 'expected_prompt_sha256': prod.prompt_hash('Original ' + str(i))}
        for i, text in edits]}


def test_compact_pagination(client):
    pid = project(client)
    seen = []
    for offset in range(0, 126, 10):
        r = client.get(BASE + pid + f'?fields=id,start,end,prompt&offset={offset}&limit=10')
        assert r.status_code == 200
        d = r.json()
        seen.extend(s['id'] for s in d['scenes'])
        assert set(d['scenes'][0]) == {'id', 'start', 'end', 'prompt', 'prompt_sha256'}
        assert len(r.content) < 5000
    assert seen == list(range(1, 127))
    assert client.get(BASE + pid + '?fields=script,owner_id').status_code == 422
    assert client.get(BASE + pid + '/scenes/prompts?limit=26').status_code == 422


def test_partial_atomic_edit_preserves_other_data_and_replays(client):
    pid = project(client)
    old = copy.deepcopy(store.get_project(pid))
    body = patch(pid, [(1, 'New prompt'), (22, 'White backdrop')])
    r = client.patch(BASE + pid + '/scenes/prompts', json=body)
    assert r.status_code == 200, r.text
    p = store.get_project(pid)
    assert p['scenes'][1] == old['scenes'][1]
    assert p['voiceover'] == old['voiceover'] and p['script'] == old['script']
    for i in (0, 21):
        assert p['scenes'][i]['generation_receipt'] == old['scenes'][i]['generation_receipt']
        assert p['scenes'][i]['image'] == old['scenes'][i]['image']
        assert p['scenes'][i]['workspace_regeneration_required'] is True
        assert p['scenes'][i]['references'] == old['scenes'][i]['references']
    assert p['render'] is None and p['render_history'][-1] == old['render']
    assert client.patch(BASE + pid + '/scenes/prompts', json=body).json()['reused']
    body['scenes'][0]['prompt'] = 'Different'
    assert client.patch(BASE + pid + '/scenes/prompts', json=body).status_code == 409


@pytest.mark.parametrize('change,status', [('hash',409),('missing',404),('duplicate',422),('extra',422)])
def test_invalid_edit_is_all_or_nothing(client, change, status):
    pid = project(client)
    old = copy.deepcopy(store.get_project(pid))
    body = patch(pid, [(1, 'New'), (22, 'White')])
    if change == 'hash': body['scenes'][1]['expected_prompt_sha256'] = '0'*64
    if change == 'missing': body['scenes'][1]['id'] = 999
    if change == 'duplicate': body['scenes'][1]['id'] = 1
    if change == 'extra': body['scenes'][0]['image'] = 'tampered.jpg'
    assert client.patch(BASE + pid + '/scenes/prompts', json=body).status_code == status
    assert store.get_project(pid) == old


def test_runpod_rejects_unreviewed_and_missing_credentials(client):
    pid = project(client)
    d = client.get(BASE + pid + '/render/runpod').json()
    assert not d['ready'] and d['local_fallback'] is False
    body = {'idempotency_key':'render-1','expected_input_sha256': d['input_sha256']}
    assert client.post(BASE + pid + '/render/runpod', json=body).status_code == 409
    assert not store.get_project(pid).get('forge_runpod_jobs')


def test_preflight_validates_current_inputs_not_sticky_prior_error(client, monkeypatch):
    pid = project(client)
    p = store.get_project(pid);p['error'] = 'Old generation attempt'
    monkeypatch.setattr(prod,'runpod_configured',lambda: True)
    def full(current):
        assert current['error'] is None and current['render'] is None
        return {'technical_issues': [], 'scenes': [{'id':2,'human_review':{'state':'verified'}}],
                'human_reviews':{'voiceover':{'state':'verified'}}}
    monkeypatch.setattr(prod.api,'_full',full)
    assert prod.preflight(p)['ready']
    assert p['error'] == 'Old generation attempt' and p['render']


def test_runpod_launch_once_lock_edit_and_hide_secrets(client, monkeypatch):
    pid = project(client)
    calls = []
    monkeypatch.setattr(prod, 'preflight', lambda p: {'ready':True,'input_sha256':'a'*64})
    monkeypatch.setattr(prod, 'launch_controller', lambda root: calls.append(root) or 123)
    body = {'idempotency_key':'render-1','expected_input_sha256':'a'*64}
    r = client.post(BASE + pid + '/render/runpod', json=body)
    assert r.status_code == 202, r.text
    assert len(calls) == 1
    assert client.post(BASE + pid + '/render/runpod', json=body).json()['reused']
    assert len(calls) == 1
    assert client.patch(BASE + pid + '/scenes/prompts', json=patch(pid,[(1,'New')])).status_code == 409
    assert client.post(BASE + pid + '/render/runpod', json=dict(body,idempotency_key='different')).status_code == 409
    assert client.post(BASE + pid + '/render/runpod', json=dict(body,transition_seconds=.5)).status_code == 409
    from app.util import write_json
    write_json(calls[0]/'state.json', {'state':'running','worker_token':'secret','Authorization':'private'})
    status = client.get(r.json()['status_url'])
    assert 'secret' not in status.text and 'private' not in status.text


def test_launch_failure_keeps_receipt_and_allows_no_silent_replay(client, monkeypatch):
    pid = project(client)
    monkeypatch.setattr(prod, 'preflight', lambda p: {'ready':True,'input_sha256':'a'*64})
    def fail(root): raise OSError('fixture')
    monkeypatch.setattr(prod, 'launch_controller', fail)
    body = {'idempotency_key':'render-1','expected_input_sha256':'a'*64}
    assert client.post(BASE + pid + '/render/runpod', json=body).status_code == 503
    r = client.post(BASE + pid + '/render/runpod', json=body)
    assert r.status_code == 202 and r.json()['state'] == 'failed'


@pytest.mark.parametrize('outcome', ['success', 'provider_failure', 'cleanup_failure', 'inputs_changed'])
def test_controller_always_cleans_its_pod_and_only_attaches_verified_transfer(client, monkeypatch, outcome):
    import json
    from app import forge_runpod as controller
    pid = project(client)
    calls = []
    monkeypatch.setattr(prod, 'preflight', lambda p: {'ready':True,'input_sha256':prod.api._hash(prod.render_inputs(p))})
    monkeypatch.setattr(prod, 'launch_controller', lambda root: calls.append(root) or 123)
    p = store.get_project(pid)
    r = client.post(BASE + pid + '/render/runpod', json={'idempotency_key':'render-1',
                     'expected_input_sha256': prod.api._hash(prod.render_inputs(p))})
    assert r.status_code == 202
    cleaned = []
    def execute(root, req, state):
        state['pod_id'] = 'owned-pod'
        if outcome == 'provider_failure': raise RuntimeError('fixture provider failure')
        if outcome == 'inputs_changed':
            p = store.get_project(pid); p['scenes'][0]['prompt'] = 'Changed';store.save_project(p)
        video = root/'fixture.mp4'; video.write_bytes(b'fixture transport bytes')
        return video, {'sha256':controller.sha(video),'bytes':video.stat().st_size,'duration':8,'width':1920,'height':1080}
    def cleanup(state, root):
        cleaned.append(state['pod_id'])
        if outcome == 'cleanup_failure': raise RuntimeError('fixture cleanup failure')
        state['pod_terminated'] = True
    monkeypatch.setattr(controller,'execute',execute)
    monkeypatch.setattr(controller,'cleanup',cleanup)
    monkeypatch.setattr(controller.signal,'signal',lambda *a: None)
    controller.main(calls[0])
    state = json.loads((calls[0]/'state.json').read_text())
    assert cleaned == ['owned-pod']
    p = store.get_project(pid)
    if outcome == 'success':
        assert state['state'] == 'complete'
        assert p['render']['backend'] == 'runpod'
        assert controller.sha(store.project_dir(pid)/p['render']['file']) == state['video_sha256']
        assert p['human_reviews'].get('render',{}).get('state') != 'verified'
    else:
        assert state['state'] == ('cleanup_required' if outcome == 'cleanup_failure' else 'failed')
        assert p['render'] == {'file':'render/old.mp4'}
