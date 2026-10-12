"""Étape 3 · Visuels — bible visuelle, personnages récurrents, prompts par scène, images."""
import asyncio
import random
import re
import time
from pathlib import Path

from .. import config, events, llm, store
from ..util import parse_json

MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]
CHUNK = 14
def save_throttled(p: dict, force: bool = False) -> None:
    store.save_throttled(p, force)


def _style_ref_paths(p: dict) -> list[Path]:
    v = p["settings"]["visuals"]
    if not v.get("use_style_refs"):
        return []
    base = store.style_dir(p["style_id"])
    return [base / r for r in v.get("style_refs", []) if (base / r).exists()][:1]


# ------------------------------------------------------------------ bible + personnages

def active_chars(p: dict) -> list[dict]:
    """Personnages gardés par l'utilisateur (case « Garder »)."""
    return [c for c in p.get("characters", []) if c.get("enabled", True)]


async def build_bible(p: dict) -> dict:
    v = p["settings"]["visuals"]
    prompt = (
        "You are the art director of an illustrated narrated YouTube video. Read the narration script and "
        "write the visual bible: era, places, recurring locations, season/weather progression, period-accurate "
        "costumes, props and vehicles — 3 to 6 sentences.\n"
        'Return JSON only: {"setting":"..."}'
        f"\n\nART STYLE:\n{v['art_style']}\n\nTITLE: {p['title']}\n\nSCRIPT:\n{p['script']}"
    )
    coros = [llm.chat([{"role": "user", "content": prompt}], model=p["settings"]["script"].get("model") or config.get("FAST_MODEL"), effort="low",
                      label="Bible visuelle")]
    want_chars = v.get("auto_characters", True) and not any(c.get("source") == "auto" for c in p["characters"])
    if want_chars:
        coros.append(detect_characters(p, max_n=4, generate_images=False))
    res = await asyncio.gather(*coros)
    try:
        setting = parse_json(res[0]).get("setting", "")
    except Exception:  # noqa: BLE001
        setting = res[0][:1500]
    p["bible"] = {"setting": setting}
    store.save_project(p)
    events.log(f"✓ Bible visuelle : {setting[:180]}", "ok")
    return p["bible"]


async def detect_characters(p: dict, max_n: int = 8, generate_images: bool = True) -> list[dict]:
    """Propose les personnages récurrents du script (l'utilisateur choisit ensuite qui garder)."""
    v = p["settings"]["visuals"]
    existing = p.get("characters", [])
    ex_txt = "\n".join(f"- {c['id']}: {c['name']}" for c in existing)
    prompt = (
        "You are the art director of an illustrated narrated YouTube video. List the recurring characters of "
        f"this script, most important first (max {max_n}). Include the protagonist (the 'you' of a "
        "second-person script). Only characters who appear in at least 2 moments of the story.\n"
        "For each, write a precise VISUAL description consistent with the art style below: gender, age, build, "
        "exact clothing/uniform with colors, headwear, accessories and one distinctive detail that makes them "
        "recognizable. Describe their DEFAULT appearance for most of the story — not injuries, disguises or "
        "changes that only happen later.\n"
        + (f"ALREADY DEFINED (do not repeat them):\n{ex_txt}\n" if ex_txt else "")
        + '\nReturn JSON only: {"characters":[{"id":"snake_case_id","name":"short display name",'
        '"description":"...","role":"protagonist|recurring","scenes_estimate":<int>}]}'
        f"\n\nART STYLE:\n{v['art_style']}\n\nTITLE: {p['title']}\n\nSCRIPT:\n{p['script']}"
    )
    data = parse_json(await llm.chat([{"role": "user", "content": prompt}],
                                     model=p["settings"]["script"].get("model") or config.get("FAST_MODEL"), effort="medium", label="Détection des personnages"))
    items = data.get("characters", []) if isinstance(data, dict) else data
    ids = {c["id"] for c in existing}
    names = {c["name"].lower() for c in existing}
    added = []
    for c in items[:max_n]:
        cid = re.sub(r"[^a-z0-9_]+", "_", str(c.get("id") or c.get("name", "perso")).lower()).strip("_")[:30]
        if not cid or cid in ids or str(c.get("name", "")).lower() in names or not c.get("description"):
            continue
        ch = {"id": cid, "name": c.get("name", cid), "description": c["description"], "image": None,
              "every_image": False, "enabled": True, "source": "auto", "role": c.get("role", "recurring"),
              "scenes_estimate": c.get("scenes_estimate")}
        p["characters"].append(ch)
        added.append(ch)
        ids.add(cid)
    store.save_project(p)
    events.log(f"✓ Personnages : {', '.join(c['name'] for c in added) or 'aucun nouveau'}", "ok")
    if generate_images and added and v.get("use_character_refs", True):
        await ensure_character_images(p, added)
    return added


