"""One-plan execution contracts, using only mocked image requests."""
import asyncio
import copy
import io
from pathlib import Path
from unittest.mock import AsyncMock
from fastapi import HTTPException

import pytest
from PIL import Image

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace, create, api, store, llm
    from app import workspace_generation as generation
else:
    from .workspace_api_tests import workspace, create, api, store, llm
    from . import workspace_generation as generation


def prepared_plan(workspace):
    client, _, _, app = workspace
    generation.install(app)
    generation.install(app)
    p = create(client, custom_script="The shopkeeper opens the door.")
    directory = store.project_dir(p["id"])
    Image.new("RGB", (32, 18), "white").save(directory / "reference.png")
    Image.new("RGB", (32, 18), "green").save(directory / "previous.png")
    p["scenes"] = [{"id": 1, "text": p["script"], "location_id": "shop", "characters": ["shopkeeper"],
                    "prompt": "Exact prompt written by Codex.", "prompt_author": "codex", "start": 0, "end": 6,
                    "references": [{"path": "reference.png", "owner": "project"}], "image": "previous.png"}]
    store.save_project(p)
    return client, p


def test_confirmed_plan_uses_exact_prompt_and_keeps_previous_image(workspace, monkeypatch):
    client, p = prepared_plan(workspace)
    stream = io.BytesIO()
    Image.new("RGB", (32, 18), "blue").save(stream, format="PNG")
    request = AsyncMock(return_value=stream.getvalue())
    monkeypatch.setattr(llm, "generate_image", request)
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={
        "confirm_prompt": p["scenes"][0]["prompt"], "image_model": p["model_snapshot"]["image_model"]})
    assert response.status_code == 200, response.text
    scene = response.json()["scenes"][0]
    assert request.await_count == 1
    assert request.call_args.args == (p["scenes"][0]["prompt"],)
    assert request.call_args.kwargs["model"] == p["model_snapshot"]["image_model"]
    assert request.call_args.kwargs["attempts"] == 1
    assert len(request.call_args.kwargs["refs"]) == 1
    assert scene["human_review"]["state"] == "unreviewed"
    assert scene["generation_receipt"]["references"][0]["path"] == "reference.png"
    assert (store.project_dir(p["id"]) / "previous.png").exists()
    assert scene["image"] != "previous.png"
    assert not response.json()["publication_ready"]


@pytest.mark.parametrize("change", ["prompt", "model", "refs", "author", "running"])
def test_unsafe_generation_rejected_without_request(workspace, monkeypatch, change):
    client, p = prepared_plan(workspace)
    request = AsyncMock()
    monkeypatch.setattr(llm, "generate_image", request)
    body = {"confirm_prompt": p["scenes"][0]["prompt"], "image_model": p["model_snapshot"]["image_model"]}
    if change == "prompt":
        body["confirm_prompt"] = "Other prompt."
    elif change == "model":
        body["image_model"] = "other-model"
    elif change == "refs":
        p["scenes"][0]["references"] = []
    elif change == "author":
        p["scenes"][0]["prompt_author"] = "automatic"
    else:
        p["scenes"][0]["status"] = "running"
    store.save_project(p)
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json=body)
    assert response.status_code in (409, 422)
    request.assert_not_awaited()


def test_generation_failure_preserves_previous_asset_and_hides_errors(workspace, monkeypatch):
    client, p = prepared_plan(workspace)
    monkeypatch.setattr(llm, "generate_image", AsyncMock(side_effect=RuntimeError("private upstream detail")))
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={
        "confirm_prompt": p["scenes"][0]["prompt"], "image_model": p["model_snapshot"]["image_model"]})
    assert response.status_code == 502 and "private upstream" not in response.text
    assert store.get_project(p["id"])["scenes"][0]["image"] == "previous.png"
    assert (store.project_dir(p["id"]) / "previous.png").exists()


