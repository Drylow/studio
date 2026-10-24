"""API contracts with temporary data and forbidden paid calls."""
from pathlib import Path
import json
import pytest
from fastapi import HTTPException

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace
    from app import forge_api as forge, workspace_generation as generation
    from app.workspace_identity import identity
else:
    from .workspace_api_tests import workspace
    from . import forge_api as forge, workspace_generation as generation
    from .workspace_identity import identity
from app import store, pipeline

BASE = forge.PREFIX


@pytest.fixture
def client(workspace):
    client, proxy, values, app = workspace
    generation.install(app)
    if Path(__file__).parent.name == "tests":
        from app import workspace_planning, workspace_writing
    else:
        from . import workspace_planning, workspace_writing
    workspace_planning.install(app); workspace_writing.install(app)
    forge.install(app)
    count = len(app.routes); forge.install(app)
    assert len(app.routes) == count
    return client


def create(client, **extra):
    return client.post(BASE + "/videos", json={"channel_id": "edo-daily", "title": "Fixture episode",
        "script": "You walk inside. You put the bottle on the table.", "idempotency_key": "fixture-01", **extra})


def test_creation_replay_conflict_and_archive(client):
    first = create(client); assert first.status_code == 201, first.text
    pid = first.json()["id"]
    assert create(client).json()["id"] == pid
    assert create(client).json()["reused"]
    assert create(client, title="Different episode").status_code == 409
    p = store.get_project(pid); p["archived"] = True; store.save_project(p)
    assert create(client).json()["id"] == pid
    assert len(store.list_projects()) == 1
    assert not p.get("voiceover") and not p.get("scenes")


def test_creation_keys_are_member_scoped(client):
    a = identity.set({"username": "worker-a"})
    try: first = create(client).json()
    finally: identity.reset(a)
    b = identity.set({"username": "worker-b"})
    try:
        second = create(client).json()
        mine = client.get(BASE + "/videos").json()
    finally: identity.reset(b)
    assert first["id"] != second["id"]
    assert [p["id"] for p in mine] == [second["id"]]
    assert len(client.get(BASE + "/videos?scope=team").json()) == 2


@pytest.mark.parametrize("extra", [{"idempotency_key": "../bad"}, {"idempotency_key": ""},
                                   {"idempotency_key": None}, {"auto_run": True}])
def test_invalid_creation_does_not_write(client, extra):
    assert create(client, **extra).status_code == 422
    assert store.list_projects() == []


def test_poll_is_lightweight_and_honest_after_interruption(client, monkeypatch):
    pid = create(client).json()["id"]
    p = store.get_project(pid); p["steps"]["voiceover"]["state"] = "running"; store.save_project(p)
    def forbidden(*a, **k): raise AssertionError("poll hashed files or queried a provider")
    monkeypatch.setattr(forge.api, "_file_digest", forbidden)
    monkeypatch.setattr(forge.api, "_catalog", forbidden)
    result = client.get(BASE + f"/videos/{pid}/status")
    assert result.status_code == 200
    assert result.json()["state"] == "interrupted" and not result.json()["running"]


def test_unlock_pauses_only_this_projects_queue_and_is_idempotent(client):
    import importlib
    queue = importlib.import_module(forge.__package__ + '.forge_queue')
    pid = create(client).json()['id']
    queue.save({'jobs': [{'id': 'ours', 'project_id': pid, 'state': 'queued'},
                         {'id': 'theirs', 'project_id': 'other', 'state': 'queued'}]})
    for _ in range(2):
        response = client.post(BASE + f'/videos/{pid}/unlock', json={})
        assert response.status_code == 200 and response.json()['unlocked']
    jobs = queue.load()['jobs']
    assert jobs[0]['state'] == 'cancelled' and jobs[1]['state'] == 'queued'
    assert not client.get(BASE + f'/videos/{pid}/operations').json()['running']


