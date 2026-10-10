"""Workspace contracts against the private vendor store, with no paid requests.

Run with TubeForge's isolated Python. Only temporary fixture data are written.
"""
import io
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient


HERE = Path(__file__).resolve()
DEPLOYED = HERE.parent.name == "tests"
REPO = HERE.parents[2] if not DEPLOYED else HERE.parent.parent
VENDOR = HERE.parent.parent if DEPLOYED else REPO / "work" / "TubeForge"
if not (VENDOR / "app" / "store.py").exists():
    pytest.skip("Private TubeForge installation is required", allow_module_level=True)
sys.path.insert(0, str(VENDOR))
sys.path.insert(1, str(REPO / "production"))
from app import channels, config, llm, pipeline, store
from app.util import read_json, write_json
if DEPLOYED:
    from app import workspace_api as api
else:
    from tubeforge_support import workspace_api as api


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    values = {"PROXY_API_KEY": "private-fixture-key", "PROXY_BASE_URL": "https://fixture.invalid/v1",
              "SCRIPT_MODEL": "fixture-text", "FAST_MODEL": "fixture-fast"}
    monkeypatch.setattr(config, "get", lambda key: values.get(key, ""))
    monkeypatch.setattr(config, "update", lambda changes: values.update(changes))
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "STYLES_DIR", tmp_path / "styles")
    monkeypatch.setattr(channels, "FILE", tmp_path / "channels.json")
    monkeypatch.setattr(pipeline, "BATCHES_FILE", tmp_path / "batches.json")
    monkeypatch.setattr(store, "_cache", {})
    monkeypatch.setattr(store, "_mtimes", {})
    monkeypatch.setattr(pipeline, "is_running", lambda pid: False)
    def forbidden(*args, **kwargs):
        raise AssertionError("Automatic or paid generation was called")
    for name in ("start", "start_side", "run_all"):
        monkeypatch.setattr(pipeline, name, forbidden)
    for name in ("chat", "generate_image"):
        monkeypatch.setattr(llm, name, forbidden)
    style = store.default_style("pov-history", "POV style")
    style["visuals"].update(image_model="fixture-image", style_refs=[])
    style["thumbnail"]["model"] = "fixture-image"
    store.save_style(style)
    write_json(channels.FILE, [{"id": cid, "name": name, "language": "English", "style_id": "pov-history",
                                "kind": "long", "historical_profile": True, "target_minutes": 22,
                                "video_preview": "refs/preview.png", "preview_label": "Apercu existant"}
                               for cid, name in api.PROFILE_NAMES.items()])
    proxy = AsyncMock()
    proxy.get.return_value = httpx.Response(200, json={"data": [
        {"id": "fixture-text", "capabilities": {"text": True, "image": False}},
        {"id": "fixture-image", "output_modalities": ["image"]},
        {"id": "future-image-fixture", "owned_by": "arbitrary-upstream-owner"},
    ]})
    monkeypatch.setattr(llm, "client", lambda: proxy)
    app = FastAPI()
    web = tmp_path / "web"
    web.mkdir()
    app.mount("/", StaticFiles(directory=web, html=True))
    api.install(app)
    count = len(app.router.routes)
    api.install(app)
    assert len(app.router.routes) == count
    with TestClient(app) as client:
        yield client, proxy, values, app


def create(client, **changes):
    response = client.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "A day",
                                                           "duration_minutes": 22, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def media_project(client):
    p = create(client, custom_script="First action.")
    pdir = store.project_dir(p["id"])
    (pdir / "scene.png").write_bytes(b"image fixture")
    (pdir / "reference.png").write_bytes(b"reference fixture")
    (pdir / "voice.mp3").write_bytes(b"audio fixture")
    (pdir / "render.mp4").write_bytes(b"render fixture")
    scene = {"id": 1, "text": "First action.", "prompt": "Codex authored exact prompt.",
             "location_id": "shop", "characters": ["named-worker"], "start": 0, "end": 10,
             "references": [{"path": "reference.png", "owner": "project"}], "image": "scene.png"}
    result = client.put(f"/api/workspace/projects/{p['id']}/scenes", json={"scenes": [scene]})
    assert result.status_code == 200, result.text
    p = store.get_project(p["id"])
    p["voiceover"] = {"file": "voice.mp3", "duration": 10}
    p["render"] = {"file": "render.mp4", "duration": 10}
    store.save_project(p)
    return p


