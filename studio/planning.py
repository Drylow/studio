"""Read-only team agenda: cadence suggestions remain separate from real dates."""

from datetime import datetime, time, timedelta, timezone
import re
from flask import g, jsonify, request
from studio.domain import blockers, date
from studio.schedule import TZ, cadence_slots, in_scope, resolve_scope


def planning(store, start, days=7, scope="all", *, at=None, preview=False):
    if not isinstance(start, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start):
        raise ValueError("Choisis une date de début valide.")
    try:
        day = datetime.fromisoformat(start).date()
        first = datetime.combine(day, time(), tzinfo=TZ)
    except ValueError:
        raise ValueError("Cette date n’existe pas.")
    if not isinstance(days, int) or not 1 <= days <= 31:
        raise ValueError("Choisis une période de 1 à 31 jours.")
    end = first + timedelta(days=days)
    at = at or datetime.now(timezone.utc)
    channels = [c for c in store.channels() if in_scope(c, scope)]
    settings = store.settings()
    videos = store.videos()
    slots = []
    for c in channels:
        actual = [
            v
            for v in videos
            if v["channel_id"] == c["id"]
            and date(v["post_at"])
            and date(v["post_at"]).tzinfo
            and first <= date(v["post_at"]) < end
        ]
        for slot in cadence_slots(c, first, end):
            # A reserved date fills the same wall-clock suggestion, including DST folds.
            if any(
                abs(
                    (
                        date(v["post_at"]).astimezone(TZ).replace(tzinfo=None)
                        - slot.replace(tzinfo=None)
                    ).total_seconds()
                )
                < 900
                for v in actual
            ):
                continue
            paused = bool(settings["paused"] or c["paused"])
            slots.append(
                dict(
                    channel_id=c["id"],
                    responsible_id=c["responsible_id"],
                    post_at=slot.isoformat(),
                    kind="suggestion",
                    video_id=None,
                    title="Créneau du rythme",
                    state="En pause" if paused else "À programmer",
                    blockers=["Publication en pause"] if paused else [],
                )
            )
        for v in actual:
            slot = date(v["post_at"])
            if v["status"] in {"published", "reported"}:
                reasons = []
                state = (
                    "Publiée" if v["status"] == "published" else "Publication rapportée"
                )
            else:
                reasons = blockers(v, c, settings, automatic=True, at=max(at, slot))
                if v["status"] not in {"ready", "scheduled"}:
                    reasons.append("Vidéo encore en préparation")
                if preview:
                    reasons.append("Aperçu : publication désactivée")
                state = "Bloquée" if reasons else "Contrôles déclarés OK"
            slots.append(
                dict(
                    channel_id=c["id"],
                    responsible_id=c["responsible_id"],
                    post_at=slot.isoformat(),
                    kind="reserved",
                    video_id=v["id"],
                    title=v["title"],
                    state=state,
                    blockers=reasons,
                )
            )
    return dict(
        start=start,
        days=days,
        timezone=str(TZ),
        slots=sorted(slots, key=lambda s: (date(s["post_at"]), s["channel_id"])),
    )


def register(app, store):
    # Newly seeded channels arrive after the schema migration on a fresh database.
    with store.db() as c:
        c.execute(
            "UPDATE studio_channels SET cadence_anchor=? WHERE cadence_anchor=''",
            (datetime.now(TZ).date().isoformat(),),
        )

    @app.get("/api/studio/planning")
    def team_planning():
        scope = resolve_scope(store, request.args.get("scope"), g.user["id"])
        try:
            days = int(request.args.get("days", "7"))
        except ValueError:
            raise ValueError("Choisis une période de 1 à 31 jours.")
        return jsonify(
            planning(
                store,
                request.args.get("start") or datetime.now(TZ).date().isoformat(),
                days,
                scope,
                preview=app.config["PREVIEW"],
            )
        )
