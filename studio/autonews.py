"""Cage Dispatch and Pitch Dispatch on autopilot.

The hosted worker picks the hottest fresh story of a channel, reads its source
articles, keeps only facts quoted verbatim from them, writes a 4–6 minute
analysis, checks every sentence against those facts, illustrates it with
reusable Wikimedia Commons photos, voices and renders it, makes the thumbnail,
checks the frames, records the rights manifest and marks it ready. Publication
then goes through the usual gates (domain.blockers, publishing.publish).
Nothing here bypasses a rights, freshness, pause or identity check.
"""

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from studio.store import ROOT, now, uid

KEYS = {"mma_en": "MMA / UFC", "football_en": "European football (soccer)"}
REFERENCE = Path(__file__).resolve().parents[1] / "presets/news_thumbnails/approved_2026-10-05/reference_01.png"
THRESHOLD = 7
FRESH_HOURS = 18
_last = {}


def daily_max():
    try:
        return max(0, int(os.getenv("NEWS_AUTO_DAILY", "2")))
    except ValueError:
        return 2


def dry_run():
    """NEWS_AUTO_DRY=1: produce and check, but stop before publication."""
    return os.getenv("NEWS_AUTO_DRY", "") == "1"


def voice_record():
    return {
        "provider": "Algrow",
        "commercial_use": "owner_accepted_risk",
        "automated_access": "owner_accepted_risk",
        "evidence_url": "https://algrow.online/terms",
        "owner_decision": "7 octobre 2026 : le propriétaire garde la voix Algrow pour la "
        "publication automatique en connaissant la restriction d'usage automatisé (section 13).",
        "reviewed_at": now(),
    }


# ── outils remplaçables dans les tests ──────────────────────────────────────


def _chat(messages, **kw):
    from services import ai

    return ai.chat_json(messages, model=ai.text_model(), timeout=300, **kw)


def _fetch(url):
    from services import article
    from studio.newsroom import public_url

    return article.fetch(public_url(url, resolve=True))


def _portraits(name):
    from services import commons

    return commons.portraits(name)


def _image(prompt, refs):
    from services import ai

    return ai.generate_image(prompt, width=1280, height=720, refs=refs, quality="high")


def _build(folder, log):
    from services import news_brief

    return news_brief.build(folder, ROOT / "work", log=log)


@dataclass
class Tools:
    chat: Callable = _chat
    fetch: Callable = _fetch
    portraits: Callable = _portraits
    image: Callable = _image
    build: Callable = _build
    download: Callable = None
    sheets: Callable = None
    decode: Callable = None
    extra: dict = field(default_factory=dict)


# ── choix du sujet ───────────────────────────────────────────────────────────


def initialize(store):
    from studio.newsroom import DEFAULTS, initialize as radar

    radar(store)
    with store.db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_autonews_scores(item_id TEXT PRIMARY KEY, score INTEGER NOT NULL, why TEXT NOT NULL DEFAULT '', scored_at TEXT NOT NULL)"
        )
        # Automatic channels need several outlets: add the checked feeds they lack.
        for ch in channels(store):
            for name, url in DEFAULTS.get(ch["template_key"] or ch["key"], []):
                count = c.execute(
                    "SELECT count(*) FROM studio_news_feeds WHERE channel_id=?", (ch["id"],)
                ).fetchone()[0]
                if count >= 6:
                    break
                c.execute(
                    "INSERT OR IGNORE INTO studio_news_feeds(id,channel_id,name,url) VALUES(?,?,?,?)",
                    (uid(), ch["id"], name, url),
                )


def channels(store):
    return [
        c
        for c in store.channels()
        if (c["template_key"] or c["key"]) in KEYS
        and c["publication_mode"] == "news"
        and c["autonomy"] == "auto"
        and c["enabled"]
        and not c["paused"]
        and c["connected"]
    ]