async def generate_character_image(p: dict, c: dict, owner_dir: Path | None = None) -> str:
    v = p["settings"]["visuals"]
    prompt = (f"{v['art_style']}\n\nCharacter design sheet of {c['name']}: {c['description']}. "
              "Single character, full body, standing in a neutral three-quarter pose, plain light grey "
              "background, no other characters, no text.")
    refs = [llm.png_for_upload(x) for x in _style_ref_paths(p)]
    data = await llm.generate_image(prompt, v.get("image_model", config.get("IMAGE_MODEL")), "1:1", refs or None,
                                    label=f"Fiche {c['name']}", provider=v.get("image_provider", "cli_proxy"))
    pdir = owner_dir or store.project_dir(p["id"])
    n = 1
    while (pdir / "characters" / f"{c['id']}_v{n}.png").exists():
        n += 1
    rel = f"characters/{c['id']}_v{n}.png"
    (pdir / rel).parent.mkdir(parents=True, exist_ok=True)
    (pdir / rel).write_bytes(data)
    c["image"] = rel
    return rel


async def ensure_character_images(p: dict, only: list[dict] | None = None) -> None:
    if not p["settings"]["visuals"].get("use_character_refs", True):
        return
    todo = only if only is not None else [c for c in active_chars(p) if not c.get("image")]

    async def one(c):
        c["status"] = "running"
        save_throttled(p)
        t0 = time.time()
        try:
            await generate_character_image(p, c)
            c["status"], c["error"] = "done", None
            events.log(f"✓ Fiche personnage « {c['name']} » dessinée ({events.fmt_duration(time.time() - t0)})", "ok")
        except Exception as e:  # noqa: BLE001 — un personnage sans référence n'est pas bloquant
            c["status"], c["error"] = "error", str(e)[:300]
            events.log(f"✗ Fiche « {c['name']} » : {str(e)[:160]}", "error")
        save_throttled(p)
    await asyncio.gather(*(one(c) for c in todo))
    store.save_project(p)


# ------------------------------------------------------------------ prompts de scènes

def _prompt_rules(p: dict) -> str:
    return (
        "For each scene write an image prompt describing ONE single frame that illustrates what the narration "
        "says at that exact moment.\n"
        "- Describe the shot type (wide establishing, medium, close-up, over-the-shoulder, low angle, top-down, "
        "or first-person POV with the viewer's own hands visible), the subject, their action and emotion, "
        "era-accurate setting details, time of day, weather, lighting and mood.\n"
        "- Visualize literally and concretely what is said. For abstract lines (numbers, thoughts, time passing) "
        "invent a clear visual: a symbolic scene, a map, a document, an object close-up.\n"
        "- Vary shot types and compositions; never use the same framing twice in a row.\n"
        "- Keep continuity: characters keep the same clothes, places stay consistent, time and season progress "
        "with the story.\n"
        "- NO REALISTIC HUMANS, ever: every person (crowds, police, children, passers-by, even far in the "
        "background) is a stylized character of the video's art style. Never write 'realistic', 'photo', "
        "'detailed face' or skin details; describe people by clothing, posture and action.\n"
        "- Sequences: when a frame shows the same place and the same moment/action as the previous scene (a chase "
        "continuing, the same room, the same conversation), set \"continues\": true and write in \"link\" what "
        "stays identical (place, light, outfits, objects) and what changes in this new moment. Otherwise "
        "\"continues\": false.\n"
        "- Content safety (mandatory): no gore, no blood, no visible wounds, no detailed corpses; show danger "
        "indirectly (smoke, distant explosions, ruins, fear, a fallen helmet). No hate symbols (no swastikas — "
        "use plain banners/generic insignia). No real living people.\n"
        "- Do NOT describe the art style (it is added automatically). No text or lettering in the image unless "
        "essential (then max 3 words).\n"
        "- 40 to 90 words per prompt, in English.\n"
        'Return JSON only: {"scenes":[{"id":<scene id>,"prompt":"...","characters":["character_id"],'
        '"continues":false,"link":"",'
        '"motion":"zoom_in|zoom_out|pan_left|pan_right|pan_up|pan_down"}]}. "characters" = ids of the defined '
        "characters visible in the frame (empty list if none)."
    )


