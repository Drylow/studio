"""Durable VPS controller. Only the disposable RunPod executes media code."""
import base64
import fcntl
import hashlib
import json
import os
import secrets
import shutil
import signal
import sys
import tarfile
import time
from pathlib import Path

import requests
from app import config, store
from . import workspace_api as api
from .forge_production import render_inputs

API = 'https://rest.runpod.io/v1'


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(p, value):
    p = Path(p)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(p)


def safe(root, rel):
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('Path outside job')
    return p


def headers():
    key = os.environ.get('RUNPOD_API_KEY') or (config.DATA / 'forge-runpod/api-key').read_text().strip()
    if not key:
        raise RuntimeError('RunPod key unavailable')
    return {'Authorization': 'Bearer ' + key}


def cleanup(state, root):
    auth = headers()
    pod = state.get('pod_id')
    if not pod and state.get('pod_name'):
        r = requests.get(API + '/pods', headers=auth, timeout=30)
        r.raise_for_status()
        rows = r.json()
        rows = rows.get('pods', rows.get('data', [])) if isinstance(rows, dict) else rows
        matches = [p for p in rows if p.get('name') == state['pod_name']]
        if len(matches) > 1:
            raise RuntimeError('Multiple pods need reconciliation')
        if matches:
            pod = matches[0]['id']
            state['pod_id'] = pod
    if not pod:
        state['pod_terminated'] = True
        write(root / 'state.json', state)
        return
    state['pod_terminated'] = False
    for _ in range(3):
        try:
            requests.delete(API + '/pods/' + pod, headers=auth, timeout=30)
            r = requests.get(API + '/pods/' + pod, headers=auth, timeout=30)
            if r.status_code == 404:
                state['pod_terminated'] = True
                break
        except requests.RequestException:
            pass
        time.sleep(3)
    write(root / 'state.json', state)
    if not state['pod_terminated']:
        raise RuntimeError('Pod cleanup needs reconciliation')