def paris_day_start(at):
    from studio.domain import TZ

    local = at.astimezone(TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def made_today(store, cid, at):
    """(videos kept, attempts) since midnight in Paris; failed attempts are capped too."""
    row = store.one(
        "SELECT count(*) AS attempts, sum(status!='blocked') AS kept FROM studio_videos WHERE channel_id=? AND json_extract(engine_ref,'$.auto')=1 AND created_at>=?",
        (cid, paris_day_start(at).isoformat()),
    )
    return row["kept"] or 0, row["attempts"] or 0


def busy(store, cid):
    return store.one(
        "SELECT id FROM studio_jobs WHERE kind='news_auto' AND status IN ('queued','running') AND json_extract(payload,'$.channel_id')=?",
        (cid,),
    )


def recent_titles(store, cid, at):
    rows = store.rows(
        "SELECT title FROM studio_videos WHERE channel_id=? AND created_at>=? ORDER BY created_at DESC LIMIT 20",
        (cid, (at - timedelta(days=3)).isoformat()),
    )
    return [r["title"] for r in rows]


def score(store, ch, items, at, tools):
    fresh = [i for i in items if not store.one(
        "SELECT 1 FROM studio_autonews_scores WHERE item_id=?", (i["id"],))]
    if fresh:
        answer = tools.chat(
            [
                {
                    "role": "system",
                    "content": f"""You are the editor of {ch['name']}, a YouTube channel covering {KEYS[ch['template_key'] or ch['key']]} news for English-speaking fans.
Score each headline 0-10 for how much fans will want a 5-minute video about it TODAY.
High: big names, fight announcements or cancellations, injuries and withdrawals, title changes,
call-outs and beefs, controversies, star transfers, sackings, scandals, records, shock results.
Low: routine previews, betting tips, minor leagues, listicles, live blogs, opinion pieces without news,
anything already covered in the recent videos listed. Never score above 3 a story that is not real news.
Return JSON {{"items": [{{"id": "...", "score": 0-10, "why": "short reason"}}]}}.""",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "recent_videos": recent_titles(store, ch["id"], at),
                            "headlines": [
                                {"id": i["id"], "title": i["title"], "summary": (i["summary"] or "")[:300]}
                                for i in fresh
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        known = {i["id"] for i in fresh}
        with store.db() as c:
            for row in answer.get("items") or []:
                if row.get("id") in known:
                    try:
                        value = max(0, min(10, int(row.get("score", 0))))
                    except (TypeError, ValueError):
                        value = 0
                    c.execute(
                        "INSERT OR REPLACE INTO studio_autonews_scores VALUES(?,?,?,?)",
                        (row["id"], value, str(row.get("why", ""))[:300], now()),
                    )
    return store.rows(
        "SELECT i.*,s.score,s.why FROM studio_news_items i JOIN studio_autonews_scores s ON s.item_id=i.id WHERE i.channel_id=? AND i.status='new' AND i.published>=? ORDER BY s.score DESC, i.published DESC",
        (ch["id"], (at - timedelta(hours=FRESH_HOURS)).isoformat()),
    )


def tick(store, at=None, tools=None, every=600):
    """At most every ten minutes: queue one production per channel when a story is hot enough."""
    at = at or datetime.now(timezone.utc)
    key = str(store.path)
    if tools is None and time.monotonic() - _last.get(key, -1e9) < every:
        return []
    _last[key] = time.monotonic()
    app = store.web_app
    if (
        app.config["PREVIEW"]
        or Path(app.config["DEVELOPMENT_MAINTENANCE_PATH"]).exists()
        or store.settings()["paused"]
    ):
        return []
    tools = tools or Tools()
    initialize(store)
    queued = []
    for ch in channels(store):
        with store.db() as c:
            c.execute(
                "UPDATE studio_news_config SET enabled=1,revision=revision+1 WHERE channel_id=? AND enabled=0",
                (ch["id"],),
            )
        kept, attempts = made_today(store, ch["id"], at)
        if busy(store, ch["id"]) or kept >= daily_max() or attempts >= daily_max() * 2 + 1:
            continue
        items = store.rows(
            "SELECT * FROM studio_news_items WHERE channel_id=? AND status='new' AND published>=? ORDER BY published DESC LIMIT 30",
            (ch["id"], (at - timedelta(hours=FRESH_HOURS)).isoformat()),
        )
        if not items:
            continue
        ranked = score(store, ch, items, at, tools)
        best = next((i for i in ranked if i["score"] >= THRESHOLD), None)
        if best:
            queued.append(
                store.enqueue(
                    "news_auto",
                    None,
                    {"channel_id": ch["id"], "item_id": best["id"], "actor": "Delamain"},
                )
            )
            store.log("Delamain", "autonews", f"Sujet choisi ({best['score']}/10) : {best['title']}")
    return queued


# ── fabrication ──────────────────────────────────────────────────────────────


def _norm(text):
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def supported(facts, sources):
    """Keep only facts whose quote is found verbatim in the cited article."""
    kept = []
    for fact in facts:
        source = sources.get(fact.get("source_id"))
        quote = _norm(str(fact.get("quote", "")))
        if source and len(quote.split()) >= 4 and quote in _norm(source["text"]):
            kept.append(
                {
                    "id": f"f{len(kept) + 1}",
                    "claim": str(fact.get("claim", "")).strip(),
                    "quote": str(fact["quote"]).strip(),
                    "source_id": fact["source_id"],
                    "status": fact.get("status", "reported"),
                }
            )
    return kept


def _facts(tools, title, sources):
    answer = tools.chat(
        [
            {
                "role": "system",
                "content": """Extract the verifiable facts of this news story from the articles.
Every fact needs a verbatim quote (6-30 words, copied exactly, same spelling and punctuation) from the
article it comes from. status: confirmed (officially announced or on the record), reported (the outlet
reports it), rumor (unconfirmed, sources say, speculation). Include who, what, when, numbers, direct
quotes of people only if they appear in the article. Also list the main people (full names, max 3) the
story is about, most important first.
Return JSON {"facts": [{"claim": "...", "quote": "...", "source_id": "...", "status": "..."}],
"people": ["Full Name"], "rumor": true|false}.""",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"story": title, "articles": list(sources.values())}, ensure_ascii=False
                ),
            },
        ]
    )
    return answer


SCRIPT_RULES = """Write a 4-6 minute YouTube news analysis in English for {channel} ({sport}).
Use ONLY the supplied facts; attribute claims to their outlet ("according to ..."). Rumors stay rumors
("reportedly", "has not been confirmed"). Never invent quotes, numbers, dates or reactions; a quote must
be copied from a fact. No betting talk. Hook in the first two sentences, then context, then why it
matters, what could happen next (framed as possibilities), and end with a question to the audience and
"drop your thoughts below". Total narration 640-780 words in 6-9 segments.
Return JSON {{"title": "max 90 chars, curiosity but factual, no ALL CAPS sentences",
"title_options": ["3 alternatives"], "segments": [{{"headline": "max 6 words", "lines": ["2-3 short
on-screen points, max 6 words each"], "narration": "...", "source_ids": ["s1"], "fact_ids": ["f1"],
"people": ["names shown in this segment"]}}], "description": "2 short paragraphs, no links",
"tags": ["10-15 tags"], "pinned_comment": "one question", "thumbnail": {{"line1": "max 14 chars",
"line2": "max 14 chars", "people": ["1-2 full names, left first"], "scene": "short background idea
related to the story, no logos, no text, no brands"}}}}."""


def _script(tools, ch, facts, sources, people, feedback=None):
    messages = [
        {
            "role": "system",
            "content": SCRIPT_RULES.format(
                channel=ch["name"], sport=KEYS[ch["template_key"] or ch["key"]]
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "facts": facts,
                    "sources": [{"id": k, "name": v["name"]} for k, v in sources.items()],
                    "people": people,
                    "problems_to_fix": feedback or [],
                },
                ensure_ascii=False,
            ),
        },
    ]
    return tools.chat(messages)


def _factcheck(tools, plan, facts):
    answer = tools.chat(
        [
            {
                "role": "system",
                "content": """You are a strict fact-checker. For each narration sentence, check it is supported by
the facts list (or is clearly framed as opinion, a question or a possibility). Flag invented quotes,
numbers, dates, results, people, rumors stated as confirmed, and claims attributed to the wrong outlet.
Return JSON {"problems": [{"segment": index, "sentence": "...", "issue": "..."}]} (empty when clean).""",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "facts": facts,
                        "segments": [s["narration"] for s in plan.get("segments", [])],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    )
    return answer.get("problems") or []


def illustrate(plan, photos):
    """Each segment shows the person it is about, alternating that person's photos."""
    used = {}
    for seg in plan["segments"]:
        # Only a person this segment is about; never someone else's face (text-only card instead).
        named = seg.get("people") or []
        names = [n for n in named if n in photos] if named else [
            n for n in photos if n.split()[-1].lower() in seg["narration"].lower()
        ]
        if names:
            options = photos[names[0]]
            p = options[used.get(names[0], 0) % len(options)]
            used[names[0]] = used.get(names[0], 0) + 1
            seg["visual"] = {"url": p["url"], "credit": p["credit"], "rights": p["rights"]}
        else:
            seg.pop("visual", None)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "photo"


def _solo(tools, path):
    """Vision check: one clearly visible person, not a group, crowd, poster or text."""
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((768, 768))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    answer = tools.chat(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Photo for a sports news video. Is exactly ONE person the clear main subject, with the "
                        "face visible (not a group, two people side by side, a crowd, a poster, a logo or mostly text)? "
                        'Return JSON {"ok": true|false}.',
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()},
                    },
                ],
            }
        ]
    )
    return answer.get("ok") is True