def test_flow_scene_pins_provider_and_records_actual_account(workspace, monkeypatch):
    client, p = prepared_plan(workspace)
    p["model_snapshot"]["image_provider"] = "google_flow"
    store.save_project(p)
    monkeypatch.setattr(generation.google_flow, "configured", lambda: True)
    stream = io.BytesIO()
    Image.new("RGB", (32, 18), "blue").save(stream, format="JPEG")
    async def generate(*args, **kwargs):
        assert kwargs["provider"] == "google_flow" and kwargs["attempts"] == 1
        kwargs["receipt"].update(account="account@example.invalid", count=1)
        return stream.getvalue()
    request = AsyncMock(side_effect=generate)
    monkeypatch.setattr(llm, "generate_image", request)
    body = {"confirm_prompt": p["scenes"][0]["prompt"], "image_model": p["model_snapshot"]["image_model"]}
    rejected = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={**body, "image_provider": "cli_proxy"})
    assert rejected.status_code == 409 and request.await_count == 0
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={**body, "image_provider": "google_flow"})
    assert response.status_code == 200, response.text
    scene = response.json()["scenes"][0]
    assert scene["image"].endswith(".jpg")
    assert scene["generation_receipt"]["provider_receipt"]["account"] == "account@example.invalid"
    assert scene["generation_receipt"]["transport"] == "google_flow"


def batch_project(workspace, preview_ready=False):
    client, p = prepared_plan(workspace)
    template = p["scenes"][0]
    p["script"] = " ".join(f"Action {i}." for i in range(7))
    p["scenes"] = [copy.deepcopy(template) | {"id": sid, "text": f"Action {i}.",
        "prompt": f"Authored scene {i}.", "image": "previous.png" if preview_ready and i < 3 else None,
        "start": i * 6, "end": (i + 1) * 6} for i, sid in enumerate([17, 4, 9, 21, 5, 8, 2])]
    if preview_ready:
        for scene in p["scenes"][:3]:
            scene["human_review"] = {"state": "verified", "evidence": api._scene_evidence(p, scene)}
    store.save_project(p)
    stream = io.BytesIO()
    Image.new("RGB", (32, 18), "blue").save(stream, format="PNG")
    return client, p, stream.getvalue()


def batch_body(p, phase="preview"):
    return {"phase": phase, "confirmation": api._generation_confirmation(p),
            "image_model": p["model_snapshot"]["image_model"]}


def test_preview_endpoint_generates_first_three_in_order(workspace, monkeypatch):
    import time
    client, p, data = batch_project(workspace)
    request = AsyncMock(return_value=data)
    monkeypatch.setattr(llm, "generate_image", request)
    response = client.post(f"/api/workspace/projects/{p['id']}/images/generate", json=batch_body(p))
    assert response.status_code == 202, response.text
    for _ in range(200):
        latest = client.get(f"/api/workspace/projects/{p['id']}").json()
        if not latest["running"]:
            break
        time.sleep(.005)
    assert latest["workspace_batch"]["state"] == "done"
    assert latest["workspace_batch"]["scene_ids"] == [17, 4, 9]
    assert latest["workspace_batch"]["done"] == 3
    assert all(s["image_available"] for s in latest["scenes"][:3])
    assert all(not s["image_available"] for s in latest["scenes"][3:])
    assert [c.args[0] for c in request.await_args_list] == [s["prompt"] for s in p["scenes"][:3]]
    assert not latest["publication_ready"]


