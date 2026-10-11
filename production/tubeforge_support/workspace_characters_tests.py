"""Identity mapping contracts; all fixtures local and all model/image requests mocked."""
import asyncio
import copy
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest
from PIL import Image

if Path(__file__).parent.name == "tests":
    from test_workspace_api import workspace
    from test_workspace_generation import prepared_plan
    from test_workspace_planning import fictional, answer
    from app import workspace_characters as cast, workspace_generation as generation, workspace_planning as planning
else:
    from .workspace_api_tests import workspace
    from .workspace_generation_tests import prepared_plan
    from .workspace_planning_tests import fictional, answer
    from . import workspace_characters as cast, workspace_generation as generation, workspace_planning as planning
from app import llm, store


def register(p, name="Atreus", key="child", owner="style", required=True):
    base = store.style_dir(p["style_id"]) if owner == "style" else store.project_dir(p["id"])
    path = f"identity-{name.lower()}-{key}.png"
    Image.new("RGB", (32, 18), "white").save(base / path)
    ref = {"path": path, "owner": owner, "character": name, "variant": key, "role": "identity",
           "review_state": "verified", "sha256": hashlib.sha256((base / path).read_bytes()).hexdigest()}
    source = store.get_style(p["style_id"]) if owner == "style" else p
    source.setdefault("workspace_cast_registry", {})[name] = {"required": required,
        "variants": {key: {"description": "Round white-headed child archer in yellow long sleeves and trousers.",
                           "references": [ref]}}}
    if owner == "style":
        store.save_style(source)
    return ref


def scene(p, ref, name="Atreus", key="child"):
    shot = {"id": 1, "characters": [name], "character_variants": {name: key}, "references": [ref]}
    shot["prompt"] = "A physical wide scene.\n" + cast.binding(p, shot)
    return shot


def test_author_selects_only_present_cast_and_keeps_variant_order(workspace):
    p = fictional(workspace)
    register(p, "Kratos", "norse")
    atreus = register(p)
    second = copy.deepcopy(atreus)
    second["path"] = "identity-atreus-child-second.png"
    directory = store.style_dir(p["style_id"])
    (directory / second["path"]).write_bytes((directory / atreus["path"]).read_bytes())
    style = store.get_style(p["style_id"])
    style["workspace_cast_registry"]["Atreus"]["variants"]["child"]["references"].append(second)
    store.save_style(style)
    shot = {"characters": ["Atreus"], "character_variants": {"Atreus": "child"}}
    background = {"owner": "style", "path": "ref.png", "role": "style-only"}
    refs, block = cast.author(p, shot, [background])
    assert refs == [atreus, second, background]
    assert "Image 1: Atreus" in block and "Image 2: Atreus" in block and "Kratos" not in block
    shot.update(references=refs, prompt=block)
    before = copy.deepcopy(shot)
    cast.validate(p, shot)
    assert shot == before  # Executor validation never authors or reorders.


@pytest.mark.parametrize("provider", ["cli_proxy", None])
def test_generic_identity_bindings_keep_literal_image_labels_without_flow_markers(workspace, provider):
    p = fictional(workspace)
    ref = register(p)
    if provider is None:
        p["model_snapshot"].pop("image_provider", None)
    else:
        p["model_snapshot"]["image_provider"] = provider
    # Provider selection comes only from the frozen model snapshot, not mutable settings.
    p["settings"]["visuals"]["image_provider"] = "google_flow"
    shot = scene(p, ref)
    block = cast.binding(p, shot)
    assert 'Image 1: Atreus; variant "child";' in block
    assert "@reference_" not in block
    cast.validate(p, shot)


def test_flow_bindings_match_actual_ordered_slots_and_keep_two_hero_refs_one_identity(workspace):
    p = fictional(workspace)
    p["model_snapshot"]["image_provider"] = "google_flow"
    hero = register(p, name="Kratos", key="norse")
    hero_second = dict(hero, path="identity-kratos-norse-second.png")
    directory = store.style_dir(p["style_id"])
    (directory / hero_second["path"]).write_bytes((directory / hero["path"]).read_bytes())
    style = store.get_style(p["style_id"])
    style["workspace_cast_registry"]["Kratos"]["variants"]["norse"]["references"].append(hero_second)
    store.save_style(style)
    atreus = register(p, name="Atreus", key="child")
    mimir = register(p, name="Mimir", key="head")
    freya = register(p, name="Freya", key="norse")
    generic = {"path": "ref.png", "owner": "style", "role": "style-only"}
    refs = [generic, hero, hero_second, dict(generic, role="location"), atreus, mimir, freya, generic]
    shot = {"characters": ["Kratos", "Atreus", "Mimir", "Freya"],
            "character_variants": {"Kratos": "norse", "Atreus": "child", "Mimir": "head", "Freya": "norse"},
            "references": refs}
    before = copy.deepcopy(refs)
    block = cast.binding(p, shot)
    assert "Image 2 (@reference_2): the round-white-headed warrior protagonist;" in block
    assert "Image 3 (@reference_3): the round-white-headed warrior protagonist;" in block
    assert "Image 5 (@reference_5): Atreus;" in block
    assert "Image 6 (@reference_6): Mimir;" in block
    assert "Image 7 (@reference_7): Freya;" in block
    assert all(f"@reference_{index}" not in block for index in (1, 4, 8, 9, 10))
    assert "same single named individual" in block and "draw that identity exactly once" in block
    assert shot["references"] == before
    shot["prompt"] = "Physical wide scene.\n" + block
    cast.validate(p, shot)
    assert shot["references"] == before