def _photos(tools, folder, people, per_person=2):
    """Up to two single-person reusable portraits per person, with their rights."""
    from services import commons

    download = tools.download or commons.download
    found = {}
    for name in people[:3]:
        try:
            options = tools.portraits(name)
        except Exception:
            options = []
        kept = []
        for n, option in enumerate(options[:6]):
            dest = folder / "photos" / f"{_slug(name)}-{n}.img"
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                download(option["url"], dest)
                from PIL import Image

                with Image.open(dest) as im:
                    im.verify()
                if not _solo(tools, dest):
                    continue
            except Exception:
                continue
            kept.append(dict(option, file=str(dest)))
            if len(kept) >= per_person:
                break
        if kept:
            found[name] = kept
    return found


def _thumb_rights(photos):
    records = [p["rights"] for p in photos]
    shared = next((r for r in records if "BY-SA" in r["license"]), None)
    main = dict(shared or records[0])
    main["components"] = [
        {"evidence_url": r["evidence_url"], "license": r["license"], "author": r["author"]}
        for r in records
    ]
    main["changes"] = "Portraits cut out, resized and placed on a generated background with text"
    if shared:
        main["adaptation_license"] = shared["license"]
    return main


def _style_only():
    """The approved thumbnail's central band: its text style without any face."""
    from PIL import Image

    with Image.open(REFERENCE) as im:
        w, h = im.size
        band = im.convert("RGB").crop((int(w * 0.37), int(h * 0.45), int(w * 0.71), h))
        out = io.BytesIO()
        band.save(out, "PNG")
    return out.getvalue()


