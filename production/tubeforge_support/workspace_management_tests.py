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
    result = managed.post("/api/workspace/management/channels", json={"name": "My channel", "handle": "@Example", "style_id": style["id"]})
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
