import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migrate import enrich_survivor_cast, rebase


def test_paths_change_but_authored_text_does_not():
    data = {"path": "C:\\old\\work\\test.png", "script": "C:/old/leave this narration alone",
            "prompt": "C:/old/leave this authored prompt alone", "references": ["C:/old/output/ref.png"]}
    result = rebase(data, "C:/old", "/opt/studio")
    assert result["path"] == "/opt/studio/work/test.png"
    assert result["references"] == ["/opt/studio/output/ref.png"]
    assert result["script"] == data["script"] and result["prompt"] == data["prompt"]


def test_missing_cast_is_added_without_replacing_existing_character(tmp_path):
    studio = tmp_path / "source"
    presets = studio / "production/tubeforge_presets"
    presets.mkdir(parents=True)
    reference = studio / "reference.png"
    reference.write_bytes(b"test fixture only")
    identity = {"files": ["reference.png"], "sha256": [hashlib.sha256(reference.read_bytes()).hexdigest()], "description": "fixture"}
    preset = {"id": "survivor-alien-aftermath", "characters": {"Reed": identity, "Mara": identity}, "review_provenance": "fixture"}
    (presets / "alien.json").write_text(json.dumps(preset))
    data = tmp_path / "data"
    style = data / "styles" / preset["id"] / "style.json"
    style.parent.mkdir(parents=True)
    style.write_text(json.dumps({"workspace_cast_registry": {"Reed": {"custom": "preserve me"}}}))
    added = enrich_survivor_cast(data, studio)
    assert added == [{"style": preset["id"], "character": "Mara"}]
    assert json.loads(style.read_text())["workspace_cast_registry"]["Reed"] == {"custom": "preserve me"}
    assert enrich_survivor_cast(data, studio) == []
    reference.write_bytes(b"edited fixture")
    content = json.loads(style.read_text())
    del content["workspace_cast_registry"]["Mara"]
    style.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        enrich_survivor_cast(data, studio)