def _thumbnail(tools, folder, ch, plan, photos):
    from PIL import Image

    spec = plan.get("thumbnail") or {}
    names = [n for n in spec.get("people") or [] if n in photos] or list(photos)
    chosen = [photos[n][0] for n in names[:2]]
    if not chosen:
        raise ValueError("Aucune photo sous licence réutilisable pour la miniature.")
    accent = "light blue" if (ch["template_key"] or ch["key"]) == "mma_en" else "bright green"
    line1 = str(spec.get("line1", "")).upper()[:16]
    line2 = str(spec.get("line2", "")).upper()[:16]
    who = " and ".join(p["name"] for p in chosen)
    count = len(chosen)
    prompt = (
        "YouTube sports news thumbnail, 16:9. "
        f"Exactly {count} person{'s' if count > 1 else ''}: {who}, copied from the reference photo"
        f"{'s' if count > 1 else ''} (same face, same person), as sharp, realistic, high-contrast chest-up cut-out"
        f"{'s on the left and right, facing each other' if count == 2 else ' large on the left'}. "
        "No other person, no other face anywhere. "
        f"Background: {spec.get('scene') or 'dramatic arena lights'}, dark moody scene with {accent} glow and light smoke. "
        f'Huge bold condensed 3D text in the centre-bottom on two lines: "{line1}" then "{line2}", '
        f"{accent} gradient with glow on the first line, white with dark outline on the second, "
        "typography and colours like the LAST reference image (it shows the text style only). "
        "No logos, no brands, no belts, no jerseys with club crests, no other text."
    )
    refs = [Path(p["file"]).read_bytes() for p in chosen]
    refs.append(_style_only())
    last = None
    for _ in range(2):
        blob = tools.image(prompt, refs)
        im = Image.open(io.BytesIO(blob)).convert("RGB").resize((1280, 720))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=88)
        check = tools.chat(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f'Check this YouTube thumbnail. Is the big text exactly "{line1} {line2}" with no '
                            f"misspelling and no extra words, are exactly {count} people visible, with no logos, no "
                            "brand names and no distorted faces? "
                            'Return JSON {"ok": true|false, "people_visible": n, "problem": "..."}.',
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
                            },
                        },
                    ],
                }
            ]
        )
        if check.get("ok") is True and check.get("people_visible", count) == count:
            path = folder / "thumb.jpg"
            path.write_bytes(out.getvalue())
            return path, _thumb_rights(chosen)
        last = check.get("problem") or "contrôle refusé"
    raise ValueError("Miniature refusée par le contrôle : " + str(last)[:200])


