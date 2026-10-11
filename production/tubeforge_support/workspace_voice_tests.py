"""Voice workflow contracts, with no paid synthesis."""
import asyncio
import copy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace, create, media_project, api, store
    from app import workspace_voice as voice
else:
    from .workspace_api_tests import workspace, create, media_project, api, store
    from . import workspace_voice as voice


SETTINGS = {"voice_id": "fixture-voice", "voice_name": "Fixture voice", "speed": 1}


def setup(workspace, monkeypatch):
    client, _, _, app = workspace
    voice.install(app)
    count = len(app.routes)
    voice.install(app)
    assert len(app.routes) == count
    monkeypatch.setattr(voice, "_key", lambda provider="algrow": "fixture-secret")
    return client


def test_next_generation_exact_script_and_no_review_gate(workspace, monkeypatch):
    client = setup(workspace, monkeypatch)
    script = "Line one.\n\nLine two exactly as pasted."
    p = create(client, custom_script=script, duration_minutes=15)
    started = []
    monkeypatch.setattr(voice.pipeline, "start", lambda pid, fn: started.append((pid, fn)))
    response = client.post(f"/api/workspace/projects/{p['id']}/voice/generate", json=SETTINGS | {"script_hash": p["script_hash"]})
    assert response.status_code == 202, response.text
    assert started == [(p["id"], voice.narrate)]
    assert response.json()["script"] == script
    assert response.json()["human_reviews"]["script"]["state"] == "unreviewed"
    before = copy.deepcopy(store.get_project(p["id"]))
    before["scenes"] = [{"prompt": "Exact authored prompt", "image": "previous.png"}]
    scenes = copy.deepcopy(before["scenes"])
    async def synth(text, settings, folder, progress=None):
        assert text == script
        assert settings["voice_id"] == SETTINGS["voice_id"]
        (folder / "voice.mp3").write_bytes(b"fixture audio")
        return {"file": "voice.mp3", "duration": 955, "words": [{"w": "Line", "s": 0, "e": 1}]}
    mock = AsyncMock(side_effect=synth)
    monkeypatch.setattr(voice.tts, "synthesize", mock)
    asyncio.run(voice.narrate(before))
    assert mock.await_count == 1
    assert before["script"] == script and before["scenes"] == scenes
    full = api._full(before)
    assert full["duration_info"]["kind"] == "actual"
    assert full["duration_info"]["seconds"] == 955
    response = client.put(f"/api/workspace/projects/{p['id']}/script", json={"text": script + " New."})
    assert response.json()["duration_info"]["kind"] == "estimated"


@pytest.mark.parametrize("change", ["empty", "changed", "speed", "busy"])
def test_rejected_generation_never_starts(workspace, monkeypatch, change):
    client = setup(workspace, monkeypatch)
    p = create(client, custom_script="A supplied script." if change != "empty" else "")
    started = []
    monkeypatch.setattr(voice.pipeline, "start", lambda *args: started.append(args))
    if change == "busy":
        monkeypatch.setattr(voice.pipeline, "is_running", lambda pid: True)
    body = SETTINGS | {"script_hash": p["script_hash"]}
    if change == "changed": body["script_hash"] = "old"
    if change == "speed": body["speed"] = 2
    assert client.post(f"/api/workspace/projects/{p['id']}/voice/generate", json=body).status_code in (409, 422)
    assert not started


def test_channel_voice_saved_only_for_this_channel_and_future_projects(workspace, monkeypatch):
    client = setup(workspace, monkeypatch)
    p = create(client, custom_script="Narration.")
    other = create(client, custom_script="Other project.")
    before = copy.deepcopy(store.get_project(other["id"])["settings"]["voice"])
    r = client.post(f"/api/workspace/projects/{p['id']}/voice/channel-default", json=SETTINGS)
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["voice"]["voice_id"] == SETTINGS["voice_id"]
    assert store.get_project(other["id"])["settings"]["voice"] == before
    future = create(client, custom_script="Future narration.")
    assert future["settings"]["voice"]["voice_id"] == SETTINGS["voice_id"]
    other_channel = create(client, profile_id="aztec-daily", custom_script="Other channel.")
    assert other_channel["settings"]["voice"].get("voice_id") != SETTINGS["voice_id"]