def test_mount_order_idempotence_and_seed_contract(workspace):
    client, _, _, app = workspace
    response = client.get("/api/workspace")
    assert response.status_code == 200
    profiles = client.get("/api/workspace/channels").json()
    assert len(profiles) == 5
    assert profiles[0]["video_preview_url"] == "/style-media/pov-history/refs/preview.png"
    assert profiles[0]["reference_status"] == "waiting_for_user_references"
    assert "/api/workspace" in app.openapi()["paths"]


def test_catalog_uses_existing_proxy_and_sanitizes(workspace):
    client, proxy, values, _ = workspace
    catalog = client.post("/api/workspace/models/refresh").json()
    assert catalog["available"] and not catalog["generation_tested"]
    assert catalog["provider_connection"] == "not_tested"
    assert "owned_by" not in str(catalog)
    assert values["PROXY_API_KEY"] not in str(catalog)
    args = proxy.get.call_args
    assert args.args == (values["PROXY_BASE_URL"] + "/models",)
    assert args.kwargs["follow_redirects"] is False
    assert args.kwargs["headers"] == {"Authorization": "Bearer private-fixture-key"}
    future = next(m for m in catalog["models"] if m["id"].startswith("future-"))
    assert future["capabilities"] == {"text": None, "image": None}
    assert not future["capability_verified"] and future["suggested_role"] == "image"


@pytest.mark.parametrize("failure", ["http", "exception", "shape"])
def test_catalog_failure_never_echoes_upstream(workspace, failure):
    client, proxy, values, _ = workspace
    if failure == "http":
        proxy.get.return_value = httpx.Response(401, text=values["PROXY_API_KEY"])
    elif failure == "exception":
        proxy.get.side_effect = RuntimeError(values["PROXY_API_KEY"])
    else:
        proxy.get.return_value = httpx.Response(200, json=[values["PROXY_API_KEY"]])
    response = client.get("/api/workspace/models")
    assert response.status_code == 200
    assert not response.json()["available"]
    assert values["PROXY_API_KEY"] not in response.text
    rejected = client.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "One"})
    assert rejected.status_code == 503
    assert store.list_projects() == []


def test_project_snapshot_review_mode_exact_script_and_no_auto(workspace):
    client, _, _, _ = workspace
    p = create(client, custom_script="  Exact script.\n\n", image_model="future-image-fixture")
    assert p["mode"] == "review" and p["codex_directed"]
    assert p["script"] == "  Exact script.\n\n"
    assert p["settings"]["script"]["model"] == "fixture-text"
    assert p["settings"]["models"]["image"] == "future-image-fixture"
    assert p["target_duration_seconds"] == 1320
    assert p["workspace_queue"]["state"] == "queued_for_authoring"
    assert p["review_state"] == "waiting_for_voiceover"
    assert not p["publication_ready"] and not p["prompts_approved"]
    persisted = read_json(store.project_dir(p["id"]) / "project.json")
    assert persisted["model_snapshot"] == p["model_snapshot"]


def test_visual_style_selection_is_frozen_and_keeps_channel_voice(workspace):
    client, _, _, _ = workspace
    channel = store.get_style("pov-history")
    channel["voice"].update(provider="algrow", voice_id="channel-voice")
    store.save_style(channel)
    alternate = store.default_style("alternate", "Alternate visual style")
    alternate["visuals"]["art_style"] = "Exact alternate style."
    alternate["voice"].update(provider="another-provider", voice_id="other-voice")
    store.save_style(alternate)
    assert {s["id"] for s in client.get("/api/workspace/styles").json()} == {"pov-history", "alternate"}
    p = create(client, style_id="alternate", custom_script="  Script imported exactly.\n")
    assert p["style_id"] == "alternate" and p["style_name"] == alternate["name"]
    assert p["style_snapshot"]["prompt"] == "Exact alternate style."
    assert p["settings"]["visuals"]["art_style"] == "Exact alternate style."
    assert p["settings"]["voice"]["provider"] == "algrow"
    assert p["settings"]["voice"]["voice_id"] == "channel-voice"
    alternate["visuals"]["art_style"] = "Changed later."
    store.save_style(alternate)
    saved = client.get(f"/api/workspace/projects/{p['id']}").json()
    assert saved["style_snapshot"] == p["style_snapshot"]
    assert saved["settings"]["visuals"]["art_style"] == "Exact alternate style."
    assert saved["script"] == "  Script imported exactly.\n"
    assert not saved["running"] and not saved["publication_ready"]