def _sheets_ok(tools, folder):
    problems = []
    for sheet in sorted((folder / "check").glob("sheet_*.jpg"))[:4]:
        answer = tools.chat(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Contact sheet of an automatically edited sports analysis video (one frame every 5 s, "
                            "time at the bottom right). Normal layout: dark branded card, headline and 2-3 short points on the "
                            "left, usually a photo inside a thin blue frame on the right (portrait photos have dark bars on "
                            "their sides inside the frame: normal; a card without photo, text only, is also normal), one "
                            "caption line at the bottom, the same card for several frames. Report only real problems a viewer would notice: a fully black or glitched frame, "
                            "text cut off or overlapping, gibberish words, a photo that is clearly unrelated or shows a logo. "
                            'Return JSON {"blocking": ["time: problem"]} (empty when fine).',
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64,"
                                + base64.b64encode(sheet.read_bytes()).decode()
                            },
                        },
                    ],
                }
            ]
        )
        problems += answer.get("blocking") or []
    return problems


def description(plan, sources, photos):
    lines = [plan.get("description", "").strip(), "", "Sources:"]
    lines += [f"- {s['name']}: {s['url']}" for s in sources.values()]
    if photos:
        lines += ["", "Photos (Wikimedia Commons):"]
        lines += [
            f"- {p['name']}: {p['rights']['author'][:80]}, {p['rights']['license']}, {p['rights']['evidence_url']}"
            for options in photos.values()
            for p in options
        ]
    return "\n".join(lines).strip()[:4900]


def produce(store, payload, job, tools=None):
    tools = tools or Tools()
    from studio.newsroom import prepare
    from services.news_rights import automation_rights

    item = store.one("SELECT * FROM studio_news_items WHERE id=?", (payload["item_id"],))
    ch = store.channel(payload["channel_id"])
    if not item or not ch or item["channel_id"] != ch["id"]:
        raise ValueError("Sujet ou chaîne introuvable.")
    resume = None
    if payload.get("resume") and item["video_id"]:
        # A stopped video restarts from its saved script: same text, cached voice.
        resume = store.video(item["video_id"])
        if not resume or resume["status"] != "blocked" or not resume["engine_ref"].get("auto"):
            return {"skipped": "nothing to resume"}
        vid = resume["id"]
        folder = ROOT / resume["engine_ref"]["job"]
    elif item["status"] != "new" or item["video_id"]:
        return {"skipped": "already used"}
    else:
        vid = prepare(store, item["id"], item["revision"], "Delamain")
        folder = ROOT / "work/studio/productions" / vid
        folder.mkdir(parents=True, exist_ok=True)
        ref = {"kind": "news", "job": str(folder.relative_to(ROOT)), "brief": True, "auto": True}
        store.update("studio_videos", vid, {"engine_ref": ref, "asset_dir": ref["job"]})
    store.update("studio_videos", vid, {"status": "creating", "error": ""})
    try:
        return _produce(store, ch, item, vid, folder, job, tools, automation_rights, resume)
    except Exception as error:
        store.update(
            "studio_videos", vid, {"status": "blocked", "error": str(error)[:800]}
        )
        store.log("Delamain", "autonews", f"Vidéo arrêtée ({item['title'][:80]}) : {str(error)[:200]}")
        raise