def test_guards_remain_enforced_and_no_fake_review(client):
    pid = create(client).json()["id"]
    for name in ("render", "preview", "prepare", "write-script"):
        response = client.post(BASE + f"/videos/{pid}/actions/{name}", json={})
        assert response.status_code in (409, 422), (name, response.text)
    assert client.post(BASE + f"/videos/{pid}/review", json={"state": "verified"}).status_code == 422
    assert client.post(BASE + f"/videos/{pid}/review", json={"scope": "voiceover", "state": "verified",
        "reviewer": "Fixture AI", "source": "delegated_ai_inspection", "notes": "Missing file"}).status_code == 409
    response = client.post(BASE + f"/videos/{pid}/review", json={"scope": "script", "state": "verified",
        "reviewer": "Fixture AI", "source": "delegated_ai_inspection", "notes": "Read fixture narration"})
    assert response.status_code == 200
    assert response.json()["human_reviews"]["script"]["source"] == "delegated_ai_inspection"


def test_saved_voice_reused_and_active_job_not_retried(client, monkeypatch):
    pid = create(client).json()["id"]
    (store.project_dir(pid) / "existing.wav").write_bytes(b"fixture voice")
    p = store.get_project(pid); p["voiceover"] = {"file": "existing.wav", "duration": 4}; store.save_project(p)
    assert client.post(BASE + f"/videos/{pid}/actions/voice", json={}).json()["reused"]
    monkeypatch.setattr(pipeline, "is_running", lambda p: True)
    assert client.post(BASE + f"/videos/{pid}/actions/voice", json={}).status_code == 409


def test_download_prevents_escape_and_streams_existing_file(client, tmp_path):
    pid = create(client).json()["id"]
    p = store.get_project(pid)
    assert client.get(BASE + f"/videos/{pid}/download").status_code == 404
    outside = tmp_path / "secret.mp4"; outside.write_bytes(b"private")
    p["render"] = {"file": str(outside)}; store.save_project(p)
    assert client.get(BASE + f"/videos/{pid}/download").status_code == 404
    path = store.project_dir(pid) / "render/final.mp4"; path.parent.mkdir(); path.write_bytes(b"fixture-output")
    p["render"] = {"file": "render/final.mp4"}; store.save_project(p)
    assert client.get(BASE + f"/videos/{pid}/download").content == b"fixture-output"
    assert client.get(BASE + f"/videos/{pid}/download?kind=config").status_code == 422


def test_complete_live_inventory_and_schema(client):
    rows = client.get(BASE + "/endpoints").json()["endpoints"]
    assert any(r["public_path"] == BASE + "/videos" and r["method"] == "POST" for r in rows)
    assert any(r["public_path"] == "/api/2d/api/workspace/projects/{pid}/scenes" for r in rows)
    paths = client.get(BASE + "/openapi.json").json()["paths"]
    for row in rows:
        assert row["public_path"] in paths
    guide = client.get(BASE + "/LLM.txt")
    assert guide.status_code == 200
    assert "LIVE COMPLETE ENDPOINT INVENTORY" in guide.text
    assert "POST " + BASE + "/videos" in guide.text


def test_media_urls_get_public_gateway_prefix():
    assert forge.external_urls({"image_url": "/media/one/image.png", "references": [{
        "url": "/api/workspace/projects/one/scenes/1/references/0"}]}) == {
        "image_url": "/api/2d/media/one/image.png", "references": [{
        "url": "/api/2d/api/workspace/projects/one/scenes/1/references/0"}]}


def test_reference_sources_are_guarded_and_attempt_is_not_replayed(client, monkeypatch):
    pid = create(client).json()['id']
    endpoint = BASE + f'/videos/{pid}/references/generate'
    assert client.post(endpoint, json={'asset_id':'cast-a','prompt':'One adult','references':[]}).status_code == 422
    assert client.post(endpoint, json={'asset_id':'cast-a','prompt':'One adult','references':[{
        'owner':'project','path':'missing.png','sha256':'missing','review_state':'verified'}]}).status_code == 409
    base=store.project_dir(pid);(base/'guide.png').write_bytes(b'fixture source')
    ref={'owner':'project','path':'guide.png','sha256':forge.api._file_digest(base,'guide.png'),'review_state':'verified'}
    calls=[];monkeypatch.setattr(pipeline,'start',lambda *args:calls.append(args))
    body={'asset_id':'cast-a','prompt':'One adult','references':[ref]}
    assert client.post(endpoint,json=body).status_code==202
    assert client.post(endpoint,json=body).status_code==409
    assert len(calls)==1 and not store.get_project(pid)['workspace_reference_jobs']['cast-a'].get('sha256')
