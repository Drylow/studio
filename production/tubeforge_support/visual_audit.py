"""Read-only visual review through the configured proxy; run media work on VPS.

This produces attributed review evidence. It never rewrites prompts, selects an
image, generates a correction, publishes, or claims a primary-agent inspection.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

REVISION = "visual-audit-2026-10-21-v5"
CATEGORIES = ("drawing_style", "identity", "anatomy", "furniture_geometry", "scene_action", "background_cast")
SEVERITIES = {"none", "minor", "major", "uncertain"}
PRIMARY_RISKS = {"desk_camera_change", "owner_flagged"}
RUBRIC = """Inspect the actual attached pixels, not just the prompt. This is a
cartoon narrative frame. References have separate explicit roles: drawing-only
fixes linework, adult proportions, face/eye design, cel shadows and finish;
identity fixes actor/wardrobe, never a permanent expression; scene-anchor fixes
room/materials, not the camera. The final image is the CANDIDATE to evaluate.
Check all six categories:
drawing_style: same drawn finish, no flattened/chibi redesign or unintended
flesh-tone faces when the reference characters have pure-white cartoon skin.
identity: named cast, wardrobe, no duplicated or missing actor required by action.
anatomy: exactly one pupil per visible eye, attached arms/hands, supported props.
furniture_geometry: seated pelvis/back supported by chair behind the body,
legs under an opaque table, operator at the desk working edge, chest facing the
keyboard and screen. Keyboard nearest operator, display beyond keyboard; hands
reach from the operator side. Flag sideways perching and a rotated actor pasted
onto a frontal desk/room. Profile/over-shoulder is fine only with coherent desk
projection. A standing visitor beside a desk is legitimate. If spatial alignment
cannot be established confidently, use uncertain rather than invent a rationale.
scene_action: plausible staging for the narration, motivated expression, consistent
scene materials/landmarks where a scene anchor is provided. A purposeful object
insert does not require a whole person. Do not demand text legibility or identical
framing. Do not invent invisible anatomy or a room behind the camera.
When provided, the primary-authored beat identifies the particular instant being
illustrated. Compare it with the named cast and actual pixels. Do not invent an
additional required actor from a different narration clause. The authored beat
does not excuse a concrete visible defect or a contradiction with the story.
background_cast: inspect EVERY visible bystander, patron and side character,
including small people behind the main action. When the drawing and identity
references use round white cartoon heads, ALL humans follow that construction,
with white exposed skin and the same eye language. Merely painting a realistic
human face white is insufficient: long human jaws, realistic noses, facial age
creases, flesh or gray skin and naked gray silhouettes are real defects. Preserve
distinct hair/clothes and motivated expressions; do not require bald clones.
Inventory visible extras by position, or state that none are present. Rear or
occluded faces may legitimately hide eyes. A front-facing blank disc is not a
finished face. Follow the reference eye design rather than impose a different
channel's eyes. Inspect the OUTER head contour as well as the skin colour: a
human-shaped nose, ear or angular jaw projecting from a background profile does
not match a simple circular-head reference. Hair may wrap the circle and profile
views may hide one eye; they do not excuse changing the underlying head anatomy.
Apply this also to depicted people inside photos, screens, paintings and mirrors.
Return JSON only: {"confidence":0.0,"checks":[{"category":"drawing_style",
"severity":"none|minor|major|uncertain","reason":"specific visible evidence"},
...one entry for EACH of the six categories...],"summary":"short diagnosis"}.
Report uncertainty honestly. A successful API request is not visual approval.

Severity calibration: none means no actual visible defect, not an obligation to
find a flaw. Minor/major must name a concrete error, not describe a valid choice.
In a profile or rear three-quarter view, ONE visible eye or no visible face is
NORMAL. Never flag the occluded second eye, blank back of head, or hidden wardrobe
as a missing body part or identity failure. Perspective may crop or hide props.
A still illustrates ONE meaningful beat of its narration, not every clause or
the entire sequence simultaneously. A notebook and conversation can illustrate
discussing priorities; no written proof or literal priority diagram is required.
Expressions vary with the action, so a polite smile can be legitimate.
Conversely peach skin replacing white cartoon skin, a distinctly flat simplified
redesign, or a workstation with actor and keyboard facing different axes are
real defects. Inspect desk/chair/body alignment even when two hands touch keys;
attached limbs alone do not establish a plausible operator position. Compare the
drawing's detail/shadows/proportions as well as its broad cartoon category.
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(data):
    """Fail closed on incomplete, uncertain, or internally inconsistent output."""
    if not isinstance(data, dict):
        raise ValueError("Audit must be a JSON object")
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (float, int)) or not 0 <= confidence <= 1:
        raise ValueError("Invalid confidence")
    checks = data.get("checks")
    if not isinstance(checks, list) or len(checks) != len(CATEGORIES):
        raise ValueError("Incomplete audit")
    if {c.get("category") for c in checks if isinstance(c, dict)} != set(CATEGORIES):
        raise ValueError("Missing or duplicate audit category")
    for c in checks:
        if c.get("severity") not in SEVERITIES or not isinstance(c.get("reason"), str) or not c["reason"].strip():
            raise ValueError("Invalid visual evidence")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Missing audit summary")
    levels = {c["severity"] for c in checks}
    decision = "reject" if "major" in levels else "needs_review" if levels != {"none"} or confidence < .85 else "pass"
    return dict(data, decision=decision)


