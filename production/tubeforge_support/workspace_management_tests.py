"""Management writes never generate content or mutate existing projects."""
import io
from pathlib import Path

import pytest
from PIL import Image

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace, create, api, store, channels, read_json
    from app import workspace_management as management
else:
    from .workspace_api_tests import workspace, create, api, store, channels, read_json
    from . import workspace_management as management


@pytest.fixture
def managed(workspace):
    client, _, _, app = workspace
    management.install(app)
    count = len(app.router.routes)
    management.install(app)
    assert len(app.router.routes) == count
    return client


def new_style(client, **changes):
    response = client.post("/api/workspace/management/styles", json={"name": "My visual style",
        "prompt": "Exact visual prompt.", "background_direction": "Exact background rules.",
        "thumbnail_prompt": "Different thumbnail direction.", **changes})
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, sid):
    image = io.BytesIO()
    Image.new("RGB", (32, 18), "white").save(image, format="PNG")
    response = client.post(f"/api/workspace/management/styles/{sid}/references",
                           files={"file": ("reference.png", image.getvalue(), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


def test_create_channel_preset_copies_template_and_references(managed):
    template = new_style(managed)
    ref = upload(managed, template['id'])
    response = managed.post('/api/workspace/management/presets', json={
        'name': 'Marine channel', 'template_style_id': template['id'], 'language': 'English',
        'voice': {'provider': 'algrow', 'voice_id': 'fixture-voice'},
        'preset': {'background_mode': 'consistent'}})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['channel']['style_id'] == result['preset']['id'] != template['id']
    assert result['preset']['name'] == result['channel']['name'] == 'Marine channel'
    assert result['preset']['background_mode'] == 'consistent'
    assert result['preset']['references'][0]['path'] == ref['path']
    assert result['preset']['references'][0]['exists']
    assert store.get_style(template['id'])['visuals']['background_mode'] == 'free'


def test_invalid_channel_preset_does_not_create_style_or_channel(managed):
    previous = managed.get('/api/workspace/management').json()
    response = managed.post('/api/workspace/management/presets', json={
        'name': 'Invalid preset', 'voice': {'provider': 'unknown', 'voice_id': 'fixture-voice'},
        'preset': {'prompt': 'A drawing prompt.'}})
    assert response.status_code == 422
    assert managed.get('/api/workspace/management').json() == previous


def test_channel_and_visual_preset_save_together_and_preserve_existing_project(managed):
    created = managed.post('/api/workspace/management/presets', json={
        'name': 'Marine', 'voice': {'provider': 'algrow', 'voice_id': 'fixture-voice'},
        'preset': {'prompt': 'Original marine drawing.', 'image_model': 'fixture-image'}}).json()
    cid = created['channel']['id']
    project = managed.post('/api/workspace/projects', json={
        'profile_id': cid, 'title': 'Existing film', 'custom_script': 'Saved original narration.'}).json()
    previous = store.get_project(project['id']).copy()
    result = managed.put('/api/workspace/management/presets/' + cid, json={
        'name': 'Marine renamed', 'description': 'New description.',
        'preset': {'prompt': 'Updated visual language.', 'background_mode': 'consistent'}})
    assert result.status_code == 200, result.text
    assert result.json()['channel']['name'] == result.json()['preset']['name'] == 'Marine renamed'
    assert result.json()['preset']['prompt'] == 'Updated visual language.'
    assert store.get_project(project['id']) == previous
    invalid = managed.put('/api/workspace/management/presets/' + cid, json={
        'name': 'Must not be adopted', 'preset': {'background_mode': 'invalid'}})
    assert invalid.status_code == 422
    assert next(row for row in api._profiles() if row['id'] == cid)['name'] == 'Marine renamed'


def test_shared_style_is_isolated_before_channel_preset_edit(managed):
    style = new_style(managed)
    channels_created = [managed.post('/api/workspace/management/channels', json={
        'name': name, 'style_id': style['id'], 'voice': {'voice_id': 'fixture-voice'}}).json()
        for name in ('First', 'Second')]
    result = managed.put('/api/workspace/management/presets/' + channels_created[0]['id'], json={
        'preset': {'prompt': 'Only the first channel changes.'}})
    assert result.status_code == 200, result.text
    assert result.json()['channel']['style_id'] != style['id']
    assert next(row for row in api._profiles() if row['id'] == channels_created[1]['id'])['style_id'] == style['id']
    assert store.get_style(style['id'])['visuals']['art_style'] == 'Exact visual prompt.'


def test_drawing_guide_is_frozen_and_required_independently_of_character_refs(managed):
    style = new_style(managed)
    ref = upload(managed, style['id'])
    selected = managed.put('/api/workspace/management/styles/' + style['id'], json={
        'drawing_reference_path': ref['path']})
    assert selected.status_code == 200, selected.text
    assert selected.json()['drawing_reference_path'] == ref['path']
    channel = managed.post('/api/workspace/management/channels', json={
        'name': 'Marine', 'style_id': style['id'], 'voice': {'voice_id': 'fixture-voice'}}).json()
    project = managed.post('/api/workspace/projects', json={
        'profile_id': channel['id'], 'title': 'A story', 'custom_script': 'Saved narration.'}).json()
    guide = project['drawing_reference_snapshot']
    assert guide['sha256'] == ref['sha256'] and guide['review_state'] == 'verified'
    valid = dict(guide, owner='style', role='style-only')
    api._validate_drawing_reference(project, {'references': [valid]})
    with pytest.raises(Exception, match='drawing guide'):
        api._validate_drawing_reference(project, {'references': [dict(valid, role='identity')]})
    with pytest.raises(Exception, match='drawing guide'):
        api._validate_drawing_reference(project, {'references': []})
    (store.style_dir(style['id']) / ref['path']).write_bytes(b'modified source')
    with pytest.raises(Exception, match='missing or changed'):
        api._validate_drawing_reference(project, {'references': [valid]})


def test_existing_character_edits_save_with_channel_without_implicit_validation(managed):
    style = new_style(managed)
    image = io.BytesIO()
    Image.new('RGB', (32, 32), 'white').save(image, format='PNG')
    imported = managed.post('/api/workspace/management/styles/' + style['id'] + '/characters',
        files={'file': ('hero.png', image.getvalue(), 'image/png')},
        data={'name': 'Hero', 'description': 'Original character', 'is_main': 'true'})
    assert imported.status_code == 200
    channel = managed.post('/api/workspace/management/channels', json={
        'name': 'Marine', 'style_id': style['id'], 'voice': {'voice_id': 'fixture-voice'}}).json()
    result = managed.put('/api/workspace/management/presets/' + channel['id'], json={
        'description': 'New channel description', 'characters': [{'name': 'Hero', 'variant': 'default',
        'description': 'Exact revised character', 'is_main': True}]})
    assert result.status_code == 200, result.text
    character = result.json()['preset']['characters'][0]['variants'][0]
    assert character['description'] == 'Exact revised character'
    assert character['references'][0]['review_state'] == 'unreviewed'


def test_preset_write_failure_restores_existing_records(managed, monkeypatch):
    created = managed.post('/api/workspace/management/presets', json={
        'name': 'Marine', 'voice': {'voice_id': 'fixture-voice'}, 'preset': {'prompt': 'Original drawing'}}).json()
    cid = created['channel']['id']
    before = managed.get('/api/workspace/management').json()
    original = management._save_channel
    def failing(channel):
        original(channel)
        raise RuntimeError('fixture write failure')
    monkeypatch.setattr(management, '_save_channel', failing)
    with pytest.raises(RuntimeError, match='fixture write failure'):
        managed.put('/api/workspace/management/presets/' + cid, json={
            'name': 'Must be rolled back', 'preset': {'prompt': 'Must be rolled back'}})
    assert managed.get('/api/workspace/management').json() == before


def test_style_create_upload_previews_reorder_and_duplicate(managed):
    style = new_style(managed)
    assert style["prompt"] == "Exact visual prompt." and not style["references"]
    refs = [upload(managed, style["id"]), upload(managed, style["id"])]
    url = f"/api/workspace/management/styles/{style['id']}"
    result = managed.put(url, json={"references": list(reversed(refs)), "video_preview": refs[0]["path"],
                                    "thumbnail_preview": refs[1]["path"]})
    assert result.status_code == 200, result.text
    assert [r["path"] for r in result.json()["references"]] == [r["path"] for r in reversed(refs)]
    assert result.json()["video_preview_url"].endswith(refs[0]["path"])
    clone = new_style(managed, name="Copy", base_id=style["id"], prompt=style["prompt"])
    assert clone["id"] != style["id"]
    assert (store.style_dir(clone["id"]) / refs[0]["path"]).read_bytes() == (store.style_dir(style["id"]) / refs[0]["path"]).read_bytes()
    assert managed.put(url, json={"references": []}).status_code == 200
    assert (store.style_dir(style["id"]) / refs[0]["path"]).exists()
    assert len(next(s for s in api._styles() if s["id"] == clone["id"])["references"]) == 2


def test_background_modes_are_explicit_and_frozen_per_project(managed):
    style=new_style(managed)
    assert style['background_mode']=='free'
    channel=managed.post('/api/workspace/management/channels',json={
        'name':'Fictional test channel','style_id':style['id'],'language':'English','target_minutes':15,
        'voice':{'provider':'algrow','voice_id':'fixture-voice'}}).json()
    first=managed.post('/api/workspace/projects',json={'profile_id':channel['id'],
        'title':'First','custom_script':'A complete imported story.'}).json()
    assert first['settings']['visuals']['background_mode']=='free'
    url=f'/api/workspace/management/styles/{style["id"]}'
    assert managed.put(url,json={'background_mode':'unexpected'}).status_code==422
    assert managed.put(url,json={'background_mode':'consistent'}).json()['background_mode']=='consistent'
    assert managed.get(f'/api/workspace/projects/{first["id"]}').json()['settings']['visuals']['background_mode']=='free'
    second=managed.post('/api/workspace/projects',json={'profile_id':channel['id'],
        'title':'Second','custom_script':'Another complete imported story.'}).json()
    assert second['settings']['visuals']['background_mode']=='consistent'
    assert second['style_snapshot']['background_mode']=='consistent'
    assert new_style(managed,name='New blank style')['background_mode']=='free'
    assert new_style(managed,name='Clone',base_id=style['id'])['background_mode']=='consistent'


def test_camera_policy_changes_are_per_preset_and_do_not_change_existing_films(managed):
    style=new_style(managed)
    channel=managed.post('/api/workspace/management/channels',json={
        'name':'Stable fictional channel','style_id':style['id'],'language':'English','target_minutes':15,
        'voice':{'provider':'algrow','voice_id':'fixture-voice'}}).json()
    first=managed.post('/api/workspace/projects',json={'profile_id':channel['id'],
        'title':'Existing film','custom_script':'A complete story.'}).json()
    url=f'/api/workspace/management/styles/{style["id"]}'
    assert first['settings']['visuals']['camera_policy']=='varied'
    assert managed.put(url,json={'camera_policy':'invalid'}).status_code==422
    assert managed.put(url,json={'camera_policy':'stable'}).json()['camera_policy']=='stable'
    assert managed.get(f'/api/workspace/projects/{first["id"]}').json()['settings']['visuals']['camera_policy']=='varied'
    second=managed.post('/api/workspace/projects',json={'profile_id':channel['id'],
        'title':'New film','custom_script':'Another complete story.'}).json()
    assert second['settings']['visuals']['camera_policy']=='stable'
    assert second['style_snapshot']['camera_policy']=='stable'
    assert new_style(managed,name='Other channel style')['camera_policy']=='varied'


def test_channel_management_defaults_and_existing_project_unchanged(managed):
    previous = create(managed, custom_script="Existing episode.")
    original = (store.project_dir(previous["id"]) / "project.json").read_bytes()
    style = new_style(managed)
    result = managed.put("/api/workspace/management/channels/edo-daily", json={
        "name": "Edo revised", "handle": "@EdoExample", "description": "Channel description.",
        "setting": "Edo period", "style_id": style["id"], "language": "French", "target_minutes": 24})
    assert result.status_code == 200, result.text
    assert result.json()["style_name"] == style["name"]
    assert not result.json()["video_preview_url"]
    assert (store.project_dir(previous["id"]) / "project.json").read_bytes() == original
    later = create(managed, duration_minutes=24)
    assert later["style_id"] == style["id"] and later["settings"]["language"] == "French"
    assert later["settings"]["voice"]["provider"] == "algrow"
    assert later["target_duration_seconds"] == 1440
    using_defaults = managed.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "Default duration"})
    assert using_defaults.status_code == 201
    assert using_defaults.json()["target_duration_seconds"] == 1440
    assert managed.put(f"/api/workspace/management/styles/{style['id']}", json={"prompt": "New style text."}).status_code == 200
    assert store.get_project(later["id"])["settings"]["visuals"]["art_style"] == style["prompt"]


def test_create_archive_restore_channel_and_style_without_deletion(managed):
    style = new_style(managed)
    result = managed.post("/api/workspace/management/channels", json={"name": "My channel", "handle": "@Example", "style_id": style["id"], "voice": {"voice_id": "fixture-channel-voice", "provider": "algrow"}})
    assert result.status_code == 201, result.text
    c = result.json()
    assert c["id"] in {p["id"] for p in managed.get("/api/workspace/channels").json()}
    style_url = f"/api/workspace/management/styles/{style['id']}"
    channel_url = f"/api/workspace/management/channels/{c['id']}"
    assert managed.put(style_url, json={"archived": True}).status_code == 409
    assert managed.put(channel_url, json={"archived": True}).status_code == 200
    assert c["id"] not in {p["id"] for p in managed.get("/api/workspace/channels").json()}
    assert managed.put(style_url, json={"archived": True}).status_code == 200
    assert store.style_dir(style["id"]).exists()
    assert managed.put(channel_url, json={"archived": False}).status_code == 404
    assert managed.put(style_url, json={"archived": False}).status_code == 200
    assert managed.put(channel_url, json={"archived": False}).status_code == 200
    assert len(managed.get("/api/workspace/channels").json()) == 6


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "One", "prompt": ""},
                                  {"name": "One", "prompt": "x", "base_id": "../private"}])
