"""Writer transport, preservation and failure contracts; never call paid services."""
import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace, create
    from app import workspace_writing as writer
else:
    from .workspace_api_tests import workspace, create
    from tubeforge_support import workspace_writing as writer
from app import channels, llm, store
from app.util import write_json


@pytest.fixture
def pilot(workspace, monkeypatch):
    client, _, values, app = workspace
    style = store.default_style("survivor-patch", "Patch")
    style["visuals"]["image_model"] = "fixture-image"
    style["workspace_authoring_mode"] = "codex"
    store.save_style(style)
    write_json(channels.FILE, [{"id": "patch-channel", "name": "Patch", "style_id": style["id"],
                                "language": "English", "workspace_managed": True, "target_minutes": 22}])
    p = create(client, profile_id="patch-channel", style_id="survivor-patch", custom_script="")
    p = store.get_project(p["id"])
    monkeypatch.setattr(writer, "resources", lambda: {"writer": "write", "reviewer": "review", "length_editor": "shorten",
                                                      "skills": "rules", "anchors": [{"raw_excerpt": "real sample"}]})
    writer.install(app)
    return client, p


def prepared(p):
    return writer.request(p, {"minutes": 3, "script_hash": writer.api._hash(p.get("script") or "")})


def response(issues=None):
    return json.dumps({"script": "A concrete sentence. " * 140,
        "story_bible": {key: ["fixture"] for key in
                        ("cast", "locations", "chronology", "setups_and_payoffs", "persistent_states")},
        "audit": {"issues": issues or [], "unsupported_claims": [], "fixes": [], "limitations": ["Model review only"],
                  "groups": {key: {"evidence": "fixture evidence", "findings": []} for key in "ABCDE"}}})


def test_historical_scripts_stay_manual(workspace):
    p = store.get_project(create(workspace[0])["id"])
    assert not writer.allowed(p)
    with pytest.raises(HTTPException) as error:
        writer.request(p, {"script_hash": writer.api._hash("")})
    assert error.value.status_code == 409


@pytest.mark.parametrize("minutes", [True, float("nan"), 0, 31])
def test_invalid_length_rejected_before_proxy(pilot, minutes):
    with pytest.raises(HTTPException) as error:
        writer.request(pilot[1], {"minutes": minutes, "script_hash": writer.api._hash("")})
    assert error.value.status_code == 422


def test_stale_editor_rejected(pilot):
    with pytest.raises(HTTPException) as error:
        writer.request(pilot[1], {"script_hash": "stale"})
    assert error.value.status_code == 409


def test_empty_project_receives_reviewed_script_without_images(pilot, monkeypatch):
    p = pilot[1]
    chat = AsyncMock(side_effect=[response(), response()])
    monkeypatch.setattr(llm, "chat", chat)
    asyncio.run(writer.generate(p, prepared(p)))
    assert chat.await_count == 2
    for call in chat.await_args_list:
        assert call.kwargs["model"] == p["model_snapshot"]["text_model"]
        assert call.kwargs["attempts"] == 1 and call.kwargs["hedge"] is False
    assert p["script"] == json.loads(response())["script"].strip()
    assert p["workspace_story_bible"]["locations"] == ["fixture"]
    assert not p["scenes"] and not p["voiceover"]
    assert p["workspace_script_writer"]["state"] == "applied"


def test_existing_script_and_media_preserved_as_draft(pilot, monkeypatch):
    p = pilot[1]
    p["script"] = "My approved original script."
    p["scenes"] = [{"id": 1, "image": "original.png"}]
    before = copy.deepcopy(p["scenes"])
    monkeypatch.setattr(llm, "chat", AsyncMock(side_effect=[response(), response()]))
    asyncio.run(writer.generate(p, prepared(p)))
    assert p["script"] == "My approved original script." and p["scenes"] == before
    assert p["workspace_script_writer"]["state"] == "draft_ready"
    draft = p["workspace_script_writer"]["draft"]
    with pytest.raises(HTTPException) as error:
        writer.apply(p, draft, writer.api._hash(p["script"]))
    assert error.value.status_code == 409


def test_remaining_model_issue_prevents_automatic_adoption(pilot, monkeypatch):
    p = pilot[1]
    monkeypatch.setattr(llm, "chat", AsyncMock(side_effect=[response(), response(["Unclosed route loop"])]))
    asyncio.run(writer.generate(p, prepared(p)))
    assert not p["script"] and p["workspace_script_writer"]["state"] == "draft_ready"


def test_upstream_error_is_sanitized_and_not_retried(pilot, monkeypatch):
    p = pilot[1]
    p["script"] = "Preserve me."
    chat = AsyncMock(side_effect=RuntimeError("Authorization: Bearer SECRET-fixture"))
    monkeypatch.setattr(llm, "chat", chat)
    with pytest.raises(RuntimeError) as error:
        asyncio.run(writer.generate(p, prepared(p)))
    assert "SECRET" not in str(error.value)
    assert chat.await_count == 1 and p["script"] == "Preserve me."
    assert p["steps"]["script"]["state"] == "error"