def route_primary(result, item):
    """Risk routing is independent of the model verdict; never hide a miss."""
    risks = item.get("risk_flags", [])
    if not isinstance(risks, list) or any(r not in PRIMARY_RISKS for r in risks):
        raise ValueError("Unknown primary-review risk")
    return dict(result, primary_review_reasons=list(risks),
                requires_primary_review=bool(risks) or result.get("decision") != "pass")


def image_part(path, side=1024):
    import base64
    import io
    from PIL import Image

    with Image.open(path) as src:
        im = src.convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}


async def review(item, model, output, client_chat=None):
    if sys.platform == "win32":
        raise RuntimeError("Visual media review must run on the production VPS")
    if client_chat is None:
        from app import llm
        client_chat = llm.chat
    refs = item.get("references", [])
    if any(r.get("role") not in {"drawing-only", "identity", "scene-anchor"} for r in refs):
        raise ValueError("Each reference needs its actual role")
    paths = [Path(r["path"]) for r in refs] + [Path(item["path"])]
    hashes = [digest(p.read_bytes()) for p in paths]
    spec = dict(item=item, model=model, hashes=hashes, revision=REVISION, rubric_sha256=digest(RUBRIC.encode()))
    key = digest(json.dumps(spec, sort_keys=True).encode())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / (key + ".json")
    evidence = dict(spec, cache_key=key, id=item["id"], source="cli_proxy_vision", state="submitting")
    try:
        with receipt.open("x", encoding="utf-8") as handle:
            json.dump(evidence, handle, indent=2)
    except FileExistsError:
        previous = json.loads(receipt.read_text(encoding="utf-8"))
        if previous.get("cache_key") != key:
            raise ValueError("Unexpected audit cache")
        # Errors and ambiguous outcomes require an explicit retry decision.
        return dict(previous, decision=previous.get("decision") or "needs_review", cache_hit=True)
    evidence["cache_hit"] = False
    context = ("\nNarration: " + item.get("narration", "")
               + "\nCast: " + json.dumps(item.get("characters", []))
               + "\nPrimary-authored beat: " + item.get("authored_action", ""))
    content = [{"type": "text", "text": RUBRIC + context}]
    for ref, path in zip(refs, paths):
        content.extend([{"type": "text", "text": "REFERENCE role=" + ref["role"]}, image_part(path)])
    content.extend([{"type": "text", "text": "CANDIDATE — inspect this image"}, image_part(paths[-1])])
    try:
        raw = await client_chat([{"role": "user", "content": content}], model=model, effort="low", attempts=1, hedge=False, timeout=180, label="Visual audit")
        evidence["raw_response"] = raw
        clean = raw.strip()
        if clean.startswith("```") and clean.endswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        evidence.update(validate(json.loads(clean)), state="proxy_reviewed")
        if hashes != [digest(p.read_bytes()) for p in paths]:
            raise ValueError("Source changed during review")
    except Exception as exc:
        evidence.update(state="needs_review", decision="needs_review", error_type=type(exc).__name__,
                        error_status=getattr(exc, "status", None), error_message=str(exc)[:1000])
    receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return evidence


async def run(manifest, output, model):
    if sys.platform == "win32":
        raise RuntimeError("Run this audit on the VPS, never on the PC")
    from app import llm
    catalog = await llm.client().get(llm._url("/models"), headers=llm._headers(), timeout=20)
    catalog.raise_for_status()
    if model not in {row.get("id") for row in catalog.json().get("data", []) if isinstance(row, dict)}:
        raise ValueError("Audit model is absent from the current proxy catalog; no image requests sent")
    sem = asyncio.Semaphore(3)
    # Validate risk declarations before sending any request.
    for item in manifest["items"]:
        route_primary({}, item)

    async def one(item):
        async with sem:
            return await review(item, model, output)

    results = await asyncio.gather(*(one(item) for item in manifest["items"]))
    results = [route_primary(result, item) for result, item in zip(results, manifest["items"])]
    report = {"source": "cli_proxy_vision", "revision": REVISION, "model": model,
              "results": results, "counts": {key: sum(r.get("decision") == key for r in results) for key in ("pass", "needs_review", "reject")},
              "flagged_ids": [r["id"] for r in results if r["requires_primary_review"]],
              "primary_agent_inspection_claimed": False}
    (Path(output) / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    report = asyncio.run(run(json.loads(Path(args.manifest).read_text(encoding="utf-8")), args.output, args.model))
    print(json.dumps({"counts": report["counts"], "flagged_ids": report["flagged_ids"]}))
