"""One-plan execution contracts, using only mocked image requests."""
import asyncio
import copy
import io
from pathlib import Path
from unittest.mock import AsyncMock
from fastapi import HTTPException

import httpx
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


@pytest.mark.parametrize("aspect,prompt", [("9:16", "Physical wide scene"),
    ("16:9", "Use a portrait composition."), ("16:9", "A translucent warrior reaches toward his family.")])
def test_fictional_manual_plan_blocks_wrong_composition_before_request(workspace, monkeypatch, aspect, prompt):
    import importlib
    workspace_planning = importlib.import_module(generation.__package__ + ".workspace_planning")
    client, p = prepared_plan(workspace)
    monkeypatch.setattr(workspace_planning, "allowed", lambda project: True)
    p["settings"]["visuals"]["aspect"] = aspect
    p["scenes"][0]["prompt"] = prompt
    store.save_project(p)
    request = AsyncMock()
    monkeypatch.setattr(llm, "generate_image", request)
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={
        "confirm_prompt": prompt, "image_model": p["model_snapshot"]["image_model"]})
    assert response.status_code == 422
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


def test_remaining_regenerates_flagged_existing_images_and_skips_good_ones(workspace, monkeypatch):
    _, p, data = batch_project(workspace, preview_ready=True)
    for scene in p["scenes"][3:]:
        scene.update(image="previous.png", generation_receipt={"id": "previous-" + str(scene["id"])})
    targets = [p["scenes"][3], p["scenes"][5]]
    for scene in targets:
        scene["workspace_regeneration_required"] = True
    old = {scene["id"]: copy.deepcopy(scene["generation_receipt"]) for scene in targets}
    store.save_project(p)
    request = AsyncMock(return_value=data)
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        await generation.start_batch(p["id"], batch_body(p, "remaining"))
        await generation._batch_tasks[p["id"]]

    asyncio.run(run())
    latest = store.get_project(p["id"])
    assert latest["workspace_batch"]["state"] == "done" and latest["workspace_batch"]["done"] == 2
    assert latest["workspace_batch"]["scene_ids"] == [21, 8]
    assert [call.args[0] for call in request.await_args_list] == [scene["prompt"] for scene in targets]
    for scene in latest["scenes"]:
        if scene["id"] in old:
            assert scene["image"] != "previous.png" and "workspace_regeneration_required" not in scene
            previous = scene["generation_receipt"]["previous_image"]
            assert previous["path"] == "previous.png" and previous["generation_receipt"] == old[scene["id"]]
        else:
            assert scene["image"] == "previous.png"
    assert (store.project_dir(p["id"]) / "previous.png").is_file()


def test_flagged_regeneration_failure_keeps_selected_old_image_and_retry_flag(workspace, monkeypatch):
    _, p, _ = batch_project(workspace, preview_ready=True)
    for scene in p["scenes"][3:]:
        scene["image"] = "previous.png"
    target = p["scenes"][3]
    target.update(workspace_regeneration_required=True, generation_receipt={"id": "old-selected-receipt"})
    old_receipt = copy.deepcopy(target["generation_receipt"])
    store.save_project(p)
    request = AsyncMock(side_effect=RuntimeError("private fixture failure"))
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        await generation.start_batch(p["id"], batch_body(p, "remaining"))
        await generation._batch_tasks[p["id"]]

    asyncio.run(run())
    latest = store.get_project(p["id"])
    assert latest["workspace_batch"]["state"] == "failed" and latest["workspace_batch"]["done"] == 0
    assert request.await_count == 1
    failed = latest["scenes"][3]
    assert failed["image"] == "previous.png" and failed["workspace_regeneration_required"] is True
    assert failed["generation_receipt"] == old_receipt
    assert (store.project_dir(p["id"]) / "previous.png").is_file()