@pytest.mark.parametrize("unsafe", ["stale", "unreviewed", "missing-reference", "missing-prompt", "model", "phase"])
def test_batch_preflight_rejects_before_paid_requests(workspace, monkeypatch, unsafe):
    _, p, _ = batch_project(workspace, preview_ready=True)
    request = AsyncMock()
    monkeypatch.setattr(llm, "generate_image", request)
    body = batch_body(p, "remaining")
    if unsafe == "stale":
        body["confirmation"] = "stale-confirmation"
    elif unsafe == "unreviewed":
        p["scenes"][0]["human_review"] = {"state": "unreviewed"}
    elif unsafe == "missing-reference":
        p["scenes"][-1]["references"] = [{"owner": "project", "path": "absent.png"}]
    elif unsafe == "missing-prompt":
        p["scenes"][-1]["prompt"] = ""
    elif unsafe == "model":
        body["image_model"] = "wrong-fixture-model"
    else:
        body["phase"] = "all"
    store.save_project(p)
    if unsafe != "stale":
        body["confirmation"] = api._generation_confirmation(p)
    async def run():
        with pytest.raises(HTTPException):
            await generation.start_batch(p["id"], body)
    asyncio.run(run())
    request.assert_not_awaited()


def test_remaining_preserves_approved_and_existing_images(workspace, monkeypatch):
    _, p, data = batch_project(workspace, preview_ready=True)
    p["scenes"][4]["image"] = "previous.png"
    store.save_project(p)
    request = AsyncMock(return_value=data)
    monkeypatch.setattr(llm, "generate_image", request)
    async def run():
        await generation.start_batch(p["id"], batch_body(p, "remaining"))
        await generation._batch_tasks[p["id"]]
    asyncio.run(run())
    latest = api._full(store.get_project(p["id"]))
    assert latest["workspace_batch"]["done"] == 3
    assert latest["workspace_batch"]["state"] == "done"
    assert all(s["human_review"]["state"] == "verified" and s["image"] == "previous.png" for s in latest["scenes"][:3])
    assert latest["scenes"][4]["image"] == "previous.png"
    assert request.await_count == 3


def test_failure_stops_without_retry_and_resume_skips_successes(workspace, monkeypatch):
    _, p, data = batch_project(workspace)
    request = AsyncMock(side_effect=[data, RuntimeError("private failure"), data, data])
    monkeypatch.setattr(llm, "generate_image", request)
    async def run():
        await generation.start_batch(p["id"], batch_body(p))
        await generation._batch_tasks[p["id"]]
        failed = store.get_project(p["id"])
        assert failed["workspace_batch"]["state"] == "failed"
        assert failed["workspace_batch"]["done"] == 1 and request.await_count == 2
        assert "private failure" not in failed["workspace_batch"]["error"]
        selected = failed["scenes"][0]["image"]
        await generation.start_batch(p["id"], batch_body(failed))
        await generation._batch_tasks[p["id"]]
        latest = store.get_project(p["id"])
        assert latest["workspace_batch"]["scene_ids"] == [4, 9]
        assert latest["workspace_batch"]["state"] == "done"
        assert latest["scenes"][0]["image"] == selected
    asyncio.run(run())


@pytest.mark.parametrize("change", ["stop", "prompt", "reference", "preview-review"])
def test_batch_stops_on_request_or_changed_inputs(workspace, monkeypatch, change):
    _, p, data = batch_project(workspace, preview_ready=change == "preview-review")
    phase = "remaining" if change == "preview-review" else "preview"
    async def image(*args, **kwargs):
        latest = copy.deepcopy(store.get_project(p["id"]))
        if change == "stop":
            latest["workspace_batch"]["stop_requested"] = True
        elif change == "prompt":
            latest["scenes"][-1]["prompt"] = "Edited during the first request"
        elif change == "reference":
            Image.new("RGB", (32, 18), "red").save(store.project_dir(p["id"]) / "reference.png")
        else:
            latest["scenes"][0]["human_review"] = {"state": "unreviewed"}
        store.save_project(latest)
        return data
    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)
    async def run():
        await generation.start_batch(p["id"], batch_body(p, phase))
        with pytest.raises(HTTPException) as exc:
            await generation.start_batch(p["id"], batch_body(p, phase))
        assert exc.value.status_code == 409
        with pytest.raises(HTTPException):
            await generation.generate(p["id"], p["scenes"][-1]["id"], {})
        await generation._batch_tasks[p["id"]]
    asyncio.run(run())
    latest = store.get_project(p["id"])
    assert latest["workspace_batch"]["state"] == ("stopped" if change == "stop" else "failed")
    assert request.await_count == 1


