"""Title-to-script through the selected text proxy; keep image authoring separate."""
import asyncio
import copy
import json
import math
from pathlib import Path
import uuid

from fastapi import APIRouter, HTTPException
from app import config, llm, pipeline, store
from app.util import now, parse_json, write_json
from . import workspace_api as api, workspace_management as management

STYLES = {"survivor-patch", "survivor-alien-aftermath"}
SKILLS = ("voice-anchoring-skill.md", "script-structures-skill.md",
          "retention-mechanics-skill.md", "humanizer-skill.md", "greenlight-audit-skill.md")
ANCHORS = ("N1FAy1ZjlPI", "SIZXW0ABD9g", "1AF04-V4Yao")


def allowed(p):
    cid = p.get("profile_id") or p.get("channel_id")
    channel = management._channel(cid) if cid else None
    return bool(channel and cid not in api.PROFILE_NAMES and not channel.get("historical_profile")
                and p.get("style_id") in STYLES)


def resources():
    root = Path(config.get("STUDIO_ROOT") or "")
    if not config.get("STUDIO_ROOT") or not root.is_dir():
        raise HTTPException(409, "Le dossier des consignes du studio doit être configuré")
    prompts = Path(__file__).parent / "scriptwriting"
    try:
        rules = "\n\n".join((root / "skills/facelessos" / name).read_text(encoding="utf-8") for name in SKILLS)
        anchors = []
        for vid in ANCHORS:
            transcript = root / "work/survivor-launch-2026-10-12/reference-transcripts" / (vid + ".txt")
            if not transcript.is_file():
                continue
            text = transcript.read_text(encoding="utf-8")
            words = text.split()
            if len(words) < 180:
                raise ValueError("Missing real voice anchor")
            anchors.append({"url": "https://www.youtube.com/watch?v=" + vid,
                            "source_kind": "local_competitor_transcript",
                            "raw_excerpt": " ".join(words[:210])})
        if not anchors:
            # A clone contains our own writing samples, never private third-party transcripts.
            examples = json.loads((prompts / "house-voice-examples.json").read_text(encoding="utf-8"))
            for example in examples:
                if example.get("source_kind") != "original_house_narration" or len(example.get("excerpt", "").split()) < 180:
                    raise ValueError("Invalid original writing sample")
            anchors = examples
        return {"writer": (prompts / "survival.txt").read_text(encoding="utf-8"),
                "reviewer": (prompts / "review.txt").read_text(encoding="utf-8"),
                "length_editor": (prompts / "length.txt").read_text(encoding="utf-8"),
                "skills": rules, "anchors": anchors}
    except (OSError, ValueError):
        raise HTTPException(409, "Consignes Faceless OS ou exemples d’écriture manquants") from None


def request(p, body):
    if not allowed(p):
        raise HTTPException(409, "L’écriture depuis un titre est disponible pour les deux styles Survivor")
    if p.get("settings", {}).get("language", "English") != "English":
        raise HTTPException(409, "Les références d’écriture actuelles sont en anglais")
    if body.get("script_hash") != api._hash(p.get("script") or ""):
        raise HTTPException(409, "Le texte a changé ; actualisez avant de demander un brouillon")
    title = api._text(body.get("title", p.get("title", "")), "titre", required=True).strip()
    brief = api._text(body.get("brief", ""), "consignes")
    minutes = body.get("minutes", 15)
    if (len(title) > 240 or len(brief) > 8000 or "\x00" in title + brief
            or type(minutes) not in (int, float) or not math.isfinite(minutes) or not 3 <= minutes <= 30):
        raise HTTPException(422, "Titre de 240 caractères, consignes de 8 000 caractères et durée de 3 à 30 minutes maximum")
    model = (p.get("model_snapshot") or {}).get("text_model")
    if not model or not config.get("PROXY_BASE_URL") or not config.get("PROXY_API_KEY"):
        raise HTTPException(409, "Choisissez le modèle texte et configurez le CLI Proxy")
    source = resources()
    return {"title": title, "brief": brief, "minutes": minutes, "model": model,
            "script_hash": body["script_hash"], "title_before": p.get("title"), "source": source,
            "words_min": round(minutes * 145 * .8), "words_max": round(minutes * 145 * 1.2)}