def _context_header(p: dict) -> str:
    chars = "\n".join(f"- {c['id']}: {c['name']} — {c['description']}" for c in active_chars(p))
    setting = (p.get("bible") or {}).get("setting", "")
    return (f"VIDEO TITLE: {p['title']}\n\nVISUAL BIBLE:\n{setting}\n\n"
            f"DEFINED CHARACTERS:\n{chars or '(none)'}\n\n")


async def _prompts_for_chunk(p: dict, chunk: list[dict], before: list[dict], after: list[dict]) -> dict:
    lines = []
    for s in before:
        lines.append(f"(context, already done) {s['text']}")
    for s in chunk:
        lines.append(f"SCENE id={s['id']} ({s['end'] - s['start']:.1f}s): {s['text']}")
    for s in after:
        lines.append(f"(context, next) {s['text']}")
    msg = _context_header(p) + _prompt_rules(p) + "\n\nSCENES:\n" + "\n".join(lines)
    for attempt in range(3):
        try:
            data = parse_json(await llm.chat([{"role": "user", "content": msg}],
                                             model=p["settings"]["script"].get("model") or config.get("FAST_MODEL"), effort="low",
                                             label=f"Prompts scènes {chunk[0]['id']}–{chunk[-1]['id']}"))
            items = data["scenes"] if isinstance(data, dict) else data
            out = {int(x["id"]): x for x in items if x.get("prompt")}
            if all(s["id"] in out for s in chunk):
                return out
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
    return out


def _fix_motions(scenes: list[dict]) -> None:
    prev = None
    for s in scenes:
        if s.get("motion") not in MOTIONS or s["motion"] == prev:
            s["motion"] = random.choice([m for m in MOTIONS if m != prev])
        prev = s["motion"]


async def write_prompts(p: dict, progress=None, only_missing: bool = True) -> None:
    if not p.get("bible"):
        if progress:
            progress(0, 1, "Bible visuelle et personnages…")
        await build_bible(p)
    scenes = p["scenes"]
    targets = [s for s in scenes if not (only_missing and s.get("prompt"))]
    chunks = [targets[i:i + CHUNK] for i in range(0, len(targets), CHUNK)]
    events.log(f"Écriture de {len(targets)} prompts d'images en {len(chunks)} lots parallèles")
    ids = {s["id"]: k for k, s in enumerate(scenes)}
    done = 0
    char_ids = {c["id"] for c in active_chars(p)}

    async def run(chunk):
        nonlocal done
        k0, k1 = ids[chunk[0]["id"]], ids[chunk[-1]["id"]]
        res = await _prompts_for_chunk(p, chunk, scenes[max(0, k0 - 2):k0], scenes[k1 + 1:k1 + 3])
        for s in chunk:
            r = res.get(s["id"])
            if r:
                s["prompt"] = r["prompt"].strip()
                s["characters"] = [c for c in r.get("characters", []) if c in char_ids]
                s["motion"] = r.get("motion")
                s["continues"] = bool(r.get("continues")) and s is not scenes[0]
                s["link"] = (r.get("link") or "").strip()
        done += len(chunk)
        if progress:
            progress(done, len(targets), f"Prompts {done}/{len(targets)}")
        save_throttled(p)

    await asyncio.gather(*(run(c) for c in chunks), ensure_character_images(p))
    _fix_motions(scenes)
    save_throttled(p, force=True)


# ------------------------------------------------------------------ images

NO_HUMANS = ("MANDATORY RULES: (1) It is strictly impossible to show a realistic human: ALL people — main "
             "characters, crowds, police, children, background figures — are stylized characters drawn exactly "
             "in this art style; no realistic faces, no photographic people. (2) Every visible hand has exactly "
             "five fingers — never six, never four; five fingers minimum and maximum.")


