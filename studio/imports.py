"""Import existing production records without assuming they were published."""

import hashlib
import json
import os
from pathlib import Path
from studio.store import ROOT, now

CHANNELS = [
    (
        "mma_en",
        "Cage Dispatch",
        "@CageDispatch",
        "MMA",
        "news",
        "#00d8ef",
        "CD",
        "auto",
        5,
    ),
    (
        "football_en",
        "Pitch Dispatch",
        "@PitchDispatch",
        "Football",
        "news",
        "#bcf158",
        "PD",
        "auto",
        5,
    ),
    (
        "boxing_en",
        "Ring Dispatch",
        "@RingDispatch",
        "Boxe",
        "news",
        "#ffa65d",
        "RD",
        "manual",
        5,
    ),
    (
        "oddly_specific_en",
        "Oddly Specific Lives",
        "@OddlySpecificLives",
        "POV · vies",
        "pov",
        "#f27fbc",
        "OSL",
        "manual",
        14,
    ),
    (
        "oddly_expensive_en",
        "Oddly Expensive Lives",
        "@OddlyExpensiveLives",
        "Économie",
        "pov",
        "#ebdb5f",
        "OEL",
        "manual",
        14,
    ),
    (
        "oddly_things_en",
        "Oddly Specific Things",
        "@OddlySpecificThings",
        "POV · objets",
        "pov",
        "#b090f7",
        "OST",
        "manual",
        14,
    ),
    (
        "survivors_account",
        "The Survivor’s Account",
        "@SurvivorsAccount",
        "Histoire · témoignages",
        "history",
        "#dfa981",
        "SA",
        "manual",
        20,
    ),
    (
        "frontier_blood",
        "Frontier Blood",
        "@FrontierBlood",
        "Histoire · frontière",
        "history",
        "#e76a6a",
        "FB",
        "manual",
        20,
    ),
]


