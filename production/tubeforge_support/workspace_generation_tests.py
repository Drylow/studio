"""One-plan execution contracts, using only mocked image requests."""
import io
from pathlib import Path
from unittest.mock import AsyncMock

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