def compose_prompt(p: dict, s: dict, with_char_refs: bool, with_style_ref: bool,
                   prev: dict | None = None) -> str:
    v = p["settings"]["visuals"]
    chars = [c for c in active_chars(p) if c["id"] in (s.get("characters") or []) or c.get("every_image")]
    parts = [v["art_style"], NO_HUMANS, "SCENE: " + (s.get("prompt") or s["text"])]
    if prev is not None:
        parts.append(
            "CONTINUITY: the attached image marked as the previous frame is the shot just before this one in the "
            f"same sequence (previous frame: {prev.get('prompt') or prev['text']}). Stay in the same world: same "
            "place, lighting, color palette, outfits and props. "
            + (f"What links them: {s['link']}. " if s.get("link") else "")
            + "Show the NEW moment described in SCENE with a fresh camera angle — do not copy the previous frame.")
    if chars:
        parts.append("CHARACTERS IN THIS FRAME:\n" + "\n".join(f"- {c['name']}: {c['description']}" for c in chars))
        marks = [c for c in chars if c.get("signature")]
        if marks:
            parts.append(" ".join(f"{c['name']} must be instantly recognizable: {c['signature']}." for c in marks))
    if with_style_ref:
        parts.append("The FIRST attached image is an art-style reference: match its drawing style, line work, "
                     "character design and coloring exactly, but do not copy its content or composition.")
    if prev is not None:
        parts.append("The image right after the style reference is the PREVIOUS FRAME of the sequence.")
    varying = [c["name"] for c in chars if c.get("outfit_varies")]
    if with_char_refs and varying:
        parts.append(f"For {', '.join(varying)}: copy the head, face and distinctive mark from the character sheet, "
                     "but dress them for THIS scene's era and role (the sheet's outfit is only neutral).")
    if with_char_refs:
        parts.append("The attached character sheet(s) show the exact design of the characters to reuse (clothing, "
                     "colors, proportions). Create a brand-new composition for this scene; do not copy the "
                     "sheet's pose or plain background.")
    ratio = "vertical 9:16" if v.get("aspect") == "9:16" else "widescreen 16:9"
    parts.append(f"{ratio} frame, full-bleed illustration. No text, no captions, no watermark, no border.")
    return "\n\n".join(parts)


async def _safer_prompt(p: dict, prompt: str) -> str:
    return (await llm.chat([{"role": "user", "content":
        "This image prompt was rejected by the image model's safety filter. Rewrite it so it is clearly "
        "acceptable: remove gore, blood, wounds, corpses, explicit violence, weapons aimed at people, hate "
        "symbols and real people's names, while keeping the scene's meaning and mood (imply danger indirectly). "
        f"Return only the new prompt.\n\nPROMPT:\n{prompt}"}], model=p["settings"]["script"].get("model") or config.get("FAST_MODEL"), effort="low",
        label="Prompt adouci (modération)")).strip()


def _next_image_name(pdir: Path, s: dict) -> str:
    n = 1
    while (pdir / "images" / f"s{s['id']:03d}_v{n}.png").exists():
        n += 1
    return f"images/s{s['id']:03d}_v{n}.png"


def continuity_mode(p: dict) -> str:
    return p["settings"]["visuals"].get("continuity", "smart")


def previous_scene(p: dict, s: dict) -> dict | None:
    scenes = p["scenes"]
    for i, x in enumerate(scenes):
        if x["id"] == s["id"]:
            return scenes[i - 1] if i > 0 else None
    return None


def wants_prev_ref(p: dict, s: dict) -> bool:
    mode = continuity_mode(p)
    return mode == "always" or (mode == "smart" and bool(s.get("continues")))


