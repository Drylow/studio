"""Adapters run the existing recent production engines through persistent jobs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from studio.store import ROOT, now
from studio.imports import read, relative, digest


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, store, jid):
        self.store, self.id = store, jid

    def cancelled(self):
        row = self.store.one(
            "SELECT cancel_requested FROM studio_jobs WHERE id=?", (self.id,)
        )
        return not row or bool(row["cancel_requested"])

    def update(self, progress=None, message=None):
        if self.cancelled():
            raise Cancelled("Travail annulé ; les étapes terminées sont conservées.")
        with self.store.db() as c:
            if progress is not None:
                c.execute(
                    "UPDATE studio_jobs SET progress=? WHERE id=?",
                    (max(0, min(1, float(progress))), self.id),
                )
            if message:
                c.execute(
                    "UPDATE studio_jobs SET message=?,updated_at=? WHERE id=?",
                    (str(message)[:1000], now(), self.id),
                )


def execute(store, row):
    job = Job(store, row["id"])
    payload = json.loads(row["payload"])
    actor = payload.get("actor", "Studio")
    if row["kind"] == "agent":
        from studio.agent import respond

        return respond(store, payload["message"], actor, row["id"])
    if row["kind"] == "news_scan":
        from studio.newsroom import scan

        job.update(0.05, "Recherche des infos datées dans les sources du radar")
        result = scan(store, payload["channel_id"])
        job.update(1, "Radar actualisé")
        return result
    if row["kind"] == "news_prepare":
        from studio.newsroom import prepare

        job.update(0.1, "Préparation de la fiche de recherche")
        vid = prepare(store, payload["item_id"], payload["revision"], actor)
        job.update(1, "Fiche de recherche préparée")
        return {"video_id": vid}
    v = store.video(row["video_id"])
    if not v:
        raise ValueError("Vidéo introuvable.")
    ch = store.channel(v["channel_id"])
    kind = row["kind"]
    if kind == "publish":
        from studio.publishing import publish

        return publish(store, v, ch, job)
    if kind == "verify":
        return verify(store, v, job)
    if kind == "discord":
        ref = v["engine_ref"]
        if ref.get("kind") != "news" or not ref.get("brief"):
            raise ValueError(
                "La livraison intégrée concerne les analyses sportives. Utilise le paquet existant pour ce format."
            )
        from services.news_brief_discord import send

        send(ROOT / ref["job"], ROOT / "work")
        store.log(actor, "discord", "Paquet livré : " + v["title"])
        return {"sent": True}
    if kind not in {"script", "render"}:
        raise ValueError("Travail inconnu.")
    if store.settings()["paused"] or ch["paused"]:
        raise ValueError("La production est en pause.")
    # Reserve the per-video authorized envelope atomically. Actual supplier invoices remain separate.
    with store.db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_budget(job_id TEXT PRIMARY KEY,day TEXT NOT NULL,amount REAL NOT NULL)"
        )
        from studio.domain import TZ
        from datetime import datetime

        day = datetime.now(TZ).date().isoformat()
        reserved = c.execute(
            "SELECT COALESCE(SUM(amount),0) FROM studio_budget WHERE day=? AND job_id!=?",
            (day, row["id"]),
        ).fetchone()[0]
        cap = min(ch["budget"], v["cost_cap"])
        if cap <= 0 or reserved + cap > store.settings()["daily_budget"]:
            raise ValueError("Budget des lancements atteint pour aujourd’hui.")
        c.execute(
            "INSERT OR IGNORE INTO studio_budget VALUES(?,?,?)", (row["id"], day, cap)
        )
    store.update("studio_videos", v["id"], {"status": "creating", "error": ""})
    job.update(0.02, "Préparation du moteur de création")
    ref = v["engine_ref"]
    if ch["format"] == "pov":
        os.environ.setdefault("POV_DATA_DIR", str(ROOT / "work/prod"))
        from services import pov_engine as E, pov_store as S

        if ref.get("base") and str(Path(ref["base"]).resolve()) != str(
            Path(S.data_dir()).resolve()
        ):
            raise ValueError(
                "Ce projet utilise un autre dossier de production. Configure POV_DATA_DIR avant la reprise."
            )
        pr = S.get_project(ref["pid"]) if ref.get("pid") else None
        if not pr:
            template = ch["template_key"] or ch["key"]
            if template not in E.TEMPLATES:
                raise ValueError("Associe cette chaîne à un modèle Oddly existant.")
            pr = E.new_project(
                E.studio_channel(template), v["title"], v["minutes"], v["notes"]
            )
            if v["script"]:
                pr["script"] = v["script"]
                S.save_project(pr)
            pr["title_locked"] = True
            S.save_project(pr)
            ref = {"kind": "pov", "pid": pr["id"], "base": S.data_dir()}
            store.update("studio_videos", v["id"], {"engine_ref": ref})
        if v["script"] and v["script"] != pr.get("script"):
            pr["script"] = v["script"]
            pr["voice"] = pr["render"] = None
            pr["scenes"] = []
            S.save_project(pr)
        if kind == "script":
            E.job_script(job, pr["id"])
        else:
            E.job_autopilot(job, pr["id"], render_video=True)
        pr = S.get_project(pr["id"])
        pd = Path(S.project_dir(pr["id"]))
    elif ch["format"] == "history":
        from services import history as H

        pr = H.get_project(ref["pid"]) if ref.get("pid") else None
        if not pr:
            pr = H.new_project(
                v["title"],
                v["minutes"],
                v["notes"],
                {"channel": ch["template_key"] or ch["key"]},
            )
            if v["script"]:
                pr["script"] = H.script_from_fos(v["script"], v["title"])
                H.save_project(pr)
            ref = {"kind": "history", "pid": pr["id"], "base": H.data_dir()}
            store.update("studio_videos", v["id"], {"engine_ref": ref})
        sync_history_script(H, pr, v["script"])
        if kind == "script":
            H.job_script(job, pr["id"])
        else:
            H.job_autopilot(job, pr["id"])
        pr = H.get_project(pr["id"])
        pd = Path(H.project_dir(pr["id"]))
    elif ch["format"] == "news":
        return news_production(store, v, ch, job, kind)
    else:
        raise ValueError("Choisis un format récent pour cette chaîne.")
    rd = pr.get("render") or {}
    rd_path = rd.get("file") or rd.get("path") or ""
    path = relative(pd / rd_path) if rd_path else ""
    thumbs = pr.get("thumbnail") or pr.get("thumbnails") or []
    if isinstance(thumbs, dict):
        thumbs = thumbs.get("files", []) or [thumbs.get("file", "")]
    if isinstance(thumbs, str):
        thumbs = [thumbs]
    thumb = next(
        (
            relative(pd / (t.get("file", "") if isinstance(t, dict) else t))
            for t in thumbs
            if t
        ),
        "",
    )
    script = pr.get("script") or ""
    if not isinstance(script, str):
        from services.history_ai import narration

        script = (pr.get("fos") or {}).get("text") or narration(script)
    store.update(
        "studio_videos",
        v["id"],
        {
            "script": script,
            "video_path": path,
            "thumb_path": thumb,
            "asset_dir": str(pd.relative_to(ROOT)) if pd.is_relative_to(ROOT) else "",
            "status": "review" if path else "script",
            "quality_status": "unknown",
            "rights_status": "unknown",
            "approved_digest": "",
            "render_digest": "",
        },
    )
    store.log(actor, "production", "Étape terminée : " + v["title"])
    return {"engine_ref": ref, "rendered": bool(path)}


def sync_history_script(engine, project, text):
    """Edited narration must invalidate dependent engine stages before resume."""
    if not text.strip():
        return
    from services.history_ai import narration

    current = (project.get("fos") or {}).get("text") or (
        narration(project["script"]) if project.get("script") else ""
    )
    if text != current:
        project["script"] = engine.script_from_fos(text, project["title"])
        project["fos"] = {"text": text}
        project["voice"] = project["plan"] = project["render"] = None
        engine.save_project(project)


def news_production(store, v, ch, job, kind):
    from services import ai, news_brief

    if not v["sources"] or not v["notes"].strip():
        raise ValueError(
            "Ajoute les sources datées et les faits vérifiés dans la fiche vidéo avant de créer une analyse."
        )
    for s in v["sources"]:
        if not s.get("url", "").startswith("https://") or not s.get("name"):
            raise ValueError("Chaque source doit avoir un nom et une adresse HTTPS.")
    folder = ROOT / "work/studio/productions" / v["id"]
    folder.mkdir(parents=True, exist_ok=True)
    ref = {"kind": "news", "job": str(folder.relative_to(ROOT)), "brief": True}
    previous = v["engine_ref"]
    plan = read(folder / "brief.json")
    if not plan and previous.get("brief") and previous.get("job"):
        plan = read(ROOT / previous["job"] / "brief.json")
    context_digest = hashlib.sha256(
        json.dumps(
            [v["title"], v["notes"], v["sources"]], sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()
    if (
        plan
        and kind == "render"
        and plan.get("studio_context_digest") not in (None, context_digest)
    ):
        raise ValueError(
            "Les faits ou sources ont changé. Réécris le script avant de relancer le montage."
        )
    if kind == "script" or (not plan and not v["script"].strip()):
        job.update(0.08, "Écriture à partir des faits et sources fournis")
        plan = ai.chat_json(
            [
                {
                    "role": "system",
                    "content": """Write a factual English sports news analysis of 550–900 words.