def read(path, fallback=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback if fallback is not None else {}


def relative(path):
    try:
        p = Path(path).resolve()
        return str(p.relative_to(ROOT)) if p.is_file() else ""
    except (ValueError, TypeError):
        return ""


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def seed(store):
    with store.db() as c:
        for key, name, handle, niche, fmt, accent, initials, mode, _ in CHANNELS:
            if c.execute(
                "SELECT 1 FROM studio_channels WHERE key=?", (key,)
            ).fetchone():
                continue
            p = c.execute(
                "SELECT id FROM delamain_projects WHERE lower(name)=lower(?) OR channel_id=?",
                (name, handle),
            ).fetchone()
            pid = (
                p["id"]
                if p
                else c.execute(
                    """INSERT INTO delamain_projects(name,channel_id,niche,lang,autonomy,video_tool)
                VALUES(?,?,?,'en',?,?)""",
                    (name, handle, niche, mode, fmt),
                ).lastrowid
            )
            c.execute(
                "INSERT INTO studio_channels(project_id,key,format,accent,initials,template_key,updated_at) VALUES(?,?,?,?,?,?,?)",
                (pid, key, fmt, accent, initials, key, now()),
            )
        for p in c.execute(
            "SELECT p.* FROM delamain_projects p LEFT JOIN studio_channels s ON s.project_id=p.id WHERE s.project_id IS NULL"
        ).fetchall():
            c.execute(
                "INSERT INTO studio_channels(project_id,key,format,initials,updated_at) VALUES(?,?,?,?,?)",
                (
                    p["id"],
                    "legacy_" + str(p["id"]),
                    "unassigned",
                    p["name"][:2].upper(),
                    now(),
                ),
            )


def import_productions(store):
    channels = {c["key"]: c for c in store.channels()}
    existing = {v["imported_key"] for v in store.videos()}
    by_key = {v["imported_key"]: v for v in store.videos()}
    count = 0
    for job in sorted((ROOT / "news").glob("*/*")):
        ch = channels.get(job.parent.name)
        if not ch or not job.is_dir():
            continue
        brief = read(job / "brief.json")
        plan = brief or read(job / "plan.json")
        if not plan:
            continue
        key = str(job.relative_to(ROOT))
        result = read(job / "result.json")
        audit = read(job / "rights_audit.json")
        result_file = relative(result.get("file", ""))
        thumb = ""
        choice = ""
        try:
            choice = (job / "thumb_choice.txt").read_text().strip()
            thumb = relative(choice if Path(choice).is_absolute() else ROOT / choice)
        except OSError:
            pass
        if not thumb:
            thumb = relative(job / Path(choice).name) if choice else ""
        if not thumb:
            thumb = relative(job / "thumb.jpg")
        if key in existing:
            old = by_key[key]
            restored = {}
            if not old["thumb_path"] and thumb:
                restored["thumb_path"] = thumb
            if not old["video_path"] and result_file:
                restored["video_path"] = result_file
            if restored:
                store.update("studio_videos", old["id"], restored)
            continue
        receipt = read(job / "discord_receipt.json")
        delivered = (job / "discord_done").exists() or bool(receipt)
        if not delivered:
            delivered = bool(result.get("sent_at") or result.get("discord_sent"))
        link = result.get("link") or result.get("gofile") or ""
        if not link and (job / "gofile_link.txt").exists():
            link = (job / "gofile_link.txt").read_text().strip()
        status = "delivered" if delivered else ("review" if result or link else "idea")
        sources = plan.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        store.add_video(
            {
                "channel_id": ch["id"],
                "title": plan.get("title") or job.name,
                "status": status,
                "minutes": result.get("minutes") or 5,
                "script": "\n\n".join(
                    s.get("narration", "") for s in brief.get("segments", [])
                ),
                "sources": sources,
                "description": plan.get("description", ""),
                "asset_dir": key,
                "thumb_path": thumb,
                "video_path": result_file,
                "external_url": link,
                "engine_ref": {"kind": "news", "job": key, "brief": bool(brief)},
                "quality_status": (
                    "verified" if result.get("reviewed_at") else "unknown"
                ),
                "rights_status": (
                    "blocked"
                    if audit.get("automation_clearance") == "blocked"
                    else "unknown"
                ),
                "rights_manifest": audit,
                "event_at": (
                    plan.get("date", "") + "T12:00:00+02:00" if plan.get("date") else ""
                ),
                "imported_key": key,
                "created_at": result.get("reviewed_at") or now(),
            }
        )
        count += 1
    # These folders belong to the recent engines and may be mounted outside the checkout.
    roots = [Path(os.getenv("POV_DATA_DIR") or ROOT / "work/prod"), ROOT / "data/pov"]
    history_roots = [
        Path(os.getenv("HISTORY_DATA_DIR") or ROOT / "work/history"),
        ROOT / "data/history",
    ]
    for base, kind in [(p, "pov") for p in roots] + [
        (p, "history") for p in history_roots
    ]:
        for f in (
            (base / "projects").glob("*/project.json")
            if kind == "pov"
            else base.glob("*/project.json")
        ):
            pr = read(f)
            key = str(f.resolve())
            if not pr or key in existing:
                continue
            template = pr.get("template") or (pr.get("options") or {}).get("channel")
            if kind == "pov" and not template and pr.get("channel_id"):
                template = read(
                    base / "channels" / pr["channel_id"] / "channel.json"
                ).get("template")
            ch = channels.get(template)
            if not ch:
                # No guessing which of several channels owns a production.
                continue
            rd = pr.get("render") or {}
            asset = relative(f)
            store.add_video(
                {
                    "channel_id": ch["id"],
                    "title": pr.get("title") or f.parent.name,
                    "status": (
                        "review" if rd else "script" if pr.get("script") else "idea"
                    ),
                    "minutes": pr.get("minutes") or 14,
                    "script": (
                        pr.get("script")
                        if isinstance(pr.get("script"), str)
                        else (pr.get("fos") or {}).get("text", "")
                    ),
                    "asset_dir": str(Path(asset).parent) if asset else "",
                    "engine_ref": {"kind": kind, "pid": pr["id"], "base": str(base)},
                    "imported_key": key,
                }
            )
            existing.add(key)
            count += 1
    return count