def bundle(root, req):
    pid = req['project_id']
    project = store.get_project(pid)
    if api._hash(render_inputs(project)) != req['input_sha256']:
        raise ValueError('Inputs changed after render submission')
    src = store.project_dir(pid).resolve()
    stage = root / 'input'
    stage.mkdir()
    (stage / 'project').mkdir()
    (stage / 'run').mkdir()
    inputs = req['inputs']
    files = {inputs['voiceover']['file']: inputs['voice_sha256']}
    files.update({s['image']: s['sha256'] for s in inputs['scenes']})
    for rel, digest in files.items():
        f = safe(src, rel)
        if not digest or sha(f) != digest:
            raise ValueError('Input bytes changed')
        dst = safe(stage / 'project', rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        if sha(dst) != digest:
            raise ValueError('Input copy verification failed')
    job = dict(req['options'], out='project/render/final.mp4',
               voice='project/' + inputs['voiceover']['file'], duration=inputs['voiceover']['duration'],
               width=1920, height=1080, fps=24, threads=16, crf=18,
               scenes=[dict(image='project/' + s['image'], start=s['start'], end=s['end']) for s in inputs['scenes']])
    write(stage / 'job.json', job)
    renderer = Path(__file__).with_name('slideshow_render.py').read_text()
    renderer = renderer.replace('min(4, int(job.get', 'min(32, int(job.get')
    (stage / 'slideshow_render.py').write_text(renderer)
    # This script is shipped to the pod; it is never imported/executed by the VPS.
    worker = '''import json,os,subprocess
from pathlib import Path
assert os.environ.get('RUNPOD_RENDER_HOST')=='1'
from slideshow_render import render
Path('run').mkdir(exist_ok=True)
r=render(json.loads(Path('job.json').read_text()))
probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',r['file']],check=True,capture_output=True,text=True).stdout)
assert any(s['codec_type']=='audio' for s in probe['streams']), 'Missing audio'
r.update(file='render/final.mp4',host='RunPod',sheets=[])
Path('run/render-report.json').write_text(json.dumps(r))
'''
    (stage / 'render_worker.py').write_text(worker)
    write(stage / 'bundle-hashes.json', {p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob('*') if p.is_file()})
    archive = root / 'input.tar'
    with tarfile.open(archive, 'w') as t:
        for p in stage.rglob('*'):
            if p.is_file():
                t.add(p, arcname=p.relative_to(stage).as_posix())
    if archive.stat().st_size > 2 * 1024**3:
        raise ValueError('Input bundle exceeds worker limit')
    return archive


def execute(root, req, state):
    archive = bundle(root, req)
    auth = headers()
    token = secrets.token_urlsafe(32)
    h = {'X-Worker-Token': token}
    code = Path(__file__).with_name('forge_runpod_worker.py').read_bytes()
    command = "apt-get update -qq && apt-get install -y -qq --no-install-recommends ffmpeg >/tmp/install.log 2>&1 && pip install --quiet --no-cache-dir pillow numpy && printf '%s' \"$WORKER_CODE\" | base64 -d >/worker.py && python /worker.py"
    state.update(state='running', phase='creating_pod', pod_name='forge-api-' + req['job_id'], started=time.time())
    write(root / 'state.json', state)
    body = {'name': state['pod_name'], 'imageName': 'python:3.12-slim-bookworm', 'computeType': 'CPU',
            'cpuFlavorIds': ['cpu5c', 'cpu3c'], 'vcpuCount': 32, 'containerDiskInGb': 35,
            'ports': ['8000/http'], 'env': {'WORKER_TOKEN': token, 'WORKER_CODE': base64.b64encode(code).decode()},
            'dockerStartCmd': ['bash', '-c', command]}
    r = requests.post(API + '/pods', headers=auth, json=body, timeout=60)
    if not r.ok:
        raise RuntimeError('RunPod create HTTP ' + str(r.status_code))
    state.update(pod_id=r.json()['id'], phase='booting')
    write(root / 'state.json', state)
    url = 'https://' + state['pod_id'] + '-8000.proxy.runpod.net'
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            r = requests.get(url + '/status', headers=h, timeout=15)
            if r.ok and r.json().get('state') == 'ready':
                break
        except requests.RequestException:
            pass
        time.sleep(10)
    else:
        raise TimeoutError('RunPod bootstrap timeout')
    with archive.open('rb') as stream:
        r = requests.put(url + '/bundle', headers=h | {'X-SHA256': sha(archive)}, data=stream, timeout=300)
        r.raise_for_status()
    requests.post(url + '/start', headers=h, timeout=30).raise_for_status()
    state['phase'] = 'rendering'
    write(root / 'state.json', state)
    deadline = time.monotonic() + 2400
    while time.monotonic() < deadline:
        r = requests.get(url + '/status', headers=h, timeout=30)
        r.raise_for_status()
        result = r.json()
        if result['state'] == 'complete':
            break
        if result['state'] == 'failed':
            log = requests.get(url + '/log', headers=h, timeout=30)
            if log.ok:
                (root / 'worker.log').write_bytes(log.content)
            raise RuntimeError('RunPod media worker failed; inspect private log')
        time.sleep(10)
    else:
        raise TimeoutError('RunPod render timeout')
    state['phase'] = 'downloading'
    write(root / 'state.json', state)
    output = root / 'result.tar'
    with requests.get(url + '/result', headers=h, stream=True, timeout=300) as r:
        r.raise_for_status()
        with output.open('wb') as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)
    if output.stat().st_size != result['bytes'] or sha(output) != result['sha256']:
        raise ValueError('Result transfer hash mismatch')
    extracted = root / 'result'
    with tarfile.open(output) as t:
        for m in t.getmembers():
            if not m.isfile() or Path(m.name).is_absolute() or '..' in Path(m.name).parts:
                raise ValueError('Unsafe result archive')
        t.extractall(extracted, filter='data')
    report = json.loads((extracted / 'run/render-report.json').read_text())
    video = safe(extracted / 'project', report['file'])
    if report['host'] != 'RunPod' or sha(video) != report['sha256'] or video.stat().st_size != report['bytes']:
        raise ValueError('Invalid RunPod result')
    write(root / 'report.json', report)
    return video, report