def test_invalid_style_create_rejected_without_files(managed, body):
    assert managed.post("/api/workspace/management/styles", json=body).status_code == 422
    assert {s["id"] for s in api._styles()} == {"pov-history"}


@pytest.mark.parametrize("body", [{"style_id": "missing"}, {"target_minutes": 0}, {"language": "unknown"},
                                  {"archived": "yes"}, {"name": ""}])
def test_invalid_channel_update_is_atomic(managed, body):
    before = channels.FILE.read_bytes()
    assert managed.put("/api/workspace/management/channels/edo-daily", json=body).status_code in (404, 422)
    assert channels.FILE.read_bytes() == before


def test_reference_paths_are_owned_and_shared_style_cannot_be_archived(managed):
    style = new_style(managed)
    url = f"/api/workspace/management/styles/{style['id']}"
    for body in ({"references": [{"path": "../private"}]}, {"video_preview": "../private"}):
        assert managed.put(url, json=body).status_code == 422
    assert managed.put("/api/workspace/management/styles/pov-history", json={"archived": True}).status_code == 409
    assert len(read_json(channels.FILE)) == 5


def test_existing_style_references_survive_management_and_duplication(managed):
    style = store.get_style("pov-history")
    directory = store.style_dir("pov-history")
    Image.new("RGB", (32, 18), "white").save(directory / "original.png")
    style["visuals"]["style_refs"] = ["original.png"]
    style["visuals"]["reference_sources"] = [{"path": "original.png", "label": "Original capture"}]
    style.pop("workspace_references", None)
    store.save_style(style)
    item = next(s for s in managed.get("/api/workspace/management").json()["styles"] if s["id"] == "pov-history")
    assert item["references"][0]["label"] == "Original capture"
    assert item["references"][0]["exists"]
    clone = new_style(managed, base_id="pov-history")
    assert clone["references"][0]["path"] == "original.png"
    uploaded = upload(managed, "pov-history")
    assert store.get_style("pov-history")["visuals"]["style_refs"] == ["original.png", uploaded["path"]]