def test_incomplete_story_bible_cannot_be_applied(pilot, monkeypatch):
    p = pilot[1]
    data = json.loads(response())
    data["story_bible"].pop("persistent_states")
    chat = AsyncMock(return_value=json.dumps(data))
    monkeypatch.setattr(llm, "chat", chat)
    with pytest.raises(RuntimeError):
        asyncio.run(writer.generate(p, prepared(p)))
    assert not p["script"] and chat.await_count == 1


def test_adoption_requires_current_script_hash(pilot):
    p = pilot[1]
    with pytest.raises(HTTPException) as error:
        writer.apply(p, {"id": "draft", "script": "new"}, "stale")
    assert error.value.status_code == 409 and not p["script"]


def test_long_first_draft_reaches_length_review(pilot, monkeypatch):
    p = pilot[1]
    first = json.loads(response())
    first["script"] *= 2
    chat = AsyncMock(side_effect=[json.dumps(first), response()])
    monkeypatch.setattr(llm, "chat", chat)
    asyncio.run(writer.generate(p, prepared(p)))
    assert chat.await_count == 2 and len(p["script"].split()) == 420


def test_audit_group_finding_cannot_hide_behind_empty_issue_list(pilot, monkeypatch):
    p = pilot[1]
    reviewed = json.loads(response())
    reviewed["audit"]["groups"]["B"]["findings"] = ["The exit loop is open"]
    monkeypatch.setattr(llm, "chat", AsyncMock(side_effect=[response(), json.dumps(reviewed)]))
    asyncio.run(writer.generate(p, prepared(p)))
    assert not p["script"]
    assert "The exit loop is open" in p["workspace_script_writer"]["draft"]["audit"]["issues"]


def test_tiny_word_split_difference_does_not_discard_completed_review(pilot):
    data = json.loads(response())
    data["script"] = "word " * 523
    result = writer.output(json.dumps(data), prepared(pilot[1]), audited=True)
    assert len(result["script"].split()) == 523
    data["script"] = "word " * 600
    with pytest.raises(ValueError):
        writer.output(json.dumps(data), prepared(pilot[1]), audited=True)


def test_long_review_gets_one_length_edit_with_measured_count(pilot, monkeypatch):
    p = pilot[1]
    long_review = json.loads(response())
    long_review["script"] = "word " * 638
    chat = AsyncMock(side_effect=[response(), json.dumps(long_review), response()])
    monkeypatch.setattr(llm, "chat", chat)
    asyncio.run(writer.generate(p, prepared(p)))
    assert chat.await_count == 3 and len(p["script"].split()) == 420
    instruction = json.loads(chat.await_args_list[2].args[0][1]["content"])
    assert instruction["actual_narration_word_count"] == 638
    assert chat.await_args_list[2].kwargs["attempts"] == 1
    assert chat.await_args_list[2].kwargs["hedge"] is False


def test_unresolved_length_is_saved_as_draft_instead_of_losing_text(pilot, monkeypatch):
    p = pilot[1]
    long_result = json.loads(response())
    long_result["script"] = "word " * 638
    chat = AsyncMock(side_effect=[response(), json.dumps(long_result), json.dumps(long_result)])
    monkeypatch.setattr(llm, "chat", chat)
    asyncio.run(writer.generate(p, prepared(p)))
    assert chat.await_count == 3 and not p["script"]
    assert p["workspace_script_writer"]["draft"]["word_count"] == 638
    assert p["workspace_script_writer"]["draft"]["audit"]["issues"]


def test_http_writer_route_precedes_static_mount_and_preserves_project(pilot, monkeypatch):
    client, p = pilot
    calls = []
    monkeypatch.setattr(writer.pipeline, "start", lambda *args: calls.append(args))
    r = client.post(f"/api/workspace/projects/{p['id']}/script/generate",
                    json={"minutes": 3, "script_hash": writer.api._hash("")})
    assert r.status_code == 200 and r.json()["can_write_script"] is True
    assert len(calls) == 1 and calls[0][0] == p["id"]
    assert not p["script"] and not p["scenes"]


def test_http_adoption_uses_current_draft_and_text_hash(pilot):
    client, p = pilot
    result = json.loads(response())
    p["workspace_script_writer"] = {"draft": {**result, "id": "fixture-draft", "title": "A night"}}
    store.save_project(p)
    r = client.post(f"/api/workspace/projects/{p['id']}/script/apply-draft",
                    json={"draft_id": "fixture-draft", "script_hash": writer.api._hash("")})
    assert r.status_code == 200 and len(r.json()["script"].split()) == 420
    assert r.json()["workspace_script_writer"]["state"] == "applied"