@pytest.mark.parametrize("change", [{"style_id": "missing"}, {"style_id": "../private"},
                                   {"title": "x" * 241}, {"custom_script": "x" * (1024 * 1024 + 1)},
                                   {"custom_script": "bad\x00text"}])
def test_creation_invalid_style_or_script_does_not_create_data(workspace, change):
    client, _, _, _ = workspace
    response = client.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "One", **change})
    assert response.status_code == 422 and store.list_projects() == []


def test_archived_style_cannot_be_selected(workspace):
    client, _, _, _ = workspace
    archived = store.default_style("old-style", "Archived style")
    archived["archived"] = True
    store.save_style(archived)
    assert "old-style" not in {s["id"] for s in client.get("/api/workspace/styles").json()}
    response = client.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "One", "style_id": "old-style"})
    assert response.status_code == 422


def test_rename_changes_only_title_and_rejects_empty_title(workspace):
    client, _, _, _ = workspace
    p = create(client, custom_script="Exact script.")
    url = f"/api/workspace/projects/{p['id']}/title"
    assert client.put(url, json={"title": " "}).status_code == 422
    result = client.put(url, json={"title": "  Better title  "})
    assert result.status_code == 200
    saved = result.json()
    assert saved["title"] == "Better title" and not saved["title_auto"]
    for key in ("script", "settings", "style_snapshot", "model_snapshot", "human_reviews"):
        assert saved[key] == p[key]


@pytest.mark.parametrize("change", [{"text_model": "not-in-catalog"}, {"image_model": "fixture-text"},
                                   {"duration_minutes": 19}, {"duration_minutes": True},
                                   {"mode": "auto"}, {"auto_run": True}, {"profile_id": "unknown"}])
def test_invalid_project_rejected_before_creation(workspace, change):
    client, _, _, _ = workspace
    response = client.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "One", **change})
    assert response.status_code == 422
    assert store.list_projects() == []


def test_batch_validation_and_per_row_snapshot(workspace):
    client, _, _, _ = workspace
    good = {"profile_id": "edo-daily", "title": "One"}
    response = client.post("/api/workspace/batches", json={"rows": [good, good | {"duration_minutes": 1}]})
    assert response.status_code == 422 and store.list_projects() == []
    response = client.post("/api/workspace/batches", json={"image_model": "fixture-image", "rows": [
        good, good | {"profile_id": "aztec-daily", "image_model": "future-image-fixture"}]})
    assert response.status_code == 201, response.text
    result = response.json()
    assert len(result["projects"]) == 2
    assert result["projects"][1]["model_snapshot"]["image_model"] == "future-image-fixture"
    assert result["batch"]["queue_state"] == "queued_for_authoring"
    assert client.get("/api/workspace/batches").json()[0]["id"] == result["batch"]["id"]


def test_new_defaults_do_not_change_existing_snapshot(workspace):
    client, _, _, _ = workspace
    p = create(client)
    before = p["model_snapshot"]
    response = client.put("/api/workspace/settings", json={"text_model": "fixture-text", "image_model": "future-image-fixture"})
    assert response.status_code == 200
    assert response.json()["image_model"] == "future-image-fixture"
    assert create(client)["model_snapshot"]["image_model"] == "future-image-fixture"
    assert client.get(f"/api/workspace/projects/{p['id']}").json()["model_snapshot"] == before


