"""Prepare fictional-channel shots using the configured text proxy and real word clock."""
import asyncio
import copy
import json
import math

from fastapi import APIRouter, HTTPException
from app import config, llm, pipeline, store
from app.steps import scenes as timing
from app.util import parse_json, now
from . import workspace_api as api, workspace_management as management, workspace_generation as generation
from . import workspace_composition as composition
from . import workspace_characters as cast


def allowed(p):
    if (store.get_style(p.get("style_id")) or {}).get("workspace_authoring_mode") == "codex":
        return False
    cid = p.get("profile_id") or p.get("channel_id")
    if not cid:
        return False
    channel = management._channel(cid)
    return bool(channel and cid not in api.PROFILE_NAMES and not channel.get("historical_profile"))


def signature(p):
    style = store.get_style(p.get("style_id")) or {}
    evidence = {"script": p.get("script"), "voice": p.get("voiceover"),
                "style": style, "models": p.get("model_snapshot"), "settings": p.get("settings")}
    entries = cast.registry(p)
    if entries:
        evidence["cast_registry"] = entries
    return api._hash(evidence)


def _shot_evidence(s):
    keys = ("text", "prompt", "location_id", "characters", "references", "start", "end")
    # Retain valid pre-registry receipts for projects that have no variant field.
    if "character_variants" in s:
        keys += ("character_variants",)
    return {key: s.get(key) for key in keys}


def authored(p, s):
    receipt = p.get("planning_receipt") or {}
    return (allowed(p) and s.get("prompt_author") == "configured_text_proxy"
            and receipt.get("input_hash") == signature(p)
            and receipt.get("shots", {}).get(str(s["id"])) == api._hash(_shot_evidence(s)))


def inputs(p):
    if not allowed(p):
        raise HTTPException(409, "This channel keeps its segmentation and prompts written by Codex")
    if p.get("scenes"):
        raise HTTPException(409, "Existing shots are kept; preparation does not replace them")
    if api._duration_info(p)["kind"] != "actual":
        raise HTTPException(409, "First generate the voice for the saved script")
    if not config.get("PROXY_BASE_URL") or not config.get("PROXY_API_KEY"):
        raise HTTPException(409, "The studio text proxy must be configured")
    model = (p.get("model_snapshot") or {}).get("text_model") or p["settings"]["script"].get("model")
    if not model:
        raise HTTPException(409, "Choose the project's text model")
    words = store.load_words(p["id"])
    if (not words or any(type(w.get(k)) not in (int, float) or not math.isfinite(w[k]) for w in words for k in ("s", "e"))
            or any(type(w.get(k)) is not int for w in words for k in ("c0", "c1"))):
        raise HTTPException(409, "The voice word alignment is missing")
    if any(w["c0"] < 0 or w["c1"] > len(p["script"]) or w["c1"] <= w["c0"] for w in words):
        raise HTTPException(409, "The word alignment does not match the script")
    if (any(w["s"] < 0 or w["e"] < w["s"] or w["e"] > p["voiceover"]["duration"] + .1 for w in words)
            or any(a["s"] > b["s"] or a["c1"] > b["c0"] for a, b in zip(words, words[1:]))
            or p["voiceover"].get("script_hash", api._hash(p["script"])) != api._hash(p["script"])):
        raise HTTPException(409, "The alignment and voice must match the current script")
    style = store.get_style(p["style_id"]) or {}
    refs = copy.deepcopy(style.get("workspace_references") or [])
    if not refs:
        raise HTTPException(409, "Add the style's approved references")
    for ref in refs:
        ref["owner"] = "style"
        digest = api._file_digest(store.style_dir(p["style_id"]), ref.get("path"))
        if not digest or ref.get("sha256") != digest or ref.get("review_state") != "verified":
            raise HTTPException(409, "A style reference is missing or has changed")
    entries = cast.registry(p)
    era_refs = {} if entries else style.get("workspace_character_references") or {}
    if not isinstance(era_refs, dict):
        raise HTTPException(409, "The style's character references are invalid")
    for selected in era_refs.values():
        if not isinstance(selected, list) or not selected:
            raise HTTPException(409, "Each era must have an approved character reference")
        for ref in selected:
            if (not isinstance(ref, dict) or ref.get("review_state") != "verified"
                    or not ref.get("sha256") or api._file_digest(store.style_dir(p["style_id"]), ref.get("path")) != ref["sha256"]):
                raise HTTPException(409, "A character reference is missing, unverified, or has changed")
    shots = timing.split(words, p["script"], p["voiceover"]["duration"], target=6)
    for i, shot in enumerate(shots, 1):
        shot.update(id=i, text=p["script"][shot["c0"]:shot["c1"]].strip())
    return model, style, refs, shots