def test_regeneration_flag_edit_during_request_rejects_obsolete_output(workspace, monkeypatch):
    _, p, data = batch_project(workspace, preview_ready=True)
    target = p["scenes"][3]
    target.update(image="previous.png", workspace_regeneration_required=True)
    store.save_project(p)

    async def image(*args, **kwargs):
        current = copy.deepcopy(store.get_project(p["id"]))
        current["scenes"][3].pop("workspace_regeneration_required")
        store.save_project(current)
        return data

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)
    body = {"confirm_prompt": target["prompt"], "image_model": p["model_snapshot"]["image_model"]}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(generation.generate(p["id"], target["id"], body))
    assert exc.value.status_code == 409
    latest = store.get_project(p["id"])
    assert latest["scenes"][3]["image"] == "previous.png"
    assert latest["workspace_generation_history"][-1]["state"] == "obsolete_unselected"


def correction_project(workspace):
    _, p, data = batch_project(workspace, preview_ready=True)
    for shot in p["scenes"][3:]:
        shot.update(image="previous.png", generation_receipt={"id": "old-" + str(shot["id"])})
    p["scenes"][3]["workspace_regeneration_required"] = True
    p["scenes"][5]["workspace_regeneration_required"] = True
    p["scenes"][4]["image"] = None  # Missing but not flagged: corrections must not generate it.
    store.save_project(p)
    return p, data


def test_corrections_target_only_flagged_shots_after_verified_preview(workspace, monkeypatch):
    p, data = correction_project(workspace)
    request = AsyncMock(return_value=data)
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        await generation.start_batch(p["id"], batch_body(p, "corrections"))
        await generation._batch_tasks[p["id"]]

    asyncio.run(run())
    latest = store.get_project(p["id"])
    job = latest["workspace_batch"]
    assert job["state"] == "done" and job["scene_ids"] == [21, 8]
    assert job["done"] == job["processed"] == 2
    assert job["failed_scene_ids"] == [] and job["scene_errors"] == {}
    assert latest["scenes"][4]["image"] is None
    assert latest["scenes"][6]["image"] == "previous.png"
    assert all(shot["image"] == "previous.png" for shot in latest["scenes"][:3])
    assert [call.args[0] for call in request.await_args_list] == [p["scenes"][i]["prompt"] for i in (3, 5)]
    assert all(call.kwargs["attempts"] == 1 for call in request.await_args_list)


@pytest.mark.parametrize("error", [generation.google_flow.FlowError(
    "Google Flow est indisponible ou a refusé la requête (HTTP 400).", 400),
    HTTPException(502, "private upstream response must stay hidden")])
def test_corrections_continue_after_one_failed_attempt_without_rewriting_or_retry(workspace, monkeypatch, error):
    p, data = correction_project(workspace)
    old = copy.deepcopy(p["scenes"][3])
    request = AsyncMock(side_effect=[error, data])
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        await generation.start_batch(p["id"], batch_body(p, "corrections"))
        await generation._batch_tasks[p["id"]]

    asyncio.run(run())
    latest = store.get_project(p["id"])
    job = latest["workspace_batch"]
    assert job["state"] == "done_with_errors" and job["done"] == 1 and job["processed"] == 2
    assert job["failed_scene_ids"] == [21] and set(job["scene_errors"]) == {"21"}
    assert "private upstream" not in job["scene_errors"]["21"]
    if isinstance(error, generation.google_flow.FlowError):
        assert job["scene_errors"]["21"] == str(error)
    failed, succeeded = latest["scenes"][3], latest["scenes"][5]
    assert failed["image"] == old["image"] and failed["generation_receipt"] == old["generation_receipt"]
    assert failed["workspace_regeneration_required"] is True
    assert succeeded["image"] != "previous.png" and "workspace_regeneration_required" not in succeeded
    assert succeeded["generation_receipt"]["previous_image"]["path"] == "previous.png"
    assert latest["scenes"][4]["image"] is None and latest["scenes"][6]["image"] == "previous.png"
    assert request.await_count == 2
    assert [call.args[0] for call in request.await_args_list] == [p["scenes"][i]["prompt"] for i in (3, 5)]
    assert all(call.kwargs["attempts"] == 1 and call.kwargs["model"] == p["model_snapshot"]["image_model"]
               for call in request.await_args_list)