def main(root):
    if sys.platform != 'linux':
        raise RuntimeError('Controller must run on VPS')
    allowed = (config.DATA / 'forge-runpod/jobs').resolve()
    root = Path(root).resolve()
    if not root.is_relative_to(allowed):
        raise ValueError('Invalid job directory')
    req = json.loads((root / 'request.json').read_text())
    state = json.loads((root / 'state.json').read_text())
    if state['state'] != 'queued':
        raise RuntimeError('Existing job requires reconciliation, not blind replay')
    state['controller_pid'] = os.getpid()
    write(root / 'state.json', state)
    def interrupted(*_):
        raise RuntimeError('Controller interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    with (allowed.parent / 'render.lock').open('a') as lock:
        # One disposable pod at a time for this API; queued jobs survive HTTP reconnects.
        fcntl.flock(lock, fcntl.LOCK_EX)
        video = report = None
        try:
            video, report = execute(root, req, state)
        except Exception as e:
            state.update(state='failed', error=type(e).__name__ + ': ' + str(e)[:240])
        finally:
            try:
                cleanup(state, root)
            except Exception:
                state.update(state='cleanup_required', error='Reconcile the RunPod before any retry')
            state['finished'] = time.time()
            try:
                p = store.get_project(req['project_id'])
                if p and (p.get('workspace_external_execution') or {}).get('job_id') == req['job_id']:
                    if report and state.get('pod_terminated') and api._hash(render_inputs(p)) == req['input_sha256']:
                        rel = 'render/runpod-' + req['job_id'] + '.mp4'
                        dest = store.project_dir(p['id']) / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(video, dest)
                        if sha(dest) != report['sha256']:
                            raise ValueError('Final copy hash mismatch')
                        if p.get('render'):
                            p.setdefault('render_history', []).append(p['render'])
                        p['render'] = {'file': rel, 'duration': report['duration'], 'sha256': report['sha256'],
                                       'bytes': report['bytes'], 'backend': 'runpod', 'qa_pending': False,
                                       'width': report['width'], 'height': report['height'], 'job_id': req['job_id']}
                        if p.get('error'):
                            p.setdefault('resolved_errors', []).append({'error': p['error'], 'resolved_by': req['job_id']})
                            p['error'] = None
                        p.setdefault('human_reviews', {}).pop('render', None)
                        state.update(state='complete', phase='complete', video_sha256=report['sha256'],
                                     bytes=report['bytes'], duration=report['duration'],
                                     width=report['width'], height=report['height'])
                    elif report and state.get('state') != 'cleanup_required':
                        state.update(state='failed', error='Inputs changed; render retained privately, not published')
                    p['workspace_external_execution'].update(state=state['state'])
                    p['steps']['render'].update(state='done' if state['state'] == 'complete' else 'error',
                                               msg='RunPod render ready for visual review' if state['state'] == 'complete' else state.get('error', 'RunPod failed'))
                    store.save_project(p)
            except Exception:
                state.update(state='failed', error='Result attachment failed; reconcile job before retry')
                p = store.get_project(req['project_id'])
                if p and (p.get('workspace_external_execution') or {}).get('job_id') == req['job_id']:
                    p['workspace_external_execution']['state'] = 'failed'
                    p['steps']['render'].update(state='error', msg=state['error'])
                    store.save_project(p)
            write(root / 'state.json', state)
            # Inputs/results remain private for failure diagnosis. No source deletion.


if __name__ == '__main__':
    main(sys.argv[1])
