"""Compact prompt edits and durable RunPod jobs. Never renders on the API host."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from app import config, store
from app.util import now, read_json, write_json
from . import workspace_api as api
from .forge_migrations import project_lock, ensure_idle


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PromptEdit(Strict):
    id: int = Field(gt=0, strict=True)
    prompt: str = Field(min_length=1, max_length=30000)
    expected_prompt_sha256: str = Field(pattern='^[a-f0-9]{64}$')


class PromptPatch(Strict):
    idempotency_key: str = Field(min_length=1, max_length=100, pattern='^[A-Za-z0-9_-]+$')
    scenes: list[PromptEdit] = Field(min_length=1, max_length=25)
    expected_prompts_sha256: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')


def prompt_hash(text):
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def prompt_view(p, fields='id,start,end,prompt', offset=0, limit=10):
    selected = fields.split(',')
    if not selected or any(k not in ('id', 'start', 'end', 'prompt', 'text', 'prompt_sha256') for k in selected):
        raise HTTPException(422, 'Choose id,start,end,prompt,text,prompt_sha256')
    scenes = p.get('scenes', [])
    rows = [dict(s, prompt_sha256=prompt_hash(s.get('prompt'))) for s in scenes]
    return {'project_id': p['id'], 'total': len(rows), 'offset': offset,
            'next_offset': offset + limit if offset + limit < len(rows) else None,
            'prompts_sha256': api._hash([{'id': s['id'], 'prompt': s.get('prompt')} for s in scenes]),
            'scenes': [{k: row.get(k) for k in dict.fromkeys(['id', *selected, 'prompt_sha256'])}
                       for row in rows[offset:offset+limit]]}


def job_root(pid, jid):
    api._identifier(pid)
    if len(jid) != 32 or any(c not in '0123456789abcdef' for c in jid):
        raise HTTPException(422, 'Invalid job ID')
    return config.DATA / 'forge-runpod' / 'jobs' / pid / jid


def runpod_configured():
    return bool(os.environ.get('RUNPOD_API_KEY')) or (config.DATA / 'forge-runpod' / 'api-key').is_file()


def render_inputs(p):
    root = store.project_dir(p['id'])
    return {'project_id': p['id'], 'script_sha256': api._hash(p.get('script')),
            'model_snapshot': p.get('model_snapshot'), 'voiceover': p.get('voiceover'),
            'voice_sha256': api._file_digest(root, (p.get('voiceover') or {}).get('file')),
            'scenes': [{'id': s['id'], 'start': s.get('start'), 'end': s.get('end'),
                        'image': s.get('image'), 'sha256': api._file_digest(root, s.get('image')),
                        'authoring': api._hash({k: v for k, v in s.items() if k not in ('human_review', 'status', 'error')}),
                        'regeneration_required': bool(s.get('workspace_regeneration_required'))}
                       for s in p.get('scenes', [])]}


def preflight(p):
    # A failed old attempt/output is not a render input. Validate current media,
    # fresh reviews, timings and pending regeneration instead of a sticky error string.
    inputs_only = copy.deepcopy(p)
    inputs_only.update(error=None, render=None)
    full = api._full(inputs_only)
    issues = list(full['technical_issues'])
    stale = [s['id'] for s in full['scenes'] if s['human_review']['state'] != 'verified'
             or s.get('workspace_regeneration_required')]
    if stale:
        issues.append('Regenerate and review every selected image')
    if full['human_reviews']['voiceover']['state'] != 'verified':
        issues.append('Review the current voiceover')
    if not runpod_configured():
        issues.append('RunPod credential is not configured on the server')
    return {'project_id': p['id'], 'backend': 'runpod', 'controller': 'VPS', 'local_fallback': False,
            'ready': not issues, 'blockers': issues, 'scene_ids_needing_review': stale,
            'input_sha256': api._hash(render_inputs(p)), 'configured': runpod_configured(),
            'previous_error': p.get('error')}


class RenderRequest(Strict):
    idempotency_key: str = Field(min_length=1, max_length=100, pattern='^[A-Za-z0-9_-]+$')
    expected_input_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    transition_seconds: float = Field(default=.25, ge=0, le=1, allow_inf_nan=False)
    intro_fade_seconds: float = Field(default=1, ge=0, le=5, allow_inf_nan=False)
    outro_fade_seconds: float = Field(default=5, ge=0, le=10, allow_inf_nan=False)


def launch_controller(root):
    with (root / 'controller.log').open('ab') as log:
        return subprocess.Popen([sys.executable, '-m', 'app.forge_runpod', str(root.resolve())],
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True).pid


def job_status(p, jid):
    record = next((j for j in p.get('forge_runpod_jobs', []) if j['id'] == jid), None)
    if not record:
        raise HTTPException(404, 'Render job not found')
    state = read_json(job_root(p['id'], jid) / 'state.json', {})
    # Explicit whitelist: worker credentials/private logs never leave the server.
    allowed = ('state', 'phase', 'started', 'finished', 'error', 'pod_id', 'pod_terminated',
               'video_sha256', 'bytes', 'duration', 'width', 'height', 'controller_pid')
    return {'job_id': jid, 'project_id': p['id'], 'backend': 'runpod', 'local_fallback': False,
            **{k: state[k] for k in allowed if k in state},
            'status_url': f'/api/forge/v1/videos/{p["id"]}/render/runpod/{jid}',
            'download_url': f'/api/forge/v1/videos/{p["id"]}/download?kind=video'
            if state.get('state') == 'complete' else None}


def install(router):
    @router.get('/videos/{pid}/scenes/prompts')
    async def prompts(pid: str, fields: str = 'id,start,end,prompt', offset: int = Query(0, ge=0),
                      limit: int = Query(10, ge=1, le=25)):
        return prompt_view(api._project(pid), fields, offset, limit)

    @router.patch('/videos/{pid}/scenes/prompts')
    async def patch_prompts(pid: str, body: PromptPatch):
        async with project_lock(pid):
            p = api._project(pid)
            signature = api._hash(body.model_dump())
            for old in p.get('forge_prompt_edits', []):
                if old['idempotency_key'] == body.idempotency_key:
                    if signature != old['request_sha256']:
                        raise HTTPException(409, 'Prompt edit key reused with different input')
                    return dict(old, reused=True)
            p = api._project(pid, True)
            ensure_idle(p)
            if body.expected_prompts_sha256 and body.expected_prompts_sha256 != prompt_view(p)['prompts_sha256']:
                raise HTTPException(409, 'Prompt list changed; read it again')
            rows = {s['id']: s for s in p.get('scenes', [])}
            ids = [s.id for s in body.scenes]
            if len(set(ids)) != len(ids):
                raise HTTPException(422, 'Duplicate scene ID')
            changed = []
            for edit in body.scenes:
                if edit.id not in rows:
                    raise HTTPException(404, f'Scene {edit.id} not found')
                if prompt_hash(rows[edit.id].get('prompt')) != edit.expected_prompt_sha256:
                    raise HTTPException(409, f'Scene {edit.id} prompt changed; read it again')
                if not edit.prompt.strip() or '\x00' in edit.prompt:
                    raise HTTPException(422, 'Prompt must be nonempty text without null bytes')
                if rows[edit.id].get('prompt') != edit.prompt:
                    changed.append(edit.id)
            eid = uuid.uuid4().hex
            backup = config.DATA / 'prompt-edits' / pid / eid
            backup.mkdir(parents=True, exist_ok=False)
            write_json(backup / 'project-before.json', p)
            for edit in body.scenes:
                if edit.id in changed:
                    s = rows[edit.id]
                    s.update(prompt=edit.prompt, prompt_author='codex', workspace_regeneration_required=True)
                    # Preserve images, receipts and reviews: changed evidence makes reviews stale.
            if changed:
                if p.get('render'):
                    p.setdefault('render_history', []).append(copy.deepcopy(p['render']))
                p.update(render=None, prompts_approved=False)
                p['steps']['visuals'].update(state='idle', msg='Prompts edited; selected images need regeneration')
                p['steps']['render'].update(state='idle', msg='Awaiting regenerated and reviewed images')
            result = {'edit_id': eid, 'idempotency_key': body.idempotency_key, 'request_sha256': signature,
                      'changed_scene_ids': changed, 'created': now(), 'generation_started': False,
                      'prompts_sha256': prompt_view(p)['prompts_sha256'],
                      'scenes': [{'id': i, 'prompt_sha256': prompt_hash(rows[i].get('prompt'))} for i in ids]}
            p.setdefault('forge_prompt_edits', []).append(result)
            store.save_project(p)
            return dict(result, reused=False)

    @router.get('/videos/{pid}/render/runpod')
    async def render_preflight(pid: str):
        return preflight(api._project(pid))

    @router.get('/videos/{pid}/render/runpod/{jid}')
    async def render_status(pid: str, jid: str):
        return job_status(api._project(pid), jid)

    @router.post('/videos/{pid}/render/runpod/{jid}/reconcile')
    async def reconcile(pid: str, jid: str):
        async with project_lock(pid):
            p = api._project(pid)
            job_status(p, jid)  # Ownership/project membership and identifier validation.
            root = job_root(pid, jid)
            state = read_json(root / 'state.json', {})
            if state.get('state') == 'complete':
                return job_status(p, jid)
            if time.time() - state.get('created', 0) < 60:
                raise HTTPException(409, 'Controller is starting; poll status before reconciliation')
            process = state.get('controller_pid')
            if process:
                try:
                    command = Path(f'/proc/{int(process)}/cmdline').read_bytes()
                    if b'app.forge_runpod' in command and str(root.resolve()).encode() in command:
                        raise HTTPException(409, 'Controller is still active; poll status')
                except FileNotFoundError:
                    pass
            from .forge_runpod import cleanup
            import asyncio
            try:
                if not state.get('pod_terminated'):
                    await asyncio.to_thread(cleanup, state, root)
            except Exception:
                raise HTTPException(503, 'Pod cleanup failed; retry reconciliation before any new render') from None
            state.update(state='failed', phase='reconciled', error='Interrupted job reconciled; submit a new key to retry')
            write_json(root / 'state.json', state)
            if (p.get('workspace_external_execution') or {}).get('job_id') == jid:
                p['workspace_external_execution']['state'] = 'failed'
                p['steps']['render'].update(state='error', msg=state['error'])
                store.save_project(p)
            return job_status(p, jid)

    @router.post('/videos/{pid}/render/runpod', status_code=202)
    async def render(pid: str, body: RenderRequest):
        async with project_lock(pid):
            p = api._project(pid)
            signature = api._hash(body.model_dump())
            for job in p.get('forge_runpod_jobs', []):
                if job['idempotency_key'] == body.idempotency_key:
                    if job['request_sha256'] != signature:
                        raise HTTPException(409, 'Render key reused with different input')
                    return dict(job_status(p, job['id']), reused=True)
            p = api._project(pid, True)
            ensure_idle(p)
            check = preflight(p)
            if check['input_sha256'] != body.expected_input_sha256:
                raise HTTPException(409, 'Render inputs changed; read preflight again')
            if not check['ready']:
                raise HTTPException(409, check)
            jid = uuid.uuid4().hex
            root = job_root(pid, jid)
            root.mkdir(parents=True, exist_ok=False)
            job = {'id': jid, 'idempotency_key': body.idempotency_key, 'request_sha256': signature,
                   'input_sha256': check['input_sha256'], 'created': now()}
            write_json(root / 'request.json', {'project_id': pid, 'job_id': jid,
                       'inputs': render_inputs(p), 'input_sha256': check['input_sha256'],
                       'options': body.model_dump(exclude={'idempotency_key', 'expected_input_sha256'})})
            write_json(root / 'state.json', {'state': 'queued', 'phase': 'waiting_for_runpod_slot', 'created': time.time()})
            p.setdefault('forge_runpod_jobs', []).append(job)
            p['workspace_external_execution'] = {'state': 'queued', 'backend': 'runpod', 'job_id': jid}
            p['steps']['render'].update(state='queued', msg='Queued on RunPod; no local rendering')
            store.save_project(p)
            try:
                launch_controller(root)
            except Exception:
                write_json(root / 'state.json', {'state': 'failed', 'error': 'Controller launch failed'})
                p['workspace_external_execution']['state'] = 'failed'
                p['steps']['render'].update(state='error', msg='RunPod controller launch failed')
                store.save_project(p)
                raise HTTPException(503, 'RunPod controller launch failed; inspect job before retrying') from None
            return dict(job_status(p, jid), reused=False)