@pytest.mark.parametrize("change", ["prompt", "reference", "preview-review", "stop"])
def test_corrections_stop_instead_of_continuing_after_failure_when_inputs_change(workspace, monkeypatch, change):
    p, _ = correction_project(workspace)

    async def image(*args, **kwargs):
        current = copy.deepcopy(store.get_project(p["id"]))
        if change == "prompt":
            current["scenes"][5]["prompt"] = "Authored prompt changed during the first request."
        elif change == "reference":
            Image.new("RGB", (32, 18), "red").save(store.project_dir(p["id"]) / "reference.png")
        elif change == "preview-review":
            current["scenes"][0]["human_review"] = {"state": "unreviewed"}
        else:
            current["workspace_batch"]["stop_requested"] = True
        store.save_project(current)
        raise generation.google_flow.FlowError("Google Flow est indisponible ou a refusé la requête (HTTP 400).", 400)

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        await generation.start_batch(p["id"], batch_body(p, "corrections"))
        await generation._batch_tasks[p["id"]]

    asyncio.run(run())
    job = store.get_project(p["id"])["workspace_batch"]
    assert job["state"] == ("stopped" if change == "stop" else "failed")
    assert job["processed"] == 1 and job["done"] == 0 and job["failed_scene_ids"] == [21]
    assert request.await_count == 1


def test_corrections_require_reviewed_preview_before_any_request(workspace, monkeypatch):
    p, _ = correction_project(workspace)
    p["scenes"][0]["human_review"] = {"state": "unreviewed"}
    store.save_project(p)
    request = AsyncMock()
    monkeypatch.setattr(llm, "generate_image", request)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(generation.start_batch(p["id"], batch_body(p, "corrections")))
    assert exc.value.status_code == 409
    request.assert_not_awaited()


def concurrent_project(workspace, monkeypatch, phase="remaining", provider="google_flow"):
    _, p, data = batch_project(workspace, preview_ready=phase != "preview")
    p["model_snapshot"]["image_provider"] = provider
    template = copy.deepcopy(p["scenes"][-1])
    for i, sid in enumerate([11, 12, 13], 7):
        p["scenes"].append(dict(template, id=sid, text=f"Action {i}.", prompt=f"Authored scene {i}.",
                                image=None, start=i * 6, end=(i + 1) * 6))
    p["script"] = " ".join(shot["text"] for shot in p["scenes"])
    if phase != "preview":
        for shot in p["scenes"][:3]:
            shot["human_review"] = {"state": "verified", "evidence": api._scene_evidence(p, shot)}
    if phase == "corrections":
        for shot in p["scenes"][3:]:
            shot.update(image="previous.png", workspace_regeneration_required=True,
                        generation_receipt={"id": "old-" + str(shot["id"])})
    store.save_project(p)
    monkeypatch.setattr(generation.google_flow, "configured", lambda: True)
    return p, data


async def turns_until(predicate):
    # Deterministic event-loop yielding, no wall-clock waits or real network calls.
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("Expected mocked task transition did not happen")


