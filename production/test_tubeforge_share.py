"""Run using a fresh TubeForge installation's interpreter; no external API calls."""
import copy
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "production"))
from tubeforge_setup import seed_presets
from app import channels, config, store, workspace_writing
from app.util import read_json


@pytest.fixture
def private_store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "STYLES_DIR", tmp_path / "styles")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(channels, "FILE", tmp_path / "channels.json")
    monkeypatch.setattr(store, "_cache", {})
    monkeypatch.setattr(store, "_mtimes", {})
    return tmp_path


def test_portable_presets_import_full_cast_and_preserve_edits(private_store):
    private = {"AI_IMAGE_MODEL": "fixture-image", "AI_TEXT_MODEL": "fixture-text"}
    seed_presets(config.ROOT, private, "fixture-voice")
    patch = store.get_style("survivor-patch")
    alien = store.get_style("survivor-alien-aftermath")
    assert set(patch["workspace_cast_registry"]) == {"Patch", "Mara", "Cart Infected", "Delivery Infected"}
    assert set(alien["workspace_cast_registry"]) == {"Reed", "Mara", "Surveyor", "Worker"}
    for style in (patch, alien):
        for character in style["workspace_cast_registry"].values():
            assert all((store.style_dir(style["id"]) / ref["path"]).is_file()
                       for ref in character["variants"]["default"]["references"])
    alien["visuals"]["art_style"] = "My colleague's custom art direction"
    store.save_style(alien)
    before = copy.deepcopy(read_json(channels.FILE))
    result = seed_presets(config.ROOT, private, "a-different-voice")
    assert all(r["status"] == "preserved_existing" for r in result)
    assert store.get_style(alien["id"])["visuals"]["art_style"] == alien["visuals"]["art_style"]
    assert read_json(channels.FILE) == before


def test_writer_works_without_private_competitor_transcripts(tmp_path, monkeypatch):
    skills = tmp_path / "skills/facelessos"
    skills.mkdir(parents=True)
    for name in workspace_writing.SKILLS:
        shutil.copy2(ROOT / "skills/facelessos" / name, skills / name)
    monkeypatch.setattr(config, "get", lambda key: str(tmp_path) if key == "STUDIO_ROOT" else "")
    data = workspace_writing.resources()
    assert len(data["anchors"]) == 3
    assert all(a["source_kind"] == "original_house_narration" for a in data["anchors"])
    assert all("url" not in a for a in data["anchors"])
    assert len(data["skills"]) > 1000
