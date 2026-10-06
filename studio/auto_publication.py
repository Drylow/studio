"""Release checked news immediately; keep explicit calendar reservations intact."""
from pathlib import Path
from studio.domain import blockers
from studio.store import now


def tick(store):
    app = store.web_app
    if app.config["PREVIEW"] or Path(app.config["DEVELOPMENT_MAINTENANCE_PATH"]).exists():
        return []
    settings = store.settings()
    if settings["paused"]:
        return []
    queued = []
    at = now()
    for video in store.videos():
        channel = store.channel(video["channel_id"])
        if not channel:
            continue
        scheduled = video["status"] == "scheduled" and video["post_at"] and video["post_at"] <= at
        news_ready = (channel["publication_mode"] == "news" and channel["autonomy"] == "auto"
                      and video["status"] in {"ready", "scheduled"}
                      and (not video["post_at"] or video["post_at"] <= at))
        if (scheduled or news_ready) and not blockers(video, channel, settings, automatic=True):
            queued.append(store.enqueue("publish", video["id"], {"actor": "Delamain"}))
    return queued