def _produce(store, ch, item, vid, folder, job, tools, automation_rights, resume=None):
    from studio.imports import digest, relative
    from services import news_brief

    saved = folder / "brief.json"
    if resume and saved.is_file():
        plan = json.loads(saved.read_text(encoding="utf-8"))
        sources = {s["id"]: s for s in plan["sources"]}
        wanted = list(dict.fromkeys(
            [n for s in plan["segments"] for n in s.get("people") or []]
            + list((plan.get("thumbnail") or {}).get("people") or [])))
        job.update(0.36, "Reprise : photos sous licence réutilisable")
        photos = _photos(tools, folder, wanted)
        illustrate(plan, photos)
        news_brief.validate(plan)
        saved.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return _media(store, ch, vid, folder, job, tools, automation_rights, plan, sources, photos)
    job.update(0.05, "Lecture des articles sources")
    listed = json.loads(item["sources"] or "[]") or [{"name": "Source", "url": item["url"]}]
    sources = {}
    for i, s in enumerate(listed[:4]):
        try:
            got = tools.fetch(s["url"])
        except Exception:
            continue
        if got.get("words", 0) >= 120:
            sid = f"s{len(sources) + 1}"
            sources[sid] = {
                "id": sid,
                "name": s.get("name") or got.get("title") or "Source",
                "url": s["url"],
                "published": s.get("published") or item["published"],
                "text": got["text"],
            }
    if not sources:
        raise ValueError("Aucun article source lisible : pas de vidéo sans faits vérifiables.")

    job.update(0.12, "Faits cités mot pour mot dans les sources")
    extracted = _facts(tools, item["title"], sources)
    facts = supported(extracted.get("facts") or [], sources)
    if len(facts) < 5:
        raise ValueError(f"Seulement {len(facts)} faits retrouvés mot pour mot dans les sources.")
    people = [str(p) for p in extracted.get("people") or []][:3]
    notes = "VERIFIED FACTS (quoted in sources)\n" + "\n".join(
        f"[{f['id']}/{f['source_id']}/{f['status']}] {f['claim']} — \"{f['quote']}\"" for f in facts
    )
    plain = [{k: v for k, v in s.items() if k != "text"} for s in sources.values()]
    store.update("studio_videos", vid, {"notes": notes, "sources": plain})

    job.update(0.2, "Écriture du script")
    plan, problems = None, None
    for attempt in range(3):
        draft = _script(tools, ch, facts, sources, people, problems)
        draft.update(
            channel=ch["template_key"] or ch["key"],
            date=now()[:10],
            sources=plain,
            reviewed_at=now(),
            review={"by": "contrôle automatique des faits", "at": now()},
            format="analysis_brief",
        )
        try:
            news_brief.validate(draft)
        except ValueError as error:
            words = sum(len(str(s.get("narration", "")).split()) for s in draft.get("segments") or [])
            problems = [{"issue": str(error)}]
            if not 550 <= words <= 900:
                # A bare "550 to 900 words" did not get the length fixed: give the count and the way.
                way = (
                    "Expand: give each fact more context, what it means and what could happen next, "
                    "framed as analysis, without adding any new claim."
                    if words < 550
                    else "Tighten: shorten the segments without dropping the key facts."
                )
                problems = [{"issue": f"The narration totals {words} words; it must total 680-760 words across 6-9 segments. {way}"}]
            continue
        job.update(0.3, "Vérification de chaque phrase")
        problems = _factcheck(tools, draft, facts)
        if not problems:
            plan = draft
            break
    if not plan:
        raise ValueError("Le script n'a pas passé la vérification des faits : " + json.dumps(problems, ensure_ascii=False)[:300])

    job.update(0.36, "Photos sous licence réutilisable")
    wanted = list(dict.fromkeys(people + list((plan.get("thumbnail") or {}).get("people") or [])))
    photos = _photos(tools, folder, wanted)
    illustrate(plan, photos)
    news_brief.validate(plan)
    (folder / "brief.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    store.update(
        "studio_videos",
        vid,
        {"title": plan["title"][:100], "script": news_brief.validate(plan), "status": "script"},
    )
    return _media(store, ch, vid, folder, job, tools, automation_rights, plan, sources, photos)


