"""Miniatures YouTube (style « POV mains au premier plan, roman graphique » par défaut)."""
import asyncio

from .. import config, events, llm, store
from ..util import parse_json


async def write_concepts(title: str, context: str, style: str, count: int, instruction: str = "",
                         forced_text: str = "", language: str = "") -> list[dict]:
    msg = (
        f"You design viral YouTube thumbnails. Video title: {title}\n\n"
        + (f"Video content / idea:\n{context}\n\n" if context else "")
        + f"THUMBNAIL STYLE:\n{style}\n\n"
        + (f"EXTRA INSTRUCTIONS: {instruction}\n\n" if instruction else "")
        + f"Propose {count} clearly different thumbnail concepts. Each is ONE striking image that makes people "
          "curious: a single clear focal point, strong emotion or tension, story-telling props readable at a "
          "glance, strong contrast, works at small size. Content safety: no gore, no blood, no hate symbols.\n"
        + (f'Every concept must leave room for the text "{forced_text}".\n' if forced_text else
           "Optionally add a 1-3 word bold text (or leave it empty)"
           + (f", written in {language}" if language else "") + ".\n")
        + 'Return JSON only: {"thumbnails":[{"prompt":"detailed image description, 50-100 words","text":""}]}'
    )
    data = parse_json(await llm.chat([{"role": "user", "content": msg}], model=config.get("FAST_MODEL"),
                                     effort="low", label="Thumbnail concepts"))
    items = (data.get("thumbnails") if isinstance(data, dict) else data) or []
    out = []
    for c in items[:count]:
        if c.get("prompt"):
            out.append({"prompt": c["prompt"], "text": forced_text or c.get("text", "")})
    return out


def thumb_prompt(style: str, concept: dict, with_ref: bool = False) -> str:
    prompt = f"{style}\n\n{concept['prompt']}"
    if with_ref:
        prompt += ("\n\nThe attached image is only an inspiration for subject and composition: redraw everything "
                   "from scratch in the thumbnail style above, do not copy it.")
    if concept.get("text"):
        prompt += (f'\n\nInclude the bold, hand-lettered text "{concept["text"]}" large and perfectly legible, '
                   "placed where it does not cover the focal point.")
    else:
        prompt += "\n\nNo text, no letters, no watermark."
    return prompt


async def generate(p: dict, count: int | None = None, progress=None, instruction: str = "") -> list[dict]:
    t = p["settings"]["thumbnail"]
    count = int(count or t.get("count", 2) or 0)
    if count <= 0:
        return []
    excerpt = " ".join((p.get("script") or "").split()[:900])
    concepts = await write_concepts(p["title"], excerpt, t["style"], count, instruction,
                                    language=p["settings"].get("language", ""))
    pdir = store.project_dir(p["id"])
    (pdir / "thumbs").mkdir(exist_ok=True)
    done = 0

    async def one(c):
        nonlocal done
        try:
            img = await llm.generate_image(thumb_prompt(t["style"], c), t.get("model", config.get("IMAGE_MODEL")), "16:9",
                                           label="Thumbnail", provider=t.get("image_provider", "cli_proxy"))
        except Exception as e:  # noqa: BLE001
            events.log(f"✗ Thumbnail: {str(e)[:160]}", "error")
            return None
        n = 1
        while (pdir / "thumbs" / f"thumb_{n:02d}.png").exists():
            n += 1
        rel = f"thumbs/thumb_{n:02d}.png"
        (pdir / rel).write_bytes(img)
        done += 1
        events.log(f"✓ Thumbnail {done}/{len(concepts)}" + (f" « {c['text']} »" if c.get("text") else ""), "ok")
        if progress:
            progress(done, len(concepts), f"Thumbnails {done}/{len(concepts)}")
        return {"file": rel, "prompt": c["prompt"], "text": c.get("text", "")}

    results = [r for r in await asyncio.gather(*(one(c) for c in concepts)) if r]
    p["thumbnails"] = (p.get("thumbnails") or []) + results
    store.save_project(p)
    if not results:
        raise RuntimeError("No thumbnail could be generated")
    return results