def test_flow_batch_bounded_three_reverse_results_preserve_all_receipts_and_pilot_reviews(workspace, monkeypatch):
    p, data = concurrent_project(workspace, monkeypatch, "corrections")
    active, maximum = 0, 0
    entered, releases, returned = {}, {}, []

    async def image(prompt, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        entered[prompt].set()
        assert kwargs["provider"] == "google_flow" and kwargs["attempts"] == 1
        assert kwargs["model"] == p["model_snapshot"]["image_model"] and len(kwargs["refs"]) == 1
        kwargs["receipt"]["account"] = prompt
        try:
            await releases[prompt].wait()
            returned.append(prompt)
            return data
        finally:
            active -= 1

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        prompts = [shot["prompt"] for shot in p["scenes"][3:]]
        entered.update({prompt: asyncio.Event() for prompt in prompts})
        releases.update({prompt: asyncio.Event() for prompt in prompts})
        await generation.start_batch(p["id"], batch_body(p, "corrections"))
        batch = generation._batch_tasks[p["id"]]
        await asyncio.gather(*(entered[prompt].wait() for prompt in prompts[:3]))
        assert active == 3 and request.await_count == 3
        for early, replacement in [(2, 3), (1, 4), (0, 5)]:
            releases[prompts[early]].set()
            await entered[prompts[replacement]].wait()
            assert active == 3
        for prompt in prompts:
            releases[prompt].set()
        await batch

    asyncio.run(run())
    latest = store.get_project(p["id"])
    assert maximum == 3 and active == 0
    assert returned[:3] == [p["scenes"][i]["prompt"] for i in (5, 4, 3)]
    assert request.await_count == 7
    job = latest["workspace_batch"]
    assert job["state"] == "done" and job["done"] == job["processed"] == 7
    assert job["current_scene_ids"] == [] and job["concurrency"] == 3
    paths = []
    for shot in latest["scenes"][3:]:
        receipt = shot["generation_receipt"]
        assert receipt["prompt"] == shot["prompt"] and receipt["provider_receipt"]["account"] == shot["prompt"]
        assert receipt["previous_image"]["generation_receipt"] == {"id": "old-" + str(shot["id"])}
        assert len(shot["generation_history"]) == 1 and shot["human_review"]["state"] == "unreviewed"
        assert latest["workspace_generations"][str(shot["id"])]["state"] == "generated_unreviewed"
        paths.append(shot["image"])
    assert len(set(paths)) == 7 and all((store.project_dir(p["id"]) / path).exists() for path in paths)
    assert all(shot["image"] == "previous.png" and shot["human_review"]["state"] == "verified"
               for shot in latest["scenes"][:3])
    assert p["id"] not in generation._active_projects and not generation._other_generations(p["id"])


@pytest.mark.parametrize("provider,phase", [("google_flow", "preview"), ("cli_proxy", "remaining")])
def test_preview_and_cli_batches_remain_sequential(workspace, monkeypatch, provider, phase):
    p, data = concurrent_project(workspace, monkeypatch, phase, provider)
    active, maximum = 0, 0

    async def image(*args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return data

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        await generation.start_batch(p["id"], batch_body(p, phase))
        await generation._batch_tasks[p["id"]]

    asyncio.run(run())
    assert maximum == 1 and active == 0
    assert store.get_project(p["id"])["workspace_batch"]["concurrency"] == 1
    assert request.await_count == (3 if phase == "preview" else 7)


@pytest.mark.parametrize("action", ["stop", "cancel"])
def test_flow_batch_stop_closes_admission_and_waits_for_three_live_calls(workspace, monkeypatch, action):
    p, data = concurrent_project(workspace, monkeypatch)
    active, entered_count, cancelled = 0, 0, []

    async def image(*args, **kwargs):
        nonlocal active, entered_count
        active += 1
        entered_count += 1
        if entered_count == 3:
            entered.set()
        try:
            await release.wait()
            return data
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        finally:
            active -= 1

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)
    entered = release = None

    async def run():
        nonlocal entered, release
        entered, release = asyncio.Event(), asyncio.Event()
        await generation.start_batch(p["id"], batch_body(p, "remaining"))
        batch = generation._batch_tasks[p["id"]]
        await entered.wait()
        current = api._project(p["id"])
        if action == "stop":
            generation._update_batch(p["id"], current["workspace_batch"]["id"], stop_requested=True, state="stopping")
        else:
            batch.cancel()
            await asyncio.sleep(0)
        assert generation.batch_running(p["id"]) and active == 3
        with pytest.raises(HTTPException):
            await generation.generate(p["id"], 11, {})
        with pytest.raises(HTTPException):
            api._project(p["id"], writable=True)
        release.set()
        await batch

    asyncio.run(run())
    latest = store.get_project(p["id"])
    assert latest["workspace_batch"]["state"] == ("stopped" if action == "stop" else "interrupted")
    assert latest["workspace_batch"]["done"] == latest["workspace_batch"]["processed"] == 3
    assert request.await_count == 3 and active == 0 and not cancelled
    assert all(shot["image"] for shot in latest["scenes"][3:6])
    assert all(not shot["image"] for shot in latest["scenes"][6:])
    assert not generation.batch_running(p["id"]) and p["id"] not in generation._active_projects


@pytest.mark.parametrize("phase", ["remaining", "corrections"])
def test_missing_captcha_configuration_stops_admission_and_drains_started_calls(workspace, monkeypatch, phase):
    p, data = concurrent_project(workspace, monkeypatch, phase)
    first, second, third = [shot["prompt"] for shot in p["scenes"][3:6]]
    entered_count = 0
    entered = fail = release_second = release_third = None
    provider_error = generation.google_flow._error(httpx.Response(400, json={
        "error": "No captcha provider API keys configured. Add at least one at "
                 "https://example.invalid/?key=private-key&email=private-account@example.invalid"}))

    async def image(prompt, **kwargs):
        nonlocal entered_count
        entered_count += 1
        if entered_count == 3:
            entered.set()
        if prompt == first:
            await fail.wait()
            raise provider_error
        await (release_second if prompt == second else release_third).wait()
        return data

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)

    async def run():
        nonlocal entered, fail, release_second, release_third
        entered, fail, release_second, release_third = [asyncio.Event() for _ in range(4)]
        await generation.start_batch(p["id"], batch_body(p, phase))
        batch = generation._batch_tasks[p["id"]]
        await entered.wait()
        fail.set()
        await turns_until(lambda: bool(store.get_project(p["id"])["workspace_batch"]["failed_scene_ids"]))
        assert request.await_count == 3 and not batch.done()
        release_second.set()
        await turns_until(lambda: store.get_project(p["id"])["workspace_batch"]["done"] == 1)
        # A newly free slot must not admit scene four while the third call drains.
        assert request.await_count == 3 and not batch.done()
        release_third.set()
        await batch

    asyncio.run(run())
    latest = store.get_project(p["id"])
    job = latest["workspace_batch"]
    assert job["state"] == "failed" and job["done"] == 2
    assert job["processed"] == request.await_count == 3
    assert job["failed_scene_ids"] == [21] and job["scene_errors"] == {"21": str(provider_error)}
    assert job["error"] == str(provider_error) and "fournisseur captcha" in job["error"]
    assert "private-" not in str(job) and "example.invalid" not in str(job)
    assert [call.args[0] for call in request.await_args_list] == [first, second, third]
    assert all(call.kwargs["attempts"] == 1 and call.kwargs["provider"] == "google_flow"
               and call.kwargs["model"] == p["model_snapshot"]["image_model"]
               for call in request.await_args_list)
    for shot in latest["scenes"][4:6]:
        assert shot["image"] != "previous.png" and shot["generation_receipt"]["state"] == "generated_unreviewed"
    if phase == "corrections":
        assert latest["scenes"][3]["image"] == "previous.png"
        assert latest["scenes"][3]["workspace_regeneration_required"] is True
        assert latest["scenes"][3]["generation_receipt"] == {"id": "old-21"}
        assert all(shot["image"] == "previous.png" and shot["workspace_regeneration_required"] is True
                   for shot in latest["scenes"][6:])
    else:
        assert all(not shot["image"] for shot in latest["scenes"][6:])
    assert job["current_scene_ids"] == [] and not generation.batch_running(p["id"])
    assert p["id"] not in generation._active_projects
    assert not any(key[0] == p["id"] for key in generation._batch_permits)