async def prepare(p):
    async def run(progress):
        model, style, refs, shots = inputs(p)
        stamp = signature(p)
        result = []
        rules = (
            "Write concrete varied storyboard image prompts for the supplied fictional story. "
            "Return JSON {shots:[{id,location_id,characters:[named identities],character_variants:{exact_character_name:exact_variant_key},prompt}]}. "
            "Exactly one entry per requested id, in order. Do not rewrite narration. "
            "Each prompt must show a distinct narrated action, consequence, object or interaction; "
            "alternate compositions and avoid repeated tableaux. Specify framing, visible action, "
            "outfits, props and environment. Keep recurring characters' identities and outfits consistent "
            "within each story era. Every humanoid has a round white head and white simplified hands. "
            "No realistic faces, no text, no watermarks. Use attached reference images as drawing-style "
            "guidance, not copied scenes. Only one instance of each character per scene. "
            "For Kratos preserve the red facial stripe and simple face of the approved references; Greek-era chain blades versus "
            "Norse-era axe and fur/leather attire must follow the narration. Atreus is a distinct smaller "
            "round-white-headed boy with bow, not another Kratos. Depict family deaths as non-graphic "
            "aftermath, avoid showing violence against children. No image generation, only prompts. "
            + composition.RULES +
            "Do not use the proper name Kratos in the image prompt; describe the reference avatar. "
            "When era-specific character references are supplied, return reference_era equal to one "
            "of their exact keys. The era follows this shot's narration, not the end of the story."
            "When a cast registry is supplied, use its EXACT character names in characters and select "
            "an explicit character_variants key for every required registered identity in the shot. "
            "Variants determine age and costume from this shot's narration, not the end of the story. "
            "Do not select or draw absent cast members. Copy the chosen variant's appearance into its "
            "character's scene description; never swap another character's costume or hero marking."
        )
        try:
            limit = max(1, min(8, int(config.get("WORKSPACE_PLAN_CONCURRENCY") or 4)))
        except (TypeError, ValueError):
            limit = 4
        semaphore = asyncio.Semaphore(limit)
        completed = 0

        async def batch_worker(offset):
            nonlocal completed
            batch = shots[offset:offset + 12]
            async with semaphore:
                raw = await llm.chat([
                    {"role": "system", "content": rules + "\nApproved style: " + style.get("visuals", {}).get("art_style", "")},
                    {"role": "user", "content": json.dumps({"full_story": p["script"],
                        "character_reference_eras": [] if cast.registry(p) else list(style.get("workspace_character_references", {})),
                        "cast_registry": cast.summary(p),
                        "context_before": [s["text"] for s in shots[max(0, offset - 2):offset]],
                        "context_after": [s["text"] for s in shots[offset + len(batch):offset + len(batch) + 2]],
                        "requested_shots": [{"id": s["id"], "narration": s["text"]} for s in batch]}, ensure_ascii=False)}
                ], model=model, effort="low", attempts=1, hedge=False, label="Preparing shots")
            prepared = []
            rows = parse_json(raw).get("shots")
            if not isinstance(rows, list) or [r.get("id") for r in rows if isinstance(r, dict)] != [s["id"] for s in batch]:
                raise ValueError("Invalid storyboard response")
            for shot, row in zip(batch, rows):
                if (not isinstance(row.get("prompt"), str) or len(row["prompt"].strip()) < 80
                        or not isinstance(row.get("location_id"), str) or not row["location_id"].strip()
                        or not isinstance(row.get("characters"), list)
                        or any(not isinstance(c, str) or not c.strip() for c in row["characters"])
                        or len({c.strip().casefold() for c in row["characters"]}) != len(row["characters"])):
                    raise ValueError("Incomplete storyboard response")
                prompt = composition.compose(row["prompt"], style.get("visuals", {}).get("art_style", ""), row["characters"])
                if composition.contradictory(prompt):
                    raise ValueError("Contradictory image composition")
                selected_refs = refs
                era_refs = {} if cast.registry(p) else style.get("workspace_character_references") or {}
                if era_refs:
                    era = row.get("reference_era")
                    if era not in era_refs:
                        raise ValueError("Missing explicit reference era")
                    selected_refs = copy.deepcopy(era_refs[era])
                    for ref in selected_refs:
                        ref["owner"] = "style"
                        if api._file_digest(store.style_dir(p["style_id"]), ref["path"]) != ref.get("sha256"):
                            raise ValueError("Character reference changed")
                scene = dict(shot, prompt=prompt, location_id=row["location_id"].strip(),
                    characters=row["characters"], references=copy.deepcopy(selected_refs), prompt_author="configured_text_proxy",
                    status="idle", human_review={"state": "unreviewed"})
                if cast.registry(p):
                    scene["character_variants"] = copy.deepcopy(row.get("character_variants") or {})
                    scene["references"], block = cast.author(p, scene, selected_refs)
                    if block:
                        scene["prompt"] += "\n" + block
                    cast.validate(p, scene)
                prepared.append(scene)
            completed += len(prepared)
            progress(completed, len(shots), f"{completed}/{len(shots)} shots ready · {limit} batches in parallel")
            return prepared

        progress(0, len(shots), f"Preparation · {limit} batches in parallel")
        tasks = [asyncio.create_task(batch_worker(offset)) for offset in range(0, len(shots), 12)]
        try:
            batches = await asyncio.gather(*tasks)
            result = [shot for batch in batches for shot in batch]
            inputs(p)  # Recheck physical reference files before publishing the complete plan.
            for shot in result:
                if any(api._file_digest(store.project_dir(p["id"]) if r.get("owner") == "project" else
                        store.style_dir(p["style_id"]), r["path"]) != r.get("sha256") for r in shot["references"]):
                    raise ValueError("Reference changed during preparation")
                cast.validate(p, shot)
            if signature(p) != stamp or p.get("scenes"):
                raise ValueError("Project changed")
            p["planning_receipt"] = {"input_hash": stamp, "text_model": model, "created_at": now(),
                "shots": {str(s["id"]): api._hash(_shot_evidence(s)) for s in result}}
            p.update(scenes=result, scenes_script_hash=timing.script_hash(p["script"]), render=None)
            progress(len(result), len(result), "Shots ready: test the first three images")
            store.save_project(p)
        except BaseException as error:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if not isinstance(error, Exception):
                raise
            raise RuntimeError("Preparation failed. No existing shots or media were replaced; you can try again") from None
    await pipeline._step(p, "planning", run)


def install(app):
    if getattr(app.state, "workspace_planning_installed", False):
        return
    router = APIRouter(prefix="/api/workspace")

    @router.post("/projects/{pid}/images/prepare", status_code=202)
    async def start(pid: str, body: dict):
        p = api._project(pid, writable=True)
        if generation.batch_running(pid) or pid in generation._active_projects:
            raise HTTPException(409, "An image generation is in progress")
        if body.get("script_hash") != api._hash(p.get("script") or ""):
            raise HTTPException(409, "The script has changed; refresh the project")
        inputs(p)
        pipeline.start(pid, prepare)
        return api._full(p)

    static = next((i for i, r in enumerate(app.router.routes) if getattr(r, "path", None) == ""), len(app.router.routes))
    app.router.routes[static:static] = router.routes
    app.state.workspace_planning_installed = True
