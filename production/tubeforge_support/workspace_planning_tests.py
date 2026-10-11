"""Storyboard contracts, upstream text and image calls isolated."""
import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace, create
    from app import workspace_planning as planning, workspace_generation as generation
else:
    from .workspace_api_tests import workspace, create
    from . import workspace_planning as planning, workspace_generation as generation
from app import channels, llm, pipeline, store
from app.util import write_json


def fictional(workspace):
    client = workspace[0]
    p = store.get_project(create(client, custom_script="You pick up the axe.\nYou walk to the door.")["id"])
    p["profile_id"] = "fictional-test"
    write_json(channels.FILE, [{"id": "fictional-test", "name": "Fiction", "style_id": "pov-history", "workspace_managed": True}])
    p["voiceover"] = {"file": "voice.mp3", "duration": 12}
    (store.project_dir(p["id"]) / "voice.mp3").write_bytes(b"fixture voice")
    words = []
    cursor = 0
    for i, word in enumerate(p["script"].split()):
        start = p["script"].index(word, cursor)
        cursor = start + len(word)
        words.append(dict(w=word, s=i, e=i + .8, c0=start, c1=cursor))
    store.save_words(p["id"], words)
    style = store.get_style("pov-history")
    ref = store.style_dir("pov-history") / "ref.png"
    ref.write_bytes(b"approved fixture reference")
    style["workspace_references"] = [{"path": "ref.png", "role": "style-only", "review_state": "verified",
        "sha256": hashlib.sha256(ref.read_bytes()).hexdigest()}]
    store.save_style(style)
    store.save_project(p)
    return p


def answer(batch):
    return json.dumps({"shots": [dict(id=s["id"], location_id="cabin", characters=["Kratos"],
        prompt="A round white-headed Kratos in leather and fur carries his axe toward the wooden cabin door, clean comic lines and matte colors.") for s in batch]})


def test_prepare_preserves_script_voice_clock_refs_and_never_generates_images(workspace, monkeypatch):
    p = fictional(workspace)
    model, _, refs, shots = planning.inputs(p)
    mock = AsyncMock(return_value=answer(shots))
    monkeypatch.setattr(llm, "chat", mock)
    asyncio.run(planning.prepare(p))
    assert p["scenes"] and p["steps"]["planning"]["state"] == "done"
    assert p["scenes"][0]["start"] == 0 and p["scenes"][-1]["end"] == 12
    assert all(s["text"] in p["script"] and s["references"] == refs for s in p["scenes"])
    assert all(planning.authored(p, s) for s in p["scenes"])
    assert all(not s.get("image") for s in p["scenes"])
    assert mock.call_args.kwargs["model"] == model
    assert mock.call_args.kwargs["attempts"] == 1
    p["scenes"][0]["prompt"] += " Changed"
    assert not planning.authored(p, p["scenes"][0])


def test_historical_channels_remain_manual(workspace):
    p = store.get_project(create(workspace[0], custom_script="Exact story")["id"])
    with pytest.raises(HTTPException):
        planning.inputs(p)
    p["profile_id"] = "renamed-history"
    write_json(channels.FILE, [{"id": "renamed-history", "historical_profile": True}])
    assert not planning.allowed(p)


def test_existing_scenes_missing_clock_and_changed_reference_block(workspace):
    p = fictional(workspace)
    p["scenes"] = [{"id": 77, "prompt": "keep me"}]
    with pytest.raises(HTTPException):
        planning.inputs(p)
    p["scenes"] = []
    (store.style_dir("pov-history") / "ref.png").write_bytes(b"changed")
    with pytest.raises(HTTPException):
        planning.inputs(p)
    store.save_words(p["id"], [])
    with pytest.raises(HTTPException):
        planning.inputs(p)


def test_bad_upstream_publishes_no_partial_plan(workspace, monkeypatch):
    p = fictional(workspace)
    monkeypatch.setattr(llm, "chat", AsyncMock(return_value='{"shots": []}'))
    with pytest.raises(RuntimeError):
        asyncio.run(planning.prepare(p))
    assert not p["scenes"] and not p.get("planning_receipt")


def test_endpoint_requires_snapshot_and_only_starts_preparation(workspace, monkeypatch):
    client, _, _, app = workspace
    planning.install(app)
    p = fictional(workspace)
    start = AsyncMock()
    monkeypatch.setattr(pipeline, "start", lambda *args: start(*args))
    assert client.post(f'/api/workspace/projects/{p["id"]}/images/prepare', json={"script_hash": "old"}).status_code == 409
    called = []
    monkeypatch.setattr(pipeline, "start", lambda *args: called.append(args))
    response = client.post(f'/api/workspace/projects/{p["id"]}/images/prepare', json={"script_hash": planning.api._hash(p["script"])})
    assert response.status_code == 202, response.text
    assert called == [(p["id"], planning.prepare)]


def test_prepared_prompt_is_accepted_by_generation_but_changed_one_is_rejected(workspace, monkeypatch):
    from PIL import Image
    p = fictional(workspace)
    ref = store.style_dir("pov-history") / "ref.png"
    Image.new("RGB", (32, 18), "white").save(ref)
    style = store.get_style("pov-history")
    style["workspace_references"][0]["sha256"] = hashlib.sha256(ref.read_bytes()).hexdigest()
    store.save_style(style)
    _, _, _, shots = planning.inputs(p)
    monkeypatch.setattr(llm, "chat", AsyncMock(return_value=answer(shots)))
    asyncio.run(planning.prepare(p))
    scene = p["scenes"][0]
    body = {"confirm_prompt": scene["prompt"], "image_model": p["model_snapshot"]["image_model"]}
    prepared = generation._prepare(p, scene, body)
    assert prepared[0] == scene["prompt"] and len(prepared[3]) == 1
    scene["prompt"] += " Unrecorded change"
    body["confirm_prompt"] = scene["prompt"]
    with pytest.raises(HTTPException):
        generation._prepare(p, scene, body)