@pytest.mark.parametrize("phase", ["remaining", "corrections"])
def test_parallel_quota_failure_no_retry_remaining_stops_corrections_continue(workspace, monkeypatch, phase):
    p, data = concurrent_project(workspace, monkeypatch, phase)
    entered_count = 0
    first_prompt = p["scenes"][3]["prompt"]

    async def image(prompt, **kwargs):
        nonlocal entered_count
        entered_count += 1
        if entered_count == 3:
            entered.set()
        if prompt == first_prompt:
            await fail.wait()
            raise generation.google_flow.FlowError("Quota ou cadence Google Flow atteint.", 429)
        await finish.wait()
        return data

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)
    entered = fail = finish = None

    async def run():
        nonlocal entered, fail, finish
        entered, fail, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
        await generation.start_batch(p["id"], batch_body(p, phase))
        batch = generation._batch_tasks[p["id"]]
        await entered.wait()
        fail.set()
        await turns_until(lambda: bool(store.get_project(p["id"])["workspace_batch"]["failed_scene_ids"]))
        if phase == "remaining":
            assert request.await_count == 3
        finish.set()
        await batch

    asyncio.run(run())
    latest = store.get_project(p["id"])
    job = latest["workspace_batch"]
    assert job["state"] == ("failed" if phase == "remaining" else "done_with_errors")
    assert job["done"] == (2 if phase == "remaining" else 6)
    assert job["processed"] == request.await_count == (3 if phase == "remaining" else 7)
    assert job["failed_scene_ids"] == [21] and "Quota" in job["scene_errors"]["21"]
    assert sum(call.args[0] == first_prompt for call in request.await_args_list) == 1
    if phase == "corrections":
        assert latest["scenes"][3]["image"] == "previous.png"
        assert latest["scenes"][3]["workspace_regeneration_required"] is True
        assert latest["scenes"][3]["generation_receipt"] == {"id": "old-21"}
    else:
        assert all(not shot["image"] for shot in latest["scenes"][6:])