def character_upload(client, sid, **changes):
    picture = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(picture, "PNG")
    return client.post(f"/api/workspace/management/styles/{sid}/characters",
                       data={"name": "Patch", "variant": "default", "description": "Round white head, orange bandage.",
                             "is_main": "true", **changes},
                       files={"file": ("identity.png", picture.getvalue(), "image/png")})


def test_character_images_separate_from_style_images_and_explicitly_validated(managed):
    style = new_style(managed)
    result = character_upload(managed, style["id"])
    assert result.status_code == 200, result.text
    item = result.json()
    assert item["main_character"] == "Patch" and item["references"] == []
    ref = item["characters"][0]["variants"][0]["references"][0]
    assert ref["exists"] and not ref["valid"] and ref["role"] == "identity"
    url = f"/api/workspace/management/styles/{style['id']}/characters"
    saved = managed.put(url, json={"name": "Patch", "variant": "default", "description": "Same identity.", "verify": True})
    assert saved.status_code == 200 and saved.json()["characters"][0]["variants"][0]["references"][0]["valid"]
    assert saved.json()["main_character"] == "Patch"
    unset = managed.put(url, json={"name": "Patch", "description": "Same identity.", "is_main": False})
    assert unset.status_code == 200 and unset.json()["main_character"] is None
    (store.style_dir(style["id"]) / ref["path"]).write_bytes(b"changed")
    assert managed.put(url, json={"name": "Patch", "description": "Same identity.", "verify": True}).status_code == 409