async def generate_scene_image(p: dict, s: dict, edit_instruction: str | None = None,
                               use_prev: bool | None = None) -> None:
    v = p["settings"]["visuals"]
    pdir = store.project_dir(p["id"])
    model = s.get("image_model") or v.get("image_model", config.get("IMAGE_MODEL"))
    s["status"], s["error"] = "running", None
    try:
        if edit_instruction:
            if not s.get("image"):
                raise ValueError("Pas d'image à ajuster")
            prompt = (f"Edit this image: {edit_instruction}. Keep the same art style, characters and overall "
                      "composition unless the instruction says otherwise. No text, no watermark.")
            refs = [llm.png_for_upload(pdir / s["image"])]
        else:
            refs = []
            style_refs = _style_ref_paths(p)
            for path in style_refs:
                refs.append(llm.png_for_upload(path))
            char_refs = []
            if v.get("use_character_refs", True):
                for c in active_chars(p):
                    if (c["id"] in (s.get("characters") or []) or c.get("every_image")) and c.get("image"):
                        if (pdir / c["image"]).exists():
                            char_refs.append(llm.png_for_upload(pdir / c["image"], 1024))
            prev = previous_scene(p, s)
            if use_prev is None:
                use_prev = wants_prev_ref(p, s)
            if not (use_prev and prev and prev.get("image") and (pdir / prev["image"]).exists()):
                prev = None
            if prev is not None:
                refs.append(llm.png_for_upload(pdir / prev["image"], 1024))
            refs += char_refs[: 1 if prev is not None else 2]
            prompt = compose_prompt(p, s, bool(char_refs), bool(style_refs), prev)
        data = None
        for attempt in range(3):
            try:
                data = await llm.generate_image(prompt, model, v.get("aspect", "16:9"), refs or None,
                                                label=f"Image #{s['id']}", provider=v.get("image_provider", "cli_proxy"))
                break
            except llm.ModerationError:
                if attempt == 2:
                    raise
                events.log(f"⚠ Image #{s['id']} refusée par la modération — prompt adouci, nouvel essai", "warn")
                safer = await _safer_prompt(p, s.get("prompt") or s["text"])
                s["prompt"] = safer
                if not edit_instruction:
                    prompt = compose_prompt(p, s, bool(char_refs), bool(style_refs), prev)
        rel = _next_image_name(pdir, s)
        (pdir / rel).parent.mkdir(parents=True, exist_ok=True)
        (pdir / rel).write_bytes(data)
        s["image"], s["status"], s["uploaded"] = rel, "done", False
        s.pop("clip", None)
    except Exception as e:  # noqa: BLE001
        s["status"], s["error"] = "error", str(e)[:400]
        raise


async def generate_images(p: dict, scene_ids: list[int] | None = None, progress=None, only_missing=True) -> dict:
    scenes = [s for s in p["scenes"] if (scene_ids is None or s["id"] in scene_ids)
              and not (only_missing and s.get("image") and scene_ids is None)]
    for s in scenes:
        s["status"] = "queued"
    save_throttled(p, force=True)
    done, failed = 0, 0
    t_start = time.time()
    if scenes:
        events.log(f"Génération de {len(scenes)} image(s) — jusqu'à {config.get_int('IMAGE_CONCURRENCY')} en "
                   "parallèle sur les comptes du proxy")

    # Continuité : une scène liée à la précédente attend que celle-ci soit dessinée pour la prendre en
    # référence ; les séquences indépendantes, elles, partent toutes en parallèle sur les comptes.
    ready = {s["id"]: asyncio.Event() for s in scenes}
    order = {x["id"]: i for i, x in enumerate(p["scenes"])}

    async def one(s):
        nonlocal done, failed
        prev = previous_scene(p, s)
        if prev is not None and prev["id"] in ready and wants_prev_ref(p, s):
            await ready[prev["id"]].wait()
        t0 = time.time()
        try:
            await generate_scene_image(p, s)
            ok = True
        except Exception as e:  # noqa: BLE001 — l'erreur est notée sur la scène
            failed += 1
            ok = False
            events.log(f"✗ Image #{s['id']} : {str(e)[:160]}", "error")
        done += 1
        if ok:
            rate = done / max(1.0, time.time() - t_start) * 60
            left = (len(scenes) - done) / max(rate / 60, 1e-6)
            events.log(f"✓ Image #{s['id']} ({events.fmt_duration(time.time() - t0)}) — {done}/{len(scenes)}, "
                       f"{rate:.0f} img/min, reste ≈ {events.fmt_duration(left)}", "ok")
        if progress:
            progress(done, len(scenes), f"Images {done}/{len(scenes)}" + (f" — {failed} échec(s)" if failed else ""))
        save_throttled(p)
        ready[s["id"]].set()

    chains = sum(1 for s in scenes if wants_prev_ref(p, s))
    if chains:
        events.log(f"Continuité : {chains} image(s) dessinée(s) à partir de l'image précédente ({continuity_mode(p)})")
    await asyncio.gather(*(one(s) for s in sorted(scenes, key=lambda x: order.get(x["id"], 0))))
    save_throttled(p, force=True)
    return {"done": done - failed, "failed": failed}


