"""Persist resumable sessions before upload; never blindly duplicate a publication."""

import json
from pathlib import Path
import urllib.request
import urllib.error
from studio.store import ROOT, now
from studio.domain import blockers
from studio.imports import digest


def publish(store, v, ch, job):
    reasons = blockers(v, ch, store.settings())
    if reasons:
        raise ValueError(" · ".join(reasons))
    path = (ROOT / v["video_path"]).resolve()
    thumb = (ROOT / v["thumb_path"]).resolve()
    if (
        not path.is_relative_to(ROOT)
        or not thumb.is_relative_to(ROOT)
        or not path.is_file()
        or not thumb.is_file()
    ):
        raise ValueError("Fichiers de publication absents.")
    if digest(path) != v["render_digest"]:
        raise ValueError(
            "La vidéo a changé après son contrôle. Recommence les vérifications."
        )
    from studio.review import recheck_rights

    recheck_rights(store, v)
    from routes.youtube import _access_token, _opener, _fetch_channel

    p = store.one(
        "SELECT yt_refresh_token,proxy FROM delamain_projects WHERE id=?", (ch["id"],)
    )
    access = _access_token(p["yt_refresh_token"], p["proxy"])
    if not access:
        raise ValueError("L’accès Google de cette chaîne a expiré ou a été refusé. Reconnecte-la depuis Chaînes → Connecter YouTube.")
    _, actual_channel = _fetch_channel(access)
    if not ch["yt_channel_id"] or actual_channel != ch["yt_channel_id"]:
        raise ValueError("YouTube n’a pas confirmé l’identité de la chaîne attendue. Vérifie sa connexion avant de publier.")
    op = _opener(p["proxy"])
    with store.db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_uploads(video_id TEXT PRIMARY KEY, session_url TEXT NOT NULL, youtube_id TEXT DEFAULT '', updated_at TEXT NOT NULL)"
        )
    existing = store.one("SELECT * FROM studio_uploads WHERE video_id=?", (v["id"],))
    total = path.stat().st_size
    if existing and existing["youtube_id"]:
        return finish(store, v, ch, job, op, access, existing["youtube_id"], thumb)
    upload_url = existing["session_url"] if existing else ""
    offset = 0
    if upload_url:
        probe = urllib.request.Request(
            upload_url,
            data=b"",
            method="PUT",
            headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"},
        )
        try:
            with op.open(probe, timeout=30) as r:
                response = json.load(r)
                if response.get("id"):
                    return finish(store, v, ch, job, op, access, response["id"], thumb)
        except urllib.error.HTTPError as e:
            if e.code == 308:
                offset = int(e.headers.get("Range", "bytes=0--1").split("-")[-1]) + 1
            else:
                raise ValueError(
                    "La session YouTube précédente ne peut pas être reprise. Vérifie YouTube avant un nouveau chargement."
                ) from None
    else:
        meta = {
            "snippet": {
                "title": v["title"][:100],
                "description": v["description"],
                "tags": v["tags"][:30],
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }
        req = urllib.request.Request(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            data=json.dumps(meta).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer " + access,
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(total),
            },
        )
        with op.open(req, timeout=45) as r:
            upload_url = r.headers.get("Location")
        if not upload_url:
            raise ValueError("YouTube n’a pas fourni de session de chargement.")
        with store.db() as c:
            c.execute(
                "INSERT INTO studio_uploads VALUES(?,?,?,?)",
                (v["id"], upload_url, "", now()),
            )
    with open(path, "rb") as f:
        f.seek(offset)
        while offset < total:
            job.update(offset / total * 0.85, "Chargement privé sur YouTube")
            if blockers(
                store.video(v["id"]), store.channel(ch["id"]), store.settings()
            ):
                raise ValueError(
                    "Publication suspendue : les réglages ou contrôles ont changé."
                )
            data = f.read(8 * 1024 * 1024)
            end = offset + len(data) - 1
            req = urllib.request.Request(
                upload_url,
                data=data,
                method="PUT",
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(data)),
                    "Content-Range": f"bytes {offset}-{end}/{total}",
                },
            )
            try:
                with op.open(req, timeout=180) as r:
                    response = json.load(r)
                    if response.get("id"):
                        return finish(
                            store, v, ch, job, op, access, response["id"], thumb
                        )
            except urllib.error.HTTPError as e:
                if e.code != 308:
                    raise
            offset = end + 1
    raise ValueError(
        "Chargement envoyé mais résultat non confirmé. Relance pour vérifier la session existante."
    )


def finish(store, v, ch, job, op, access, yt_id, thumb):
    # Save the ID before thumbnail/status calls: retry cannot create a second upload.
    with store.db() as c:
        c.execute(
            "UPDATE studio_uploads SET youtube_id=?,updated_at=? WHERE video_id=?",
            (yt_id, now(), v["id"]),
        )
    store.update("studio_videos", v["id"], {"youtube_id": yt_id, "status": "review"})
    job.update(0.9, "Vidéo privée chargée ; miniature et contrôles finaux")
    data = thumb.read_bytes()
    if len(data) > 2 * 1024 * 1024:
        raise ValueError(
            "Miniature trop lourde pour YouTube (2 Mo maximum). La vidéo reste privée."
        )
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + yt_id,
        data=data,
        method="POST",
        headers={
            "Authorization": "Bearer " + access,
            "Content-Type": "image/png" if thumb.suffix == ".png" else "image/jpeg",
        },
    )
    with op.open(req, timeout=90):
        pass
    # Respect a pause that arrived while the upload was in progress.
    if store.settings()["paused"] or store.channel(ch["id"])["paused"]:
        raise ValueError(
            "Publication suspendue. La vidéo chargée reste privée sur YouTube."
        )
    from studio.review import recheck_rights

    recheck_rights(store, store.video(v["id"]))
    if v["post_at"]:
        from datetime import datetime, timezone

        if datetime.fromisoformat(v["post_at"]) > datetime.now(timezone.utc):
            store.update("studio_videos", v["id"], {"status": "scheduled"})
            return {"youtube_id": yt_id, "private": True}
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/videos?part=status",
        data=json.dumps(
            {
                "id": yt_id,
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            }
        ).encode(),
        method="PUT",
        headers={
            "Authorization": "Bearer " + access,
            "Content-Type": "application/json",
        },
    )
    with op.open(req, timeout=45) as response:
        confirmed = json.load(response)
    if confirmed.get("status", {}).get("privacyStatus") != "public":
        raise ValueError("YouTube n’a pas confirmé la publication publique.")
    store.update("studio_videos", v["id"], {"status": "published", "error": ""})
    store.log("Studio", "publish", "Publication YouTube confirmée : " + v["title"])
    return {"youtube_id": yt_id, "published": True}
