"""Persist resumable sessions before upload; never blindly duplicate a publication."""

import json
import os
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from studio.store import ROOT, now
from studio.domain import blockers
from studio.imports import digest
from studio.youtube_permissions import direct_news


def chunk_size():
    """YOUTUBE_CHUNK_MB: o2switch cuts uploads of 8 MB bodies; 1 MB pieces go through."""
    try:
        mb = int(os.getenv("YOUTUBE_CHUNK_MB", "8"))
    except ValueError:
        mb = 8
    return max(1, min(mb, 64)) * 1024 * 1024  # multiples of 256 KiB, as YouTube requires


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
    # A direct upload cannot be held privately and released later with upload-only
    # permission. The durable queue must wait until an explicit reservation is due.
    direct = direct_news(ch)
    if (
        direct
        and v["post_at"]
        and datetime.fromisoformat(v["post_at"]) > datetime.now(timezone.utc)
    ):
        raise ValueError(
            "Cette vidéo sera envoyée quand sa réservation sera arrivée à échéance."
        )
    if thumb.stat().st_size > 2 * 1024 * 1024:
        raise ValueError(
            "Miniature trop lourde pour YouTube (2 Mo maximum). Aucun envoi effectué."
        )
    from routes.youtube import _access_token, _opener, _fetch_channel

    p = store.one(
        "SELECT yt_refresh_token,proxy FROM delamain_projects WHERE id=?", (ch["id"],)
    )
    try:
        access = _access_token(p["yt_refresh_token"], p["proxy"])
    except urllib.error.HTTPError as error:
        # invalid_grant: Google ended this authorization (expired or revoked).
        if error.code not in (400, 401):
            raise
        access = ""
    if not access:
        raise ValueError(
            "L’accès Google de cette chaîne a expiré ou a été refusé. Reconnecte-la depuis Chaînes → Connecter YouTube."
        )
    _, actual_channel = _fetch_channel(access)
    if not ch["yt_channel_id"] or actual_channel != ch["yt_channel_id"]:
        raise ValueError(
            "YouTube n’a pas confirmé l’identité de la chaîne attendue. Vérifie sa connexion avant de publier."
        )
    op = _opener(p["proxy"])
    with store.db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_uploads(video_id TEXT PRIMARY KEY, session_url TEXT NOT NULL, youtube_id TEXT DEFAULT '', updated_at TEXT NOT NULL)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_upload_modes(video_id TEXT PRIMARY KEY REFERENCES studio_uploads(video_id), privacy_status TEXT NOT NULL CHECK(privacy_status IN ('private','public')))"
        )
    existing = store.one(
        "SELECT u.*,coalesce(m.privacy_status,'private') AS privacy_status FROM studio_uploads u LEFT JOIN studio_upload_modes m ON m.video_id=u.video_id WHERE u.video_id=?",
        (v["id"],),
    )
    privacy = (
        existing["privacy_status"] if existing else ("public" if direct else "private")
    )
    total = path.stat().st_size
    if existing and existing["youtube_id"]:
        return finish(
            store, v, ch, job, op, access, existing["youtube_id"], thumb, privacy
        )
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
                    return finish(
                        store, v, ch, job, op, access, response["id"], thumb, privacy
                    )
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
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
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
                "INSERT INTO studio_uploads(video_id,session_url,youtube_id,updated_at) VALUES(?,?,?,?)",
                (v["id"], upload_url, "", now()),
            )
            c.execute("INSERT INTO studio_upload_modes VALUES(?,?)", (v["id"], privacy))
    with open(path, "rb") as f:
        f.seek(offset)
        while offset < total:
            job.update(
                offset / total * 0.85,
                (
                    "Envoi sur YouTube"
                    if privacy == "public"
                    else "Chargement privé sur YouTube"
                ),
            )
            if blockers(
                store.video(v["id"]), store.channel(ch["id"]), store.settings()
            ):
                raise ValueError(
                    "Publication suspendue : les réglages ou contrôles ont changé."
                )
            data = f.read(min(chunk_size(), total - offset))
            if not data or path.stat().st_size != total:
                raise ValueError(
                    "La taille de la vidéo a changé pendant son envoi. Publication interrompue."
                )
            end = offset + len(data) - 1
            if privacy == "public" and end + 1 == total:
                # Direct publication happens at completion, so revalidate before
                # sending the final bytes rather than relying on a later update.
                current = store.video(v["id"])
                recheck_rights(store, current)
                if digest(path) != current["render_digest"]:
                    raise ValueError(
                        "La vidéo a changé pendant son envoi. Publication interrompue."
                    )
                if blockers(current, store.channel(ch["id"]), store.settings()):
                    raise ValueError("Publication suspendue avant la fin de l’envoi.")
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
                            store,
                            v,
                            ch,
                            job,
                            op,
                            access,
                            response["id"],
                            thumb,
                            privacy,
                        )
            except urllib.error.HTTPError as e:
                if e.code != 308:
                    raise
            offset = end + 1
    raise ValueError(
        "Chargement envoyé mais résultat non confirmé. Relance pour vérifier la session existante."
    )