def test_interrupted_batch_can_be_recovered_explicitly(workspace, monkeypatch):
    _, p, data = batch_project(workspace)
    p["workspace_batch"] = {"id": "old-batch", "state": "running", "phase": "preview"}
    p["workspace_generation"] = {"id": "old-request", "batch_id": "old-batch"}
    p["scenes"][0].update(status="running", generation_id="old-request")
    p["steps"]["visuals"]["state"] = "running"
    store.save_project(p)
    assert api._full(p)["workspace_batch"]["state"] == "interrupted"
    monkeypatch.setattr(llm, "generate_image", AsyncMock(return_value=data))
    async def run():
        await generation.start_batch(p["id"], batch_body(p))
        await generation._batch_tasks[p["id"]]
    asyncio.run(run())
    assert store.get_project(p["id"])["workspace_batch"]["state"] == "done"


def test_render_requires_verified_complete_assets(workspace, monkeypatch):
    client, p, _ = batch_project(workspace, preview_ready=True)
    from unittest.mock import Mock
    start = Mock()
    monkeypatch.setattr(generation.pipeline, "start", start)
    url = f"/api/workspace/projects/{p['id']}/render"
    assert client.post(url).status_code == 409
    start.assert_not_called()
    directory = store.project_dir(p["id"])
    (directory / "voice.mp3").write_bytes(b"fixture voice")
    p["voiceover"] = {"file": "voice.mp3", "duration": 42}
    for scene in p["scenes"]:
        scene["image"] = "previous.png"
        scene["human_review"] = {"state": "verified", "evidence": api._scene_evidence(p, scene)}
    p["human_reviews"] = {scope: {"state": "verified", "evidence": api._scope_evidence(p, scope)} for scope in ("script", "voiceover")}
    store.save_project(p)
    assert client.post(url).status_code == 202
    start.assert_called_once_with(p["id"], generation.pipeline.do_render)


def test_stop_endpoint_finishes_current_request_without_starting_another(workspace, monkeypatch):
    import time
    client, p, data = batch_project(workspace)
    async def image(*args, **kwargs):
        await asyncio.sleep(.1)
        return data
    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)
    url = f"/api/workspace/projects/{p['id']}"
    assert client.post(url + "/images/stop").status_code == 409
    assert client.post(url + "/images/generate", json=batch_body(p)).status_code == 202
    response = client.post(url + "/images/stop")
    assert response.status_code == 200 and response.json()["workspace_batch"]["stop_requested"]
    for _ in range(200):
        latest = client.get(url).json()
        if not latest["running"]:
            break
        time.sleep(.005)
    assert latest["workspace_batch"]["state"] == "stopped"
    assert request.await_count <= 1
    assert latest["workspace_batch"]["done"] == request.await_count


def test_prompt_correction_keeps_existing_generation_receipts(workspace, monkeypatch):
    client, p, data = batch_project(workspace)
    monkeypatch.setattr(llm, "generate_image", AsyncMock(return_value=data))
    async def run():
        await generation.start_batch(p["id"], batch_body(p))
        await generation._batch_tasks[p["id"]]
    asyncio.run(run())
    latest = api._full(store.get_project(p["id"]))
    old_scene = copy.deepcopy(latest["scenes"][0])
    latest["scenes"][0]["prompt"] = "A manually corrected prompt."
    response = client.put(f"/api/workspace/projects/{p['id']}/scenes", json={"scenes": latest["scenes"]})
    assert response.status_code == 200, response.text
    scene = response.json()["scenes"][0]
    for key in ("image", "generation_receipt", "generation_history", "sent_references"):
        assert scene[key] == old_scene[key]