def test_flow_validator_requires_new_saved_grounding_without_executor_rewrite(workspace):
    p = fictional(workspace)
    p["model_snapshot"]["image_provider"] = "cli_proxy"
    ref = register(p)
    shot = scene(p, ref)
    generic_prompt = shot["prompt"]
    p["model_snapshot"]["image_provider"] = "google_flow"
    with pytest.raises(HTTPException) as exc:
        cast.validate(p, shot)
    assert exc.value.status_code == 422 and shot["prompt"] == generic_prompt
    shot["prompt"] = "Physical wide scene.\n" + cast.binding(p, shot)
    saved = copy.deepcopy(shot)
    cast.validate(p, shot)
    assert shot == saved and "Image 1 (@reference_1): Atreus;" in shot["prompt"]


def test_flow_without_identity_references_emits_no_unbound_markers(workspace):
    p = fictional(workspace)
    p["model_snapshot"]["image_provider"] = "google_flow"
    register(p)
    shot = {"characters": [], "references": [{"path": "ref.png", "owner": "style", "role": "style-only"}]}
    assert cast.binding(p, shot) == ""


@pytest.mark.parametrize("label", ["", " ", " role ", None, 12, False])
def test_registry_rejects_invalid_explicit_prompt_labels(workspace, label):
    p = fictional(workspace)
    register(p)
    style = store.get_style(p["style_id"])
    style["workspace_cast_registry"]["Atreus"]["prompt_label"] = label
    store.save_style(style)
    with pytest.raises(HTTPException) as exc:
        cast.registry(p)
    assert exc.value.status_code == 422


def test_prompt_role_labels_override_names_and_hero_alias_without_changing_identity_keys(workspace):
    p = fictional(workspace)
    p["model_snapshot"]["image_provider"] = "google_flow"
    hero = register(p, name="Kratos", key="norse")
    atreus = register(p, name="Atreus", key="child")
    freya = register(p, name="Freya", key="norse")
    labels = {"Kratos": "the red-marked white-circle-headed father", "Atreus": "the white-circle-headed son",
              "Freya": "the white-circle-headed woodland healer"}
    style = store.get_style(p["style_id"])
    for name, label in labels.items():
        style["workspace_cast_registry"][name]["prompt_label"] = label
    store.save_style(style)
    refs = [{"path": "ref.png", "owner": "style", "role": "style-only"}, hero, atreus, freya]
    shot = {"characters": ["Kratos", "Atreus", "Freya"],
            "character_variants": {"Kratos": "norse", "Atreus": "child", "Freya": "norse"}, "references": refs}
    block = cast.binding(p, shot)
    for index, name in enumerate(shot["characters"], 2):
        assert f"Image {index} (@reference_{index}): {labels[name]};" in block
        assert name not in block
        assert cast.summary(p)[name]["prompt_label"] == labels[name]
    assert cast.selected(p, shot) == [hero, atreus, freya]
    assert [ref["character"] for ref in cast.selected(p, shot)] == shot["characters"]
    shot["prompt"] = block
    cast.validate(p, shot)


def test_summary_without_optional_prompt_label_keeps_original_shape(workspace):
    p = fictional(workspace)
    register(p)
    summary = cast.summary(p)
    assert set(summary["Atreus"]) == {"required", "variants"}


@pytest.mark.parametrize("change", ["missing_variant", "wrong_variant", "missing_ref", "wrong_identity",
                                    "unverified", "hash_changed", "missing_binding", "absent_cast", "alias"])