def confirm_direct(op, access, yt_id, channel_id):
    query = urllib.parse.urlencode({"part": "snippet,status", "id": yt_id})
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/videos?" + query,
        headers={"Authorization": "Bearer " + access},
    )
    with op.open(req, timeout=45) as response:
        items = json.load(response).get("items", [])
    if (
        len(items) != 1
        or items[0].get("id") != yt_id
        or items[0].get("snippet", {}).get("channelId") != channel_id
    ):
        raise ValueError(
            "YouTube n’a pas confirmé la vidéo sur la bonne chaîne. Aucun nouvel envoi ne sera créé."
        )
    if items[0].get("status", {}).get("privacyStatus") != "public":
        raise ValueError(
            "La vidéo est chargée, mais YouTube ne confirme pas sa mise en ligne publique. Vérifie les autorisations de publication du projet Google ; aucun doublon ne sera envoyé."
        )


def finish(store, v, ch, job, op, access, yt_id, thumb, privacy="private"):
    # Save the ID before thumbnail/status calls: retry cannot create a second upload.
    with store.db() as c:
        c.execute(
            "UPDATE studio_uploads SET youtube_id=?,updated_at=? WHERE video_id=?",
            (yt_id, now(), v["id"]),
        )
    store.update("studio_videos", v["id"], {"youtube_id": yt_id, "status": "review"})
    job.update(
        0.9,
        (
            "Vidéo envoyée ; vérification de la miniature"
            if privacy == "public"
            else "Vidéo privée chargée ; miniature et contrôles finaux"
        ),
    )
    if privacy == "public":
        confirm_direct(op, access, yt_id, ch["yt_channel_id"])
    data = thumb.read_bytes()
    if len(data) > 2 * 1024 * 1024:
        raise ValueError(
            "Miniature trop lourde pour YouTube (2 Mo maximum). L’envoi existant doit être vérifié."
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
    try:
        with op.open(req, timeout=90) as response:
            if privacy == "public" and not json.load(response).get("items"):
                raise ValueError(
                    "La vidéo est déjà publique, mais YouTube n’a pas confirmé la miniature. Reprends cet envoi ; aucun doublon ne sera créé."
                )
    except OSError:
        if privacy == "public":
            raise ValueError(
                "La vidéo est déjà publique, mais sa miniature n’a pas été confirmée. Reprends cet envoi pour appliquer la miniature ; aucun doublon ne sera créé."
            ) from None
        raise
    if privacy == "public":
        # The historical flow cannot unpublish an already completed direct upload.
        # A late pause stops later jobs, but must not hide the real public result.
        confirm_direct(op, access, yt_id, ch["yt_channel_id"])
        store.update("studio_videos", v["id"], {"status": "published", "error": ""})
        store.log(
            "Studio",
            "publish",
            "Publication YouTube et miniature confirmées : " + v["title"],
        )
        return {"youtube_id": yt_id, "published": True}
    # Respect a pause that arrived while the upload was in progress.
    if store.settings()["paused"] or store.channel(ch["id"])["paused"]:
        raise ValueError(
            "Publication suspendue. La vidéo chargée reste privée sur YouTube."
        )
    from studio.review import recheck_rights

    recheck_rights(store, store.video(v["id"]))
    if v["post_at"]:
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
