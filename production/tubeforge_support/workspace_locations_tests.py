"""Spatial contracts, reference tampering and camera variety without paid calls."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from PIL import Image

if Path(__file__).parent.name == 'tests':
    from test_workspace_api import workspace, create
    from app import workspace_locations as locations, workspace_generation as generation, workspace_planning as planning
else:
    from .workspace_api_tests import workspace, create
    from . import workspace_locations as locations, workspace_generation as generation, workspace_planning as planning
from app import llm, store


def camera_plan(n=9):
    views = {key: {'description': 'View of the cabin from ' + key, 'angle': key + ' facing the centre'}
             for key in ('door', 'opposite-wall', 'side-wall')}
    return {'locations': {'cabin': {'description': 'Small boat cabin',
        'layout': 'Door at stern; window on port wall; fixed table at bow',
        'anchors': ['Door at stern', 'Window on port wall', 'Table fixed at bow'], 'views': views}},
        'shots': [{'id': i+1, 'location_id': 'cabin', 'location_view': list(views)[i % 3],
            'shot_type': 'wide' if i % 2 else 'close_up',
            'visual_beat': 'The narrated repair advances at step ' + str(i+1)} for i in range(n)]}


def project_with_location(workspace):
    p = store.get_project(create(workspace[0], custom_script='You repair the motor.')['id'])
    p['settings']['visuals']['background_mode'] = 'consistent'
    master = store.project_dir(p['id']) / 'refs/cabin.png'
    master.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (32,18), 'yellow').save(master)
    entry = camera_plan()['locations']['cabin']
    entry['master'] = {'owner':'project','path':'refs/cabin.png','role':'location-master',
        'location_id':'cabin','review_state':'verified','sha256':hashlib.sha256(master.read_bytes()).hexdigest()}
    for key, view in entry['views'].items():
        view['reference'] = dict(entry['master'], role='location-view', location_view=key)
    p['workspace_location_registry'] = {'cabin':entry}
    return p


def authored_scene(p):
    s = dict(camera_plan(1)['shots'][0], text=p['script'], characters=[], prompt_author='codex',
             start=0,end=6, references=[])
    s['location_contract'] = locations.contract({'locations':locations.summary(p)},s)
    s['references'] = locations.author(p,s,[])
    s['prompt'] = 'One full-width flat cartoon scene.\n' + s['location_contract'] + '\n' + locations.binding(p,s)
    return s


def test_global_plan_counts_positions_not_crop_names():
    data = camera_plan()
    assert not locations.audit(locations.validate_plan(data,data['shots'])['shots'])['warnings']
    data['locations']['cabin']['views']['side-wall']['angle'] = 'door facing the centre'
    with pytest.raises(ValueError): locations.validate_plan(data,data['shots'])


def test_stable_axis_is_allowed_and_unknown_views_are_rejected():
    data = camera_plan()
    for row in data['shots']: row['location_view']='door'
    assert len(locations.validate_plan(data,data['shots'],policy='stable')['shots']) == 9
    with pytest.raises(ValueError): locations.validate_plan(data,data['shots'],policy='varied')
    data=camera_plan();data['shots'][0]['location_view']='invented-room'
    with pytest.raises(ValueError): locations.validate_plan(data,data['shots'])


def test_registry_geometry_cannot_be_rewritten_by_the_prepass(workspace):
    p=project_with_location(workspace);data=camera_plan()
    data['locations']['cabin']['layout']='Move the window onto the opposite wall'
    result=locations.validate_plan(data,data['shots'],locations.summary(p))
    assert result['locations']['cabin']['layout']==p['workspace_location_registry']['cabin']['layout']
    locations.check_registry(p)


def test_selected_view_keeps_master_and_preserves_other_reference_order(workspace):
    p=project_with_location(workspace);s=authored_scene(p)
    path=store.project_dir(p['id'])/'refs/side.png';Image.new('RGB',(32,18),'green').save(path)
    ref={'owner':'project','path':'refs/side.png','role':'location-view','location_id':'cabin',
         'location_view':'side-wall','review_state':'verified','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    p['workspace_location_registry']['cabin']['views']['side-wall']['reference']=ref
    s['location_view']='side-wall'
    base=[{'role':'identity','path':'actor.png'}, {'role':'location','path':'unrelated-room.png'},
          {'role':'object','path':'radio.png'}]
    refs=locations.author(p,s,base)
    assert [r['path'] for r in refs]==['refs/cabin.png','refs/side.png','actor.png','radio.png']
    assert base[1]['path']=='unrelated-room.png'


def test_changed_file_or_geometry_blocks_before_image_call(workspace):
    p=project_with_location(workspace);s=authored_scene(p)
    locations.validate(p,s)
    stamp=generation._signature(p,s)
    p['workspace_location_registry']['cabin']['layout'] += '; added hatch'
    assert generation._signature(p,s)!=stamp
    with pytest.raises(HTTPException): locations.validate(p,s)
    p=project_with_location(workspace);s=authored_scene(p)
    (store.project_dir(p['id'])/'refs/cabin.png').write_bytes(b'changed')
    with pytest.raises(HTTPException): locations.validate(p,s)


def test_camera_change_invalidates_review_and_generation_signature(workspace):
    p=project_with_location(workspace);s=authored_scene(p)
    image=store.project_dir(p['id'])/'image.png';Image.new('RGB',(32,18),'white').save(image)
    s['image']='image.png';evidence=locations.api._scene_evidence(p,s);stamp=generation._signature(p,s)
    assert evidence
    s['location_view']='opposite-wall'
    assert locations.api._scene_evidence(p,s) is None
    assert generation._signature(p,s)!=stamp


def test_registry_endpoint_checks_conflict_and_preserves_source_media(workspace):
    p=project_with_location(workspace);entries=p.pop('workspace_location_registry')
    p['scenes']=[{'id':1,'image':'existing.png'}];store.save_project(p)
    url=f'/api/workspace/projects/{p["id"]}/locations';client=workspace[0]
    assert client.put(url,json={'locations':entries,'previous_hash':'stale'}).status_code==409
    response=client.put(url,json={'locations':entries,'previous_hash':locations.api._hash({})})
    assert response.status_code==200,response.text
    assert store.get_project(p['id'])['scenes'][0]['image']=='existing.png'
    entries['cabin']['master']['sha256']='bad'
    response=client.put(url,json={'locations':entries,'previous_hash':response.json()['location_registry_hash']})
    assert response.status_code==409


def test_real_prepass_uses_configured_proxy_once_and_never_generates_images(workspace,monkeypatch):
    p=project_with_location(workspace);data=camera_plan()
    mock=AsyncMock(return_value=json.dumps(data));monkeypatch.setattr(llm,'chat',mock)
    result=asyncio.run(locations.plan(p,[dict(row,text=p['script']) for row in data['shots']],'fixture-selected-text'))
    assert len(result['shots'])==9 and mock.await_count==1
    assert mock.call_args.kwargs['attempts']==1 and mock.call_args.kwargs['hedge'] is False
    assert mock.call_args.kwargs['model']=='fixture-selected-text'
    assert 'world-space' in mock.call_args.args[0][0]['content']


def test_prepare_connects_global_views_to_exact_prompts_and_saved_receipts(workspace,monkeypatch):
    p=project_with_location(workspace)
    data=camera_plan();shots=[dict(row,text=p['script'],start=i*6,end=(i+1)*6)
                               for i,row in enumerate(data['shots'])]
    style=store.get_style(p['style_id']);refs=[]
    monkeypatch.setattr(planning,'inputs',lambda p:('fixture-text',style,refs,shots))
    monkeypatch.setattr(planning,'allowed',lambda p:True)
    async def chat(messages,**kw):
        body=json.loads(messages[1]['content'])
        if 'requested_shots' not in body:return json.dumps(data)
        assert body['location_camera_plan']['locations']['cabin']['anchors']==data['locations']['cabin']['anchors']
        return json.dumps({'shots':[{'id':r['id'],'location_id':'cabin','characters':[],
            'prompt':'A clean round-headed cartoon boat scene shows the narrated motor repair progressing in the cabin, with permanent fixtures unchanged.'}
            for r in body['requested_shots']]})
    monkeypatch.setattr(llm,'chat',chat)
    asyncio.run(planning.prepare(p))
    assert all(planning.authored(p,s) for s in p['scenes'])
    assert [s['location_view'] for s in p['scenes']]==[s['location_view'] for s in data['shots']]
    assert not p['workspace_camera_audit']['warnings']
    assert all(s['location_contract'] in s['prompt'] for s in p['scenes'])
    p['scenes'][0]['location_view']='side-wall'
    assert not planning.authored(p,p['scenes'][0])


def test_consistent_mode_without_masters_cannot_silently_generate_free_scenery(workspace):
    p=project_with_location(workspace);p['workspace_location_registry']={}
    with pytest.raises(HTTPException) as error:
        locations.validate(p, {'id':1})
    assert error.value.status_code == 422


def test_unillustrated_reverse_angle_blocks_before_paid_generation(workspace):
    p=project_with_location(workspace)
    p['workspace_location_registry']['cabin']['views']['side-wall'].pop('reference')
    with pytest.raises(HTTPException): locations.check_registry(p)
    with pytest.raises(HTTPException):
        locations.selected(p, dict(location_id='cabin', location_view='side-wall'))


def test_camera_policy_is_frozen_per_project_and_legacy_variety_is_preserved(workspace):
    p=project_with_location(workspace)
    assert locations.camera_policy(p)=='varied'
    assert 'at least three distinct' in locations.rules(p)
    p['settings']['visuals'].pop('camera_policy', None)
    p['style_snapshot']['camera_policy']='stable'
    assert locations.camera_policy(p)=='stable'
    assert 'No minimum viewpoints' in locations.rules(p)
    p['settings']['visuals']['camera_policy']='varied'
    assert locations.camera_policy(p)=='varied'


def test_free_mode_ignores_location_registry_but_keeps_identity_references(workspace):
    p=project_with_location(workspace);p['settings']['visuals']['background_mode']='free'
    s=authored_scene(p)
    identities=[{'role':'identity','path':'same-character.png'}]
    assert locations.author(p,s,identities+[p['workspace_location_registry']['cabin']['master']])==identities
    assert locations.selected(p,s)==[]
    s['location_view']='any-creative-background'
    locations.validate(p,s)


def test_old_projects_default_to_free_without_setting_changes(workspace):
    p=store.get_project(create(workspace[0],custom_script='A story.')['id'])
    p['settings']['visuals'].pop('background_mode',None);p['style_snapshot'].pop('background_mode',None)
    original=copy.deepcopy(p)
    assert locations.mode(p)=='free' and p==original


@pytest.mark.parametrize('mode',['free','consistent'])
def test_character_identity_binding_is_independent_of_background_mode(workspace,mode):
    if Path(__file__).parent.name=='tests':
        from app import workspace_characters as cast
    else:
        from . import workspace_characters as cast
    p=project_with_location(workspace);p['settings']['visuals']['background_mode']=mode
    image=store.project_dir(p['id'])/'actor.png';Image.new('RGB',(32,18),'white').save(image)
    identity={'owner':'project','path':'actor.png','role':'identity','character':'Mariner',
              'variant':'default','review_state':'verified','sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
    p['workspace_cast_registry']={'Mariner':{'variants':{'default':{
        'description':'A white circle-headed mariner with navy hat.', 'references':[identity]}}}}
    s=authored_scene(p);s.update(characters=['Mariner'],character_variants={'Mariner':'default'})
    base=locations.author(p,s,[identity]);s['references'],block=cast.author(p,s,base)
    s['prompt']='A new narrated action.\n'+(s['location_contract'] if mode=='consistent' else 'Free scenery.')+'\n'+block+'\n'+locations.binding(p,s)
    cast.validate(p,s);locations.validate(p,s)
    assert [r for r in s['references'] if r['role']=='identity']==[identity]
    assert sum(r['role']=='location-master' for r in s['references'])==(mode=='consistent')


def test_free_preparation_skips_global_location_call(workspace,monkeypatch):
    p=store.get_project(create(workspace[0],custom_script='You inspect the radio.')['id'])
    style=store.get_style(p['style_id'])
    shots=[{'id':1,'text':p['script'],'start':0,'end':6}]
    monkeypatch.setattr(planning,'inputs',lambda p:('fixture-text',style,[],shots))
    monkeypatch.setattr(planning,'allowed',lambda p:True)
    prepass=AsyncMock(side_effect=AssertionError('Free scenery must not plan a location registry'))
    monkeypatch.setattr(locations,'plan',prepass)
    mock=AsyncMock(return_value=json.dumps({'shots':[{'id':1,'location_id':'any-narrated-place',
        'characters':[],'prompt':'A clean flat cartoon frame shows a radio being inspected at a new location chosen to illustrate the narration.'}]}))
    monkeypatch.setattr(llm,'chat',mock)
    asyncio.run(planning.prepare(p))
    assert prepass.await_count==0 and mock.await_count==1
    assert 'BACKGROUND MODE: FREE' in mock.call_args.args[0][0]['content']
    assert 'location_contract' not in p['scenes'][0]