def test_identity_mismatch_is_rejected(workspace, change):
    p = fictional(workspace)
    ref = register(p)
    shot = scene(p, ref)
    if change == "missing_variant":
        shot["character_variants"] = {}
    elif change == "wrong_variant":
        shot["character_variants"]["Atreus"] = "teen"
    elif change == "missing_ref":
        shot["references"] = []
    elif change == "wrong_identity":
        shot["references"][0]["character"] = "Kratos"
    elif change == "unverified":
        shot["references"][0]["review_state"] = "unreviewed"
    elif change == "hash_changed":
        (store.style_dir(p["style_id"]) / ref["path"]).write_bytes(b"changed")
    elif change == "missing_binding":
        shot["prompt"] = "A physical wide scene without the recorded mapping."
    elif change == "absent_cast":
        shot["characters"] = ["Kratos"]
    else:
        shot["characters"] = ["atreus"]
        shot["character_variants"] = {}
    with pytest.raises(HTTPException):
        cast.validate(p, shot)


def test_project_entry_overrides_style_and_uses_project_file(workspace):
    p = fictional(workspace)
    register(p)
    teen = register(p, key="teen", owner="project")
    assert list(cast.registry(p)["Atreus"]["variants"]) == ["teen"]
    cast.validate(p, scene(p, teen, key="teen"))
    with pytest.raises(HTTPException):
        cast.selected(p, {"characters": ["Atreus"], "character_variants": {"Atreus": "child"}})


def test_executor_requires_prepared_cast_before_any_image_call(workspace, monkeypatch):
    client, p = prepared_plan(workspace)
    monkeypatch.setattr(planning, "allowed", lambda project: True)
    register(p)
    p["scenes"][0]["characters"] = ["Atreus"]
    store.save_project(p)
    request = AsyncMock()
    monkeypatch.setattr(llm, "generate_image", request)
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={
        "confirm_prompt": p["scenes"][0]["prompt"], "image_model": p["model_snapshot"]["image_model"]})
    assert response.status_code == 422
    request.assert_not_awaited()


def test_executor_sends_saved_identity_mapping_and_refs_unchanged(workspace, monkeypatch):
    client, p = prepared_plan(workspace)
    monkeypatch.setattr(planning, "allowed", lambda project: True)
    ref = register(p)
    shot = p["scenes"][0]
    shot.update(characters=["Atreus"], character_variants={"Atreus": "child"})
    refs, block = cast.author(p, shot, shot["references"])
    shot.update(references=refs, prompt=shot["prompt"] + "\n" + block)
    exact_prompt = shot["prompt"]
    store.save_project(p)
    stream = io.BytesIO()
    Image.new("RGB", (32, 18), "blue").save(stream, format="PNG")
    request = AsyncMock(return_value=stream.getvalue())
    monkeypatch.setattr(llm, "generate_image", request)
    response = client.post(f"/api/workspace/projects/{p['id']}/scenes/1/generate", json={
        "confirm_prompt": exact_prompt, "image_model": p["model_snapshot"]["image_model"]})
    assert response.status_code == 200, response.text
    assert request.call_args.args == (exact_prompt,)
    assert len(request.call_args.kwargs["refs"]) == 2
    receipt = response.json()["scenes"][0]["generation_receipt"]["references"]
    assert receipt[0]["path"] == ref["path"] and receipt[0]["character"] == "Atreus"
    assert receipt[0]["variant"] == "child" and receipt[1]["path"] == "reference.png"


def test_planner_receives_registry_and_publishes_explicit_project_variants(workspace, monkeypatch):
    p = fictional(workspace)
    ref = register(p, name="Kratos", key="norse", owner="project")
    _, _, _, shots = planning.inputs(p)
    response = json.loads(answer(shots))
    for row in response["shots"]:
        row["character_variants"] = {"Kratos": "norse"}
    request = AsyncMock(return_value=json.dumps(response))
    monkeypatch.setattr(llm, "chat", request)
    asyncio.run(planning.prepare(p))
    sent = json.loads(request.call_args.args[0][1]["content"])
    assert sent["cast_registry"]["Kratos"]["required"] is True
    assert "norse" in sent["cast_registry"]["Kratos"]["variants"]
    for shot in p["scenes"]:
        assert shot["character_variants"] == {"Kratos": "norse"}
        assert shot["references"][0] == ref
        assert "Image 1: the round-white-headed warrior protagonist" in shot["prompt"]
        cast.validate(p, shot)
        assert planning.authored(p, shot)
    p["scenes"][0]["character_variants"]["Kratos"] = "greek"
    assert not planning.authored(p, p["scenes"][0])


def test_planner_omission_keeps_atomic_empty_plan(workspace, monkeypatch):
    p = fictional(workspace)
    register(p, name="Kratos", key="norse")
    _, _, _, shots = planning.inputs(p)
    monkeypatch.setattr(llm, "chat", AsyncMock(return_value=answer(shots)))
    with pytest.raises(RuntimeError):
        asyncio.run(planning.prepare(p))
    assert not p["scenes"] and not p.get("planning_receipt")