@pytest.mark.parametrize("change", ["image", "reference", "prompt", "script", "audio"])
def test_human_review_is_bound_to_actual_evidence(workspace, change):
    client, _, _, _ = workspace
    p = media_project(client)
    route = f"/api/workspace/projects/{p['id']}"
    assert client.get(route).json()["review_state"] == "rendered_awaiting_review"
    for scope in ("script", "voiceover", "render"):
        assert client.post(route + "/review", json={"scope": scope, "state": "verified"}).status_code == 200
    assert client.post(route + "/review", json={"scene_id": 1, "state": "verified", "notes": "Image inspected"}).status_code == 200
    assert client.get(route).json()["publication_ready"]
    if change in ("image", "reference", "audio"):
        name = {"image": "scene.png", "reference": "reference.png", "audio": "voice.mp3"}[change]
        (store.project_dir(p["id"]) / name).write_bytes(b"changed fixture")
    elif change == "prompt":
        p = store.get_project(p["id"])
        p["scenes"][0]["prompt"] = "Changed prompt"
        store.save_project(p)
    else:
        assert client.put(route + "/script", json={"text": "Changed manual script"}).status_code == 200
    result = client.get(route).json()
    assert not result["publication_ready"]
    if change != "audio":
        assert result["scenes"][0]["human_review"]["state"] == "stale"
    else:
        assert result["human_reviews"]["voiceover"]["state"] == "stale"
        assert result["human_reviews"]["render"]["state"] == "stale"


def test_correction_records_note_without_generation(workspace):
    client, _, _, _ = workspace
    p = media_project(client)
    route = f"/api/workspace/projects/{p['id']}/review"
    result = client.post(route, json={"scene_id": 1, "state": "correct", "notes": "Correct distant skyline"})
    assert result.status_code == 200
    assert result.json()["review_state"] == "needs_correction"
    assert result.json()["scenes"][0]["human_review"]["notes"] == "Correct distant skyline"
    assert result.json()["scenes"][0]["prompt"] == "Codex authored exact prompt."


def test_uploads_are_unreviewed_ordered_and_shared(workspace):
    client, _, _, _ = workspace
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, "PNG")
    for label in ("Older reference", "New user reference"):
        result = client.post("/api/workspace/profiles/edo-daily/references",
                             files={"file": ("../../unsafe.png", buf.getvalue(), "image/png")}, data={"label": label})
        assert result.status_code == 200, result.text
    refs = result.json()["references"]
    assert len(refs) == 2 and all(r["state"] == "unreviewed" for r in refs)
    assert all(".." not in r["path"] for r in refs)
    reversed_refs = list(reversed(refs))
    result = client.put("/api/workspace/profiles/edo-daily", json={"references": reversed_refs})
    assert result.status_code == 200
    assert result.json()["references"][0]["label"] == "New user reference"
    assert client.get("/api/workspace/profiles").json()[1]["references"][0]["path"] == refs[1]["path"]
    response = client.put("/api/workspace/profiles/edo-daily", json={"references": [{"path": "../outside.png"}]})
    assert response.status_code == 422
    p = create(client)
    result = client.post(f"/api/workspace/projects/{p['id']}/references",
                         files={"file": ("ref.png", buf.getvalue(), "image/png")}, data={"role": "location"})
    assert result.status_code == 200
    assert result.json()["references"][0]["role"] == "location"
    assert result.json()["references"][0]["state"] == "unreviewed"


def test_missing_and_escaped_image_cannot_be_verified(workspace):
    client, _, _, _ = workspace
    p = media_project(client)
    (store.project_dir(p["id"]) / "scene.png").unlink()
    response = client.post(f"/api/workspace/projects/{p['id']}/review", json={"scene_id": 1, "state": "verified"})
    assert response.status_code == 409
    assert api._file_digest(store.project_dir(p["id"]), "../outside.png") is None


def test_manual_script_edit_never_invents_timing_or_rewrites(workspace):
    client, _, _, _ = workspace
    p = create(client)
    route = f"/api/workspace/projects/{p['id']}"
    text = "  Manual narration.\n"
    assert client.put(route + "/script", json={"text": text}).json()["script"] == text
    row = {"id": 1, "text": "Manual narration.", "prompt": " Exact prompt ", "location_id": "street",
           "characters": [], "references": []}
    result = client.put(route + "/scenes", json={"scenes": [row]})
    assert result.status_code == 200
    scene = result.json()["scenes"][0]
    assert scene["prompt"] == " Exact prompt " and "start" not in scene and "end" not in scene
    result = client.put(route + "/scenes", json={"scenes": [row | {"text": "Invented narration"}]})
    assert result.status_code == 422