def _media(store, ch, vid, folder, job, tools, automation_rights, plan, sources, photos):
    from studio.imports import digest, relative

    job.update(0.45, "Voix et montage")
    tools.build(folder, lambda msg: job.update(None, msg))
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    path = ROOT / relative(result["file"])

    job.update(0.8, "Miniature")
    thumb, thumb_rights = _thumbnail(tools, folder, ch, plan, photos)

    job.update(0.88, "Contrôle des images du montage")
    blocking = (tools.sheets or _sheets_ok)(tools, folder)
    if blocking:
        raise ValueError("Contrôle des planches : " + "; ".join(map(str, blocking))[:400])
    if tools.decode:
        tools.decode(path)
    else:
        from studio.jobs import verify as decode_check

        decode_check(store, dict(store.video(vid), video_path=relative(str(path))), job)

    job.update(0.94, "Manifeste des droits")
    voice = voice_record()
    music = {"kind": "original_synthesized", "generation_record": "services/music.py · " + str(folder.relative_to(ROOT))}
    plan["audio_rights"] = {"voice": voice, "music": music}
    automation_rights(plan)
    from services.news_rights import image_rights

    image_rights({"rights": thumb_rights})
    proofs = {s["visual"]["url"]: s["visual"]["rights"] for s in plan["segments"] if s.get("visual")}
    sha = digest(path)
    manifest = {
        "voice": voice,
        "music": music,
        "thumbnail": thumb_rights,
        "visuals": proofs,
        "video_sha256": sha,
        "thumbnail_sha256": digest(thumb),
        "checked_at": now(),
        "checked_by": "contrôle automatique (faits cités, licences Commons, planches)",
    }
    with store.db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_reviews(video_id TEXT PRIMARY KEY,manifest TEXT NOT NULL,video_sha256 TEXT NOT NULL,thumbnail_sha256 TEXT NOT NULL,created_at TEXT NOT NULL)"
        )
        c.execute(
            "INSERT OR REPLACE INTO studio_reviews VALUES(?,?,?,?,?)",
            (vid, json.dumps(manifest, ensure_ascii=False), sha, manifest["thumbnail_sha256"], now()),
        )
    (folder / "rights_review.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tags = [str(t)[:60] for t in plan.get("tags") or []][:30]
    store.update(
        "studio_videos",
        vid,
        {
            "video_path": relative(str(path)),
            "thumb_path": relative(str(thumb)),
            "description": description(plan, sources, photos),
            "tags": tags,
            "render_digest": sha,
            "quality_status": "verified",
            "rights_status": "verified",
            "rights_manifest": manifest,
            "status": "review" if dry_run() else "ready",
            "error": "",
        },
    )
    store.log("Delamain", "autonews", ("Vidéo prête à regarder : " if dry_run() else "Vidéo prête à publier : ") + plan["title"])
    if dry_run():
        notify(ch, f"🧪 **{ch['name']}** — vidéo prête (essai, non publiée) : {plan['title']}\nÀ regarder dans le studio : Vidéos.")
    job.update(1, "Vidéo prête" + (" (essai)" if dry_run() else " ; publication automatique"))
    return {"video_id": vid, "ready": not dry_run()}


def notify(ch, text):
    """One plain message on the channel's Discord, never blocking production."""
    url = os.getenv("DISCORD_WEBHOOK_" + (ch["template_key"] or ch["key"]).upper()) or os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        return
    try:
        from studio.youtube_renewal import post

        post(url, text[:1900])
    except Exception:
        pass


def announce(store, v, youtube_id):
    """After an automatic publication: the link on the channel's Discord."""
    ch = store.channel(v["channel_id"])
    if ch and (v.get("engine_ref") or {}).get("auto") and youtube_id:
        notify(ch, f"✅ **{ch['name']}** — publiée automatiquement : {v['title']}\nhttps://youtu.be/{youtube_id}")
