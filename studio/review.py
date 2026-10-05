"""Review and license evidence are bound to the actual rendered files."""

from pathlib import Path
from flask import request, jsonify, send_file
from studio.store import ROOT, now
from studio.imports import read, digest
from services.news_rights import image_rights, automation_rights


def register_reviews(app, store, owner):
    def video(vid):
        v = store.video(vid)
        if not v:
            raise ValueError("Vidéo introuvable.")
        return v

    def actual(v, key):
        p = (ROOT / v.get(key, "")).resolve()
        if not v.get(key) or not p.is_relative_to(ROOT) or not p.is_file():
            raise ValueError(
                "Le fichier local est absent : "
                + ("vidéo" if key == "video_path" else "miniature")
            )
        return p

    @app.get("/api/studio/videos/<vid>/controls")
    def controls(vid):
        v = video(vid)
        folder = (ROOT / v["asset_dir"]).resolve() if v["asset_dir"] else None
        plan = (
            read(folder / "brief.json")
            if folder and folder.is_relative_to(ROOT)
            else {}
        )
        images = [
            {
                "url": s["visual"]["url"],
                "credit": s["visual"].get("credit", ""),
                "rights": s["visual"].get("rights", {}),
            }
            for s in plan.get("segments", [])
            if s.get("visual")
        ]
        sheets = (
            [p.name for p in (folder / "check").glob("sheet_*.jpg")]
            if folder and folder.is_relative_to(ROOT)
            else []
        )
        review = (
            store.one("SELECT * FROM studio_reviews WHERE video_id=?", (vid,))
            if store.one("SELECT name FROM sqlite_master WHERE name='studio_reviews'")
            else None
        )
        return jsonify(
            images=images,
            sheets=sorted(sheets),
            reviewed=bool(review),
            local_video=bool(v["video_path"]),
        )

    @app.get("/media/<vid>/check/<name>")
    def sheet(vid, name):
        v = video(vid)
        if (
            not v["asset_dir"]
            or not name.startswith("sheet_")
            or not name.endswith(".jpg")
        ):
            raise ValueError("Planche introuvable.")
        folder = (ROOT / v["asset_dir"] / "check").resolve()
        p = (folder / name).resolve()
        if (
            not folder.is_relative_to(ROOT)
            or not p.is_relative_to(folder)
            or not p.is_file()
        ):
            raise ValueError("Planche introuvable.")
        return send_file(p, conditional=True)

    @app.post("/api/studio/videos/<vid>/review")
    def review(vid):
        v = video(vid)
        b = request.get_json(silent=True) or {}
        path = actual(v, "video_path")
        if not all(
            b.get(k) is True
            for k in ["watched", "audio_checked", "facts_checked", "captions_checked"]
        ):
            raise ValueError(
                "Confirme la relecture des images, du son, des faits et des textes."
            )
        if (
            v["quality_status"] not in {"technical", "verified"}
            or digest(path) != v["render_digest"]
        ):
            raise ValueError("Lance d’abord le contrôle technique du fichier actuel.")
        store.update(
            "studio_videos", vid, {"quality_status": "verified"}, b.get("revision", -1)
        )
        store.log("Équipe", "review", "Relecture du rendu confirmée : " + v["title"])
        return jsonify(ok=True)

    @app.post("/api/studio/videos/<vid>/rights")
    def rights(vid):
        owner()
        v = video(vid)
        b = request.get_json(silent=True) or {}
        path = actual(v, "video_path")
        thumb = actual(v, "thumb_path")
        ch = store.channel(v["channel_id"])
        voice = b.get("voice") or {}
        thumb_rights = dict(b.get("thumbnail") or {}, reviewed_at=now())
        image_rights({"rights": thumb_rights})
        voice = dict(voice, reviewed_at=now())
        ref = v["engine_ref"]
        if ch["format"] != "news" or not ref.get("brief"):
            raise ValueError(
                "Le contrôle intégré des licences concerne les analyses sportives. Le manifeste de ce format doit encore être adapté."
            )
        folder = (ROOT / str(ref.get("job", ""))).resolve()
        if not folder.is_relative_to(ROOT):
            raise ValueError("Dossier de production invalide.")
        plan = read(folder / "brief.json")
        images = b.get("visuals") or []
        proofs = {x.get("url"): x.get("rights") for x in images if isinstance(x, dict)}
        for seg in plan.get("segments", []):
            if seg.get("visual"):
                url = seg["visual"]["url"]
                if url in proofs:
                    seg["visual"]["rights"] = dict(proofs[url], reviewed_at=now())
        music = {
            "kind": "original_synthesized",
            "generation_record": "services/music.py · " + ref["job"],
        }
        plan["audio_rights"] = {"voice": voice, "music": music}
        automation_rights(plan)
        sha = digest(path)
        manifest = {
            "voice": voice,
            "music": music,
            "thumbnail": thumb_rights,
            "visuals": proofs,
            "video_sha256": sha,
            "thumbnail_sha256": digest(thumb),
            "checked_at": now(),
        }
        with store.db() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS studio_reviews(video_id TEXT PRIMARY KEY,manifest TEXT NOT NULL,video_sha256 TEXT NOT NULL,thumbnail_sha256 TEXT NOT NULL,created_at TEXT NOT NULL)"
            )
        import json

        # Update optimistic video revision first. A stale request must not write a new release manifest.
        store.update(
            "studio_videos",
            vid,
            {"rights_status": "verified", "rights_manifest": manifest},
            b.get("revision", -1),
        )
        with store.db() as c:
            c.execute(
                "INSERT OR REPLACE INTO studio_reviews VALUES(?,?,?,?,?)",
                (
                    vid,
                    json.dumps(manifest, ensure_ascii=False),
                    sha,
                    manifest["thumbnail_sha256"],
                    now(),
                ),
            )
        (folder / "rights_review.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        store.log(
            "Propriétaire", "rights", "Preuves de droits enregistrées : " + v["title"]
        )
        return jsonify(ok=True)

    @app.post("/api/studio/videos/<vid>/thumbnail")
    def thumbnail(vid):
        v = video(vid)
        if v["youtube_id"] or v["status"] in {"published", "reported"}:
            raise ValueError("Cette version est déjà chargée sur YouTube.")
        if store.one(
            "SELECT id FROM studio_jobs WHERE video_id=? AND status IN ('queued','running')",
            (vid,),
        ):
            raise ValueError(
                "Attends la fin du travail en cours avant de changer la miniature."
            )
        f = request.files.get("file")
        if not f:
            raise ValueError("Choisis un fichier JPEG ou PNG.")
        data = f.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("La miniature doit peser moins de 2 Mo.")
        from PIL import Image
        import io

        try:
            image = Image.open(io.BytesIO(data))
            width, height = image.size
            fmt = image.format
            image.verify()
        except Exception:
            raise ValueError("Ce fichier n’est pas une image valide.") from None
        if (
            fmt not in {"PNG", "JPEG"}
            or width < 640
            or width > 8192
            or height > 8192
            or abs(width / height - 16 / 9) > 0.02
        ):
            raise ValueError(
                "Image attendue : JPEG/PNG au format 16:9, au moins 640 pixels de large."
            )
        folder = ROOT / "work/studio/assets" / vid
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ("thumbnail.png" if fmt == "PNG" else "thumbnail.jpg")
        path.write_bytes(data)
        store.update(
            "studio_videos",
            vid,
            {
                "thumb_path": str(path.relative_to(ROOT)),
                "rights_status": "unknown",
                "approved_digest": "",
            },
        )
        store.log("Équipe", "thumbnail", "Miniature importée : " + v["title"])
        return jsonify(ok=True)


def recheck_rights(store, v):
    if not store.one("SELECT name FROM sqlite_master WHERE name='studio_reviews'"):
        raise ValueError("Manifeste de droits absent.")
    r = store.one("SELECT * FROM studio_reviews WHERE video_id=?", (v["id"],))
    if (
        not r
        or digest(ROOT / v["video_path"]) != r["video_sha256"]
        or digest(ROOT / v["thumb_path"]) != r["thumbnail_sha256"]
    ):
        raise ValueError("Les fichiers ont changé après le contrôle des droits.")