@pytest.mark.parametrize("change", ["prompt", "reference", "missing-reference", "model", "invalid-registry", "preview-review"])
def test_parallel_input_change_stops_admission_and_preserves_each_started_result(workspace, monkeypatch, change):
    p, data = concurrent_project(workspace, monkeypatch, "corrections")
    entered_count = 0

    async def image(*args, **kwargs):
        nonlocal entered_count
        entered_count += 1
        if entered_count == 3:
            entered.set()
        await release.wait()
        return data

    request = AsyncMock(side_effect=image)
    monkeypatch.setattr(llm, "generate_image", request)
    entered = release = None

    async def run():
        nonlocal entered, release
        entered, release = asyncio.Event(), asyncio.Event()
        await generation.start_batch(p["id"], batch_body(p, "corrections"))
        batch = generation._batch_tasks[p["id"]]
        await entered.wait()
        current = api._project(p["id"])
        if change == "prompt":
            current["scenes"][-1]["prompt"] = "Changed unopened shot during requests."
        elif change == "reference":
            Image.new("RGB", (32, 18), "red").save(store.project_dir(p["id"]) / "reference.png")
        elif change == "missing-reference":
            (store.project_dir(p["id"]) / "reference.png").unlink()
        elif change == "model":
            current["model_snapshot"]["image_model"] = "other-fixture-image"
        elif change == "invalid-registry":
            current["workspace_cast_registry"] = {"Atreus": {"variants": None}}
        else:
            current["scenes"][0]["human_review"] = {"state": "unreviewed"}
        store.save_project(current)
        release.set()
        await batch

    asyncio.run(run())
    latest = store.get_project(p["id"])
    assert latest["workspace_batch"]["state"] == "failed" and request.await_count == 3
    assert latest["workspace_batch"]["processed"] == 3
    assert all(shot["image"] == "previous.png" for shot in latest["scenes"][6:])
    if change in ("reference", "missing-reference", "model", "invalid-registry"):
        assert all(shot["image"] == "previous.png" and shot["workspace_regeneration_required"] is True
                   for shot in latest["scenes"][3:6])
        assert len(latest["workspace_generation_history"]) == 3
        assert all(receipt["state"] == "obsolete_unselected" for receipt in latest["workspace_generation_history"])
        assert len({receipt["image"]["path"] for receipt in latest["workspace_generation_history"]}) == 3
    else:
        assert all(shot["image"] != "previous.png" for shot in latest["scenes"][3:6])


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
