"""Stable local cadence and shared team filters; never creates publication jobs."""

from datetime import datetime, time, timedelta, timezone
import math
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Paris")


def cadence_slots(channel, start, end):
    """Yield suggestions in [start, end), keeping wall time across DST changes.

    Nonexistent spring hours are omitted. Ambiguous autumn hours use the first
    occurrence. The anchor persists, so a two-day rhythm never resets on reload.
    """
    local_start = start.astimezone(TZ).replace(tzinfo=None)
    anchor_day = datetime.fromisoformat(
        channel.get("cadence_anchor") or local_start.date().isoformat()
    ).date()
    anchor = datetime.combine(anchor_day, time.fromisoformat(channel["post_time"]))
    step = timedelta(days=float(channel["cadence_days"]))
    index = max(0, math.floor((local_start - anchor) / step))
    local = anchor + step * index
    local_end = end.astimezone(TZ).replace(tzinfo=None)
    while local < local_end:
        slot = local.replace(tzinfo=TZ, fold=0)
        round_trip = slot.astimezone(timezone.utc).astimezone(TZ)
        if round_trip.replace(tzinfo=None) == local and start <= slot < end:
            yield slot
        local += step


def resolve_scope(store, scope, user_id):
    scope = scope or "all"
    if scope == "mine":
        return user_id
    if scope in {"all", "unassigned"}:
        return scope
    if scope not in {u["id"] for u in store.users()}:
        raise ValueError("Ce membre de l’équipe n’existe pas.")
    return scope


def in_scope(channel, scope):
    return (
        scope == "all"
        or (scope == "unassigned" and not channel.get("responsible_id"))
        or channel.get("responsible_id") == scope
    )