async def rewrite_scene_prompt(p: dict, s: dict) -> str:
    idx = next(i for i, x in enumerate(p["scenes"]) if x["id"] == s["id"])
    res = await _prompts_for_chunk(p, [s], p["scenes"][max(0, idx - 2):idx], p["scenes"][idx + 1:idx + 3])
    r = res.get(s["id"]) or {}
    if r.get("prompt"):
        s["prompt"] = r["prompt"].strip()
        s["characters"] = [c for c in r.get("characters", []) if c in {x["id"] for x in active_chars(p)}]
        s["continues"] = bool(r.get("continues")) and idx > 0
        s["link"] = (r.get("link") or "").strip()
    return s.get("prompt", "")


def _img_part(path: Path, side: int = 640) -> dict:
    import base64
    import io

    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}


async def critique_and_fix(p: dict, s: dict, reason: str = "") -> str:
    """L'IA regarde l'image actuelle encadrée par la précédente et la suivante, comprend ce qui ne va pas
    (par rapport au texte, au style, à la continuité, à la raison donnée) et écrit un meilleur prompt."""
    pdir = store.project_dir(p["id"])
    idx = next(i for i, x in enumerate(p["scenes"]) if x["id"] == s["id"])
    prev = p["scenes"][idx - 1] if idx > 0 else None
    nxt = p["scenes"][idx + 1] if idx + 1 < len(p["scenes"]) else None
    content: list[dict] = [{"type": "text", "text": (
        _context_header(p) + "You are the art director reviewing ONE frame of the video, framed by its neighbours.\n"
        f"ART STYLE (mandatory): {p['settings']['visuals']['art_style']}\n{NO_HUMANS}\n\n"
        + (f"PREVIOUS FRAME — narration: {prev['text']}\nprompt: {prev.get('prompt', '')}\n\n" if prev else "")
        + f"CURRENT FRAME (the one to fix) — narration: {s['text']}\nprompt used: {s.get('prompt', '')}\n\n"
        + (f"NEXT FRAME — narration: {nxt['text']}\nprompt: {nxt.get('prompt', '')}\n\n" if nxt else "")
        + (f"WHAT THE USER DISLIKES: {reason}\n\n" if reason else "The user dislikes the current frame without "
           "saying why: find the most likely reasons.\n\n")
        + "Images attached in order: " + ", ".join(x for x, ok in (("previous frame", prev and prev.get("image")),
                                                               ("CURRENT frame", s.get("image")),
                                                               ("next frame", nxt and nxt.get("image"))) if ok)
        + ".\nDiagnose what is wrong with the CURRENT frame (does not match the narration, breaks continuity with "
          "its neighbours, realistic humans, off-style, confusing composition, repeated framing…), then write a "
          "better image prompt (40-90 words, English, no art-style words) that fixes it and flows between the "
          "previous and next frames.\n"
          'Return JSON only: {"problem":"short diagnosis in French","prompt":"...","continues":true|false,'
          '"link":"what stays the same as the previous frame"}')}]
    for x in (prev, s, nxt):
        if x and x.get("image") and (pdir / x["image"]).exists():
            content.append(_img_part(pdir / x["image"]))
    data = parse_json(await llm.chat([{"role": "user", "content": content}], model=p["settings"]["script"].get("model") or config.get("SCRIPT_MODEL"),
                                     effort="low", label=f"Diagnostic image #{s['id']}"))
    s["critique"] = (data.get("problem") or "").strip()
    if data.get("prompt"):
        s["prompt"] = data["prompt"].strip()
    s["continues"] = bool(data.get("continues")) and idx > 0
    s["link"] = (data.get("link") or "").strip()
    events.log(f"🧠 Image #{s['id']} : {s['critique'][:200]}", "info")
    return s["prompt"]