Use only the verified facts supplied. Attribute claims, distinguish rumors from confirmed facts.
Return JSON with title and segments, each with headline, lines (2–3 short strings), narration and source_ids.
No visual field, no photos, no external clips. Each segment cites supplied source IDs. Do not invent quotes.
The narration should explain the story with a clear hook and useful context.""",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "topic": v["title"],
                            "facts": v["notes"],
                            "sources": v["sources"],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            tries=2,
        )
    elif v["script"].strip() and (
        not plan or v["script"].strip() != news_brief.validate(plan).strip()
    ):
        # A pasted/edited script remains exactly the narration the user saved.
        paragraphs = [p.strip() for p in v["script"].split("\n\n") if p.strip()]
        plan = {
            "title": v["title"],
            "segments": [
                {
                    "headline": f"Analysis {i + 1}",
                    "lines": [" ".join(text.split()[:8])],
                    "narration": text,
                    "source_ids": [source["id"] for source in v["sources"]],
                }
                for i, text in enumerate(paragraphs)
            ],
        }
    plan.update(
        channel=ch["template_key"] or ch["key"],
        date=now()[:10],
        reviewed_at=now(),
        sources=v["sources"],
        studio_context_digest=context_digest,
    )
    news_brief.validate(plan)
    (folder / "brief.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    store.update("studio_videos", v["id"], {"engine_ref": ref, "asset_dir": ref["job"]})
    text = news_brief.validate(plan)
    store.update("studio_videos", v["id"], {"script": text, "status": "script"})
    if kind == "script":
        return {"script_ready": True}
    job.update(0.2, "Voix et montage des cartes originales")
    result = news_brief.build(
        folder, ROOT / "work", log=lambda msg: job.update(None, msg)
    )
    result = read(folder / "result.json") or result or {}
    path = relative(result.get("file", ""))
    store.update(
        "studio_videos",
        v["id"],
        {
            "video_path": path,
            "status": "review",
            "quality_status": "unknown",
            "rights_status": "unknown",
            "approved_digest": "",
        },
    )
    return {"rendered": bool(path)}


def verify(store, v, job):
    path = (ROOT / v["video_path"]).resolve() if v["video_path"] else None
    if not path or not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("Le fichier vidéo local est absent.")
    import imageio_ffmpeg

    job.update(0.1, "Décodage et intégrité du fichier")
    result = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        timeout=7200,
    )
    if result.returncode or result.stderr.strip():
        raise ValueError("Le fichier présente une erreur de décodage.")
    # Technical success is distinct from the mandatory visual/editorial review.
    sha = digest(path)
    store.update(
        "studio_videos", v["id"], {"render_digest": sha, "quality_status": "technical"}
    )
    job.update(1, "Intégrité vérifiée ; relecture visuelle et éditoriale requise")
    return {"sha256": sha, "technical": True, "visual_review_required": True}