def test_failed_synthesis_retains_old_audio_and_sanitizes_error(workspace, monkeypatch):
    setup(workspace, monkeypatch)
    p = media_project(workspace[0])
    old = copy.deepcopy(p["voiceover"])
    scenes = copy.deepcopy(p["scenes"])
    monkeypatch.setattr(voice.tts, "synthesize", AsyncMock(side_effect=RuntimeError("fixture-secret")))
    with pytest.raises(RuntimeError, match="narration précédente") as exc:
        asyncio.run(voice.narrate(p))
    assert "fixture-secret" not in str(exc.value)
    assert p["voiceover"] == old and p["scenes"] == scenes
    assert p["steps"]["voiceover"]["state"] == "error"


def test_script_review_no_longer_required_for_readiness(workspace, monkeypatch):
    client = setup(workspace, monkeypatch)
    p = media_project(client)
    for body in ({"scope": "voiceover", "state": "verified"}, {"scene_id": 1, "state": "verified"}):
        assert client.post(f"/api/workspace/projects/{p['id']}/review", json=body).status_code == 200
    full = client.get(f"/api/workspace/projects/{p['id']}").json()
    assert full["human_reviews"]["script"]["state"] == "unreviewed"
    assert full["technical_ready"]
    started = []
    monkeypatch.setattr(voice.pipeline, "start", lambda *args: started.append(args))
    voice.generation.install(workspace[3])
    assert client.post(f"/api/workspace/projects/{p['id']}/render").status_code == 202
    assert len(started) == 1


def test_catalog_does_not_generate_audio_or_expose_key(workspace, monkeypatch):
    client = setup(workspace, monkeypatch)
    class Provider:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            import httpx
            assert kwargs["headers"]["Authorization"] == "Bearer fixture-secret"
            return httpx.Response(200, request=httpx.Request("GET", url), json={"voices": [
                {"voice_id": "fixture-voice", "name": "Fixture", "preview_url": "https://fixture.invalid/sample.mp3"}]})
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **kwargs: Provider())
    response = client.get("/api/workspace/voices?language=English&search=Fixture")
    assert response.status_code == 200
    assert response.json()["voices"][0]["id"] == "fixture-voice"
    assert "fixture-secret" not in response.text


def test_ai33_uses_elevenlabs_ids_and_provider_for_synthesis(workspace, monkeypatch):
    setup(workspace, monkeypatch)
    if Path(__file__).parent.name == 'tests':
        from app import studio_bridge
    else:
        from . import studio_bridge
    p = create(workspace[0], custom_script='Exact supplied script.')
    p['settings']['voice'] = voice.voice_settings(SETTINGS | {'provider': 'ai33', 'voice_id': 'elevenlabs_fixture-voice'})
    async def synth(text, settings, folder, progress=None):
        assert text == p['script'] and settings['provider'] == 'ai33'
        assert settings['voice_id'] == 'fixture-voice'
        (folder / 'voice.mp3').write_bytes(b'fixture audio')
        return {'file': 'voice.mp3', 'duration': 12, 'words': []}
    mock = AsyncMock(side_effect=synth)
    monkeypatch.setattr(studio_bridge, 'voice', mock)
    asyncio.run(voice.narrate(p))
    assert mock.await_count == 1 and p['voiceover']['provider'] == 'ai33'


def test_new_channel_requires_own_voice_and_keeps_provider(workspace, monkeypatch):
    client = setup(workspace, monkeypatch)
    voice.management.install(workspace[3])
    body = {'name': 'New channel', 'style_id': 'pov-history'}
    assert client.post('/api/workspace/management/channels', json=body).status_code == 422
    response = client.post('/api/workspace/management/channels', json=body | {'voice': SETTINGS | {'provider': 'ai33'}})
    assert response.status_code == 201, response.text
    assert response.json()['voice']['voice_id'] == SETTINGS['voice_id']
    p = create(client, profile_id=response.json()['id'], custom_script='Exact script.')
    assert p['settings']['voice']['provider'] == 'ai33'