def output(raw, prepared, audited=False, strict_length=True):
    data = parse_json(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid script response")
    text = data.get("script")
    if (not isinstance(text, str) or "\x00" in text or "```" in text or "[VISUAL" in text.upper()
            or len(text.encode("utf-8")) > api.MAX_SCRIPT
            or not (max(1, prepared["words_min"] - 5) if audited and strict_length else max(100, prepared["words_min"] // 2))
                <= len(text.split()) <= (prepared["words_max"] + 5 if audited and strict_length else prepared["words_max"] * 3)):
        raise ValueError("Invalid narration or duration")
    bible = data.get("story_bible")
    if not isinstance(bible, dict) or any(not isinstance(bible.get(key), list) or not bible[key]
            for key in ("cast", "locations", "chronology", "setups_and_payoffs", "persistent_states")):
        raise ValueError("Missing continuity bible")
    if audited:
        audit = data.get("audit")
        if not isinstance(audit, dict) or any(not isinstance(audit.get(key), list)
                or any(not isinstance(x, str) for x in audit[key])
                for key in ("issues", "unsupported_claims", "fixes", "limitations")):
            raise ValueError("Missing honest writing review")
        groups = audit.get("groups")
        if not isinstance(groups, dict) or any(not isinstance(groups.get(key), dict)
                or not isinstance(groups[key].get("evidence"), str) or not groups[key]["evidence"].strip()
                or not isinstance(groups[key].get("findings"), list)
                or any(not isinstance(x, str) for x in groups[key]["findings"])
                for key in "ABCDE"):
            raise ValueError("Missing Faceless OS review evidence")
        for key in "ABCDE":
            for finding in groups[key]["findings"]:
                if finding not in audit["issues"]:
                    audit["issues"].append(finding)
    data["script"] = text.strip()
    return data


def apply(p, draft, expected_hash):
    if api._hash(p.get("script") or "") != expected_hash:
        raise HTTPException(409, "Le texte a changé ; le brouillon ne le remplace pas")
    if p.get("voiceover") or p.get("scenes") or p.get("render"):
        raise HTTPException(409, "Ce projet a déjà des médias ; utilisez une nouvelle vidéo pour ce script")
    p.update(script=draft["script"], custom_script=False, title=draft["title"], title_auto=False,
             target_duration_seconds=None, prompts_approved=False,
             workspace_story_bible=copy.deepcopy(draft["story_bible"]))
    store.add_history(p, "configured_text_proxy", draft["script"])
    p.setdefault("human_reviews", {}).pop("script", None)
    p["steps"]["script"].update(state="done", msg="Script écrit depuis le titre · à lire avant la voix")
    p["workspace_script_writer"]["applied_draft_id"] = draft["id"]
    return store.save_project(p)


def finish(p, prepared, result, folder):
    """Persist a completed review; also permits recovery of an already received reply."""
    if (api._hash(p.get("script") or "") != prepared["script_hash"]
            or p.get("title") != prepared["title_before"]):
        raise ValueError("Project edited while writing")
    draft = {**result, "id": folder.name, "title": prepared["title"],
             "word_count": len(result["script"].split()), "created": now(),
             "review_kind": "model_review_not_user_approval", "desired_minutes": prepared["minutes"]}
    write_json(folder / "result.json", draft)
    writer = p.setdefault("workspace_script_writer", {})
    writer.update(draft=draft, state="draft_ready", request_hash=prepared["script_hash"])
    if (not (p.get("script") or "").strip() and not p.get("voiceover") and not p.get("scenes")
            and not result["audit"]["issues"] and not result["audit"]["unsupported_claims"]):
        apply(p, draft, prepared["script_hash"])
        writer["state"] = "applied"
    store.save_project(p)
    return writer["state"]


async def generate(p, prepared):
    async def run(progress):
        source = prepared["source"]
        source_data = {"title": prepared["title"], "brief": prepared["brief"],
            "language": "English", "desired_minutes": prepared["minutes"],
            "word_count_window": [prepared["words_min"], prepared["words_max"]],
            "style_id": p["style_id"], "voice_reference_data": source["anchors"]}
        folder = store.project_dir(p["id"]) / "script-generations" / uuid.uuid4().hex
        folder.mkdir(parents=True)
        write_json(folder / "request.json", {**source_data, "model": prepared["model"],
                   "script_hash_before": prepared["script_hash"], "automatic_retries": 0,
                   "automatic_hedges": False, "maximum_text_calls": 3,
                   "stages": ["draft", "review", "length_edit_only_if_needed"],
                   "skills": list(SKILLS), "created": now()})
        partial, last = [], 0

        def delta(piece):
            nonlocal last
            partial.append(piece)
            chars = sum(map(len, partial))
            if chars > last + 1200:
                last = chars
                progress(0, 2, f"Écriture en cours… environ {chars // 6} mots reçus")

        try:
            progress(0, 2, "Écriture depuis le titre…")
            priority = ("\n\nPRIORITY CONTRACT: The skill documents above are reference guidance, not a different output schema. "
                "Return only the JSON required at the start. User word_count_window overrides ANY default word counts, "
                "runtimes, source quotas or documentary templates in those documents. This is original fictional narration. "
                "Do not lengthen the episode to fit every template. Keep its ending within the actual requested length.")
            raw = await llm.chat([{"role": "system", "content": source["writer"] + "\n\nFACELESS OS RULES:\n" + source["skills"] + priority},
                {"role": "user", "content": json.dumps(source_data, ensure_ascii=False)}],
                model=prepared["model"], effort="medium", attempts=1, hedge=False,
                timeout=900, on_delta=delta, label="Écriture du script")
            (folder / "draft-response.txt").write_text(raw, encoding="utf-8")
            first = output(raw, prepared)
            progress(1, 2, "Vérification du rythme, de l’histoire et de la cohérence…")
            raw = await llm.chat([{"role": "system", "content": source["reviewer"] + "\n\nFACELESS OS RULES:\n" + source["skills"] + priority},
                {"role": "user", "content": json.dumps({**source_data, "draft": first,
                    "actual_draft_word_count": len(first["script"].split()),
                    "length_instruction": "Rewrite within the supplied word_count_window. Count narration only; shorten or expand the draft as needed."}, ensure_ascii=False)}],
                model=prepared["model"], effort="medium", attempts=1, hedge=False,
                timeout=900, label="Vérification du script")
            (folder / "review-response.txt").write_text(raw, encoding="utf-8")
            result = output(raw, prepared, audited=True, strict_length=False)
            total = 2
            count = len(result["script"].split())
            if not prepared["words_min"] - 5 <= count <= prepared["words_max"] + 5:
                total = 3
                progress(2, 3, "Ajustement de la longueur du script…")
                raw = await llm.chat([{"role": "system", "content": source["length_editor"]},
                    {"role": "user", "content": json.dumps({"reviewed_result": result,
                        "actual_narration_word_count": count,
                        "word_count_window": [prepared["words_min"], prepared["words_max"]],
                        "aim_for_words": round(prepared["minutes"] * 145)}, ensure_ascii=False)}],
                    model=prepared["model"], effort="medium", attempts=1, hedge=False,
                    timeout=900, label="Ajustement de la durée du script")
                (folder / "length-response.txt").write_text(raw, encoding="utf-8")
                result = output(raw, prepared, audited=True, strict_length=False)
                count = len(result["script"].split())
                if not prepared["words_min"] - 5 <= count <= prepared["words_max"] + 5:
                    result["audit"]["issues"].append(
                        f"Longueur à ajuster : {count} mots, fenêtre demandée {prepared['words_min']}-{prepared['words_max']} mots")
            state = finish(p, prepared, result, folder)
            progress(total, total, "Script prêt" if state == "applied" else "Brouillon prêt · texte existant conservé")
        except asyncio.CancelledError:
            raise
        except Exception:
            p.setdefault("workspace_script_writer", {})["state"] = "error"
            # Never surface upstream text, headers or credentials through job errors.
            raise RuntimeError("Écriture interrompue ou réponse incomplète. Le texte existant est conservé ; aucun nouvel appel automatique.") from None
    await pipeline._step(p, "script", run)


def install(app):
    if getattr(app.state, "workspace_writing_installed", False):
        return
    router = APIRouter(prefix="/api/workspace/projects")

    @router.post("/{pid}/script/generate")
    async def write(pid: str, body: dict):
        p = api._project(pid, True)
        prepared = request(p, body)
        p.setdefault("workspace_script_writer", {}).update(state="queued", request_hash=prepared["script_hash"])
        store.save_project(p)
        try:
            pipeline.start(pid, generate, prepared)
        except pipeline.Busy:
            raise HTTPException(409, "Une opération est déjà en cours") from None
        return api._full(p)

    @router.post("/{pid}/script/apply-draft")
    async def adopt(pid: str, body: dict):
        p = api._project(pid, True)
        draft = (p.get("workspace_script_writer") or {}).get("draft")
        if not allowed(p) or not draft or draft["id"] != body.get("draft_id"):
            raise HTTPException(409, "Ce brouillon n’est plus disponible")
        apply(p, draft, body.get("script_hash"))
        p["workspace_script_writer"]["state"] = "applied"
        return api._full(store.save_project(p))

    existing = list(app.router.routes)
    app.include_router(router)
    added = app.router.routes[len(existing):]
    mount = next((i for i, route in enumerate(existing) if getattr(route, "path", None) == ""), len(existing))
    app.router.routes[:] = existing[:mount] + added + existing[mount:]
    app.state.workspace_writing_installed = True
