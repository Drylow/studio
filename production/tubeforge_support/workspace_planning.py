"""Prepare fictional-channel shots using the configured text proxy and real word clock."""
import copy
import json
import math

from fastapi import APIRouter, HTTPException
from app import config, llm, pipeline, store
from app.steps import scenes as timing
from app.util import parse_json, now
from . import workspace_api as api, workspace_management as management, workspace_generation as generation


def allowed(p):
    cid = p.get("profile_id") or p.get("channel_id")
    if not cid:
        return False
    channel = management._channel(cid)
    return bool(channel and cid not in api.PROFILE_NAMES and not channel.get("historical_profile"))


def signature(p):
    style = store.get_style(p.get("style_id")) or {}
    return api._hash({"script": p.get("script"), "voice": p.get("voiceover"),
                      "style": style, "models": p.get("model_snapshot"), "settings": p.get("settings")})


def authored(p, s):
    receipt = p.get("planning_receipt") or {}
    return (allowed(p) and s.get("prompt_author") == "configured_text_proxy"
            and receipt.get("input_hash") == signature(p)
            and receipt.get("shots", {}).get(str(s["id"])) == api._hash(
                {k: s.get(k) for k in ("text", "prompt", "location_id", "characters", "references", "start", "end")}))


def inputs(p):
    if not allowed(p):
        raise HTTPException(409, "Cette chaîne conserve son découpage et ses prompts écrits par Codex")
    if p.get("scenes"):
        raise HTTPException(409, "Les plans existants sont conservés ; la préparation ne les remplace pas")
    if api._duration_info(p)["kind"] != "actual":
        raise HTTPException(409, "Générez d’abord la voix du script enregistré")
    if not config.get("PROXY_BASE_URL") or not config.get("PROXY_API_KEY"):
        raise HTTPException(409, "Le proxy texte du studio doit être configuré")
    model = (p.get("model_snapshot") or {}).get("text_model") or p["settings"]["script"].get("model")
    if not model:
        raise HTTPException(409, "Choisissez le modèle texte du projet")
    words = store.load_words(p["id"])
    if (not words or any(type(w.get(k)) not in (int, float) or not math.isfinite(w[k]) for w in words for k in ("s", "e"))
            or any(type(w.get(k)) is not int for w in words for k in ("c0", "c1"))):
        raise HTTPException(409, "L’alignement des mots de la voix est manquant")
    if any(w["c0"] < 0 or w["c1"] > len(p["script"]) or w["c1"] <= w["c0"] for w in words):
        raise HTTPException(409, "L’alignement des mots ne correspond pas au script")
    if (any(w["s"] < 0 or w["e"] < w["s"] or w["e"] > p["voiceover"]["duration"] + .1 for w in words)
            or any(a["s"] > b["s"] or a["c1"] > b["c0"] for a, b in zip(words, words[1:]))
            or p["voiceover"].get("script_hash", api._hash(p["script"])) != api._hash(p["script"])):
        raise HTTPException(409, "L’alignement et la voix doivent correspondre au script actuel")
    style = store.get_style(p["style_id"]) or {}
    refs = copy.deepcopy(style.get("workspace_references") or [])
    if not refs:
        raise HTTPException(409, "Ajoutez les références approuvées du style")
    for ref in refs:
        ref["owner"] = "style"
        digest = api._file_digest(store.style_dir(p["style_id"]), ref.get("path"))
        if not digest or ref.get("sha256") != digest or ref.get("review_state") != "verified":
            raise HTTPException(409, "Une référence du style est manquante ou a changé")
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
            "Return JSON {shots:[{id,location_id,characters:[named identities],prompt}]}. "
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
            "aftermath, avoid showing violence against children. No image generation, only prompts."
        )
        try:
            for offset in range(0, len(shots), 12):
                batch = shots[offset:offset + 12]
                progress(offset, len(shots), f"Préparation des plans {offset + 1} à {offset + len(batch)}")
                raw = await llm.chat([
                    {"role": "system", "content": rules + "\nApproved style: " + style.get("visuals", {}).get("art_style", "")},
                    {"role": "user", "content": json.dumps({"full_story": p["script"], "previous_shots": result[-2:],
                        "requested_shots": [{"id": s["id"], "narration": s["text"]} for s in batch]}, ensure_ascii=False)}
                ], model=model, effort="low", attempts=1, label="Préparation des plans")
                rows = parse_json(raw).get("shots")
                if not isinstance(rows, list) or [r.get("id") for r in rows if isinstance(r, dict)] != [s["id"] for s in batch]:
                    raise ValueError("Invalid storyboard response")
                for shot, row in zip(batch, rows):
                    if (not isinstance(row.get("prompt"), str) or len(row["prompt"].strip()) < 80
                            or not isinstance(row.get("location_id"), str) or not row["location_id"].strip()
                            or not isinstance(row.get("characters"), list)
                            or any(not isinstance(c, str) or not c.strip() for c in row["characters"])):
                        raise ValueError("Incomplete storyboard response")
                    prompt = style.get("visuals", {}).get("art_style", "") + "\nScene: " + row["prompt"].strip()
                    result.append(dict(shot, prompt=prompt, location_id=row["location_id"].strip(),
                        characters=row["characters"], references=copy.deepcopy(refs), prompt_author="configured_text_proxy",
                        status="idle", human_review={"state": "unreviewed"}))
            inputs(p)  # Recheck physical reference files before publishing the complete plan.
            if signature(p) != stamp or p.get("scenes"):
                raise ValueError("Project changed")
            p["planning_receipt"] = {"input_hash": stamp, "text_model": model, "created_at": now(),
                "shots": {str(s["id"]): api._hash({k: s.get(k) for k in
                    ("text", "prompt", "location_id", "characters", "references", "start", "end")}) for s in result}}
            p.update(scenes=result, scenes_script_hash=timing.script_hash(p["script"]), render=None)
            progress(len(result), len(result), "Plans prêts : testez les trois premières images")
            store.save_project(p)
        except Exception:
            raise RuntimeError("La préparation a échoué. Aucun plan existant ni média n’a été remplacé ; vous pouvez réessayer") from None
    await pipeline._step(p, "planning", run)


def install(app):
    if getattr(app.state, "workspace_planning_installed", False):
        return
    router = APIRouter(prefix="/api/workspace")

    @router.post("/projects/{pid}/images/prepare", status_code=202)
    async def start(pid: str, body: dict):
        p = api._project(pid, writable=True)
        if generation.batch_running(pid) or pid in generation._active_projects:
            raise HTTPException(409, "Une génération d’images est en cours")
        if body.get("script_hash") != api._hash(p.get("script") or ""):
            raise HTTPException(409, "Le script a changé ; actualisez le projet")
        inputs(p)
        pipeline.start(pid, prepare)
        return api._full(p)

    static = next((i for i, r in enumerate(app.router.routes) if getattr(r, "path", None) == ""), len(app.router.routes))
    app.router.routes[static:static] = router.routes
    app.state.workspace_planning_installed = True