def test_no_reference_plan_cannot_be_verified(workspace):
    client, _, _, _ = workspace
    p = media_project(client)
    p["scenes"][0]["references"] = []
    store.save_project(p)
    response = client.post(f"/api/workspace/projects/{p['id']}/review", json={"scene_id": 1, "state": "verified"})
    assert response.status_code == 409
    correction = client.post(f"/api/workspace/projects/{p['id']}/review",
                             json={"scene_id": 1, "state": "correct", "notes": "Master reference missing"})
    assert correction.status_code == 200
    assert correction.json()["review_state"] == "needs_correction"


def test_imported_studio_reference_is_locked_to_root_and_hash(workspace, tmp_path):
    client, _, values, _ = workspace
    p = media_project(client)
    studio = tmp_path / "studio"
    studio.mkdir()
    (studio / "master.png").write_bytes(b"Studio master fixture")
    values["STUDIO_ROOT"] = str(studio)
    p["scenes"][0].pop("references")
    p["scenes"][0]["codex_receipt"] = {"references": [{"path": "master.png", "role": "location",
        "sha256": api._file_digest(studio, "master.png")} ]}
    store.save_project(p)
    route = f"/api/workspace/projects/{p['id']}/review"
    detail = client.get(f"/api/workspace/projects/{p['id']}").json()
    ref = detail["scenes"][0]["sent_references"][0]
    assert ref["owner"] == "studio"
    assert client.get(ref["url"]).content == b"Studio master fixture"
    assert client.post(route, json={"scene_id": 1, "state": "verified"}).status_code == 200
    (studio / "master.png").write_bytes(b"Changed studio master")
    assert client.get(ref["url"]).status_code == 409
    assert client.post(route, json={"scene_id": 1, "state": "verified"}).status_code == 409
    p["scenes"][0]["codex_receipt"]["references"][0]["path"] = "../outside.png"
    store.save_project(p)
    assert client.post(route, json={"scene_id": 1, "state": "verified"}).status_code == 409


@pytest.mark.parametrize("issue", ["qa_pending", "clock_gap", "script_coverage", "voiceover_stale", "technical_test"])
def test_publication_gate_includes_technical_readiness(workspace, issue):
    client, _, _, _ = workspace
    p = media_project(client)
    route = f"/api/workspace/projects/{p['id']}"
    for scope in ("script", "voiceover", "render"):
        assert client.post(route + "/review", json={"scope": scope, "state": "verified"}).status_code == 200
    assert client.post(route + "/review", json={"scene_id": 1, "state": "verified"}).status_code == 200
    assert client.get(route).json()["publication_ready"]
    p = store.get_project(p["id"])
    if issue == "qa_pending":
        p["render"]["qa_pending"] = True
    elif issue == "clock_gap":
        p["scenes"][0]["start"] = 1
    elif issue == "script_coverage":
        p["scenes"][0]["text"] = "Only a partial excerpt"
    elif issue == "technical_test":
        p["technical_test"] = True
    else:
        p["voiceover_stale"] = True
    store.save_project(p)
    result = client.get(route).json()
    assert not result["publication_ready"] and not result["technical_ready"]
    assert result["technical_issues"]
    if issue == "qa_pending":
        assert result["review_state"] == "rendered_qa_pending"


def test_legacy_projects_visible_but_readonly(workspace):
    client, _, _, _ = workspace
    p = store.create_project("Legacy user project", "pov-history", mode="review", characters=[])
    summary = client.get("/api/workspace").json()["projects"][0]
    assert summary["id"] == p["id"] and summary["readonly"]
    assert summary["review_state"] == "legacy_readonly"
    assert summary["legacy_url"].startswith("/legacy.html#/")
    assert client.get(f"/api/workspace/projects/{p['id']}").status_code == 404


def test_reference_manifest_labels_preserved(workspace):
    client, _, _, _ = workspace
    style = store.get_style("pov-history")
    (store.style_dir("pov-history") / "refs").mkdir()
    (store.style_dir("pov-history") / "refs/observed.png").write_bytes(b"fixture")
    style["visuals"].update(style_refs=["refs/observed.png"], reference_update_pending=True,
                            reference_sources=[{"file": "refs/observed.png", "observed": "2026-10-05",
                                                "label": "Older observed screenshot", "role": "style-only"}])
    store.save_style(style)
    profile = client.get("/api/workspace/channels").json()[0]
    assert profile["reference_update_pending"]
    assert profile["references"][0]["observed"] == "2026-10-05"
    assert profile["references"][0]["role"] == "style-only"
    assert profile["references"][0]["exists"]