def test_project_cast_snapshot_survives_later_style_edits(managed):
    style = new_style(managed)
    assert character_upload(managed, style["id"]).status_code == 200
    url = f"/api/workspace/management/styles/{style['id']}/characters"
    body = {"name": "Patch", "description": "Original identity.", "verify": True}
    assert managed.put(url, json=body).status_code == 200
    p = create(managed, style_id=style["id"], custom_script="You survive.")
    saved = store.get_project(p["id"])
    assert saved["main_character"] == "Patch"
    before = saved["style_cast_snapshot"]
    assert managed.put(url, json=body | {"description": "Changed identity."}).status_code == 200
    assert store.get_project(p["id"])["style_cast_snapshot"] == before
    later = create(managed, style_id=style["id"], custom_script="Later episode.")
    assert store.get_project(later["id"])["style_cast_snapshot"]["Patch"]["variants"]["default"]["description"] == "Changed identity."


def test_character_validation_rejects_aliases_and_preserves_registry(managed):
    style = new_style(managed)
    assert character_upload(managed, style["id"]).status_code == 200
    before = store.get_style(style["id"])["workspace_cast_registry"]
    assert character_upload(managed, style["id"], name="patch").status_code == 422
    url = f"/api/workspace/management/styles/{style['id']}/characters"
    assert managed.put(url, json={"name": "Patch", "description": "Identity", "verify": "yes"}).status_code == 422
    assert store.get_style(style["id"])["workspace_cast_registry"] == before


def test_style_provider_opt_in_keeps_global_and_other_style_policy(managed, monkeypatch):
    monkeypatch.setattr(api, "_visual_policy", lambda: {"image_provider": "google_flow"})
    style = new_style(managed, image_provider="cli_proxy", image_model="fixture-image")
    p = create(managed, style_id=style["id"], custom_script="Script.", image_provider="cli_proxy")
    assert store.get_project(p["id"])["model_snapshot"]["image_provider"] == "cli_proxy"
    rejected = managed.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "Other style",
                                                            "custom_script": "Script.", "image_provider": "cli_proxy"})
    assert rejected.status_code == 422
