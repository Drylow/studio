"""Read-only Data API counters. Observed growth starts at the first snapshot.

No extra Analytics grant, fabricated history, tokens or raw provider errors in UI.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from flask import jsonify, request
from studio.store import now, uid, Conflict

RETENTION_DAYS = 29
SYNC_HOURS = 4
COOLDOWN_MINUTES = 15
_purged = {}


def at(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def purge(store):
    clock = datetime.now(timezone.utc)
    key = str(store.path)
    if key in _purged and clock - _purged[key] < timedelta(hours=1):
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    with store.db() as c:
        c.execute("DELETE FROM studio_channel_snapshots WHERE captured_at<?", (cutoff,))
        c.execute("UPDATE studio_channel_sync SET videos_json='[]',videos_at='' WHERE videos_at!='' AND videos_at<?", (cutoff,))
    _purged[key] = clock


def clear(c, cid):
    """Invalidate a pending refresh along with the cache."""
    c.execute("DELETE FROM studio_channel_snapshots WHERE channel_id=?", (cid,))
    c.execute("DELETE FROM studio_channel_sync WHERE channel_id=?", (cid,))


def report(store, channel, days=7):
    clock = datetime.now(timezone.utc)
    cutoff = (clock - timedelta(days=RETENTION_DAYS)).isoformat()
    history = store.rows(
        "SELECT captured_at,views,subscribers,videos FROM studio_channel_snapshots WHERE channel_id=? AND youtube_id=? AND captured_at>=? ORDER BY captured_at",
        (channel["id"], channel["yt_channel_id"], cutoff),
    ) if channel["connected"] else []
    state = store.one("SELECT * FROM studio_channel_sync WHERE channel_id=?", (channel["id"],)) or {}
    last = history[-1] if history else None
    result = dict(
        channel_id=channel["id"], connected=bool(channel["connected"]),
        updated_at=last["captured_at"] if last else None,
        totals={k: last[k] if last else None for k in ("views", "subscribers", "videos")},
        stale=bool(last and clock - at(last["captured_at"]) > timedelta(hours=SYNC_HOURS * 2)),
        error=state.get("error", "") if channel["connected"] else "",
        refreshing=bool(state.get("lease_until") and state["lease_until"] > clock.isoformat()),
        gain=None, since=None, until=last["captured_at"] if last else None,
        partial=False, days=days, history=[], recent_videos=[], videos_updated_at=None,
    )
    if last:
        start = clock - timedelta(days=days)
        before = [s for s in history if at(s["captured_at"]) <= start]
        baseline = before[-1] if before else history[0]
        selected = [s for s in history if s["captured_at"] >= baseline["captured_at"]]
        result["history"] = selected
        if len(selected) >= 2 and baseline["views"] is not None and last["views"] is not None:
            result.update(gain=last["views"] - baseline["views"], since=baseline["captured_at"],
                          partial=at(baseline["captured_at"]) > start)
        if state.get("videos_at") and state["videos_at"] >= cutoff:
            result["recent_videos"] = json.loads(state.get("videos_json", "[]"))
            result["videos_updated_at"] = state["videos_at"]
    return result


def counter(data, key):
    value = data.get(key)
    if isinstance(value, (str, int)) and not isinstance(value, bool) and re.fullmatch(r"\d{1,18}", str(value)):
        return int(value)
    return None


def provider(project):
    from routes.youtube import _opener

    opener = _opener(project.get("proxy", ""))
    token_request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "refresh_token": project["yt_refresh_token"],
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "grant_type": "refresh_token",
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with opener.open(token_request, timeout=10) as response:
        token = json.load(response).get("access_token")
    if not token:
        raise ValueError("Missing Google access")

    def get(resource, **params):
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/" + resource + "?" + urllib.parse.urlencode(params),
            headers={"Authorization": "Bearer " + token},
        )
        with opener.open(req, timeout=10) as response:
            return json.load(response)

    channels = get("channels", part="statistics,contentDetails", mine="true").get("items", [])
    matching = [c for c in channels if c.get("id") == project["yt_channel_id"]]
    if len(matching) != 1:
        raise ValueError("Google channel identity mismatch")
    channel = matching[0]
    stats = channel.get("statistics", {})
    totals = dict(views=counter(stats, "viewCount"), videos=counter(stats, "videoCount"),
                  subscribers=None if stats.get("hiddenSubscriberCount", False) else counter(stats, "subscriberCount"))
    # An optional playlist failure doesn't discard the channel counters.
    recent = None
    try:
        uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        ids = []
        if uploads:
            for item in get("playlistItems", part="contentDetails", playlistId=uploads, maxResults=8).get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId", "")
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                    ids.append(video_id)
        recent = []
        if ids:
            for video in get("videos", part="snippet,statistics", id=",".join(ids)).get("items", []):
                snippet = video.get("snippet", {})
                if video.get("id") not in ids or snippet.get("channelId") != project["yt_channel_id"]:
                    continue
                published = snippet.get("publishedAt", "")
                at(published)
                recent.append(dict(id=video["id"], title=str(snippet.get("title", ""))[:300],
                                   published_at=published, views=counter(video.get("statistics", {}), "viewCount")))
            recent.sort(key=lambda v: v["published_at"], reverse=True)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        recent = None
    return totals, recent


def sync(store, cid, background=False):
    if getattr(store, "web_app", None) and store.web_app.config["PREVIEW"]:
        raise ValueError("Les statistiques YouTube réelles sont désactivées dans l’aperçu.")
    if not os.getenv("GOOGLE_CLIENT_ID") or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise ValueError("L’accès Google doit être configuré sur le serveur.")
    lease = uid()
    clock = datetime.now(timezone.utc)
    cooldown = timedelta(hours=SYNC_HOURS) if background else timedelta(minutes=COOLDOWN_MINUTES)
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        project = c.execute(
            "SELECT p.* FROM delamain_projects p JOIN studio_channels s ON s.project_id=p.id WHERE p.id=? AND s.retired=0", (cid,)
        ).fetchone()
        if not project or not project["yt_refresh_token"] or not project["yt_channel_id"]:
            raise ValueError("Connecte d’abord cette chaîne à YouTube.")
        project = dict(project)
        c.execute("INSERT OR IGNORE INTO studio_channel_sync(channel_id) VALUES(?)", (cid,))
        state = c.execute("SELECT * FROM studio_channel_sync WHERE channel_id=?", (cid,)).fetchone()
        if state["lease_until"] > clock.isoformat():
            return "running"
        if state["checked_at"] and clock - at(state["checked_at"]) < cooldown:
            return "cached"
        c.execute("UPDATE studio_channel_sync SET checked_at=?,lease_until=?,lease_id=? WHERE channel_id=?",
                  (clock.isoformat(), (clock + timedelta(minutes=2)).isoformat(), lease, cid))
    error = ""
    totals, recent = None, None
    try:
        totals, recent = provider(project)
    except urllib.error.HTTPError as exc:
        error = "L’accès Google a expiré ou a été refusé. Reconnecte cette chaîne." if exc.code in {400, 401} else "YouTube refuse la lecture des statistiques. Vérifie la connexion ou réessaie plus tard."
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        error = "Impossible de lire les statistiques de cette chaîne. Vérifie sa connexion YouTube."
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        current = c.execute("SELECT p.yt_refresh_token,p.yt_channel_id,s.retired FROM delamain_projects p JOIN studio_channels s ON s.project_id=p.id WHERE p.id=?", (cid,)).fetchone()
        owned = c.execute("SELECT lease_id FROM studio_channel_sync WHERE channel_id=?", (cid,)).fetchone()
        if not current or current["retired"] or current["yt_refresh_token"] != project["yt_refresh_token"] or current["yt_channel_id"] != project["yt_channel_id"] or not owned or owned["lease_id"] != lease:
            raise Conflict("La connexion a changé pendant l’actualisation. Recommence depuis la chaîne.")
        captured = now()
        if totals:
            c.execute("INSERT INTO studio_channel_snapshots VALUES(?,?,?,?,?,?)",
                      (cid, project["yt_channel_id"], captured, totals["views"], totals["subscribers"], totals["videos"]))
        if recent is not None:
            c.execute("UPDATE studio_channel_sync SET videos_json=?,videos_at=? WHERE channel_id=?",
                      (json.dumps(recent, ensure_ascii=False), captured, cid))
        c.execute("UPDATE studio_channel_sync SET lease_until='',lease_id='',error=? WHERE channel_id=?", (error, cid))
    return "error" if error else "updated"


def tick(store):
    """One due channel per idle worker pass, even while publishing is paused."""
    from pathlib import Path
    if Path(store.web_app.config.get("DEVELOPMENT_MAINTENANCE_PATH", "/nonexistent")).exists():
        return
    purge(store)
    if store.web_app.config["PREVIEW"] or not os.getenv("GOOGLE_CLIENT_ID") or not os.getenv("GOOGLE_CLIENT_SECRET"):
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=SYNC_HOURS)).isoformat()
    due = store.one(
        "SELECT p.id FROM delamain_projects p JOIN studio_channels s ON s.project_id=p.id LEFT JOIN studio_channel_sync a ON a.channel_id=p.id WHERE s.retired=0 AND p.yt_refresh_token!='' AND p.yt_channel_id!='' AND (a.checked_at IS NULL OR a.checked_at<?) AND (a.lease_until IS NULL OR a.lease_until<?) ORDER BY COALESCE(a.checked_at,'') LIMIT 1", (cutoff, now())
    )
    if due:
        try:
            sync(store, due["id"], background=True)
        except (ValueError, OSError):
            pass


def register(app, store):
    def period():
        value = request.args.get("days", "7")
        if value not in {"1", "7", "28"}:
            raise ValueError("Choisis une période de 1, 7 ou 28 jours.")
        return int(value)

    def channel(cid):
        result = store.channel(cid)
        if not result:
            raise ValueError("Cette chaîne a été retirée ou n’existe pas.")
        return result

    @app.get("/api/studio/channel-stats")
    def channel_ranking():
        days = period()
        purge(store)
        reports = [report(store, ch, days) for ch in store.channels()]
        for result in reports:
            result["history"] = []
            result["recent_videos"] = []
        ranking = sorted((r for r in reports if r["gain"] is not None and not r["stale"] and not r["error"]), key=lambda r: r["gain"], reverse=True)
        return jsonify(channels=reports, ranking=ranking, days=days)

    @app.get("/api/studio/channels/<int:cid>/stats")
    def channel_report(cid):
        purge(store)
        return jsonify(report(store, channel(cid), period()))

    @app.post("/api/studio/channels/<int:cid>/stats/refresh")
    def channel_refresh(cid):
        channel(cid)
        result = sync(store, cid)
        return jsonify(status=result, **report(store, channel(cid), period()))
