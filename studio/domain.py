"""Calendar, stock and publication eligibility use the same server rules."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from studio.store import now

TZ = ZoneInfo("Europe/Paris")
STATUSES = {
    "idea",
    "research",
    "script",
    "creating",
    "review",
    "ready",
    "scheduled",
    "published",
    "reported",
    "blocked",
    "delivered",
}


def date(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def utc_date(value):
    if not value:
        return ""
    d = date(value)
    if not d or not d.tzinfo:
        raise ValueError("La date doit inclure son fuseau horaire.")
    return d.astimezone(timezone.utc).isoformat()


def fresh(video, channel, at=None):
    if channel["format"] != "news":
        return True
    d = date(video.get("event_at"))
    if not d or not d.tzinfo:
        return False
    at = at or datetime.now(timezone.utc)
    return d <= at + timedelta(minutes=5) and at - d <= timedelta(
        hours=channel["freshness_hours"]
    )


def blockers(video, channel, settings, *, automatic=False, at=None):
    out = []
    if settings["paused"] or channel["paused"]:
        out.append("Publication en pause")
    if not channel["connected"]:
        out.append("Chaîne YouTube à connecter")
    if not video.get("video_path"):
        out.append("Montage vidéo absent")
    if not video.get("thumb_path"):
        out.append("Miniature à choisir")
    if video["quality_status"] != "verified" or not video.get("render_digest"):
        out.append("Contrôle du rendu à terminer")
    if video["rights_status"] != "verified":
        out.append("Droits de réutilisation à vérifier")
    if not fresh(video, channel, at):
        out.append("Actualité périmée ou date de source absente")
    if channel["autonomy"] == "manual" and video.get("approved_digest") != video.get(
        "render_digest"
    ):
        out.append("Validation humaine requise")
    if automatic and channel["autonomy"] == "auto" and not channel["enabled"]:
        out.append("Automatisation non activée sur cette chaîne")
    if video["status"] in {"published", "reported"}:
        out.append("Vidéo déjà publiée ou publication rapportée")
    return out


def stock_eligible(v, c, at):
    scheduled_at = date(v.get("post_at"))
    eligible_at = scheduled_at if scheduled_at and scheduled_at > at else at
    return (
        v["status"] in {"ready", "scheduled"}
        and v["quality_status"] == "verified"
        and v["rights_status"] == "verified"
        and bool(v.get("video_path"))
        and bool(v.get("thumb_path"))
        and bool(v.get("render_digest"))
        and fresh(v, c, eligible_at)
        and (
            c["autonomy"] == "auto"
            or v.get("approved_digest") == v.get("render_digest")
        )
    )


def channel_summary(c, videos, at=None):
    at = at or datetime.now(timezone.utc)
    vs = [v for v in videos if v["channel_id"] == c["id"]]
    eligible = [v for v in vs if stock_eligible(v, c, at)]
    scheduled = sorted(
        [v for v in eligible if date(v["post_at"]) and date(v["post_at"]) >= at],
        key=lambda v: v["post_at"],
    )
    # Coverage stops at the first missing cadence slot, rather than claiming count*cadence days.
    local = at.astimezone(TZ)
    h, m = map(int, c["post_time"].split(":"))
    slot = local.replace(hour=h, minute=m, second=0, microsecond=0)
    if slot < local:
        slot += timedelta(days=float(c["cadence_days"]))
    covered_until = None
    for _ in range(365):
        match = next(
            (
                v
                for v in scheduled
                if abs((date(v["post_at"]) - slot).total_seconds()) < 900
            ),
            None,
        )
        if not match:
            break
        covered_until = slot
        slot += timedelta(days=float(c["cadence_days"]))
    return dict(
        c,
        ready=len(eligible),
        total=len(vs),
        producing=sum(v["status"] in {"creating", "script", "research"} for v in vs),
        awaiting_review=sum(v["status"] == "review" for v in vs),
        scheduled=len(scheduled),
        next_post=scheduled[0]["post_at"] if scheduled else "",
        days_ahead=(
            round(max(0, (covered_until - at).total_seconds() / 86400), 1)
            if covered_until
            else 0
        ),
        delivered=sum(v["status"] == "delivered" for v in vs),
        published=sum(v["status"] == "published" for v in vs),
    )


def overview(store):
    at = datetime.now(timezone.utc)
    videos = store.videos()
    settings = store.settings()
    channels = [channel_summary(c, videos, at) for c in store.channels()]
    today = at.astimezone(TZ).date()
    due = [
        v
        for v in videos
        if (date(v["post_at"]) and date(v["post_at"]).astimezone(TZ).date() == today)
        and v["status"] not in {"published", "reported"}
    ]
    alerts = []
    for c in channels:
        if not c["connected"]:
            alerts.append(
                {
                    "kind": "connection",
                    "channel_id": c["id"],
                    "title": c["name"],
                    "message": "Connexion YouTube à terminer",
                }
            )
        elif c["ready"] < c["target_stock"]:
            alerts.append(
                {
                    "kind": "stock",
                    "channel_id": c["id"],
                    "title": c["name"],
                    "message": "Stock disponible sous l’objectif",
                }
            )
    for v in videos:
        if v["status"] == "blocked":
            alerts.append(
                {
                    "kind": "blocked",
                    "video_id": v["id"],
                    "title": v["title"],
                    "message": v["error"] or "Contrôle à reprendre",
                }
            )
    return {
        "channels": channels,
        "videos": videos,
        "settings": settings,
        "today": due,
        "alerts": alerts,
        "stats": {
            "channels": len(channels),
            "ready": sum(c["ready"] for c in channels),
            "producing": sum(c["producing"] for c in channels),
            "review": sum(c["awaiting_review"] for c in channels),
            "scheduled": sum(c["scheduled"] for c in channels),
        },
        "tasks": store.rows(
            'SELECT * FROM studio_tasks ORDER BY done, due_at="", due_at, created_at DESC'
        ),
        "activity": store.rows(
            "SELECT * FROM studio_activity ORDER BY id DESC LIMIT 40"
        ),
        "users": store.users(),
        "jobs": store.rows(
            "SELECT id,kind,video_id,status,progress,message,error,created_at,updated_at FROM studio_jobs ORDER BY created_at DESC LIMIT 30"
        ),
        "worker": store.one("SELECT * FROM studio_worker WHERE id=1"),
        "server_time": now(),
    }
