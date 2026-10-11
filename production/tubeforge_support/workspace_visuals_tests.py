"""Catalog replacement retains project evidence and enforces the image provider."""
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock

from .workspace_api_tests import workspace, create, api, store, channels, read_json, write_json
from . import workspace_management as management, workspace_visuals as visuals


def test_theme_catalog_replacement_preserves_projects_and_old_reference_paths(workspace, tmp_path, monkeypatch):
    client, _, values, app = workspace
    management.install(app)
    existing = create(client, custom_script="Existing episode.")
    previous = (store.project_dir(existing["id"]) / "project.json").read_bytes()
    old_ref = store.style_dir("pov-history") / "old-reference.png"
    old_ref.write_bytes(b"original-reference")
    archived = store.default_style("old-archived", "Old archived")
    archived["archived"] = True
    store.save_style(archived)
    monkeypatch.setattr(visuals.google_flow, "configured", lambda: True)
    monkeypatch.setattr(visuals.google_flow, "setting", lambda key: "fixture-flow" if key == "USEAPI_IMAGE_MODEL" else "")
    monkeypatch.setattr(visuals.google_flow, "status", AsyncMock(return_value={"available": True, "accounts": [], "error": None}))
    values["USEAPI_IMAGE_MODEL"] = "fixture-flow"
    source = tmp_path / "studio/output/imagegen/fictional-theme-references-2026-10-11"
    source.mkdir(parents=True)
    scenes = []
    for theme, _ in visuals.THEMES:
        directory = source / theme
        directory.mkdir()
        for i in range(3):
            data = (theme + str(i)).encode()
            image = f"{theme}/{i}.png"
            (source / image).write_bytes(data)
            scenes.append({"theme": theme, "stem": str(i), "image": image,
                "image_sha256": hashlib.sha256(data).hexdigest(), "review_state": "reviewed_by_codex"})
    write_json(source / "registre.json", {"scenes": scenes})
    policy = visuals.activate(tmp_path / "studio")
    ids = {"fictional-" + theme for theme, _ in visuals.THEMES}
    catalog = client.get("/api/workspace/management").json()
    assert {s["id"] for s in catalog["styles"]} == ids
    assert all(len(s["references"]) == 3 and all(r["exists"] for r in s["references"]) for s in catalog["styles"])
    assert all(c["style_id"] == visuals.STYLE_ID for c in catalog["channels"])
    assert old_ref.read_bytes() == b"original-reference"
    assert not (old_ref.parent / "style.json").exists()
    assert (store.project_dir(existing["id"]) / "project.json").read_bytes() == previous
    backup = api.config.DATA / policy["backup"]
    assert (backup / "pov-history/style.json").is_file()
    assert (backup / "old-archived/style.json").is_file()
    fresh = create(client)
    assert fresh["style_id"] == visuals.STYLE_ID
    assert fresh["model_snapshot"]["image_provider"] == "google_flow"
    assert fresh["settings"]["visuals"]["image_provider"] == "google_flow"
    for theme, _ in visuals.THEMES:
        project = create(client, style_id="fictional-" + theme)
        assert len(project["settings"]["visuals"]["style_refs"]) == 3
    assert client.post("/api/workspace/projects", json={"profile_id": "edo-daily", "title": "Rejected",
        "image_model": "fixture-image", "image_provider": "cli_proxy"}).status_code == 422
    assert client.put("/api/workspace/settings", json={"image_model": "fixture-image",
        "image_provider": "cli_proxy"}).status_code == 422
    assert client.put("/api/workspace/settings", json={"image_model": "fixture-flow",
        "image_provider": "google_flow"}).status_code == 200
    custom = client.post("/api/workspace/management/styles", json={"name": "Later custom style", "prompt": "Custom."})
    assert custom.status_code == 201
    assert client.post("/api/workspace/management/channels", json={"name": "Later channel",
        "style_id": "fictional-pokemon", "voice": {"voice_id": "fixture-channel-voice"}}).status_code == 201
    assert visuals.activate(tmp_path / "studio") == policy
    assert custom.json()["id"] in {s["id"] for s in api._styles()}
