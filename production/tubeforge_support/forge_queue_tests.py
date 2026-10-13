"""Resource fairness, durable holds and review gates; no generation providers."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
if Path(__file__).parent.name != 'tests':
    sys.path.insert(0, str(ROOT / 'work/TubeForge'))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if Path(__file__).parent.name == 'tests':
    from app import forge_queue as queue
else:
    from . import forge_queue as queue


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(queue.config, 'DATA', tmp_path)
    values = {'TTS_CONCURRENCY':2,'PROJECT_PARALLEL':6,'RENDER_CONCURRENCY':1,'IMAGE_CONCURRENCY':24}
    monkeypatch.setattr(queue.config, 'get_int', lambda key: values.get(key, 1))
    monkeypatch.setattr(queue.config, 'get', lambda key: str(values.get(key, 1)))
    monkeypatch.setattr(queue, '_lock', asyncio.Lock())
    projects = {}; busy = set(); dispatch = []
    monkeypatch.setattr(queue.store, 'list_projects', lambda *args: list(projects.values()))
    monkeypatch.setattr(queue.pipeline, 'is_running', lambda pid: pid in busy)
    monkeypatch.setattr(queue.generation, 'batch_running', lambda pid: False)
    monkeypatch.setattr(queue.generation, '_active_projects', set())
    async def invoke(app, path, **kwargs):
        dispatch.append(kwargs); busy.add(kwargs['pid'])
    monkeypatch.setattr(queue.forge, 'invoke', invoke)
    def add(pid, **changes):
        p={'id':pid,'script':'You enter the room.','steps':{},'settings':{'voice':{}},'scenes':[],**changes}
        projects[pid]=p
        job={'id':pid+'-job','project_id':pid,'created':len(projects),'input_hash':queue.fingerprint(p),
             'state':'queued','stage':None,'automatic_plans':False,'member_id':'fixture','member_name':'Fixture',
             'completed_stages':[]}
        data=queue.load();data['jobs'].append(job);queue.save(data)
        return p,job
    return add,projects,busy,dispatch


def test_voice_capacity_and_no_duplicate_dispatch(world):
    add,projects,busy,calls=world
    for i in range(4):add(str(i))
    asyncio.run(queue.tick(None));asyncio.run(queue.tick(None))
    assert len(calls)==2 and all(c['action']=='voice' for c in calls)
    jobs=queue.load()['jobs'];assert [j['state'] for j in jobs].count('queued')==2


def test_review_hold_does_not_block_other_videos(world, monkeypatch):
    add,projects,busy,calls=world
    add('held',voiceover={'file':'voice.wav'},scenes=[{'image':'one.png'}])
    monkeypatch.setattr(queue.api,'_file_digest',lambda *a: 'hash')
    monkeypatch.setattr(queue.api,'_full',lambda p:{'scenes':[{'human_review':{'state':'unreviewed'}}]})
    add('ready');asyncio.run(queue.tick(None))
    assert [c['pid'] for c in calls]==['ready']
    assert queue.load()['jobs'][0]['state']=='awaiting_preview_review'


def test_input_edit_holds_instead_of_billing(world):
    add,projects,busy,calls=world;add('one');projects['one']['script']='Changed narration'
    asyncio.run(queue.tick(None))
    assert not calls and queue.load()['jobs'][0]['state']=='changed'


def test_failed_stage_is_not_retried(world):
    add,projects,busy,calls=world;add('one')
    data=queue.load();data['jobs'][0].update(state='running',stage='voice');queue.save(data)
    projects['one']['steps']={'voiceover':{'state':'error'}}
    asyncio.run(queue.tick(None));asyncio.run(queue.tick(None))
    assert not calls and queue.load()['jobs'][0]['state']=='failed'


def test_other_native_jobs_consume_capacity(world):
    add,projects,busy,calls=world
    for pid in ['external-a','external-b']:
        projects[pid]={'id':pid,'steps':{'voiceover':{'state':'running'}}};busy.add(pid)
    add('queued');asyncio.run(queue.tick(None))
    assert not calls


def test_ambiguous_dispatch_remains_interrupted(world, monkeypatch):
    add,projects,busy,calls=world;add('one')
    monkeypatch.setattr(queue.forge,'invoke',AsyncMock(side_effect=TimeoutError()))
    asyncio.run(queue.tick(None));asyncio.run(queue.tick(None))
    assert queue.load()['jobs'][0]['state']=='interrupted'
    assert queue.forge.invoke.await_count==1


def test_images_share_the_existing_provider_ceiling(world, monkeypatch):
    add,projects,busy,calls=world
    for pid in ('a','b','c'):add(pid,voiceover={'file':'voice.wav'},scenes=[{'image':None}])
    monkeypatch.setattr(queue.api,'_file_digest',lambda *a:'hash')
    asyncio.run(queue.tick(None))
    assert len(calls)==2
    assert all(c['body']['concurrency']==3 for c in calls)


def test_lifespan_restart_holds_reserved_jobs(world, monkeypatch):
    add,projects,busy,calls=world;add('one')
    data=queue.load();data['jobs'][0].update(state='running',stage='voice');queue.save(data)
    async def once():
        task=asyncio.create_task(queue.run(None));await asyncio.sleep(.02);task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    asyncio.run(once())
    assert queue.load()['jobs'][0]['state']=='interrupted' and not calls
